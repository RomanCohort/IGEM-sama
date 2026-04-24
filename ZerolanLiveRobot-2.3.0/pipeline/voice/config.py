"""Voice pipeline configuration models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VoiceConversionBackend(str, Enum):
    NONE = "none"
    RVC = "rvc"
    SO_VITS_SVC = "so_vits_svc"


class RVCConfig(BaseModel):
    """Configuration for RVC voice conversion model."""
    model_path: str = Field(default="models/rvc/igem_sama.pth",
                            description="Path to trained RVC model file.")
    index_path: str = Field(default="", description="Path to voice feature index file.")
    device: str = Field(default="cuda", description="Device: 'cuda' or 'cpu'.")
    f0_method: str = Field(default="rmvpe", description="Pitch extraction: 'pm', 'harvest', 'crepe', 'rmvpe'.")
    f0_up_key: int = Field(default=0, description="Pitch shift in semitones.")
    index_rate: float = Field(default=0.75, description="Feature search blending ratio.")
    filter_radius: int = Field(default=3, description="Median filter radius for pitch.")
    resample_sr: int = Field(default=0, description="Resample output sample rate (0=auto).")
    rms_mix_rate: float = Field(default=0.25, description="Volume envelope blending.")
    protect: float = Field(default=0.33, description="Voiceless consonant protection.")


class VoicePipelineConfig(BaseModel):
    """Configuration for the voice conversion pipeline."""
    enable: bool = Field(default=False, description="Enable voice conversion post-processing.")
    backend: VoiceConversionBackend = Field(default=VoiceConversionBackend.RVC)
    rvc: RVCConfig = Field(default=RVCConfig())
    tts_pitch_shift: int = Field(default=0, description="Global pitch shift for TTS output (semitones).")
    tts_speed: float = Field(default=1.0, description="TTS speed multiplier.")
    tts_emotion_strength: float = Field(default=1.0, description="Emotion expression strength.")


class VoiceTrainConfig(BaseModel):
    """Configuration for voice model training."""
    dataset_dir: str = Field(default="data/voice_dataset",
                             description="Directory containing training audio files.")
    output_dir: str = Field(default="models/rvc",
                            description="Directory to save trained model.")
    model_name: str = Field(default="igem_sama")
    batch_size: int = Field(default=8)
    epochs: int = Field(default=200)
    save_every_n_epochs: int = Field(default=25)
    sample_rate: int = Field(default=40000)
    version: str = Field(default="v2")
