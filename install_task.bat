@echo off
REM Install ATM daily scheduled task - runs at 06:05 every day
cd /d "%~dp0"

set TASK_NAME=ATM_DailyReport

echo ========================================
echo   ATM - Install Windows Scheduled Task
echo ========================================
echo.

REM Remove existing task silently
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Find the EXE - check parent dist first (where user task_pool lives)
set EXE_PATH=
if exist "%~dp0..\dist\AI_TaskManager.exe" (
    set "EXE_PATH=%~dp0..\dist\AI_TaskManager.exe"
    echo [INFO] Using: ..\dist\AI_TaskManager.exe
) else if exist "%~dp0dist\AI_TaskManager.exe" (
    set "EXE_PATH=%~dp0dist\AI_TaskManager.exe"
    echo [INFO] Using: dist\AI_TaskManager.exe
) else if exist "%~dp0AI_TaskManager.exe" (
    set "EXE_PATH=%~dp0AI_TaskManager.exe"
    echo [INFO] Using: AI_TaskManager.exe
)

if defined EXE_PATH (
    schtasks /create /tn "%TASK_NAME%" /tr "%EXE_PATH% --send-report" /sc daily /st 06:05 /f
    if errorlevel 1 (
        echo [ERROR] Failed to register task. Run as Administrator.
    ) else (
        echo [OK] Task "%TASK_NAME%" registered successfully.
        echo     Will run daily at 06:05.
    )
) else (
    echo [ERROR] AI_TaskManager.exe not found.
    echo         Run build.bat first.
)

pause
