""" 日志工具（带敏感信息脱敏） """
import re
from pathlib import Path
from loguru import logger as _logger

# 敏感信息匹配模式
SENSITIVE_PATTERNS = [
    (r'sk-[A-Za-z0-9]{20,}', 'sk-***REDACTED***'),  # OpenAI/Kimi API Key
    (r'Bearer\s+[A-Za-z0-9_-]{20,}', 'Bearer ***'),  # Bearer Token
    (r'password[=:]\s*\S+', 'password=***'),  # 密码
    (r'token[=:]\s*[A-Za-z0-9_-]{10,}', 'token=***'),  # Token
    (r'secret[=:]\s*\S+', 'secret=***'),  # Secret
]

def sanitize(message: str) -> str:
    """脱敏敏感信息"""
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = re.sub(pattern, replacement, str(message), flags=re.IGNORECASE)
    return message

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
