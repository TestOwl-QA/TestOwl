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
    
    标准化的Bug数据结构，支持多平台导出
    """
    # 基本信息
    id: str = ""                       # Bug ID（提交后由平台分配）
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
    # 例如：{"app_version": "1.0.0", "device": "iPhone 14", "os": "iOS 16"}
    
    # 附件
    attachments: List[str] = field(default_factory=list)  # 附件路径/URL列表
    screenshots: List[str] = field(default_factory=list)  # 截图路径/URL列表
    logs: str = ""                     # 日志内容
    
    # 人员
    reporter: str = ""                 # 报告人
    assignee: str = ""                 # 指派人
    
    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""
    
    # 关联
    related_requirement: str = ""      # 关联需求
    related_test_case: str = ""        # 关联测试用例
    
    # 标签和模块
    module: str = ""                   # 所属模块
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
    
    def to_platform_format(self, platform: str) -> Dict[str, Any]:
        """
        转换为特定平台的格式
        
        Args:
            platform: 平台名称（jira/zentao/redmine/tapd）
        """
        converters = {
            "jira": self._to_jira_format,
            "zentao": self._to_zentao_format,
            "redmine": self._to_redmine_format,
            "tapd": self._to_tapd_format,
        }
        
        converter = converters.get(platform)
        if converter:
            return converter()
        
        return self.to_dict()
    
    def _to_jira_format(self) -> Dict[str, Any]:
        """转换为Jira格式"""
        severity_map = {
            BugSeverity.CRITICAL: "Highest",
            BugSeverity.HIGH: "High",
            BugSeverity.MEDIUM: "Medium",
            BugSeverity.LOW: "Low",
            BugSeverity.TRIVIAL: "Lowest",
        }
        
        description = self._build_description()
        
        return {
            "fields": {
                "project": {"key": ""},  # 需要填充
                "summary": self.title,
                "description": description,
                "issuetype": {"name": "Bug"},
                "priority": {"name": severity_map.get(self.severity, "Medium")},
                "labels": self.tags,
            }
        }
    
    def _to_zentao_format(self) -> Dict[str, Any]:
        """转换为禅道格式"""
        severity_map = {
            BugSeverity.CRITICAL: 1,
            BugSeverity.HIGH: 2,
            BugSeverity.MEDIUM: 3,
            BugSeverity.LOW: 4,
            BugSeverity.TRIVIAL: 5,
        }
        
        return {
            "title": self.title,
            "steps": "\n".join(self.reproduction_steps),
            "type": "codeerror",
            "severity": severity_map.get(self.severity, 3),
            "pri": int(self.priority.value[1]),  # P0->0, P1->1, etc.
            "desc": self.description,
        }
    
    def _to_redmine_format(self) -> Dict[str, Any]:
        """转换为Redmine格式"""
        description = self._build_description()
        
        return {
            "issue": {
                "subject": self.title,
                "description": description,
                "priority_id": 2,  # 需要映射
                "tracker_id": 1,   # Bug tracker
            }
        }
    
    def _to_tapd_format(self) -> Dict[str, Any]:
        """转换为Tapd格式"""
        return {
            "title": self.title,
            "description": self._build_description(),
            "priority": self.priority.value,
            "severity": self.severity.value,
        }
    
    def _build_description(self) -> str:
        """构建完整描述"""
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
                self.logs[:5000],  # 限制长度
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
    category: str = ""             # 问题类别（逻辑错误、UI问题、性能问题等）
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
