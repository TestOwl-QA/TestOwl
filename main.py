#!/usr/bin/env python3
"""
GameTestAgent - 游戏测试智能助手

FastAPI Web服务入口文件
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

# ========== FastAPI 部分 ==========
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(title="GameTestAgent API", version="1.0.0")

# ========== 原逻辑部分 ==========
from src.core.agent import GameTestAgent
from src.core.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 全局Agent实例
agent = None

# 启动时初始化Agent
@app.on_event("startup")
async def startup_event():
    global agent
    
    logger.info("正在初始化Agent...")
    try:
        config = get_config()
        config.validate()
        
        agent = GameTestAgent(config)
        
        # 注册技能
        from src.skills.document_analyzer import DocumentAnalyzerSkill
        from src.skills.test_case_generator import TestCaseGeneratorSkill
        
        agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
        agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
        
        logger.info(f"Agent初始化完成！已注册技能: {', '.join(agent.list_skills())}")
    except Exception as e:
        logger.error(f"配置错误: {e}")
        logger.error("请检查 config/config.yaml 文件是否正确配置")
        raise

# 请求模型
class TaskRequest(BaseModel):
    skill: str
    params: Dict[str, Any] = {}

# ========== API 路由 ==========
@app.get("/")
async def root():
    """服务状态检查"""
    return {
        "status": "running",
        "service": "GameTestAgent",
        "skills": agent.list_skills() if agent else []
    }

@app.post("/execute")
async def execute_task(request: TaskRequest):
    """执行任务接口"""
    try:
        result = await agent.execute(request.skill, **request.params)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"任务执行失败: {e}")
        return {"status": "error", "message": str(e)}

# ========== CLI 模式（可选保留） ==========
async def cli_main():
    """原CLI入口"""
    print("=" * 60)
    print("GameTestAgent - CLI模式")
    print("=" * 60)
    print("提示：此程序现在作为Web服务运行，请使用以下命令启动：")
    print("")
    print("  uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print("")
    print("然后在浏览器访问: http://121.41.36.197:8000")
    print("=" * 60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(cli_main())
