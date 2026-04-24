"""Combined TTS + Voice Conversion pipeline.

Wraps the existing TTSSyncPipeline and adds optional RVC voice conversion
post-processing. When voice conversion is disabled, the pipeline is
transparent and passes through to the base TTS.
"""

import tempfile
import os

import soundfile as sf
from loguru import logger
from zerolan.data.pipeline.tts import TTSPrediction, TTSQuery

from pipeline.tts.tts_sync import TTSSyncPipeline
from pipeline.voice.config import VoicePipelineConfig
from pipeline.voice.voice_converter import VoiceConverter


class VoicePipeline:
    """Combined TTS + Voice Conversion pipeline.

    Wraps the existing TTSSyncPipeline and adds optional voice conversion
    post-processing for a distinctive character voice.

    Usage:
        voice_pipeline = VoicePipeline(tts_pipeline, config)
        prediction = voice_pipeline.predict(query)  # Same interface as TTS
    """

    def __init__(self, tts_pipeline: TTSSyncPipeline, config: VoicePipelineConfig):
        self._tts = tts_pipeline
        self._config = config
        self._converter: VoiceConverter | None = None

        if config.enable and config.backend.value != "none":
            self._converter = VoiceConverter(config.rvc)
            # Try to load model on init
            try:
                self._converter.load_model()
            except Exception as e:
                logger.warning(f"Voice converter model load failed: {e}")

    def predict(self, query: TTSQuery) -> TTSPrediction:
        """Generate TTS audio with optional voice conversion.

        1. Call base TTS pipeline
        2. If voice conversion is enabled and model is available, apply RVC
        3. Return modified TTSPrediction with converted audio

        Args:
            query: TTS query with text and reference audio settings.

        Returns:
            TTSPrediction with (optionally converted) audio data.
        """
        # Step 1: Generate TTS audio
        prediction = self._tts.predict(query=query)

        if prediction is None:
            return None

        # Step 2: Apply voice conversion if available
        if self._converter and self._converter.is_available():
            try:
                prediction = self._apply_voice_conversion(prediction)
            except Exception as e:
                logger.error(f"Voice conversion failed, using raw TTS: {e}")

        return prediction

    def _apply_voice_conversion(self, prediction: TTSPrediction) -> TTSPrediction:
        """Apply RVC voice conversion to a TTS prediction.

        Args:
            prediction: Raw TTS output.

        Returns:
            Prediction with converted audio data.
        """
        # Save TTS output to temp file
        fd, temp_input = tempfile.mkstemp(suffix=".wav", prefix="tts_pre_vc_")
        os.close(fd)

        try:
            with open(temp_input, 'wb') as f:
                f.write(prediction.wave_data)

            # Apply voice conversion
            converted_path = self._converter.convert(temp_input)

            # Read back converted audio
            data, _ = sf.read(converted_path, dtype='float32')
            prediction.wave_data = data.tobytes()

        finally:
            # Clean up temp files
            if os.path.exists(temp_input):
                os.unlink(temp_input)

        return prediction
