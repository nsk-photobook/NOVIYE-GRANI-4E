@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install --user Pillow
  py tools\import_photos.py
) else (
  python -m pip install --user Pillow
  python tools\import_photos.py
)
pause
