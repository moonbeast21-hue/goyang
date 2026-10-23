@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call install_windows.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name "퇴임식_기념영상_제작기" --collect-all librosa --collect-all soundfile main.py
echo EXE output: dist\퇴임식_기념영상_제작기\퇴임식_기념영상_제작기.exe
pause

