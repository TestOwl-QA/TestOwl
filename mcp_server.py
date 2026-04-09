"""MCP 服务器 - 支持 STDIO 和 SSE 两种模式

使用方法:
    # STDIO 模式（默认，用于 Claude Desktop 等本地客户端）
    python mcp_server.py
    
    # SSE 模式（用于远程连接，支持文件上传和 API Key 验证）
    python mcp_server.py --sse
    python mcp_server.py --sse --host 0.0.0.0 --port 8000
"""
import os
import sys
import argparse
import base64
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

from mcp.server import Server
from mcp.types import Tool, TextContent
from src.core.config import Config
from src.core.agent import GameTestAgent
from src.skills.document_analyzer import DocumentAnalyzerSkill
from src.skills.test_case_generator import TestCaseGeneratorSkill
from src.skills.bug_tracker import BugTrackerSkill
from src.skills.table_checker import TableCheckerSkill
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ==================== 核心 MCP 逻辑 ====================

class MCPHandler:
    """MCP 请求处理器"""
    
    def __init__(self):
        self.agent: GameTestAgent = None
        self.server = Server("testowl")
        self.user_api_key: Optional[str] = None
        self._setup_tools()
    
    def _setup_tools(self):
        """设置 MCP 工具"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                # 文件上传工具（SSE 模式专用）
                Tool(name="upload_file", description="上传文件到服务器，返回文件路径。支持通过Base64上传文件内容。（SSE模式专用）",
                     inputSchema={
                         "type": "object",
                         "properties": {
                             "filename": {"type": "string", "description": "文件名，如 requirements.docx"},
                             "content_base64": {"type": "string", "description": "文件的Base64编码内容"}
                         },
                         "required": ["filename", "content_base64"]
                     }),
                
                # 需求分析
                Tool(name="analyze_document", description="分析需求文档，提取测试点。支持：1) 直接传入文本内容 2) 传入已上传文件的路径（SSE模式）",
                     inputSchema={
                         "type": "object", 
                         "properties": {
                             "text": {"type": "string", "description": "直接传入的需求文本内容（碎片化描述）"},
                             "file_path": {"type": "string", "description": "已上传文件的路径（SSE模式）"}
                         }
                     }),
                
                # 测试用例生成
                Tool(name="generate_test_cases", description="生成测试用例。支持：1) 直接传入需求文本 2) 传入已上传文件路径（SSE模式）",
                     inputSchema={
                         "type": "object", 
                         "properties": {
                             "text": {"type": "string", "description": "直接传入的需求文本内容"},
                             "file_path": {"type": "string", "description": "已上传文件的路径（SSE模式）"},
                             "output_format": {"type": "string", "enum": ["excel", "xmind"], "description": "输出格式，默认excel"}
                         }
                     }),
                
                # Bug 追踪
                Tool(name="track_bug", description="记录和追踪 Bug，传入 Bug 详细描述",
                     inputSchema={"type": "object", "properties": {"bug_info": {"type": "string"}}, "required": ["bug_info"]}),
                
                # 表格检查
                Tool(name="check_table", description="检查表格数据",
                     inputSchema={
                         "type": "object",
                         "properties": {
                             "file_path": {"type": "string", "description": "已上传的表格文件路径（SSE模式）"},
                             "text": {"type": "string", "description": "直接传入的表格数据描述"}
                         }
                     })
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            # SSE 模式下检查 API Key
            if self.user_api_key is not None and not self.user_api_key:
                return [TextContent(type="text", text="错误：未检测到 API Key。请在 MCP 服务器配置中添加请求头：X-API-Key=你的KIMI密钥")]
            
            if self.user_api_key:
                os.environ["LLM_API_KEY"] = self.user_api_key
            
            return await self._handle_tool_call(name, arguments)
    
    async def _handle_tool_call(self, name: str, arguments: dict) -> list:
        """处理工具调用"""
        
        if name == "upload_file":
            return await self._handle_upload(arguments)
        
        elif name == "analyze_document":
            text = arguments.get("text", "")
            file_path = arguments.get("file_path", "")
            
            if text:
                result = await self.agent.execute("document_analyzer", {"text": text})
            elif file_path:
                result = await self.agent.execute("document_analyzer", {"file_path": file_path})
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
            
            result = await self.agent.execute("test_case_generator", params)
        
        elif name == "track_bug":
            result = await self.agent.execute("bug_tracker", arguments)
        
        elif name == "check_table":
            text = arguments.get("text", "")
            file_path = arguments.get("file_path", "")
            
            if file_path:
                result = await self.agent.execute("table_checker", {"file_path": file_path})
            elif text:
                result = await self.agent.execute("table_checker", {"text": text})
            else:
                return [TextContent(type="text", text="错误：需要提供 text 或 file_path")]
        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
        
        if result.success:
            return [TextContent(type="text", text=str(result.data))]
        else:
            return [TextContent(type="text", text=f"执行失败: {result.error}")]
    
    async def _handle_upload(self, arguments: dict) -> list:
        """处理文件上传"""
        try:
            import aiofiles
        except ImportError:
            return [TextContent(type="text", text="错误：文件上传需要 aiofiles 库，请安装：pip install aiofiles")]
        
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
    
    def init_agent(self, api_key: Optional[str] = None):
        """初始化 Agent"""
        if api_key:
            os.environ["LLM_API_KEY"] = api_key
        else:
            os.environ["LLM_API_KEY"] = os.environ.get("LLM_API_KEY", "")
        
        config = Config(str(PROJECT_ROOT / "config" / "config.yaml"))
        self.agent = GameTestAgent(config)
        self.agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
        self.agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
        self.agent.register_skill("bug_tracker", BugTrackerSkill(config))
        self.agent.register_skill("table_checker", TableCheckerSkill(config))


# ==================== STDIO 模式 ====================

async def run_stdio():
    """运行 STDIO 模式服务器"""
    from mcp.server.stdio import stdio_server
    
    handler = MCPHandler()
    handler.init_agent()
    
    async with stdio_server() as (read_stream, write_stream):
        await handler.server.run(read_stream, write_stream, handler.server.create_initialization_options())


# ==================== SSE 模式 ====================

async def run_sse(host: str = "0.0.0.0", port: int = 8000):
    """运行 SSE 模式服务器"""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import Response
    from contextlib import asynccontextmanager
    import uvicorn
    
    handler = MCPHandler()
    sse_transport = SseServerTransport("/messages/")
    
    def get_api_key_from_request(request) -> Optional[str]:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return request.headers.get("X-API-Key", "")
    
    async def handle_sse(request):
        from starlette.requests import Request
        handler.user_api_key = get_api_key_from_request(request)
        handler.init_agent()  # 获取到 Key 后再初始化 Agent
        scope = request.scope
        receive = request.receive
        send = request._send
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await handler.server.run(streams[0], streams[1], handler.server.create_initialization_options())
    
    async def handle_post_message(request):
        """处理POST消息 - 适配新版MCP SDK"""
        scope = request.scope
        receive = request.receive
        send = request._send
        await sse_transport.handle_post_message(scope, receive, send)
    
    app = Starlette(routes=[
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Route("/messages/", endpoint=handle_post_message, methods=["POST"]),
    ])
    
    print(f"🚀 MCP SSE 服务器启动于 http://{host}:{port}")
    print(f"   SSE 端点: http://{host}:{port}/sse")
    config = uvicorn.Config(app, host=host, port=port, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="MCP 服务器 - 支持 STDIO 和 SSE 模式")
    parser.add_argument("--sse", action="store_true", help="使用 SSE 模式（默认 STDIO 模式）")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 模式监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="SSE 模式监听端口（默认 8000）")
    args = parser.parse_args()
    
    if args.sse:
        asyncio.run(run_sse(args.host, args.port))
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()