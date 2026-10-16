@echo off
chcp 65001 >nul
echo ===== 最近的打卡结果 (LATEST-STATUS.txt) =====
if exist "%~dp0LATEST-STATUS.txt" (type "%~dp0LATEST-STATUS.txt") else (echo 还没有记录)
echo.
echo ===== 失败记录 (failures\) =====
if exist "%~dp0failures" (dir /b "%~dp0failures" 2>nul) else (echo 没有失败记录)
echo.
echo ===== checkin.log 最后 30 行 =====
powershell -NoProfile -Command "Get-Content '%~dp0checkin.log' -Tail 30"
echo.
pause
