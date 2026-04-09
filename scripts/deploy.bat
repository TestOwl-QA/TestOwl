@echo off
chcp 65001 >nul
REM Token优化器模块部署脚本（Windows版）
REM 使用方法: deploy.bat "提交信息"

echo ==========================================
echo TestOwl Token优化器模块部署
echo ==========================================

REM 检查提交信息
if "%~1"=="" (
    set COMMIT_MSG=添加Token优化器模块 - 智能缓存、内容摘要、分块处理
) else (
    set COMMIT_MSG=%~1
)

echo.
echo 📋 提交信息: %COMMIT_MSG%
echo.

REM 1. 检查Git状态
echo 🔍 检查Git状态...
git status

REM 2. 添加新文件
echo.
echo 📦 添加新文件...
git add src/core/token_optimizer.py
git add tests/test_token_optimizer.py
git add test_token_optimizer_simple.py
git add src/skills/document_analyzer/skill.py

REM 3. 查看待提交的文件
echo.
echo 📋 待提交的文件:
git diff --cached --stat

REM 4. 提交
echo.
echo 💾 提交更改...
git commit -m "%COMMIT_MSG%"

REM 5. 推送到远程
echo.
echo 🚀 推送到远程仓库...
for /f "tokens=*" %%a in ('git branch --show-current') do set BRANCH=%%a
git push origin %BRANCH%

echo.
echo ==========================================
echo ✅ 部署完成！
echo ==========================================
echo.
echo 📊 本次更新内容:
echo    - 新增TokenOptimizer核心模块
echo    - 智能缓存系统（内存缓存，24小时过期）
echo    - 内容摘要器（智能压缩70%内容）
echo    - 分块处理器（大文档自动分块）
echo    - Token使用统计和成本估算
echo    - 集成到DocumentAnalyzerSkill
echo.
echo 🧪 测试方法:
echo    python test_token_optimizer_simple.py
echo    python -m pytest tests/test_token_optimizer.py -v
echo.

pause
