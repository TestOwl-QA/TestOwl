"""
Xmind导出器

功能：
1. 支持将测试用例导出为Xmind思维导图
2. 支持将测试点导出为思维导图
3. 支持多种布局样式
"""

import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pathlib import Path

from src.core.config import Config
from src.adapters.storage.base import StorageAdapter
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.skills.test_case_generator.models import TestCase

logger = get_logger(__name__)


class XmindExporter(StorageAdapter):
    """
    Xmind思维导图导出器
    
    注意：由于.xmind文件格式是专有二进制格式，
    本实现采用以下策略：
    1. 优先使用 xmind 库（如果已安装）
    2. 否则导出为兼容的 JSON 格式，可导入到 Xmind/Zen
    3. 或者导出为 Markdown 大纲格式
    
    使用示例：
        ```python
        exporter = XmindExporter(config)
        
        # 导出测试用例
        await exporter.export_test_cases(
            test_cases,
            output_path="test_cases.xmind",
            title="登录模块测试用例"
        )
        ```
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self._xmind_available = self._check_xmind_library()
    
    def _check_xmind_library(self) -> bool:
        """检查是否安装了 xmind 库"""
        try:
            import xmind
            return True
        except ImportError:
            logger.warning("xmind library not installed. Will use JSON/Markdown fallback.")
            return False
    
    async def export_test_cases(
        self,
        test_cases: List["TestCase"],
        output_path: str,
        title: str = "测试用例",
        template: str = "default",
    ) -> Dict[str, Any]:
        """
        导出测试用例为Xmind格式
        
        Args:
            test_cases: 测试用例列表
            output_path: 输出文件路径
            title: 思维导图标题
            template: 模板名称
        
        Returns:
            导出结果
        """
        output_path = Path(output_path)
        
        # 根据可用库选择导出方式
        if self._xmind_available and output_path.suffix == ".xmind":
            return await self._export_with_xmind_lib(test_cases, output_path, title)
        elif output_path.suffix == ".json":
            return await self._export_as_json(test_cases, output_path, title)
        else:
            # 默认导出为 Markdown 大纲
            md_path = output_path.with_suffix(".md")
            return await self._export_as_markdown(test_cases, md_path, title)
    
    async def _export_with_xmind_lib(
        self,
        test_cases: List["TestCase"],
        output_path: Path,
        title: str,
    ) -> Dict[str, Any]:
        """使用 xmind 库导出"""
        try:
            import xmind
            
            # 创建工作簿
            workbook = xmind.load(output_path)
            sheet = workbook.getPrimarySheet()
            sheet.setTitle(title)
            
            root_topic = sheet.getRootTopic()
            root_topic.setTitle(title)
            
            # 按优先级和模块分组
            grouped_cases = self._group_test_cases(test_cases)
            
            for group_name, cases in grouped_cases.items():
                group_topic = root_topic.addSubTopic()
                group_topic.setTitle(f"{group_name} ({len(cases)}个)")
                
                for case in cases:
                    case_topic = group_topic.addSubTopic()
                    case_topic.setTitle(f"TC{case.id}: {case.title}")
                    
                    # 添加详细信息
                    if case.precondition:
                        pre_topic = case_topic.addSubTopic()
                        pre_topic.setTitle(f"前置: {case.precondition}")
                    
                    if case.steps:
                        steps_topic = case_topic.addSubTopic()
                        steps_topic.setTitle("测试步骤")
                        for i, step in enumerate(case.steps, 1):
                            step_topic = steps_topic.addSubTopic()
                            step_topic.setTitle(f"{i}. {step}")
                    
                    if case.expected_result:
                        exp_topic = case_topic.addSubTopic()
                        exp_topic.setTitle(f"预期: {case.expected_result}")
                    
                    # 添加标记
                    self._add_priority_marker(case_topic, case.priority)
            
            # 保存
            xmind.save(workbook, output_path)
            
            return {
                "success": True,
                "output_path": str(output_path),
                "format": "xmind",
                "test_case_count": len(test_cases),
            }
            
        except Exception as e:
            logger.error(f"Xmind export failed: {e}")
            # 降级到 JSON
            json_path = output_path.with_suffix(".json")
            return await self._export_as_json(test_cases, json_path, title)
    
    async def _export_as_json(
        self,
        test_cases: List["TestCase"],
        output_path: Path,
        title: str,
    ) -> Dict[str, Any]:
        """导出为 JSON 格式（可导入到 Xmind/Zen）"""
        
        # 构建思维导图结构
        mindmap = {
            "title": title,
            "root": {
                "title": title,
                "children": []
            }
        }
        
        # 按优先级分组
        grouped_cases = self._group_test_cases(test_cases)
        
        for group_name, cases in grouped_cases.items():
            group_node = {
                "title": f"{group_name} ({len(cases)}个)",
                "children": []
            }
            
            for case in cases:
                case_node = {
                    "title": f"TC{case.id}: {case.title}",
                    "priority": case.priority,
                    "children": []
                }
                
                # 添加详情
                details = []
                if case.precondition:
                    details.append({"title": f"前置条件: {case.precondition}"})
                if case.steps:
                    steps_node = {
                        "title": "测试步骤",
                        "children": [{"title": f"{i}. {s}"} for i, s in enumerate(case.steps, 1)]
                    }
                    details.append(steps_node)
                if case.expected_result:
                    details.append({"title": f"预期结果: {case.expected_result}"})
                if case.test_data:
                    details.append({"title": f"测试数据: {case.test_data}"})
                
                case_node["children"] = details
                group_node["children"].append(case_node)
            
            mindmap["root"]["children"].append(group_node)
        
        # 保存 JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(mindmap, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "output_path": str(output_path),
            "format": "json",
            "test_case_count": len(test_cases),
            "note": "JSON格式可导入到 Xmind/Zen 等思维导图软件",
        }
    
    async def _export_as_markdown(
        self,
        test_cases: List["TestCase"],
        output_path: Path,
        title: str,
    ) -> Dict[str, Any]:
        """导出为 Markdown 大纲格式"""
        
        lines = [f"# {title}", ""]
        
        # 按优先级分组
        grouped_cases = self._group_test_cases(test_cases)
        
        for group_name, cases in grouped_cases.items():
            lines.append(f"## {group_name} ({len(cases)}个)")
            lines.append("")
            
            for case in cases:
                lines.append(f"### TC{case.id}: {case.title}")
                lines.append("")
                lines.append(f"- **优先级**: {case.priority}")
                lines.append(f"- **类型**: {case.test_type}")
                
                if case.precondition:
                    lines.append(f"- **前置条件**: {case.precondition}")
                
                if case.steps:
                    lines.append("- **测试步骤**:")
                    for i, step in enumerate(case.steps, 1):
                        lines.append(f"  {i}. {step}")
                
                if case.expected_result:
                    lines.append(f"- **预期结果**: {case.expected_result}")
                
                if case.test_data:
                    lines.append(f"- **测试数据**: {case.test_data}")
                
                lines.append("")
        
        # 保存 Markdown
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return {
            "success": True,
            "output_path": str(output_path),
            "format": "markdown",
            "test_case_count": len(test_cases),
            "note": "Markdown格式可直接阅读或导入支持Markdown的思维导图软件",
        }
    
    def _group_test_cases(self, test_cases: List["TestCase"]) -> Dict[str, List["TestCase"]]:
        """按优先级分组测试用例"""
        groups = {
            "🔴 高优先级": [],
            "🟡 中优先级": [],
            "🟢 低优先级": [],
        }
        
        for case in test_cases:
            if case.priority == "高":
                groups["🔴 高优先级"].append(case)
            elif case.priority == "中":
                groups["🟡 中优先级"].append(case)
            else:
                groups["🟢 低优先级"].append(case)
        
        # 移除空组
        return {k: v for k, v in groups.items() if v}
    
    def _add_priority_marker(self, topic, priority: str):
        """为Topic添加优先级标记"""
        # xmind库的具体标记API可能需要根据版本调整
        # 这里仅作为示例
        markers = {
            "高": "priority-1",
            "中": "priority-2",
            "低": "priority-3",
        }
        marker = markers.get(priority)
        if marker:
            try:
                topic.addMarker(marker)
            except Exception:
                # 标记添加失败时静默处理，不影响整体导出
                pass
    
    async def export_test_points(
        self,
        test_points: List[Dict[str, Any]],
        output_path: str,
        title: str = "测试点",
    ) -> Dict[str, Any]:
        """
        导出测试点为思维导图
        
        Args:
            test_points: 测试点列表
            output_path: 输出文件路径
            title: 思维导图标题
        
        Returns:
            导出结果
        """
        output_path = Path(output_path)
        
        # 构建思维导图结构
        mindmap = {
            "title": title,
            "root": {
                "title": title,
                "children": []
            }
        }
        
        # 按模块分组
        by_module = {}
        for point in test_points:
            module = point.get("module", "未分类")
            if module not in by_module:
                by_module[module] = []
            by_module[module].append(point)
        
        for module, points in by_module.items():
            module_node = {
                "title": f"{module} ({len(points)}个)",
                "children": []
            }
            
            for point in points:
                point_node = {
                    "title": point.get("description", "无描述"),
                    "priority": point.get("priority", "中"),
                    "children": []
                }
                
                # 添加子测试点
                sub_points = point.get("sub_points", [])
                for sub in sub_points:
                    point_node["children"].append({
                        "title": sub.get("description", "无描述")
                    })
                
                module_node["children"].append(point_node)
            
            mindmap["root"]["children"].append(module_node)
        
        # 保存
        if output_path.suffix == ".json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(mindmap, f, ensure_ascii=False, indent=2)
            format_type = "json"
        else:
            # 导出为 Markdown
            md_path = output_path.with_suffix(".md")
            lines = [f"# {title}", ""]
            
            for module, points in by_module.items():
                lines.append(f"## {module} ({len(points)}个)")
                lines.append("")
                for point in points:
                    lines.append(f"- {point.get('description', '无描述')}")
                    for sub in point.get("sub_points", []):
                        lines.append(f"  - {sub.get('description', '无描述')}")
                lines.append("")
            
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            output_path = md_path
            format_type = "markdown"
        
        return {
            "success": True,
            "output_path": str(output_path),
            "format": format_type,
            "test_point_count": len(test_points),
        }
