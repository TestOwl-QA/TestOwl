"""MCP SSE 服务器 - 支持远程调用，必须使用用户自己的API Key"""
import os
import base64
import aiofiles
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response, JSONResponse
import uvicorn

PROJECT_ROOT = Path(__file__).parent.resolve()
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

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
    # 设置占位符绕过验证
    os.environ["LLM_API_KEY"] = "placeholder"
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
        # 文件上传工具
        Tool(name="upload_file", description="上传文件到服务器，返回文件路径。支持通过Base64上传文件内容。",
             inputSchema={
                 "type": "object",
                 "properties": {
                     "filename": {"type": "string", "description": "文件名，如 requirements.docx"},
                     "content_base64": {"type": "string", "description": "文件的Base64编码内容"}
                 },
                 "required": ["filename", "content_base64"]
             }),
        
        # 需求分析 - 支持文本和文件
        Tool(name="analyze_document", description="分析需求文档，提取测试点。支持：1) 直接传入文本内容 2) 传入已上传文件的路径",
             inputSchema={
                 "type": "object", 
                 "properties": {
                     "text": {"type": "string", "description": "直接传入的需求文本内容（碎片化描述）"},
                     "file_path": {"type": "string", "description": "已上传文件的路径"}
                 }
             }),
        
        # 测试用例生成 - 支持文本和文件
        Tool(name="generate_test_cases", description="生成测试用例。支持：1) 直接传入需求文本 2) 传入已上传文件路径",
             inputSchema={
                 "type": "object", 
                 "properties": {
                     "text": {"type": "string", "description": "直接传入的需求文本内容"},
                     "file_path": {"type": "string", "description": "已上传文件的路径"},
                     "output_format": {"type": "string", "enum": ["excel", "xmind"], "description": "输出格式，默认excel"}
                 }
             }),
        
        # Bug 追踪
        Tool(name="track_bug", description="记录和追踪 Bug，传入 Bug 详细描述",
             inputSchema={"type": "object", "properties": {"bug_info": {"type": "string"}}, "required": ["bug_info"]}),
        
        # 表格检查 - 支持文件
        Tool(name="check_table", description="检查表格数据",
             inputSchema={
                 "type": "object",
                 "properties": {
                     "file_path": {"type": "string", "description": "已上传的表格文件路径"},
                     "text": {"type": "string", "description": "直接传入的表格数据描述"}
                 }
             })
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if not user_api_key:
        return [TextContent(type="text", text="错误：未检测到 API Key。请在 MCP 服务器配置中添加请求头：X-API-Key=你的KIMI密钥")]
    
    os.environ["LLM_API_KEY"] = user_api_key
    
    if name == "upload_file":
        # 处理文件上传
        filename = arguments.get("filename", "")
        content_base64 = arguments.get("content_base64", "")
        
        if not filename or not content_base64:
            return [TextContent(type="text", text="错误：需要提供 filename 和 content_base64")]
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{filename}"
        file_path = UPLOAD_DIR / safe_name
        
        # 解码并保存
        try:
            file_content = base64.b64decode(content_base64)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)
            
            return [TextContent(type="text", text=f"文件上传成功！路径：{str(file_path)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"上传失败：{str(e)}")]
    
    elif name == "analyze_document":
        text = arguments.get("text", "")
        file_path = arguments.get("file_path", "")
        
        if text:
            # 使用文本内容
            result = await agent.execute("document_analyzer", {"text": text})
        elif file_path:
            # 使用文件路径
            result = await agent.execute("document_analyzer", {"file_path": file_path})
        else:
            return [TextContent(type="text", text="错误：需要提供 text 或 file_path")]
    
    elif name == "generate_test_cases":
        text = arguments.get("text", "")
        file_path = arguments.get("file_path", "")
        output_format = arguments.get("output_format", "excel")
        
        params = {"output_format": output_format}
        if text:
            params["text"] = text
        elif file_path:
            params["file_path"] = file_path
        else:
            return [TextContent(type="text", text="错误：需要提供 text 或 file_path")]
        
        result = await agent.execute("test_case_generator", params)
    
    elif name == "track_bug":
        result = await agent.execute("bug_tracker", arguments)
    
    elif name == "check_table":
        text = arguments.get("text", "")
        file_path = arguments.get("file_path", "")
        
        if file_path:
            result = await agent.execute("table_checker", {"file_path": file_path})
        elif text:
            result = await agent.execute("table_checker", {"text": text})
        else:
            return [TextContent(type="text", text="错误：需要提供 text 或 file_path")]
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]
    
    if result.success:
        return [TextContent(type="text", text=str(result.data))]
    else:
        return [TextContent(type="text", text=f"执行失败: {result.error}")]

def get_api_key_from_request(request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return api_key
    return None

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
