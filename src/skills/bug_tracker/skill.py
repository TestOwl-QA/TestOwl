"""
Bug追踪技能

功能：
1. 分析Bug报告，提供根因分析
2. Bug智能分类和优先级建议
"""

import json
import re
from typing import Any, Dict, List, Optional

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.skills.bug_tracker.models import BugReport, BugAnalysis, BugSeverity, BugPriority
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BugTrackerSkill(BaseSkill):
    """Bug追踪技能 - 专注于Bug分析与诊断"""

    def __init__(self, config: Config):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "bug_tracker"

    @property
    def description(self) -> str:
        return "分析Bug报告，提供根因分析、影响评估与修复建议"

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {"name": "title", "type": "string", "required": True, "description": "Bug标题"},
            {"name": "description", "type": "string", "required": True, "description": "Bug详细描述"},
            {"name": "reproduction_steps", "type": "array", "required": False, "description": "复现步骤", "default": []},
            {"name": "expected_result", "type": "string", "required": False, "description": "预期结果", "default": ""},
            {"name": "actual_result", "type": "string", "required": False, "description": "实际结果", "default": ""},
            {"name": "environment", "type": "object", "required": False, "description": "环境信息", "default": {}},
            {"name": "severity", "type": "string", "required": False, "description": "严重程度（critical/high/medium/low）", "default": "medium"},
            {"name": "priority", "type": "string", "required": False, "description": "优先级（p0/p1/p2/p3）", "default": "p2"},
            {"name": "assignee", "type": "string", "required": False, "description": "指派人", "default": ""},
            {"name": "labels", "type": "array", "required": False, "description": "标签列表", "default": []},
        ]

    async def execute(self, context: SkillContext) -> SkillResult:
        bug_report = BugReport(
            title=context.get_param("title"),
            description=context.get_param("description"),
            reproduction_steps=context.get_param("reproduction_steps", []),
            expected_result=context.get_param("expected_result", ""),
            actual_result=context.get_param("actual_result", ""),
            environment=context.get_param("environment", {}),
        )
        logger.info(f"Processing bug report: {bug_report.title}")
        analysis = await self._analyze_bug(bug_report)
        return SkillResult.ok(data={
            "bug_report": bug_report.to_dict(),
            "analysis": analysis.to_dict() if analysis else None,
        })

    async def _analyze_bug(self, bug_report: BugReport) -> BugAnalysis:
        prompt = self._build_analysis_prompt(bug_report)
        try:
            response = await self._get_llm_client().complete(prompt)
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
            return BugAnalysis(bug_report=bug_report, root_cause=f"分析失败: {str(e)}", risk_level="未知")

    def _build_analysis_prompt(self, bug_report: BugReport) -> str:
        if bug_report.reproduction_steps:
            lines = [f"{i+1}. {step}" for i, step in enumerate(bug_report.reproduction_steps)]
            steps_text = "\n".join(lines)
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
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, response)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        brace_pattern = r'\{[\s\S]*\}'
        brace_match = re.search(brace_pattern, response)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse LLM response as JSON")
        return {}
