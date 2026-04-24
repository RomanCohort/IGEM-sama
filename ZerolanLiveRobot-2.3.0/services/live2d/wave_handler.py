from live2d.utils.lipsync import WavHandler
import soundfile as sf
import time
import numpy as np
from loguru import logger
from typing import Dict


class Live2DWaveHandler(WavHandler):
    def __init__(self):
        super().__init__()
        self._spectral_bands: Dict[str, float] = {}
        self._rms_smoothed: float = 0.0
        self._rms_smoothing: float = 0.7  # EMA smoothing factor

    def Start(self, filePath: str) -> None:
        # Use `soundfile` instead of `wave`, because it supports more audio types.
        self.ReleasePcmData()
        self._spectral_bands.clear()
        self._rms_smoothed = 0.0
        try:
            data, samplerate = sf.read(filePath, dtype='float32')

            self.sampleRate = samplerate
            self.numChannels = data.ndim if data.ndim > 1 else 1
            self.numFrames = len(data)

            self.pcmData = data

            if self.numChannels == 1:
                self.pcmData = self.pcmData.reshape(1, -1)
            else:
                self.pcmData = self.pcmData.T  # shape: (channels, frames)

            self.startTime = time.time()
            self.lastOffset = 0

        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            self.ReleasePcmData()

    def GetSmoothedRms(self) -> float:
        """Return RMS with exponential moving average smoothing."""
        raw_rms = self.GetRms()
        self._rms_smoothed = (self._rms_smoothing * self._rms_smoothed +
                              (1 - self._rms_smoothing) * raw_rms)
        return self._rms_smoothed

    def GetSpectralFeatures(self) -> Dict[str, float]:
        """Return frequency band energies for current playback position.

        Computes a short-time FFT on a 20-30ms window around the current
        playback offset in the PCM buffer.

        Returns:
            Dict with keys:
              - 'low': energy in 80-500Hz band
              - 'mid': energy in 500-2000Hz band
              - 'high': energy in 2000-5000Hz band
              - 'centroid': spectral centroid (0-1 normalized)
              - 'flatness': spectral flatness (0-1 normalized)
        """
        if self.pcmData is None or len(self.pcmData.shape) < 2 or self.pcmData.shape[1] == 0:
            return {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'centroid': 0.5, 'flatness': 0.5}

        # Get current playback offset
        current_offset = self.lastOffset
        if current_offset >= self.pcmData.shape[1]:
            return {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'centroid': 0.5, 'flatness': 0.5}

        # Use first channel for spectral analysis
        channel_data = self.pcmData[0]

        # 25ms window (standard for speech analysis)
        window_size = int(self.sampleRate * 0.025)
        start = max(0, current_offset - window_size // 2)
        end = min(len(channel_data), start + window_size)
        start = max(0, end - window_size)  # Ensure we get exactly window_size samples

        if end - start < 64:  # Too few samples for meaningful FFT
            return {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'centroid': 0.5, 'flatness': 0.5}

        window = channel_data[start:end].copy()

        # Apply Hann window to reduce spectral leakage
        hann = np.hanning(len(window))
        window = window * hann

        # Compute FFT
        fft = np.fft.rfft(window)
        magnitude = np.abs(fft)

        # Frequency resolution
        freq_resolution = self.sampleRate / len(window)
        freqs = np.arange(len(magnitude)) * freq_resolution

        # Compute band energies
        def band_energy(low_freq, high_freq):
            mask = (freqs >= low_freq) & (freqs < high_freq)
            if not np.any(mask):
                return 0.0
            return float(np.mean(magnitude[mask] ** 2))

        low_energy = band_energy(80, 500)
        mid_energy = band_energy(500, 2000)
        high_energy = band_energy(2000, 5000)

        # Spectral centroid (normalized to 0-1)
        total_energy = low_energy + mid_energy + high_energy
        if total_energy > 1e-10:
            weighted_sum = np.sum(freqs[:len(magnitude)] * magnitude[:len(freqs)] ** 2)
            magnitude_sum = np.sum(magnitude[:len(freqs)] ** 2)
            if magnitude_sum > 1e-10:
                centroid = weighted_sum / magnitude_sum
                centroid = min(centroid / (self.sampleRate / 2), 1.0)
            else:
                centroid = 0.5
        else:
            centroid = 0.5

        # Spectral flatness (geometric mean / arithmetic mean)
        if total_energy > 1e-10 and np.all(magnitude > 0):
            valid_mask = (freqs >= 80) & (freqs < 5000)
            valid_mag = magnitude[valid_mask]
            if len(valid_mag) > 0 and np.all(valid_mag > 0):
                log_mean = np.mean(np.log(valid_mag))
                lin_mean = np.mean(valid_mag)
                if lin_mean > 0:
                    flatness = float(np.exp(log_mean) / lin_mean)
                    flatness = min(max(flatness, 0.0), 1.0)
                else:
                    flatness = 0.5
            else:
                flatness = 0.5
        else:
            flatness = 0.5

        self._spectral_bands = {
            'low': low_energy,
            'mid': mid_energy,
            'high': high_energy,
            'centroid': centroid,
            'flatness': flatness,
        }
        return self._spectral_bands
