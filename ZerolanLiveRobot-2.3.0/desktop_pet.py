"""IGEM-sama Desktop Pet Mode.

Launches only the Live2D model as a transparent, always-on-top
desktop pet — no Bilibili, no LLM, no TTS. Just the character
living on your desktop with idle animations.

Usage:
    python desktop_pet.py               # Default model
    python desktop_pet.py --model PATH  # Custom model3.json
    python desktop_pet.py --size 600    # Window size
"""

import sys
import random
import argparse
import traceback

import live2d.v3 as live2d
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtWidgets import QApplication, QOpenGLWidget, QMenu, QAction
from loguru import logger

from emotion.expression_map import EXPRESSION_MAP, MOTION_MAP, MOTION_PRIORITY_NORMAL


class PetCanvas(QOpenGLWidget):
    """Live2D canvas — renders directly via QOpenGLWidget (no framebuffer wrapper)."""

    def __init__(self, model_path: str, win_size: int = 600):
        super().__init__()
        self.setFixedSize(win_size, win_size)
        self._model_path = model_path
        self.model = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._initialized = False

    def initializeGL(self):
        try:
            live2d.init()
            live2d.glInit()
            self.model = live2d.LAppModel()
            self.model.LoadModelJson(self._model_path)
            # Auto blink/breath via timer-based Update calls
            self.model.StartMotion("Idle", 0, MOTION_PRIORITY_NORMAL)
            self._initialized = True
            logger.info("Live2D model loaded successfully")
        except Exception as e:
            logger.error(f"Live2D init failed: {e}")
            traceback.print_exc()

    def paintGL(self):
        if not self._initialized or self.model is None:
            return
        try:
            live2d.clearBuffer()
            self.model.Update()
            self.model.Draw()
        except Exception as e:
            logger.debug(f"paintGL error: {e}")

    def resizeGL(self, w, h):
        if self.model:
            self.model.Resize(w, h)

    def set_auto_blink(self, enable: bool):
        if self.model:
            try:
                # Try v6 Model API first, then LAppModel
                if hasattr(self.model, 'SetAutoBlink'):
                    self.model.SetAutoBlink(enable)
                elif hasattr(self.model, 'SetAutoBlinkEnable'):
                    self.model.SetAutoBlinkEnable(enable)
            except Exception:
                pass

    def set_auto_breath(self, enable: bool):
        if self.model:
            try:
                if hasattr(self.model, 'SetAutoBreath'):
                    self.model.SetAutoBreath(enable)
                elif hasattr(self.model, 'SetAutoBreathEnable'):
                    self.model.SetAutoBreathEnable(enable)
            except Exception:
                pass


class DesktopPetWindow(QOpenGLWidget):
    """Transparent, frameless, always-on-top desktop pet window."""

    def __init__(self, model_path: str, win_size: int = 600):
        super().__init__()
        self._model_path = model_path
        self._win_size = win_size
        self._drag_pos = QPoint()
        self._current_emotion = "neutral"
        self._tick_count = 0
        self.model = None

        # Window flags: frameless, always on top, no taskbar entry
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(win_size, win_size)
        self.setWindowTitle("IGEM-sama")

    def initializeGL(self):
        try:
            live2d.init()
            live2d.glInit()
            self.model = live2d.LAppModel()
            self.model.LoadModelJson(self._model_path)
            self.model.StartMotion("Idle", 0, MOTION_PRIORITY_NORMAL)
            logger.info("Desktop pet: Live2D model loaded")
        except Exception as e:
            logger.error(f"Live2D init failed: {e}")
            traceback.print_exc()
            return

        # Render timer — 60fps
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self.update)
        self._render_timer.start(16)

        # Tick timer — every second
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(1000)

        # Random emotion timer — first after 15-30s
        self._emotion_timer = QTimer(self)
        self._emotion_timer.timeout.connect(self._on_emotion_tick)
        self._emotion_timer.start(random.randint(15000, 30000))

    def paintGL(self):
        if self.model is None:
            return
        try:
            live2d.clearBuffer()
            self.model.Update()
            self.model.Draw()
        except Exception:
            pass

    def resizeGL(self, w, h):
        if self.model:
            self.model.Resize(w, h)

    def _on_tick(self):
        self._tick_count += 1
        if self._tick_count % random.randint(30, 60) == 0:
            self._trigger_random_motion()

    def _on_emotion_tick(self):
        emotions = list(EXPRESSION_MAP.keys())
        weights = [3 if e in ("neutral", "calm", "happy") else 1 for e in emotions]
        new_emotion = random.choices(emotions, weights=weights, k=1)[0]
        self._apply_emotion(new_emotion)
        self._trigger_motion(new_emotion)
        self._emotion_timer.setInterval(random.randint(10000, 30000))

    def _apply_emotion(self, emotion_label: str, intensity: float = 0.5):
        if self.model is None:
            return
        preset = EXPRESSION_MAP.get(emotion_label)
        if not preset:
            return
        self._current_emotion = emotion_label
        try:
            for param_id, (value, weight) in preset.params.items():
                blended = value * weight * intensity
                self.model.SetParameterValue(param_id, blended)
        except Exception:
            pass

    def _trigger_motion(self, emotion_label: str):
        if self.model is None:
            return
        motions = MOTION_MAP.get(emotion_label, [])
        if not motions:
            return
        motion = random.choice(motions)
        try:
            self.model.StartMotion(motion["group"], motion["no"], MOTION_PRIORITY_NORMAL)
        except Exception:
            pass

    def _trigger_random_motion(self):
        if self.model is None:
            return
        try:
            no = random.randint(0, 9)
            self.model.StartMotion("TapBody", no, MOTION_PRIORITY_NORMAL)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._apply_emotion("happy", 0.7)
            self._trigger_motion("happy")
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            QTimer.singleShot(3000, lambda: self._apply_emotion("neutral", 0.3))

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        actions = [
            ("开心", "happy"),
            ("生气", "angry"),
            ("难过", "sad"),
            ("害羞", "shy"),
            ("好奇", "curious"),
            ("得意", "proud"),
        ]
        for label, emotion in actions:
            action = QAction(label, self)
            action.triggered.connect(lambda _, e=emotion: self._react(e))
            menu.addAction(action)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        menu.exec_(pos)

    def _react(self, emotion: str):
        self._apply_emotion(emotion, 0.8)
        self._trigger_motion(emotion)
        QTimer.singleShot(5000, lambda: self._apply_emotion("neutral", 0.2))

    def closeEvent(self, event):
        live2d.dispose()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="IGEM-sama Desktop Pet")
    parser.add_argument("--model", type=str,
                        default="./resources/static/models/live2d/hiyori_pro_mic.model3.json",
                        help="Path to the Live2D model3.json file")
    parser.add_argument("--size", type=int, default=600,
                        help="Window size in pixels (default: 600)")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    pet = DesktopPetWindow(args.model, args.size)
    screen = app.primaryScreen().geometry()
    pet.move(screen.width() - args.size - 50, screen.height() - args.size - 80)
    pet.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
