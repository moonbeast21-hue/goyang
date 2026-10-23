@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0"
call install_windows.bat
if errorlevel 1 goto failed

echo 프로그램을 시작합니다...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo ==================================================
echo 프로그램을 실행하지 못했습니다.
echo 이 창의 오류 내용을 사진으로 찍어 보내주세요.
echo ==================================================
pause
exit /b 1

