"""
需求文档分析技能

功能：
1. 解析多种格式的需求文档（Word、PDF、Markdown等）
2. 使用LLM提取测试要点
3. 生成结构化的分析结果
"""

import json
from typing import Any, Dict, List

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.skills.document_analyzer.models import AnalysisResult, TestPoint, Priority
from src.adapters.document.parser import DocumentParser
from src.adapters.llm.client import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentAnalyzerSkill(BaseSkill):
    """
    需求文档分析技能
    
    使用示例：
        ```python
        skill = DocumentAnalyzerSkill(config)
        context = SkillContext(
            agent=agent,
            config=config,
            params={"file_path": "需求文档.docx"}
        )
        result = await skill.execute(context)
        ```
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.document_parser = DocumentParser(config)
        self.llm_client = LLMClient(config)
    
    @property
    def name(self) -> str:
        return "document_analyzer"
    
    @property
    def description(self) -> str:
        return "分析需求文档，提取测试要点"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "file_path",
                "type": "string",
                "required": False,
                "description": "文档文件路径（与content二选一）",
            },
            {
                "name": "content",
                "type": "string",
                "required": False,
                "description": "文档内容文本（与file_path二选一）",
            },
            {
                "name": "doc_url",
                "type": "string",
                "required": False,
                "description": "云文档URL（如Confluence、飞书文档等）",
            },
            {
                "name": "focus_areas",
                "type": "array",
                "required": False,
                "description": "重点关注领域（如：['功能', '性能', '安全']）",
                "default": [],
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行文档分析
        
        Args:
            context: 包含 file_path、content 或 doc_url
        
        Returns:
            AnalysisResult 对象
        """
        # 1. 获取文档内容
        content = await self._get_document_content(context)
        if not content:
            return SkillResult.fail("无法获取文档内容")
        
        logger.info(f"Document content length: {len(content)} characters")
        
        # 2. 使用LLM分析文档
        try:
            analysis_result = await self._analyze_with_llm(content, context)
            return SkillResult.ok(data=analysis_result)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return SkillResult.fail(f"文档分析失败: {str(e)}")
    
    async def _get_document_content(self, context: SkillContext) -> str:
        """
        获取文档内容
        
        支持多种来源：本地文件、直接文本、云文档URL
        """
        file_path = context.get_param("file_path")
        content = context.get_param("content")
        doc_url = context.get_param("doc_url")
        
        # 优先级：content > file_path > doc_url
        if content:
            return content
        
        if file_path:
            return self.document_parser.parse_file(file_path)
        
        if doc_url:
            return await self.document_parser.parse_url(doc_url)
        
        return ""
    
    async def _analyze_with_llm(
        self, 
        content: str, 
        context: SkillContext
    ) -> AnalysisResult:
        """
        使用LLM分析文档内容
        
        构建精心设计的Prompt，让LLM提取测试要点
        """
        focus_areas = context.get_param("focus_areas", [])
        focus_hint = f"\n重点关注领域: {', '.join(focus_areas)}" if focus_areas else ""
        
        prompt = f"""你是一个专业的游戏测试专家。请分析以下需求文档，提取测试要点。

## 分析要求

1. **文档摘要**：用2-3句话概括文档核心内容
2. **测试要点提取**：识别所有需要测试的功能点、规则、边界条件
   - 每个测试要点包含：标题、详细描述、优先级(P0/P1/P2/P3)、类别
   - 优先级定义：
     * P0 - 阻塞级，必须测试，失败会阻塞发布
     * P1 - 高优先级，核心功能必须测试
     * P2 - 中优先级，常规功能测试
     * P3 - 低优先级，有精力时测试
   - 类别包括：功能、性能、安全、兼容性、UI/UX、数据、接口等
3. **风险点识别**：列出可能存在的测试风险
4. **待确认问题**：列出需求中不明确、需要与产品确认的问题{focus_hint}

## 输出格式

请以JSON格式输出，结构如下：
```json
{{
  "document_summary": "文档摘要",
  "test_points": [
    {{
      "id": "TP001",
      "title": "测试要点标题",
      "description": "详细描述",
      "priority": "P1",
      "category": "功能",
      "related_requirement": "关联的需求描述",
      "preconditions": ["前置条件1", "前置条件2"],
      "test_data": ["测试数据建议1"],
      "notes": "备注"
    }}
  ],
  "risk_points": ["风险点1", "风险点2"],
  "questions": ["待确认问题1", "待确认问题2"]
}}
```

## 需求文档内容

{content[:15000]}  <!-- 限制长度避免超出token限制 -->

请直接输出JSON，不要包含其他说明文字。"""

        # 调用LLM
        response = await self.llm_client.complete(prompt)
        
        # 解析JSON响应
        try:
            # 尝试提取JSON部分
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            
            # 构建AnalysisResult
            return self._build_analysis_result(data, content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"LLM返回格式错误: {e}")
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分"""
        # 尝试找到JSON代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        
        # 尝试找到JSON对象
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        
        return text.strip()
    
    def _build_analysis_result(
        self, 
        data: Dict, 
        original_content: str
    ) -> AnalysisResult:
        """从解析的数据构建AnalysisResult对象"""
        
        # 解析测试要点
        test_points = []
        for i, tp_data in enumerate(data.get("test_points", [])):
            try:
                priority = Priority(tp_data.get("priority", "P2"))
            except ValueError:
                priority = Priority.P2
            
            test_point = TestPoint(
                id=tp_data.get("id", f"TP{i+1:03d}"),
                title=tp_data.get("title", ""),
                description=tp_data.get("description", ""),
                priority=priority,
                category=tp_data.get("category", "功能"),
                related_requirement=tp_data.get("related_requirement", ""),
                preconditions=tp_data.get("preconditions", []),
                test_data=tp_data.get("test_data", []),
                notes=tp_data.get("notes", ""),
            )
            test_points.append(test_point)
        
        # 统计类别
        categories = {}
        for tp in test_points:
            categories[tp.category] = categories.get(tp.category, 0) + 1
        
        return AnalysisResult(
            document_title=self._extract_title(original_content),
            document_summary=data.get("document_summary", ""),
            test_points=test_points,
            categories=categories,
            risk_points=data.get("risk_points", []),
            questions=data.get("questions", []),
            metadata={
                "total_points": len(test_points),
                "content_length": len(original_content),
            }
        )
    
    def _extract_title(self, content: str) -> str:
        """从内容中提取标题"""
        lines = content.strip().split('\n')
        for line in lines[:10]:  # 检查前10行
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:100]  # 限制长度
            if line.startswith('# '):
                return line[2:100]
        return "未命名文档"
