@echo off
setlocal

:: Determine the root directory (where this .bat lives — USB root or install folder)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHON=%ROOT%\python\python.exe"

if not exist "%PYTHON%" (
    echo.
    echo  ERROR: Embedded Python が見つかりません。
    echo  Expected: %PYTHON%
    echo.
    echo  setup_packages.bat を先に実行してください。
    echo  Please run setup_packages.bat first.
    echo.
    pause
    exit /b 1
)

"%PYTHON%" "%ROOT%\run.py"

if errorlevel 1 (
    echo.
    echo  アプリの起動に失敗しました。
    echo  Application failed to start.
    pause
)
