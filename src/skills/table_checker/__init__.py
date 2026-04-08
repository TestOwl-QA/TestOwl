"""
表检查技能模块

功能：
- 配置表、数据表、数据库表检查
- 可扩展的规则系统
- 常见规则：唯一性、非空、范围、引用完整性、格式等
"""

from src.skills.table_checker.skill import (
    TableCheckerSkill,
    RuleEngine,
    CheckRule,
    CheckResult,
    RuleType,
    GAME_TEST_RULES,
    get_game_rule,
)

__all__ = [
    "TableCheckerSkill",
    "RuleEngine",
    "CheckRule",
    "CheckResult",
    "RuleType",
    "GAME_TEST_RULES",
    "get_game_rule",
]