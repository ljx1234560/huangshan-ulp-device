@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-web.ps1" %*
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" (
    echo.
    echo Startup failed with exit code %CODE%.
    pause
)
exit /b %CODE%
