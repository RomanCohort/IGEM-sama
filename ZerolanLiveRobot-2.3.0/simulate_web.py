"""IGEM-sama Web 模拟直播间

在浏览器中模拟弹幕互动，无需 B站/OBS/TTS/ASR 等外部服务。
可视化情绪、人格演化、短期记忆等全部6个新模块。

Usage: python simulate_web.py
然后浏览器打开 http://127.0.0.1:8888
"""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

try:
    from flask import Flask, jsonify, request, Response, send_from_directory
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logger.error("Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Lightweight module state (no full bot needed)
# ---------------------------------------------------------------------------

class SimulationState:
    """Holds all lightweight module instances for the web simulation."""

    def __init__(self):
        self.chat_messages = []  # [{id, role, content, time, emotion?}]
        self.emotion_tracker = None
        self.personality_evolution = None
        self.short_term_memory = None
        self.llm_available = False
        self.llm_predict_fn = None  # Set if LLM API works
        self._last_decay = time.time()
        self._last_personality_tick = time.time()

    def init_modules(self):
        """Initialize all lightweight modules."""
        # Emotion tracker
        from emotion.tracker import EmotionTracker
        self.emotion_tracker = EmotionTracker()

        # Personality evolution
        from personality.config import PersonalityEvolutionConfig
        from personality.personality_state import PersonalityEvolution
        evo_config = PersonalityEvolutionConfig(enable=True)
        self.personality_evolution = PersonalityEvolution(evo_config)

        # Short-term memory
        from memory.short_term import ShortTermMemory, ShortTermMemoryConfig
        stm_config = ShortTermMemoryConfig(enable=True)
        self.short_term_memory = ShortTermMemory(stm_config)

        # Try LLM connection
        self._try_init_llm()

        logger.info("All lightweight modules initialized")

    def _try_init_llm(self):
        """Try to set up LLM prediction function."""
        try:
            from manager.config_manager import get_config
            config = get_config()
            llm_config = config.pipeline.llm
            if llm_config.enable and llm_config.predict_url:
                from pipeline.llm.config import LLMPipelineConfig
                from pipeline.llm.llm_sync import LLMSyncPipeline
                llm_cfg = LLMPipelineConfig(
                    model_id=llm_config.model_id,
                    api_key=llm_config.api_key,
                    openai_format=True,
                    predict_url=llm_config.predict_url,
                    stream_predict_url=llm_config.stream_predict_url,
                )
                self._llm_pipeline = LLMSyncPipeline(llm_cfg)
                self.llm_available = True
                logger.info(f"LLM connected: {llm_config.model_id}")
            else:
                self.llm_available = False
        except Exception as e:
            logger.warning(f"LLM not available: {e}")
            self.llm_available = False

    def tick(self):
        """Periodic tick: decay emotions, evolve personality."""
        now = time.time()
        dt = now - self._last_decay
        self._last_decay = now

        # Emotion decay
        if self.emotion_tracker:
            self.emotion_tracker.decay(dt=dt)

        # Personality evolution (tick every ~1s)
        pdt = now - self._last_personality_tick
        if pdt >= 1.0 and self.personality_evolution and self.emotion_tracker:
            self.personality_evolution.evolve(
                self.emotion_tracker.state.intensities, dt=pdt
            )
            self._last_personality_tick = now


state = SimulationState()


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    try:
        from flask_cors import CORS
        CORS(app)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Serve the simulation HTML
    # ------------------------------------------------------------------
    @app.route("/")
    def index():
        return SIMULATION_HTML

    # ------------------------------------------------------------------
    # Serve Live2D model static files
    # ------------------------------------------------------------------
    @app.route("/live2d/<path:filename>")
    def live2d_static(filename):
        model_dir = Path(__file__).parent / "resources" / "static" / "models" / "live2d"
        return send_from_directory(str(model_dir), filename)

    # ------------------------------------------------------------------
    # Live2D Expression API
    # ------------------------------------------------------------------
    @app.route("/api/live2d/expression", methods=["POST"])
    def live2d_expression():
        """Return expression parameters and motion for a given emotion."""
        data = request.json or {}
        emotion = data.get("emotion", "neutral")
        intensity = data.get("intensity", 0.6)

        from emotion.expression_map import EXPRESSION_MAP, MOTION_MAP
        import random

        # Get expression parameters
        preset = EXPRESSION_MAP.get(emotion, EXPRESSION_MAP.get("neutral"))
        params = {}
        if preset:
            for param_id, (value, weight) in preset.params.items():
                scaled_weight = weight * intensity
                blended_value = value * scaled_weight
                params[param_id] = [round(blended_value, 4), round(scaled_weight, 4)]

        # Get motion
        motion = None
        motions = MOTION_MAP.get(emotion)
        if motions:
            m = random.choice(motions)
            motion = {"group": m["group"], "no": m["no"]}

        return jsonify({
            "emotion": emotion,
            "intensity": intensity,
            "params": params,
            "motion": motion,
        })

    # ------------------------------------------------------------------
    # Status API
    # ------------------------------------------------------------------
    @app.route("/api/status")
    def api_status():
        s = state
        emotion_data = {}
        dominant = "neutral"
        dominant_intensity = 0.0

        if s.emotion_tracker:
            emotion_data = s.emotion_tracker.state.intensities
            dominant = s.emotion_tracker.state.dominant.value
            dominant_intensity = s.emotion_tracker.state.dominant_intensity

        personality_data = {}
        if s.personality_evolution:
            ps = s.personality_evolution.get_state()
            for name, trait in ps.traits.items():
                personality_data[name] = round(trait.value, 4)

        stm_info = {"enabled": False, "summaries": 0, "context": ""}
        if s.short_term_memory:
            stm_info = {
                "enabled": True,
                "summaries": len(s.short_term_memory._summaries),
                "context": s.short_term_memory.build_summary_context()[:200] if s.short_term_memory._summaries else "",
            }

        # Tick for decay/evolution
        s.tick()

        return jsonify({
            "running": True,
            "llm_available": s.llm_available,
            "emotion": {
                "dominant": dominant,
                "intensity": round(dominant_intensity, 3),
                "all": {k: round(v, 3) for k, v in emotion_data.items()},
            },
            "personality": personality_data,
            "short_term_memory": stm_info,
            "message_count": len(s.chat_messages),
            "modules": {
                "emotion": s.emotion_tracker is not None,
                "personality": s.personality_evolution is not None,
                "short_term_memory": s.short_term_memory is not None,
                "lip_sync": True,  # Always available in simulation
                "voice_clone": False,  # Needs RVC model
                "perception": False,  # Needs OCR/ImgCap
                "game_loop": False,  # Needs game
            },
        })

    # ------------------------------------------------------------------
    # Chat API
    # ------------------------------------------------------------------
    @app.route("/api/chat/send", methods=["POST"])
    def chat_send():
        """Send a danmaku message and get IGEM-sama's response."""
        data = request.json or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "Empty message"}), 400

        s = state

        # Update emotion from message
        if s.emotion_tracker:
            s.emotion_tracker.update_from_keywords(text)

        # Add user message
        user_msg = {
            "id": str(uuid.uuid4())[:8],
            "role": "user",
            "content": text,
            "time": time.time(),
            "emotion": s.emotion_tracker.state.dominant.value if s.emotion_tracker else "neutral",
        }
        s.chat_messages.append(user_msg)

        # Get LLM response
        response_text = ""
        personality_hint = ""

        if s.llm_available:
            try:
                # Build prompt
                base_prompt = '你现在是"IGEM-sama"，IGEM-FBH队伍的AI形象大使和吉祥物。你由IGEM-FBH团队开发。你的性格活泼可爱，对合成生物学充满热情，喜欢用通俗易懂的方式向观众科普生物学知识。请把自己当成一个真正的人类，与观众友好交流。你的话不要太长，控制在50字左右。'

                # Add personality dynamic prompt
                if s.personality_evolution:
                    dynamic_prompt = s.personality_evolution.build_system_prompt(base_prompt)
                else:
                    dynamic_prompt = base_prompt

                # Add emotion hint
                if s.emotion_tracker:
                    emotion_hint = s.emotion_tracker.get_emotion_prompt_hint()
                    if emotion_hint:
                        dynamic_prompt += f"\n{emotion_hint}"

                # Call LLM
                from zerolan.data.pipeline.llm import LLMQuery, Conversation, RoleEnum
                danmaku_text = f'你收到了一条弹幕，\n用户"模拟观众"说：\n{text}'
                query = LLMQuery(
                    text=danmaku_text,
                    history=[Conversation(role=RoleEnum.system, content=dynamic_prompt)],
                )
                prediction = s._llm_pipeline.predict(query)
                if prediction and prediction.response:
                    response_text = prediction.response
                else:
                    response_text = "(LLM未返回内容)"
            except Exception as e:
                logger.error(f"LLM error: {e}")
                response_text = f"(LLM调用失败: {str(e)[:50]})"
        else:
            # Fallback responses
            response_text = _fallback_response(text)

        # Get personality state for display
        if s.personality_evolution:
            ps = s.personality_evolution.get_state()
            lively = ps.traits.get("lively")
            if lively and lively.value > 0.8:
                personality_hint = f"[活泼度{lively.value:.0%}]"

        # Add bot message
        bot_msg = {
            "id": str(uuid.uuid4())[:8],
            "role": "assistant",
            "content": response_text,
            "time": time.time(),
            "personality_hint": personality_hint,
        }
        s.chat_messages.append(bot_msg)

        # Evolve personality based on this interaction
        if s.personality_evolution and s.emotion_tracker:
            s.personality_evolution.evolve(
                s.emotion_tracker.state.intensities, dt=30
            )

        return jsonify({
            "ok": True,
            "user_message": user_msg,
            "bot_message": bot_msg,
            "emotion": {
                "dominant": s.emotion_tracker.state.dominant.value if s.emotion_tracker else "neutral",
                "intensity": round(s.emotion_tracker.state.dominant_intensity, 3) if s.emotion_tracker else 0,
            },
        })

    # ------------------------------------------------------------------
    # Emotion control
    # ------------------------------------------------------------------
    @app.route("/api/emotion/set", methods=["POST"])
    def emotion_set():
        """Manually set an emotion."""
        data = request.json or {}
        emotion = data.get("emotion", "neutral")
        intensity = data.get("intensity", 0.8)

        s = state
        if s.emotion_tracker:
            from emotion.tracker import EmotionLabel
            try:
                label = EmotionLabel(emotion)
                s.emotion_tracker.update_from_label(label, intensity)
            except ValueError:
                return jsonify({"error": f"Unknown emotion: {emotion}"}), 400

        # Also evolve personality
        if s.personality_evolution and s.emotion_tracker:
            s.personality_evolution.evolve(
                s.emotion_tracker.state.intensities, dt=30
            )

        return jsonify({"ok": True, "emotion": emotion, "intensity": intensity})

    # ------------------------------------------------------------------
    # Chat history
    # ------------------------------------------------------------------
    @app.route("/api/chat/history")
    def chat_history():
        """Get recent chat messages."""
        messages = state.chat_messages[-50:]  # Last 50
        return jsonify({"messages": messages, "total": len(state.chat_messages)})

    # ------------------------------------------------------------------
    # Personality detail
    # ------------------------------------------------------------------
    @app.route("/api/personality/detail")
    def personality_detail():
        """Get detailed personality state with display names."""
        s = state
        if not s.personality_evolution:
            return jsonify({"error": "Personality not available"}), 503

        ps = s.personality_evolution.get_state()
        from personality.prompt_builder import PersonalityPromptBuilder
        builder = PersonalityPromptBuilder()

        traits = []
        display_names = {
            "lively": "活泼", "tsundere": "傲娇", "knowledgeable": "博学",
            "playful": "调皮", "warm": "温柔", "scientific": "科普",
        }
        for name, trait in ps.traits.items():
            desc = builder._get_trait_description(name, trait.value)
            traits.append({
                "name": name,
                "display_name": display_names.get(name, name),
                "value": round(trait.value, 4),
                "default_value": round(trait.default_value, 4),
                "delta": round(trait.value - trait.default_value, 4),
                "description": desc,
            })

        prompt_ext = builder.build_prompt_extension(ps)

        return jsonify({
            "traits": traits,
            "interaction_count": ps.interaction_count,
            "prompt_extension": prompt_ext,
        })

    # ------------------------------------------------------------------
    # Short-term memory detail
    # ------------------------------------------------------------------
    @app.route("/api/memory/short_term")
    def memory_short_term():
        """Get short-term memory status."""
        s = state
        if not s.short_term_memory:
            return jsonify({"error": "STM not available"}), 503

        summaries = []
        for entry in s.short_term_memory._summaries:
            summaries.append({
                "text": entry.summary_text[:200],
                "message_count": entry.message_count,
                "topics": entry.topics,
            })

        return jsonify({
            "enabled": s.short_term_memory._config.enable,
            "summary_count": len(summaries),
            "summaries": summaries,
            "context": s.short_term_memory.build_summary_context(),
        })

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    @app.route("/api/reset", methods=["POST"])
    def reset_simulation():
        """Reset all simulation state."""
        state.chat_messages.clear()
        if state.emotion_tracker:
            from emotion.tracker import EmotionState
            state.emotion_tracker.state = EmotionState()
        if state.personality_evolution:
            from personality.config import PersonalityEvolutionConfig
            from personality.personality_state import PersonalityEvolution
            state.personality_evolution = PersonalityEvolution(
                PersonalityEvolutionConfig(enable=True)
            )
        if state.short_term_memory:
            state.short_term_memory.reset()
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Viseme demo API
    # ------------------------------------------------------------------
    @app.route("/api/demo/viseme")
    def demo_viseme():
        """Demo viseme classification results."""
        from services.live2d.viseme_engine import VisemeEngine
        engine = VisemeEngine()

        test_cases = [
            ("静默", 0.01, {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'centroid': 0.5, 'flatness': 0.5}),
            ("A音", 0.3, {'low': 0.6, 'mid': 0.3, 'high': 0.1, 'centroid': 0.3, 'flatness': 0.3}),
            ("I音", 0.2, {'low': 0.2, 'mid': 0.3, 'high': 0.5, 'centroid': 0.7, 'flatness': 0.4}),
            ("U音", 0.15, {'low': 0.7, 'mid': 0.2, 'high': 0.1, 'centroid': 0.2, 'flatness': 0.6}),
            ("E音", 0.25, {'low': 0.3, 'mid': 0.4, 'high': 0.3, 'centroid': 0.5, 'flatness': 0.4}),
            ("O音", 0.2, {'low': 0.4, 'mid': 0.4, 'high': 0.2, 'centroid': 0.4, 'flatness': 0.5}),
        ]

        results = []
        for name, rms, spectral in test_cases:
            is_speaking = rms > 0.02
            params = engine.process_frame(rms, spectral, is_speaking)
            viseme = engine.get_current_viseme()
            results.append({
                "name": name,
                "viseme": viseme,
                "mouth_open": round(params.get("ParamMouthOpenY", 0), 3),
                "mouth_form": round(params.get("ParamMouthForm", 0), 3),
                "speaking": is_speaking,
            })

        return jsonify({"results": results})

    return app


def _fallback_response(text: str) -> str:
    """Generate a simple fallback response when LLM is not available."""
    text_lower = text.lower()

    if any(kw in text_lower for kw in ["你好", "嗨", "hello", "hi"]):
        return "你好呀！我是IGEM-sama！很高兴认识你！"
    elif any(kw in text_lower for kw in ["是谁", "你是谁", "who"]):
        return "我是IGEM-sama！IGEM-FBH队伍的AI形象大使！"
    elif any(kw in text_lower for kw in ["项目", "project", "做什么"]):
        return "我们IGEM-FBH正在做合成生物学的创新研究哦！"
    elif any(kw in text_lower for kw in ["igem", "比赛", "竞赛"]):
        return "iGEM是国际遗传工程机器设计大赛，超级有趣！"
    elif any(kw in text_lower for kw in ["厉害", "棒", "666", "nb"]):
        return "谢谢夸奖！嘿嘿~"
    elif any(kw in text_lower for kw in ["生物学", "合成", "生物"]):
        return "合成生物学超酷的！用工程方法设计生物系统！"
    else:
        responses = [
            "嗯嗯，我听到了！",
            "有趣的话题呢！",
            "让我想想...嗯！",
            "哇，你说的好有道理！",
            "这个我知道！但让我查查知识库~",
        ]
        import hashlib
        idx = int(hashlib.md5(text.encode()).hexdigest()[:8], 16) % len(responses)
        return responses[idx]


# ---------------------------------------------------------------------------
# Frontend HTML
# ---------------------------------------------------------------------------

SIMULATION_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IGEM-sama 模拟直播间</title>
<!-- Live2D: Cubism Core SDK -->
<script src="https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"></script>
<!-- PixiJS -->
<script src="https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js"></script>
<!-- pixi-live2d-display (Cubism4) -->
<script src="https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js"></script>
<style>
:root {
  --bg: #0a0e14; --bg2: #0f1419; --card: #131820; --card2: #1a1f28;
  --border: #252b35; --text: #e6edf3; --muted: #6b7688; --dim: #4a5568;
  --accent: #ff6b8a; --accent2: #c678dd; --accent3: #61afef;
  --success: #3fb950; --warn: #d29922; --danger: #f85149;
  --pink: #ff79c6; --blue: #8be9fd; --purple: #bd93f9;
  --orange: #ffb86c; --green: #50fa7b; --cyan: #8be9fd;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system,'Segoe UI','PingFang SC',sans-serif; background:var(--bg); color:var(--text); height:100vh; overflow:hidden; }

/* Layout: 4-column grid */
.app { display:grid; grid-template-columns:280px 380px 1fr 300px; grid-template-rows:56px 1fr; height:100vh; }

/* Header */
.header { grid-column:1/-1; background:var(--card); border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; padding:0 24px; }
.header-left { display:flex; align-items:center; gap:16px; }
.header h1 { font-size:18px; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.badge { font-size:11px; padding:3px 10px; border-radius:12px; background:var(--success); color:#000; font-weight:600; }
.badge.off { background:var(--border); color:var(--muted); }
.header-right { display:flex; align-items:center; gap:12px; font-size:13px; color:var(--muted); }
.header-right .dot { width:8px; height:8px; border-radius:50%; background:var(--success); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Left panel - modules */
.left-panel { background:var(--card); border-right:1px solid var(--border); overflow-y:auto; padding:12px; }
.section { margin-bottom:14px; }
.section-title { font-size:11px; text-transform:uppercase; color:var(--muted); letter-spacing:1.5px; margin-bottom:8px; display:flex; align-items:center; gap:6px; }
.section-title .icon { font-size:14px; }

/* Emotion bars */
.emotion-item { display:flex; align-items:center; gap:6px; margin-bottom:4px; font-size:11px; }
.emotion-label { width:42px; color:var(--muted); text-align:right; flex-shrink:0; }
.emotion-track { flex:1; height:14px; background:var(--bg); border-radius:7px; overflow:hidden; position:relative; }
.emotion-fill { height:100%; border-radius:7px; transition:width 0.6s ease; min-width:0; }
.emotion-val { width:32px; font-size:10px; color:var(--dim); text-align:right; flex-shrink:0; }

/* Personality bars */
.trait-item { display:flex; align-items:center; gap:6px; margin-bottom:6px; font-size:11px; }
.trait-label { width:36px; text-align:right; flex-shrink:0; }
.trait-track { flex:1; height:16px; background:var(--bg); border-radius:8px; overflow:hidden; position:relative; }
.trait-fill { height:100%; border-radius:8px; transition:width 0.8s ease, background 0.5s; position:relative; }
.trait-fill .default-marker { position:absolute; top:2px; bottom:2px; width:2px; background:rgba(255,255,255,0.5); border-radius:1px; }
.trait-val { width:32px; font-size:10px; color:var(--dim); text-align:right; flex-shrink:0; }
.trait-desc { font-size:9px; color:var(--dim); margin-top:-4px; margin-bottom:4px; padding-left:42px; }

/* Module status */
.module-grid { display:grid; grid-template-columns:1fr 1fr; gap:4px; }
.module-card { background:var(--bg); border-radius:6px; padding:6px 8px; font-size:10px; display:flex; align-items:center; gap:5px; }
.module-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.module-dot.on { background:var(--success); box-shadow:0 0 4px var(--success); }
.module-dot.off { background:var(--border); }

/* Live2D panel */
.live2d-panel { background:var(--bg2); border-right:1px solid var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; position:relative; overflow:hidden; }
#live2d-canvas { width:100%; height:100%; }
.live2d-loading { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; color:var(--muted); }
.live2d-loading .spinner { width:40px; height:40px; border:3px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:spin 1s linear infinite; margin:0 auto 12px; }
@keyframes spin { to{transform:rotate(360deg)} }
.live2d-status { position:absolute; bottom:8px; left:8px; font-size:10px; color:var(--dim); background:rgba(0,0,0,0.5); padding:2px 8px; border-radius:8px; }

/* Center - chat */
.center-panel { display:flex; flex-direction:column; background:var(--bg2); }

/* Chat messages */
.chat-area { flex:1; overflow-y:auto; padding:14px 16px; }
.chat-msg { margin-bottom:10px; display:flex; gap:8px; animation:fadeIn 0.3s; }
@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
.chat-msg.user { flex-direction:row-reverse; }
.chat-avatar { width:32px; height:32px; border-radius:50%; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:12px; }
.chat-msg.user .chat-avatar { background:var(--accent3); color:#000; }
.chat-msg.bot .chat-avatar { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff; }
.chat-bubble { max-width:70%; padding:8px 12px; border-radius:12px; font-size:13px; line-height:1.5; position:relative; }
.chat-msg.user .chat-bubble { background:var(--accent3); color:#000; border-bottom-right-radius:4px; }
.chat-msg.bot .chat-bubble { background:var(--card2); border-bottom-left-radius:4px; }
.chat-bubble .personality-tag { font-size:9px; color:var(--purple); margin-top:2px; }
.chat-time { font-size:9px; color:var(--dim); margin-top:2px; }
.chat-msg.user .chat-time { text-align:right; }

/* Chat input */
.chat-input-area { padding:10px 16px; background:var(--card); border-top:1px solid var(--border); }
.chat-input-row { display:flex; gap:6px; }
.chat-input-row input { flex:1; background:var(--bg); border:1px solid var(--border); color:var(--text); border-radius:18px; padding:8px 14px; font-size:13px; outline:none; }
.chat-input-row input:focus { border-color:var(--accent); }
.chat-input-row button { background:linear-gradient(135deg,var(--accent),var(--accent2)); border:none; color:#fff; padding:8px 16px; border-radius:18px; cursor:pointer; font-size:13px; font-weight:600; white-space:nowrap; }
.chat-input-row button:hover { opacity:0.9; }
.chat-quick { display:flex; gap:4px; margin-top:6px; flex-wrap:wrap; }
.quick-btn { background:var(--card2); border:1px solid var(--border); color:var(--muted); padding:3px 10px; border-radius:12px; font-size:11px; cursor:pointer; transition:0.2s; }
.quick-btn:hover { border-color:var(--accent); color:var(--accent); }

/* Right panel - status */
.right-panel { background:var(--card); border-left:1px solid var(--border); overflow-y:auto; padding:12px; }

/* Viseme demo */
.viseme-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; }
.viseme-card { background:var(--bg); border-radius:6px; padding:6px; text-align:center; }
.viseme-mouth { width:30px; height:20px; margin:2px auto; border:2px solid var(--accent); border-radius:50%; position:relative; transition:all 0.3s; }
.viseme-name { font-size:9px; color:var(--muted); }

/* STM display */
.stm-card { background:var(--bg); border-radius:6px; padding:8px; margin-bottom:6px; font-size:11px; }
.stm-card .summary-text { color:var(--text); line-height:1.4; }
.stm-card .topics { display:flex; gap:3px; margin-top:4px; flex-wrap:wrap; }
.stm-card .topic { background:var(--card2); border:1px solid var(--border); padding:1px 6px; border-radius:8px; font-size:9px; color:var(--accent3); }

/* Personality prompt */
.prompt-box { background:var(--bg); border-radius:6px; padding:8px; font-size:10px; line-height:1.5; color:var(--green); font-family:'Consolas',monospace; white-space:pre-wrap; word-break:break-all; max-height:200px; overflow-y:auto; }

/* Welcome message */
.welcome { text-align:center; padding:40px 16px; color:var(--muted); }
.welcome h2 { font-size:20px; color:var(--text); margin-bottom:6px; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.welcome p { font-size:12px; margin-bottom:3px; }

/* Scrollbar */
::-webkit-scrollbar { width:5px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:var(--dim); }
</style>
</head>
<body>
<div class="app">
  <!-- Header -->
  <div class="header">
    <div class="header-left">
      <h1>IGEM-sama</h1>
      <span class="badge" id="llm-badge">检测中</span>
    </div>
    <div class="header-right">
      <div class="dot"></div>
      <span id="status-text">模拟直播间</span>
      <span style="color:var(--dim)">|</span>
      <span id="msg-count">0 条消息</span>
    </div>
  </div>

  <!-- Left Panel: Emotion + Personality + Modules -->
  <div class="left-panel">
    <!-- Emotion -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x1F496;</span> 情绪状态</div>
      <div id="emotion-bars"></div>
      <div style="display:flex;align-items:center;gap:6px;margin-top:6px;font-size:11px;">
        <span style="color:var(--muted)">主导:</span>
        <span id="dominant-emotion" style="color:var(--accent);font-weight:600;">neutral</span>
        <span id="dominant-intensity" style="color:var(--dim);">0.00</span>
      </div>
      <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:3px;">
        <button class="quick-btn" onclick="setEmotion('happy')">开心</button>
        <button class="quick-btn" onclick="setEmotion('excited')">激动</button>
        <button class="quick-btn" onclick="setEmotion('curious')">好奇</button>
        <button class="quick-btn" onclick="setEmotion('proud')">自豪</button>
        <button class="quick-btn" onclick="setEmotion('shy')">害羞</button>
        <button class="quick-btn" onclick="setEmotion('sad')">难过</button>
        <button class="quick-btn" onclick="setEmotion('angry')">生气</button>
      </div>
    </div>

    <!-- Personality -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x2728;</span> 人格特质</div>
      <div id="trait-bars"></div>
    </div>

    <!-- Modules -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x1F4E1;</span> 模块状态</div>
      <div class="module-grid" id="module-grid"></div>
    </div>

    <!-- Short-term memory -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x1F9E0;</span> 短期记忆</div>
      <div id="stm-area">
        <div style="font-size:11px;color:var(--dim);">暂无摘要</div>
      </div>
    </div>
  </div>

  <!-- Live2D Panel -->
  <div class="live2d-panel">
    <canvas id="live2d-canvas"></canvas>
    <div class="live2d-loading" id="live2d-loading">
      <div class="spinner"></div>
      <div>加载 Live2D 模型...</div>
    </div>
    <div class="live2d-status" id="live2d-status">未加载</div>
  </div>

  <!-- Center: Chat -->
  <div class="center-panel">
    <div class="chat-area" id="chat-area">
      <div class="welcome" id="welcome">
        <h2>IGEM-sama 模拟直播间</h2>
        <p>输入弹幕与IGEM-sama互动</p>
        <p style="font-size:10px;color:var(--dim);margin-top:6px;">Live2D / 情绪追踪 / 人格演化 / 短期记忆</p>
      </div>
    </div>
    <div class="chat-input-area">
      <div class="chat-input-row">
        <input type="text" id="chat-input" placeholder="输入弹幕消息..." autofocus onkeydown="if(event.key==='Enter')sendMessage()">
        <button onclick="sendMessage()">发送</button>
      </div>
      <div class="chat-quick">
        <button class="quick-btn" onclick="quickSend('你好！')">打招呼</button>
        <button class="quick-btn" onclick="quickSend('你是谁？')">问身份</button>
        <button class="quick-btn" onclick="quickSend('你们的项目是做什么的？')">问项目</button>
        <button class="quick-btn" onclick="quickSend('什么是iGEM？')">问iGEM</button>
        <button class="quick-btn" onclick="quickSend('太厉害了！')">夸奖</button>
        <button class="quick-btn" onclick="quickSend('为什么合成生物学这么难？')">好奇</button>
      </div>
    </div>
  </div>

  <!-- Right Panel: Viseme + Prompt -->
  <div class="right-panel">
    <!-- Personality Prompt -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x1F4DD;</span> 动态人格Prompt</div>
      <div class="prompt-box" id="prompt-box">等待数据...</div>
    </div>

    <!-- Viseme Demo -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x1F444;</span> Lip Sync 口型</div>
      <div class="viseme-grid" id="viseme-grid"></div>
    </div>

    <!-- Actions -->
    <div class="section">
      <div class="section-title"><span class="icon">&#x2699;</span> 操作</div>
      <button class="quick-btn" onclick="resetSim()" style="width:100%;text-align:center;padding:6px;margin-bottom:4px;">重置模拟</button>
      <button class="quick-btn" onclick="loadViseme()" style="width:100%;text-align:center;padding:6px;">刷新口型演示</button>
    </div>
  </div>
</div>

<script>
const API = '';
let refreshTimer;

// Emotion colors
const EMOTION_COLORS = {
  happy:'#FFD700', excited:'#FF6347', calm:'#87CEEB', curious:'#9370DB',
  sad:'#4682B4', angry:'#DC143C', shy:'#FF69B4', proud:'#32CD32', neutral:'#808080'
};
const EMOTION_NAMES = {
  happy:'开心', excited:'激动', calm:'平静', curious:'好奇',
  sad:'难过', angry:'生气', shy:'害羞', proud:'自豪', neutral:'平静'
};
const TRAIT_COLORS = {
  lively:'linear-gradient(90deg,#FFD700,#FFA500)', tsundere:'linear-gradient(90deg,#FF69B4,#FF1493)',
  knowledgeable:'linear-gradient(90deg,#61afef,#1e90ff)', playful:'linear-gradient(90deg,#50fa7b,#3fb950)',
  warm:'linear-gradient(90deg,#ffb86c,#ff8c00)', scientific:'linear-gradient(90deg,#bd93f9,#8b5cf6)'
};

async function api(path, method='GET', body=null) {
  try {
    const opts = { method, headers:{'Content-Type':'application/json'} };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    return await res.json();
  } catch(e) { console.error('API error:', e); return null; }
}

// ==================== Live2D ====================
let live2dModel = null;
let live2dApp = null;
let currentEmotion = 'neutral';
let lipSyncTimer = null;

async function initLive2D() {
  const canvas = document.getElementById('live2d-canvas');
  const panel = canvas.parentElement;
  const w = panel.clientWidth;
  const h = panel.clientHeight;

  try {
    live2dApp = new PIXI.Application({
      view: canvas,
      width: w,
      height: h,
      transparent: true,
      autoStart: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });

    live2dModel = await PIXI.live2d.Live2DModel.from('/live2d/hiyori_pro_mic.model3.json', {
      autoInteract: false,
    });

    live2dApp.stage.addChild(live2dModel);

    // Scale and center model
    const scale = Math.min(w / live2dModel.width * 0.85, h / live2dModel.height * 0.9);
    live2dModel.scale.set(scale);
    live2dModel.x = (w - live2dModel.width * scale) / 2;
    live2dModel.y = (h - live2dModel.height * scale) / 2;

    // Hide loading, show status
    document.getElementById('live2d-loading').style.display = 'none';
    document.getElementById('live2d-status').textContent = 'Live2D 已加载';
    document.getElementById('live2d-status').style.color = 'var(--success)';

    // Start idle motion
    playMotion('Idle', 0);

    console.log('Live2D model loaded successfully');
  } catch(e) {
    console.error('Live2D load failed:', e);
    document.getElementById('live2d-loading').innerHTML = '<div style="color:var(--danger)">Live2D 加载失败</div><div style="font-size:10px;margin-top:4px;">' + e.message + '</div>';
    document.getElementById('live2d-status').textContent = '加载失败';
    document.getElementById('live2d-status').style.color = 'var(--danger)';
  }
}

function playMotion(group, no) {
  if (!live2dModel) return;
  try {
    live2dModel.motion(group, no);
  } catch(e) {
    console.warn('Motion play failed:', e);
  }
}

function applyExpression(emotion, intensity) {
  if (!live2dModel) return;
  if (emotion === currentEmotion) return;
  currentEmotion = emotion;

  api('/api/live2d/expression', 'POST', {emotion, intensity}).then(data => {
    if (!data || !data.params) return;

    try {
      const coreModel = live2dModel.internalModel.coreModel;
      for (const [paramId, [value, weight]] of Object.entries(data.params)) {
        const idx = coreModel._model.parameters.ids.indexOf(paramId);
        if (idx >= 0) {
          coreModel._model.parameters.values[idx] = value;
        }
      }
    } catch(e) {
      console.warn('Expression apply failed:', e);
    }

    // Trigger motion
    if (data.motion) {
      playMotion(data.motion.group, data.motion.no);
    }
  });
}

// Lip-sync animation when bot speaks
function startLipSync(durationMs) {
  if (!live2dModel) return;
  stopLipSync();

  const visemes = [
    {openY: 0.85, form: 0.2},  // A
    {openY: 0.25, form: 0.8},  // I
    {openY: 0.35, form: -0.6}, // U
    {openY: 0.55, form: 0.5},  // E
    {openY: 0.65, form: -0.4}, // O
  ];

  let step = 0;
  const interval = 120; // ms per viseme
  const totalSteps = Math.floor(durationMs / interval);

  lipSyncTimer = setInterval(() => {
    step++;
    if (step > totalSteps) {
      stopLipSync();
      return;
    }

    const v = visemes[step % visemes.length];
    // Fade out near the end
    const fade = step > totalSteps * 0.7 ? (totalSteps - step) / (totalSteps * 0.3) : 1;

    try {
      const coreModel = live2dModel.internalModel.coreModel;
      const openIdx = coreModel._model.parameters.ids.indexOf('ParamMouthOpenY');
      const formIdx = coreModel._model.parameters.ids.indexOf('ParamMouthForm');
      if (openIdx >= 0) coreModel._model.parameters.values[openIdx] = v.openY * fade;
      if (formIdx >= 0) coreModel._model.parameters.values[formIdx] = v.form * fade;
    } catch(e) {}
  }, interval);
}

function stopLipSync() {
  if (lipSyncTimer) {
    clearInterval(lipSyncTimer);
    lipSyncTimer = null;
  }
  // Reset mouth
  if (live2dModel) {
    try {
      const coreModel = live2dModel.internalModel.coreModel;
      const openIdx = coreModel._model.parameters.ids.indexOf('ParamMouthOpenY');
      const formIdx = coreModel._model.parameters.ids.indexOf('ParamMouthForm');
      if (openIdx >= 0) coreModel._model.parameters.values[openIdx] = 0;
      if (formIdx >= 0) coreModel._model.parameters.values[formIdx] = 0;
    } catch(e) {}
  }
}

// ==================== Chat ====================
let messageCount = 0;

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  addChatMessage('user', text);
  document.getElementById('welcome').style.display = 'none';

  const typingId = addChatMessage('bot', '...正在思考', true);

  const r = await api('/api/chat/send', 'POST', {text});

  removeChatMessage(typingId);

  if (r && r.ok) {
    addChatMessage('bot', r.bot_message.content, false, r.bot_message.personality_hint);
    messageCount++;
    document.getElementById('msg-count').textContent = messageCount + ' 条消息';

    // Estimate speech duration: ~150ms per Chinese character
    const charCount = r.bot_message.content.length;
    const durationMs = Math.max(1500, charCount * 150);
    startLipSync(durationMs);

    // Trigger a small motion when responding
    playMotion('TapBody', Math.floor(Math.random() * 5));

    refresh();
  } else {
    addChatMessage('bot', '(发送失败)', false);
  }
}

function quickSend(text) {
  document.getElementById('chat-input').value = text;
  sendMessage();
}

let msgIdCounter = 0;
function addChatMessage(role, content, isTyping=false, personalityHint='') {
  const area = document.getElementById('chat-area');
  const id = 'msg-' + (++msgIdCounter);
  const now = new Date();
  const timeStr = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');

  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.id = id;

  const avatar = role === 'user' ? 'U' : 'S';
  let extra = '';
  if (personalityHint) extra += `<div class="personality-tag">${personalityHint}</div>`;
  if (isTyping) extra += '<span class="typing-dots" style="animation:pulse 1s infinite">...</span>';

  div.innerHTML = `
    <div class="chat-avatar">${avatar}</div>
    <div>
      <div class="chat-bubble">${content}${extra}</div>
      <div class="chat-time">${timeStr}</div>
    </div>
  `;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return id;
}

function removeChatMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ---- Emotion ----
function renderEmotions(emotionData) {
  const container = document.getElementById('emotion-bars');
  container.innerHTML = '';
  const sorted = Object.entries(emotionData.all).sort((a,b) => b[1]-a[1]);

  for (const [name, val] of sorted) {
    if (val < 0.005 && name !== 'neutral') continue;
    const color = EMOTION_COLORS[name] || '#808080';
    const displayName = EMOTION_NAMES[name] || name;
    const pct = Math.min(val * 100, 100);
    container.innerHTML += `
      <div class="emotion-item">
        <span class="emotion-label">${displayName}</span>
        <div class="emotion-track"><div class="emotion-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="emotion-val">${val.toFixed(2)}</span>
      </div>`;
  }

  document.getElementById('dominant-emotion').textContent = EMOTION_NAMES[emotionData.dominant] || emotionData.dominant;
  document.getElementById('dominant-emotion').style.color = EMOTION_COLORS[emotionData.dominant] || 'var(--accent)';
  document.getElementById('dominant-intensity').textContent = emotionData.intensity.toFixed(2);
}

async function setEmotion(emotion) {
  await api('/api/emotion/set', 'POST', {emotion, intensity:0.8});
  // Immediately apply expression
  applyExpression(emotion, 0.8);
  refresh();
}

// ---- Personality ----
async function renderPersonality() {
  const data = await api('/api/personality/detail');
  if (!data || !data.traits) return;

  const container = document.getElementById('trait-bars');
  container.innerHTML = '';

  for (const trait of data.traits) {
    const pct = Math.min(trait.value * 100, 100);
    const defaultPct = trait.default_value * 100;
    const bg = TRAIT_COLORS[trait.name] || 'linear-gradient(90deg,var(--accent),var(--accent2))';
    const arrow = trait.delta > 0.01 ? '↑' : trait.delta < -0.01 ? '↓' : '→';
    const arrowColor = trait.delta > 0.01 ? 'var(--success)' : trait.delta < -0.01 ? 'var(--danger)' : 'var(--dim)';

    container.innerHTML += `
      <div class="trait-item">
        <span class="trait-label" style="color:${TRAIT_COLORS[trait.name] ? TRAIT_COLORS[trait.name].match(/#([0-9a-f]{6})/i)?.[0] || 'var(--text)' : 'var(--text)'}">${trait.display_name}</span>
        <div class="trait-track">
          <div class="trait-fill" style="width:${pct}%;background:${bg}">
            <div class="default-marker" style="left:${defaultPct}%"></div>
          </div>
        </div>
        <span class="trait-val">${trait.value.toFixed(2)} <span style="color:${arrowColor}">${arrow}</span></span>
      </div>`;
    if (trait.description) {
      container.innerHTML += `<div class="trait-desc">${trait.description}</div>`;
    }
  }

  document.getElementById('prompt-box').textContent = data.prompt_extension || '(人格处于默认状态)';
}

// ---- Modules ----
function renderModules(modules) {
  const container = document.getElementById('module-grid');
  container.innerHTML = '';

  const names = {
    emotion:'情绪追踪', personality:'人格演化', short_term_memory:'短期记忆',
    lip_sync:'Lip Sync', voice_clone:'语音克隆', perception:'多模态感知', game_loop:'游戏互动'
  };

  for (const [key, on] of Object.entries(modules)) {
    const cls = on ? 'on' : 'off';
    container.innerHTML += `
      <div class="module-card">
        <div class="module-dot ${cls}"></div>
        <span>${names[key] || key}</span>
      </div>`;
  }
}

// ---- Viseme ----
async function loadViseme() {
  const data = await api('/api/demo/viseme');
  if (!data || !data.results) return;

  const container = document.getElementById('viseme-grid');
  container.innerHTML = '';

  for (const v of data.results) {
    const openPct = Math.abs(v.mouth_open) * 100;
    const formPct = (v.mouth_form + 1) * 50;
    const mouthStyle = `width:${24 + formPct * 0.2}px;height:${8 + openPct * 0.2}px;border-radius:${24 + formPct * 0.2}px ${24 + formPct * 0.2}px ${8 + openPct * 0.1}px ${8 + openPct * 0.1}px`;

    container.innerHTML += `
      <div class="viseme-card">
        <div class="viseme-mouth" style="${mouthStyle}"></div>
        <div class="viseme-name">${v.name}(${v.viseme})</div>
      </div>`;
  }
}

// ---- STM ----
function renderSTM(stmData) {
  const container = document.getElementById('stm-area');
  if (!stmData || !stmData.enabled || stmData.summary_count === 0) {
    container.innerHTML = '<div style="font-size:11px;color:var(--dim)">暂无摘要 (对话积累后自动生成)</div>';
    return;
  }

  container.innerHTML = '';
  for (const s of stmData.summaries) {
    let topics = '';
    if (s.topics && s.topics.length) {
      topics = '<div class="topics">' + s.topics.map(t => `<span class="topic">${t}</span>`).join('') + '</div>';
    }
    container.innerHTML += `
      <div class="stm-card">
        <div class="summary-text">${s.text}</div>
        <div style="font-size:9px;color:var(--dim);margin-top:3px;">压缩 ${s.message_count} 条消息</div>
        ${topics}
      </div>`;
  }
}

// ---- Refresh ----
let lastDominantEmotion = 'neutral';
async function refresh() {
  const data = await api('/api/status');
  if (!data) return;

  const badge = document.getElementById('llm-badge');
  badge.textContent = data.llm_available ? 'LLM 已连接' : 'LLM 未连接';
  badge.className = 'badge' + (data.llm_available ? '' : ' off');

  renderEmotions(data.emotion);
  renderModules(data.modules);
  renderSTM(data.short_term_memory);

  document.getElementById('status-text').textContent = data.emotion.dominant !== 'neutral'
    ? `情绪: ${EMOTION_NAMES[data.emotion.dominant] || data.emotion.dominant}`
    : '模拟直播间';

  // Update Live2D expression when emotion changes
  if (data.emotion.dominant !== lastDominantEmotion && data.emotion.dominant !== 'neutral') {
    applyExpression(data.emotion.dominant, data.emotion.intensity);
    lastDominantEmotion = data.emotion.dominant;
  } else if (data.emotion.dominant === 'neutral') {
    lastDominantEmotion = 'neutral';
  }
}

// ---- Reset ----
async function resetSim() {
  if (!confirm('确定要重置所有模拟状态吗？')) return;
  await api('/api/reset', 'POST');
  document.getElementById('chat-area').innerHTML = `
    <div class="welcome" id="welcome">
      <h2>IGEM-sama 模拟直播间</h2>
      <p>输入弹幕与IGEM-sama互动</p>
    </div>`;
  messageCount = 0;
  document.getElementById('msg-count').textContent = '0 条消息';
  currentEmotion = 'neutral';
  lastDominantEmotion = 'neutral';
  stopLipSync();
  refresh();
  renderPersonality();
}

// ---- Init ----
refresh();
renderPersonality();
loadViseme();
initLive2D();
refreshTimer = setInterval(() => { refresh(); renderPersonality(); }, 3000);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 50)
    logger.info("  IGEM-sama Web 模拟直播间")
    logger.info("=" * 50)

    # Disable external services in config
    try:
        from manager.config_manager import get_config
        config = get_config()
        config.service.live_stream.enable = False
        config.service.live_stream.bilibili.enable = False
        config.service.live_stream.bilibili.room_id = 0
        config.service.obs.enable = False
        config.service.playground.enable = False
        config.service.qqbot.enable = False
        config.service.browser.enable = False
        config.service.game.enable = False
        config.pipeline.tts.enable = False
        config.pipeline.asr.enable = False
        config.pipeline.ocr.enable = False
        config.pipeline.img_cap.enable = False
        config.pipeline.vid_cap.enable = False
        config.pipeline.vla.enable = False
        config.pipeline.vec_db.enable = False
        config.pipeline.kb.enable = False
    except Exception as e:
        logger.warning(f"Config override skipped: {e}")

    # Initialize lightweight modules
    state.init_modules()

    # Start Flask
    app = create_app()
    host = "127.0.0.1"
    port = 8888

    logger.info("")
    logger.info(f"  浏览器打开: http://{host}:{port}")
    logger.info("")

    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
