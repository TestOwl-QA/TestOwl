"""
禅道平台适配器

实现与禅道API的交互，支持Bug的提交、查询、更新等操作
"""

import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from src.adapters.platform.base import (
    PlatformAdapter, 
    PlatformBug, 
    SubmitResult
)
from src.core.config import PlatformConfig
from src.core.exceptions import PlatformError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ZentaoAdapter(PlatformAdapter):
    """
    禅道平台适配器
    
    禅道API文档：https://www.zentao.net/book/zentaopmshelp/562.html
    
    使用示例：
        ```python
        config = PlatformConfig(
            name="zentao",
            base_url="http://your-zentao.com",
            username="admin",
            password="your-password",
            project_key="1"  # 项目ID
        )
        
        adapter = ZentaoAdapter(config)
        await adapter.connect()
        
        # 提交Bug
        result = await adapter.submit_bug(PlatformBug(
            title="登录失败",
            description="输入正确密码后无法登录",
            severity="high"
        ))
        ```
    """
    
    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.username = config.username
        self.password = config.password
        self.project_id = config.project_key
        self._token = None
        self._session = httpx.AsyncClient(timeout=30.0)
    
    def _get_token(self) -> str:
        """
        获取禅道API Token
        
        Returns:
            Token字符串
        """
        # 禅道Token格式：账户+密码的MD5
        token_str = f"{self.username}{self.password}"
        return hashlib.md5(token_str.encode()).hexdigest()
    
    async def connect(self) -> bool:
        """
        连接到禅道并获取会话
        
        Returns:
            是否连接成功
        """
        try:
            # 获取Token
            self._token = self._get_token()
            
            # 获取会话ID
            url = urljoin(self.base_url, "/api.php?m=user&f=login")
            params = {
                'account': self.username,
                'password': self.password,
            }
            
            response = await self._session.get(url, params=params)
            data = response.json()
            
            if data.get('status') == 'success':
                self._log_info("禅道连接成功")
                return True
            else:
                self._log_error(f"禅道连接失败: {data.get('message', '未知错误')}")
                return False
                
        except Exception as e:
            self._log_error("禅道连接失败", e)
            return False
    
    async def test_connection(self) -> bool:
        """
        测试禅道连接是否正常
        
        Returns:
            连接是否正常
        """
        if not self._token:
            return await self.connect()
        return True
    
    async def submit_bug(self, bug: PlatformBug) -> SubmitResult:
        """
        提交Bug到禅道
        
        Args:
            bug: Bug数据
        
        Returns:
            提交结果
        """
        if not await self.test_connection():
            return SubmitResult(
                success=False,
                error="未连接到禅道服务器",
                platform="zentao"
            )
        
        try:
            # 严重程度映射
            severity_map = {
                'critical': '1',  # 致命
                'high': '2',      # 严重
                'medium': '3',    # 一般
                'low': '4',       # 轻微
            }
            
            # 优先级映射
            priority_map = {
                'p0': '1',  # 立即处理
                'p1': '2',  # 高
                'p2': '3',  # 中
                'p3': '4',  # 低
            }
            
            url = urljoin(self.base_url, "/api.php?m=bug&f=create")
            
            data = {
                'product': self.project_id,  # 产品ID
                'title': bug.title,
                'steps': bug.description,
                'severity': severity_map.get(bug.severity.lower(), '3'),
                'pri': priority_map.get(bug.priority.lower(), '3'),
            }
            
            # 添加指派人
            if bug.assignee:
                data['assignedTo'] = bug.assignee
            
            response = await self._session.post(url, data=data)
            result = response.json()
            
            if result.get('status') == 'success':
                bug_id = result.get('data', {}).get('id', '')
                bug_url = f"{self.base_url}/bug-view-{bug_id}.html"
                
                self._log_info(f"Bug提交成功: #{bug_id}")
                
                return SubmitResult(
                    success=True,
                    bug_id=str(bug_id),
                    bug_url=bug_url,
                    platform="zentao"
                )
            else:
                return SubmitResult(
                    success=False,
                    error=result.get('message', '提交失败'),
                    platform="zentao"
                )
                
        except Exception as e:
            error_msg = str(e)
            self._log_error("Bug提交失败", e)
            
            return SubmitResult(
                success=False,
                error=error_msg,
                platform="zentao"
            )
    
    async def get_bug(self, bug_id: str) -> Optional[Dict[str, Any]]:
        """
        获取禅道Bug详情
        
        Args:
            bug_id: Bug ID
        
        Returns:
            Bug详情字典
        """
        if not await self.test_connection():
            return None
        
        try:
            url = urljoin(self.base_url, f"/api.php?m=bug&f=view&id={bug_id}")
            
            response = await self._session.get(url)
            result = response.json()
            
            if result.get('status') == 'success':
                bug_data = result.get('data', {})
                return {
                    'id': str(bug_data.get('id', '')),
                    'title': bug_data.get('title', ''),
                    'description': bug_data.get('steps', ''),
                    'status': bug_data.get('status', ''),
                    'severity': bug_data.get('severity', ''),
                    'priority': bug_data.get('pri', ''),
                    'assignee': bug_data.get('assignedTo', ''),
                    'url': f"{self.base_url}/bug-view-{bug_id}.html"
                }
            
            return None
            
        except Exception as e:
            self._log_error(f"获取Bug失败: {bug_id}", e)
            return None
    
    async def update_bug(self, bug_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新禅道Bug信息
        
        Args:
            bug_id: Bug ID
            updates: 要更新的字段
        
        Returns:
            是否更新成功
        """
        if not await self.test_connection():
            return False
        
        try:
            url = urljoin(self.base_url, f"/api.php?m=bug&f=edit&id={bug_id}")
            
            response = await self._session.post(url, data=updates)
            result = response.json()
            
            if result.get('status') == 'success':
                self._log_info(f"Bug更新成功: #{bug_id}")
                return True
            
            return False
            
        except Exception as e:
            self._log_error(f"更新Bug失败: {bug_id}", e)
            return False
    
    async def search_bugs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索禅道Bug
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            Bug列表
        """
        if not await self.test_connection():
            return []
        
        try:
            url = urljoin(self.base_url, "/api.php?m=bug&f=search")
            params = {
                'query': query,
                'limit': limit
            }
            
            response = await self._session.get(url, params=params)
            result = response.json()
            
            if result.get('status') == 'success':
                bugs = result.get('data', [])
                return [
                    {
                        'id': str(bug.get('id', '')),
                        'title': bug.get('title', ''),
                        'status': bug.get('status', ''),
                        'url': f"{self.base_url}/bug-view-{bug.get('id')}.html"
                    }
                    for bug in bugs
                ]
            
            return []
            
        except Exception as e:
            self._log_error("搜索Bug失败", e)
            return []
    
    async def close(self):
        """关闭HTTP会话"""
        await self._session.aclose()
