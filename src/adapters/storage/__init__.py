"""
存储适配器模块

提供多种导出格式支持：
- Excel: 格式化的测试用例表格
- Xmind: 思维导图格式
- JSON: 结构化数据
"""

from src.adapters.storage.base import StorageAdapter
from src.adapters.storage.excel_exporter import ExcelExporter
from src.adapters.storage.xmind_exporter import XmindExporter

__all__ = [
    "StorageAdapter",
    "ExcelExporter",
    "XmindExporter",
]
