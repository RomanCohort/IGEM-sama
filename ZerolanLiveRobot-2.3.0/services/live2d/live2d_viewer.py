import os.path
import sys
from pathlib import Path
from queue import Queue

import live2d.v3 as live2d
from PyQt5.QtWidgets import QApplication
from loguru import logger
from typeguard import typechecked

from common.concurrent.abs_runnable import ThreadRunnable
from common.concurrent.killable_thread import KillableThread
from services.live2d.config import Live2DViewerConfig
from services.live2d.live2d_canvas import Live2DCanvas


class Live2DViewer(ThreadRunnable):
    def name(self):
        return "Live2DViewer"

    def __init__(self, config: Live2DViewerConfig):
        super().__init__()
        self._model_path: str = config.model3_json_file
        assert os.path.exists(self._model_path), f'The specified Live2D model file does not exist: {self._model_path}'
        self._canvas: Live2DCanvas | None = None
        self._audios: Queue[Path] = Queue()
        self._sync_lip_loop_thread: KillableThread = KillableThread(target=self._sync_lip_loop, daemon=True)
        self._sync_lip_loop_flag: bool = True
        self._auto_lip_sync: bool = config.auto_lip_sync
        self._auto_blink: bool = config.auto_blink
        self._auto_breath: bool = config.auto_breath
        self._win_h: int = int(config.win_height)
        self._win_w: int = int(config.win_width)
        self._lip_sync_config = config.lip_sync

    def start(self):
        super().start()
        # Note: live2d.init() is called inside Live2DCanvas.on_init()
        # (which runs inside initializeGL) for v6 compatibility
        app = QApplication(sys.argv)
        self._canvas = Live2DCanvas(
            path=self._model_path,
            lip_sync_n=3,
            win_size=(self._win_w, self._win_h),
            lip_sync_config=self._lip_sync_config,
        )
        self._sync_lip_loop_thread.start()
        self._canvas.show()
        self.set_auto_blink(self._auto_blink)
        self.set_auto_breath(self._auto_breath)
        app.exec()
        live2d.dispose()

    def _sync_lip_loop(self):
        while self._sync_lip_loop_flag:
            try:
                audio_path = self._audios.get(block=True)
                self._canvas.wavHandler.Start(str(audio_path))
            except Exception as e:
                logger.exception(e)

    def stop(self):
        super().stop()
        self._sync_lip_loop_flag = False
        self._canvas.close()
        self._sync_lip_loop_thread.kill()

    @typechecked
    def sync_lip(self, audio_path: Path):
        if not self._auto_lip_sync:
            return
        assert audio_path.exists()
        self._audios.put(audio_path)

    @typechecked
    def set_auto_blink(self, enable: bool):
        if self._canvas and self._canvas.model:
            model = self._canvas.model
            # LAppModel may not have SetAutoBlink/SetAutoBlinkEnable;
            # check availability before calling
            if hasattr(model, 'SetAutoBlink'):
                model.SetAutoBlink(enable)
            elif hasattr(model, 'SetAutoBlinkEnable'):
                model.SetAutoBlinkEnable(enable)
            else:
                logger.debug("Auto blink not supported by current model wrapper")
                return
            logger.info(f"Set auto blink to: {enable}")

    @typechecked
    def set_auto_breath(self, enable: bool):
        if self._canvas and self._canvas.model:
            model = self._canvas.model
            if hasattr(model, 'SetAutoBreath'):
                model.SetAutoBreath(enable)
            elif hasattr(model, 'SetAutoBreathEnable'):
                model.SetAutoBreathEnable(enable)
            else:
                logger.debug("Auto breath not supported by current model wrapper")
                return
            logger.info(f"Set auto breath to: {enable}")
