"""
质量验证引擎

核心协调器，管理验证流程和重试逻辑
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from src.quality.validator import (
    ValidationResult, QualityScore, ValidatorRegistry, BaseValidator
)
from src.quality.retry import RetryStrategy, RetryConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QualityReport:
    """完整质量报告"""
    success: bool                      # 最终是否成功
    final_output: Any                  # 最终输出
    validation_results: List[ValidationResult]  # 所有验证结果
    retry_summary: Dict[str, Any]      # 重试摘要
    execution_time_ms: int             # 执行时间
    metadata: Dict[str, Any]           # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "validation_results": [v.to_dict() for v in self.validation_results],
            "retry_summary": self.retry_summary,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


class QualityEngine:
    """
    质量验证引擎
    
    协调验证器和重试策略，确保输出质量
    
    使用示例：
        ```python
        engine = QualityEngine()
        
        # 配置验证流水线
        engine.configure_pipeline([
            "json_syntax",
            "test_case_semantic",
            "excel_structure",
        ])
        
        # 执行带验证的生成
        report = await engine.execute(
            input_data=requirement_doc,
            generator=agent.generate_test_cases,
            max_retries=3
        )
        
        if report.success:
            print("生成成功！", report.final_output)
        else:
            print("生成失败，请人工复核")
            print(report.validation_results[-1].issues)
        ```
    """
    
    def __init__(self):
        self.validators: List[BaseValidator] = []
        self.retry_strategy: Optional[RetryStrategy] = None
        self.logger = get_logger(f"{__name__}.QualityEngine")
    
    def configure_pipeline(
        self, 
        validator_names: List[str],
        validator_configs: Dict[str, Dict] = None
    ) -> "QualityEngine":
        """
        配置验证流水线
        
        Args:
            validator_names: 验证器名称列表
            validator_configs: 各验证器的配置
            
        Returns:
            self，支持链式调用
        """
        self.validators = ValidatorRegistry.create_pipeline(
            validator_names, 
            validator_configs
        )
        self.logger.info(f"Pipeline configured with {len(self.validators)} validators")
        return self
    
    def configure_retry(self, config: RetryConfig) -> "QualityEngine":
        """
        配置重试策略
        
        Args:
            config: 重试配置
            
        Returns:
            self，支持链式调用
        """
        self.retry_strategy = RetryStrategy(config)
        return self
    
    async def execute(
        self,
        input_data: Any,
        generator: Callable,
        generator_params: Dict[str, Any] = None,
        max_retries: int = 3,
        validation_context: Dict[str, Any] = None
    ) -> QualityReport:
        """
        执行带质量验证的生成
        
        Args:
            input_data: 原始输入
            generator: 生成函数（如 agent.execute）
            generator_params: 生成函数参数
            max_retries: 最大重试次数
            validation_context: 验证上下文
            
        Returns:
            QualityReport 完整质量报告
        """
        start_time = datetime.now()
        generator_params = generator_params or {}
        validation_context = validation_context or {}
        
        # 初始化重试策略
        if not self.retry_strategy:
            self.retry_strategy = RetryStrategy(RetryConfig(max_retries=max_retries))
        
        attempt = 0
        all_results: List[ValidationResult] = []
        current_output = None
        
        while attempt <= max_retries:
            self.logger.info(f"Generation attempt {attempt + 1}/{max_retries + 1}")
            
            try:
                # 1. 执行生成
                if attempt == 0:
                    # 首次生成
                    current_output = await generator(input_data, **generator_params)
                else:
                    # 重试：使用反馈增强的输入
                    retry_context = self.retry_strategy.build_retry_context(
                        input_data, current_output, all_results[-1], attempt
                    )
                    
                    # 将反馈加入生成参数
                    enhanced_input = {
                        "original_input": input_data,
                        "feedback": retry_context["feedback_prompt"],
                        "previous_output": current_output,
                    }
                    
                    # 调整温度参数
                    if "temperature" in generator_params:
                        generator_params["temperature"] = retry_context["temperature"]
                    
                    current_output = await generator(enhanced_input, **generator_params)
                
                # 2. 执行验证流水线
                validation_result = await self._run_validation_pipeline(
                    input_data, current_output, validation_context
                )
                all_results.append(validation_result)
                
                # 3. 判断是否通过
                if validation_result.success:
                    self.logger.info(f"Validation passed on attempt {attempt + 1}")
                    break
                
                # 4. 判断是否需要重试
                if not self.retry_strategy.should_retry(validation_result, attempt):
                    self.logger.warning(f"Retry strategy decided to stop at attempt {attempt + 1}")
                    break
                
                attempt += 1
                
            except Exception as e:
                self.logger.error(f"Generation/validation failed: {e}")
                attempt += 1
                if attempt > max_retries:
                    break
        
        # 计算执行时间
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 构建最终报告
        final_success = all_results[-1].success if all_results else False
        
        report = QualityReport(
            success=final_success,
            final_output=current_output if final_success else None,
            validation_results=all_results,
            retry_summary=self.retry_strategy.get_retry_summary(),
            execution_time_ms=execution_time,
            metadata={
                "total_attempts": attempt + 1,
                "validator_count": len(self.validators),
                "final_score": all_results[-1].score.total_score if all_results else 0,
            }
        )
        
        self._log_report(report)
        return report
    
    async def _run_validation_pipeline(
        self,
        input_data: Any,
        output_data: Any,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        运行验证流水线
        
        所有验证器并行执行，合并结果
        """
        import asyncio
        
        if not self.validators:
            # 没有配置验证器，直接通过
            return ValidationResult.passed(
                QualityScore(100.0, {}, True, 0.0),
                {"note": "No validators configured"}
            )
        
        # 并行执行所有验证器
        validation_tasks = [
            validator.validate(input_data, output_data, context)
            for validator in self.validators
        ]
        
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        # 合并结果
        all_issues = []
        dimension_scores = {}
        total_weight = 0.0
        weighted_score = 0.0
        
        for validator, result in zip(self.validators, results):
            if isinstance(result, Exception):
                self.logger.error(f"Validator {validator.name} failed: {result}")
                continue
            
            all_issues.extend(result.issues)
            dimension_scores[validator.name] = result.score.total_score
            
            # 加权计算总分
            weighted_score += result.score.total_score * validator.weight
            total_weight += validator.weight
        
        # 计算最终分数
        final_score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        # 判断是否通过：所有验证都通过且没有严重问题
        passed = all(r.success for r in results if not isinstance(r, Exception))
        passed = passed and not any(i.severity.value == "critical" for i in all_issues)
        
        # 阈值取所有验证器中最高的
        threshold = max(
            (r.score.threshold for r in results if not isinstance(r, Exception)),
            default=60.0
        )
        
        score = QualityScore(
            total_score=final_score,
            dimension_scores=dimension_scores,
            passed=passed and final_score >= threshold,
            threshold=threshold
        )
        
        if score.passed:
            return ValidationResult.passed(score, {"dimensions": list(dimension_scores.keys())})
        else:
            return ValidationResult.failed(all_issues, score, {"dimensions": list(dimension_scores.keys())})
    
    def _log_report(self, report: QualityReport):
        """记录质量报告"""
        if report.success:
            self.logger.info(
                f"Quality check PASSED | "
                f"Score: {report.validation_results[-1].score.total_score:.1f} | "
                f"Attempts: {report.retry_summary.get('total_attempts', 1)} | "
                f"Time: {report.execution_time_ms}ms"
            )
        else:
            self.logger.warning(
                f"Quality check FAILED | "
                f"Final Score: {report.validation_results[-1].score.total_score:.1f} | "
                f"Issues: {report.validation_results[-1].error_count} errors | "
                f"Attempts: {report.retry_summary.get('total_attempts', 1)}"
            )
    
    def get_validator_status(self) -> List[Dict[str, Any]]:
        """获取验证器状态"""
        return [
            {
                "name": v.name,
                "description": v.description,
                "weight": v.weight,
            }
            for v in self.validators
        ]