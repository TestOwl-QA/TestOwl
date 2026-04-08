"""
表检查技能

功能：
1. 支持配置表、数据表、数据库表等多种表格式检查
2. 可扩展的规则系统
3. 常见规则：唯一性、非空、范围、引用完整性、格式等
"""

import re
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RuleType(Enum):
    """规则类型"""
    UNIQUE = "unique"           # 唯一性检查
    NOT_NULL = "not_null"       # 非空检查
    RANGE = "range"             # 范围检查
    FORMAT = "format"           # 格式检查（正则）
    REFERENCE = "reference"     # 引用完整性检查
    ENUM = "enum"               # 枚举值检查
    CUSTOM = "custom"           # 自定义规则


@dataclass
class CheckRule:
    """检查规则定义"""
    name: str
    rule_type: RuleType
    column: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    severity: str = "error"  # error/warning/info
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "rule_type": self.rule_type.value,
            "column": self.column,
            "params": self.params,
            "description": self.description,
            "severity": self.severity,
        }


@dataclass
class CheckResult:
    """单个检查结果"""
    rule_name: str
    column: str
    row_index: int
    row_id: Any
    message: str
    severity: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "column": self.column,
            "row_index": self.row_index,
            "row_id": str(self.row_id),
            "message": self.message,
            "severity": self.severity,
        }


class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        self._rules: Dict[RuleType, Callable] = {
            RuleType.UNIQUE: self._check_unique,
            RuleType.NOT_NULL: self._check_not_null,
            RuleType.RANGE: self._check_range,
            RuleType.FORMAT: self._check_format,
            RuleType.REFERENCE: self._check_reference,
            RuleType.ENUM: self._check_enum,
            RuleType.CUSTOM: self._check_custom,
        }
    
    def check(
        self,
        data: List[Dict[str, Any]],
        rules: List[CheckRule],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[CheckResult]:
        """
        执行数据检查
        
        Args:
            data: 要检查的数据列表
            rules: 检查规则列表
            context: 上下文数据（用于引用检查等）
        
        Returns:
            检查结果列表
        """
        results = []
        
        for rule in rules:
            checker = self._rules.get(rule.rule_type)
            if checker:
                rule_results = checker(data, rule, context or {})
                results.extend(rule_results)
            else:
                logger.warning(f"Unknown rule type: {rule.rule_type}")
        
        return results
    
    def _check_unique(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """唯一性检查"""
        results = []
        seen = {}
        
        for i, row in enumerate(data):
            value = row.get(rule.column)
            if value is not None and value != "":
                if value in seen:
                    # 发现重复
                    results.append(CheckResult(
                        rule_name=rule.name,
                        column=rule.column,
                        row_index=i,
                        row_id=row.get("id", i),
                        message=f"值 '{value}' 重复，首次出现在第 {seen[value] + 1} 行",
                        severity=rule.severity,
                    ))
                else:
                    seen[value] = i
        
        return results
    
    def _check_not_null(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """非空检查"""
        results = []
        
        for i, row in enumerate(data):
            value = row.get(rule.column)
            if value is None or value == "":
                results.append(CheckResult(
                    rule_name=rule.name,
                    column=rule.column,
                    row_index=i,
                    row_id=row.get("id", i),
                    message=f"列 '{rule.column}' 不能为空",
                    severity=rule.severity,
                ))
        
        return results
    
    def _check_range(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """范围检查"""
        results = []
        min_val = rule.params.get("min")
        max_val = rule.params.get("max")
        
        for i, row in enumerate(data):
            value = row.get(rule.column)
            if value is not None and value != "":
                try:
                    num_val = float(value)
                    if min_val is not None and num_val < min_val:
                        results.append(CheckResult(
                            rule_name=rule.name,
                            column=rule.column,
                            row_index=i,
                            row_id=row.get("id", i),
                            message=f"值 {value} 小于最小值 {min_val}",
                            severity=rule.severity,
                        ))
                    if max_val is not None and num_val > max_val:
                        results.append(CheckResult(
                            rule_name=rule.name,
                            column=rule.column,
                            row_index=i,
                            row_id=row.get("id", i),
                            message=f"值 {value} 大于最大值 {max_val}",
                            severity=rule.severity,
                        ))
                except (ValueError, TypeError):
                    results.append(CheckResult(
                        rule_name=rule.name,
                        column=rule.column,
                        row_index=i,
                        row_id=row.get("id", i),
                        message=f"值 '{value}' 不是有效的数字",
                        severity=rule.severity,
                    ))
        
        return results
    
    def _check_format(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """格式检查（正则）"""
        results = []
        pattern = rule.params.get("pattern", "")
        regex = re.compile(pattern)
        
        for i, row in enumerate(data):
            value = row.get(rule.column)
            if value is not None and value != "":
                if not regex.match(str(value)):
                    results.append(CheckResult(
                        rule_name=rule.name,
                        column=rule.column,
                        row_index=i,
                        row_id=row.get("id", i),
                        message=f"值 '{value}' 不符合格式要求: {pattern}",
                        severity=rule.severity,
                    ))
        
        return results
    
    def _check_reference(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """引用完整性检查"""
        results = []
        ref_table = rule.params.get("reference_table")
        ref_column = rule.params.get("reference_column", "id")
        
        # 从上下文中获取引用数据
        ref_data = context.get("reference_data", {}).get(ref_table, [])
        ref_values = {row.get(ref_column) for row in ref_data}
        
        for i, row in enumerate(data):
            value = row.get(rule.column)
            if value is not None and value != "":
                if value not in ref_values:
                    results.append(CheckResult(
                        rule_name=rule.name,
                        column=rule.column,
                        row_index=i,
                        row_id=row.get("id", i),
                        message=f"引用值 '{value}' 在表 '{ref_table}' 中不存在",
                        severity=rule.severity,
                    ))
        
        return results
    
    def _check_enum(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """枚举值检查"""
        results = []
        allowed_values = set(rule.params.get("values", []))
        
        for i, row in enumerate(data):
            value = row.get(rule.column)
            if value is not None and value != "":
                if value not in allowed_values:
                    results.append(CheckResult(
                        rule_name=rule.name,
                        column=rule.column,
                        row_index=i,
                        row_id=row.get("id", i),
                        message=f"值 '{value}' 不在允许的枚举值中: {allowed_values}",
                        severity=rule.severity,
                    ))
        
        return results
    
    def _check_custom(
        self,
        data: List[Dict[str, Any]],
        rule: CheckRule,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """自定义规则检查"""
        results = []
        # 获取自定义检查函数
        custom_func = rule.params.get("check_function")
        if callable(custom_func):
            for i, row in enumerate(data):
                result = custom_func(row, context)
                if result:
                    results.append(CheckResult(
                        rule_name=rule.name,
                        column=rule.column,
                        row_index=i,
                        row_id=row.get("id", i),
                        message=result,
                        severity=rule.severity,
                    ))
        return results


class TableCheckerSkill(BaseSkill):
    """
    表检查技能
    
    支持多种表格式和可扩展的规则系统
    
    使用示例：
        ```python
        skill = TableCheckerSkill(config)
        
        # 定义规则
        rules = [
            CheckRule(
                name="ID唯一性",
                rule_type=RuleType.UNIQUE,
                column="id",
                severity="error"
            ),
            CheckRule(
                name="名称非空",
                rule_type=RuleType.NOT_NULL,
                column="name",
                severity="error"
            ),
            CheckRule(
                name="等级范围",
                rule_type=RuleType.RANGE,
                column="level",
                params={"min": 1, "max": 100},
                severity="warning"
            ),
        ]
        
        context = SkillContext(
            agent=agent,
            config=config,
            params={
                "data": table_data,
                "rules": rules,
            }
        )
        result = await skill.execute(context)
        ```
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.rule_engine = RuleEngine()
    
    @property
    def name(self) -> str:
        return "table_checker"
    
    @property
    def description(self) -> str:
        return "检查配置表、数据表、数据库表的数据质量"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "data",
                "type": "array",
                "required": True,
                "description": "要检查的数据列表",
            },
            {
                "name": "rules",
                "type": "array",
                "required": True,
                "description": "检查规则列表",
            },
            {
                "name": "context",
                "type": "object",
                "required": False,
                "description": "上下文数据（用于引用检查等）",
                "default": {},
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行表检查
        
        Args:
            context: 包含data、rules、context等参数
        
        Returns:
            检查结果汇总
        """
        data = context.get_param("data", [])
        rules_data = context.get_param("rules", [])
        check_context = context.get_param("context", {})
        
        if not data:
            return SkillResult.error("没有数据需要检查")
        
        if not rules_data:
            return SkillResult.error("没有指定检查规则")
        
        logger.info(f"Checking {len(data)} rows with {len(rules_data)} rules")
        
        # 解析规则
        rules = self._parse_rules(rules_data)
        
        # 执行检查
        results = self.rule_engine.check(data, rules, check_context)
        
        # 汇总结果
        summary = self._summarize_results(results)
        
        return SkillResult.ok(data={
            "summary": summary,
            "errors": [r.to_dict() for r in results if r.severity == "error"],
            "warnings": [r.to_dict() for r in results if r.severity == "warning"],
            "infos": [r.to_dict() for r in results if r.severity == "info"],
            "all_results": [r.to_dict() for r in results],
        })
    
    def _parse_rules(self, rules_data: List[Dict]) -> List[CheckRule]:
        """解析规则数据"""
        rules = []
        
        for rule_data in rules_data:
            try:
                rule_type = RuleType(rule_data.get("rule_type", "custom"))
            except ValueError:
                rule_type = RuleType.CUSTOM
            
            rule = CheckRule(
                name=rule_data.get("name", "未命名规则"),
                rule_type=rule_type,
                column=rule_data.get("column", ""),
                params=rule_data.get("params", {}),
                description=rule_data.get("description", ""),
                severity=rule_data.get("severity", "error"),
            )
            rules.append(rule)
        
        return rules
    
    def _summarize_results(self, results: List[CheckResult]) -> Dict[str, Any]:
        """汇总检查结果"""
        error_count = sum(1 for r in results if r.severity == "error")
        warning_count = sum(1 for r in results if r.severity == "warning")
        info_count = sum(1 for r in results if r.severity == "info")
        
        # 按规则统计
        rule_stats = {}
        for r in results:
            if r.rule_name not in rule_stats:
                rule_stats[r.rule_name] = {"errors": 0, "warnings": 0, "infos": 0}
            rule_stats[r.rule_name][f"{r.severity}s"] += 1
        
        return {
            "total_checked": len(results),
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "passed": error_count == 0,
            "rule_statistics": rule_stats,
        }
    
    def add_custom_rule_type(
        self,
        rule_type: str,
        checker: Callable[[List[Dict], CheckRule, Dict], List[CheckResult]],
    ):
        """
        添加自定义规则类型
        
        Args:
            rule_type: 规则类型名称
            checker: 检查函数
        """
        enum_type = RuleType(rule_type) if rule_type in [t.value for t in RuleType] else RuleType.CUSTOM
        self.rule_engine._rules[enum_type] = checker
        logger.info(f"Added custom rule type: {rule_type}")


# 预定义的游戏测试常用规则
GAME_TEST_RULES = {
    "item_id_unique": lambda: CheckRule(
        name="物品ID唯一性",
        rule_type=RuleType.UNIQUE,
        column="item_id",
        severity="error",
    ),
    "item_name_not_empty": lambda: CheckRule(
        name="物品名称非空",
        rule_type=RuleType.NOT_NULL,
        column="item_name",
        severity="error",
    ),
    "level_range": lambda min_lv=1, max_lv=100: CheckRule(
        name="等级范围检查",
        rule_type=RuleType.RANGE,
        column="level",
        params={"min": min_lv, "max": max_lv},
        severity="warning",
    ),
    "price_positive": lambda: CheckRule(
        name="价格非负",
        rule_type=RuleType.RANGE,
        column="price",
        params={"min": 0},
        severity="error",
    ),
    "id_format": lambda pattern=r"^[A-Z]{2}\d{4}$": CheckRule(
        name="ID格式检查",
        rule_type=RuleType.FORMAT,
        column="id",
        params={"pattern": pattern},
        severity="error",
    ),
    "rarity_enum": lambda values=None: CheckRule(
        name="稀有度枚举检查",
        rule_type=RuleType.ENUM,
        column="rarity",
        params={"values": values or ["N", "R", "SR", "SSR", "UR"]},
        severity="error",
    ),
    "item_type_reference": lambda ref_table="ItemType": CheckRule(
        name="物品类型引用检查",
        rule_type=RuleType.REFERENCE,
        column="type_id",
        params={"reference_table": ref_table, "reference_column": "id"},
        severity="error",
    ),
}


def get_game_rule(rule_name: str, **kwargs) -> CheckRule:
    """
    获取预定义的游戏测试规则
    
    Args:
        rule_name: 规则名称
        **kwargs: 规则参数
    
    Returns:
        CheckRule对象
    """
    rule_factory = GAME_TEST_RULES.get(rule_name)
    if rule_factory:
        return rule_factory(**kwargs)
    raise ValueError(f"Unknown game rule: {rule_name}")