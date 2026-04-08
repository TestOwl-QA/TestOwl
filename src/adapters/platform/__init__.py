"""
项目管理平台适配器模块

提供与各项目管理平台（Jira、禅道、Tapd、Redmine）的集成能力
"""

from src.adapters.platform.base import (
    PlatformAdapter,
    PlatformBug,
    SubmitResult,
    BugStatus,
)
from src.adapters.platform.jira import JiraAdapter
from src.adapters.platform.zentao import ZentaoAdapter
from src.adapters.platform.tapd import TapdAdapter
from src.adapters.platform.redmine import RedmineAdapter

# 平台名称到适配器类的映射
PLATFORM_ADAPTERS = {
    'jira': JiraAdapter,
    'zentao': ZentaoAdapter,
    'tapd': TapdAdapter,
    'redmine': RedmineAdapter,
}


def get_platform_adapter(platform_name: str, config) -> PlatformAdapter:
    """
    获取平台适配器实例
    
    Args:
        platform_name: 平台名称（jira/zentao/tapd/redmine）
        config: 平台配置对象
    
    Returns:
        平台适配器实例
    
    Raises:
        ValueError: 不支持的平台名称
    """
    platform_name = platform_name.lower()
    
    if platform_name not in PLATFORM_ADAPTERS:
        raise ValueError(
            f"不支持的平台: {platform_name}。"
            f"支持的平台: {list(PLATFORM_ADAPTERS.keys())}"
        )
    
    adapter_class = PLATFORM_ADAPTERS[platform_name]
    return adapter_class(config)


__all__ = [
    'PlatformAdapter',
    'PlatformBug',
    'SubmitResult',
    'BugStatus',
    'JiraAdapter',
    'ZentaoAdapter',
    'TapdAdapter',
    'RedmineAdapter',
    'get_platform_adapter',
    'PLATFORM_ADAPTERS',
]
