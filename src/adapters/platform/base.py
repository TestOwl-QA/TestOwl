"""
项目管理平台适配器基类

定义所有平台适配器的通用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

from src.core.config import PlatformConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BugStatus(Enum):
    """Bug状态枚举"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


@dataclass
class PlatformBug:
    """
    平台通用的Bug数据结构
    
    用于在不同平台之间统一Bug数据格式
    """
    title: str                           # 标题
    description: str                     # 描述
    severity: str = "medium"             # 严重程度：critical/high/medium/low
    priority: str = "p2"                 # 优先级：p0/p1/p2/p3
    assignee: str = ""                   # 指派人
    labels: List[str] = None             # 标签
    attachments: List[str] = None        # 附件路径
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = []
        if self.attachments is None:
            self.attachments = []


@dataclass
class SubmitResult:
    """
    Bug提交结果
    """
    success: bool                        # 是否成功
    bug_id: str = ""                     # 平台返回的Bug ID
    bug_url: str = ""                    # Bug详情页URL
    error: str = ""                      # 错误信息
    platform: str = ""                   # 平台名称


class PlatformAdapter(ABC):
    """
    项目管理平台适配器基类
    
    所有平台适配器（Jira、禅道、Tapd、Redmine）都需要继承此类
    
    使用示例：
        ```python
        # 初始化适配器
        adapter = JiraAdapter(platform_config)
        
        # 连接测试
        is_connected = await adapter.test_connection()
        
        # 提交Bug
        result = await adapter.submit_bug(platform_bug)
        ```
    """
    
    def __init__(self, config: PlatformConfig):
        """
        初始化平台适配器
        
        Args:
            config: 平台配置对象
        """
        self.config = config
        self.platform_name = config.name
        self._client = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        连接到平台
        
        Returns:
            是否连接成功
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        测试连接是否正常
        
        Returns:
            连接是否正常
        """
        pass
    
    @abstractmethod
    async def submit_bug(self, bug: PlatformBug) -> SubmitResult:
        """
        提交Bug到平台
        
        Args:
            bug: Bug数据
        
        Returns:
            提交结果
        """
        pass
    
    @abstractmethod
    async def get_bug(self, bug_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Bug详情
        
        Args:
            bug_id: Bug ID
        
        Returns:
            Bug详情字典，不存在则返回None
        """
        pass
    
    @abstractmethod
    async def update_bug(self, bug_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新Bug信息
        
        Args:
            bug_id: Bug ID
            updates: 要更新的字段
        
        Returns:
            是否更新成功
        """
        pass
    
    @abstractmethod
    async def search_bugs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Bug
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            Bug列表
        """
        pass
    
    def _log_error(self, message: str, error: Exception = None):
        """
        记录错误日志
        
        Args:
            message: 错误消息
            error: 异常对象
        """
        if error:
            logger.error(f"[{self.platform_name}] {message}: {str(error)}")
        else:
            logger.error(f"[{self.platform_name}] {message}")
    
    def _log_info(self, message: str):
        """
        记录信息日志
        
        Args:
            message: 信息消息
        """
        logger.info(f"[{self.platform_name}] {message}")
