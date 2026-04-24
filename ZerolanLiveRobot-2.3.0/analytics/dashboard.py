"""Lightweight Web Dashboard for IGEM-sama Stream Analytics.

Serves a single-page HTML dashboard and a JSON API endpoint.
Run alongside the bot for real-time monitoring.

API Endpoints:
  GET /api/analytics  - Current analytics snapshot (JSON)
  GET /api/history    - Last N snapshots (JSON)
  GET /               - HTML dashboard
"""

import json
from pathlib import Path

from loguru import logger

try:
    from flask import Flask, jsonify, Response
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IGEM-sama 直播数据看板</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
h1 { color: #e94560; margin-bottom: 20px; font-size: 24px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: #16213e; border-radius: 12px; padding: 20px; border: 1px solid #0f3460; }
.card h3 { color: #e94560; font-size: 14px; text-transform: uppercase; margin-bottom: 8px; }
.card .value { font-size: 32px; font-weight: bold; color: #fff; }
.card .unit { font-size: 14px; color: #888; margin-left: 4px; }
.section { margin-bottom: 24px; }
.section h2 { color: #0f3460; background: #e94560; display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: 16px; margin-bottom: 12px; }
#keywords { display: flex; flex-wrap: wrap; gap: 8px; }
.kw { background: #0f3460; padding: 4px 12px; border-radius: 16px; font-size: 13px; }
.kw .count { color: #e94560; margin-left: 4px; }
#emotion-bar { display: flex; height: 32px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
.emotion-segment { transition: width 0.5s; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; min-width: 0; }
.status { text-align: center; padding: 12px; color: #888; font-size: 13px; }
</style>
</head>
<body>
<h1>IGEM-sama 直播数据看板</h1>
<div class="grid">
  <div class="card"><h3>弹幕总数</h3><div class="value" id="danmaku-count">0</div></div>
  <div class="card"><h3>弹幕频率</h3><div class="value" id="dpm">0</div><span class="unit">条/分钟</span></div>
  <div class="card"><h3>独立观众</h3><div class="value" id="viewers">0</div></div>
  <div class="card"><h3>当前情绪</h3><div class="value" id="emotion">neutral</div></div>
  <div class="card"><h3>互动次数</h3><div class="value" id="interactions">0</div></div>
  <div class="card"><h3>主动发言</h3><div class="value" id="autonomous">0</div></div>
</div>
<div class="section">
  <h2>情绪分布</h2>
  <div id="emotion-bar"></div>
</div>
<div class="section">
  <h2>热门话题</h2>
  <div id="keywords"></div>
</div>
<div class="status" id="status">连接中...</div>
<script>
const EMOTION_COLORS = {
  happy: '#FFD700', excited: '#FF6347', calm: '#87CEEB',
  curious: '#9370DB', sad: '#4682B4', angry: '#DC143C',
  shy: '#FF69B4', proud: '#32CD32', neutral: '#808080'
};
async function refresh() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    document.getElementById('danmaku-count').textContent = data.danmaku_count;
    document.getElementById('dpm').textContent = data.danmaku_per_minute;
    document.getElementById('viewers').textContent = data.unique_viewers;
    document.getElementById('emotion').textContent = data.dominant_emotion;
    document.getElementById('interactions').textContent = data.interaction_count;
    document.getElementById('autonomous').textContent = data.autonomous_count;
    // Emotion bar
    const bar = document.getElementById('emotion-bar');
    bar.innerHTML = '';
    for (const [emo, pct] of Object.entries(data.emotion_distribution)) {
      const seg = document.createElement('div');
      seg.className = 'emotion-segment';
      seg.style.width = (pct * 100) + '%';
      seg.style.background = EMOTION_COLORS[emo] || '#808080';
      if (pct > 0.1) seg.textContent = emo;
      bar.appendChild(seg);
    }
    // Keywords
    const kwDiv = document.getElementById('keywords');
    kwDiv.innerHTML = '';
    for (const [word, count] of (data.top_keywords || [])) {
      const span = document.createElement('span');
      span.className = 'kw';
      span.innerHTML = word + '<span class="count">' + count + '</span>';
      kwDiv.appendChild(span);
    }
    document.getElementById('status').textContent = '最后更新: ' + new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById('status').textContent = '连接失败: ' + e.message;
  }
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


class AnalyticsDashboard:
    """Flask-based web dashboard for stream analytics."""

    def __init__(self, analytics, host: str = "0.0.0.0", port: int = 8080):
        """
        Args:
            analytics: A StreamAnalytics instance.
            host: Bind address.
            port: Bind port.
        """
        self._analytics = analytics
        self._host = host
        self._port = port
        self._app = None

    def start(self):
        """Start the dashboard server (blocking)."""
        if not FLASK_AVAILABLE:
            logger.warning("Flask not installed, analytics dashboard unavailable. pip install flask")
            return

        self._app = Flask(__name__)
        self._register_routes()
        logger.info(f"Analytics dashboard starting on http://{self._host}:{self._port}")
        self._app.run(host=self._host, port=self._port, debug=False, use_reloader=False)

    def _register_routes(self):
        @self._app.route("/")
        def index():
            return _DASHBOARD_HTML

        @self._app.route("/api/analytics")
        def api_analytics():
            snap = self._analytics.snapshot()
            return jsonify(snap.model_dump())

        @self._app.route("/api/history")
        def api_history():
            history = self._analytics.get_history(60)
            return jsonify([s.model_dump() for s in history])
