"""
验证器基类与通用验证框架

所有验证器必须继承 BaseValidator，实现 validate 方法
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Type
from enum import Enum
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationSeverity(Enum):
    """验证问题严重程度"""
    CRITICAL = "critical"      # 严重错误，必须修复
    ERROR = "error"            # 错误，建议修复  
    WARNING = "warning"        # 警告，可以忽略
    INFO = "info"              # 提示信息


@dataclass
class ValidationIssue:
    """单个验证问题"""
    code: str                          # 问题代码，如 "MISSING_PRECONDITION"
    message: str                       # 问题描述
    severity: ValidationSeverity       # 严重程度
    field: Optional[str] = None        # 相关字段
    suggestion: Optional[str] = None   # 修复建议
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "field": self.field,
            "suggestion": self.suggestion,
        }


@dataclass 
class QualityScore:
    """质量评分"""
    total_score: float                 # 总分 (0-100)
    dimension_scores: Dict[str, float] # 各维度得分
    passed: bool                       # 是否通过
    threshold: float                   # 通过阈值
    
    def __post_init__(self):
        if not self.dimension_scores:
            self.dimension_scores = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": round(self.total_score, 2),
            "dimension_scores": {k: round(v, 2) for k, v in self.dimension_scores.items()},
            "passed": self.passed,
            "threshold": self.threshold,
        }


@dataclass
class ValidationResult:
    """验证结果"""
    success: bool                      # 是否通过验证
    issues: List[ValidationIssue]      # 问题列表
    score: QualityScore                # 质量评分
    metadata: Dict[str, Any]           # 元数据
    validated_at: datetime             # 验证时间
    
    def __post_init__(self):
        if self.validated_at is None:
            self.validated_at = datetime.now()
    
    @property
    def has_critical_issues(self) -> bool:
        """是否有严重问题"""
        return any(i.severity == ValidationSeverity.CRITICAL for i in self.issues)
    
    @property
    def error_count(self) -> int:
        """错误数量"""
        return sum(1 for i in self.issues if i.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR])
    
    @property
    def warning_count(self) -> int:
        """警告数量"""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "issues": [i.to_dict() for i in self.issues],
            "score": self.score.to_dict(),
            "metadata": self.metadata,
            "validated_at": self.validated_at.isoformat(),
            "has_critical_issues": self.has_critical_issues,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }
    
    @classmethod
    def passed(cls, score: QualityScore, metadata: Dict[str, Any] = None) -> "ValidationResult":
        """创建通过的结果"""
        return cls(
            success=True,
            issues=[],
            score=score,
            metadata=metadata or {},
            validated_at=datetime.now(),
        )
    
    @classmethod
    def failed(cls, issues: List[ValidationIssue], score: QualityScore, metadata: Dict[str, Any] = None) -> "ValidationResult":
        """创建失败的结果"""
        return cls(
            success=False,
            issues=issues,
            score=score,
            metadata=metadata or {},
            validated_at=datetime.now(),
        )


class BaseValidator(ABC):
    """
    验证器基类
    
    所有验证器必须继承此类并实现 validate 方法
    """
    
    # 验证器名称，用于注册和识别
    name: str = ""
    
    # 验证器描述
    description: str = ""
    
    # 验证维度权重 (0-1)
    weight: float = 1.0
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化验证器
        
        Args:
            config: 验证器配置参数
        """
        self.config = config or {}
        self.logger = get_logger(f"{__name__}.{self.name}")
    
    @abstractmethod
    async def validate(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """
        执行验证
        
        Args:
            input_data: 原始输入数据
            output_data: TestOwl 生成的输出数据
            context: 验证上下文
            
        Returns:
            ValidationResult 验证结果
        """
        pass
    
    def calculate_score(self, issues: List[ValidationIssue]) -> float:
        """
        基于问题计算得分
        
        扣分规则：
        - Critical: -20 分
        - Error: -10 分  
        - Warning: -5 分
        - Info: -1 分
        """
        base_score = 100.0
        
        deductions = {
            ValidationSeverity.CRITICAL: 20,
            ValidationSeverity.ERROR: 10,
            ValidationSeverity.WARNING: 5,
            ValidationSeverity.INFO: 1,
        }
        
        for issue in issues:
            base_score -= deductions.get(issue.severity, 0)
        
        return max(0.0, base_score)
    
    def create_issue(
        self, 
        code: str, 
        message: str, 
        severity: ValidationSeverity,
        field: str = None,
        suggestion: str = None
    ) -> ValidationIssue:
        """快捷创建问题"""
        return ValidationIssue(
            code=code,
            message=message,
            severity=severity,
            field=field,
            suggestion=suggestion,
        )
    
    # ========== 通用工具方法 ==========
    
    def has_placeholder(self, text: str) -> bool:
        """检测文本是否包含占位符"""
        if not text:
            return False
        placeholders = ["待补充", "TODO", "FIXME", "待定", "[", "]", "请填写"]
        return any(p in text for p in placeholders)
    
    def create_failed_result(
        self, 
        issues: List[ValidationIssue], 
        metadata: Dict[str, Any] = None
    ) -> ValidationResult:
        """创建失败结果"""
        score = QualityScore(
            total_score=0.0,
            dimension_scores={"completeness": 0.0},
            passed=False,
            threshold=70.0
        )
        return ValidationResult.failed(issues, score, metadata or {})
    
    def extract_items(
        self, 
        data: Any, 
        list_keys: List[str] = None,
        item_identifier: str = "name"
    ) -> List[Dict]:
        """
        通用数据提取方法
        
        从各种格式中提取项目列表
        
        Args:
            data: 输入数据
            list_keys: 可能的列表字段名
            item_identifier: 标识单个项目的字段名
        """
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            list_keys = list_keys or ["items", "data", "list"]
            for key in list_keys:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # 如果 dict 本身看起来像项目
            if item_identifier in data:
                return [data]
        
        return []


class ValidatorRegistry:
    """
    验证器注册表
    
    管理所有可用的验证器
    """
    
    _validators: Dict[str, Type[BaseValidator]] = {}
    
    @classmethod
    def register(cls, validator_class: Type[BaseValidator]) -> Type[BaseValidator]:
        """
        注册验证器
        
        可作为装饰器使用：
            @ValidatorRegistry.register
            class MyValidator(BaseValidator):
                name = "my_validator"
        """
        if not validator_class.name:
            raise ValueError(f"Validator class {validator_class.__name__} must have a name")
        
        cls._validators[validator_class.name] = validator_class
        logger.info(f"Validator registered: {validator_class.name}")
        return validator_class
    
    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseValidator]]:
        """获取验证器类"""
        return cls._validators.get(name)
    
    @classmethod
    def create(cls, name: str, config: Dict[str, Any] = None) -> Optional[BaseValidator]:
        """创建验证器实例"""
        validator_class = cls.get(name)
        if validator_class:
            return validator_class(config)
        return None
    
    @classmethod
    def list_validators(cls) -> List[Dict[str, str]]:
        """列出所有已注册的验证器"""
        return [
            {"name": name, "description": v.description}
            for name, v in cls._validators.items()
        ]
    
    @classmethod
    def create_pipeline(cls, names: List[str], configs: Dict[str, Dict] = None) -> List[BaseValidator]:
        """创建验证器流水线"""
        configs = configs or {}
        pipeline = []
        for name in names:
            validator = cls.create(name, configs.get(name, {}))
            if validator:
                pipeline.append(validator)
            else:
                logger.warning(f"Validator not found: {name}")
        return pipeline