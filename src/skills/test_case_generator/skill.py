"""
测试用例生成技能

功能：
1. 基于需求文档或测试要点生成详细测试用例
2. 支持导出为Excel、Xmind等格式
3. 支持批量生成和模板定制
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.skills.test_case_generator.models import TestCase, TestSuite, TestStep, TestCaseType
from src.skills.document_analyzer.models import AnalysisResult, TestPoint
from src.adapters.llm.client import LLMClient
from src.adapters.storage.excel_exporter import ExcelExporter
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TestCaseGeneratorSkill(BaseSkill):
    """
    测试用例生成技能
    
    使用示例：
        ```python
        # 基于文档分析结果生成用例
        skill = TestCaseGeneratorSkill(config)
        context = SkillContext(
            agent=agent,
            config=config,
            params={
                "analysis_result": analysis_result,  # DocumentAnalyzer的输出
                "output_format": "excel",
                "output_path": "测试用例.xlsx"
            }
        )
        result = await skill.execute(context)
        ```
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.llm_client = LLMClient(config)
        self.excel_exporter = ExcelExporter(config)
    
    @property
    def name(self) -> str:
        return "test_case_generator"
    
    @property
    def description(self) -> str:
        return "基于需求生成详细测试用例"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "analysis_result",
                "type": "object",
                "required": False,
                "description": "文档分析结果（DocumentAnalyzerSkill的输出）",
            },
            {
                "name": "test_points",
                "type": "array",
                "required": False,
                "description": "测试要点列表（与analysis_result二选一）",
            },
            {
                "name": "requirements_text",
                "type": "string",
                "required": False,
                "description": "需求文本（直接输入）",
            },
            {
                "name": "output_format",
                "type": "string",
                "required": False,
                "description": "输出格式：excel/xmind/json",
                "default": "excel",
            },
            {
                "name": "output_path",
                "type": "string",
                "required": False,
                "description": "输出文件路径",
            },
            {
                "name": "module_name",
                "type": "string",
                "required": False,
                "description": "模块名称（用于分类）",
                "default": "",
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行测试用例生成
        """
        # 1. 获取输入
        analysis_result = context.get_param("analysis_result")
        test_points = context.get_param("test_points")
        requirements_text = context.get_param("requirements_text")
        
        # 2. 如果没有测试要点，先生成
        if not test_points:
            if analysis_result and isinstance(analysis_result, AnalysisResult):
                test_points = analysis_result.test_points
            elif requirements_text:
                test_points = await self._extract_test_points(requirements_text)
            else:
                return SkillResult.fail("请提供 analysis_result、test_points 或 requirements_text")
        
        logger.info(f"Generating test cases for {len(test_points)} test points")
        
        # 3. 生成测试用例
        try:
            test_suite = await self._generate_test_cases(test_points, context)
            
            # 4. 导出
            output_format = context.get_param("output_format", "excel")
            output_path = context.get_param("output_path")
            
            if output_path:
                exported_path = await self._export(test_suite, output_format, output_path)
                return SkillResult.ok(data={
                    "test_suite": test_suite,
                    "exported_path": exported_path,
                    "statistics": test_suite.to_dict()["statistics"]
                })
            else:
                return SkillResult.ok(data=test_suite)
                
        except Exception as e:
            logger.error(f"Test case generation failed: {e}")
            return SkillResult.fail(f"测试用例生成失败: {str(e)}")
    
    async def _extract_test_points(self, requirements_text: str) -> List[TestPoint]:
        """从需求文本中提取测试要点"""
        prompt = f"""请分析以下需求，提取测试要点，以JSON格式返回：

需求内容：
{requirements_text[:8000]}

请返回格式：
{{
  "test_points": [
    {{
      "id": "TP001",
      "title": "测试要点标题",
      "description": "详细描述",
      "priority": "P2",
      "category": "功能"
    }}
  ]
}}"""

        response = await self.llm_client.complete(prompt)
        
        try:
            data = json.loads(self._extract_json(response))
            return [
                TestPoint(
                    id=tp.get("id", f"TP{i+1:03d}"),
                    title=tp.get("title", ""),
                    description=tp.get("description", ""),
                    priority=tp.get("priority", "P2"),
                    category=tp.get("category", "功能"),
                )
                for i, tp in enumerate(data.get("test_points", []))
            ]
        except Exception as e:
            logger.error(f"Failed to extract test points: {e}")
            return []
    
    async def _generate_test_cases(
        self, 
        test_points: List[TestPoint],
        context: SkillContext
    ) -> TestSuite:
        """基于测试要点生成详细测试用例"""
        
        module_name = context.get_param("module_name", "默认模块")
        test_suite = TestSuite(
            name=f"{module_name}测试用例",
            description=f"自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # 批量处理测试要点
        for i, point in enumerate(test_points):
            logger.debug(f"Generating test case for: {point.title}")
            
            # 使用LLM生成详细用例
            test_case = await self._generate_single_test_case(point, i + 1)
            test_suite.add_test_case(test_case)
        
        return test_suite
    
    async def _generate_single_test_case(
        self, 
        test_point: TestPoint,
        index: int
    ) -> TestCase:
        """为单个测试要点生成详细用例"""
        
        prompt = f"""基于以下测试要点，生成详细的测试用例，以JSON格式返回。

测试要点：
- 标题：{test_point.title}
- 描述：{test_point.description}
- 优先级：{test_point.priority}
- 类别：{test_point.category}
- 前置条件：{', '.join(test_point.preconditions)}
- 测试数据建议：{', '.join(test_point.test_data)}

请生成格式：
```json
{{
  "title": "详细的用例标题",
  "description": "用例描述",
  "preconditions": ["前置条件1", "前置条件2"],
  "steps": [
    {{
      "step_number": 1,
      "action": "具体操作步骤",
      "expected_result": "预期结果",
      "test_data": "测试数据"
    }}
  ],
  "postconditions": ["后置条件"],
  "tags": ["标签1", "标签2"]
}}
```

要求：
1. 步骤要详细、可执行
2. 预期结果要明确、可验证
3. 覆盖正常流程和异常流程
4. 如果有边界条件，单独作为步骤"""

        response = await self.llm_client.complete(prompt)
        
        try:
            data = json.loads(self._extract_json(response))
            
            # 构建测试步骤
            steps = [
                TestStep(
                    step_number=s.get("step_number", i+1),
                    action=s.get("action", ""),
                    expected_result=s.get("expected_result", ""),
                    test_data=s.get("test_data", ""),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
            
            # 确定用例类型
            case_type = self._map_category_to_type(test_point.category)
            
            return TestCase(
                id=f"TC{index:04d}",
                title=data.get("title", test_point.title),
                description=data.get("description", test_point.description),
                module="",
                feature="",
                type=case_type,
                priority=test_point.priority.value if isinstance(test_point.priority, Enum) else test_point.priority,
                preconditions=data.get("preconditions", test_point.preconditions),
                steps=steps,
                postconditions=data.get("postconditions", []),
                tags=data.get("tags", [test_point.category]),
                related_requirement=test_point.related_requirement,
                created_at=datetime.now().isoformat(),
            )
            
        except Exception as e:
            logger.error(f"Failed to generate test case for {test_point.title}: {e}")
            # 返回基础用例
            return TestCase(
                id=f"TC{index:04d}",
                title=test_point.title,
                description=test_point.description,
                priority=test_point.priority.value if isinstance(test_point.priority, Enum) else test_point.priority,
                tags=[test_point.category],
                created_at=datetime.now().isoformat(),
            )
    
    def _map_category_to_type(self, category: str) -> TestCaseType:
        """将类别映射到用例类型"""
        category_map = {
            "功能": TestCaseType.FUNCTIONAL,
            "性能": TestCaseType.PERFORMANCE,
            "安全": TestCaseType.SECURITY,
            "兼容": TestCaseType.COMPATIBILITY,
            "兼容性": TestCaseType.COMPATIBILITY,
            "易用": TestCaseType.USABILITY,
            "UI": TestCaseType.USABILITY,
            "UX": TestCaseType.USABILITY,
            "回归": TestCaseType.REGRESSION,
        }
        return category_map.get(category, TestCaseType.FUNCTIONAL)
    
    async def _export(
        self, 
        test_suite: TestSuite, 
        format: str, 
        output_path: str
    ) -> str:
        """导出测试用例"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "excel":
            return await self.excel_exporter.export_test_suite(test_suite, output_path)
        elif format == "json":
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(test_suite.to_dict(), f, ensure_ascii=False, indent=2)
            return output_path
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        return text.strip()
