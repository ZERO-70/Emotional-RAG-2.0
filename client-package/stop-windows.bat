@echo off
title Emotional RAG - Shutdown
cd /d "%~dp0"

echo.
echo  =====================================================
echo   Emotional RAG Backend  ^|  Shutting Down
echo  =====================================================
echo.

docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  [WARN] Docker Desktop does not appear to be running.
    echo         Nothing to stop.
    pause
    exit /b 0
)

echo  Stopping all services...
docker compose -f docker-compose.client.yml down

echo.
echo  All services stopped.
echo  Your data is preserved in the "data" and "chromadb-data" volume.
echo.
pause
