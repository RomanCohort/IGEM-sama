"""Live Stream Analytics Collector for IGEM-sama.

Collects real-time metrics:
  - Viewer count tracking
  - Danmaku frequency and peaks
  - Popular topics / keyword cloud
  - Emotion trend over time
  - Engagement scores

Data is stored in-memory with periodic JSON snapshots.
A lightweight web dashboard (Flask) serves the metrics via API.
"""

import json
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class AnalyticsSnapshot(BaseModel):
    """A point-in-time snapshot of stream analytics."""
    timestamp: float = Field(default_factory=time.time)
    danmaku_count: int = 0
    danmaku_per_minute: float = 0.0
    total_viewers: int = 0
    unique_viewers: int = 0
    top_keywords: List[tuple] = Field(default_factory=list)
    emotion_distribution: Dict[str, float] = Field(default_factory=dict)
    dominant_emotion: str = "neutral"
    avg_response_length: float = 0.0
    interaction_count: int = 0
    autonomous_count: int = 0


class StreamAnalytics:
    """Collects and aggregates stream analytics data.

    Usage:
        analytics = StreamAnalytics()
        analytics.record_danmaku("hello", uid="123", username="viewer1")
        analytics.record_emotion("happy", 0.7)
        snapshot = analytics.snapshot()
    """

    def __init__(self, persist_path: str = "data/analytics.json", window_minutes: int = 30):
        self._persist_path = Path(persist_path)
        self._window = window_minutes * 60  # seconds
        self._lock = threading.Lock()

        # Rolling window of danmaku timestamps
        self._danmaku_times: deque = deque()
        # Keyword counter (rolling)
        self._keywords: Counter = Counter()
        # Viewer tracking
        self._viewer_uids: set = set()
        self._total_danmaku: int = 0
        # Emotion history
        self._emotion_history: deque = deque(maxlen=100)
        # Response length tracking
        self._response_lengths: deque = deque(maxlen=50)
        # Interaction counts
        self._interaction_count: int = 0
        self._autonomous_count: int = 0
        # Session start
        self._session_start: float = time.time()

    # ------------------------------------------------------------------
    # Recording Methods
    # ------------------------------------------------------------------

    def record_danmaku(self, content: str, uid: str = "", username: str = ""):
        """Record an incoming danmaku. Thread-safe."""
        with self._lock:
            now = time.time()
            self._danmaku_times.append(now)
            self._total_danmaku += 1
            self._interaction_count += 1

            if uid:
                self._viewer_uids.add(uid)

            # Extract keywords (simple: split by common delimiters)
            words = content.replace("，", " ").replace("。", " ").replace("？", " ").replace("！", " ").split()
            for w in words:
                if len(w) >= 2:  # Skip single chars
                    self._keywords[w] += 1

            self._cleanup_old_data()

    def record_emotion(self, emotion: str, intensity: float):
        """Record an emotion state change. Thread-safe."""
        with self._lock:
            self._emotion_history.append((time.time(), emotion, intensity))

    def record_response(self, response_length: int):
        """Record an LLM response. Thread-safe."""
        with self._lock:
            self._response_lengths.append(response_length)

    def record_autonomous_action(self):
        """Record an autonomous behavior trigger. Thread-safe."""
        with self._lock:
            self._autonomous_count += 1

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> AnalyticsSnapshot:
        """Generate a current analytics snapshot."""
        now = time.time()
        self._cleanup_old_data()

        # Danmaku per minute
        recent_count = len(self._danmaku_times)
        window_minutes = self._window / 60
        dpm = recent_count / window_minutes if window_minutes > 0 else 0

        # Top keywords
        top_kw = self._keywords.most_common(10)

        # Emotion distribution (from recent history)
        emotion_dist: Dict[str, float] = {}
        recent_emotions = [(t, e, i) for t, e, i in self._emotion_history
                           if now - t < self._window]
        if recent_emotions:
            for _, emotion, intensity in recent_emotions:
                emotion_dist[emotion] = emotion_dist.get(emotion, 0) + intensity
            total = sum(emotion_dist.values()) or 1
            emotion_dist = {k: round(v / total, 3) for k, v in emotion_dist.items()}

        dominant = max(emotion_dist, key=emotion_dist.get) if emotion_dist else "neutral"

        # Average response length
        avg_len = (sum(self._response_lengths) / len(self._response_lengths)
                   if self._response_lengths else 0)

        return AnalyticsSnapshot(
            timestamp=now,
            danmaku_count=self._total_danmaku,
            danmaku_per_minute=round(dpm, 1),
            total_viewers=len(self._viewer_uids),
            unique_viewers=len(self._viewer_uids),
            top_keywords=top_kw,
            emotion_distribution=emotion_dist,
            dominant_emotion=dominant,
            avg_response_length=round(avg_len, 1),
            interaction_count=self._interaction_count,
            autonomous_count=self._autonomous_count,
        )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, n: int = 60) -> List[AnalyticsSnapshot]:
        """Load the last N snapshots from disk."""
        if not self._persist_path.exists():
            return []
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            snapshots = [AnalyticsSnapshot.model_validate(s) for s in data.get("history", [])]
            return snapshots[-n:]
        except Exception:
            return []

    def save_snapshot(self):
        """Save current snapshot to the history file. Thread-safe."""
        with self._lock:
            snap = self.snapshot()
            history = []
            if self._persist_path.exists():
                try:
                    data = json.loads(self._persist_path.read_text(encoding="utf-8"))
                    history = data.get("history", [])
                except Exception:
                    pass

            history.append(snap.model_dump())

            # Keep last 3600 snapshots (1 hour at 1/sec)
            if len(history) > 3600:
                history = history[-3600:]

            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(
                json.dumps({"history": history}, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _cleanup_old_data(self):
        """Remove data older than the rolling window."""
        now = time.time()
        cutoff = now - self._window

        while self._danmaku_times and self._danmaku_times[0] < cutoff:
            self._danmaku_times.popleft()

        # Shrink keywords counter (keep top 200)
        if len(self._keywords) > 200:
            self._keywords = Counter(dict(self._keywords.most_common(200)))
