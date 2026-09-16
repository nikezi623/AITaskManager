@echo off
REM ASCII-only and CRLF-terminated: cmd.exe parses .bat byte-by-byte using
REM the console code page, and non-ASCII text (or LF endings) desyncs it.
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

REM Deploy next to the user data, which lives in ..\dist\task_pool.
REM The shortcut points at ..\dist, so leaving the build in here would
REM mean double-clicking a stale executable.
REM
REM NEVER delete or rewrite anything under ..\dist\task_pool or
REM ..\dist\.atm: that is live user data plus the sync snapshot, and
REM the diff cannot tell a deletion from something it has never seen.
copy /y "dist\AI_TaskManager.exe" "..\dist\AI_TaskManager.exe" >nul
if errorlevel 1 (
  echo [WARN] Could not copy to ..\dist - is the app still running?
)

echo.
echo Build finished.
echo   AITaskManager\dist\AI_TaskManager.exe  (build output)
echo   dist\AI_TaskManager.exe               (launch this one)
endlocal
