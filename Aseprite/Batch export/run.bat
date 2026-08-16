@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
where python >nul 2>&1 && python "sprite_sheet_combiner.py" || (echo [ERROR] Python not found! Please install Python from python.org & pause)
pause
