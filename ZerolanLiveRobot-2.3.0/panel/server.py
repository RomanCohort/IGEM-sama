"""IGEM-sama Operator Control Panel - Flask Backend.

REST API for real-time control of all IGEM-sama subsystems:
  - Toggle features (autonomous, emotion, RAG, TTS)
  - Trigger actions (quiz, greeting, manual message)
  - Manage knowledge base (ingest, search, list)
  - Control emotions and Live2D expressions
  - View memories and viewer profiles
  - Monitor stream status and logs

All state changes are proxied through a shared bot reference.
"""

import json
import time
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from flask import Flask, jsonify, request, Response
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


# Global bot reference - set by the bot at startup
_bot = None


def set_bot(bot):
    """Register the running bot instance for the control panel to control."""
    global _bot
    _bot = bot


def get_bot():
    return _bot


def create_app() -> Flask:
    """Create and configure the Flask app with all API routes."""
    app = Flask(__name__, static_folder=None)
    if FLASK_AVAILABLE:
        try:
            CORS(app)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Serve the control panel HTML
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        from panel.frontend import PANEL_HTML
        return PANEL_HTML

    # ------------------------------------------------------------------
    # Status & Monitoring
    # ------------------------------------------------------------------

    @app.route("/api/status")
    def api_status():
        bot = get_bot()
        if bot is None:
            return jsonify({"running": False})
        return jsonify({
            "running": True,
            "bot_name": bot.bot_name,
            "emotion": {
                "dominant": bot.emotion_tracker.state.dominant.value,
                "intensity": round(bot.emotion_tracker.state.dominant_intensity, 2),
                "all": bot.emotion_tracker.state.intensities,
            },
            "autonomous": {
                "enabled": bot._autonomous.enabled,
            },
            "kb": {
                "enabled": bot.kb_pipeline is not None,
            },
            "memory": {
                "total_memories": len(bot.long_term_memory.memories),
                "total_viewers": len(bot.long_term_memory.viewers),
            },
            "analytics": bot.stream_analytics.snapshot().model_dump(),
            "rate_limiter": {
                "rejected_count": bot._rate_limiter.rejected_count,
            },
            "services": {
                "bilibili": bot.bilibili is not None,
                "tts": bot.tts is not None,
                "asr": bot.asr is not None,
                "obs": bot.obs is not None,
                "live2d": bot.live2d_viewer is not None,
                "playground": bot.playground is not None,
            },
        })

    # ------------------------------------------------------------------
    # Feature Toggles
    # ------------------------------------------------------------------

    @app.route("/api/toggle/autonomous", methods=["POST"])
    def toggle_autonomous():
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        enabled = data.get("enabled", not bot._autonomous.enabled)
        bot._autonomous.enabled = enabled
        return jsonify({"autonomous": enabled})

    @app.route("/api/toggle/kb", methods=["POST"])
    def toggle_kb():
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        enabled = data.get("enabled", True)
        if not enabled:
            bot.kb_pipeline = None
        else:
            # Re-initialize if possible
            return jsonify({"kb": False, "note": "Restart required to re-enable KB"})
        return jsonify({"kb": enabled})

    @app.route("/api/toggle/sentiment", methods=["POST"])
    def toggle_sentiment():
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        bot.enable_sentiment_analysis = data.get("enabled", not bot.enable_sentiment_analysis)
        return jsonify({"sentiment_analysis": bot.enable_sentiment_analysis})

    # ------------------------------------------------------------------
    # Manual Actions
    # ------------------------------------------------------------------

    @app.route("/api/action/speak", methods=["POST"])
    def action_speak():
        """Manually send a message through the LLM pipeline."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "Missing 'text'"}), 400
        bot.emit_llm_prediction(text)
        return jsonify({"ok": True, "message": text})

    @app.route("/api/action/emotion", methods=["POST"])
    def action_set_emotion():
        """Manually set an emotion state."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        emotion = data.get("emotion", "neutral")
        intensity = data.get("intensity", 0.7)
        bot.emotion_tracker.update_from_label(emotion, intensity)
        bot._expression_driver.apply_emotion(emotion, intensity)
        return jsonify({"emotion": emotion, "intensity": intensity})

    @app.route("/api/action/trigger_autonomous", methods=["POST"])
    def action_trigger_autonomous():
        """Manually trigger an autonomous action."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        prompt = data.get("prompt", "你想跟观众打个招呼。")
        bot.emit_llm_prediction(f"[自主行为]{prompt}")
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Knowledge Base Management
    # ------------------------------------------------------------------

    @app.route("/api/kb/ingest", methods=["POST"])
    def kb_ingest():
        """Ingest documents into the knowledge base."""
        bot = get_bot()
        if bot is None or bot.kb_pipeline is None:
            return jsonify({"error": "KB not available"}), 503
        data = request.json or {}
        path = data.get("path", "knowledge_base/docs")
        category = data.get("category", "general")
        reset = data.get("reset", False)

        from knowledge_base.loader import ingest_directory, ingest_document
        p = Path(path)
        if p.is_dir():
            entries = ingest_directory(path, category=category)
        elif p.is_file():
            entries = ingest_document(path, category=category)
        else:
            return jsonify({"error": f"Path not found: {path}"}), 404

        if reset:
            count = bot.kb_pipeline.ingest_with_reset(entries)
        else:
            count = bot.kb_pipeline.ingest(entries)
        return jsonify({"ingested": count, "total_entries": len(entries)})

    @app.route("/api/kb/search", methods=["POST"])
    def kb_search():
        """Search the knowledge base."""
        bot = get_bot()
        if bot is None or bot.kb_pipeline is None:
            return jsonify({"error": "KB not available"}), 503
        data = request.json or {}
        query = data.get("query", "")
        top_k = data.get("top_k", 5)
        if not query:
            return jsonify({"error": "Missing 'query'"}), 400
        result = bot.kb_pipeline.retrieve(query, top_k=top_k)
        return jsonify({
            "items": [{"text": i.text, "category": i.category, "distance": round(i.distance, 4)} for i in result.items]
        })

    # ------------------------------------------------------------------
    # Memory Management
    # ------------------------------------------------------------------

    @app.route("/api/memory/list", methods=["GET"])
    def memory_list():
        """List all long-term memories."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        memories = [
            {"id": m.id, "content": m.content[:100], "category": m.category,
             "importance": m.importance, "age_hours": round((time.time() - m.created_at) / 3600, 1)}
            for m in bot.long_term_memory.memories.values()
        ]
        return jsonify({"memories": memories, "total": len(memories)})

    @app.route("/api/memory/add", methods=["POST"])
    def memory_add():
        """Manually add a long-term memory."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        content = data.get("content", "")
        if not content:
            return jsonify({"error": "Missing 'content'"}), 400
        entry = bot.long_term_memory.add_memory(
            content=content,
            category=data.get("category", "fact"),
            importance=data.get("importance", 0.7),
            tags=data.get("tags", []),
        )
        return jsonify({"id": entry.id, "content": entry.content})

    @app.route("/api/memory/delete/<memory_id>", methods=["DELETE"])
    def memory_delete(memory_id):
        """Delete a specific memory."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        ok = bot.long_term_memory.remove_memory(memory_id)
        return jsonify({"deleted": ok})

    # ------------------------------------------------------------------
    # Viewer Profiles
    # ------------------------------------------------------------------

    @app.route("/api/viewers", methods=["GET"])
    def viewer_list():
        """List all known viewer profiles."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        viewers = [
            {"uid": v.uid, "username": v.username, "platform": v.platform,
             "visits": v.visit_count, "notes": v.notes, "preferences": v.preferences}
            for v in bot.long_term_memory.viewers.values()
        ]
        return jsonify({"viewers": viewers, "total": len(viewers)})

    @app.route("/api/viewers/<uid>/note", methods=["POST"])
    def viewer_add_note(uid):
        """Add a note to a viewer profile."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        note = data.get("note", "")
        if note:
            bot.long_term_memory.add_viewer_note(uid, note)
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # OBS Control
    # ------------------------------------------------------------------

    @app.route("/api/obs/scene", methods=["POST"])
    def obs_scene():
        """Switch OBS scene."""
        bot = get_bot()
        if bot is None or bot.obs is None:
            return jsonify({"error": "OBS not connected"}), 503
        data = request.json or {}
        scene = data.get("scene", "")
        if not scene:
            return jsonify({"error": "Missing 'scene'"}), 400
        from services.obs.overlay import OBSOverlayController
        ctrl = OBSOverlayController(bot.obs)
        ctrl.switch_scene(scene)
        return jsonify({"scene": scene})

    @app.route("/api/obs/overlay", methods=["POST"])
    def obs_overlay():
        """Show text on OBS overlay."""
        bot = get_bot()
        if bot is None or bot.obs is None:
            return jsonify({"error": "OBS not connected"}), 503
        data = request.json or {}
        text = data.get("text", "")
        source = data.get("source", "OverlayText")
        action = data.get("action", "show")  # show, hide, clear
        from services.obs.overlay import OBSOverlayController
        ctrl = OBSOverlayController(bot.obs)
        if action == "show":
            ctrl.set_overlay_text(text, source)
        elif action == "hide":
            ctrl.hide_source(source)
        elif action == "clear":
            ctrl.clear_overlay(source)
        return jsonify({"ok": True, "action": action})

    # ------------------------------------------------------------------
    # Chat / Send message as bot
    # ------------------------------------------------------------------

    @app.route("/api/chat/send", methods=["POST"])
    def chat_send():
        """Send a direct chat message (bypasses LLM, goes straight to TTS)."""
        bot = get_bot()
        if bot is None:
            return jsonify({"error": "Bot not running"}), 503
        data = request.json or {}
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "Missing 'text'"}), 400
        # Emit directly as LLM output
        from zerolan.data.pipeline.llm import LLMPrediction, Conversation
        prediction = LLMPrediction(response=text, history=[])
        from event.event_data import PipelineOutputLLMEvent
        from event.event_emitter import emitter
        from event.registry import EventKeyRegistry
        emitter.emit(PipelineOutputLLMEvent(prediction=prediction))
        return jsonify({"ok": True, "sent": text})

    return app


def start_panel(host: str = "0.0.0.0", port: int = 9090):
    """Start the control panel server."""
    if not FLASK_AVAILABLE:
        logger.warning("Flask not installed. pip install flask flask-cors")
        return
    app = create_app()
    logger.info(f"IGEM-sama control panel: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)
