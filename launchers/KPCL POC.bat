@echo off
REM KPCL POC - one click: opens the app window and starts its server(s) in the background (reused if already running).
REM Connect the office VPN first for the AI features.
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0launch.ps1" -App KPCL
exit /b 0
