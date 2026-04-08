""" MCP服务器入口 提供MCP协议支持，使Agent可以作为服务被调用 """
import os
import sys
from pathlib import Path

# API Key 从环境变量获取
os.environ["LLM_API_KEY"] = os.environ.get("LLM_API_KEY", "")

PROJECT_ROOT = Path(__file__).parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

import asyncio
from typing import Any, Dict, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from src.core.config import Config
from src.core.agent import GameTestAgent
from src.skills.document_analyzer import DocumentAnalyzerSkill
from src.skills.test_case_generator import TestCaseGeneratorSkill
from src.skills.bug_tracker import BugTrackerSkill
from src.skills.table_checker import TableCheckerSkill
from src.utils.logger import get_logger

logger = get_logger(__name__)
app = Server("testowl")
agent: GameTestAgent = None

@app.list_tools()
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

@app.call_tool()
async def call_tool(name: str, arguments: dict):
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

async def run():
    global agent
    config = Config(str(CONFIG_PATH))
    agent = GameTestAgent(config)
    agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
    agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
    agent.register_skill("bug_tracker", BugTrackerSkill(config))
    agent.register_skill("table_checker", TableCheckerSkill(config))
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(run())
