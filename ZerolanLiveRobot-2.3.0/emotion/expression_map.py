"""Emotion-to-Live2D Expression Mapping for IGEM-sama.

Maps EmotionLabel states to Live2D parameter values and motion triggers
for the Hiyori Pro model.

Two modes of expression:
  1. Parameter-based: set individual Live2D parameter values for fine-grained
     facial control (eye, brow, mouth, body angles).
  2. Motion-based: trigger pre-built motion3.json files for full-body
     animations (e.g. happy wave, surprised jump).

Compatible with live2d-py v5.x and v6.x (Python 3.13+).
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from loguru import logger

from common.ver_check import is_live2d_py_version_less_than


# ============================================================
# Live2D Cubism standard parameter IDs for Hiyori Pro model
# (from hiyori_pro_mic.cdi3.json)
# These string IDs work with both live2d-py v5 and v6.
# ============================================================

# Face
PARAM_ANGLE_X = "ParamAngleX"
PARAM_ANGLE_Y = "ParamAngleY"
PARAM_ANGLE_Z = "ParamAngleZ"
PARAM_CHEEK = "ParamCheek"

# Eyes
PARAM_EYE_L_OPEN = "ParamEyeLOpen"
PARAM_EYE_R_OPEN = "ParamEyeROpen"
PARAM_EYE_L_SMILE = "ParamEyeLSmile"
PARAM_EYE_R_SMILE = "ParamEyeRSmile"
PARAM_EYE_BALL_X = "ParamEyeBallX"
PARAM_EYE_BALL_Y = "ParamEyeBallY"

# Brows
PARAM_BROW_L_Y = "ParamBrowLY"
PARAM_BROW_R_Y = "ParamBrowRY"
PARAM_BROW_L_ANGLE = "ParamBrowLAngle"
PARAM_BROW_R_ANGLE = "ParamBrowRAngle"
PARAM_BROW_L_FORM = "ParamBrowLForm"
PARAM_BROW_R_FORM = "ParamBrowRForm"

# Mouth
PARAM_MOUTH_FORM = "ParamMouthForm"
PARAM_MOUTH_OPEN_Y = "ParamMouthOpenY"

# Body
PARAM_BODY_ANGLE_X = "ParamBodyAngleX"
PARAM_BODY_ANGLE_Y = "ParamBodyAngleY"
PARAM_BODY_ANGLE_Z = "ParamBodyAngleZ"
PARAM_BREATH = "ParamBreath"

# Arms
PARAM_ARM_L_A = "ParamArmLA"
PARAM_ARM_R_A = "ParamArmRA"

# Microphone
PARAM_MIC = "mic"


# ============================================================
# Expression Preset: parameter-based facial expression
# ============================================================

@dataclass
class ExpressionPreset:
    """A set of Live2D parameter values that form an expression.

    Each param maps to a (value, weight) tuple:
      - value: the target parameter value (usually -1 to 1)
      - weight: blending weight (0 to 1), controls how strongly to apply
    """
    params: Dict[str, Tuple[float, float]] = field(default_factory=dict)


# ============================================================
# Motion mapping: emotion → motion3.json file paths
# Based on emotion_actions.json from the original model config
# ============================================================

MOTION_MAP: Dict[str, List[dict]] = {
    "happy": [
        {"group": "TapBody", "no": 1},
        {"group": "TapBody", "no": 4},
        {"group": "TapBody", "no": 5},
        {"group": "TapBody", "no": 7},
    ],
    "angry": [
        {"group": "TapBody", "no": 8},
    ],
    "sad": [
        {"group": "TapBody", "no": 9},
    ],
    "excited": [
        {"group": "TapBody", "no": 6},
    ],
    "curious": [
        {"group": "TapBody", "no": 2},
    ],
    "shy": [
        {"group": "TapBody", "no": 3},
    ],
    "proud": [
        {"group": "TapBody", "no": 4},
        {"group": "TapBody", "no": 7},
    ],
    "calm": [
        {"group": "Idle", "no": 0},
    ],
    "neutral": [
        {"group": "Idle", "no": 0},
    ],
}

# Motion priority levels for v6 API
MOTION_PRIORITY_IDLE = 0
MOTION_PRIORITY_NORMAL = 1
MOTION_PRIORITY_FORCE = 2


# ============================================================
# Expression presets for each emotion (parameter-based)
# ============================================================

EXPRESSION_MAP: Dict[str, ExpressionPreset] = {
    "happy": ExpressionPreset({
        PARAM_EYE_L_OPEN: (0.7, 0.6),
        PARAM_EYE_R_OPEN: (0.7, 0.6),
        PARAM_EYE_L_SMILE: (0.8, 0.7),
        PARAM_EYE_R_SMILE: (0.8, 0.7),
        PARAM_BROW_L_Y: (0.3, 0.4),
        PARAM_BROW_R_Y: (0.3, 0.4),
        PARAM_MOUTH_FORM: (1.0, 0.7),
        PARAM_CHEEK: (0.6, 0.5),
        PARAM_BODY_ANGLE_Z: (-2.0, 0.3),
    }),
    "excited": ExpressionPreset({
        PARAM_EYE_L_OPEN: (1.2, 0.7),
        PARAM_EYE_R_OPEN: (1.2, 0.7),
        PARAM_EYE_L_SMILE: (0.3, 0.4),
        PARAM_EYE_R_SMILE: (0.3, 0.4),
        PARAM_BROW_L_Y: (0.6, 0.6),
        PARAM_BROW_R_Y: (0.6, 0.6),
        PARAM_BROW_L_ANGLE: (0.4, 0.5),
        PARAM_BROW_R_ANGLE: (0.4, 0.5),
        PARAM_MOUTH_FORM: (0.8, 0.6),
        PARAM_MOUTH_OPEN_Y: (0.4, 0.4),
        PARAM_BODY_ANGLE_X: (3.0, 0.3),
        PARAM_CHEEK: (0.4, 0.3),
    }),
    "calm": ExpressionPreset({
        PARAM_EYE_L_OPEN: (0.9, 0.3),
        PARAM_EYE_R_OPEN: (0.9, 0.3),
        PARAM_MOUTH_FORM: (0.2, 0.2),
        PARAM_BREATH: (0.5, 0.2),
    }),
    "curious": ExpressionPreset({
        PARAM_EYE_L_OPEN: (1.1, 0.5),
        PARAM_EYE_R_OPEN: (1.1, 0.5),
        PARAM_EYE_BALL_Y: (0.3, 0.4),
        PARAM_BROW_L_Y: (0.5, 0.5),
        PARAM_BROW_R_Y: (0.5, 0.5),
        PARAM_BROW_L_ANGLE: (0.3, 0.4),
        PARAM_BROW_R_ANGLE: (0.3, 0.4),
        PARAM_ANGLE_X: (5.0, 0.3),
        PARAM_ANGLE_Y: (3.0, 0.3),
    }),
    "sad": ExpressionPreset({
        PARAM_EYE_L_OPEN: (0.6, 0.5),
        PARAM_EYE_R_OPEN: (0.6, 0.5),
        PARAM_BROW_L_Y: (-0.4, 0.5),
        PARAM_BROW_R_Y: (-0.4, 0.5),
        PARAM_BROW_L_ANGLE: (-0.5, 0.5),
        PARAM_BROW_R_ANGLE: (-0.5, 0.5),
        PARAM_MOUTH_FORM: (-0.6, 0.5),
        PARAM_BODY_ANGLE_Z: (3.0, 0.2),
    }),
    "angry": ExpressionPreset({
        PARAM_EYE_L_OPEN: (0.8, 0.6),
        PARAM_EYE_R_OPEN: (0.8, 0.6),
        PARAM_BROW_L_Y: (-0.3, 0.6),
        PARAM_BROW_R_Y: (-0.3, 0.6),
        PARAM_BROW_L_ANGLE: (0.6, 0.6),
        PARAM_BROW_R_ANGLE: (0.6, 0.6),
        PARAM_BROW_L_FORM: (-0.5, 0.5),
        PARAM_BROW_R_FORM: (-0.5, 0.5),
        PARAM_MOUTH_FORM: (-0.4, 0.5),
    }),
    "shy": ExpressionPreset({
        PARAM_EYE_L_OPEN: (0.5, 0.5),
        PARAM_EYE_R_OPEN: (0.5, 0.5),
        PARAM_EYE_BALL_Y: (-0.3, 0.4),
        PARAM_BROW_L_Y: (0.2, 0.3),
        PARAM_BROW_R_Y: (0.2, 0.3),
        PARAM_MOUTH_FORM: (0.3, 0.4),
        PARAM_CHEEK: (0.8, 0.6),
        PARAM_ANGLE_Z: (-5.0, 0.3),
    }),
    "proud": ExpressionPreset({
        PARAM_EYE_L_OPEN: (0.9, 0.4),
        PARAM_EYE_R_OPEN: (0.9, 0.4),
        PARAM_EYE_L_SMILE: (0.4, 0.4),
        PARAM_EYE_R_SMILE: (0.4, 0.4),
        PARAM_BROW_L_Y: (0.4, 0.5),
        PARAM_BROW_R_Y: (0.4, 0.5),
        PARAM_MOUTH_FORM: (0.6, 0.5),
        PARAM_ANGLE_Y: (-3.0, 0.3),
    }),
    "neutral": ExpressionPreset({
        PARAM_EYE_L_OPEN: (1.0, 0.2),
        PARAM_EYE_R_OPEN: (1.0, 0.2),
        PARAM_BROW_L_Y: (0.0, 0.2),
        PARAM_BROW_R_Y: (0.0, 0.2),
        PARAM_MOUTH_FORM: (0.0, 0.2),
    }),
}


class Live2DExpressionDriver:
    """Drives Live2D model expressions based on emotion state.

    Supports two modes:
      - Parameter mode: sets individual Live2D parameters for fine expression
      - Motion mode: triggers pre-built animations via StartMotion

    Compatible with live2d-py v5.x and v6.x.

    Usage:
        driver = Live2DExpressionDriver(live2d_viewer)
        driver.apply_emotion("happy", intensity=0.7)
        driver.trigger_motion("happy")  # Play a motion animation
    """

    def __init__(self, viewer=None):
        self._viewer = viewer
        self._current_emotion = "neutral"
        self._current_intensity = 0.0
        self._last_motion_emotion = ""
        self._is_v6 = not is_live2d_py_version_less_than("6.0")

    def set_viewer(self, viewer):
        """Set or update the Live2D viewer reference."""
        self._viewer = viewer

    def apply_emotion(self, emotion_label: str, intensity: float = 0.6):
        """Apply a Live2D expression based on the emotion label and intensity.

        Args:
            emotion_label: One of the EmotionLabel values (e.g. "happy", "sad").
            intensity: Overall intensity 0-1, scales all parameter weights.
        """
        if self._viewer is None:
            return

        preset = EXPRESSION_MAP.get(emotion_label)
        if preset is None:
            preset = EXPRESSION_MAP["neutral"]

        self._current_emotion = emotion_label
        self._current_intensity = intensity

        try:
            model = self._viewer._canvas.model
            for param_id, (value, weight) in preset.params.items():
                scaled_weight = weight * intensity
                # v6 SetParameterValue(param_id, value) — no weight param
                # We blend the value manually by scaling it
                blended_value = value * scaled_weight
                model.SetParameterValue(param_id, blended_value)
        except Exception as e:
            logger.debug(f"Live2D expression apply failed: {e}")

    def trigger_motion(self, emotion_label: str):
        """Trigger a motion animation for the given emotion.

        Randomly selects one motion from the MOTION_MAP for variety.
        Uses live2d-py v6 StartMotion API (group, no, priority).

        Args:
            emotion_label: Emotion to trigger a motion for.
        """
        if self._viewer is None:
            return

        motions = MOTION_MAP.get(emotion_label)
        if not motions:
            return

        motion = random.choice(motions)

        try:
            model = self._viewer._canvas.model
            group = motion["group"]
            no = motion["no"]
            # v6 API: StartMotion(group, no, priority)
            if self._is_v6:
                model.StartMotion(group, no, MOTION_PRIORITY_NORMAL)
            else:
                # v5 API fallback — may not support group/no directly
                model.StartMotion(group, no, MOTION_PRIORITY_NORMAL)
            self._last_motion_emotion = emotion_label
            logger.debug(f"Live2D motion triggered: {group}:{no} for {emotion_label}")
        except Exception as e:
            logger.debug(f"Live2D motion trigger failed: {e}")

    def show_mic(self, visible: bool = True):
        """Show or hide the microphone accessory.

        Args:
            visible: True to show mic, False to hide.
        """
        if self._viewer is None:
            return
        try:
            model = self._viewer._canvas.model
            model.SetParameterValue(PARAM_MIC, 1.0 if visible else 0.0)
        except Exception as e:
            logger.debug(f"Live2D mic toggle failed: {e}")

    def get_current(self) -> Tuple[str, float]:
        """Return (current_emotion, current_intensity)."""
        return self._current_emotion, self._current_intensity
