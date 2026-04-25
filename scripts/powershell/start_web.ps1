# TestOwl Web 服务启动脚本
$ProjectRoot = "D:\QA助手"
Set-Location $ProjectRoot
$env:PYTHONPATH = $ProjectRoot

Write-Host "🚀 启动 TestOwl Web 服务..." -ForegroundColor Green
Write-Host "📂 项目路径: $ProjectRoot" -ForegroundColor Cyan

python -m uvicorn web.api:app --host 0.0.0.0 --port 8081 --reload
