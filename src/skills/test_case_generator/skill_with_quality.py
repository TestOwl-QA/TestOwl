"""
带质量验证的测试用例生成技能

在原有技能基础上增加自动验证和重试机制
"""

from typing import Any, Dict, List

from src.skills.test_case_generator.skill import TestCaseGeneratorSkill
from src.skills.base import SkillContext, SkillResult
from src.quality.engine import QualityEngine, QualityReport
from src.quality.retry import RetryConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class QualityAssuredTestCaseGenerator(TestCaseGeneratorSkill):
    """
    带质量保障的测试用例生成器
    
    自动生成 + 自动验证 + 自动重试
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.quality_engine = QualityEngine()
        
        # 配置验证流水线
        self.quality_engine.configure_pipeline([
            "json_syntax",           # 验证 JSON 格式
            "test_case_semantic",    # 验证用例语义
        ])
        
        # 配置重试策略
        self.quality_engine.configure_retry(RetryConfig(
            max_retries=3,
            temperature_increase=0.1
        ))
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行带质量验证的测试用例生成
        """
        # 获取输入参数
        analysis_result = context.get_param("analysis_result")
        test_points = context.get_param("test_points")
        requirements_text = context.get_param("requirements_text")
        output_format = context.get_param("output_format", "excel")
        output_path = context.get_param("output_path")
        
        # 准备生成器参数
        generator_params = {
            "output_format": output_format,
            "output_path": output_path,
            "module_name": context.get_param("module_name", "默认模块"),
        }
        
        # 准备输入数据
        if analysis_result:
            input_data = {"type": "analysis_result", "data": analysis_result}
        elif test_points:
            input_data = {"type": "test_points", "data": test_points}
        elif requirements_text:
            input_data = {"type": "requirements", "data": requirements_text}
        else:
            return SkillResult.fail("请提供 analysis_result、test_points 或 requirements_text")
        
        # 执行带验证的生成
        report: QualityReport = await self.quality_engine.execute(
            input_data=input_data,
            generator=self._generate_with_wrapper,
            generator_params=generator_params,
            max_retries=3,
            validation_context={
                "output_format": output_format,
                "file_path": output_path,
            }
        )
        
        # 处理结果
        if report.success:
            return SkillResult.ok(data={
                "test_suite": report.final_output,
                "quality_report": report.to_dict(),
                "exported_path": output_path,
            })
        else:
            # 生成失败，返回详细错误信息
            last_validation = report.validation_results[-1] if report.validation_results else None
            
            error_msg = "测试用例生成未通过质量验证\n\n"
            
            if last_validation:
                error_msg += f"最终得分: {last_validation.score.total_score:.1f}/100\n"
                error_msg += f"问题统计: {last_validation.error_count} 个错误, {last_validation.warning_count} 个警告\n\n"
                
                if last_validation.issues:
                    error_msg += "主要问题:\n"
                    for issue in last_validation.issues[:5]:  # 只显示前5个
                        error_msg += f"  - [{issue.severity.value}] {issue.message}\n"
            
            error_msg += f"\n重试次数: {report.retry_summary.get('total_attempts', 1)}"
            
            return SkillResult.fail(error_msg)
    
    async def _generate_with_wrapper(self, input_data: Dict, **kwargs) -> Any:
        """
        包装原有的生成逻辑
        
        适配 QualityEngine 的调用签名
        """
        # 创建临时 SkillContext
        from src.skills.base import SkillContext
        from src.core.config import get_config
        
        temp_context = SkillContext(
            agent=None,
            config=get_config(),
            params={
                "analysis_result": input_data.get("data") if input_data.get("type") == "analysis_result" else None,
                "test_points": input_data.get("data") if input_data.get("type") == "test_points" else None,
                "requirements_text": input_data.get("data") if input_data.get("type") == "requirements" else None,
                **kwargs
            }
        )
        
        # 调用父类的生成逻辑
        result = await super().execute(temp_context)
        
        if result.success:
            return result.data
        else:
            raise ValueError(f"Generation failed: {result.error}")


# 兼容原有接口的快捷函数
async def generate_test_cases_with_quality(
    input_data: Any,
    output_format: str = "excel",
    output_path: str = None,
    max_retries: int = 3
) -> SkillResult:
    """
    带质量验证的测试用例生成快捷函数
    
    使用示例:
        ```python
        result = await generate_test_cases_with_quality(
            input_data=requirement_doc,
            output_format="excel",
            output_path="测试用例.xlsx"
        )
        
        if result.success:
            print("生成成功！")
            print(result.data["quality_report"])
        else:
            print("生成失败:", result.error)
        ```
    """
    from src.core.config import get_config
    
    skill = QualityAssuredTestCaseGenerator(get_config())
    
    from src.skills.base import SkillContext
    context = SkillContext(
        agent=None,
        config=get_config(),
        params={
            "requirements_text": input_data if isinstance(input_data, str) else None,
            "output_format": output_format,
            "output_path": output_path,
        }
    )
    
    return await skill.execute(context)