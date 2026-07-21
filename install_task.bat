@echo off
setlocal enabledelayedexpansion
REM Install ATM scheduled tasks - 4 times daily (06:05, 12:00, 18:00, 21:30)
cd /d "%~dp0"

echo ========================================
echo   ATM - Install Windows Scheduled Tasks
echo ========================================
echo.

REM Find the EXE
set EXE_PATH=
if exist "%~dp0..\dist\AI_TaskManager.exe" (
    set "EXE_PATH=%~dp0..\dist\AI_TaskManager.exe"
    echo [INFO] EXE: ..\dist\AI_TaskManager.exe
) else if exist "%~dp0dist\AI_TaskManager.exe" (
    set "EXE_PATH=%~dp0dist\AI_TaskManager.exe"
    echo [INFO] EXE: dist\AI_TaskManager.exe
) else if exist "%~dp0AI_TaskManager.exe" (
    set "EXE_PATH=%~dp0AI_TaskManager.exe"
    echo [INFO] EXE: AI_TaskManager.exe
)

if not defined EXE_PATH (
    echo [ERROR] AI_TaskManager.exe not found.
    pause
    exit /b 1
)

echo.

REM Remove old single task
schtasks /delete /tn "ATM_DailyReport" /f >nul 2>&1

REM Register 4 daily tasks
schtasks /delete /tn "ATM_0605" /f >nul 2>&1
schtasks /create /tn "ATM_0605" /tr "%EXE_PATH% --send-report" /sc daily /st 06:05 /f
if errorlevel 1 (echo [FAIL] 06:05) else (echo [ OK ] 06:05)

schtasks /delete /tn "ATM_1200" /f >nul 2>&1
schtasks /create /tn "ATM_1200" /tr "%EXE_PATH% --send-report" /sc daily /st 12:00 /f
if errorlevel 1 (echo [FAIL] 12:00) else (echo [ OK ] 12:00)

schtasks /delete /tn "ATM_1800" /f >nul 2>&1
schtasks /create /tn "ATM_1800" /tr "%EXE_PATH% --send-report" /sc daily /st 18:00 /f
if errorlevel 1 (echo [FAIL] 18:00) else (echo [ OK ] 18:00)

schtasks /delete /tn "ATM_2130" /f >nul 2>&1
schtasks /create /tn "ATM_2130" /tr "%EXE_PATH% --send-report" /sc daily /st 21:30 /f
if errorlevel 1 (echo [FAIL] 21:30) else (echo [ OK ] 21:30)

echo.
echo All done. 4 daily reports: 06:05 ^| 12:00 ^| 18:00 ^| 21:30
pause
endlocal
