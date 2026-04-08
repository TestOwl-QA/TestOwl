"""MCP SSE 服务器 - 支持远程调用，必须使用用户自己的API Key"""
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
import uvicorn

PROJECT_ROOT = Path(__file__).parent.resolve()

from typing import List
from mcp.types import Tool, TextContent
from src.core.config import Config
from src.core.agent import GameTestAgent
from src.skills.document_analyzer import DocumentAnalyzerSkill
from src.skills.test_case_generator import TestCaseGeneratorSkill
from src.skills.bug_tracker import BugTrackerSkill
from src.skills.table_checker import TableCheckerSkill

server = Server("testowl")
agent = None
sse = SseServerTransport("/messages/")
user_api_key = None

@asynccontextmanager
async def lifespan(app):
    global agent
    config = Config(str(PROJECT_ROOT / "config" / "config.yaml"))
    agent = GameTestAgent(config)
    agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
    agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
    agent.register_skill("bug_tracker", BugTrackerSkill(config))
    agent.register_skill("table_checker", TableCheckerSkill(config))
    yield

@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(name="analyze_document", description="分析需求文档，提取测试点",
             inputSchema={"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}),
        Tool(name="generate_test_cases", description="生成测试用例",
             inputSchema={"type": "object", "properties": {"document_path": {"type": "string"}, "output_format": {"type": "string", "enum": ["excel", "xmind"]}}, "required": ["document_path"]}),
        Tool(name="track_bug", description="记录和追踪 Bug",
             inputSchema={"type": "object", "properties": {"bug_info": {"type": "string"}}, "required": ["bug_info"]}),
        Tool(name="check_table", description="检查表格数据",
             inputSchema={"type": "object", "properties": {"table_path": {"type": "string"}}, "required": ["table_path"]})
    ]

def get_api_key_from_request(request) -> Optional[str]:
    """从请求头获取用户的 API Key"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return api_key
    
    return None

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    # 必须有用户的 API Key
    if not user_api_key:
        return [TextContent(type="text", text="错误：未检测到 API Key。请在 MCP 服务器配置中添加请求头：X-API-Key=你的KIMI密钥")]
    
    os.environ["LLM_API_KEY"] = user_api_key
    
    if name == "analyze_document":
        result = await agent.execute("document_analyzer", arguments)
    elif name == "generate_test_cases":
        result = await agent.execute("test_case_generator", arguments)
    elif name == "track_bug":
        result = await agent.execute("bug_tracker", arguments)
    elif name == "check_table":
        result = await agent.execute("table_checker", arguments)
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]
    
    if result.success:
        return [TextContent(type="text", text=str(result.data))]
    else:
        return [TextContent(type="text", text=f"执行失败: {result.error}")]

async def handle_sse(request):
    global user_api_key
    user_api_key = get_api_key_from_request(request)
    
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())
    return Response()

app = Starlette(lifespan=lifespan, routes=[
    Route("/sse", endpoint=handle_sse, methods=["GET"]),
    Mount("/messages/", app=sse.handle_post_message),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
