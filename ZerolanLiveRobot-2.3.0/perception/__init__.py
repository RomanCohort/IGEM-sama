"""Multimodal perception system for IGEM-sama.

Provides autonomous visual awareness through periodic screen capture
and analysis, enabling the character to "see" and react to screen content.
"""

from perception.config import PerceptionConfig, VisualCaptureConfig, VisualAnalysisConfig, VisualEventConfig, VisualPerceptionMode
from perception.visual_loop import VisualLoop, VisualObservation
from perception.perception_context import PerceptionContext
from perception.event_handler import VisualEventHandler

__all__ = [
    "PerceptionConfig",
    "VisualCaptureConfig",
    "VisualAnalysisConfig",
    "VisualEventConfig",
    "VisualPerceptionMode",
    "VisualLoop",
    "VisualObservation",
    "PerceptionContext",
    "VisualEventHandler",
]
