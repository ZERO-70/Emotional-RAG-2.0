@echo off
setlocal enabledelayedexpansion
title Emotional RAG - Startup

REM Force working directory to the folder where this .bat file lives.
REM Without this, double-clicking from Explorer may use a wrong directory
REM and all relative paths (tar.gz, .env, docker-compose) will fail.
cd /d "%~dp0"

echo.
echo  =====================================================
echo   Emotional RAG Backend  ^|  Startup
echo  =====================================================
echo.

REM ── Check Docker is running ─────────────────────────────────
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Docker Desktop is not running.
    echo          Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo  [OK] Docker Desktop is running.

REM ── Load images on first run ─────────────────────────────────
docker image inspect emotional-rag:latest >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [1/3] Loading Docker images from archive...
    echo        This will take 10-20 minutes on first run. Please wait.
    echo.
    IF NOT EXIST emotional-rag-images.tar.gz (
        echo  [ERROR] emotional-rag-images.tar.gz not found in this folder!
        echo          Make sure the archive is in the same directory as this script.
        echo.
        pause
        exit /b 1
    )
    docker load -i emotional-rag-images.tar.gz
)

REM ── 1b. Verify images actually exist ─────────────────────────
docker image inspect emotional-rag:latest >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Image emotional-rag:latest was not found.
    echo          The archive may be corrupted or Docker load failed.
    echo          Try re-transferring the zip.
    pause
    exit /b 1
)
echo  [1/3] Images loaded successfully.

REM ── Check .env file ──────────────────────────────────────────
echo.
IF NOT EXIST .env (
    echo  [2/3] First-time setup: creating .env from template...
    IF NOT EXIST .env.example (
        echo  [ERROR] .env.example not found! Cannot create .env.
        pause
        exit /b 1
    )
    copy .env.example .env >nul
    echo.
    echo  ┌──────────────────────────────────────────────────────┐
    echo  │  ACTION REQUIRED:                                    │
    echo  │                                                      │
    echo  │  1. Open the file ".env" in this folder              │
    echo  │     (right-click → Open with → Notepad)             │
    echo  │                                                      │
    echo  │  2. Set your API key for your LLM provider:          │
    echo  │     - OpenRouter:  OPENROUTER_API_KEY=sk-or-v1-...  │
    echo  │     - Gemini:      GEMINI_API_KEY=AIza...            │
    echo  │                                                      │
    echo  │  3. Save the file, then re-run start-windows.bat     │
    echo  └──────────────────────────────────────────────────────┘
    echo.
    pause
    exit /b 0
) ELSE (
    echo  [2/3] .env file found.
)

REM ── Create required directories ──────────────────────────────
IF NOT EXIST data\sessions   mkdir data\sessions
IF NOT EXIST data\chromadb   mkdir data\chromadb
IF NOT EXIST data\embeddings mkdir data\embeddings
IF NOT EXIST logs            mkdir logs

REM ── Start services ───────────────────────────────────────────
echo.
echo  [3/3] Starting services (API + ChromaDB)...
docker compose -f docker-compose.client.yml up -d
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Failed to start services. Check Docker Desktop for errors.
    pause
    exit /b 1
)

echo.
echo  =====================================================
echo   All services started successfully!
echo  =====================================================
echo.
echo   API endpoint : http://localhost:8001
echo   Swagger docs : http://localhost:8001/docs
echo   Health check : http://localhost:8001/health
echo.
echo   (Services are running in the background.)
echo   (Run stop-windows.bat to shut everything down.)
echo.

REM ── Open browser after short delay ──────────────────────────
echo  Opening API docs in your browser...
timeout /t 8 /nobreak >nul
start http://localhost:8001/docs

pause
