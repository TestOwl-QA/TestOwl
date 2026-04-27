"""
配置表检查增强模块 - 提供数据质量检查和校验
"""
import re
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class CheckSeverity(Enum):
    """检查严重程度"""
    ERROR = "error"      # 必须修复
    WARNING = "warning"  # 建议修复
    INFO = "info"        # 提示信息


@dataclass
class CheckResult:
    """检查结果"""
    rule_name: str
    severity: CheckSeverity
    message: str
    location: str  # 如 "Sheet1.A5" 或 "row_10"
    suggestion: str


@dataclass
class ValidationRule:
    """校验规则"""
    name: str
    description: str
    check_func: Any  # 检查函数
    severity: CheckSeverity = CheckSeverity.WARNING


class TableChecker:
    """配置表检查器"""
    
    def __init__(self):
        self.rules = self._init_rules()
    
    def _init_rules(self) -> List[ValidationRule]:
        """初始化默认校验规则"""
        return [
            ValidationRule(
                name="空值检查",
                description="检查必填字段是否为空",
                check_func=self._check_empty_values,
                severity=CheckSeverity.ERROR
            ),
            ValidationRule(
                name="重复ID检查",
                description="检查ID字段是否唯一",
                check_func=self._check_duplicate_ids,
                severity=CheckSeverity.ERROR
            ),
            ValidationRule(
                name="数值范围检查",
                description="检查数值是否在合理范围内",
                check_func=self._check_numeric_range,
                severity=CheckSeverity.WARNING
            ),
            ValidationRule(
                name="引用完整性",
                description="检查外键引用是否存在",
                check_func=self._check_references,
                severity=CheckSeverity.ERROR
            ),
            ValidationRule(
                name="格式规范检查",
                description="检查字段格式是否符合规范",
                check_func=self._check_format,
                severity=CheckSeverity.WARNING
            ),
            ValidationRule(
                name="一致性检查",
                description="检查相关字段之间的一致性",
                check_func=self._check_consistency,
                severity=CheckSeverity.WARNING
            ),
        ]
    
    def check(self, table_data: Dict, table_name: str = "") -> Dict:
        """
        检查配置表
        
        Args:
            table_data: 表格数据，格式：
                {
                    'headers': ['id', 'name', 'value'],
                    'rows': [
                        {'id': '1', 'name': 'item1', 'value': '100'},
                        ...
                    ]
                }
            table_name: 表名
            
        Returns:
            检查报告
        """
        if not table_data or not table_data.get('rows'):
            return {
                'has_data': False,
                'message': '表格数据为空'
            }
        
        all_results = []
        
        for rule in self.rules:
            try:
                results = rule.check_func(table_data, table_name)
                for r in results:
                    r.rule_name = rule.name
                    r.severity = rule.severity
                all_results.extend(results)
            except Exception as e:
                # 规则执行失败不影响其他检查
                all_results.append(CheckResult(
                    rule_name=rule.name,
                    severity=CheckSeverity.INFO,
                    message=f"检查规则执行失败: {str(e)}",
                    location="",
                    suggestion="请检查数据格式"
                ))
        
        # 按严重程度分组
        errors = [r for r in all_results if r.severity == CheckSeverity.ERROR]
        warnings = [r for r in all_results if r.severity == CheckSeverity.WARNING]
        infos = [r for r in all_results if r.severity == CheckSeverity.INFO]
        
        return {
            'has_data': True,
            'table_name': table_name,
            'row_count': len(table_data.get('rows', [])),
            'col_count': len(table_data.get('headers', [])),
            'summary': {
                'total_issues': len(all_results),
                'errors': len(errors),
                'warnings': len(warnings),
                'infos': len(infos)
            },
            'errors': [self._result_to_dict(r) for r in errors],
            'warnings': [self._result_to_dict(r) for r in warnings],
            'infos': [self._result_to_dict(r) for r in infos],
            'health_score': self._calc_health_score(len(errors), len(warnings), len(table_data.get('rows', [])))
        }
    
    def _result_to_dict(self, result: CheckResult) -> Dict:
        """转换结果为字典"""
        return {
            'rule': result.rule_name,
            'severity': result.severity.value,
            'message': result.message,
            'location': result.location,
            'suggestion': result.suggestion
        }
    
    def _calc_health_score(self, errors: int, warnings: int, row_count: int) -> int:
        """计算健康分数 (0-100)"""
        if row_count == 0:
            return 100
        
        # 错误扣10分，警告扣2分
        score = 100 - (errors * 10) - (warnings * 2)
        return max(0, min(100, score))
    
    # ========== 具体检查规则 ==========
    
    def _check_empty_values(self, data: Dict, table_name: str) -> List[CheckResult]:
        """检查空值"""
        results = []
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        
        # 假设第一列是ID，不能为空
        id_col = headers[0] if headers else 'id'
        
        for i, row in enumerate(rows, 1):
            # 检查ID是否为空
            id_val = row.get(id_col, '').strip() if isinstance(row.get(id_col), str) else str(row.get(id_col, ''))
            if not id_val or id_val in ['', 'null', 'NULL', 'None']:
                results.append(CheckResult(
                    rule_name="",
                    severity=CheckSeverity.ERROR,
                    message=f"第{i}行的{id_col}为空",
                    location=f"row_{i}.{id_col}",
                    suggestion=f"请填写{id_col}值，这是必填字段"
                ))
            
            # 检查其他关键字段
            for col in headers[1:]:  # 跳过ID列
                val = row.get(col, '')
                if isinstance(val, str) and val.strip() == '':
                    # 只检查明显为空的字符串字段
                    results.append(CheckResult(
                        rule_name="",
                        severity=CheckSeverity.WARNING,
                        message=f"第{i}行的{col}为空",
                        location=f"row_{i}.{col}",
                        suggestion=f"请确认{col}是否允许为空"
                    ))
        
        return results
    
    def _check_duplicate_ids(self, data: Dict, table_name: str) -> List[CheckResult]:
        """检查重复ID"""
        results = []
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        
        if not headers:
            return results
        
        id_col = headers[0]
        seen_ids = {}
        
        for i, row in enumerate(rows, 1):
            id_val = str(row.get(id_col, '')).strip()
            if id_val:
                if id_val in seen_ids:
                    results.append(CheckResult(
                        rule_name="",
                        severity=CheckSeverity.ERROR,
                        message=f"重复的{id_col}: {id_val}",
                        location=f"row_{i}.{id_col}",
                        suggestion=f"第{seen_ids[id_val]}行已存在相同{id_col}，请确保{id_col}唯一"
                    ))
                else:
                    seen_ids[id_val] = i
        
        return results
    
    def _check_numeric_range(self, data: Dict, table_name: str) -> List[CheckResult]:
        """检查数值范围"""
        results = []
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        
        # 识别数值列（包含value, count, num, price等关键词）
        numeric_cols = [h for h in headers if any(kw in h.lower() for kw in 
                       ['value', 'count', 'num', 'price', 'cost', 'atk', 'def', 'hp', 'damage'])]
        
        for i, row in enumerate(rows, 1):
            for col in numeric_cols:
                val = row.get(col, '')
                if val:
                    try:
                        num_val = float(val)
                        # 检查异常值
                        if abs(num_val) > 1000000:  # 超过百万
                            results.append(CheckResult(
                                rule_name="",
                                severity=CheckSeverity.WARNING,
                                message=f"第{i}行的{col}数值过大: {num_val}",
                                location=f"row_{i}.{col}",
                                suggestion="请确认该数值是否正确，是否存在单位错误"
                            ))
                        elif num_val < 0 and 'price' not in col.lower():  # 负数（价格可以为负表示折扣）
                            results.append(CheckResult(
                                rule_name="",
                                severity=CheckSeverity.WARNING,
                                message=f"第{i}行的{col}为负数: {num_val}",
                                location=f"row_{i}.{col}",
                                suggestion="请确认负数是否符合设计意图"
                            ))
                    except (ValueError, TypeError):
                        # 不是有效数字
                        results.append(CheckResult(
                            rule_name="",
                            severity=CheckSeverity.WARNING,
                            message=f"第{i}行的{col}不是有效数字: {val}",
                            location=f"row_{i}.{col}",
                            suggestion="请检查数值格式"
                        ))
        
        return results
    
    def _check_references(self, data: Dict, table_name: str) -> List[CheckResult]:
        """检查引用完整性（简化版）"""
        results = []
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        
        # 识别可能的引用列（包含_id, ref, target等后缀）
        ref_cols = [h for h in headers if any(h.lower().endswith(suffix) for suffix in 
                   ['_id', '_ref', 'target', 'parent'])]
        
        # 收集本表所有ID作为有效引用目标
        id_col = headers[0] if headers else None
        valid_ids = set()
        if id_col:
            valid_ids = {str(r.get(id_col, '')).strip() for r in rows if r.get(id_col)}
        
        for i, row in enumerate(rows, 1):
            for col in ref_cols:
                ref_val = str(row.get(col, '')).strip()
                if ref_val and ref_val not in ['0', 'null', 'NULL', 'None', '']:
                    # 简单检查：引用值是否看起来像ID
                    if not re.match(r'^[\w\-]+$', ref_val):
                        results.append(CheckResult(
                            rule_name="",
                            severity=CheckSeverity.WARNING,
                            message=f"第{i}行的{col}引用格式异常: {ref_val}",
                            location=f"row_{i}.{col}",
                            suggestion="引用值应只包含字母、数字、下划线和连字符"
                        ))
        
        return results
    
    def _check_format(self, data: Dict, table_name: str) -> List[CheckResult]:
        """检查格式规范"""
        results = []
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        
        # 检查字段名规范（建议小写+下划线）
        for col in headers:
            if col and not re.match(r'^[a-z][a-z0-9_]*$', col):
                results.append(CheckResult(
                    rule_name="",
                    severity=CheckSeverity.INFO,
                    message=f"字段名'{col}'不符合小写+下划线规范",
                    location=f"header.{col}",
                    suggestion="建议使用snake_case命名，如'item_id'而非'ItemID'"
                ))
        
        # 检查字符串值是否有异常空格
        for i, row in enumerate(rows, 1):
            for col in headers:
                val = row.get(col, '')
                if isinstance(val, str):
                    if val != val.strip():
                        results.append(CheckResult(
                            rule_name="",
                            severity=CheckSeverity.WARNING,
                            message=f"第{i}行的{col}包含首尾空格",
                            location=f"row_{i}.{col}",
                            suggestion="建议去除首尾空格，避免匹配问题"
                        ))
                    if '  ' in val:  # 连续空格
                        results.append(CheckResult(
                            rule_name="",
                            severity=CheckSeverity.INFO,
                            message=f"第{i}行的{col}包含连续空格",
                            location=f"row_{i}.{col}",
                            suggestion="建议合并连续空格"
                        ))
        
        return results
    
    def _check_consistency(self, data: Dict, table_name: str) -> List[CheckResult]:
        """检查字段间一致性"""
        results = []
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        
        # 检查min/max关系（如果存在）
        min_col = next((h for h in headers if 'min' in h.lower()), None)
        max_col = next((h for h in headers if 'max' in h.lower()), None)
        
        if min_col and max_col:
            for i, row in enumerate(rows, 1):
                try:
                    min_val = float(row.get(min_col, 0) or 0)
                    max_val = float(row.get(max_col, 0) or 0)
                    if min_val > max_val:
                        results.append(CheckResult(
                            rule_name="",
                            severity=CheckSeverity.ERROR,
                            message=f"第{i}行的{min_col}({min_val})大于{max_col}({max_val})",
                            location=f"row_{i}",
                            suggestion=f"请确保{min_col} <= {max_col}"
                        ))
                except (ValueError, TypeError):
                    pass
        
        return results
    
    def generate_html_report(self, report: Dict) -> str:
        """生成HTML格式的检查报告"""
        if not report.get('has_data'):
            return "<p>表格数据为空</p>"
        
        summary = report.get('summary', {})
        health = report.get('health_score', 100)
        
        # 健康度颜色
        health_color = '#4CAF50' if health >= 80 else '#FF9800' if health >= 60 else '#F44336'
        
        html = [f"<h3>[报表] 配置表检查报告 - {report.get('table_name', '未命名')}</h3>"]
        
        # 概览
        html.append(f"""
        <div style="padding:15px;background:{health_color}15;border-left:4px solid {health_color};margin:10px 0;">
            <p><strong>健康度评分：{health}/100</strong></p>
            <p>共检查 {report.get('row_count', 0)} 行 × {report.get('col_count', 0)} 列</p>
            <p>[错误] {summary.get('errors', 0)} | [警告] {summary.get('warnings', 0)} | [提示] {summary.get('infos', 0)}</p>
        </div>
        """)
        
        # 错误列表
        errors = report.get('errors', [])
        if errors:
            html.append("<h4>[必须修复]</h4><ul>")
            for e in errors[:10]:  # 只显示前10个
                html.append(f"<li><strong>{e['location']}</strong>: {e['message']}<br><small>建议：{e['suggestion']}</small></li>")
            if len(errors) > 10:
                html.append(f"<li>...还有 {len(errors)-10} 个错误</li>")
            html.append("</ul>")
        
        # 警告列表
        warnings = report.get('warnings', [])
        if warnings:
            html.append("<h4>[建议修复]</h4><ul>")
            for w in warnings[:5]:
                html.append(f"<li><strong>{w['location']}</strong>: {w['message']}</li>")
            if len(warnings) > 5:
                html.append(f"<li>...还有 {len(warnings)-5} 个警告</li>")
            html.append("</ul>")
        
        # 通过检查
        if not errors and not warnings:
            html.append("<p style='color:#4CAF50;'>[通过] 检查通过，未发现明显问题</p>")
        
        return "\n".join(html)


# 便捷函数
def check_table(table_data: Dict, table_name: str = "") -> Dict:
    """快速检查表格"""
    checker = TableChecker()
    return checker.check(table_data, table_name)


def check_table_html(table_data: Dict, table_name: str = "") -> str:
    """快速检查并返回HTML报告"""
    checker = TableChecker()
    report = checker.check(table_data, table_name)
    return checker.generate_html_report(report)
