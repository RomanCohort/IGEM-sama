"""Game state perception via screen capture and visual analysis.

Uses the existing OCR + ImgCap pipelines for visual understanding,
same as the '看见' voice command but automated.
"""

import time
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from game_loop.config import GameLoopConfig


class GameState(BaseModel):
    """Current understanding of the game state."""
    screenshot_path: str = ""
    ocr_text: str = ""
    image_caption: str = ""
    game_context: str = ""
    timestamp: float = Field(default_factory=time.time)


class GamePerception:
    """Periodically captures and understands game state.

    Reuses existing screen capture + OCR/ImgCap pipeline chain.

    Usage:
        perception = GamePerception(screen, ocr_pipeline, imgcap_pipeline, config)
        state = perception.capture()
    """

    def __init__(self, screen, ocr_pipeline, imgcap_pipeline, config: GameLoopConfig):
        self._screen = screen
        self._ocr = ocr_pipeline
        self._imgcap = imgcap_pipeline
        self._config = config
        self._last_state: Optional[GameState] = None
        self._last_capture_time: float = 0

    def capture(self) -> Optional[GameState]:
        """Capture current game state via screenshot + analysis."""
        try:
            img, img_save_path = self._screen.safe_capture(k=0.99)
            if img is None:
                return None

            ocr_text = ""
            image_caption = ""

            # OCR analysis
            if self._ocr is not None:
                try:
                    from zerolan.data.pipeline.ocr import OCRQuery
                    from pipeline.ocr.ocr_sync import avg_confidence, stringify
                    ocr_pred = self._ocr.predict(OCRQuery(img_path=str(img_save_path)))
                    if avg_confidence(ocr_pred) > 0.5:
                        ocr_text = stringify(ocr_pred.region_results)
                except Exception as e:
                    logger.debug(f"Game OCR failed: {e}")

            # Image captioning
            if self._imgcap is not None:
                try:
                    from zerolan.data.pipeline.img_cap import ImgCapQuery
                    imgcap_pred = self._imgcap.predict(
                        ImgCapQuery(prompt="Describe the game screen", img_path=str(img_save_path))
                    )
                    image_caption = imgcap_pred.caption
                except Exception as e:
                    logger.debug(f"Game ImgCap failed: {e}")

            # Build combined context
            parts = []
            if ocr_text:
                parts.append(f"屏幕文字: {ocr_text[:150]}")
            if image_caption:
                parts.append(f"画面描述: {image_caption[:150]}")
            game_context = "; ".join(parts)

            state = GameState(
                screenshot_path=str(img_save_path),
                ocr_text=ocr_text,
                image_caption=image_caption,
                game_context=game_context,
            )
            self._last_state = state
            return state

        except Exception as e:
            logger.warning(f"Game capture failed: {e}")
            return None

    def should_capture(self, elapsed: float) -> bool:
        """Check if it is time for a new capture."""
        now = time.time()
        if now - self._last_capture_time < self._config.capture_interval:
            return False
        self._last_capture_time = now
        return True

    def get_last_state(self) -> Optional[GameState]:
        return self._last_state
