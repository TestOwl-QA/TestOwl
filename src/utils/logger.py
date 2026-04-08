"""
日志工具
"""

import sys
from pathlib import Path
from loguru import logger as _logger

# 移除默认处理器
_logger.remove()

# 只写文件，不输出到控制台
log_path = Path("./logs")
log_path.mkdir(exist_ok=True)

_logger.add(
    log_path / "game_test_agent_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    encoding="utf-8",
)


def get_logger(name: str):
    return _logger.bind(name=name)