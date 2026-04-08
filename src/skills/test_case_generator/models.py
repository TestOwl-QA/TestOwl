"""
测试用例数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class TestCaseType(Enum):
    """测试用例类型"""
    FUNCTIONAL = "功能测试"
    PERFORMANCE = "性能测试"
    SECURITY = "安全测试"
    COMPATIBILITY = "兼容性测试"
    USABILITY = "易用性测试"
    REGRESSION = "回归测试"


class TestCaseStatus(Enum):
    """测试用例状态"""
    DRAFT = "草稿"
    READY = "就绪"
    EXECUTING = "执行中"
    PASSED = "通过"
    FAILED = "失败"
    BLOCKED = "阻塞"
    SKIPPED = "跳过"


@dataclass
class TestStep:
    """测试步骤"""
    step_number: int
    action: str                    # 操作步骤
    expected_result: str           # 预期结果
    test_data: str = ""           # 测试数据
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "expected_result": self.expected_result,
            "test_data": self.test_data,
        }


@dataclass
class TestCase:
    """
    测试用例
    
    标准的测试用例结构，支持导出到各种格式
    """
    # 基本信息
    id: str
    title: str                     # 用例标题
    description: str = ""          # 用例描述
    
    # 分类信息
    module: str = ""               # 所属模块
    feature: str = ""              # 所属功能
    type: TestCaseType = TestCaseType.FUNCTIONAL
    priority: str = "P2"           # P0/P1/P2/P3
    
    # 前置条件
    preconditions: List[str] = field(default_factory=list)
    
    # 测试步骤
    steps: List[TestStep] = field(default_factory=list)
    
    # 后置条件
    postconditions: List[str] = field(default_factory=list)
    
    # 其他信息
    author: str = ""               # 创建人
    created_at: str = ""           # 创建时间
    updated_at: str = ""           # 更新时间
    tags: List[str] = field(default_factory=list)
    
    # 关联信息
    related_requirement: str = ""  # 关联需求
    related_bug: str = ""          # 关联Bug
    
    # 状态
    status: TestCaseStatus = TestCaseStatus.DRAFT
    
    # 备注
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "module": self.module,
            "feature": self.feature,
            "type": self.type.value,
            "priority": self.priority,
            "preconditions": self.preconditions,
            "steps": [step.to_dict() for step in self.steps],
            "postconditions": self.postconditions,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "related_requirement": self.related_requirement,
            "related_bug": self.related_bug,
            "status": self.status.value,
            "notes": self.notes,
        }
    
    def to_excel_row(self) -> Dict[str, Any]:
        """转换为Excel行格式"""
        steps_text = "\n".join([
            f"{s.step_number}. {s.action}\n   预期: {s.expected_result}"
            for s in self.steps
        ])
        
        return {
            "用例ID": self.id,
            "用例标题": self.title,
            "所属模块": self.module,
            "所属功能": self.feature,
            "用例类型": self.type.value,
            "优先级": self.priority,
            "前置条件": "\n".join(self.preconditions),
            "测试步骤": steps_text,
            "后置条件": "\n".join(self.postconditions),
            "关联需求": self.related_requirement,
            "标签": ", ".join(self.tags),
            "备注": self.notes,
        }


@dataclass
class TestSuite:
    """测试套件（用例集合）"""
    name: str
    description: str = ""
    test_cases: List[TestCase] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_test_case(self, test_case: TestCase):
        """添加测试用例"""
        self.test_cases.append(test_case)
    
    def get_by_priority(self, priority: str) -> List[TestCase]:
        """按优先级获取用例"""
        return [tc for tc in self.test_cases if tc.priority == priority]
    
    def get_by_module(self, module: str) -> List[TestCase]:
        """按模块获取用例"""
        return [tc for tc in self.test_cases if tc.module == module]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "metadata": self.metadata,
            "statistics": {
                "total": len(self.test_cases),
                "by_priority": {
                    "P0": len(self.get_by_priority("P0")),
                    "P1": len(self.get_by_priority("P1")),
                    "P2": len(self.get_by_priority("P2")),
                    "P3": len(self.get_by_priority("P3")),
                }
            }
        }
