@echo off
chcp 65001 >nul
cd /d "D:\QA助手"
set PYTHONPATH=D:\QA助手
python scripts/check_health.py
pause
