@echo off
chcp 936 >nul
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title GIF 导出工具

set "SCRIPT=%~dp0GIF导出工具.py"
if not exist "%SCRIPT%" for %%F in ("%~dp0*.py") do set "SCRIPT=%%~fF"
set "URL=http://127.0.0.1:8765"
set "LOG=%~dp0启动日志.txt"
if not exist "%LOG%" for %%F in ("%~dp0*.txt") do set "LOG=%%~fF"
set "PF86=%ProgramFiles(x86)%"
set "NOPIL="

REM ===== 0) 已经有一个实例在跑：直接开网页，不再启动第二个 =====
call :port_open
if "%UP%"=="1" goto :open

REM ===== 1) 找一个「能 import PIL」的解释器（缺 Pillow 的会被跳过） =====
set "PYW="

REM 1.1 手动指定（换电脑最省事）：环境变量 GIFTOOL_PYTHON，或同目录 python_path.txt
if defined GIFTOOL_PYTHON call :try_exe "%GIFTOOL_PYTHON%"
if not defined PYW if exist "%~dp0python_path.txt" call :try_file "%~dp0python_path.txt"

REM 1.2 py 启动器（PyPA 安装器会注册，能定位任意盘符 / 自定义目录）
call :try_pylauncher -3

REM 1.3 注册表（官方安装器会写 ExecutablePath，自定义安装目录也能找到）
call :try_reg "HKCU\Software\Python\PythonCore"
call :try_reg "HKLM\Software\Python\PythonCore"
call :try_reg "HKLM\Software\WOW6432Node\Python\PythonCore"

REM 1.4 PATH 里的 python（跳过 Microsoft Store 的占位程序）
for /f "delims=" %%P in ('where python 2^>nul') do call :try_where "%%P"

REM 1.5 常见安装目录
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try_dir "%%~fD"
for /d %%D in ("%ProgramFiles%\Python3*") do call :try_dir "%%~fD"
if defined PF86 for /d %%D in ("%PF86%\Python3*") do call :try_dir "%%~fD"
for /d %%D in ("C:\Python3*") do call :try_dir "%%~fD"

REM 1.6 沙盒运行时（最后兜底，通常没装 Pillow）
for /d %%D in ("%LOCALAPPDATA%\DoubaoWork\User Data\sandbox_runtime\bases\*") do call :try_dir "%%~fD\python"

if not defined PYW goto :no_python
if not exist "%SCRIPT%" goto :no_script

REM ===== 2) 后台启动服务（日志由 GIF导出工具.py 写进 启动日志.txt） =====
start "" "%PYW%" "%SCRIPT%"

REM ===== 3) 等端口真正监听再开浏览器，避免打开一个打不开的死页面 =====
call :wait_open
if "%UP%"=="1" goto :open

echo.
echo [错误] GIF 导出工具没能在 30 秒内启动，网页打不开。
echo 常见原因：
echo    1. 端口 8765 被别的程序占用（关掉占用它的程序再试）
echo    2. 当前 Python 缺少 Pillow 或其它依赖
echo    3. GIF导出工具.py 运行报错（见下方日志）
echo.
if exist "%LOG%" (
    echo -------- 启动日志 --------
    powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Encoding UTF8"
    echo --------------------------
) else (
    echo （没有生成 启动日志.txt：Python 解释器可能根本没起来）
)
echo.
pause
exit /b 1

:open
start "" "%URL%"
exit /b 0

:no_python
echo.
echo [错误] 没找到装了 Pillow 的 Python 解释器，工具无法运行。
echo.
if defined NOPIL (
    echo 找到这些 Python，但都缺 Pillow：
    echo    %NOPIL%
    echo.
)
echo 解决（任选一种）：
echo   1. 给已有的 Python 补依赖（在命令行执行，没有则先装 Python）：
echo        python -m pip install pillow
echo   2. 换一台机器 / 换了安装位置时，可以手动指定解释器：
echo        在同目录新建 python_path.txt，里面只写一行 python.exe 的完整路径
echo        或设置环境变量 GIFTOOL_PYTHON=完整路径
echo   3. 全新安装 Python 3（安装时勾选 Add python.exe to PATH）：
echo        https://www.python.org/downloads/
echo.
pause
exit /b 1

:no_script
echo.
echo [错误] 找不到 GIF导出工具.py（它应该和本 bat 在同一个文件夹里）
echo.
pause
exit /b 1

REM ---------------- 子程序 ----------------

:port_open
set "UP=0"
netstat -ano | findstr /c:":8765 " | findstr /i "LISTENING" >nul 2>&1
if not errorlevel 1 set "UP=1"
goto :eof

:wait_open
set "UP=0"
set "TRIES=0"
:wait_loop
call :port_open
if "%UP%"=="1" goto :eof
set /a TRIES+=1
if %TRIES% geq 30 goto :eof
ping -n 2 127.0.0.1 >nul 2>&1
goto :wait_loop

:try_pylauncher
if defined PYW goto :eof
where py >nul 2>nul || goto :eof
for /f "usebackq delims=" %%E in (`py %* -c "import sys;print(sys.executable)" 2^>nul`) do call :try_exe "%%E"
goto :eof

:try_reg
if defined PYW goto :eof
for /f "tokens=2,*" %%A in ('reg query "%~1" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do call :try_exe "%%B"
goto :eof

:try_where
if defined PYW goto :eof
echo %~1 | findstr /i "\\WindowsApps\\" >nul && goto :eof
call :try_exe "%~1"
goto :eof

:try_file
if defined PYW goto :eof
for /f "usebackq delims=" %%P in ("%~1") do call :try_exe "%%P"
goto :eof

:try_dir
if defined PYW goto :eof
call :try_exe "%~1\python.exe"
goto :eof

:try_exe
if defined PYW goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import PIL" >nul 2>&1
if errorlevel 1 (
    set "NOPIL=%NOPIL% %~1"
    goto :eof
)
if exist "%~dpn1w.exe" (set "PYW=%~dpn1w.exe") else (set "PYW=%~1")
goto :eof