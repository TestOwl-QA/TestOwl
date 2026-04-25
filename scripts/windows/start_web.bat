@echo off
chcp 65001 >nul
cd /d "D:\QA助手"
set PYTHONPATH=D:\QA助手
python -m uvicorn web.api:app --host 0.0.0.0 --port 8081 --reload
pause
