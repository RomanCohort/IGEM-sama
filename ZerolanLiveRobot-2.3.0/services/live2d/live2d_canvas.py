"""
Copied and modified from https://github.com/Arkueid/live2d-py/blob/main/package/main_pyqt5_canvas_opacity.py

Updated for live2d-py v0.6.x (Python 3.13+ compatible).

Key change: live2d.init() and glInit() must both be called inside
initializeGL() (invoked via on_init) because the OpenGL context
must be current for v6.

Enhanced with viseme-based lip sync for natural mouth movement.
"""

import math
from typing import Tuple

import live2d.v3 as live2d
from PyQt5.QtCore import Qt
from live2d.v3 import StandardParams

from common.ver_check import is_live2d_py_version_less_than
from services.live2d.opengl_canvas import OpenGLCanvas
from services.live2d.wave_handler import Live2DWaveHandler
from services.live2d.viseme_engine import VisemeEngine


class Live2DCanvas(OpenGLCanvas):
    def __init__(self, path: str, lip_sync_n: int = 3, win_size: Tuple[int, int] = (1920, 1080),
                 lip_sync_config=None):
        super().__init__()
        self.setFixedSize(*win_size)
        self._model_path = path
        self._lipSyncN = lip_sync_n

        self.wavHandler = Live2DWaveHandler()
        self.model: None | live2d.LAppModel = None
        self.setWindowTitle("Live2DCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.radius_per_frame = math.pi * 0.5 / 120
        self.total_radius = 0

        # Enhanced lip sync with viseme engine
        self._enhanced_lip_sync = lip_sync_config is not None and getattr(
            lip_sync_config, 'enable_enhanced', False)
        if self._enhanced_lip_sync:
            self._viseme_engine = VisemeEngine(lip_sync_config)
            self._silence_threshold = getattr(lip_sync_config, 'silence_threshold', 0.02)
        else:
            self._viseme_engine = None
            self._silence_threshold = 0.02

    def on_init(self):
        # v6: both init() and glInit() must be called inside initializeGL
        live2d.init()
        if is_live2d_py_version_less_than("0.6.0"):
            live2d.glewInit()
        else:
            live2d.glInit()
        self.model = live2d.LAppModel()
        self.model.LoadModelJson(self._model_path)
        self.startTimer(int(1000 / 120))

    def timerEvent(self, a0):
        self.update()

    def on_draw(self):
        live2d.clearBuffer()
        if self.wavHandler.Update():
            if self._enhanced_lip_sync and self._viseme_engine:
                # Enhanced: viseme-based multi-parameter lip sync
                rms = self.wavHandler.GetSmoothedRms()
                spectral = self.wavHandler.GetSpectralFeatures()
                is_speaking = rms > self._silence_threshold
                params = self._viseme_engine.process_frame(rms, spectral, is_speaking)
                for param_id, value in params.items():
                    self.model.SetParameterValue(param_id, value)
            else:
                # Fallback: simple RMS-based single parameter
                self.model.SetParameterValue(
                    StandardParams.ParamMouthOpenY, self.wavHandler.GetRms() * self._lipSyncN
                )
        self.model.Update()
        self.model.Draw()

    def on_resize(self, width: int, height: int):
        self.model.Resize(width, height)
