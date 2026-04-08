"""
Redmine平台适配器

实现与Redmine API的交互，支持Bug的提交、查询、更新等操作
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from src.adapters.platform.base import (
    PlatformAdapter, 
    PlatformBug, 
    SubmitResult
)
from src.core.config import PlatformConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RedmineAdapter(PlatformAdapter):
    """
    Redmine平台适配器
    
    Redmine API文档：https://www.redmine.org/projects/redmine/wiki/Rest_api
    
    使用示例：
        ```python
        config = PlatformConfig(
            name="redmine",
            base_url="http://your-redmine.com",
            api_token="your-api-key",
            project_key="your-project-identifier"
        )
        
        adapter = RedmineAdapter(config)
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
        self.api_key = config.api_token
        self.project_id = config.project_key
        self._session = httpx.AsyncClient(timeout=30.0)
    
    def _get_headers(self) -> Dict[str, str]:
        """
        获取API请求头
        
        Returns:
            请求头字典
        """
        return {
            'X-Redmine-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    async def connect(self) -> bool:
        """
        连接到Redmine并验证凭证
        
        Returns:
            是否连接成功
        """
        try:
            # 验证凭证：获取当前用户信息
            url = urljoin(self.base_url, "/users/current.json")
            
            response = await self._session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                user = data.get('user', {})
                self._log_info(f"Redmine连接成功，用户: {user.get('login', 'unknown')}")
                return True
            else:
                self._log_error(f"Redmine连接失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self._log_error("Redmine连接失败", e)
            return False
    
    async def test_connection(self) -> bool:
        """
        测试Redmine连接是否正常
        
        Returns:
            连接是否正常
        """
        return await self.connect()
    
    async def submit_bug(self, bug: PlatformBug) -> SubmitResult:
        """
        提交Bug到Redmine
        
        Args:
            bug: Bug数据
        
        Returns:
            提交结果
        """
        try:
            url = urljoin(self.base_url, "/issues.json")
            
            # Redmine的Issue数据结构
            issue_data = {
                'project_id': self.project_id,
                'subject': bug.title,
                'description': bug.description,
                'tracker_id': 1,  # 默认为Bug类型（tracker_id需要根据实际配置调整）
            }
            
            # 严重程度映射到优先级
            priority_map = {
                'critical': 5,   # 最高
                'high': 4,       # 高
                'medium': 3,     # 普通
                'low': 2,        # 低
            }
            if bug.severity.lower() in priority_map:
                issue_data['priority_id'] = priority_map[bug.severity.lower()]
            
            # 指派人（需要用户ID）
            if bug.assignee:
                # 如果是数字，当作用户ID
                if bug.assignee.isdigit():
                    issue_data['assigned_to_id'] = int(bug.assignee)
            
            data = {'issue': issue_data}
            
            response = await self._session.post(
                url, 
                headers=self._get_headers(), 
                json=data
            )
            
            if response.status_code == 201:
                result = response.json()
                issue = result.get('issue', {})
                bug_id = issue.get('id', '')
                bug_url = f"{self.base_url}/issues/{bug_id}"
                
                self._log_info(f"Bug提交成功: #{bug_id}")
                
                return SubmitResult(
                    success=True,
                    bug_id=str(bug_id),
                    bug_url=bug_url,
                    platform="redmine"
                )
            else:
                error_info = response.json().get('errors', ['未知错误'])
                return SubmitResult(
                    success=False,
                    error=str(error_info),
                    platform="redmine"
                )
                
        except Exception as e:
            error_msg = str(e)
            self._log_error("Bug提交失败", e)
            
            return SubmitResult(
                success=False,
                error=error_msg,
                platform="redmine"
            )
    
    async def get_bug(self, bug_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Redmine Bug详情
        
        Args:
            bug_id: Issue ID
        
        Returns:
            Bug详情字典
        """
        try:
            url = urljoin(self.base_url, f"/issues/{bug_id}.json")
            
            response = await self._session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                data = response.json()
                issue = data.get('issue', {})
                
                return {
                    'id': str(issue.get('id', '')),
                    'title': issue.get('subject', ''),
                    'description': issue.get('description', ''),
                    'status': issue.get('status', {}).get('name', ''),
                    'priority': issue.get('priority', {}).get('name', ''),
                    'assignee': issue.get('assigned_to', {}).get('name', '') if issue.get('assigned_to') else '',
                    'author': issue.get('author', {}).get('name', ''),
                    'created': issue.get('created_on', ''),
                    'updated': issue.get('updated_on', ''),
                    'url': f"{self.base_url}/issues/{bug_id}"
                }
            
            return None
            
        except Exception as e:
            self._log_error(f"获取Bug失败: {bug_id}", e)
            return None
    
    async def update_bug(self, bug_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新Redmine Bug信息
        
        Args:
            bug_id: Issue ID
            updates: 要更新的字段
        
        Returns:
            是否更新成功
        """
        try:
            url = urljoin(self.base_url, f"/issues/{bug_id}.json")
            
            data = {'issue': updates}
            
            response = await self._session.put(
                url, 
                headers=self._get_headers(), 
                json=data
            )
            
            if response.status_code == 204:
                self._log_info(f"Bug更新成功: #{bug_id}")
                return True
            
            return False
            
        except Exception as e:
            self._log_error(f"更新Bug失败: {bug_id}", e)
            return False
    
    async def search_bugs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Redmine Bug
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            Bug列表
        """
        try:
            url = urljoin(self.base_url, "/issues.json")
            
            params = {
                'project_id': self.project_id,
                'subject': f"~{query}~",  # 模糊搜索
                'limit': limit
            }
            
            response = await self._session.get(
                url, 
                headers=self._get_headers(),
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                
                return [
                    {
                        'id': str(issue.get('id', '')),
                        'title': issue.get('subject', ''),
                        'status': issue.get('status', {}).get('name', ''),
                        'url': f"{self.base_url}/issues/{issue.get('id')}"
                    }
                    for issue in issues
                ]
            
            return []
            
        except Exception as e:
            self._log_error("搜索Bug失败", e)
            return []
    
    async def close(self):
        """关闭HTTP会话"""
        await self._session.aclose()
