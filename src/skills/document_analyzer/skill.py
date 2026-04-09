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
from src.core.token_optimizer import TokenOptimizer
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.skills.document_analyzer.models import AnalysisResult, TestPoint, Priority
from src.adapters.document.parser import DocumentParser
from src.adapters.llm.client import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentAnalyzerSkill(BaseSkill):
    """需求文档分析技能"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.document_parser = DocumentParser(config)
        self.llm_client = LLMClient(config)
        
        # 初始化Token优化器
        self.token_optimizer = TokenOptimizer(config={
            'cache_max_entries': 1000,
            'cache_ttl_hours': 24,
            'summary_ratio': 0.3,
            'chunk_size': 6000,
            'chunk_overlap': 500,
            'max_chunks': 5,
        })
        
        # 初始化知识库服务（可选）
        try:
            from src.services.knowledge_service import get_knowledge_service
            self.knowledge_service = get_knowledge_service()
            logger.info("知识库服务已加载")
        except Exception as e:
            logger.warning(f"知识库服务初始化失败: {e}")
            self.knowledge_service = None
    
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
        """执行文档分析"""
        content = await self._get_document_content(context)
        if not content:
            return SkillResult.fail("无法获取文档内容")
        
        logger.info(f"Document content length: {len(content)} characters")
        
        try:
            analysis_result = await self._analyze_with_llm(content, context)
            return SkillResult.ok(data=analysis_result)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return SkillResult.fail(f"文档分析失败: {str(e)}")
    
    async def _get_document_content(self, context: SkillContext) -> str:
        """获取文档内容"""
        file_path = context.get_param("file_path")
        content = context.get_param("content")
        doc_url = context.get_param("doc_url")
        
        if content:
            return content
        if file_path:
            return self.document_parser.parse_file(file_path)
        if doc_url:
            return await self.document_parser.parse_url(doc_url)
        
        return ""
    
    async def _analyze_with_llm(
        self, content: str, context: SkillContext
    ) -> AnalysisResult:
        """使用LLM分析文档内容（Token优化版本）"""
        focus_areas = context.get_param("focus_areas", [])
        
        cache_key = self.token_optimizer.generate_cache_key(
            content, focus_areas=focus_areas, version="v3"
        )
        
        logger.info(f"Starting optimized analysis for {len(content)} chars document")
        
        result_data, usage = await self.token_optimizer.process_large_document(
            content=content,
            chunk_processor=lambda chunk: self._analyze_chunk(chunk, focus_areas),
            merge_strategy="aggregate",
            cache_key=cache_key
        )
        
        logger.info(f"Token usage - Input: {usage.input_tokens}, Output: {usage.output_tokens}")
        
        stats = self.token_optimizer.get_stats()
        logger.info(f"Cache hit rate: {stats['cache_stats']['hit_rate']}")
        
        merged_data = self._merge_chunk_results(result_data)
        
        return self._build_analysis_result(merged_data, content)
    
    async def _analyze_chunk(
        self, content: str, focus_areas: List[str]
    ) -> Dict:
        """分析单个文档块"""
        
        # 获取知识库上下文
        knowledge_context = ""
        if self.knowledge_service:
            try:
                query_keywords = " ".join(focus_areas) if focus_areas else "游戏测试 数值 关卡"
                result = self.knowledge_service.search(query_keywords, top_k=2)
                knowledge_context = result.to_context(max_length=1500)
                if knowledge_context:
                    logger.info(f"知识库检索成功，相关度: {result.relevance_score:.2f}")
            except Exception as e:
                logger.warning(f"知识库检索失败: {e}")
        
        focus_hint = f"\n重点关注领域: {', '.join(focus_areas)}" if focus_areas else ""
        knowledge_hint = f"\n\n{knowledge_context}" if knowledge_context else ""
        
        prompt = f"""你是一个专业的游戏测试专家。请分析以下需求文档片段，提取测试要点。
{knowledge_hint}

## 分析要求
1. **文档摘要**：用1-2句话概括该片段核心内容
2. **测试要点提取**：识别所有需要测试的功能点、规则、边界条件
   - 每个测试要点包含：标题、详细描述、优先级(P0/P1/P2/P3)、类别
   - 优先级定义：
     * P0 - 阻塞级，必须测试
     * P1 - 高优先级，核心功能
     * P2 - 中优先级，常规功能
     * P3 - 低优先级
   - 类别包括：功能、性能、安全、兼容性、UI/UX、数据、接口等
3. **风险点识别**：列出可能存在的测试风险
4. **待确认问题**：列出需求中不明确的问题{focus_hint}

## 输出格式
请以JSON格式输出：
```json
{{
  "document_summary": "片段摘要",
  "test_points": [
    {{
      "id": "TP001",
      "title": "测试要点标题",
      "description": "详细描述",
      "priority": "P1",
      "category": "功能",
      "related_requirement": "关联需求",
      "preconditions": [],
      "test_data": [],
      "notes": ""
    }}
  ],
  "risk_points": [],
  "questions": []
}}
```

## 需求文档片段
{content}

请直接输出JSON。"""
        
        try:
            response = await self.llm_client.complete(prompt)
            json_str = self._extract_json(response)
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Chunk analysis failed: {e}")
            return {
                "document_summary": "",
                "test_points": [],
                "risk_points": [],
                "questions": []
            }
    
    def _merge_chunk_results(self, results: List[Dict]) -> Dict:
        """合并多个块的分析结果"""
        merged = {
            "document_summary": "",
            "test_points": [],
            "risk_points": [],
            "questions": []
        }
        
        summaries = []
        for i, result in enumerate(results):
            if result.get("document_summary"):
                summaries.append(result["document_summary"])
            
            for tp in result.get("test_points", []):
                tp["id"] = f"TP{len(merged['test_points'])+1:03d}"
                merged["test_points"].append(tp)
            
            for rp in result.get("risk_points", []):
                if rp not in merged["risk_points"]:
                    merged["risk_points"].append(rp)
            
            for q in result.get("questions", []):
                if q not in merged["questions"]:
                    merged["questions"].append(q)
        
        if summaries:
            merged["document_summary"] = " ".join(summaries[:3])
        
        return merged
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分"""
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
    
    def _build_analysis_result(
        self, data: Dict, original_content: str
    ) -> AnalysisResult:
        """构建最终分析结果"""
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
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:100]
            if line.startswith('# '):
                return line[2:100]
        return "未命名文档"
