"""
Jira平台适配器

实现与Jira的API交互，支持Bug的提交、查询、更新等操作
"""

from typing import Any, Dict, List, Optional

from src.adapters.platform.base import (
    PlatformAdapter, 
    PlatformBug, 
    SubmitResult
)
from src.core.config import PlatformConfig
from src.core.exceptions import PlatformError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class JiraAdapter(PlatformAdapter):
    """
    Jira平台适配器
    
    使用示例：
        ```python
        config = PlatformConfig(
            name="jira",
            base_url="https://your-domain.atlassian.net",
            username="your-email@example.com",
            api_token="your-api-token",
            project_key="PROJ"
        )
        
        adapter = JiraAdapter(config)
        await adapter.connect()
        
        # 提交Bug
        result = await adapter.submit_bug(PlatformBug(
            title="登录失败",
            description="输入正确密码后无法登录",
            severity="high",
            priority="p1"
        ))
        ```
    """
    
    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.base_url = config.base_url.rstrip('/')
        self.username = config.username
        self.api_token = config.api_token or config.password
        self.project_key = config.project_key
    
    async def connect(self) -> bool:
        """
        初始化Jira客户端连接
        
        Returns:
            是否连接成功
        """
        try:
            from jira import JIRA
            
            # 创建Jira客户端
            self._client = JIRA(
                server=self.base_url,
                basic_auth=(self.username, self.api_token)
            )
            
            self._log_info("Jira客户端连接成功")
            return True
            
        except ImportError:
            raise PlatformError(
                "未安装jira库，请执行: pip install jira"
            )
        except Exception as e:
            self._log_error("Jira连接失败", e)
            return False
    
    async def test_connection(self) -> bool:
        """
        测试Jira连接是否正常
        
        Returns:
            连接是否正常
        """
        if not self._client:
            await self.connect()
        
        try:
            # 尝试获取当前用户信息
            user = self._client.current_user()
            self._log_info(f"连接测试成功，当前用户: {user}")
            return True
        except Exception as e:
            self._log_error("连接测试失败", e)
            return False
    
    async def submit_bug(self, bug: PlatformBug) -> SubmitResult:
        """
        提交Bug到Jira
        
        Args:
            bug: Bug数据
        
        Returns:
            提交结果
        """
        if not self._client:
            await self.connect()
        
        try:
            # 构建Issue数据
            issue_dict = {
                'project': {'key': self.project_key},
                'summary': bug.title,
                'description': bug.description,
                'issuetype': {'name': 'Bug'},  # Issue类型为Bug
            }
            
            # 设置优先级（Jira优先级字段映射）
            priority_map = {
                'p0': 'Highest',
                'p1': 'High', 
                'p2': 'Medium',
                'p3': 'Low'
            }
            if bug.priority.lower() in priority_map:
                issue_dict['priority'] = {'name': priority_map[bug.priority.lower()]}
            
            # 设置严重程度（如果有自定义字段）
            # 注意：严重程度字段在不同Jira实例中可能不同
            # 这里假设有一个名为"Severity"的自定义字段
            
            # 创建Issue
            new_issue = self._client.create_issue(fields=issue_dict)
            
            # 添加标签
            if bug.labels:
                labels = [{'name': label} for label in bug.labels]
                new_issue.update(fields={'labels': labels})
            
            # 添加附件
            if bug.attachments:
                for attachment_path in bug.attachments:
                    self._client.add_attachment(
                        issue=new_issue, 
                        attachment=attachment_path
                    )
            
            # 指派处理人
            if bug.assignee:
                new_issue.assign(bug.assignee)
            
            bug_url = f"{self.base_url}/browse/{new_issue.key}"
            
            self._log_info(f"Bug提交成功: {new_issue.key}")
            
            return SubmitResult(
                success=True,
                bug_id=new_issue.key,
                bug_url=bug_url,
                platform="jira"
            )
            
        except Exception as e:
            error_msg = str(e)
            self._log_error("Bug提交失败", e)
            
            return SubmitResult(
                success=False,
                error=error_msg,
                platform="jira"
            )
    
    async def get_bug(self, bug_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Jira Bug详情
        
        Args:
            bug_id: Issue Key（如 PROJ-123）
        
        Returns:
            Bug详情字典
        """
        if not self._client:
            await self.connect()
        
        try:
            issue = self._client.issue(bug_id)
            
            return {
                'id': issue.key,
                'title': issue.fields.summary,
                'description': issue.fields.description or '',
                'status': issue.fields.status.name,
                'priority': issue.fields.priority.name if issue.fields.priority else '',
                'assignee': issue.fields.assignee.displayName if issue.fields.assignee else '',
                'reporter': issue.fields.reporter.displayName if issue.fields.reporter else '',
                'created': str(issue.fields.created),
                'updated': str(issue.fields.updated),
                'url': f"{self.base_url}/browse/{issue.key}"
            }
            
        except Exception as e:
            self._log_error(f"获取Bug失败: {bug_id}", e)
            return None
    
    async def update_bug(self, bug_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新Jira Bug信息
        
        Args:
            bug_id: Issue Key
            updates: 要更新的字段
        
        Returns:
            是否更新成功
        """
        if not self._client:
            await self.connect()
        
        try:
            issue = self._client.issue(bug_id)
            issue.update(fields=updates)
            
            self._log_info(f"Bug更新成功: {bug_id}")
            return True
            
        except Exception as e:
            self._log_error(f"更新Bug失败: {bug_id}", e)
            return False
    
    async def search_bugs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Jira Bug
        
        Args:
            query: JQL查询语句或关键词
            limit: 返回数量限制
        
        Returns:
            Bug列表
        """
        if not self._client:
            await self.connect()
        
        try:
            # 如果不是JQL格式，构建简单的搜索条件
            if not any(keyword in query.upper() for keyword in ['SELECT', 'WHERE', 'AND', 'OR', '=']):
                query = f'text ~ "{query}" AND project = {self.project_key}'
            
            issues = self._client.search_issues(query, maxResults=limit)
            
            results = []
            for issue in issues:
                results.append({
                    'id': issue.key,
                    'title': issue.fields.summary,
                    'status': issue.fields.status.name,
                    'priority': issue.fields.priority.name if issue.fields.priority else '',
                    'url': f"{self.base_url}/browse/{issue.key}"
                })
            
            return results
            
        except Exception as e:
            self._log_error(f"搜索Bug失败", e)
            return []
