$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

try {
    Write-Host "Retirement Video Maker - setup" -ForegroundColor Cyan

    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            Write-Host "Creating Python environment..."
            & py -3 -m venv .venv
        }
        elseif (Get-Command python -ErrorAction SilentlyContinue) {
            Write-Host "Creating Python environment..."
            & python -m venv .venv
        }
        else {
            throw "Python was not found. Install Python 3.11 or newer and select Add Python to PATH."
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Python could not create the virtual environment."
        }
    }

    Write-Host "Installing required libraries. The first run may take several minutes..."
    & ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Library installation failed. Check the internet connection and the messages above."
    }

    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Host "WARNING: FFmpeg is not on PATH. Editing works, but MP4 export is unavailable." -ForegroundColor Yellow
    }

    Write-Host "Starting the program..." -ForegroundColor Green
    & ".venv\Scripts\python.exe" main.py
    if ($LASTEXITCODE -ne 0) {
        throw "The program stopped with exit code $LASTEXITCODE."
    }
}
catch {
    Write-Host ""
    Write-Host "STARTUP ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Copy all messages from this window and send them for diagnosis." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}
