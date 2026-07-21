@echo off
setlocal enabledelayedexpansion
REM Install ATM scheduled task - one task, 4 triggers (06:05, 12:00, 18:00, 21:30)
cd /d "%~dp0"

echo ========================================
echo   ATM - Install Windows Scheduled Task
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

REM Store absolute path
for %%f in ("%EXE_PATH%") do set "EXE_FULL=%%~ff"

REM Generate XML
set "XML=%TEMP%\atm_task.xml"
(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>ATM habit check-in report - 4 times daily^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2024-01-01T06:05:00^</StartBoundary^>
echo       ^<ScheduleByDay^>
echo         ^<DaysInterval^>1^</DaysInterval^>
echo       ^</ScheduleByDay^>
echo     ^</CalendarTrigger^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2024-01-01T12:00:00^</StartBoundary^>
echo       ^<ScheduleByDay^>
echo         ^<DaysInterval^>1^</DaysInterval^>
echo       ^</ScheduleByDay^>
echo     ^</CalendarTrigger^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2024-01-01T18:00:00^</StartBoundary^>
echo       ^<ScheduleByDay^>
echo         ^<DaysInterval^>1^</DaysInterval^>
echo       ^</ScheduleByDay^>
echo     ^</CalendarTrigger^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2024-01-01T21:30:00^</StartBoundary^>
echo       ^<ScheduleByDay^>
echo         ^<DaysInterval^>1^</DaysInterval^>
echo       ^</ScheduleByDay^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>%EXE_FULL:\=\\%^</Command^>
echo       ^<Arguments^>--send-report^</Arguments^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%XML%"

REM Remove old tasks
schtasks /delete /tn "ATM_DailyReport" /f >nul 2>&1
schtasks /delete /tn "ATM_0605" /f >nul 2>&1
schtasks /delete /tn "ATM_1200" /f >nul 2>&1
schtasks /delete /tn "ATM_1800" /f >nul 2>&1
schtasks /delete /tn "ATM_2130" /f >nul 2>&1
schtasks /delete /tn "ATM_Report" /f >nul 2>&1

REM Create single task with 4 triggers
schtasks /create /tn "ATM_Report" /xml "%XML%" /f

if errorlevel 1 (
    echo [FAIL] Run as Administrator.
) else (
    echo [ OK ] Task registered: 06:05 ^| 12:00 ^| 18:00 ^| 21:30
)

del "%XML%" >nul 2>&1
echo.
pause
endlocal
