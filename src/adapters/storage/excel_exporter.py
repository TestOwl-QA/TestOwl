"""
Excel导出器

将测试用例导出为Excel格式
"""

from pathlib import Path
from typing import List, Dict, Any, TYPE_CHECKING

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

from src.core.config import Config
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.skills.test_case_generator.models import TestSuite, TestCase

logger = get_logger(__name__)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ExcelExporter:
    """
    Excel导出器
    
    使用示例：
        ```python
        exporter = ExcelExporter(config)
        await exporter.export_test_suite(test_suite, "output.xlsx")
        ```
    """
    
    def __init__(self, config: Config):
        """
        初始化导出器
        
        Args:
            config: 配置对象
        """
        self.config = config
    
    async def export_test_suite(
        self, 
        test_suite: "TestSuite",
        output_path: str
    ) -> str:
        """
        导出测试套件到Excel
        
        Args:
            test_suite: 测试套件
            output_path: 输出文件路径
        
        Returns:
            导出文件路径
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建工作簿
        wb = Workbook()
        ws = wb.active
        ws.title = "测试用例"
        
        # 设置列宽
        column_widths = {
            'A': 12,  # 用例ID
            'B': 40,  # 用例标题
            'C': 15,  # 所属模块
            'D': 15,  # 所属功能
            'E': 12,  # 用例类型
            'F': 10,  # 优先级
            'G': 30,  # 前置条件
            'H': 60,  # 测试步骤
            'I': 30,  # 后置条件
            'J': 20,  # 关联需求
            'K': 20,  # 标签
            'L': 30,  # 备注
        }
        
        for col, width in column_widths.items():
            ws.column_dimensions[col].width = width
        
        # 定义样式
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        cell_alignment = Alignment(vertical="top", wrap_text=True)
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 写入标题行
        headers = [
            "用例ID", "用例标题", "所属模块", "所属功能", 
            "用例类型", "优先级", "前置条件", "测试步骤",
            "后置条件", "关联需求", "标签", "备注"
        ]
        
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # 写入数据
        priority_colors = {
            "P0": "FF6B6B",  # 红色
            "P1": "FFA94D",  # 橙色
            "P2": "FFD43B",  # 黄色
            "P3": "69DB7C",  # 绿色
        }
        
        for row_idx, test_case in enumerate(test_suite.test_cases, 2):
            row_data = test_case.to_excel_row()
            
            for col_idx, header in enumerate(headers, 1):
                key = header
                value = row_data.get(key, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.alignment = cell_alignment
                cell.border = thin_border
                
                # 根据优先级设置背景色
                if header == "优先级":
                    color = priority_colors.get(value, "FFFFFF")
                    cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        
        # 冻结首行
        ws.freeze_panes = 'A2'
        
        # 保存
        wb.save(path)
        logger.info(f"Test suite exported to: {path}")
        
        return str(path)
    
    async def export_test_cases_to_csv(
        self,
        test_cases: List["TestCase"],
        output_path: str
    ) -> str:
        """
        导出测试用例到CSV
        
        Args:
            test_cases: 测试用例列表
            output_path: 输出文件路径
        
        Returns:
            导出文件路径
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 转换为DataFrame
        data = [tc.to_excel_row() for tc in test_cases]
        df = pd.DataFrame(data)
        
        # 保存
        df.to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"Test cases exported to CSV: {path}")
        
        return str(path)
