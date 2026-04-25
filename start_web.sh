#!/bin/bash
# TestOwl Web 服务启动脚本
PROJECT_ROOT="D:\QA助手"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

echo "🚀 启动 TestOwl Web 服务..."
echo "📂 项目路径: $PROJECT_ROOT"

python -m uvicorn web.api:app --host 0.0.0.0 --port 8081 --reload
