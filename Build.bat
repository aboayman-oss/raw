@echo off
setlocal

call .venv\Scripts\activate.bat

powershell -ExecutionPolicy Bypass -File "%~dp0build_release.ps1"
exit /b %errorlevel%
