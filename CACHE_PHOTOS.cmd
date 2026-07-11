@echo off
chcp 65001 >nul
python tools\cache_photos.py
if errorlevel 1 (
  echo.
  echo Не удалось скачать фотографии. Проверьте интернет и установку Python.
) else (
  echo.
  echo Фотографии сохранены внутри сайта.
)
pause
