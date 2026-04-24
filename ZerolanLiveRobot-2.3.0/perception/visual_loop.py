"""Periodic visual capture and analysis loop.

Captures and analyzes the screen at regular intervals, building
a rolling buffer of visual observations that can be injected
into LLM context or trigger autonomous behavior.
"""

import time
from collections import deque
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from perception.config import PerceptionConfig


class VisualObservation(BaseModel):
    """A single visual observation."""
    timestamp: float = Field(default_factory=time.time)
    ocr_text: str = ""
    image_caption: str = ""
    summary: str = ""
    screenshot_path: str = ""


class VisualLoop:
    """Periodic visual perception loop.

    Captures and analyzes the screen at regular intervals, building
    a rolling buffer of visual observations.

    Usage:
        loop = VisualLoop(screen, ocr_pipeline, imgcap_pipeline, config)
        loop.on_tick(elapsed)
        context = loop.get_context()
    """

    def __init__(self, screen, ocr_pipeline, imgcap_pipeline, config: PerceptionConfig):
        self._screen = screen
        self._ocr = ocr_pipeline
        self._imgcap = imgcap_pipeline
        self._config = config
        self._observations: deque = deque(maxlen=10)
        self._last_capture_time: float = 0
        self._last_image_hash = None

    def on_tick(self, elapsed: int):
        """Called from SecondEvent handler. Captures if interval elapsed."""
        if not self._config.visual.enable:
            return
        now = time.time()
        if now - self._last_capture_time < self._config.visual.capture_interval:
            return
        self._last_capture_time = now
        self._capture_and_analyze()

    def _capture_and_analyze(self) -> Optional[VisualObservation]:
        """Capture screen, run OCR/ImgCap, build observation."""
        try:
            # Capture screen
            window_title = self._config.visual.window_title or None
            img, img_save_path = self._screen.safe_capture(k=self._config.visual.capture_scale)
            if img is None:
                return None

            ocr_text = ""
            image_caption = ""

            # OCR analysis
            if self._config.analysis.enable_ocr and self._ocr is not None:
                try:
                    from zerolan.data.pipeline.ocr import OCRQuery
                    from pipeline.ocr.ocr_sync import avg_confidence, stringify
                    ocr_pred = self._ocr.predict(OCRQuery(img_path=str(img_save_path)))
                    if avg_confidence(ocr_pred) > self._config.analysis.ocr_confidence_threshold:
                        ocr_text = stringify(ocr_pred.region_results)
                except Exception as e:
                    logger.debug(f"Perception OCR failed: {e}")

            # Image captioning
            if self._config.analysis.enable_imgcap and self._imgcap is not None:
                try:
                    from zerolan.data.pipeline.img_cap import ImgCapQuery
                    imgcap_pred = self._imgcap.predict(
                        ImgCapQuery(prompt="Describe what you see", img_path=str(img_save_path))
                    )
                    image_caption = imgcap_pred.caption
                except Exception as e:
                    logger.debug(f"Perception ImgCap failed: {e}")

            # Build summary
            parts = []
            if ocr_text:
                parts.append(f"文字: {ocr_text[:100]}")
            if image_caption:
                parts.append(f"画面: {image_caption[:100]}")
            summary = "; ".join(parts) if parts else ""

            obs = VisualObservation(
                timestamp=time.time(),
                ocr_text=ocr_text,
                image_caption=image_caption,
                summary=summary,
                screenshot_path=str(img_save_path),
            )
            self._observations.append(obs)
            return obs

        except Exception as e:
            logger.warning(f"Visual capture failed: {e}")
            return None

    def get_context(self) -> str:
        """Build visual context string for LLM injection.

        Returns formatted string from recent observations:
            [视觉观察]
            - 10秒前: 屏幕上显示着...
        """
        if not self._observations:
            return ""

        parts = ["[视觉观察]"]
        now = time.time()
        for obs in reversed(self._observations):
            age = int(now - obs.timestamp)
            if obs.summary:
                parts.append(f"- {age}秒前: {obs.summary[:self._config.analysis.max_context_length]}")

        if len(parts) <= 1:
            return ""

        return "\n".join(parts)

    def get_latest_observation(self) -> Optional[VisualObservation]:
        """Return the most recent observation, or None."""
        return self._observations[-1] if self._observations else None

    def detect_visual_change(self, new_image_path: str) -> bool:
        """Detect if the visual scene has changed significantly.

        Uses perceptual hashing (pHash) to compare with previous capture.
        """
        try:
            import imagehash
            from PIL import Image
        except ImportError:
            logger.debug("imagehash not installed, skipping change detection")
            return False

        try:
            new_hash = imagehash.phash(Image.open(new_image_path))
            if self._last_image_hash is None:
                self._last_image_hash = new_hash
                return True

            distance = new_hash - self._last_image_hash
            self._last_image_hash = new_hash
            # pHash distance: 0 = identical, higher = more different
            # Normalize: typical max distance ~32 for 8-bit hash
            normalized = distance / 32.0
            return normalized > self._config.events.change_threshold

        except Exception as e:
            logger.debug(f"Change detection failed: {e}")
            return False
