@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ========================================
echo   Memorial App Setup
echo ========================================
echo.

:: ---- Root path ----
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PY_DIR=%ROOT%\python"
set "PYTHON=%PY_DIR%\python.exe"
set "SITE_PKG=%PY_DIR%\Lib\site-packages"
set "PTH_FILE=%PY_DIR%\python311._pth"

:: ---- Step 1: Check Python ----
echo [1/5] Checking Python...
if not exist "%PYTHON%" (
    echo ERROR: python\python.exe not found.
    echo.
    echo Download "Windows embeddable package (64-bit)" from:
    echo   https://www.python.org/downloads/release/python-3119/
    echo and extract it into the "python" folder next to this script.
    pause
    exit /b 1
)
echo OK
echo.

:: ---- Step 2: Disable isolated mode (rename _pth) ----
echo [2/5] Disabling isolated mode...
if exist "%PTH_FILE%" (
    ren "%PTH_FILE%" "python311._pth.bak"
    echo OK
) else (
    echo WARNING: python311._pth not found, skipping.
)
echo.

:: ---- Step 3: Create site-packages ----
echo [3/5] Creating site-packages...
if not exist "%SITE_PKG%" mkdir "%SITE_PKG%"
echo OK
echo.

:: ---- Step 4: Install pip ----
echo [4/5] Installing pip...
"%PYTHON%" -m ensurepip --upgrade >nul 2>&1

if errorlevel 1 (
    echo ensurepip failed, downloading get-pip.py...
    curl -L -o "%TEMP%\get-pip.py" https://bootstrap.pypa.io/get-pip.py
    if errorlevel 1 (
        echo ERROR: download failed. Check your internet connection.
        pause
        exit /b 1
    )
    "%PYTHON%" "%TEMP%\get-pip.py"
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 1
    )
    del "%TEMP%\get-pip.py" >nul 2>&1
)
echo OK
echo.

:: ---- Step 5: Install packages ----
echo [5/5] Installing packages...
echo.

set "PIP=%PYTHON% -m pip"

:: Upgrade build tools first
%PIP% install --upgrade pip setuptools wheel
if errorlevel 1 goto error

:: numpy must come before pandas (pin below 2 for compatibility)
%PIP% install "numpy<2"
if errorlevel 1 goto error

:: pandas pinned for numpy<2 compatibility
%PIP% install "pandas<2.2"
if errorlevel 1 goto error

:: PySide6 exact version for stability
%PIP% install "PySide6==6.6.1"
if errorlevel 1 goto error

:: WebEngine for live HTML preview in the visual editor
%PIP% install "PySide6-WebEngine==6.6.1"
if errorlevel 1 (
    echo WARNING: PySide6-WebEngine install failed.
    echo          The visual editor will fall back to plain text preview.
    echo          This does not affect Word/PDF export.
)

:: Remaining packages
%PIP% install SQLAlchemy openpyxl xlrd python-docx reportlab
if errorlevel 1 goto error

echo.
echo ========================================
echo   Setup Complete!
echo   Run run.bat to start the application.
echo ========================================
pause
exit /b 0

:error
echo.
echo ERROR: Installation failed. Check the output above.
pause
exit /b 1
