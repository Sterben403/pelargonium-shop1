@echo off
rem LZ12: local AI search demo. Opens http://127.0.0.1:8012/ai-demo
rem Needs Python 3.11+ and Ollama (installed, or the portable copy in %%LOCALAPPDATA%%\ollama-portable).
setlocal
cd /d "%~dp0"

set "OLLAMA_EXE=ollama"
where ollama >nul 2>nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\ollama-portable\bin\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\ollama-portable\bin\ollama.exe"
    set "OLLAMA_MODELS=%LOCALAPPDATA%\ollama-portable\models"
  ) else (
    echo Ollama not found. Install it from https://ollama.com - without it the demo uses the regular search only.
    set "OLLAMA_EXE="
  )
)

if defined OLLAMA_EXE (
  curl -s http://127.0.0.1:11434/api/version >nul 2>nul
  if errorlevel 1 (
    echo Starting Ollama...
    start "Ollama" /min "%OLLAMA_EXE%" serve
    ping -n 5 127.0.0.1 >nul
  )
  echo Checking model qwen2.5:3b, the first download is about 1.9 GB...
  "%OLLAMA_EXE%" pull qwen2.5:3b
)

if not exist .venv\Scripts\python.exe (
  echo Creating .venv and installing dependencies...
  python -m venv .venv || goto :error
  .venv\Scripts\python -m pip install -q -r ..\backend\requirements.txt httpx tiktoken || goto :error
)

rem open the browser once the server has had time to start
start "" /b cmd /c "ping -n 5 127.0.0.1 >nul & start http://127.0.0.1:8012/ai-demo"
.venv\Scripts\python demo_server.py
goto :eof

:error
echo Failed to set up Python environment.
pause
