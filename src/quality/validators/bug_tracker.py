"""
Bug 追踪验证器

验证 Bug 报告的质量
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
class BugReportValidator(BaseValidator):
    """Bug 报告验证器"""
    
    name = "bug_report"
    description = "验证 Bug 报告的质量（描述完整性、复现步骤清晰度）"
    weight = 1.0
    
    # 最小字段长度要求
    MIN_TITLE_LENGTH = 10
    MIN_DESCRIPTION_LENGTH = 30
    MIN_REPRODUCE_STEPS = 2
    MIN_STEP_LENGTH = 10
    
    # 有效严重程度
    VALID_SEVERITIES = ["致命", "严重", "一般", "轻微", "建议", "Critical", "Major", "Minor", "Trivial"]
    
    # 有效优先级
    VALID_PRIORITIES = ["P0", "P1", "P2", "P3", "紧急", "高", "中", "低"]
    
    async def validate(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """验证 Bug 报告"""
        issues = []
        context = context or {}
        
        # 提取 Bug 报告
        bugs = self._extract_bugs(output_data)
        
        if not bugs:
            issues.append(self.create_issue(
                code="NO_BUG_REPORTS",
                message="未提取到 Bug 报告",
                severity=ValidationSeverity.CRITICAL,
                suggestion="确保输出了 Bug 数据"
            ))
            return self._create_failed_result(issues)
        
        for idx, bug in enumerate(bugs):
            bug_id = bug.get("id", bug.get("Bug编号", f"#{idx+1}"))
            prefix = f"Bug[{bug_id}]"
            
            # 1. 验证标题
            title = bug.get("title", bug.get("Bug标题", bug.get("标题", "")))
            if not title:
                issues.append(self.create_issue(
                    code="EMPTY_BUG_TITLE",
                    message=f"{prefix}: Bug 标题为空",
                    severity=ValidationSeverity.CRITICAL,
                    field=f"bugs[{idx}].title",
                    suggestion="Bug 标题应简洁描述问题"
                ))
            elif len(str(title)) < self.MIN_TITLE_LENGTH:
                issues.append(self.create_issue(
                    code="SHORT_BUG_TITLE",
                    message=f"{prefix}: Bug 标题过短（{len(str(title))}字符）",
                    severity=ValidationSeverity.ERROR,
                    field=f"bugs[{idx}].title",
                    suggestion=f"标题应至少{self.MIN_TITLE_LENGTH}个字符"
                ))
            
            # 2. 验证描述
            description = bug.get("description", bug.get("Bug描述", bug.get("描述", "")))
            if not description:
                issues.append(self.create_issue(
                    code="EMPTY_DESCRIPTION",
                    message=f"{prefix}: Bug 描述为空",
                    severity=ValidationSeverity.CRITICAL,
                    field=f"bugs[{idx}].description",
                    suggestion="详细描述 Bug 的现象、影响范围"
                ))
            elif len(str(description)) < self.MIN_DESCRIPTION_LENGTH:
                issues.append(self.create_issue(
                    code="SHORT_DESCRIPTION",
                    message=f"{prefix}: Bug 描述过短（{len(str(description))}字符）",
                    severity=ValidationSeverity.ERROR,
                    field=f"bugs[{idx}].description",
                    suggestion=f"描述应至少{self.MIN_DESCRIPTION_LENGTH}个字符"
                ))
            
            # 3. 验证复现步骤
            steps = bug.get("reproduce_steps", bug.get("复现步骤", bug.get("steps", [])))
            if isinstance(steps, str):
                steps = [steps]
            
            if not steps:
                issues.append(self.create_issue(
                    code="NO_REPRODUCE_STEPS",
                    message=f"{prefix}: 缺少复现步骤",
                    severity=ValidationSeverity.CRITICAL,
                    field=f"bugs[{idx}].reproduce_steps",
                    suggestion="提供清晰的复现步骤，便于开发人员定位问题"
                ))
            elif len(steps) < self.MIN_REPRODUCE_STEPS:
                issues.append(self.create_issue(
                    code="INSUFFICIENT_STEPS",
                    message=f"{prefix}: 复现步骤不足（{len(steps)}步，建议至少{self.MIN_REPRODUCE_STEPS}步）",
                    severity=ValidationSeverity.WARNING,
                    field=f"bugs[{idx}].reproduce_steps",
                    suggestion="补充更多复现细节"
                ))
            else:
                # 检查每个步骤的描述长度
                for step_idx, step in enumerate(steps):
                    step_text = str(step)
                    if len(step_text) < self.MIN_STEP_LENGTH:
                        issues.append(self.create_issue(
                            code="SHORT_STEP",
                            message=f"{prefix}: 步骤{step_idx+1}描述过短",
                            severity=ValidationSeverity.WARNING,
                            field=f"bugs[{idx}].reproduce_steps[{step_idx}]",
                            suggestion=f"步骤描述应至少{self.MIN_STEP_LENGTH}个字符"
                        ))
            
            # 4. 验证预期结果与实际结果
            expected = bug.get("expected_result", bug.get("预期结果", ""))
            actual = bug.get("actual_result", bug.get("实际结果", ""))
            
            if not expected:
                issues.append(self.create_issue(
                    code="MISSING_EXPECTED_RESULT",
                    message=f"{prefix}: 缺少预期结果",
                    severity=ValidationSeverity.ERROR,
                    field=f"bugs[{idx}].expected_result",
                    suggestion="描述正常情况下应该出现的结果"
                ))
            
            if not actual:
                issues.append(self.create_issue(
                    code="MISSING_ACTUAL_RESULT",
                    message=f"{prefix}: 缺少实际结果",
                    severity=ValidationSeverity.ERROR,
                    field=f"bugs[{idx}].actual_result",
                    suggestion="描述实际出现的错误现象"
                ))
            
            # 5. 验证严重程度
            severity = bug.get("severity", bug.get("严重程度", ""))
            if not severity:
                issues.append(self.create_issue(
                    code="MISSING_SEVERITY",
                    message=f"{prefix}: 未设置严重程度",
                    severity=ValidationSeverity.ERROR,
                    field=f"bugs[{idx}].severity",
                    suggestion=f"严重程度: {', '.join(self.VALID_SEVERITIES[:4])}"
                ))
            elif str(severity) not in self.VALID_SEVERITIES:
                issues.append(self.create_issue(
                    code="INVALID_SEVERITY",
                    message=f"{prefix}: 无效的严重程度 '{severity}'",
                    severity=ValidationSeverity.WARNING,
                    field=f"bugs[{idx}].severity",
                    suggestion=f"使用标准严重程度: {', '.join(self.VALID_SEVERITIES[:4])}"
                ))
            
            # 6. 验证优先级
            priority = bug.get("priority", bug.get("优先级", ""))
            if priority and str(priority).upper() not in [p.upper() for p in self.VALID_PRIORITIES]:
                issues.append(self.create_issue(
                    code="INVALID_PRIORITY",
                    message=f"{prefix}: 无效的优先级 '{priority}'",
                    severity=ValidationSeverity.WARNING,
                    field=f"bugs[{idx}].priority",
                    suggestion=f"优先级: {', '.join(self.VALID_PRIORITIES[:4])}"
                ))
            
            # 7. 检测占位符
            all_text = f"{title} {description} {str(steps)}"
            if self._has_placeholder(all_text):
                issues.append(self.create_issue(
                    code="PLACEHOLDER_CONTENT",
                    message=f"{prefix}: 内容中包含占位符",
                    severity=ValidationSeverity.ERROR,
                    suggestion="移除所有[待补充]、[TODO]等占位符"
                ))
            
            # 8. 验证环境信息（可选但推荐）
            environment = bug.get("environment", bug.get("测试环境", ""))
            if not environment:
                issues.append(self.create_issue(
                    code="MISSING_ENVIRONMENT",
                    message=f"{prefix}: 缺少测试环境信息",
                    severity=ValidationSeverity.INFO,
                    suggestion="建议提供设备型号、系统版本、应用版本"
                ))
        
        # 计算得分
        score_value = self.calculate_score(issues)
        passed = score_value >= 70.0 and not any(
            i.severity == ValidationSeverity.CRITICAL for i in issues
        )
        
        score = QualityScore(
            total_score=score_value,
            dimension_scores={
                "completeness": max(0, 100 - len([i for i in issues if i.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]]) * 10),
                "clarity": 100 - len([i for i in issues if i.code in ["SHORT_STEP", "SHORT_DESCRIPTION"]]) * 5,
                "actionability": 100 if all(bug.get("reproduce_steps") for bug in bugs) else 50,
            },
            passed=passed,
            threshold=70.0
        )
        
        if score.passed:
            return ValidationResult.passed(score, {"bug_count": len(bugs)})
        
        return ValidationResult.failed(issues, score, {"bug_count": len(bugs)})
    
    def _extract_bugs(self, data: Any) -> List[Dict]:
        """提取 Bug 列表"""
        return self.extract_items(
            data, 
            list_keys=["bugs", "bug_list", "Bug列表", "缺陷列表"],
            item_identifier="title"
        )
