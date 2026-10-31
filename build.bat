@echo off
REM Compila Info Widget y deja el .exe en .\dist
REM Uso:  build.bat

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
exit /b %ERRORLEVEL%
