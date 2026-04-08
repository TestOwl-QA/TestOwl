#!/usr/bin/env python3
"""
TestOwl Web API 服务入口

提供HTTP REST API接口，使Agent可以作为Web服务被调用
修复问题: GT-003 路由404错误
"""

import os
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径（确保在任何目录启动都能找到模块）
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from src.core.config import Config, get_config
from src.core.agent import GameTestAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 全局Agent实例
agent: GameTestAgent = None
config: Config = None


class AnalyzeRequest(BaseModel):
    """文档分析请求"""
    file_path: str
    output_format: Optional[str] = "json"


class GenerateRequest(BaseModel):
    """测试用例生成请求"""
    document_path: str
    output_format: Optional[str] = "excel"


class BugTrackRequest(BaseModel):
    """Bug追踪请求"""
    bug_info: str
    platform: Optional[str] = None


class TableCheckRequest(BaseModel):
    """表检查请求"""
    table_path: str
    rules: Optional[List[str]] = None


class SkillResponse(BaseModel):
    """技能执行响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent, config
    
    # 启动时初始化
    try:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
        config = Config(str(config_path) if config_path.exists() else None)
        config.validate()
        
        agent = GameTestAgent(config)
        
        # 注册所有技能
        from src.skills.document_analyzer import DocumentAnalyzerSkill
        from src.skills.test_case_generator import TestCaseGeneratorSkill
        from src.skills.bug_tracker import BugTrackerSkill
        from src.skills.table_checker import TableCheckerSkill
        
        agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
        agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
        agent.register_skill("bug_tracker", BugTrackerSkill(config))
        agent.register_skill("table_checker", TableCheckerSkill(config))
        
        logger.info("✅ TestOwl Web API 启动成功")
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        raise
    
    yield
    
    # 关闭时清理
    logger.info("🛑 TestOwl Web API 关闭")


# 创建FastAPI应用
app = FastAPI(
    title="TestOwl API",
    description="TestOwl - 游戏测试智能助手，提供文档分析、测试用例生成、Bug追踪、表检查等功能",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """根路径 - 服务状态检查"""
    return {
        "status": "running",
        "service": "TestOwl",
        "version": "1.0.0",
        "skills": agent.list_skills() if agent else [],
        "docs_url": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "agent_status": agent.status.value if agent else "unknown"
    }


@app.get("/skills")
async def list_skills():
    """列出所有可用技能"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    return {
        "skills": agent.list_skills(),
        "count": len(agent.list_skills())
    }


@app.post("/analyze", response_model=SkillResponse)
async def analyze_document(request: AnalyzeRequest):
    """分析需求文档"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    try:
        result = await agent.execute(
            "document_analyzer",
            {"file_path": request.file_path, "output_format": request.output_format}
        )
        return SkillResponse(success=result.success, data=result.data, error=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate", response_model=SkillResponse)
async def generate_test_cases(request: GenerateRequest):
    """生成测试用例"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    try:
        result = await agent.execute(
            "test_case_generator",
            {"document_path": request.document_path, "output_format": request.output_format}
        )
        return SkillResponse(success=result.success, data=result.data, error=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bug/track", response_model=SkillResponse)
async def track_bug(request: BugTrackRequest):
    """记录和追踪Bug"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    try:
        result = await agent.execute(
            "bug_tracker",
            {"bug_info": request.bug_info, "platform": request.platform}
        )
        return SkillResponse(success=result.success, data=result.data, error=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/table/check", response_model=SkillResponse)
async def check_table(request: TableCheckRequest):
    """检查表格数据"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    try:
        params = {"table_path": request.table_path}
        if request.rules:
            params["rules"] = request.rules
        
        result = await agent.execute("table_checker", params)
        return SkillResponse(success=result.success, data=result.data, error=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"全局异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量读取配置，提供默认值
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "8000"))
    reload = os.getenv("AGENT_RELOAD", "false").lower() == "true"
    
    print(f"🚀 启动 TestOwl Web API...")
    print(f"📍 访问地址: http://{host}:{port}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "web_api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
