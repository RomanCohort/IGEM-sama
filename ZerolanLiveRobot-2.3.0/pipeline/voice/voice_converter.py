"""RVC-based voice converter for IGEM-sama.

Applies voice conversion to TTS output audio to create a distinctive
character voice. Uses RVC (Retrieval-based Voice Conversion) for
high-quality voice cloning with low latency.
"""

import os
import tempfile

from loguru import logger

from pipeline.voice.config import RVCConfig


class VoiceConverter:
    """Applies voice conversion (RVC) to TTS output audio.

    Loads a trained RVC model and applies voice conversion to transform
    the TTS voice into the target character voice.

    Usage:
        converter = VoiceConverter(rvc_config)
        converter.load_model()
        output_path = converter.convert("tts_output.wav")
    """

    def __init__(self, config: RVCConfig):
        self._config = config
        self._model_loaded = False
        self._rvc_infer = None

    def load_model(self):
        """Load the RVC model into memory."""
        if not os.path.exists(self._config.model_path):
            logger.warning(f"RVC model not found: {self._config.model_path}")
            return False

        try:
            # Try to import RVC inference module
            from rvc_python.infer import RVCInference
            self._rvc_infer = RVCInference(
                model_path=self._config.model_path,
                device=self._config.device,
            )
            self._rvc_infer.load_model()
            if self._config.index_path and os.path.exists(self._config.index_path):
                self._rvc_infer.load_index(self._config.index_path)
            self._model_loaded = True
            logger.info(f"RVC model loaded: {self._config.model_path}")
            return True
        except ImportError:
            logger.warning("rvc-python not installed. Install with: pip install rvc-python")
            return False
        except Exception as e:
            logger.error(f"Failed to load RVC model: {e}")
            return False

    def convert(self, input_audio_path: str, output_audio_path: str = None) -> str:
        """Apply voice conversion to an audio file.

        Args:
            input_audio_path: Path to TTS output WAV file.
            output_audio_path: Path for converted output (temp file if None).

        Returns:
            Path to the converted audio file, or the original path if
            conversion failed.
        """
        if not self._model_loaded or self._rvc_infer is None:
            return input_audio_path

        if output_audio_path is None:
            fd, output_audio_path = tempfile.mkstemp(suffix=".wav", prefix="rvc_")
            os.close(fd)

        try:
            self._rvc_infer.infer(
                input_path=input_audio_path,
                output_path=output_audio_path,
                f0_method=self._config.f0_method,
                f0_up_key=self._config.f0_up_key,
                index_rate=self._config.index_rate,
                filter_radius=self._config.filter_radius,
                resample_sr=self._config.resample_sr,
                rms_mix_rate=self._config.rms_mix_rate,
                protect=self._config.protect,
            )
            logger.debug(f"Voice conversion: {input_audio_path} -> {output_audio_path}")
            return output_audio_path
        except Exception as e:
            logger.error(f"Voice conversion failed: {e}")
            return input_audio_path

    def is_available(self) -> bool:
        """Check if the voice conversion model is loaded and ready."""
        return self._model_loaded

    def unload_model(self):
        """Release GPU memory."""
        if self._rvc_infer is not None:
            try:
                del self._rvc_infer
            except Exception:
                pass
            self._rvc_infer = None
            self._model_loaded = False
            logger.info("RVC model unloaded.")
