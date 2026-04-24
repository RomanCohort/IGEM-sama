"""Viseme engine for enhanced lip sync in IGEM-sama.

Classifies audio spectral features into Chinese vowel visemes (A, I, U, E, O)
and maps them to multiple Live2D mouth parameters for natural mouth movement.

Uses rule-based spectral band analysis — no ML model, zero latency.
"""

from typing import Dict

from emotion.expression_map import PARAM_MOUTH_OPEN_Y, PARAM_MOUTH_FORM
from services.live2d.lip_sync_interpolator import LipSyncInterpolator


# Viseme-to-Live2D parameter mapping
# Each viseme defines target values for mouth-related parameters
VISEME_PARAMS: Dict[str, Dict[str, float]] = {
    "rest": {PARAM_MOUTH_OPEN_Y: 0.0, PARAM_MOUTH_FORM: 0.0},
    "A":    {PARAM_MOUTH_OPEN_Y: 0.85, PARAM_MOUTH_FORM: 0.2},   # Wide open, neutral form
    "I":    {PARAM_MOUTH_OPEN_Y: 0.25, PARAM_MOUTH_FORM: 0.8},   # Slightly open, wide smile
    "U":    {PARAM_MOUTH_OPEN_Y: 0.35, PARAM_MOUTH_FORM: -0.6},  # Slightly open, pursed
    "E":    {PARAM_MOUTH_OPEN_Y: 0.55, PARAM_MOUTH_FORM: 0.5},   # Mid open, slight smile
    "O":    {PARAM_MOUTH_OPEN_Y: 0.65, PARAM_MOUTH_FORM: -0.4},  # Open, rounded
}


class VisemeEngine:
    """Classifies audio frames into visemes and maps to Live2D parameters.

    Uses spectral band energy ratios (low/mid/high frequency) to determine
    the current vowel being spoken. This is a lightweight, rule-based approach
    with zero ML latency.

    Usage:
        engine = VisemeEngine(config)
        params = engine.process_frame(rms, spectral_features, is_speaking)
        for param_id, value in params.items():
            model.SetParameterValue(param_id, value)
    """

    def __init__(self, config=None):
        # Config fields with defaults
        self._intensity_scale = getattr(config, 'intensity_scale', 3.0) if config else 3.0
        self._silence_threshold = getattr(config, 'silence_threshold', 0.02) if config else 0.02

        # Interpolator for smooth transitions
        smoothing = getattr(config, 'interpolation_smoothing', 0.3) if config else 0.3
        attack = getattr(config, 'attack_speed', 0.5) if config else 0.5
        release = getattr(config, 'release_speed', 0.2) if config else 0.2
        self._interpolator = LipSyncInterpolator(
            smoothing=smoothing, attack=attack, release=release
        )

        self._current_viseme = "rest"
        self._was_speaking = False

    def process_frame(self, rms: float, spectral_features: Dict[str, float],
                      is_speaking: bool) -> Dict[str, float]:
        """Process a single audio frame and return Live2D mouth parameter values.

        Args:
            rms: Current audio RMS amplitude.
            spectral_features: Dict with keys 'low', 'mid', 'high', 'centroid', 'flatness'.
            is_speaking: Whether speech is currently detected.

        Returns:
            Dict of {param_id: value} for Live2D mouth parameters.
        """
        if not is_speaking or rms < self._silence_threshold:
            # Transition to rest
            self._current_viseme = "rest"
            self._was_speaking = False
            return self._interpolator.interpolate(VISEME_PARAMS["rest"])

        # Classify viseme from spectral features
        viseme = self._classify_viseme(rms, spectral_features)
        self._current_viseme = viseme
        self._was_speaking = True

        # Map viseme to parameter targets
        targets = self._map_viseme_to_params(viseme, rms)

        # Apply interpolation
        return self._interpolator.interpolate(targets)

    def _classify_viseme(self, rms: float, spectral: Dict[str, float]) -> str:
        """Classify current audio frame into a viseme using spectral bands.

        Chinese vowel formant characteristics:
          - A: High low-freq energy, low high-freq (F1 ~1000Hz)
          - I: High high-freq energy, low low-freq (F2 ~2500Hz)
          - U: Low overall, dominant low-freq, very low high-freq
          - E: Balanced mid-freq, moderate high-freq
          - O: Moderate low-freq, low high-freq, rounded formant

        Spectral features used:
          - 'low' (80-500Hz), 'mid' (500-2000Hz), 'high' (2000-5000Hz)
          - 'centroid' (spectral centroid frequency)
          - 'flatness' (spectral flatness measure)
        """
        low = spectral.get('low', 0.0)
        mid = spectral.get('mid', 0.0)
        high = spectral.get('high', 0.0)
        centroid = spectral.get('centroid', 0.5)
        flatness = spectral.get('flatness', 0.5)

        total = low + mid + high
        if total < 1e-6:
            return "rest"

        # Normalize band energies
        low_ratio = low / total
        mid_ratio = mid / total
        high_ratio = high / total

        # Decision tree based on spectral ratios and centroid
        if low_ratio > 0.55:
            # Dominant low frequency
            if high_ratio < 0.15:
                return "U"   # U: very low high-freq, dominant low
            else:
                return "A"   # A: strong low-freq (F1), some high
        elif high_ratio > 0.40:
            # Dominant high frequency
            if mid_ratio < 0.30:
                return "I"   # I: high F2, weak mid
            else:
                return "E"   # E: high-freq with mid support
        elif mid_ratio > 0.40:
            # Dominant mid frequency
            if low_ratio > 0.30:
                return "O"   # O: rounded, mid+low
            else:
                return "E"   # E: mid-focused
        else:
            # Relatively balanced — use centroid
            if centroid < 0.35:
                return "A"
            elif centroid > 0.65:
                return "I"
            elif flatness > 0.6:
                return "O"
            else:
                return "E"

    def _map_viseme_to_params(self, viseme: str, rms: float) -> Dict[str, float]:
        """Map viseme + RMS intensity to Live2D parameter target values.

        Args:
            viseme: Classified viseme (A/I/U/E/O/rest).
            rms: Current audio RMS amplitude for intensity scaling.

        Returns:
            Dict of {param_id: target_value}.
        """
        base = VISEME_PARAMS.get(viseme, VISEME_PARAMS["rest"])
        targets = {}

        # Scale mouth open by RMS intensity
        intensity = min(rms * self._intensity_scale, 1.0)

        for param_id, base_value in base.items():
            if param_id == PARAM_MOUTH_OPEN_Y:
                # Scale open amount by audio intensity
                targets[param_id] = base_value * intensity
            elif param_id == PARAM_MOUTH_FORM:
                # Blend mouth form toward viseme target based on intensity
                targets[param_id] = base_value * (0.5 + 0.5 * intensity)
            else:
                targets[param_id] = base_value

        return targets

    def get_current_viseme(self) -> str:
        """Return the last classified viseme."""
        return self._current_viseme
