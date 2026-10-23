@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call install_windows.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe main.py

