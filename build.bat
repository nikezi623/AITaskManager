@echo off
setlocal
cd /d "%~dp0"

python -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
  echo Installing PyInstaller...
  python -m pip install pyinstaller
  if errorlevel 1 exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --icon "photo\app_icon.ico" --add-data "photo\app_icon.ico;photo" --name AI_TaskManager app.py
if errorlevel 1 exit /b 1

REM Clean stale task_pool in build output dir (user data lives in ..\\dist\\task_pool)
if exist "dist\task_pool" rmdir /s /q "dist\task_pool"

echo.
echo Build finished: dist\AI_TaskManager.exe
endlocal
