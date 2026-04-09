"""
TestOwl 质量验证系统

提供多维度结果验证、自动重试、质量评分功能
"""

# 先导入验证器模块以触发注册
import src.quality.validators as _validators_module

from src.quality.validator import (
    ValidationResult,
    QualityScore,
    BaseValidator,
    ValidatorRegistry,
)
from src.quality.engine import QualityEngine
from src.quality.retry import RetryStrategy, RetryConfig

__all__ = [
    "ValidationResult",
    "QualityScore",
    "BaseValidator",
    "ValidatorRegistry",
    "QualityEngine",
    "RetryStrategy",
    "RetryConfig",
]