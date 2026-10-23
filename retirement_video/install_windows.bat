@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0"

echo ==================================================
echo  퇴임식 기념영상 제작기 - 실행 환경 확인
echo ==================================================

where ffmpeg > nul 2>&1
if errorlevel 1 (
  echo [주의] FFmpeg가 아직 설치되지 않았습니다.
  echo 프로그램은 실행되지만 MP4 출력과 동영상 분석은 사용할 수 없습니다.
  echo 설치 명령: winget install --id Gyan.FFmpeg -e
  echo.
)

if exist ".venv\Scripts\python.exe" goto install_packages

set "PYTHON_CMD="
where py > nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if defined PYTHON_CMD goto check_python
where python > nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  echo [오류] Python을 찾을 수 없습니다.
  echo https://www.python.org/downloads/windows/ 에서 Python 3.11 이상을 설치하세요.
  echo 설치 화면에서 반드시 "Add Python to PATH"를 선택하세요.
  exit /b 1
)

:check_python
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo [오류] Python 3.11 이상이 필요합니다.
  exit /b 1
)

echo Python 가상환경을 만드는 중입니다...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
  echo [오류] Python 가상환경 생성에 실패했습니다.
  exit /b 1
)

:install_packages
echo 필요한 라이브러리를 확인하고 설치하는 중입니다...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo [오류] 라이브러리 설치에 실패했습니다. 인터넷 연결을 확인하세요.
  exit /b 1
)
echo 설치 준비가 완료되었습니다.
exit /b 0

