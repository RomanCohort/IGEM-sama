"""Smooth interpolation between lip sync frames for natural mouth movement.

Creates the natural asymmetry seen in human speech:
fast mouth opening (attack) and slower mouth closing (release).
"""

from typing import Dict


class LipSyncInterpolator:
    """Interpolates Live2D mouth parameter values between frames.

    Uses different coefficients for rising (mouth opening) vs falling
    (mouth closing) to create natural-looking mouth movement.
    """

    def __init__(self, smoothing: float = 0.3, attack: float = 0.5, release: float = 0.2):
        self._smoothing = smoothing
        self._attack = attack
        self._release = release
        self._current: Dict[str, float] = {}

    def interpolate(self, targets: Dict[str, float], dt: float = 1 / 120) -> Dict[str, float]:
        """Smoothly interpolate current values toward targets.

        Args:
            targets: Target parameter values {param_id: value}.
            dt: Time delta since last frame in seconds.

        Returns:
            Interpolated parameter values.
        """
        result = {}
        for param_id, target in targets.items():
            current = self._current.get(param_id, 0.0)

            # Different rates for rising vs falling
            if target > current:
                # Mouth opening: fast attack
                rate = self._attack
            else:
                # Mouth closing: slower release
                rate = self._release

            # Exponential smoothing with direction-dependent speed
            alpha = 1.0 - (1.0 - rate) ** (dt * 120)
            new_value = current + (target - current) * alpha

            self._current[param_id] = new_value
            result[param_id] = new_value

        # Decay parameters that are no longer in targets
        for param_id in list(self._current.keys()):
            if param_id not in targets:
                current = self._current[param_id]
                alpha = 1.0 - (1.0 - self._release) ** (dt * 120)
                new_value = current * (1.0 - alpha)
                if abs(new_value) < 0.01:
                    del self._current[param_id]
                else:
                    self._current[param_id] = new_value

        return result

    def reset(self):
        """Reset all interpolated values to zero."""
        self._current.clear()
