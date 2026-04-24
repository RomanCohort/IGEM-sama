"""Autonomous Behavior System for IGEM-sama.

Makes IGEM-sama feel alive by generating proactive behavior:
  - Idle chatter when no one is talking (every ~60-120 seconds)
  - Greeting new viewers proactively
  - Periodic science facts or project highlights
  - Reacting to silence / inactivity
  - Time-based behaviors (morning greeting, late night musing)

All behaviors are triggered by the SecondEvent timer tick.
"""

import random
import time
from enum import Enum
from typing import Callable, List, Optional

from loguru import logger


class BehaviorType(str, Enum):
    IDLE_CHAT = "idle_chat"
    GREETING = "greeting"
    SCIENCE_FACT = "science_fact"
    PROJECT_HIGHLIGHT = "project_highlight"
    SILENCE_REACT = "silence_react"
    TIME_EVENT = "time_event"
    EMOTION_REACT = "emotion_react"


class BehaviorRule:
    """A rule that defines when and what autonomous behavior to trigger."""

    def __init__(
        self,
        behavior_type: BehaviorType,
        interval_range: tuple = (60, 120),
        prompts: Optional[List[str]] = None,
        condition: Optional[Callable] = None,
    ):
        self.behavior_type = behavior_type
        self.interval_range = interval_range
        self.prompts = prompts or []
        self.condition = condition  # Optional extra condition check
        self._next_trigger = 0
        self._reset_timer()

    def _reset_timer(self):
        lo, hi = self.interval_range
        self._next_trigger = time.time() + random.randint(lo, hi)

    def should_trigger(self, elapsed: int) -> bool:
        """Check if this behavior should fire now."""
        if time.time() < self._next_trigger:
            return False
        if self.condition and not self.condition():
            self._reset_timer()
            return False
        self._reset_timer()
        return True

    def pick_prompt(self) -> str:
        """Pick a random prompt from the list."""
        if not self.prompts:
            return ""
        return random.choice(self.prompts)


# Default behavior rules with Chinese prompts
DEFAULT_RULES: List[BehaviorRule] = [
    BehaviorRule(
        behavior_type=BehaviorType.IDLE_CHAT,
        interval_range=(90, 180),
        prompts=[
            "你突然想起了一件有趣的事，想跟观众分享。随便聊点轻松的话题吧。",
            "直播间现在有点安静，你主动说点什么活跃一下气氛。",
            "你觉得有点无聊，自言自语一下最近在想什么。",
            "你想跟观众互动一下，问他们一个有趣的问题。",
            "你突然有了一个灵感，想跟观众讨论一下。",
        ],
    ),
    BehaviorRule(
        behavior_type=BehaviorType.SCIENCE_FACT,
        interval_range=(180, 360),
        prompts=[
            "你想给观众科普一个有趣的合成生物学小知识。",
            "分享一个关于DNA或基因工程的冷知识。",
            "给观众讲一个生物学上的有趣现象。",
            "你想起了一个关于微生物的有趣事实，分享给大家。",
        ],
    ),
    BehaviorRule(
        behavior_type=BehaviorType.PROJECT_HIGHLIGHT,
        interval_range=(240, 480),
        prompts=[
            "你想介绍一下IGEM-FBH团队的项目亮点。",
            "提一下你们队伍正在研究的方向，引起观众兴趣。",
            "你想分享一些团队在实验中的趣事。",
            "介绍一下iGEM竞赛是什么，吸引新观众了解。",
        ],
    ),
    BehaviorRule(
        behavior_type=BehaviorType.SILENCE_REACT,
        interval_range=(120, 200),
        prompts=[
            "直播间已经安静好一会儿了，你有点寂寞，嘟囔几句话。",
            "没人说话，你开始自顾自地哼歌或者发呆。",
            "你想念热闹的弹幕，呼唤观众来聊天。",
        ],
    ),
]


class AutonomousBehavior:
    """Manages IGEM-sama's autonomous (proactive) behaviors.

    Usage:
        auto = AutonomousBehavior(on_trigger=bot.emit_llm_prediction)
        # Called every second from SecondEvent handler
        auto.on_tick(elapsed)
    """

    def __init__(
        self,
        on_trigger: Callable[[str], None],
        rules: Optional[List[BehaviorRule]] = None,
    ):
        """
        Args:
            on_trigger: Callback function that takes a prompt string and
                        feeds it to the LLM (typically bot.emit_llm_prediction).
            rules: List of behavior rules. Uses DEFAULT_RULES if None.
        """
        self._on_trigger = on_trigger
        self.rules = rules or list(DEFAULT_RULES)
        self._last_user_interaction = time.time()
        self._silence_threshold = 60  # seconds before considered "silent"
        self._cooldown_after_reply = 15  # seconds to wait after user interaction
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        logger.info(f"Autonomous behavior {'enabled' if value else 'disabled'}")

    def on_user_interaction(self):
        """Call this when a user (danmaku/ASR) interacts with the bot.

        Resets the silence timer and adds cooldown before next autonomous action.
        """
        self._last_user_interaction = time.time()

    def on_tick(self, elapsed: int):
        """Called every second from the SecondEvent handler.

        Checks all rules and triggers the first matching behavior.
        """
        if not self._enabled:
            return

        # Don't act too soon after user interaction
        time_since_interaction = time.time() - self._last_user_interaction
        if time_since_interaction < self._cooldown_after_reply:
            return

        for rule in self.rules:
            if rule.should_trigger(elapsed):
                # For silence-react, require actual silence
                if rule.behavior_type == BehaviorType.SILENCE_REACT:
                    if time_since_interaction < self._silence_threshold:
                        continue

                prompt = rule.pick_prompt()
                if prompt:
                    logger.info(f"Autonomous behavior [{rule.behavior_type.value}]: {prompt[:50]}...")
                    # Prefix to distinguish autonomous from reactive
                    self._on_trigger(f"[自主行为]{prompt}")
                break  # Only one autonomous action per tick
