"""Live2D viewer with frame capture for demo mode.

Creates a transparent Live2D window (like desktop_pet.py) and captures
frames at ~20fps as JPEG, storing them in a shared buffer for the
Flask MJPEG streaming endpoint.
"""

import io
import threading
import time
import traceback
from typing import Optional

import live2d.v3 as live2d
from live2d.v3 import StandardParams
from PyQt5.QtCore import Qt, QTimer, QByteArray, QBuffer
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
from loguru import logger

from emotion.expression_map import MOTION_PRIORITY_NORMAL
from services.live2d.wave_handler import Live2DWaveHandler


class DemoLive2DWidget(QOpenGLWidget):
    """Live2D canvas that captures frames for MJPEG streaming."""

    def __init__(self, model_path: str, win_size: int = 600):
        super().__init__()
        self.setFixedSize(win_size, win_size)
        self._model_path = model_path
        self.model = None
        self._initialized = False
        # Frame capture buffer
        self._frame_lock = threading.Lock()
        self._latest_frame: bytes = b""
        self._frame_count = 0
        # Lip sync
        self.wavHandler: Optional[Live2DWaveHandler] = None
        # Window flags: frameless, always on top, no taskbar entry
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("IGEM-sama")

    def initializeGL(self):
        try:
            live2d.init()
            live2d.glInit()
            self.model = live2d.LAppModel()
            self.model.LoadModelJson(self._model_path)
            self.model.StartMotion("Idle", 0, MOTION_PRIORITY_NORMAL)
            self._initialized = True
            # Initialize lip sync handler
            self.wavHandler = Live2DWaveHandler()
            logger.info("Demo Live2D model loaded")

            # Start frame capture timer (12fps — smooth enough, light on CPU)
            self._capture_timer = QTimer(self)
            self._capture_timer.timeout.connect(self._capture_frame)
            self._capture_timer.start(83)  # 83ms ≈ 12fps

        except Exception as e:
            logger.error(f"Live2D init failed: {e}")
            traceback.print_exc()

    def paintGL(self):
        if not self._initialized or self.model is None:
            return
        try:
            live2d.clearBuffer()
            # Lip sync: update mouth from wavHandler
            if self.wavHandler and self.wavHandler.Update():
                rms = self.wavHandler.GetRms()
                try:
                    self.model.SetParameterValue(StandardParams.ParamMouthOpenY, min(rms * 3, 1.0))
                except Exception:
                    pass
            self.model.Update()
            self.model.Draw()
        except Exception:
            pass

    def resizeGL(self, w, h):
        if self.model:
            self.model.Resize(w, h)

    def _capture_frame(self):
        """Capture the current frame as JPEG bytes."""
        try:
            img = self.grabFramebuffer()
            buf = QBuffer()
            buf.open(QBuffer.ReadWrite)
            img.save(buf, "JPEG", 85)  # 85% quality — good balance
            data = bytes(buf.data())
            buf.close()
            with self._frame_lock:
                self._latest_frame = data
                self._frame_count += 1
        except Exception:
            pass

    def get_frame(self) -> bytes:
        """Get the latest captured frame (thread-safe)."""
        with self._frame_lock:
            return self._latest_frame

    def sync_lip(self, audio_path: str):
        """Start lip sync from an audio file."""
        if self.wavHandler:
            try:
                self.wavHandler.Start(audio_path)
            except Exception as e:
                logger.debug(f"Lip sync start failed: {e}")


class DemoLive2DViewer:
    """Manages the Live2D widget in its own QApplication thread."""

    def __init__(self, model_path: str, win_size: int = 600, show_window: bool = True):
        self._model_path = model_path
        self._win_size = win_size
        self._show_window = show_window
        self.widget: Optional[DemoLive2DWidget] = None
        self._canvas: Optional[DemoLive2DWidget] = None
        self._app: Optional[QApplication] = None

    def start(self):
        """Start the Live2D viewer (blocks the calling thread)."""
        self._app = QApplication([])
        self.widget = DemoLive2DWidget(self._model_path, self._win_size)
        # Compatibility: Live2DExpressionDriver accesses viewer._canvas.model
        self._canvas = self.widget

        # Must show widget for GL context to initialize
        screen = self._app.primaryScreen().geometry()
        if self._show_window:
            self.widget.move(
                screen.width() - self._win_size - 50,
                screen.height() - self._win_size - 80
            )
        else:
            # Move off-screen but keep shown (GL requires visible widget)
            self.widget.move(screen.width() + 100, screen.height() + 100)
        self.widget.show()

        self._app.exec()
        live2d.dispose()

    def get_frame(self) -> bytes:
        """Get the latest captured frame."""
        if self.widget:
            return self.widget.get_frame()
        return b""

    def set_auto_blink(self, enable: bool):
        """No-op for demo mode (LAppModel doesn't support this)."""
        pass

    def set_auto_breath(self, enable: bool):
        """No-op for demo mode (LAppModel doesn't support this)."""
        pass

    def sync_lip(self, audio_path: str):
        """Start lip sync — delegates to the widget."""
        if self.widget:
            self.widget.sync_lip(audio_path)
