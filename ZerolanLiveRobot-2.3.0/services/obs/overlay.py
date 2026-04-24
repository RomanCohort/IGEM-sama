"""OBS Overlay Control for IGEM-sama.

Extends the basic ObsStudioWsClient with:
  - Scene switching (e.g. "idle" → "quiz" → "game")
  - Source visibility toggling (show/hide overlays)
  - Overlay display for quiz results, vote counts, countdown timers
  - Text color and style control for emphasis

All operations use the OBS WebSocket protocol v5.
"""

import json
import time
import uuid
from typing import Dict, List, Optional

from loguru import logger


class OBSOverlayController:
    """High-level OBS control for IGEM-sama livestream overlays.

    Wraps an existing ObsStudioWsClient to add scene and overlay control.
    """

    def __init__(self, obs_client):
        """
        Args:
            obs_client: An ObsStudioWsClient instance with an active connection.
        """
        self._client = obs_client

    def _send_request(self, request_type: str, request_data: dict = None) -> Optional[dict]:
        """Send a request to OBS WebSocket and return the response."""
        if not self._client.is_connected:
            logger.warning("OBS not connected, skipping overlay request.")
            return None

        request = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": str(uuid.uuid4()),
                "requestData": request_data or {},
            }
        }
        try:
            self._client._client.send(json.dumps(request))
            return None  # Fire-and-forget for simplicity
        except Exception as e:
            logger.warning(f"OBS request failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Scene Control
    # ------------------------------------------------------------------

    def switch_scene(self, scene_name: str):
        """Switch to a different OBS scene.

        Pre-create scenes in OBS: "idle", "quiz", "talk", "game", etc.
        """
        self._send_request("SetCurrentProgramScene", {
            "sceneName": scene_name,
        })
        logger.info(f"OBS: Switched to scene '{scene_name}'")

    def get_current_scene(self) -> Optional[str]:
        """Get the name of the current scene."""
        # Note: This is a request-response call, but we fire-and-forget
        # for simplicity. In production, use async with callback.
        return None

    # ------------------------------------------------------------------
    # Source Visibility
    # ------------------------------------------------------------------

    def show_source(self, source_name: str, scene_name: str = None):
        """Make a source visible in the specified scene."""
        data = {"sourceName": source_name, "sourceVisible": True}
        if scene_name:
            data["sceneName"] = scene_name
        self._send_request("SetSceneItemEnabled", data)

    def hide_source(self, source_name: str, scene_name: str = None):
        """Hide a source in the specified scene."""
        data = {"sourceName": source_name, "sourceVisible": False}
        if scene_name:
            data["sceneName"] = scene_name
        self._send_request("SetSceneItemEnabled", data)

    # ------------------------------------------------------------------
    # Text Overlay
    # ------------------------------------------------------------------

    def set_overlay_text(self, text: str, source_name: str = "OverlayText"):
        """Update a text source with overlay content (quiz, vote, etc.)."""
        self._send_request("SetInputSettings", {
            "inputName": source_name,
            "inputSettings": {"text": text},
        })

    def clear_overlay(self, source_name: str = "OverlayText"):
        """Clear the overlay text."""
        self.set_overlay_text("", source_name)

    # ------------------------------------------------------------------
    # IGEM-sama Specific Overlays
    # ------------------------------------------------------------------

    def show_quiz(self, question: str, options: List[str], answer_hidden: bool = True):
        """Display a quiz overlay.

        Format:
            ❓ 题目：XXX
            A. option1
            B. option2
            C. option3
        """
        options_str = "\n".join([f"{chr(65 + i)}. {opt}" for i, opt in enumerate(options)])
        overlay = f"❓ {question}\n{options_str}"
        if not answer_hidden:
            overlay += "\n\n（弹幕回复你的答案！）"
        self.set_overlay_text(overlay, "QuizOverlay")
        self.show_source("QuizOverlay")

    def show_quiz_answer(self, answer: str):
        """Reveal the quiz answer."""
        overlay = f"✅ 正确答案：{answer}"
        self.set_overlay_text(overlay, "QuizOverlay")

    def show_vote(self, question: str, options: List[str], counts: Optional[Dict[str, int]] = None):
        """Display a vote overlay with optional counts."""
        lines = [f"📊 {question}"]
        for i, opt in enumerate(options):
            label = chr(65 + i)
            if counts and opt in counts:
                bar = "█" * min(counts[opt], 20)
                lines.append(f"{label}. {opt} {bar} ({counts[opt]}票)")
            else:
                lines.append(f"{label}. {opt}")
        self.set_overlay_text("\n".join(lines), "VoteOverlay")
        self.show_source("VoteOverlay")

    def show_countdown(self, seconds: int, event_name: str = ""):
        """Display a countdown overlay."""
        mins, secs = divmod(seconds, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        overlay = f"⏱ {time_str}"
        if event_name:
            overlay += f"\n{event_name}"
        self.set_overlay_text(overlay, "CountdownOverlay")
        self.show_source("CountdownOverlay")

    def show_lottery(self, keyword: str, prize: str):
        """Display a lottery overlay."""
        overlay = f"🎁 抽奖进行中！\n发送「{keyword}」参与\n奖品：{prize}"
        self.set_overlay_text(overlay, "LotteryOverlay")
        self.show_source("LotteryOverlay")

    def show_viewer_highlight(self, username: str, message: str):
        """Display a highlighted viewer message (e.g. Super Chat equivalent)."""
        overlay = f"⭐ {username}：{message}"
        self.set_overlay_text(overlay, "HighlightOverlay")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def hide_all_overlays(self):
        """Hide all IGEM-sama overlay sources."""
        for source in ["QuizOverlay", "VoteOverlay", "CountdownOverlay",
                        "LotteryOverlay", "HighlightOverlay"]:
            self.hide_source(source)
