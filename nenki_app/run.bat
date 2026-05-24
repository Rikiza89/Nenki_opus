@echo off
cd /d %~dp0

set PYTHONHOME=%CD%\python
set PYTHONPATH=%CD%

:: Add PySide6 to PATH so QtWebEngineProcess.exe can find Qt DLLs when
:: spawned as a subprocess (embedded Python does not set this automatically).
set "P6=%CD%\python\Lib\site-packages\PySide6"
if exist "%P6%\QtWebEngineProcess.exe" (
    set "PATH=%P6%;%PATH%"
    set "QTWEBENGINEPROCESS_PATH=%P6%\QtWebEngineProcess.exe"
)

python\python.exe memorial_app\app\main.py

pause
