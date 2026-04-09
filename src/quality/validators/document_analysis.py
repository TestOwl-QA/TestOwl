"""
文档分析验证器

验证文档分析结果的质量
"""

import re
from typing import Any, Dict, List

from src.quality.validator import (
    BaseValidator, ValidationResult, ValidationIssue,
    QualityScore, ValidationSeverity, ValidatorRegistry
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register
class DocumentAnalysisValidator(BaseValidator):
    """文档分析结果验证器"""
    
    name = "document_analysis"
    description = "验证文档分析结果的质量（测试点覆盖度、分类合理性）"
    weight = 1.0
    
    # 最小测试点数量（根据文档长度动态计算）
    MIN_TEST_POINTS_RATIO = 0.05  # 每100字至少0.5个测试点
    
    # 有效分类列表
    VALID_CATEGORIES = [
        "功能测试", "性能测试", "兼容性测试", "安全测试",
        "UI测试", "接口测试", "边界测试", "异常测试",
        "流程测试", "数据测试", "配置测试", "回归测试"
    ]
    
    async def validate(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """验证文档分析结果"""
        issues = []
        context = context or {}
        
        # 提取分析结果
        analysis = self._extract_analysis(output_data)
        
        if not analysis:
            issues.append(self.create_issue(
                code="NO_ANALYSIS_RESULT",
                message="未提取到文档分析结果",
                severity=ValidationSeverity.CRITICAL,
                suggestion="确保输出了文档分析数据"
            ))
            return self._create_failed_result(issues)
        
        # 1. 验证测试点存在
        test_points = analysis.get("test_points", [])
        if not test_points:
            issues.append(self.create_issue(
                code="NO_TEST_POINTS",
                message="未提取到测试点",
                severity=ValidationSeverity.CRITICAL,
                suggestion="文档分析应提取至少一个测试点"
            ))
        
        # 2. 验证测试点覆盖度
        input_text = str(input_data) if input_data else ""
        expected_min_points = max(3, int(len(input_text) * self.MIN_TEST_POINTS_RATIO / 100))
        
        if len(test_points) < expected_min_points:
            issues.append(self.create_issue(
                code="LOW_COVERAGE",
                message=f"测试点数量不足（{len(test_points)}个，建议至少{expected_min_points}个）",
                severity=ValidationSeverity.WARNING,
                suggestion="仔细阅读文档，提取更多测试点"
            ))
        
        # 3. 验证每个测试点的完整性
        for idx, point in enumerate(test_points):
            point_id = point.get("id", f"#{idx+1}")
            prefix = f"测试点[{point_id}]"
            
            # 检查描述
            description = point.get("description", point.get("描述", ""))
            if not description or len(str(description).strip()) < 10:
                issues.append(self.create_issue(
                    code="SHORT_DESCRIPTION",
                    message=f"{prefix}: 描述过短或为空",
                    severity=ValidationSeverity.ERROR,
                    field=f"test_points[{idx}].description",
                    suggestion="测试点描述应清晰说明测试内容"
                ))
            
            # 检查分类
            category = point.get("category", point.get("分类", ""))
            if category and category not in self.VALID_CATEGORIES:
                issues.append(self.create_issue(
                    code="INVALID_CATEGORY",
                    message=f"{prefix}: 未知的测试分类 '{category}'",
                    severity=ValidationSeverity.WARNING,
                    field=f"test_points[{idx}].category",
                    suggestion=f"建议使用标准分类: {', '.join(self.VALID_CATEGORIES[:5])}..."
                ))
            
            # 检查优先级
            priority = point.get("priority", point.get("优先级", ""))
            valid_priorities = ["P0", "P1", "P2", "P3", "高", "中", "低"]
            if priority and str(priority).upper() not in valid_priorities:
                issues.append(self.create_issue(
                    code="INVALID_PRIORITY",
                    message=f"{prefix}: 无效的优先级 '{priority}'",
                    severity=ValidationSeverity.WARNING,
                    field=f"test_points[{idx}].priority",
                    suggestion="优先级应为 P0/P1/P2/P3 或 高/中/低"
                ))
            
            # 检测占位符
            if self._has_placeholder(str(description)):
                issues.append(self.create_issue(
                    code="PLACEHOLDER_IN_DESCRIPTION",
                    message=f"{prefix}: 描述中包含占位符",
                    severity=ValidationSeverity.ERROR,
                    field=f"test_points[{idx}].description",
                    suggestion="移除[待补充]、[TODO]等占位符"
                ))
        
        # 4. 验证需求理解准确性
        summary = analysis.get("summary", analysis.get("文档摘要", ""))
        if not summary:
            issues.append(self.create_issue(
                code="MISSING_SUMMARY",
                message="缺少文档摘要",
                severity=ValidationSeverity.WARNING,
                suggestion="提供文档核心内容摘要"
            ))
        elif len(str(summary)) < 20:
            issues.append(self.create_issue(
                code="SHORT_SUMMARY",
                message="文档摘要过短",
                severity=ValidationSeverity.WARNING,
                suggestion="摘要应准确概括文档主要内容"
            ))
        
        # 5. 验证功能模块划分
        modules = analysis.get("modules", analysis.get("功能模块", []))
        if not modules:
            issues.append(self.create_issue(
                code="NO_MODULES",
                message="未识别功能模块",
                severity=ValidationSeverity.WARNING,
                suggestion="根据文档内容划分功能模块"
            ))
        
        # 计算得分
        score_value = self.calculate_score(issues)
        passed = score_value >= 70.0 and not any(
            i.severity == ValidationSeverity.CRITICAL for i in issues
        )
        
        score = QualityScore(
            total_score=score_value,
            dimension_scores={
                "completeness": max(0, 100 - len([i for i in issues if i.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]]) * 15),
                "coverage": min(100, len(test_points) / max(expected_min_points, 1) * 100),
                "accuracy": 100 - len([i for i in issues if i.code.startswith("INVALID")]) * 10,
            },
            passed=passed,
            threshold=70.0
        )
        
        if score.passed:
            return ValidationResult.passed(score, {
                "test_point_count": len(test_points),
                "module_count": len(modules)
            })
        
        return ValidationResult.failed(issues, score, {
            "test_point_count": len(test_points),
            "module_count": len(modules)
        })
    
    def _extract_analysis(self, data: Any) -> Dict:
        """提取分析结果"""
        if isinstance(data, dict):
            return data
        return {}
