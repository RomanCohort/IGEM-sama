"""IGEM-sama Demo Mode — simulated live stream without real services.

Launches a web-based mock Bilibili live stream room where you can
interact with IGEM-sama using simulated danmaku. The Live2D character
is embedded directly in the browser via MJPEG streaming.
No real LLM API, Bilibili credentials, or Milvus required.

Usage:
    python demo.py                  # Default (port 7070, with Live2D)
    python demo.py --port 8080      # Custom port
    python demo.py --no-live2d      # Skip Live2D window
    python demo.py --auto-viewers   # Start with simulated viewers
    python demo.py --hidden         # Live2D window hidden (only in browser)
"""

import argparse
import sys
import threading
import time
import webbrowser

from loguru import logger

from demo.core import DemoCore
from demo.server import create_app


def main():
    parser = argparse.ArgumentParser(description="IGEM-sama Demo Mode")
    parser.add_argument("--port", type=int, default=7070, help="Web server port (default: 7070)")
    parser.add_argument("--no-live2d", action="store_true", help="Don't launch Live2D window")
    parser.add_argument("--auto-viewers", action="store_true", help="Start with simulated viewers")
    parser.add_argument("--show-window", action="store_true", help="Show Live2D desktop window (hidden by default)")
    parser.add_argument("--no-tts", action="store_true", help="Disable TTS voice output")
    parser.add_argument("--api-key", type=str, default="", help="DeepSeek API key (enables real LLM)")
    args = parser.parse_args()

    logger.info("IGEM-sama Demo Mode starting...")

    # Initialize Live2D viewer with frame capture (optional)
    live2d_viewer = None
    if not args.no_live2d:
        try:
            from demo.video_stream import DemoLive2DViewer

            show_window = args.show_window
            live2d_viewer = DemoLive2DViewer(
                model_path="./resources/static/models/live2d/hiyori_pro_mic.model3.json",
                win_size=600,
                show_window=show_window,
            )

            # Start Live2D in a separate thread (blocks on app.exec())
            live2d_thread = threading.Thread(target=live2d_viewer.start, daemon=True, name="Live2DThread")
            live2d_thread.start()
            logger.info("Live2D viewer starting in background thread...")

            # Wait for the Live2D window to initialize and start capturing frames
            for i in range(10):
                time.sleep(1)
                if live2d_viewer.widget and live2d_viewer.widget.model is not None:
                    logger.info("Live2D model initialized successfully")
                    break
            else:
                logger.warning("Live2D model did not initialize in time")

        except Exception as e:
            logger.warning(f"Live2D viewer failed to start: {e}")
            logger.info("Continuing without Live2D window (use --no-live2d to suppress)")

    # Initialize DemoCore
    core = DemoCore(live2d_viewer=live2d_viewer, api_key=args.api_key, enable_tts=not args.no_tts)
    if args.api_key:
        logger.info("Using DeepSeek LLM (real AI responses)")
    else:
        logger.info("Using MockLLM (keyword-matched preset responses)")

    # Start tick loop (emotion decay, expression sync, autonomous)
    core.start_tick()

    # Start auto-viewers if requested
    if args.auto_viewers:
        core.start_auto_viewers()
        logger.info("Auto-viewer simulation enabled")

    # Create Flask app (pass live2d_viewer for MJPEG streaming)
    app = create_app(core, live2d_viewer=live2d_viewer)

    # Open browser after a short delay
    url = f"http://localhost:{args.port}"
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    logger.info(f"Demo server: {url}")
    logger.info("Press Ctrl+C to stop")

    # Run Flask
    app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
