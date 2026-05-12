"""MCP 服务器 - 支持 STDIO 和 SSE 两种模式

使用方法:
    # STDIO 模式（默认，用于 Claude Desktop 等本地客户端）
    python scripts/mcp_server.py
    
    # SSE 模式（用于远程连接，支持文件上传和 API Key 验证）
    python scripts/mcp_server.py --sse
    python scripts/mcp_server.py --sse --host 0.0.0.0 --port 8000
"""
import os
import sys
import argparse
import base64
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

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
from src.skills.db_checker import DBCheckerSkill
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
            """列出可用工具"""
            return [
                Tool(
                    name="analyze_document",
                    description="分析测试需求文档，提取测试要点和风险点",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "需求文本内容"},
                            "content_base64": {"type": "string", "description": "文档内容的base64编码"},
                            "filename": {"type": "string", "description": "文件名（用于判断格式）"},
                        },
                    },
                ),
                Tool(
                    name="generate_test_cases",
                    description="根据需求生成测试用例",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "需求描述"},
                            "content_base64": {"type": "string", "description": "文档内容的base64编码"},
                            "output_format": {"type": "string", "enum": ["excel", "json", "markdown"], "default": "excel"},
                        },
                    },
                ),
                Tool(
                    name="check_table",
                    description="检查游戏配置表（Excel/CSV）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "配置表文件路径"},
                            "content_base64": {"type": "string", "description": "配置表内容的base64编码"},
                            "rules": {"type": "array", "items": {"type": "string"}, "description": "要应用的检查规则"},
                        },
                    },
                ),
                Tool(
                    name="track_bug",
                    description="分析Bug并提供修复建议",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bug_description": {"type": "string", "description": "Bug描述"},
                            "screenshot_base64": {"type": "string", "description": "截图的base64编码（可选）"},
                            "context": {"type": "string", "description": "额外上下文信息（可选）"},
                        },
                        "required": ["bug_description"],
                    },
                ),
                Tool(
                    name="check_database",
                    description="检查数据库配置和数据一致性",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "connection_string": {"type": "string", "description": "数据库连接字符串"},
                            "checks": {"type": "array", "items": {"type": "string"}, "description": "要执行的检查类型"},
                        },
                        "required": ["connection_string"],
                    },
                ),
                Tool(
                    name="upload_file",
                    description="上传文件到服务器（用于后续分析）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "文件名"},
                            "content_base64": {"type": "string", "description": "文件内容的base64编码"},
                        },
                        "required": ["filename", "content_base64"],
                    },
                ),
                Tool(
                    name="echo",
                    description="回显输入内容，用于连通性测试",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "要回显的文本"},
                        },
                    },
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            """调用工具"""
            return await self._handle_tool_call(name, arguments)
    
    async def _handle_tool_call(self, name: str, arguments: dict) -> List[TextContent]:
        """处理工具调用"""
        # 延迟初始化 Agent（确保使用最新的 API Key）
        if self.agent is None:
            config = Config()
            # 如果用户提供了 API Key，覆盖配置
            if self.user_api_key:
                config.llm.api_key = self.user_api_key
            
            self.agent = GameTestAgent(config)
            # 注册所有技能（使用 register_skill_class 确保 config 正确传入）
            self.agent.register_skill_class("document_analyzer", DocumentAnalyzerSkill)
            self.agent.register_skill_class("test_case_generator", TestCaseGeneratorSkill)
            self.agent.register_skill_class("bug_tracker", BugTrackerSkill)
            self.agent.register_skill_class("table_checker", TableCheckerSkill)
            self.agent.register_skill_class("db_checker", DBCheckerSkill)
        
        try:
            if name == "analyze_document":
                text = arguments.get("text", "")
                content_base64 = arguments.get("content_base64", "")
                filename = arguments.get("filename", "document.txt")
                
                # 如果有base64内容，解码并保存
                if content_base64:
                    file_path = await self._save_uploaded_file(filename, content_base64)
                    # 读取文件内容
                    text = await self._read_file_content(file_path)
                
                if not text:
                    return [TextContent(type="text", text="错误：需要提供 text 或 content_base64")]
                
                result = await self.agent.execute("document_analyzer", {"text": text})
                if not result.success:
                    return [TextContent(type="text", text=f"分析失败: {result.error}")]
                return [TextContent(type="text", text=json.dumps(
                    result.data.to_dict() if hasattr(result.data, 'to_dict') else result.data,
                    ensure_ascii=False, indent=2))]
            
            elif name == "generate_test_cases":
                text = arguments.get("text", "")
                content_base64 = arguments.get("content_base64", "")
                output_format = arguments.get("output_format", "excel")
                
                params = {"output_format": output_format}
                if text:
                    params["text"] = text
                elif content_base64:
                    # 解码 base64 内容并作为文本传入
                    try:
                        decoded_text = base64.b64decode(content_base64).decode("utf-8")
                        params["text"] = decoded_text
                    except Exception as e:
                        return [TextContent(type="text", text=f"文件内容解码失败: {str(e)}")]
                else:
                    return [TextContent(type="text", text="错误：需要提供 text 或 content_base64")]
                
                result = await self.agent.execute("test_case_generator", params)
                if not result.success:
                    return [TextContent(type="text", text=f"生成用例失败: {result.error}")]
                return [TextContent(type="text", text=json.dumps(
                    result.data.to_dict() if hasattr(result.data, 'to_dict') else result.data,
                    ensure_ascii=False, indent=2))]
            
            elif name == "check_table":
                file_path = arguments.get("file_path", "")
                content_base64 = arguments.get("content_base64", "")
                rules = arguments.get("rules", [])
                
                if content_base64:
                    file_path = await self._save_uploaded_file("table.xlsx", content_base64)
                
                if not file_path:
                    return [TextContent(type="text", text="错误：需要提供 file_path 或 content_base64")]
                
                # 读取文件并解析为表格数据
                table_data = await self._read_file_as_table(file_path)
                if not table_data:
                    return [TextContent(type="text", text="错误：无法解析文件中的表格数据")]

                result = await self.agent.execute("table_checker", {
                    "data": table_data,
                    "rules": rules,
                })
                if not result.success:
                    return [TextContent(type="text", text=f"表检查失败: {result.error}")]
                return [TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False, indent=2))]
            
            elif name == "track_bug":
                bug_description = arguments.get("bug_description", "")
                screenshot_base64 = arguments.get("screenshot_base64", "")
                ctx = arguments.get("context", "")

                params = {
                    "title": bug_description[:100] if bug_description else "未知Bug",
                    "description": bug_description,
                }
                if isinstance(ctx, dict):
                    params["expected_result"] = ctx.get("expected_result", "")
                    params["actual_result"] = ctx.get("actual_result", "")
                if screenshot_base64:
                    screenshot_path = await self._save_uploaded_file("screenshot.png", screenshot_base64)
                    params["screenshot_path"] = str(screenshot_path)

                result = await self.agent.execute("bug_tracker", params)
                if not result.success:
                    return [TextContent(type="text", text=f"Bug分析失败: {result.error}")]
                return [TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False, indent=2))]
            
            elif name == "check_database":
                connection_string = arguments.get("connection_string", "")
                checks = arguments.get("checks", [])
                
                result = await self.agent.execute("db_checker", {
                    "connection_string": connection_string,
                    "checks": checks,
                })
                if not result.success:
                    return [TextContent(type="text", text=f"数据库检查失败: {result.error}")]
                return [TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False, indent=2))]
            
            elif name == "upload_file":
                filename = arguments.get("filename", "")
                content_base64 = arguments.get("content_base64", "")
                
                if not filename or not content_base64:
                    return [TextContent(type="text", text="错误：需要提供 filename 和 content_base64")]
                
                file_path = await self._save_uploaded_file(filename, content_base64)
                return [TextContent(type="text", text=f"文件上传成功: {file_path}")]

            elif name == "echo":
                text = arguments.get("text", "")
                return [TextContent(type="text", text=text)]

            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]
        
        except Exception as e:
            logger.error(f"工具调用失败: {e}", exc_info=True)
            return [TextContent(type="text", text=f"错误: {str(e)}")]
    
    async def _save_uploaded_file(self, filename: str, content_base64: str) -> Path:
        """保存上传的文件"""
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = UPLOAD_DIR / safe_filename
        
        # 解码并保存
        content = base64.b64decode(content_base64)
        with open(file_path, "wb") as f:
            f.write(content)
        
        return file_path
    
    async def _read_file_content(self, file_path: Path) -> str:
        """读取文件内容"""
        # 根据文件类型选择读取方式
        suffix = file_path.suffix.lower()
        
        if suffix == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        
        elif suffix in [".docx", ".doc"]:
            try:
                from docx import Document
                doc = Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])
            except Exception as e:
                return f"[文档解析失败: {e}]"
        
        elif suffix == ".pdf":
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                return "\n".join([page.extract_text() for page in reader.pages])
            except Exception as e:
                return f"[PDF解析失败: {e}]"
        
        elif suffix in [".xlsx", ".xls"]:
            try:
                import pandas as pd
                df = pd.read_excel(file_path)
                return df.to_string()
            except Exception as e:
                return f"[Excel解析失败: {e}]"
        
        elif suffix in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
            try:
                import pytesseract
                from PIL import Image
                img = Image.open(file_path)
                return pytesseract.image_to_string(img, lang='chi_sim+eng')
            except ImportError:
                return "[OCR功能未安装，请安装: pip install pytesseract Pillow]"
            except Exception as e:
                return f"[图片OCR失败: {str(e)}]"
        
        else:
            # 尝试作为文本读取
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except:
                return f"[不支持的文件格式: {suffix}]"

    async def _read_file_as_table(self, file_path: Path) -> list:
        """读取文件并解析为表格数据（行列表）"""
        suffix = file_path.suffix.lower()
        rows = []

        try:
            if suffix in [".xlsx", ".xls"]:
                import pandas as pd
                df = pd.read_excel(file_path)
                rows = df.to_dict(orient="records")
            elif suffix == ".csv":
                import pandas as pd
                df = pd.read_csv(file_path)
                rows = df.to_dict(orient="records")
            else:
                # 尝试作为文本解析
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]
                if lines:
                    # 假设第一行是表头，逗号或制表符分隔
                    delimiter = "\t" if "\t" in lines[0] else ","
                    headers = lines[0].split(delimiter)
                    for line in lines[1:]:
                        values = line.split(delimiter)
                        rows.append({headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))})
        except Exception as e:
            logger.error(f"表格解析失败: {e}")

        return rows

    async def run_stdio(self):
        """运行 STDIO 模式"""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )
    
    def run_sse(self, host: str = "0.0.0.0", port: int = 8000):
        """运行 SSE 模式（同步方法，内部处理异步）"""
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from starlette.responses import JSONResponse
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware
        from urllib.parse import parse_qs
        import uvicorn
        import json

        sse = SseServerTransport("/messages/")

        async def mcp_asgi(scope, receive, send):
            """统一的 MCP ASGI 入口，手动路由所有端点"""
            if scope["type"] != "http":
                return

            path = scope["path"]
            method = scope["method"]

            # 健康检查
            if path == "/health":
                response = JSONResponse({"status": "ok", "service": "testowl-mcp"})
                await response(scope, receive, send)
                return

            # API Key 验证
            if path == "/validate-key" and method == "POST":
                body = b""
                more_body = True
                while more_body:
                    msg = await receive()
                    body += msg.get("body", b"")
                    more_body = msg.get("more_body", False)
                try:
                    data = json.loads(body)
                    api_key = data.get("api_key", "")
                    if not api_key:
                        resp = JSONResponse({"valid": False, "error": "未提供 API Key"})
                    elif len(api_key) < 10:
                        resp = JSONResponse({"valid": False, "error": "API Key 格式不正确"})
                    else:
                        resp = JSONResponse({"valid": True, "message": "API Key 格式正确"})
                except Exception as e:
                    resp = JSONResponse({"valid": False, "error": str(e)})
                await resp(scope, receive, send)
                return

            # POST 消息
            if path.startswith("/messages") and method == "POST":
                await sse.handle_post_message(scope, receive, send)
                return

            # SSE 连接
            if path == "/sse":
                api_key = ""
                for name, value in scope.get("headers", []):
                    if name == b"x-api-key":
                        api_key = value.decode()
                        break
                if not api_key:
                    query = scope.get("query_string", b"").decode()
                    params = parse_qs(query)
                    api_key = params.get("api_key", [""])[0]
                if api_key:
                    self.user_api_key = api_key
                    logger.info("使用用户提供的 API Key")

                async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
                    await self.server.run(
                        read_stream,
                        write_stream,
                        self.server.create_initialization_options(),
                    )
                return

            # 404
            response = JSONResponse({"error": "Not found"}, status_code=404)
            await response(scope, receive, send)

        middleware = [
            Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
        ]

        routes = [
            Mount("/", app=mcp_asgi),
        ]

        app = Starlette(debug=True, routes=routes, middleware=middleware)
        
        print(f"🚀 MCP SSE 服务器启动于 http://{host}:{port}")
        print(f"   SSE 端点: http://{host}:{port}/sse")
        uvicorn.run(app, host=host, port=port)


# ==================== 启动入口 ====================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TestOwl MCP Server")
    parser.add_argument("--sse", action="store_true", help="使用 SSE 模式（默认 STDIO）")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 模式主机地址")
    parser.add_argument("--port", type=int, default=8000, help="SSE 模式端口")
    
    args = parser.parse_args()
    
    handler = MCPHandler()
    
    if args.sse:
        # SSE 模式：直接调用同步方法
        handler.run_sse(host=args.host, port=args.port)
    else:
        # STDIO 模式：使用 asyncio
        asyncio.run(handler.run_stdio())


if __name__ == "__main__":
    main()
