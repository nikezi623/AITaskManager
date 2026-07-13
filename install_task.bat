@echo off
REM 安装 ATM 每日定时任务 —— 每天 06:05 发送企业微信任务提醒
cd /d "%~dp0"

set TASK_NAME=ATM_DailyReport

echo ========================================
echo   ATM - 安装 Windows 每日定时任务
echo ========================================
echo.

REM 先删除已有同名任务（静默）
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM 判断是打包后的 EXE 还是源码运行
if exist "dist\AI_TaskManager.exe" (
    set PROGRAM="%~dp0dist\AI_TaskManager.exe" --send-report
    echo [INFO] 使用打包版本: dist\AI_TaskManager.exe
) else if exist "AI_TaskManager.exe" (
    set PROGRAM="%~dp0AI_TaskManager.exe" --send-report
    echo [INFO] 使用打包版本: AI_TaskManager.exe
) else (
    REM 源码运行 —— 需要系统中的 pythonw.exe
    for /f "delims=" %%i in ('where pythonw 2^>nul') do set PYTHONW=%%i
    if defined PYTHONW (
        set PROGRAM="!PYTHONW!" "%~dp0app.py" --send-report
        echo [INFO] 使用源码运行: !PYTHONW!
    ) else (
        echo [ERROR] 未找到 pythonw.exe，请确认 Python 已安装并加入 PATH。
        pause
        exit /b 1
    )
)

echo [INFO] 任务命令: %PROGRAM%
echo.

REM 创建计划任务：每天 06:05 运行
schtasks /create /tn "%TASK_NAME%" /tr "%PROGRAM%" /sc daily /st 06:05 /f

if errorlevel 1 (
    echo.
    echo [ERROR] 注册失败！请以管理员身份运行此脚本。
) else (
    echo.
    echo [OK] 计划任务 "%TASK_NAME%" 已注册成功！
    echo       每天 06:05 自动发送任务日报到企业微信。
    echo       无需软件常驻后台，Windows 系统会准时执行。
)

pause
