@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python 3 is required to run this patcher.
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
)
py -3 "%~dp0install_gui.py"
if errorlevel 1 pause
