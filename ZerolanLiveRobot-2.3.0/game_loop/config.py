"""Game loop configuration models."""

from enum import Enum
from typing import List, Tuple

from pydantic import BaseModel, Field


class GamePlatform(str, Enum):
    MINECRAFT = "minecraft"
    SCREEN_BASED = "screen_based"


class GameLoopConfig(BaseModel):
    """Configuration for the game interaction loop."""
    enable: bool = Field(default=False)
    platform: GamePlatform = Field(default=GamePlatform.MINECRAFT)
    # Screen capture settings
    capture_interval: float = Field(default=2.0, description="Seconds between screen captures.")
    capture_region: str = Field(default="Minecraft", description="Window title to capture.")
    # Decision settings
    decision_interval: float = Field(default=5.0, description="Seconds between game decisions.")
    max_actions_per_decision: int = Field(default=3, description="Max actions per decision cycle.")
    # Commentary settings
    commentary_interval_range: Tuple[int, int] = Field(default=(30, 90),
        description="Random interval range for commentary (seconds).")
    commentary_prompts: List[str] = Field(default=[
        "你正在玩游戏，描述一下你刚才的操作和想法。",
        "你对刚才游戏里发生的事情发表一下感想。",
        "向观众解释一下你现在的游戏策略。",
    ])
    # Minecraft-specific
    minecraft_ws_host: str = Field(default="127.0.0.1")
    minecraft_ws_port: int = Field(default=11007)
