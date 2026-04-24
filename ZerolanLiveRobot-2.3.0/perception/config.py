"""Perception module configuration models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class VisualPerceptionMode(str, Enum):
    DISABLED = "disabled"
    PASSIVE = "passive"        # Only observe, inject context silently
    REACTIVE = "reactive"      # Observe + react to significant visual events
    PROACTIVE = "proactive"    # Full closed loop: observe + react + trigger autonomous behavior


class VisualCaptureConfig(BaseModel):
    enable: bool = Field(default=False)
    mode: VisualPerceptionMode = Field(default=VisualPerceptionMode.PASSIVE)
    capture_interval: float = Field(default=10.0, description="Seconds between captures.")
    window_title: str = Field(default="", description="Window title to capture (empty=active window).")
    capture_scale: float = Field(default=0.99, description="Scale factor for capture region.")


class VisualAnalysisConfig(BaseModel):
    enable_ocr: bool = Field(default=True, description="Use OCR for text extraction.")
    enable_imgcap: bool = Field(default=True, description="Use image captioning.")
    ocr_confidence_threshold: float = Field(default=0.6, description="Minimum OCR confidence.")
    max_context_length: int = Field(default=200, description="Max chars of visual context to inject.")


class VisualEventConfig(BaseModel):
    enable: bool = Field(default=False, description="Detect visual events (scene changes).")
    change_threshold: float = Field(default=0.3, description="pHash distance threshold (0=same, 1=different).")
    event_cooldown: float = Field(default=30.0, description="Min seconds between visual events.")


class PerceptionConfig(BaseModel):
    visual: VisualCaptureConfig = Field(default=VisualCaptureConfig())
    analysis: VisualAnalysisConfig = Field(default=VisualAnalysisConfig())
    events: VisualEventConfig = Field(default=VisualEventConfig())
