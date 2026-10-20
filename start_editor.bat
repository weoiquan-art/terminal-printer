@echo off
chcp 65001 >nul
rem 双击启动标签编辑器（浏览器会自动打开）
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 没找到 .venv，请先按 HANDOFF.md 建立环境
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 editor.py
pause
