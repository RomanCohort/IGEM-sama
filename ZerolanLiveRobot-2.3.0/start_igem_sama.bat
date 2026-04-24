@echo off
REM ============================================================
REM IGEM-sama 一键启动脚本 (Windows)
REM Team: IGEM-FBH
REM ============================================================

cd /d "%~dp0"

echo ============================================
echo   IGEM-sama 启动器 - IGEM-FBH Team
echo ============================================

REM 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM 2. Check config
if not exist "config.yaml" (
    if exist "config.igem-sama.yaml" (
        echo [INFO] Copying config.igem-sama.yaml -^> config.yaml
        copy config.igem-sama.yaml config.yaml >nul
        echo [WARN] Please edit config.yaml and fill in your credentials!
        echo        Required: Bilibili room_id, SESSDATA, LLM API key
        echo        Then re-run this script.
        pause
        exit /b 0
    ) else (
        echo [ERROR] No config.yaml found. Copy config.igem-sama.yaml to config.yaml first.
        pause
        exit /b 1
    )
)

REM 3. Check dependencies
echo [INFO] Checking dependencies...
pip install -r requirements.txt -q 2>nul

REM 4. Ingest knowledge base
if exist "knowledge_base\docs" (
    echo [INFO] Ingesting knowledge base documents...
    python -m knowledge_base.ingest --dir knowledge_base/docs 2>nul
    if errorlevel 1 (
        echo [WARN] Knowledge base ingestion failed - Milvus may not be running
    )
)

REM 5. Create data directories
if not exist "data" mkdir data

REM 6. Start the bot
echo [INFO] Starting IGEM-sama...
python main.py

echo [INFO] IGEM-sama stopped.
pause
