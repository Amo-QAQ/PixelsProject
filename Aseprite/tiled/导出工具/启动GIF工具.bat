@echo off
cd /d "%~dp0"
set "PYW="

REM 1) 先在 PATH 里找 pythonw
where pythonw >nul 2>nul && (
    for /f "del=" %%P in ('where pythonw') do set "PYW=%%P"
)

REM 2) PATH 没有就扫沙盒 bases（用 LOCALAPPDATA，不写死用户名）
if not defined PYW (
    for /d %%a in ("%LOCALAPPDATA%\DoubaoWork\User Data\sandbox_runtime\bases\*") do (
        if exist "%%a\python\pythonw.exe" set "PYW=%%a\python\pythonw.exe"
    )
)

if not defined PYW (
    echo [错误] 未找到 Python 运行时，请先安装 Python 或联系管理员。
    pause
    exit /b
)

start "" "%PYW%" "%~dp0GIF导出工具.py"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8765"
exit
