"""
表检查验证器

验证配置表检查规则的质量
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
class TableCheckValidator(BaseValidator):
    """配置表检查规则验证器"""
    
    name = "table_check"
    description = "验证配置表检查规则的质量（Lua语法、规则完整性）"
    weight = 1.0
    
    # Lua 关键字（用于简单语法检查）
    LUA_KEYWORDS = [
        "function", "end", "if", "then", "else", "elseif",
        "for", "while", "do", "return", "local", "nil",
        "true", "false", "and", "or", "not", "in"
    ]
    
    # 常见 Lua 语法错误模式
    LUA_SYNTAX_PATTERNS = [
        (r"function\s+\w*\s*\([^)]*\)\s*[^\n]*(?<!\bend\b)", "函数缺少 end"),
        (r"\bif\b[^\n]*(?<!\bend\b)(?=\n\s*[^\s])", "if 语句缺少 end"),
        (r"\bfor\b[^\n]*(?<!\bend\b)(?=\n\s*[^\s])", "for 循环缺少 end"),
        (r"\(\)", "空括号"),
    ]
    
    async def validate(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> ValidationResult:
        """验证表检查规则"""
        issues = []
        context = context or {}
        
        # 提取检查规则
        rules = self._extract_rules(output_data)
        
        if not rules:
            issues.append(self.create_issue(
                code="NO_CHECK_RULES",
                message="未提取到检查规则",
                severity=ValidationSeverity.CRITICAL,
                suggestion="确保输出了表检查规则"
            ))
            return self._create_failed_result(issues)
        
        for idx, rule in enumerate(rules):
            rule_id = rule.get("id", rule.get("规则ID", f"#{idx+1}"))
            prefix = f"规则[{rule_id}]"
            
            # 1. 验证规则名称
            name = rule.get("name", rule.get("规则名称", ""))
            if not name:
                issues.append(self.create_issue(
                    code="EMPTY_RULE_NAME",
                    message=f"{prefix}: 规则名称为空",
                    severity=ValidationSeverity.ERROR,
                    field=f"rules[{idx}].name",
                    suggestion="规则名称应描述检查目的"
                ))
            
            # 2. 验证目标表
            target_table = rule.get("target_table", rule.get("目标表", ""))
            if not target_table:
                issues.append(self.create_issue(
                    code="MISSING_TARGET_TABLE",
                    message=f"{prefix}: 未指定目标表",
                    severity=ValidationSeverity.CRITICAL,
                    field=f"rules[{idx}].target_table",
                    suggestion="指定要检查的配置表名称"
                ))
            
            # 3. 验证检查类型
            check_type = rule.get("check_type", rule.get("检查类型", ""))
            valid_types = ["lua", "range", "enum", "reference", "unique", "not_empty"]
            if not check_type:
                issues.append(self.create_issue(
                    code="MISSING_CHECK_TYPE",
                    message=f"{prefix}: 未指定检查类型",
                    severity=ValidationSeverity.ERROR,
                    field=f"rules[{idx}].check_type",
                    suggestion=f"检查类型: {', '.join(valid_types)}"
                ))
            elif check_type.lower() not in valid_types:
                issues.append(self.create_issue(
                    code="INVALID_CHECK_TYPE",
                    message=f"{prefix}: 未知的检查类型 '{check_type}'",
                    severity=ValidationSeverity.WARNING,
                    field=f"rules[{idx}].check_type",
                    suggestion=f"使用标准类型: {', '.join(valid_types)}"
                ))
            
            # 4. 验证 Lua 脚本（如果是 Lua 类型）
            if check_type and check_type.lower() == "lua":
                lua_script = rule.get("lua_script", rule.get("脚本", rule.get("check_script", "")))
                
                if not lua_script:
                    issues.append(self.create_issue(
                        code="EMPTY_LUA_SCRIPT",
                        message=f"{prefix}: Lua 脚本为空",
                        severity=ValidationSeverity.CRITICAL,
                        field=f"rules[{idx}].lua_script",
                        suggestion="提供 Lua 检查脚本"
                    ))
                else:
                    # 简单 Lua 语法检查
                    lua_issues = self._check_lua_syntax(lua_script)
                    for lua_issue in lua_issues:
                        issues.append(self.create_issue(
                            code=f"LUA_SYNTAX_ERROR",
                            message=f"{prefix}: {lua_issue}",
                            severity=ValidationSeverity.ERROR,
                            field=f"rules[{idx}].lua_script"
                        ))
                    
                    # 检查是否包含必要元素
                    if "nErrorTable" not in lua_script and "error" not in lua_script.lower():
                        issues.append(self.create_issue(
                            code="MISSING_ERROR_REPORTING",
                            message=f"{prefix}: Lua 脚本缺少错误报告",
                            severity=ValidationSeverity.WARNING,
                            field=f"rules[{idx}].lua_script",
                            suggestion="使用 nErrorTable 或 error() 报告错误"
                        ))
            
            # 5. 验证错误消息
            error_msg = rule.get("error_message", rule.get("错误提示", ""))
            if not error_msg:
                issues.append(self.create_issue(
                    code="MISSING_ERROR_MESSAGE",
                    message=f"{prefix}: 缺少错误提示信息",
                    severity=ValidationSeverity.WARNING,
                    field=f"rules[{idx}].error_message",
                    suggestion="提供清晰的错误提示，帮助定位问题"
                ))
            
            # 6. 验证适用列
            columns = rule.get("columns", rule.get("适用列", []))
            if isinstance(columns, str):
                columns = [columns]
            
            if not columns:
                issues.append(self.create_issue(
                    code="NO_TARGET_COLUMNS",
                    message=f"{prefix}: 未指定适用列",
                    severity=ValidationSeverity.WARNING,
                    field=f"rules[{idx}].columns",
                    suggestion="指定要检查的列名"
                ))
            
            # 7. 检测占位符
            all_text = f"{name} {str(rule.get('description', ''))} {error_msg}"
            if self._has_placeholder(all_text):
                issues.append(self.create_issue(
                    code="PLACEHOLDER_CONTENT",
                    message=f"{prefix}: 内容中包含占位符",
                    severity=ValidationSeverity.ERROR,
                    suggestion="移除所有[待补充]、[TODO]等占位符"
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
                "lua_quality": 100 - len([i for i in issues if "LUA" in i.code]) * 15,
                "usability": 100 - len([i for i in issues if i.code == "MISSING_ERROR_MESSAGE"]) * 10,
            },
            passed=passed,
            threshold=70.0
        )
        
        if score.passed:
            return ValidationResult.passed(score, {"rule_count": len(rules)})
        
        return ValidationResult.failed(issues, score, {"rule_count": len(rules)})
    
    def _extract_rules(self, data: Any) -> List[Dict]:
        """提取检查规则列表"""
        return self.extract_items(
            data,
            list_keys=["rules", "check_rules", "检查规则", "rules_list"],
            item_identifier="name"
        )
    
    def _check_lua_syntax(self, script: str) -> List[str]:
        """简单 Lua 语法检查"""
        issues = []
        
        # 检查括号匹配
        open_parens = script.count("(")
        close_parens = script.count(")")
        if open_parens != close_parens:
            issues.append(f"括号不匹配: {open_parens} 开括号, {close_parens} 闭括号")
        
        open_braces = script.count("{")
        close_braces = script.count("}")
        if open_braces != close_braces:
            issues.append(f"花括号不匹配: {open_braces} 开括号, {close_braces} 闭括号")
        
        # 检查关键字匹配（简单检查）
        function_count = len(re.findall(r'\bfunction\b', script))
        end_count = len(re.findall(r'\bend\b', script))
        
        # 考虑 if/for/while 也需要 end
        if_count = len(re.findall(r'\bif\b', script))
        for_count = len(re.findall(r'\bfor\b', script))
        while_count = len(re.findall(r'\bwhile\b', script))
        
        expected_ends = if_count + for_count + while_count + function_count
        if end_count < expected_ends:
            issues.append(f"可能缺少 'end' 关键字（期望 {expected_ends} 个，实际 {end_count} 个）")
        
        # 检查常见错误模式
        if "==" not in script and "=" in script:
            # 可能有赋值误用为比较
            assignments = len(re.findall(r'[^=!]=(?!=)', script))
            if assignments > 0:
                issues.append(f"检测到 {assignments} 处赋值操作，确认是否应为比较(==)")
        
        return issues
