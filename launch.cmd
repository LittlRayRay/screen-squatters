@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
  start "" pythonw "%~dp0desktop.py"
) else (
  python "%~dp0desktop.py"
  pause
)
