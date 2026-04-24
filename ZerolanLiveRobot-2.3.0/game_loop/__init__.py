"""Game interaction loop for IGEM-sama.

Enables autonomous game playing with screen-based visual understanding
and LLM-driven decision making, with live commentary.
"""

from game_loop.config import GameLoopConfig, GamePlatform
from game_loop.game_perception import GamePerception, GameState
from game_loop.game_decision import GameDecision, GameAction
from game_loop.game_action import GameActionExecutor
from game_loop.commentary import GameCommentary

__all__ = [
    "GameLoopConfig",
    "GamePlatform",
    "GamePerception",
    "GameState",
    "GameDecision",
    "GameAction",
    "GameActionExecutor",
    "GameCommentary",
]
