"""
游戏业务规则基类

定义游戏类型特定规则的接口和通用功能。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class RuleSeverity(Enum):
    """规则严重程度"""
    ERROR = "error"       # 错误，必须修复
    WARNING = "warning"   # 警告，建议修复
    INFO = "info"         # 信息，仅供参考


@dataclass
class RuleCheckResult:
    """规则检查结果"""
    rule_name: str                        # 规则名称
    passed: bool                         # 是否通过
    message: str                         # 结果消息
    severity: RuleSeverity               # 严重程度
    table_name: Optional[str] = None    # 相关表名
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    suggestions: List[str] = field(default_factory=list)   # 修复建议
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity.value,
            "table_name": self.table_name,
            "details": self.details,
            "suggestions": self.suggestions,
        }
    
    @classmethod
    def success(cls, rule_name: str, message: str, table_name: Optional[str] = None):
        """创建成功结果"""
        return cls(
            rule_name=rule_name,
            passed=True,
            message=message,
            severity=RuleSeverity.INFO,
            table_name=table_name,
        )
    
    @classmethod
    def failure(cls, rule_name: str, message: str, severity: RuleSeverity = RuleSeverity.ERROR,
                table_name: Optional[str] = None, suggestions: List[str] = None):
        """创建失败结果"""
        return cls(
            rule_name=rule_name,
            passed=False,
            message=message,
            severity=severity,
            table_name=table_name,
            suggestions=suggestions or [],
        )
    
    @classmethod
    def warning(cls, rule_name: str, message: str, table_name: Optional[str] = None,
                suggestions: List[str] = None):
        """创建警告结果"""
        return cls(
            rule_name=rule_name,
            passed=True,  # 警告视为通过，但需要注意
            message=message,
            severity=RuleSeverity.WARNING,
            table_name=table_name,
            suggestions=suggestions or [],
        )


class BaseGameRule(ABC):
    """
    游戏业务规则基类
    
    所有游戏类型特定规则都应继承此类。
    
    示例:
        class CheckPlayerLevelRule(BaseGameRule):
            @property
            def name(self) -> str:
                return "玩家等级检查"
            
            @property
            def description(self) -> str:
                return "检查玩家等级是否在合理范围内"
            
            def applicable_tables(self) -> List[str]:
                return ["player", "character"]
            
            def check(self, connector, table_name: str) -> RuleCheckResult:
                # 执行检查逻辑
                result = connector.execute_query(
                    "SELECT COUNT(*) as cnt FROM player WHERE level < 1 OR level > 999"
                )
                if result[0]["cnt"] > 0:
                    return RuleCheckResult.failure(...)
                return RuleCheckResult.success(...)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化规则
        
        Args:
            config: 规则配置参数
        """
        self.config = config or {}
    
    @property
    @abstractmethod
    def name(self) -> str:
        """规则名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """规则描述"""
        pass
    
    @abstractmethod
    def applicable_tables(self) -> List[str]:
        """
        返回适用的表名模式列表
        
        Returns:
            表名列表，支持部分匹配
        """
        pass
    
    def is_applicable(self, table_name: str) -> bool:
        """
        检查规则是否适用于指定表
        
        Args:
            table_name: 表名
        
        Returns:
            是否适用
        """
        table_lower = table_name.lower()
        for pattern in self.applicable_tables():
            if pattern.lower() in table_lower:
                return True
        return False
    
    @abstractmethod
    def check(self, connector, table_name: str) -> RuleCheckResult:
        """
        执行规则检查
        
        Args:
            connector: 数据库连接器
            table_name: 要检查的表名
        
        Returns:
            检查结果
        """
        pass
    
    def get_column_names(self, connector, table_name: str) -> List[str]:
        """
        获取表的列名列表（辅助方法）
        
        Args:
            connector: 数据库连接器
            table_name: 表名
        
        Returns:
            列名列表
        """
        schema = connector.get_table_schema(table_name)
        return [col.name for col in schema.columns]
    
    def column_exists(self, connector, table_name: str, column_name: str) -> bool:
        """
        检查列是否存在（辅助方法）
        
        Args:
            connector: 数据库连接器
            table_name: 表名
            column_name: 列名
        
        Returns:
            是否存在
        """
        columns = self.get_column_names(connector, table_name)
        return column_name.lower() in [c.lower() for c in columns]
    
    def get_row_count(self, connector, table_name: str, condition: Optional[str] = None) -> int:
        """
        获取行数（辅助方法）
        
        Args:
            connector: 数据库连接器
            table_name: 表名
            condition: 可选的 WHERE 条件
        
        Returns:
            行数
        """
        sql = f"SELECT COUNT(*) as cnt FROM {table_name}"
        if condition:
            sql += f" WHERE {condition}"
        
        result = connector.execute_query(sql)
        return result[0].get("cnt", 0) if result else 0


class CompositeRule(BaseGameRule):
    """
    组合规则
    
    将多个规则组合在一起执行。
    """
    
    def __init__(self, rules: List[BaseGameRule], config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.rules = rules
    
    @property
    def name(self) -> str:
        return f"组合规则({len(self.rules)}个子规则)"
    
    @property
    def description(self) -> str:
        return "执行多个子规则的组合检查"
    
    def applicable_tables(self) -> List[str]:
        # 返回所有子规则的并集
        tables = set()
        for rule in self.rules:
            tables.update(rule.applicable_tables())
        return list(tables)
    
    def check(self, connector, table_name: str) -> List[RuleCheckResult]:
        """
        执行所有子规则检查
        
        Returns:
            所有子规则的结果列表
        """
        results = []
        for rule in self.rules:
            if rule.is_applicable(table_name):
                result = rule.check(connector, table_name)
                results.append(result)
        return results
