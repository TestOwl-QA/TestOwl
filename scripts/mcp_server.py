"""MCP 服务器 - 支持 STDIO 和 SSE 两种模式
黑盒测试核心工具：需求分析 / Bug分析 / 配置表检查 / 数据库检查

使用方法:
    python scripts/mcp_server.py                  # STDIO 模式
    python scripts/mcp_server.py --sse            # SSE 模式
    python scripts/mcp_server.py --sse --host 0.0.0.0 --port 8000
"""
import os
import sys
import argparse
import base64
import asyncio
import json
import subprocess
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
from src.skills.bug_tracker import BugTrackerSkill
from src.skills.table_checker import TableCheckerSkill
from src.skills.db_checker import DBCheckerSkill
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MCPHandler:
    """MCP 请求处理器 — 4 个黑盒测试核心工具"""

    def __init__(self):
        self.agent: GameTestAgent = None
        self.server = Server("testowl")
        self.user_api_key: Optional[str] = None
        self._setup_tools()

    def _setup_tools(self):
        """设置 MCP 工具（4个黑盒测试核心工具）"""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="analyze_document",
                    description="分析需求文档，提取测试要点、风险点和待确认问题",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "需求文档/策划案文本，支持直接粘贴",
                            },
                            "focus_areas": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "重点关注领域（如：功能、性能、安全）",
                            },
                        },
                        "required": ["text"],
                    },
                ),
                Tool(
                    name="analyze_bug",
                    description="分析Bug描述，自动提取复现步骤、分析根因、给出修复建议",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Bug 描述",
                            },
                            "expected": {
                                "type": "string",
                                "description": "期望行为（可选）",
                            },
                            "actual": {
                                "type": "string",
                                "description": "实际行为（可选）",
                            },
                        },
                        "required": ["description"],
                    },
                ),
                Tool(
                    name="check_table",
                    description="检查游戏配置表（Excel/CSV），支持物品/技能/关卡/商城预设规则",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content_base64": {
                                "type": "string",
                                "description": "Excel/CSV 文件的 base64 编码",
                            },
                            "filename": {
                                "type": "string",
                                "description": "文件名（用于判断格式 .xlsx/.csv）",
                            },
                            "preset": {
                                "type": "string",
                                "enum": ["generic", "item", "skill", "level", "shop"],
                                "default": "generic",
                                "description": "预设规则集",
                            },
                            "custom_rules": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "自定义规则（可选）",
                            },
                        },
                        "required": ["content_base64", "filename"],
                    },
                ),
                Tool(
                    name="check_database",
                    description="检查数据库结构、数据一致性和业务规则",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "connection_string": {
                                "type": "string",
                                "description": "数据库连接字符串，如 mysql://user:pass@host:3306/db",
                            },
                            "checks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "检查类型：connection/structure/data/rules",
                            },
                        },
                        "required": ["connection_string"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            return await self._handle_tool_call(name, arguments)

    async def _handle_tool_call(self, name: str, arguments: dict) -> List[TextContent]:
        """统一工具路由"""
        if self.agent is None:
            self._init_agent()

        try:
            if name == "analyze_document":
                return await self._tool_analyze_document(arguments)
            elif name == "analyze_bug":
                return await self._tool_analyze_bug(arguments)
            elif name == "check_table":
                return await self._tool_check_table(arguments)
            elif name == "check_database":
                return await self._tool_check_database(arguments)
            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]
        except Exception as e:
            logger.error(f"工具调用失败 [{name}]: {e}", exc_info=True)
            return [TextContent(type="text", text=f"错误: {str(e)}")]

    def _init_agent(self):
        """延迟初始化 Agent"""
        config = Config()
        if self.user_api_key:
            config.llm.api_key = self.user_api_key
        self.agent = GameTestAgent(config)
        self.agent.register_skill_class("document_analyzer", DocumentAnalyzerSkill)
        self.agent.register_skill_class("bug_tracker", BugTrackerSkill)
        self.agent.register_skill_class("table_checker", TableCheckerSkill)
        self.agent.register_skill_class("db_checker", DBCheckerSkill)

    # ── 需求文档分析 ─────────────────────────────────────────

    async def _tool_analyze_document(self, args: dict) -> List[TextContent]:
        text = args.get("text", "").strip()
        focus_areas = args.get("focus_areas", [])

        if not text:
            return [TextContent(type="text", text="错误：请提供需求文档文本")]

        result = await self.agent.execute("document_analyzer", {
            "content": text,
            "focus_areas": focus_areas,
        })
        if not result.success:
            return [TextContent(type="text", text=f"文档分析失败: {result.error}")]

        data = result.data.to_dict() if hasattr(result.data, "to_dict") else result.data
        return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

    # ── Bug 分析 ─────────────────────────────────────────────

    async def _tool_analyze_bug(self, args: dict) -> List[TextContent]:
        description = args.get("description", "").strip()
        expected = args.get("expected", "").strip()
        actual = args.get("actual", "").strip()

        if not description:
            return [TextContent(type="text", text="错误：请提供 Bug 描述")]

        params = {
            "title": description[:100],
            "description": description,
        }
        if expected:
            params["expected_result"] = expected
        if actual:
            params["actual_result"] = actual

        result = await self.agent.execute("bug_tracker", params)
        if not result.success:
            return [TextContent(type="text", text=f"Bug 分析失败: {result.error}")]
        return [TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False, indent=2))]

    # ── 配置表检查 ───────────────────────────────────────────

    async def _tool_check_table(self, args: dict) -> List[TextContent]:
        content_base64 = args.get("content_base64", "")
        filename = args.get("filename", "table.xlsx")
        preset = args.get("preset", "generic")
        custom_rules = args.get("custom_rules", [])

        if not content_base64:
            return [TextContent(type="text", text="错误：请提供配置表文件的 base64 编码")]

        file_path = await self._save_uploaded_file(filename, content_base64)
        table_data = await self._read_file_as_table(str(file_path))
        if not table_data:
            return [TextContent(type="text", text="错误：无法解析表格数据，请确认文件为 Excel 或 CSV 格式")]

        rules = self._get_table_rules(preset) + list(custom_rules)
        if not rules:
            rules = self._get_table_rules("generic")

        result = await self.agent.execute("table_checker", {
            "data": table_data,
            "rules": rules,
        })
        if not result.success:
            return [TextContent(type="text", text=f"表检查失败: {result.error}")]
        return [TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False, indent=2))]

    # ── 数据库检查 ───────────────────────────────────────────

    async def _tool_check_database(self, args: dict) -> List[TextContent]:
        connection_string = args.get("connection_string", "")
        checks = args.get("checks", [])

        if not connection_string:
            return [TextContent(type="text", text="错误：请提供数据库连接字符串")]

        result = await self.agent.execute("db_checker", {
            "connection_string": connection_string,
            "checks": checks,
        })
        if not result.success:
            return [TextContent(type="text", text=f"数据库检查失败: {result.error}")]
        return [TextContent(type="text", text=json.dumps(result.data, ensure_ascii=False, indent=2))]

    # ── 配置表预设规则 ─────────────────────────────────────────

    def _get_table_rules(self, preset: str) -> list:
        """获取预设检查规则"""
        rules = []

        if preset == "item":
            rules = [
                {"name": "物品ID唯一性", "rule_type": "unique", "column": "item_id", "severity": "error"},
                {"name": "物品名称非空", "rule_type": "not_null", "column": "item_name", "severity": "error"},
                {"name": "价格非负", "rule_type": "range", "column": "price", "params": {"min": 0}, "severity": "error"},
                {"name": "稀有度枚举", "rule_type": "enum", "column": "rarity", "params": {"values": ["N", "R", "SR", "SSR", "UR"]}, "severity": "warning"},
                {"name": "类型引用", "rule_type": "reference", "column": "type_id", "params": {"reference_table": "item_type"}, "severity": "error"},
            ]
        elif preset == "skill":
            rules = [
                {"name": "技能ID唯一性", "rule_type": "unique", "column": "skill_id", "severity": "error"},
                {"name": "技能名称非空", "rule_type": "not_null", "column": "skill_name", "severity": "error"},
                {"name": "冷却时间非负", "rule_type": "range", "column": "cooldown", "params": {"min": 0}, "severity": "warning"},
                {"name": "技能等级范围", "rule_type": "range", "column": "level", "params": {"min": 1, "max": 100}, "severity": "warning"},
            ]
        elif preset == "level":
            rules = [
                {"name": "关卡ID唯一性", "rule_type": "unique", "column": "level_id", "severity": "error"},
                {"name": "关卡名称非空", "rule_type": "not_null", "column": "level_name", "severity": "error"},
                {"name": "解锁等级合理", "rule_type": "range", "column": "unlock_level", "params": {"min": 1, "max": 100}, "severity": "warning"},
                {"name": "星级枚举", "rule_type": "enum", "column": "stars", "params": {"values": [1, 2, 3]}, "severity": "warning"},
            ]
        elif preset == "shop":
            rules = [
                {"name": "商品ID唯一性", "rule_type": "unique", "column": "goods_id", "severity": "error"},
                {"name": "商品名称非空", "rule_type": "not_null", "column": "goods_name", "severity": "error"},
                {"name": "货币类型枚举", "rule_type": "enum", "column": "currency", "params": {"values": ["gold", "diamond", "rmb"]}, "severity": "error"},
                {"name": "价格非负", "rule_type": "range", "column": "price", "params": {"min": 0}, "severity": "error"},
                {"name": "库存非负", "rule_type": "range", "column": "stock", "params": {"min": 0}, "severity": "warning"},
            ]
        return rules

    # ── 文件处理 ───────────────────────────────────────────────

    async def _save_uploaded_file(self, filename: str, content_base64: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = UPLOAD_DIR / safe_filename
        content = base64.b64decode(content_base64)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    async def _read_file_as_table(self, file_path: str) -> list:
        """读取文件并解析为表格数据"""
        path = Path(file_path)
        suffix = path.suffix.lower()
        rows = []

        try:
            if suffix in [".xlsx", ".xls"]:
                import pandas as pd
                df = pd.read_excel(path)
                rows = df.to_dict(orient="records")
            elif suffix == ".csv":
                import pandas as pd
                df = pd.read_csv(path)
                rows = df.to_dict(orient="records")
            else:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]
                if lines:
                    delimiter = "	" if "	" in lines[0] else ","
                    headers = [h.strip() for h in lines[0].split(delimiter)]
                    for line in lines[1:]:
                        values = [v.strip() for v in line.split(delimiter)]
                        rows.append({headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))})
        except Exception as e:
            logger.error(f"表格解析失败: {e}")

        return rows

    # ── 服务器启动 ─────────────────────────────────────────────

    async def run_stdio(self):
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream,
                self.server.create_initialization_options(),
            )

    def run_sse(self, host: str = "0.0.0.0", port: int = 8000):
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from starlette.responses import JSONResponse
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware
        from urllib.parse import parse_qs
        import uvicorn

        sse = SseServerTransport("/messages/")

        async def mcp_asgi(scope, receive, send):
            if scope["type"] != "http":
                return

            path = scope["path"]
            method = scope["method"]

            if path == "/health":
                response = JSONResponse({"status": "ok", "service": "testowl-mcp"})
                await response(scope, receive, send)
                return

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

            if path.startswith("/messages") and method == "POST":
                await sse.handle_post_message(scope, receive, send)
                return

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
                        read_stream, write_stream,
                        self.server.create_initialization_options(),
                    )
                return

            response = JSONResponse({"error": "Not found"}, status_code=404)
            await response(scope, receive, send)

        middleware = [
            Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
        ]
        routes = [Mount("/", app=mcp_asgi)]
        app = Starlette(debug=True, routes=routes, middleware=middleware)

        print(f"TestOwl MCP SSE: http://{host}:{port}")
        print(f"   SSE: http://{host}:{port}/sse")
        print(f"   Health: http://{host}:{port}/health")
        uvicorn.run(app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="TestOwl MCP Server - 黑盒测试核心工具")
    parser.add_argument("--sse", action="store_true", help="SSE 模式")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 主机地址")
    parser.add_argument("--port", type=int, default=8000, help="SSE 端口")
    args = parser.parse_args()

    handler = MCPHandler()
    if args.sse:
        handler.run_sse(host=args.host, port=args.port)
    else:
        asyncio.run(handler.run_stdio())


if __name__ == "__main__":
    main()
