@echo off
chcp 65001 >nul
cd /d "E:\My_work\PixelsProject\Aseprite\tiled"
title 预览GIF一键导出
echo ==========================================
echo   预览 GIF 一键导出（自动验证+渲染）
echo   可选地图：预览01 / 预览02 / map01_预览
echo ==========================================
if "%~1"=="" (
  set /p MAP=请输入地图名后回车：
) else (
  set MAP=%~1
)
python "%~dp0export_preview.py" "%MAP%"
echo.
pause
