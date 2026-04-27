#!/usr/bin/env python3
"""
TestOwl MCP 服务器启动入口

这个文件是兼容层，实际逻辑已移至 scripts/mcp_server.py
保留此文件是为了兼容现有文档和习惯

使用方法:
    # STDIO 模式（默认，用于 Claude Desktop 等本地客户端）
    python mcp_server.py
    
    # SSE 模式（用于远程连接）
    python mcp_server.py --sse
    python mcp_server.py --sse --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path

# 转发到 scripts/mcp_server.py
if __name__ == "__main__":
    # 添加 scripts 目录到路径
    scripts_dir = Path(__file__).parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    
    # 导入并运行实际的 MCP 服务器
    from scripts.mcp_server import main
    main()