@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0demo.py" --autoplay %*
) else (
  python "%~dp0demo.py" --autoplay %*
)
set "demo_result=%errorlevel%"
if not "%demo_result%"=="0" (
  echo.
  echo See the error above. The demo requires Python 3.10+ with Tcl/Tk enabled.
  if not "%~1"=="--smoke-test" pause
)
exit /b %demo_result%
