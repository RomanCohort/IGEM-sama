from pydantic import BaseModel, Field
from typing import Optional


class LipSyncConfig(BaseModel):
    """Configuration for enhanced lip sync with viseme mapping."""
    enable_enhanced: bool = Field(default=False,
                                  description="Enable enhanced viseme-based lip sync. False uses simple RMS.")
    interpolation_smoothing: float = Field(default=0.3,
                                           description="Smoothing factor for interpolation (0=instant, 1=no change).")
    attack_speed: float = Field(default=0.5,
                                description="Mouth opening speed (higher = faster opening).")
    release_speed: float = Field(default=0.2,
                                 description="Mouth closing speed (lower = more natural, slower close).")
    silence_threshold: float = Field(default=0.02,
                                     description="RMS below this = silence (mouth closes).")
    intensity_scale: float = Field(default=3.0,
                                   description="Multiplier for RMS-to-mouth-open mapping.")


class Live2DViewerConfig(BaseModel):
    enable: bool = Field(default=True,
                         description="Enable Live2d Viewer?")
    model3_json_file: str = Field(default="./resources/static/models/live2d", description="Path of `xxx.model3.json`")
    auto_lip_sync: bool = Field(default=True, description="Auto lip sync.")
    auto_blink: bool = Field(default=True, description="Auto eye blink.")
    auto_breath: bool = Field(default=True, description="Audio eye blink.")
    win_height: int = Field(default=960, description="Window height.")
    win_width: int = Field(default=960, description="Window width.")
    lip_sync: Optional[LipSyncConfig] = Field(default=None, description="Enhanced lip sync configuration.")
