@echo off
title GAIA: Emergent Civilization
echo Starting GAIA...

:: Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama is not running. The AI will fall back to basic rules.
    echo Please install Ollama and run: ollama pull qwen2.5-coder:7b
    echo.
)

start /B python -m uvicorn server:app --port 8000
timeout /t 2 /nobreak >nul
start viewer_pixi.html

echo.
echo GAIA is running! Close this window to stop the simulation.
pause
