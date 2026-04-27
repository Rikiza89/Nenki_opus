@echo off
cd /d %~dp0

set PYTHONHOME=%CD%\python
set PYTHONPATH=%CD%

python\python.exe memorial_app\app\main.py

pause
