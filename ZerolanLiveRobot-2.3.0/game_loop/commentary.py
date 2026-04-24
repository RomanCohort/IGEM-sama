"""Game commentary as autonomous behavior.

Generates periodic game commentary that is fed to emit_llm_prediction,
creating the "streamer talking about their gameplay" experience.
"""

import random
import time
from typing import Callable, List, Optional

from loguru import logger

from game_loop.config import GameLoopConfig
from game_loop.game_perception import GameState


class GameCommentary:
    """Generates game commentary as autonomous behavior.

    Usage:
        commentary = GameCommentary(on_trigger, config)
        if commentary.should_comment(game_state, elapsed):
            commentary.generate_commentary(game_state)
    """

    def __init__(self, on_trigger: Callable, config: GameLoopConfig):
        self._on_trigger = on_trigger
        self._config = config
        self._next_commentary_time: float = 0
        self._reset_timer()

    def should_comment(self, game_state: Optional[GameState], elapsed: int) -> bool:
        """Check if it is time to generate commentary."""
        return time.time() >= self._next_commentary_time

    def generate_commentary(self, game_state: Optional[GameState]):
        """Generate a commentary prompt with game context and trigger it."""
        # Pick a random commentary prompt
        prompts = self._config.commentary_prompts
        prompt = random.choice(prompts) if prompts else "你对游戏发表一下感想。"

        # Add game context if available
        if game_state and game_state.game_context:
            prompt = f"[游戏画面: {game_state.game_context[:100]}] {prompt}"

        logger.info(f"Game commentary: {prompt[:50]}...")
        self._on_trigger(prompt)
        self._reset_timer()

    def _reset_timer(self):
        """Set next commentary time with random interval."""
        lo, hi = self._config.commentary_interval_range
        self._next_commentary_time = time.time() + random.randint(lo, hi)
