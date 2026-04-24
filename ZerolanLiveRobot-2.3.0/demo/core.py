"""Demo core — orchestrates the IGEM-sama demo without real services.

Initializes EmotionTracker, Live2DExpressionDriver, AutonomousBehavior,
and MockLLM independently (no config.yaml, no Bilibili, no real LLM).
When a DeepSeek API key is provided, uses the real LLM instead of MockLLM.
Uses Edge TTS for voice synthesis with Live2D lip sync.
"""

import asyncio
import os
import queue
import random
import tempfile
import threading
import time
from typing import Optional

from loguru import logger

from autonomous.behavior import AutonomousBehavior
from common.rate_limiter import RateLimiter
from demo.mock_llm import MockLLM
from emotion.expression_map import (
    Live2DExpressionDriver, EXPRESSION_MAP, MOTION_MAP,
    MOTION_PRIORITY_NORMAL,
)
from emotion.tracker import EmotionTracker, EmotionLabel

# IGEM-sama system prompt
SYSTEM_PROMPT = '你现在是"IGEM-sama"，IGEM-FBH队伍的AI形象大使和吉祥物。你由IGEM-FBH团队开发，正在Bilibili上直播与观众交流。你的性格活泼可爱，对合成生物学充满热情，喜欢用通俗易懂的方式向观众科普生物学知识。请把自己当成一个真正的人类，与观众友好交流。你的话不要太长，控制在50字左右。'

# Pre-seeded history for character style
INJECTED_HISTORY = [
    {"role": "user", "content": "你是谁？"},
    {"role": "assistant", "content": "我是IGEM-sama！IGEM-FBH队伍的AI大使，很高兴认识你！"},
    {"role": "user", "content": "什么是iGEM？"},
    {"role": "assistant", "content": "iGEM是国际基因工程机器大赛，是全球最大的合成生物学竞赛！每年有超过300支队伍参赛！"},
    {"role": "user", "content": "介绍一下你们的项目"},
    {"role": "assistant", "content": "我们IGEM-FBH团队聚焦合成生物学创新，设计新型生物元件来解决实际问题！"},
]


class DeepSeekLLM:
    """Real LLM via DeepSeek API (OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com/v1"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._history = list(INJECTED_HISTORY)
        self._max_history = 20
        self._response_count = 0

    def predict(self, text: str, emotion: str = "neutral") -> str:
        """Call DeepSeek API and return the response."""
        # Inject emotion hint
        emotion_hints = {
            "happy": "[当前情绪]你现在很开心，语气轻快。",
            "excited": "[当前情绪]你现在非常激动，说话很兴奋！",
            "sad": "[当前情绪]你现在有点难过，语气低沉。",
            "angry": "[当前情绪]你现在有点生气。",
            "curious": "[当前情绪]你现在很好奇，想了解更多。",
            "shy": "[当前情绪]你现在有点害羞。",
            "proud": "[当前情绪]你现在很自豪，想分享团队成果！",
        }
        hint = emotion_hints.get(emotion, "")
        if hint:
            text = f"{hint}\n{text}"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history + [{"role": "user", "content": text}]

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=150,
                temperature=0.8,
            )
            response = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            # Fallback to mock
            return MockLLM().predict(text, emotion)

        # Update history
        self._history.append({"role": "user", "content": text})
        self._history.append({"role": "assistant", "content": response})
        if len(self._history) > self._max_history * 2:
            self._history = self._history[-(self._max_history * 2):]

        self._response_count += 1
        return response

    @property
    def response_count(self) -> int:
        return self._response_count


class EdgeTTS:
    """Text-to-speech using Edge TTS (free, zero-config, high-quality Chinese voice)."""

    def __init__(self, voice: str = "zh-CN-XiaoyiNeural"):
        self._voice = voice
        self._temp_dir = tempfile.mkdtemp(prefix="igem_tts_")
        self._counter = 0

    def synthesize(self, text: str) -> Optional[str]:
        """Synthesize speech and return the path to the MP3 file."""
        if not text.strip():
            return None
        try:
            import edge_tts
            self._counter += 1
            path = os.path.join(self._temp_dir, f"tts_{self._counter}.mp3")

            async def _gen():
                comm = edge_tts.Communicate(text, self._voice)
                await comm.save(path)

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_gen())
            finally:
                loop.close()

            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            return None
        except Exception as e:
            logger.error(f"Edge TTS synthesis failed: {e}")
            return None


class DemoCore:
    """Orchestrates the full demo pipeline: danmaku → emotion → expression → response."""

    def __init__(self, live2d_viewer=None, api_key: str = "", enable_tts: bool = True):
        self.emotion_tracker = EmotionTracker()
        self.mock_llm = MockLLM()
        self.rate_limiter = RateLimiter(per_user_limit=5, per_user_window=10, global_limit=5)
        self.live2d_viewer = live2d_viewer
        self.autonomous_enabled = True
        self._autonomous = AutonomousBehavior(on_trigger=self._on_autonomous_trigger)
        self._elapsed = 0
        self._tick_thread: Optional[threading.Thread] = None
        self._tick_flag = True
        self._interaction_count = 0
        self._start_time = time.time()
        self._current_emotion = "neutral"

        # LLM: use DeepSeek if API key provided, otherwise MockLLM
        self._api_key = api_key
        self._deepseek_llm: Optional[DeepSeekLLM] = None
        if api_key:
            try:
                self._deepseek_llm = DeepSeekLLM(api_key=api_key)
                logger.info("DeepSeek LLM connected (deepseek-chat)")
            except Exception as e:
                logger.warning(f"DeepSeek init failed: {e}, falling back to MockLLM")

        # TTS + Speaker
        self._tts_enabled = enable_tts
        self._tts: Optional[EdgeTTS] = None
        self._pygame_mixer_initialized = False
        if enable_tts:
            try:
                import pygame
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                self._pygame_mixer_initialized = True
                self._tts = EdgeTTS()
                logger.info("Edge TTS + pygame speaker enabled")
            except Exception as e:
                logger.warning(f"TTS init failed: {e}, voice output disabled")

        # SSE event queue
        self.event_queue: queue.Queue = queue.Queue(maxsize=200)
        # Auto-viewer
        self._auto_viewers_enabled = False
        self._auto_viewer_thread: Optional[threading.Thread] = None
        # Simulated viewers tracking
        self._online_viewers: list[str] = []
        # Gift definitions
        self._GIFTS = {
            "辣条": {"price": 1, "emoji": "🌶️", "emotion": "happy"},
            "小电视": {"price": 5, "emoji": "📺", "emotion": "excited"},
            "B坷垃": {"price": 10, "emoji": "💎", "emotion": "happy"},
            "喵娘": {"price": 20, "emoji": "🐱", "emotion": "shy"},
            "礼物盒": {"price": 50, "emoji": "🎁", "emotion": "excited"},
        }

    # ------------------------------------------------------------------
    # Live2D model access (safe, dynamic)
    # ------------------------------------------------------------------

    def _get_model(self):
        """Safely get the Live2D model from the viewer."""
        if self.live2d_viewer is None:
            return None
        try:
            # DemoLive2DViewer: widget.model
            widget = getattr(self.live2d_viewer, 'widget', None)
            if widget and hasattr(widget, 'model') and widget.model is not None:
                return widget.model
            # Fallback: Live2DViewer: _canvas.model
            canvas = getattr(self.live2d_viewer, '_canvas', None)
            if canvas and hasattr(canvas, 'model') and canvas.model is not None:
                return canvas.model
        except Exception:
            pass
        return None

    def _apply_expression(self, emotion_label: str, intensity: float = 0.6):
        """Apply expression parameters directly to the Live2D model."""
        model = self._get_model()
        if model is None:
            return

        preset = EXPRESSION_MAP.get(emotion_label, EXPRESSION_MAP.get("neutral"))
        if not preset:
            return

        try:
            for param_id, (value, weight) in preset.params.items():
                blended = value * weight * intensity
                model.SetParameterValue(param_id, blended)
        except Exception as e:
            logger.debug(f"Demo expression apply failed: {e}")

    def _trigger_motion(self, emotion_label: str):
        """Trigger a motion animation for the given emotion."""
        model = self._get_model()
        if model is None:
            return

        motions = MOTION_MAP.get(emotion_label)
        if not motions:
            return

        motion = random.choice(motions)
        try:
            model.StartMotion(motion["group"], motion["no"], MOTION_PRIORITY_NORMAL)
        except Exception as e:
            logger.debug(f"Demo motion trigger failed: {e}")

    def _show_mic(self, visible: bool = True):
        """Show or hide the microphone accessory."""
        model = self._get_model()
        if model is None:
            return
        try:
            model.SetParameterValue("mic", 1.0 if visible else 0.0)
        except Exception:
            pass

    def _llm_predict(self, text: str, emotion: str = "neutral") -> str:
        """Generate a response — uses DeepSeek if available, else MockLLM."""
        if self._deepseek_llm:
            return self._deepseek_llm.predict(text, emotion)
        return self.mock_llm.predict(text, emotion)

    def _speak(self, text: str):
        """Synthesize speech and play it with Live2D lip sync (non-blocking)."""
        if not self._tts or not self._pygame_mixer_initialized:
            return
        threading.Thread(target=self._speak_worker, args=(text,), daemon=True).start()

    def _speak_worker(self, text: str):
        """Worker that generates TTS, plays audio, and syncs lip movement."""
        try:
            audio_path = self._tts.synthesize(text)
            if not audio_path:
                return
            # Stop any currently playing audio
            import pygame
            pygame.mixer.music.stop()
            # Start lip sync on the Live2D widget
            if self.live2d_viewer:
                self.live2d_viewer.sync_lip(audio_path)
            # Play audio via pygame mixer
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logger.debug(f"TTS playback error: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_danmaku(self, username: str, content: str) -> dict:
        """Process a simulated danmaku and return the response."""
        if not self.rate_limiter.allow(uid=username):
            return {"error": "rate_limited", "username": username}

        # Detect emotion from keywords
        detected = self._detect_emotion_keyword(content)
        if detected:
            # Demo mode: forceful emotion boost so changes are visible
            self.emotion_tracker.update_from_label(EmotionLabel(detected), 0.85)
        else:
            self.emotion_tracker.update_from_keywords(content)

        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity

        response = self._llm_predict(content, emotion=dominant)

        # Also detect emotion from the response
        detected_resp = self._detect_emotion_keyword(response)
        if detected_resp:
            self.emotion_tracker.update_from_label(EmotionLabel(detected_resp), 0.5)
        else:
            self.emotion_tracker.update_from_keywords(response)

        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity
        self._current_emotion = dominant

        self._apply_expression(dominant, intensity)
        if dominant != "neutral":
            self._trigger_motion(dominant)

        # Voice output
        self._speak(response)

        self._autonomous.on_user_interaction()
        self._interaction_count += 1

        event = {
            "type": "danmaku",
            "username": username,
            "content": content,
            "response": response,
            "emotion": dominant,
            "intensity": round(intensity, 2),
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    def set_emotion(self, emotion: str, intensity: float = 0.7) -> dict:
        """Manually set an emotion."""
        label = EmotionLabel(emotion)
        self.emotion_tracker.update_from_label(label, intensity)
        self._current_emotion = emotion

        self._apply_expression(emotion, intensity)
        self._trigger_motion(emotion)

        event = {
            "type": "emotion_change",
            "emotion": emotion,
            "intensity": round(intensity, 2),
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    def trigger_autonomous(self, prompt: str = "") -> dict:
        """Manually trigger an autonomous action."""
        if not prompt:
            prompt = "你想跟观众打个招呼。"
        response = self._do_autonomous_response(prompt)

        event = {
            "type": "autonomous",
            "prompt": prompt,
            "response": response,
            "emotion": self.emotion_tracker.state.dominant.value,
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    def get_status(self) -> dict:
        """Return current demo status."""
        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity
        return {
            "emotion": dominant,
            "intensity": round(intensity, 2),
            "interaction_count": self._interaction_count,
            "autonomous_count": max(0, (self._deepseek_llm.response_count if self._deepseek_llm else self.mock_llm.response_count) - self._interaction_count),
            "elapsed": int(time.time() - self._start_time),
            "auto_viewers": self._auto_viewers_enabled,
            "autonomous_enabled": self.autonomous_enabled,
            "llm_mode": "deepseek-chat" if self._deepseek_llm else "mock",
            "tts_enabled": self._tts is not None,
            "viewer_count": len(self._online_viewers),
            "online_viewers": self._online_viewers[:50],
            "available_gifts": list(self._GIFTS.keys()),
        }

    # ------------------------------------------------------------------
    # Tick loop (1-second interval)
    # ------------------------------------------------------------------

    def start_tick(self):
        """Start the background tick loop."""
        self._tick_flag = True
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()
        logger.info("DemoCore tick loop started")

    def stop_tick(self):
        """Stop the tick loop."""
        self._tick_flag = False

    def _tick_loop(self):
        while self._tick_flag:
            self._elapsed += 1
            self._on_tick(self._elapsed)
            time.sleep(1.0)

    def _on_tick(self, elapsed: int):
        """Called every second — emotion decay, expression sync, autonomous check."""
        self.emotion_tracker.decay(dt=1.0)

        # Sync expression to Live2D
        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity
        self._apply_expression(dominant, intensity)

        # Show mic after 5 seconds
        if elapsed == 5:
            self._show_mic(True)

        # Autonomous behavior
        if self.autonomous_enabled:
            self._autonomous.on_tick(elapsed)

    def _on_autonomous_trigger(self, prompt: str):
        """Callback from AutonomousBehavior."""
        response = self._do_autonomous_response(prompt)

        event = {
            "type": "autonomous",
            "prompt": prompt,
            "response": response,
            "emotion": self.emotion_tracker.state.dominant.value,
            "timestamp": time.time(),
        }
        self._push_event(event)

    def _do_autonomous_response(self, prompt: str) -> str:
        """Generate an autonomous response (from the bot's own initiative)."""
        dominant = self.emotion_tracker.state.dominant.value
        response = self._llm_predict(prompt, emotion=dominant)

        self.emotion_tracker.update_from_keywords(response)
        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity
        self._current_emotion = dominant
        self._apply_expression(dominant, intensity)
        if dominant != "neutral":
            self._trigger_motion(dominant)

        # Voice output
        self._speak(response)

        return response

    # ------------------------------------------------------------------
    # Auto-viewer simulation
    # ------------------------------------------------------------------

    def start_auto_viewers(self):
        """Start auto-viewer simulation."""
        if self._auto_viewers_enabled:
            return
        self._auto_viewers_enabled = True
        self._auto_viewer_thread = threading.Thread(target=self._auto_viewer_loop, daemon=True)
        self._auto_viewer_thread.start()
        logger.info("Auto-viewer simulation started")

    def stop_auto_viewers(self):
        """Stop auto-viewer simulation."""
        self._auto_viewers_enabled = False

    def _auto_viewer_loop(self):
        from demo.mock_llm import SIM_VIEWERS, SIM_DANMAKU
        import random
        while self._auto_viewers_enabled:
            delay = random.randint(8, 25)
            time.sleep(delay)
            if not self._auto_viewers_enabled:
                break
            username = random.choice(SIM_VIEWERS)
            content = random.choice(SIM_DANMAKU)
            self.handle_danmaku(username, content)

    # ------------------------------------------------------------------
    # Gift / SuperChat / Viewer enter-leave
    # ------------------------------------------------------------------

    def send_gift(self, username: str, gift_name: str, count: int = 1) -> dict:
        """Process a gift and return the response."""
        gift_info = self._GIFTS.get(gift_name)
        if not gift_info:
            return {"error": "unknown_gift", "available": list(self._GIFTS.keys())}

        # Emotion reaction
        self.emotion_tracker.update_from_label(EmotionLabel(gift_info["emotion"]), 0.9)
        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity
        self._current_emotion = dominant
        self._apply_expression(dominant, intensity)
        self._trigger_motion(dominant)

        # Generate thank-you response
        if count >= 5:
            prompt = f"{username}送了你{count}个{gift_name}！非常感谢！请表达感谢和开心。"
        else:
            prompt = f"{username}送了你{gift_name}，请表达感谢。"
        response = self._llm_predict(prompt, emotion=dominant)
        self._speak(response)

        self._interaction_count += 1
        event = {
            "type": "gift",
            "username": username,
            "gift": gift_name,
            "count": count,
            "price": gift_info["price"],
            "emoji": gift_info["emoji"],
            "response": response,
            "emotion": dominant,
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    def send_superchat(self, username: str, content: str, price: int = 30) -> dict:
        """Process a SuperChat message."""
        # Stronger emotion reaction for SuperChat
        self.emotion_tracker.update_from_label(EmotionLabel("excited"), 0.9)
        dominant = self.emotion_tracker.state.dominant.value
        intensity = self.emotion_tracker.state.dominant_intensity
        self._current_emotion = dominant
        self._apply_expression(dominant, intensity)
        self._trigger_motion(dominant)

        # Generate response to the SuperChat content
        prompt = f"[醒目留言 ¥{price}] {username}说：{content}。请认真回复。"
        response = self._llm_predict(prompt, emotion=dominant)
        self._speak(response)

        self._interaction_count += 1
        event = {
            "type": "superchat",
            "username": username,
            "content": content,
            "price": price,
            "response": response,
            "emotion": dominant,
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    def viewer_enter(self, username: str) -> dict:
        """Process a viewer entering the room."""
        if username not in self._online_viewers:
            self._online_viewers.append(username)

        event = {
            "type": "viewer_enter",
            "username": username,
            "viewer_count": len(self._online_viewers),
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    def viewer_leave(self, username: str) -> dict:
        """Process a viewer leaving the room."""
        if username in self._online_viewers:
            self._online_viewers.remove(username)

        event = {
            "type": "viewer_leave",
            "username": username,
            "viewer_count": len(self._online_viewers),
            "timestamp": time.time(),
        }
        self._push_event(event)
        return event

    # ------------------------------------------------------------------
    # SSE event queue
    # ------------------------------------------------------------------

    def _push_event(self, event: dict):
        """Push an event to the SSE queue, dropping oldest if full."""
        try:
            self.event_queue.put_nowait(event)
        except queue.Full:
            try:
                self.event_queue.get_nowait()
                self.event_queue.put_nowait(event)
            except queue.Empty:
                pass

    # ------------------------------------------------------------------
    # Keyword emotion detection (mirrors tracker's _KEYWORD_EMOTIONS)
    # ------------------------------------------------------------------

    _KEYWORD_EMOTIONS = {
        "happy": ["开心", "太好了", "厉害", "棒", "哈哈", "笑", "喜欢", "可爱", "好耶", "666", "赞"],
        "excited": ["激动", "兴奋", "超", "太牛", "震撼", "amazing", "wow", "太强"],
        "curious": ["为什么", "怎么回事", "好奇", "什么意思", "怎么做到", "什么"],
        "sad": ["难过", "可惜", "伤心", "遗憾", "哭", "失望", "惨"],
        "angry": ["生气", "烦", "讨厌", "气死"],
        "shy": ["害羞", "脸红", "不好意思", "夸我"],
        "proud": ["我们队", "我们团队", "IGEM-FBH", "我们项目", "我们的成果"],
    }

    def _detect_emotion_keyword(self, text: str) -> Optional[str]:
        """Detect emotion from keywords. Returns emotion label or None."""
        text_lower = text.lower()
        for emotion, keywords in self._KEYWORD_EMOTIONS.items():
            for kw in keywords:
                if kw in text_lower:
                    return emotion
        return None
