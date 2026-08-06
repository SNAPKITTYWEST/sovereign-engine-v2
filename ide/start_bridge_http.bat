@echo off
REM Start Python HTTP Bridge Server
REM Run this before starting the C IDE

echo Starting Sovereign Engine HTTP Bridge...
echo Host: 127.0.0.1:9000
echo.

cd /d C:\tmp\sovereign-reverse\engine

REM Activate venv if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Run HTTP bridge
python -m src.bridge.http_server

pause
