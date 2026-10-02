@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "setup_and_run.ps1" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Process exited with code %ERRORLEVEL%.
    pause
)
endlocal