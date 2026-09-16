@echo off
REM UTF-8 so the Chinese habit names survive the console.
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ========================================
echo   ATM - 与手机同步数据
echo ========================================
echo.
echo 重要：请先关闭 AI_TaskManager 程序。
echo 程序运行时会把内存里的任务列表整个覆盖回文件，
echo 那样同步刚拉下来的数据就白做了。
echo.
pause

python tools\atm_sync.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
  echo [失败] 上面有错误信息。
) else (
  echo [完成] 现在可以重新打开程序了。
)
pause
endlocal
exit /b %EXITCODE%
