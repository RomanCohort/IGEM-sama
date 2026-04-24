#!/bin/bash
# ============================================================
# IGEM-sama 一键启动脚本
# Team: IGEM-FBH
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  IGEM-sama 启动器 - IGEM-FBH Team"
echo "============================================"

# 1. Check Python
if ! command -v python &> /dev/null; then
    echo "[ERROR] Python not found. Please install Python 3.10+"
    exit 1
fi

# 2. Check config
if [ ! -f "config.yaml" ]; then
    if [ -f "config.igem-sama.yaml" ]; then
        echo "[INFO] Copying config.igem-sama.yaml -> config.yaml"
        cp config.igem-sama.yaml config.yaml
        echo "[WARN] Please edit config.yaml and fill in your credentials!"
        echo "       Required: Bilibili room_id, SESSDATA, LLM API key"
        echo "       Then re-run this script."
        exit 0
    else
        echo "[ERROR] No config.yaml found. Copy config.igem-sama.yaml to config.yaml first."
        exit 1
    fi
fi

# 3. Check dependencies
echo "[INFO] Checking dependencies..."
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt

# 4. Ingest knowledge base (if docs exist and Milvus is running)
DOCS_DIR="knowledge_base/docs"
if [ -d "$DOCS_DIR" ] && [ "$(find $DOCS_DIR -name '*.md' -o -name '*.txt' -o -name '*.json' 2>/dev/null | head -1)" ]; then
    echo "[INFO] Ingesting knowledge base documents..."
    python -m knowledge_base.ingest --dir "$DOCS_DIR" 2>/dev/null || echo "[WARN] Knowledge base ingestion failed (Milvus may not be running)"
fi

# 5. Create data directories
mkdir -p data

# 6. Start analytics dashboard in background (optional)
START_DASHBOARD=${START_DASHBOARD:-false}
if [ "$START_DASHBOARD" = "true" ]; then
    echo "[INFO] Starting analytics dashboard on http://0.0.0.0:8080"
    python -c "from analytics.dashboard import AnalyticsDashboard; from analytics.collector import StreamAnalytics; d = AnalyticsDashboard(StreamAnalytics()); d.start()" &
    DASHBOARD_PID=$!
fi

# 7. Start the bot
echo "[INFO] Starting IGEM-sama..."
python main.py

# Cleanup
if [ -n "$DASHBOARD_PID" ]; then
    kill $DASHBOARD_PID 2>/dev/null
fi

echo "[INFO] IGEM-sama stopped."
