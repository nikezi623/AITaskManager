@echo off
REM Keep this file ASCII-only and CRLF-terminated: cmd.exe parses .bat
REM byte-by-byte using the console code page, so non-ASCII text (or LF
REM endings) desyncs it, especially after chcp. Chinese output lives in
REM atm_sync.py, which handles UTF-8 properly.
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ========================================
echo   ATM - Sync with phone
echo ========================================
echo.
echo IMPORTANT: close AI_TaskManager before continuing.
echo A running window keeps its own copy in memory and rewrites the
echo whole task list on the next change, discarding what this pulls down.
echo.
pause

REM Built from %~dp0 so this works regardless of the working directory
REM and needs no literal backslash in the source.
set SCRIPT=%~dp0atm_sync.py
python "%SCRIPT%" %*
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
  echo [FAILED] See the messages above.
) else (
  echo [OK] You can reopen the app now.
)
pause
endlocal
exit /b %EXITCODE%
