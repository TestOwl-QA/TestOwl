"""
Bug追踪技能

功能：
1. 分析Bug报告，提供根因分析
2. 支持多平台Bug提交（Jira、禅道、Redmine、Tapd）
3. Bug智能分类和优先级建议
"""

import json
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.skills.bug_tracker.models import BugReport, BugAnalysis, BugSeverity, BugPriority
from src.adapters.llm.client import LLMClient
from src.adapters.platform import (
    PlatformBug, 
    get_platform_adapter
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BugTrackerSkill(BaseSkill):
    """
    Bug追踪技能
    
    使用示例：
        ```python
        skill = BugTrackerSkill(config)
        context = SkillContext(
            agent=agent,
            config=config,
            params={
                "title": "登录失败",
                "description": "输入正确密码后无法登录",
                "reproduction_steps": ["打开登录界面", "输入账号密码", "点击登录"],
                "expected_result": "登录成功",
                "actual_result": "提示登录失败",
                "platform": "jira",  # 提交到Jira
                "analyze_only": False
            }
        )
        result = await skill.execute(context)
        ```
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.llm_client = LLMClient(config)
    
    @property
    def name(self) -> str:
        return "bug_tracker"
    
    @property
    def description(self) -> str:
        return "分析Bug报告，支持多平台提交"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "title",
                "type": "string",
                "required": True,
                "description": "Bug标题",
            },
            {
                "name": "description",
                "type": "string",
                "required": True,
                "description": "Bug详细描述",
            },
            {
                "name": "reproduction_steps",
                "type": "array",
                "required": False,
                "description": "复现步骤",
                "default": [],
            },
            {
                "name": "expected_result",
                "type": "string",
                "required": False,
                "description": "预期结果",
                "default": "",
            },
            {
                "name": "actual_result",
                "type": "string",
                "required": False,
                "description": "实际结果",
                "default": "",
            },
            {
                "name": "environment",
                "type": "object",
                "required": False,
                "description": "环境信息",
                "default": {},
            },
            {
                "name": "severity",
                "type": "string",
                "required": False,
                "description": "严重程度（critical/high/medium/low）",
                "default": "medium",
            },
            {
                "name": "priority",
                "type": "string",
                "required": False,
                "description": "优先级（p0/p1/p2/p3）",
                "default": "p2",
            },
            {
                "name": "assignee",
                "type": "string",
                "required": False,
                "description": "指派人",
                "default": "",
            },
            {
                "name": "labels",
                "type": "array",
                "required": False,
                "description": "标签列表",
                "default": [],
            },
            {
                "name": "platform",
                "type": "string",
                "required": False,
                "description": "提交目标平台（jira/zentao/redmine/tapd）",
                "default": "",
            },
            {
                "name": "analyze_only",
                "type": "boolean",
                "required": False,
                "description": "仅分析，不提交",
                "default": True,
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行Bug追踪
        
        Args:
            context: Bug相关参数
        
        Returns:
            Bug分析结果或提交结果
        """
        # 构建Bug报告
        bug_report = BugReport(
            title=context.get_param("title"),
            description=context.get_param("description"),
            reproduction_steps=context.get_param("reproduction_steps", []),
            expected_result=context.get_param("expected_result", ""),
            actual_result=context.get_param("actual_result", ""),
            environment=context.get_param("environment", {}),
        )
        
        logger.info(f"Processing bug report: {bug_report.title}")
        
        # 1. 使用LLM分析Bug
        analysis = await self._analyze_bug(bug_report)
        
        # 2. 如果需要提交到平台
        platform = context.get_param("platform", "")
        analyze_only = context.get_param("analyze_only", True)
        submit_result = None
        
        if platform and not analyze_only:
            submit_result = await self._submit_to_platform(context, bug_report, analysis)
        
        return SkillResult.ok(data={
            "bug_report": bug_report.to_dict(),
            "analysis": analysis.to_dict() if analysis else None,
            "submit_result": submit_result,
        })
    
    async def _analyze_bug(self, bug_report: BugReport) -> BugAnalysis:
        """
        使用LLM分析Bug
        
        Args:
            bug_report: Bug报告对象
        
        Returns:
            Bug分析结果
        """
        # 构建分析提示词
        prompt = self._build_analysis_prompt(bug_report)
        
        try:
            response = await self.llm_client.complete(prompt)
            
            # 解析LLM响应
            analysis_data = self._parse_llm_response(response)
            
            return BugAnalysis(
                bug_report=bug_report,
                root_cause=analysis_data.get("root_cause", ""),
                impact_analysis=analysis_data.get("impact_analysis", ""),
                suggested_fix=analysis_data.get("suggested_fix", ""),
                test_suggestions=analysis_data.get("test_suggestions", []),
                category=analysis_data.get("category", ""),
                component=analysis_data.get("component", ""),
                risk_level=analysis_data.get("risk_level", "中"),
                regression_risk=analysis_data.get("regression_risk", ""),
            )
            
        except Exception as e:
            logger.error(f"Bug analysis failed: {e}")
            return BugAnalysis(
                bug_report=bug_report,
                root_cause=f"分析失败: {str(e)}",
                risk_level="未知",
            )
    
    def _build_analysis_prompt(self, bug_report: BugReport) -> str:
        """
        构建Bug分析提示词
        
        Args:
            bug_report: Bug报告
        
        Returns:
            提示词字符串
        """
        steps_text = ""
        if bug_report.reproduction_steps:
            steps_text = "\n".join(
                f"{i+1}. {step}" 
                for i, step in enumerate(bug_report.reproduction_steps)
            )
        else:
            steps_text = "未提供复现步骤"
        
        prompt = f"""请分析以下Bug报告，提供专业的测试分析。

## Bug信息

**标题**: {bug_report.title}

**描述**: {bug_report.description}

**复现步骤**:
{steps_text}

**预期结果**: {bug_report.expected_result or '未提供'}

**实际结果**: {bug_report.actual_result or '未提供'}

**环境信息**: {bug_report.environment or '未提供'}

## 分析要求

请以JSON格式输出以下分析结果：

```json
{{
    "root_cause": "根因分析（可能的原因）",
    "impact_analysis": "影响分析（影响范围和严重程度）",
    "suggested_fix": "修复建议",
    "test_suggestions": ["测试建议1", "测试建议2"],
    "category": "问题分类（如：逻辑错误/UI问题/性能问题/数据问题等）",
    "component": "可能涉及的组件/模块",
    "risk_level": "风险评估（高/中/低）",
    "regression_risk": "回归风险说明"
}}
```

请只输出JSON，不要包含其他内容。"""

        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应，提取JSON数据
        
        Args:
            response: LLM响应文本
        
        Returns:
            解析后的字典
        """
        try:
            # 尝试直接解析JSON
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # 尝试从代码块中提取JSON
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, response)
        
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # 尝试提取花括号内容
        brace_pattern = r'\{[\s\S]*\}'
        brace_match = re.search(brace_pattern, response)
        
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass
        
        # 解析失败，返回空字典
        logger.warning(f"Failed to parse LLM response as JSON")
        return {}
    
    async def _submit_to_platform(
        self, 
        context: SkillContext, 
        bug_report: BugReport,
        analysis: Optional[BugAnalysis]
    ) -> Dict[str, Any]:
        """
        提交Bug到项目管理平台
        
        Args:
            context: 执行上下文
            bug_report: Bug报告
            analysis: Bug分析结果
        
        Returns:
            提交结果字典
        """
        platform_name = context.get_param("platform", "").lower()
        
        # 检查平台是否配置
        platform_config = None
        for p in self.config.platforms:
            if p.name.lower() == platform_name and p.enabled:
                platform_config = p
                break
        
        if not platform_config:
            return {
                "success": False,
                "error": f"平台 '{platform_name}' 未配置或未启用",
                "platform": platform_name
            }
        
        try:
            # 获取平台适配器
            adapter = get_platform_adapter(platform_name, platform_config)
            
            # 连接平台
            connected = await adapter.connect()
            if not connected:
                return {
                    "success": False,
                    "error": f"无法连接到 {platform_name}",
                    "platform": platform_name
                }
            
            # 构建平台Bug对象
            platform_bug = PlatformBug(
                title=bug_report.title,
                description=self._build_bug_description(bug_report, analysis),
                severity=context.get_param("severity", "medium"),
                priority=context.get_param("priority", "p2"),
                assignee=context.get_param("assignee", ""),
                labels=context.get_param("labels", []),
                attachments=bug_report.attachments,
            )
            
            # 提交Bug
            result = await adapter.submit_bug(platform_bug)
            
            return {
                "success": result.success,
                "bug_id": result.bug_id,
                "bug_url": result.bug_url,
                "error": result.error,
                "platform": platform_name
            }
            
        except Exception as e:
            logger.error(f"Failed to submit bug to {platform_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": platform_name
            }
    
    def _build_bug_description(
        self, 
        bug_report: BugReport, 
        analysis: Optional[BugAnalysis]
    ) -> str:
        """
        构建完整的Bug描述（用于提交到平台）
        
        Args:
            bug_report: Bug报告
            analysis: Bug分析结果
        
        Returns:
            格式化的Bug描述
        """
        lines = []
        
        # 基本信息
        lines.append("## Bug描述")
        lines.append(bug_report.description)
        lines.append("")
        
        # 复现步骤
        if bug_report.reproduction_steps:
            lines.append("## 复现步骤")
            for i, step in enumerate(bug_report.reproduction_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        
        # 预期/实际结果
        if bug_report.expected_result:
            lines.append(f"**预期结果**: {bug_report.expected_result}")
        if bug_report.actual_result:
            lines.append(f"**实际结果**: {bug_report.actual_result}")
        lines.append("")
        
        # 环境信息
        if bug_report.environment:
            lines.append("## 环境信息")
            for key, value in bug_report.environment.items():
                lines.append(f"- {key}: {value}")
            lines.append("")
        
        # 分析结果
        if analysis:
            lines.append("## AI分析")
            if analysis.root_cause:
                lines.append(f"**根因分析**: {analysis.root_cause}")
            if analysis.suggested_fix:
                lines.append(f"**修复建议**: {analysis.suggested_fix}")
            if analysis.risk_level:
                lines.append(f"**风险等级**: {analysis.risk_level}")
        
        return "\n".join(lines)
