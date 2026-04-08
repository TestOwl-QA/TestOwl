"""
需求文档分析的数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class Priority(Enum):
    """优先级"""
    P0 = "P0"  # 阻塞
    P1 = "P1"  # 高
    P2 = "P2"  # 中
    P3 = "P3"  # 低


@dataclass
class TestPoint:
    """
    测试要点
    
    从需求中提取的一个测试关注点
    """
    id: str                          # 唯一标识
    title: str                       # 标题
    description: str                 # 描述
    priority: Priority               # 优先级
    category: str                    # 类别（功能、性能、安全等）
    related_requirement: str = ""    # 关联需求
    preconditions: List[str] = field(default_factory=list)  # 前置条件
    test_data: List[str] = field(default_factory=list)      # 测试数据建议
    notes: str = ""                  # 备注
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "category": self.category,
            "related_requirement": self.related_requirement,
            "preconditions": self.preconditions,
            "test_data": self.test_data,
            "notes": self.notes,
        }


@dataclass
class AnalysisResult:
    """
    文档分析结果
    
    包含从需求文档中提取的所有测试相关信息
    """
    # 基础信息
    document_title: str = ""
    document_summary: str = ""
    
    # 提取的测试要点
    test_points: List[TestPoint] = field(default_factory=list)
    
    # 分类统计
    categories: Dict[str, int] = field(default_factory=dict)
    
    # 风险点
    risk_points: List[str] = field(default_factory=list)
    
    # 待确认问题
    questions: List[str] = field(default_factory=list)
    
    # 原始元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_by_priority(self, priority: Priority) -> List[TestPoint]:
        """按优先级获取测试要点"""
        return [tp for tp in self.test_points if tp.priority == priority]
    
    def get_by_category(self, category: str) -> List[TestPoint]:
        """按类别获取测试要点"""
        return [tp for tp in self.test_points if tp.category == category]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "document_title": self.document_title,
            "document_summary": self.document_summary,
            "test_points": [tp.to_dict() for tp in self.test_points],
            "categories": self.categories,
            "risk_points": self.risk_points,
            "questions": self.questions,
            "metadata": self.metadata,
        }
