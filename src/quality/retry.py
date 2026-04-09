"""
重试策略

当验证失败时，如何重试生成
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class RetryPolicy(Enum):
    """重试策略类型"""
    IMMEDIATE = "immediate"           # 立即重试
    WITH_FEEDBACK = "with_feedback"   # 带反馈重试（推荐）
    ESCALATE = "escalate"             # 升级处理（人工介入）
    ABORT = "abort"                   # 放弃


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3                      # 最大重试次数
    policy: RetryPolicy = RetryPolicy.WITH_FEEDBACK
    temperature_increase: float = 0.1         # 每次重试温度增加
    feedback_template: str = """              # 反馈提示模板
基于验证结果，请修复以下问题后重新生成：

{issues}

原始需求：
{original_input}

之前生成的结果：
{previous_output}

请确保修复所有问题后再次输出。
"""


class RetryStrategy:
    """
    重试策略执行器
    
    根据验证结果决定如何重试
    """
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.retry_history: List[Dict] = []
    
    def should_retry(self, validation_result, attempt: int) -> bool:
        """
        判断是否应该重试
        
        Args:
            validation_result: 验证结果
            attempt: 当前尝试次数
            
        Returns:
            是否应该继续重试
        """
        # 已经通过，不需要重试
        if validation_result.success:
            return False
        
        # 超过最大重试次数
        if attempt >= self.config.max_retries:
            logger.warning(f"Max retries ({self.config.max_retries}) reached, giving up")
            return False
        
        # 有严重错误，可能需要人工介入
        if validation_result.has_critical_issues and attempt >= 2:
            logger.warning("Critical issues persist after retries, escalating")
            return False
        
        return True
    
    def build_retry_context(
        self,
        original_input: Any,
        previous_output: Any,
        validation_result,
        attempt: int
    ) -> Dict[str, Any]:
        """
        构建重试上下文
        
        将验证问题转换为 LLM 可理解的反馈
        """
        # 格式化问题列表
        issues_text = self._format_issues(validation_result.issues)
        
        # 构建反馈提示
        feedback = self.config.feedback_template.format(
            issues=issues_text,
            original_input=str(original_input)[:2000],  # 限制长度
            previous_output=str(previous_output)[:2000],
        )
        
        # 调整温度参数（增加随机性）
        base_temp = 0.7
        new_temperature = min(1.0, base_temp + self.config.temperature_increase * attempt)
        
        context = {
            "feedback_prompt": feedback,
            "temperature": new_temperature,
            "attempt": attempt + 1,
            "max_attempts": self.config.max_retries,
            "validation_score": validation_result.score.total_score,
            "issues_count": len(validation_result.issues),
        }
        
        self.retry_history.append({
            "attempt": attempt,
            "score": validation_result.score.total_score,
            "issues": [i.code for i in validation_result.issues],
        })
        
        return context
    
    def _format_issues(self, issues: List) -> str:
        """格式化问题列表为文本"""
        lines = []
        
        # 按严重程度分组
        critical = [i for i in issues if i.severity.value == "critical"]
        errors = [i for i in issues if i.severity.value == "error"]
        warnings = [i for i in issues if i.severity.value == "warning"]
        
        if critical:
            lines.append("【严重问题 - 必须修复】")
            for i in critical:
                lines.append(f"  - [{i.code}] {i.message}")
                if i.suggestion:
                    lines.append(f"    建议: {i.suggestion}")
        
        if errors:
            lines.append("\n【错误 - 建议修复】")
            for i in errors:
                lines.append(f"  - [{i.code}] {i.message}")
                if i.suggestion:
                    lines.append(f"    建议: {i.suggestion}")
        
        if warnings:
            lines.append("\n【警告 - 可选修复】")
            for i in warnings[:5]:  # 限制警告数量
                lines.append(f"  - [{i.code}] {i.message}")
        
        return "\n".join(lines)
    
    def get_retry_summary(self) -> Dict[str, Any]:
        """获取重试历史摘要"""
        if not self.retry_history:
            return {"retried": False}
        
        return {
            "retried": True,
            "total_attempts": len(self.retry_history),
            "score_progression": [h["score"] for h in self.retry_history],
            "final_score": self.retry_history[-1]["score"],
        }