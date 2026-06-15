"""
Bug追踪数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class BugSeverity(Enum):
    """Bug严重程度"""
    CRITICAL = "致命"      # 系统崩溃、数据丢失
    HIGH = "严重"          # 主要功能失效
    MEDIUM = "一般"        # 次要功能问题
    LOW = "轻微"           # UI/体验问题
    TRIVIAL = "建议"       # 优化建议


class BugPriority(Enum):
    """Bug优先级"""
    P0 = "P0"  # 立即处理
    P1 = "P1"  # 24小时内
    P2 = "P2"  # 本周内
    P3 = "P3"  # 排期处理


class BugStatus(Enum):
    """Bug状态"""
    NEW = "新建"
    CONFIRMED = "已确认"
    IN_PROGRESS = "处理中"
    FIXED = "已修复"
    VERIFIED = "已验证"
    CLOSED = "已关闭"
    REOPENED = "重新打开"
    REJECTED = "已拒绝"


@dataclass
class BugReport:
    """
    Bug报告

    标准化的Bug数据结构
    """
    # 基本信息
    id: str = ""                       # Bug ID
    title: str = ""                    # 标题
    description: str = ""              # 详细描述

    # 分类
    severity: BugSeverity = BugSeverity.MEDIUM
    priority: BugPriority = BugPriority.P2
    status: BugStatus = BugStatus.NEW

    # 复现信息
    reproduction_steps: List[str] = field(default_factory=list)
    expected_result: str = ""
    actual_result: str = ""

    # 环境信息
    environment: Dict[str, str] = field(default_factory=dict)

    # 附件
    attachments: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    logs: str = ""

    # 人员
    reporter: str = ""
    assignee: str = ""

    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    # 关联
    related_requirement: str = ""
    related_test_case: str = ""

    # 标签和模块
    module: str = ""
    tags: List[str] = field(default_factory=list)

    # 备注
    comments: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "reproduction_steps": self.reproduction_steps,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "environment": self.environment,
            "attachments": self.attachments,
            "screenshots": self.screenshots,
            "logs": self.logs,
            "reporter": self.reporter,
            "assignee": self.assignee,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "related_requirement": self.related_requirement,
            "related_test_case": self.related_test_case,
            "module": self.module,
            "tags": self.tags,
            "comments": self.comments,
            "notes": self.notes,
        }

    def _build_description(self) -> str:
        """构建完整描述（供分析报告使用）"""
        parts = [
            f"## 问题描述\n{self.description}",
            "",
            "## 复现步骤",
        ]

        for i, step in enumerate(self.reproduction_steps, 1):
            parts.append(f"{i}. {step}")

        parts.extend([
            "",
            f"## 预期结果\n{self.expected_result}",
            "",
            f"## 实际结果\n{self.actual_result}",
        ])

        if self.environment:
            parts.extend([
                "",
                "## 环境信息",
            ])
            for key, value in self.environment.items():
                parts.append(f"- {key}: {value}")

        if self.logs:
            parts.extend([
                "",
                "## 日志",
                "```",
                self.logs[:5000],
                "```",
            ])

        return "\n".join(parts)


@dataclass
class BugAnalysis:
    """
    Bug分析结果

    使用LLM对Bug进行智能分析
    """
    # 原始Bug
    bug_report: BugReport

    # 分析结果
    root_cause: str = ""           # 根因分析
    impact_analysis: str = ""      # 影响分析
    suggested_fix: str = ""        # 修复建议
    test_suggestions: List[str] = field(default_factory=list)  # 测试建议

    # 分类
    category: str = ""             # 问题类别
    component: str = ""            # 可能涉及的组件

    # 历史相似Bug
    similar_bugs: List[Dict[str, Any]] = field(default_factory=list)

    # 风险评估
    risk_level: str = ""           # 高/中/低
    regression_risk: str = ""      # 回归风险

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "bug_report": self.bug_report.to_dict(),
            "root_cause": self.root_cause,
            "impact_analysis": self.impact_analysis,
            "suggested_fix": self.suggested_fix,
            "test_suggestions": self.test_suggestions,
            "category": self.category,
            "component": self.component,
            "similar_bugs": self.similar_bugs,
            "risk_level": self.risk_level,
            "regression_risk": self.regression_risk,
        }
