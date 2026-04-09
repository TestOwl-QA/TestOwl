"""
语义验证器

验证输出内容的语义合理性
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
class TestCaseSemanticValidator(BaseValidator):
    """测试用例语义验证器"""
    
    name = "test_case_semantic"
    description = "验证测试用例内容的语义合理性"
    weight = 1.0
    
    # 敏感词/无效内容检测
    INVALID_PATTERNS = [
        r"待补充", r"TODO", r"FIXME", r"待定", r"待确认",
        r"\[.*?\]",  # 方括号占位符如 [填写]
        r"请.*?填写", r"请.*?补充",
    ]
    
    # 测试步骤最小字数要求
    MIN_STEP_LENGTH = 10
    
    # 预期结果最小字数要求
    MIN_EXPECTED_LENGTH = 5
    
    async def validate(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """验证测试用例语义"""
        issues = []
        context = context or {}
        
        # 获取测试用例列表
        test_cases = self._extract_test_cases(output_data)
        
        if not test_cases:
            issues.append(self.create_issue(
                code="NO_TEST_CASES",
                message="未提取到有效的测试用例",
                severity=ValidationSeverity.CRITICAL,
                suggestion="确保输出包含测试用例数据"
            ))
            score = QualityScore(
                total_score=0.0,
                dimension_scores={"semantic": 0.0},
                passed=False,
                threshold=70.0
            )
            return ValidationResult.failed(issues, score)
        
        for idx, tc in enumerate(test_cases):
            case_id = tc.get("id", tc.get("用例编号", f"#{idx+1}"))
            prefix = f"用例[{case_id}]"
            
            # 1. 验证标题
            title = tc.get("title", tc.get("用例标题", ""))
            if not title or len(title.strip()) < 5:
                issues.append(self.create_issue(
                    code="EMPTY_TITLE",
                    message=f"{prefix}: 用例标题过短或为空",
                    severity=ValidationSeverity.ERROR,
                    field=f"test_cases[{idx}].title",
                    suggestion="标题应清晰描述测试目的，至少5个字符"
                ))
            
            # 2. 验证测试步骤
            steps = tc.get("steps", tc.get("测试步骤", []))
            if isinstance(steps, str):
                steps = [steps]
            
            if not steps:
                issues.append(self.create_issue(
                    code="NO_STEPS",
                    message=f"{prefix}: 缺少测试步骤",
                    severity=ValidationSeverity.CRITICAL,
                    field=f"test_cases[{idx}].steps",
                    suggestion="每个用例必须包含可执行的测试步骤"
                ))
            else:
                for step_idx, step in enumerate(steps):
                    step_text = step.get("action", step) if isinstance(step, dict) else str(step)
                    if len(str(step_text).strip()) < self.MIN_STEP_LENGTH:
                        issues.append(self.create_issue(
                            code="SHORT_STEP",
                            message=f"{prefix}: 步骤{step_idx+1}描述过短",
                            severity=ValidationSeverity.WARNING,
                            field=f"test_cases[{idx}].steps[{step_idx}]",
                            suggestion=f"步骤描述应详细，至少{self.MIN_STEP_LENGTH}个字符"
                        ))
            
            # 3. 验证预期结果
            expected = tc.get("expected_result", tc.get("预期结果", ""))
            if isinstance(expected, list):
                expected = " ".join(str(e) for e in expected)
            
            if not expected or len(str(expected).strip()) < self.MIN_EXPECTED_LENGTH:
                issues.append(self.create_issue(
                    code="WEAK_EXPECTED_RESULT",
                    message=f"{prefix}: 预期结果描述不足",
                    severity=ValidationSeverity.ERROR,
                    field=f"test_cases[{idx}].expected_result",
                    suggestion="预期结果应明确、可验证"
                ))
            
            # 4. 检测无效内容
            all_text = f"{title} {str(steps)} {expected}"
            for pattern in self.INVALID_PATTERNS:
                matches = re.findall(pattern, all_text)
                if matches:
                    issues.append(self.create_issue(
                        code="PLACEHOLDER_CONTENT",
                        message=f"{prefix}: 检测到占位符内容: {matches[0]}",
                        severity=ValidationSeverity.ERROR,
                        field=f"test_cases[{idx}].content",
                        suggestion="移除所有占位符，填写实际内容"
                    ))
                    break  # 每个用例只报一次
            
            # 5. 验证优先级
            priority = tc.get("priority", tc.get("优先级", ""))
            valid_priorities = ["P0", "P1", "P2", "P3", "p0", "p1", "p2", "p3"]
            if priority and str(priority).upper() not in valid_priorities:
                issues.append(self.create_issue(
                    code="INVALID_PRIORITY",
                    message=f"{prefix}: 无效的优先级 '{priority}'",
                    severity=ValidationSeverity.WARNING,
                    field=f"test_cases[{idx}].priority",
                    suggestion="优先级应为 P0/P1/P2/P3"
                ))
        
        # 6. 验证用例覆盖度（基于输入）
        if input_data and isinstance(input_data, str):
            input_keywords = self._extract_keywords(input_data)
            covered_keywords = self._check_keyword_coverage(input_keywords, test_cases)
            
            coverage_rate = len(covered_keywords) / len(input_keywords) if input_keywords else 1.0
            if coverage_rate < 0.5:
                issues.append(self.create_issue(
                    code="LOW_COVERAGE",
                    message=f"需求覆盖率较低 ({coverage_rate:.0%})",
                    severity=ValidationSeverity.WARNING,
                    suggestion="增加测试用例以覆盖更多需求点"
                ))
        
        score_value = self.calculate_score(issues)
        # 语义验证要求更高，阈值设为70
        # 通过条件：得分>=70 且 没有严重错误
        passed = score_value >= 70.0 and not any(
            i.severity == ValidationSeverity.CRITICAL for i in issues
        )
        
        score = QualityScore(
            total_score=score_value,
            dimension_scores={
                "semantic": score_value,
                "completeness": max(0, 100 - len([i for i in issues if i.code in ["NO_STEPS", "EMPTY_TITLE"]]) * 20),
                "coverage": coverage_rate * 100 if 'coverage_rate' in dir() else 100.0,
            },
            passed=passed,
            threshold=70.0
        )
        
        # 通过条件：score.passed 为 True
        if score.passed:
            return ValidationResult.passed(score, {"test_case_count": len(test_cases)})
        
        return ValidationResult.failed(issues, score, {"test_case_count": len(test_cases)})
    
    def _extract_test_cases(self, data: Any) -> List[Dict]:
        """从各种格式中提取测试用例列表"""
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            # 尝试各种可能的字段名
            for key in ["test_cases", "testCases", "用例", "cases", "data"]:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        return value
            # 如果 dict 本身看起来像用例
            if "title" in data or "用例标题" in data:
                return [data]
        
        return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从需求文本中提取关键词"""
        # 简单的关键词提取：名词短语
        # 实际项目中可以使用 NLP 库如 jieba
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)  # 提取中文词组
        return list(set(words))[:50]  # 去重，限制数量
    
    def _check_keyword_coverage(self, keywords: List[str], test_cases: List[Dict]) -> List[str]:
        """检查关键词在测试用例中的覆盖情况"""
        covered = []
        all_case_text = " ".join(str(tc) for tc in test_cases)
        
        for kw in keywords:
            if kw in all_case_text:
                covered.append(kw)
        
        return covered