"""Persistent Emotion Tracker for IGEM-sama.

Tracks emotional state across messages and sessions, providing:
  - Smooth emotional transitions (no abrupt mood swings)
  - Emotion decay over time (returns to neutral when idle)
  - Persistent state saved to disk between sessions
  - Integration hooks for Live2D expressions and TTS voice selection

Emotion model:
  Each emotion has a float intensity [0, 1].
  The dominant emotion drives avatar expression and TTS tone.
  Emotions blend smoothly via exponential moving average.
"""

import json
import os
import tempfile
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from loguru import logger


class EmotionLabel(str, Enum):
    HAPPY = "happy"
    EXCITED = "excited"
    CALM = "calm"
    CURIOUS = "curious"
    SAD = "sad"
    ANGRY = "angry"
    SHY = "shy"
    PROUD = "proud"
    NEUTRAL = "neutral"


# Default intensities for each emotion after a reset
_DEFAULT_INTENSITIES: Dict[str, float] = {e.value: 0.0 for e in EmotionLabel}
_DEFAULT_INTENSITIES[EmotionLabel.NEUTRAL.value] = 1.0

# How sentiment scores (-1..1) map to emotion labels
_SENTIMENT_EMOTION_MAP = {
    (-1.0, -0.5): EmotionLabel.SAD,
    (-0.5, -0.2): EmotionLabel.ANGRY,
    (-0.2, 0.2): EmotionLabel.NEUTRAL,
    (0.2, 0.5): EmotionLabel.CURIOUS,
    (0.5, 0.8): EmotionLabel.HAPPY,
    (0.8, 1.0): EmotionLabel.EXCITED,
}

# Keyword-based emotion detection (Chinese)
_KEYWORD_EMOTIONS = {
    EmotionLabel.HAPPY: ["开心", "太好了", "厉害", "棒", "哈哈", "笑", "喜欢", "可爱", "好耶", "666"],
    EmotionLabel.EXCITED: ["激动", "兴奋", "超", "太牛", "震撼", "amazing", "wow"],
    EmotionLabel.CURIOUS: ["为什么", "怎么回事", "好奇", "什么意思", "怎么做到"],
    EmotionLabel.SAD: ["难过", "可惜", "伤心", "遗憾", "哭", "失望"],
    EmotionLabel.ANGRY: ["生气", "烦", "讨厌", "气死"],
    EmotionLabel.SHY: ["害羞", "脸红", "不好意思", "夸我"],
    EmotionLabel.PROUD: ["我们队", "我们团队", "IGEM-FBH", "我们项目", "我们的成果"],
}


class EmotionState:
    """Represents a snapshot of all emotion intensities."""

    def __init__(self, intensities: Optional[Dict[str, float]] = None):
        self.intensities: Dict[str, float] = dict(
            intensities if intensities else _DEFAULT_INTENSITIES
        )
        self.last_update: float = time.time()

    @property
    def dominant(self) -> EmotionLabel:
        """Return the emotion with the highest intensity."""
        best = EmotionLabel.NEUTRAL
        best_val = -1.0
        for label, val in self.intensities.items():
            if val > best_val:
                best_val = val
                best = EmotionLabel(label)
        return best

    @property
    def dominant_intensity(self) -> float:
        return self.intensities.get(self.dominant.value, 0.0)

    def to_dict(self) -> dict:
        return {"intensities": self.intensities, "last_update": self.last_update}

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionState":
        state = cls(intensities=data.get("intensities"))
        state.last_update = data.get("last_update", time.time())
        return state


class EmotionTracker:
    """Tracks and persists IGEM-sama's emotional state.

    Usage:
        tracker = EmotionTracker()
        tracker.update_from_sentiment(0.7)          # from LLM sentiment analysis
        tracker.update_from_keywords("太厉害了！")    # from keyword detection
        tracker.decay()                              # call periodically (e.g. every second)
        print(tracker.state.dominant)                # EmotionLabel.HAPPY
    """

    # Smoothing factor for exponential moving average (0 = no change, 1 = instant)
    _BLEND_FACTOR = 0.4
    # How much intensity decays per second toward neutral
    _DECAY_RATE = 0.02
    # Minimum intensity to count as "active"
    _THRESHOLD = 0.05

    def __init__(self, persist_path: str = "data/emotion_state.json"):
        self._persist_path = Path(persist_path)
        self._lock = threading.Lock()
        self.state = self._load()

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def update_from_sentiment(self, score: float) -> EmotionLabel:
        """Update emotion based on a sentiment score (-1 to 1).

        Returns the new dominant emotion. Thread-safe.
        """
        with self._lock:
            target = EmotionLabel.NEUTRAL
            for (lo, hi), label in _SENTIMENT_EMOTION_MAP.items():
                if lo <= score < hi:
                    target = label
                    break
            # Clamp edge case
            if score >= 0.8:
                target = EmotionLabel.EXCITED
            if score <= -1.0:
                target = EmotionLabel.SAD

            self._blend(target, abs(score))
            self.state.last_update = time.time()
            self._save()
            return self.state.dominant

    def update_from_keywords(self, text: str) -> Optional[EmotionLabel]:
        """Detect emotion from Chinese keywords in *text*.

        Returns the detected emotion or None if no keywords matched. Thread-safe.
        """
        with self._lock:
            text_lower = text.lower()
            for emotion, keywords in _KEYWORD_EMOTIONS.items():
                for kw in keywords:
                    if kw in text_lower:
                        self._blend(emotion, 0.7)
                        self.state.last_update = time.time()
                        self._save()
                        return emotion
            return None

    def update_from_label(self, label: EmotionLabel, intensity: float = 0.6) -> EmotionLabel:
        """Directly set an emotion with a given intensity (0-1).

        Useful for manual triggers or event-driven emotion changes. Thread-safe.
        """
        with self._lock:
            self._blend(label, intensity)
            self.state.last_update = time.time()
            self._save()
            return self.state.dominant

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def decay(self, dt: float = 1.0):
        """Apply time-based decay: all emotions drift toward NEUTRAL.

        Call this periodically (e.g. every second from the SecondEvent handler). Thread-safe.
        """
        with self._lock:
            neutral_key = EmotionLabel.NEUTRAL.value
            for key in self.state.intensities:
                if key == neutral_key:
                    continue
                self.state.intensities[key] -= self._DECAY_RATE * dt
                if self.state.intensities[key] < self._THRESHOLD:
                    self.state.intensities[key] = 0.0

            # Neutral rises as others decay
            total = sum(v for k, v in self.state.intensities.items() if k != neutral_key)
            self.state.intensities[neutral_key] = max(0.0, 1.0 - total)

            self._save()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_emotion_prompt_hint(self) -> str:
        """Return a short Chinese hint about the current emotion for LLM system prompt injection. Thread-safe."""
        with self._lock:
            hints = {
                EmotionLabel.HAPPY: "你现在很开心，语气轻快。",
                EmotionLabel.EXCITED: "你现在非常激动，说话很兴奋！",
                EmotionLabel.CALM: "你现在很平静。",
                EmotionLabel.CURIOUS: "你现在很好奇，想了解更多。",
                EmotionLabel.SAD: "你现在有点难过，语气低沉。",
                EmotionLabel.ANGRY: "你现在有点生气。",
                EmotionLabel.SHY: "你现在有点害羞。",
                EmotionLabel.PROUD: "你现在很自豪，想分享团队成果！",
                EmotionLabel.NEUTRAL: "",
            }
            return hints.get(self.state.dominant, "")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _blend(self, target: EmotionLabel, intensity: float):
        """Smoothly blend the target emotion in using EMA."""
        a = self._BLEND_FACTOR
        # Boost target
        old = self.state.intensities.get(target.value, 0.0)
        self.state.intensities[target.value] = old * (1 - a) + intensity * a
        # Reduce others proportionally
        neutral_key = EmotionLabel.NEUTRAL.value
        total_non_neutral = sum(
            v for k, v in self.state.intensities.items() if k != neutral_key
        )
        self.state.intensities[neutral_key] = max(0.0, 1.0 - min(total_non_neutral, 1.0))

    def _save(self):
        """Persist current state to disk using atomic write."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2)
            # Atomic write: write to temp file in same dir, then rename
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._persist_path.parent), suffix=".json"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, str(self._persist_path))
            except Exception:
                os.unlink(tmp_path)
                raise
        except Exception as e:
            logger.warning(f"Failed to persist emotion state: {e}")

    def _load(self) -> EmotionState:
        """Load persisted state or return default."""
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text(encoding="utf-8"))
                return EmotionState.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load emotion state, using default: {e}")
        return EmotionState()
