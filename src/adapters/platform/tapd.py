"""
Tapd平台适配器

实现与Tapd API的交互，支持Bug的提交、查询、更新等操作
"""

import base64
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from datetime import datetime

import httpx

from src.adapters.platform.base import (
    PlatformAdapter, 
    PlatformBug, 
    SubmitResult
)
from src.core.config import PlatformConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TapdAdapter(PlatformAdapter):
    """
    Tapd平台适配器
    
    Tapd API文档：https://www.tapd.cn/help/view#1120003271001001347
    
    使用示例：
        ```python
        config = PlatformConfig(
            name="tapd",
            base_url="https://api.tapd.cn",
            username="your-api-user",
            password="your-api-password",
            project_key="your-workspace-id"
        )
        
        adapter = TapdAdapter(config)
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
        self.base_url = "https://api.tapd.cn"  # Tapd API固定地址
        self.api_user = config.username  # API User
        self.api_password = config.password  # API Password
        self.workspace_id = config.project_key  # 工作空间ID
        self._session = httpx.AsyncClient(timeout=30.0)
    
    def _get_auth_header(self) -> str:
        """
        生成Basic认证头
        
        Returns:
            Authorization header值
        """
        credentials = f"{self.api_user}:{self.api_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    async def connect(self) -> bool:
        """
        连接到Tapd并验证凭证
        
        Returns:
            是否连接成功
        """
        try:
            # 验证凭证有效性：获取工作空间信息
            url = f"{self.base_url}/workspaces/get_workspace_info"
            
            headers = {
                'Authorization': self._get_auth_header(),
                'Content-Type': 'application/json'
            }
            
            params = {
                'workspace_id': self.workspace_id
            }
            
            response = await self._session.get(url, headers=headers, params=params)
            data = response.json()
            
            if data.get('status') == 1:
                self._log_info("Tapd连接成功")
                return True
            else:
                self._log_error(f"Tapd连接失败: {data.get('info', '未知错误')}")
                return False
                
        except Exception as e:
            self._log_error("Tapd连接失败", e)
            return False
    
    async def test_connection(self) -> bool:
        """
        测试Tapd连接是否正常
        
        Returns:
            连接是否正常
        """
        return await self.connect()
    
    async def submit_bug(self, bug: PlatformBug) -> SubmitResult:
        """
        提交Bug到Tapd
        
        Args:
            bug: Bug数据
        
        Returns:
            提交结果
        """
        try:
            url = f"{self.base_url}/bugs"
            
            headers = {
                'Authorization': self._get_auth_header(),
                'Content-Type': 'application/json'
            }
            
            # 严重程度映射
            severity_map = {
                'critical': 'fatal',     # 致命
                'high': 'serious',       # 严重
                'medium': 'normal',      # 一般
                'low': 'prompt',         # 提示
            }
            
            # 优先级映射
            priority_map = {
                'p0': 'urgent',    # 紧急
                'p1': 'high',      # 高
                'p2': 'medium',    # 中
                'p3': 'low',       # 低
            }
            
            data = {
                'workspace_id': self.workspace_id,
                'title': bug.title,
                'description': bug.description,
                'severity': severity_map.get(bug.severity.lower(), 'normal'),
                'priority': priority_map.get(bug.priority.lower(), 'medium'),
                'category': 'code_error',  # 默认代码错误
            }
            
            # 添加指派人
            if bug.assignee:
                data['current_owner'] = bug.assignee
            
            # 添加标签
            if bug.labels:
                data['custom_field_one'] = ','.join(bug.labels)  # 使用自定义字段存储标签
            
            response = await self._session.post(url, headers=headers, json=data)
            result = response.json()
            
            if result.get('status') == 1:
                bug_data = result.get('data', {})
                bug_id = bug_data.get('id', '')
                bug_url = f"https://www.tapd.cn/bugtrace/bugs/view?id={bug_id}&workspace_id={self.workspace_id}"
                
                self._log_info(f"Bug提交成功: {bug_id}")
                
                return SubmitResult(
                    success=True,
                    bug_id=str(bug_id),
                    bug_url=bug_url,
                    platform="tapd"
                )
            else:
                return SubmitResult(
                    success=False,
                    error=result.get('info', '提交失败'),
                    platform="tapd"
                )
                
        except Exception as e:
            error_msg = str(e)
            self._log_error("Bug提交失败", e)
            
            return SubmitResult(
                success=False,
                error=error_msg,
                platform="tapd"
            )
    
    async def get_bug(self, bug_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Tapd Bug详情
        
        Args:
            bug_id: Bug ID
        
        Returns:
            Bug详情字典
        """
        try:
            url = f"{self.base_url}/bugs"
            
            headers = {
                'Authorization': self._get_auth_header(),
            }
            
            params = {
                'workspace_id': self.workspace_id,
                'id': bug_id
            }
            
            response = await self._session.get(url, headers=headers, params=params)
            result = response.json()
            
            if result.get('status') == 1:
                bugs = result.get('data', [])
                if bugs:
                    bug_data = bugs[0]
                    return {
                        'id': str(bug_data.get('id', '')),
                        'title': bug_data.get('title', ''),
                        'description': bug_data.get('description', ''),
                        'status': bug_data.get('status', ''),
                        'severity': bug_data.get('severity', ''),
                        'priority': bug_data.get('priority', ''),
                        'assignee': bug_data.get('current_owner', ''),
                        'created': bug_data.get('created', ''),
                        'url': f"https://www.tapd.cn/bugtrace/bugs/view?id={bug_id}&workspace_id={self.workspace_id}"
                    }
            
            return None
            
        except Exception as e:
            self._log_error(f"获取Bug失败: {bug_id}", e)
            return None
    
    async def update_bug(self, bug_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新Tapd Bug信息
        
        Args:
            bug_id: Bug ID
            updates: 要更新的字段
        
        Returns:
            是否更新成功
        """
        try:
            url = f"{self.base_url}/bugs"
            
            headers = {
                'Authorization': self._get_auth_header(),
                'Content-Type': 'application/json'
            }
            
            data = {
                'id': bug_id,
                'workspace_id': self.workspace_id,
                **updates
            }
            
            response = await self._session.post(url, headers=headers, json=data)
            result = response.json()
            
            if result.get('status') == 1:
                self._log_info(f"Bug更新成功: {bug_id}")
                return True
            
            return False
            
        except Exception as e:
            self._log_error(f"更新Bug失败: {bug_id}", e)
            return False
    
    async def search_bugs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Tapd Bug
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            Bug列表
        """
        try:
            url = f"{self.base_url}/bugs"
            
            headers = {
                'Authorization': self._get_auth_header(),
            }
            
            params = {
                'workspace_id': self.workspace_id,
                'title': query,  # 标题搜索
                'limit': limit
            }
            
            response = await self._session.get(url, headers=headers, params=params)
            result = response.json()
            
            if result.get('status') == 1:
                bugs = result.get('data', [])
                return [
                    {
                        'id': str(bug.get('id', '')),
                        'title': bug.get('title', ''),
                        'status': bug.get('status', ''),
                        'url': f"https://www.tapd.cn/bugtrace/bugs/view?id={bug.get('id')}&workspace_id={self.workspace_id}"
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
