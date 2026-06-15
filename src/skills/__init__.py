"""
技能模块

黑盒测试核心技能：
- document_analyzer: 需求文档分析
- bug_tracker: Bug追踪分析
- table_checker: 配置表检查
- db_checker: 数据库检查
"""

from src.skills.base import BaseSkill, SkillContext, SkillResult


__all__ = [
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "DocumentAnalyzerSkill",
    "BugTrackerSkill",
    "TableCheckerSkill",
    "DBCheckerSkill",
]