"""Voice conversion pipeline for IGEM-sama.

Wraps the existing TTS pipeline with optional RVC voice conversion
post-processing for a distinctive, recognizable character voice.
"""

from pipeline.voice.config import VoicePipelineConfig, RVCConfig, VoiceConversionBackend
from pipeline.voice.voice_pipeline import VoicePipeline

__all__ = [
    "VoicePipelineConfig",
    "RVCConfig",
    "VoiceConversionBackend",
    "VoicePipeline",
]
