"""Visual event detection and reaction handler.

When the visual scene changes significantly, this handler can:
  1. Inject context about the change into the next LLM query
  2. Trigger an autonomous reaction (commentary on what changed)
  3. Update emotion based on visual content
"""

import time
from typing import Callable, Optional

from loguru import logger

from perception.visual_loop import VisualLoop, VisualObservation
from perception.config import PerceptionConfig


class VisualEventHandler:
    """Detects and reacts to significant visual events.

    Usage:
        handler = VisualEventHandler(on_trigger, emotion_tracker, visual_loop, config)
        handler.check_and_react(elapsed)
    """

    def __init__(self, on_trigger: Callable, emotion_tracker, visual_loop: VisualLoop,
                 config: PerceptionConfig):
        self._on_trigger = on_trigger
        self._emotion_tracker = emotion_tracker
        self._visual_loop = visual_loop
        self._config = config
        self._last_event_time: float = 0

    def check_and_react(self, elapsed: int):
        """Check for visual events and trigger reactions.

        Called from SecondEvent handler after visual loop tick.
        Only active in reactive or proactive modes.
        """
        mode = self._config.visual.mode
        if mode.value not in ("reactive", "proactive"):
            return

        if not self._config.events.enable:
            return

        observation = self._visual_loop.get_latest_observation()
        if observation is None:
            return

        # Check for significant visual change
        if observation.screenshot_path:
            changed = self._visual_loop.detect_visual_change(observation.screenshot_path)
            if not changed:
                return

        # Cooldown check
        now = time.time()
        if now - self._last_event_time < self._config.events.event_cooldown:
            return

        self._last_event_time = now

        # Build and trigger reaction
        prompt = self._build_reaction_prompt(observation)
        if prompt:
            logger.info(f"Visual event triggered: {prompt[:50]}...")
            self._on_trigger(f"[视觉事件]{prompt}")

    def _build_reaction_prompt(self, observation: VisualObservation) -> str:
        """Build a reaction prompt based on the visual observation."""
        parts = []
        if observation.ocr_text:
            parts.append(f"看到文字: {observation.ocr_text[:80]}")
        if observation.image_caption:
            parts.append(f"看到画面: {observation.image_caption[:80]}")

        if not parts:
            return ""

        return "你注意到画面发生了变化。" + "，".join(parts) + "。对此发表一下感想。"
