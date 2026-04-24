"""Demo Flask server — provides Web UI and API for the simulated live stream."""

import json
import queue
import time
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, request, render_template

from demo.core import DemoCore


def create_app(core: DemoCore, live2d_viewer=None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=None,
    )

    @app.route("/")
    def index():
        return render_template("demo.html")

    @app.route("/api/danmaku", methods=["POST"])
    def api_danmaku():
        """Receive a simulated danmaku message."""
        data = request.json or {}
        username = data.get("username", "DemoUser")
        content = data.get("content", "").strip()
        if not content:
            return jsonify({"error": "Empty message"}), 400
        result = core.handle_danmaku(username, content)
        if "error" in result:
            return jsonify(result), 429
        return jsonify(result)

    @app.route("/api/emotion", methods=["POST"])
    def api_emotion():
        """Manually set an emotion."""
        data = request.json or {}
        emotion = data.get("emotion", "neutral")
        intensity = data.get("intensity", 0.7)
        result = core.set_emotion(emotion, intensity)
        return jsonify(result)

    @app.route("/api/trigger", methods=["POST"])
    def api_trigger():
        """Trigger an autonomous action."""
        data = request.json or {}
        prompt = data.get("prompt", "")
        result = core.trigger_autonomous(prompt)
        return jsonify(result)

    @app.route("/api/auto_viewers", methods=["POST"])
    def api_auto_viewers():
        """Toggle auto-viewer simulation."""
        data = request.json or {}
        enabled = data.get("enabled", not core._auto_viewers_enabled)
        if enabled:
            core.start_auto_viewers()
        else:
            core.stop_auto_viewers()
        return jsonify({"auto_viewers": core._auto_viewers_enabled})

    @app.route("/api/autonomous_toggle", methods=["POST"])
    def api_autonomous_toggle():
        """Toggle autonomous behavior."""
        data = request.json or {}
        core.autonomous_enabled = data.get("enabled", not core.autonomous_enabled)
        return jsonify({"autonomous_enabled": core.autonomous_enabled})

    @app.route("/api/gift", methods=["POST"])
    def api_gift():
        """Send a simulated gift."""
        data = request.json or {}
        username = data.get("username", "DemoUser")
        gift = data.get("gift", "辣条")
        count = data.get("count", 1)
        result = core.send_gift(username, gift, count)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)

    @app.route("/api/superchat", methods=["POST"])
    def api_superchat():
        """Send a simulated SuperChat."""
        data = request.json or {}
        username = data.get("username", "DemoUser")
        content = data.get("content", "").strip()
        price = data.get("price", 30)
        if not content:
            return jsonify({"error": "Empty message"}), 400
        result = core.send_superchat(username, content, price)
        return jsonify(result)

    @app.route("/api/viewer_enter", methods=["POST"])
    def api_viewer_enter():
        """Simulate a viewer entering the room."""
        data = request.json or {}
        username = data.get("username", "DemoUser")
        result = core.viewer_enter(username)
        return jsonify(result)

    @app.route("/api/viewer_leave", methods=["POST"])
    def api_viewer_leave():
        """Simulate a viewer leaving the room."""
        data = request.json or {}
        username = data.get("username", "DemoUser")
        result = core.viewer_leave(username)
        return jsonify(result)

    @app.route("/api/status")
    def api_status():
        """Return current status."""
        status = core.get_status()
        status["live2d"] = live2d_viewer is not None
        return jsonify(status)

    @app.route("/api/video")
    def api_video():
        """MJPEG stream of the Live2D window."""

        if live2d_viewer is None:
            return Response("No Live2D viewer", status=404)

        def generate_mjpeg():
            while True:
                frame = live2d_viewer.get_frame()
                if frame:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                time.sleep(0.08)  # ~12fps, match capture rate

        return Response(
            generate_mjpeg(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/api/stream")
    def api_stream():
        """SSE endpoint — pushes real-time events to the browser."""

        def generate():
            while True:
                try:
                    event = core.event_queue.get(timeout=30)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    # Keep-alive ping
                    yield f": keepalive\n\n"

        return Response(generate(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    return app
