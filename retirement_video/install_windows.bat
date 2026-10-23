@echo off
chcp 65001 > nul
cd /d "%~dp0"
where ffmpeg > nul 2>&1
if errorlevel 1 (
  echo [안내] FFmpeg가 PATH에 없습니다. ffmpeg.org에서 설치 후 PATH에 추가하세요.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo 설치 준비가 완료되었습니다.

