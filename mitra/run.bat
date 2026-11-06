@echo off
REM Sakala Mitra - starts the voice agent on port 8030 (and the Sakala POC on 8020 if it is down)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
start "" http://localhost:8030
python -m uvicorn server.main:app --port 8030
