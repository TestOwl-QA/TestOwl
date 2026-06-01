"""
知识库搜索技能

功能: 对 knowledge_base/ 中的游戏测试知识文档进行关键词检索
      支持8大分类: 配置表/接口/数据库/白盒/多端/性能/捉宠/代码规范

纯文本匹配，不依赖 LLM，响应快速。
"""
import base64
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 知识库目录
KB_DIR = Path(__file__).parent.parent.parent.parent / "knowledge_base"

# 分类关键词映射（用于过滤无关章节）
CATEGORY_KEYWORDS = {
    "配置表": ["配置表", "Excel", "CSV", "表格", "字段", "表结构"],
    "接口": ["接口", "API", "协议", "请求", "响应", "HTTP", "RPC"],
    "数据库": ["数据库", "SQL", "MySQL", "表", "索引", "查询"],
    "白盒": ["白盒", "代码", "覆盖率", "单元测试", "逻辑"],
    "多端": ["多端", "互通", "同步", "跨平台", "PC", "移动"],
    "性能": ["性能", "压测", "瓶颈", "TPS", "延迟", "内存", "CPU"],
    "捉宠": ["捉宠", "宠物", "捕捉", "养成", "精灵"],
    "代码规范": ["代码规范", "规范", "code review", "命名", "注释"],
}


class KnowledgeSearchSkill(BaseSkill):
    """搜索知识库，返回相关段落"""

    def __init__(self, config: Config):
        super().__init__(config)
        self._cache: Dict[str, str] = {}  # 文件内容缓存

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "搜索游戏测试知识库"

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {"name": "query", "type": "string", "required": True, "description": "搜索关键词"},
            {"name": "top_k", "type": "integer", "required": False, "default": 3, "description": "返回条数"},
        ]

    async def execute(self, context: SkillContext) -> SkillResult:
        query = context.get_param("query", "")
        top_k = context.get_param("top_k", 3)

        if not query:
            return SkillResult.fail("请提供搜索关键词")

        if not KB_DIR.exists():
            return SkillResult.fail(f"知识库目录不存在: {KB_DIR}")

        results = self._search(query, top_k)

        return SkillResult.ok(data={
            "query": query,
            "total_files": len(list(KB_DIR.glob("*.md"))),
            "results": results,
        })

    def _load_file(self, filepath: Path) -> str:
        """加载知识库文件（带缓存，自动处理 base64 编码）"""
        key = str(filepath)
        if key not in self._cache:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                # 知识库文件可能是 base64 编码存储的，尝试解码
                if self._looks_like_base64(raw):
                    try:
                        decoded = base64.b64decode(raw).decode("utf-8")
                        self._cache[key] = decoded
                    except Exception:
                        self._cache[key] = raw
                else:
                    self._cache[key] = raw
            except Exception as e:
                logger.warning(f"读取知识库文件失败: {filepath} -> {e}")
                self._cache[key] = ""
        return self._cache[key]

    def _looks_like_base64(self, text: str) -> bool:
        """判断文本是否像是 base64 编码"""
        # base64 编码的特征: 只含 A-Za-z0-9+/=，没有中文和常见标点
        if not text:
            return False
        # 如果包含中文字符，不是 base64
        if any('一' <= c <= '鿿' for c in text[:500]):
            return False
        # 如果包含 markdown 标记（##、-、|等），不是纯 base64
        first_lines = text[:500]
        if any(marker in first_lines for marker in ['##', '---', '|', '```']):
            return False
        # 纯 base64 字符检测
        b64_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r')
        non_b64 = [c for c in text[:1000] if c not in b64_chars]
        return len(non_b64) < 10  # 允许少量换行等

    def _search(self, query: str, top_k: int) -> List[Dict]:
        """核心搜索逻辑"""
        keywords = self._tokenize(query)
        if not keywords:
            return []

        scored = []

        for md_file in sorted(KB_DIR.glob("*.md")):
            content = self._load_file(md_file)
            if not content:
                continue

            # 按段落分割
            paragraphs = self._split_paragraphs(content)
            filename = md_file.stem

            for para in paragraphs:
                score = self._score_paragraph(para, keywords, filename)

                if score > 0:
                    # 提取标题（如果有 ## 开头的行）
                    title = self._extract_title(para, filename)

                    scored.append({
                        "file": filename,
                        "title": title,
                        "content": para[:300].strip(),
                        "score": score,
                    })

        # 按分数排序
        scored.sort(key=lambda x: x["score"], reverse=True)

        # 去重：同一文件中相似内容只取最高分
        seen = set()
        deduped = []
        for item in scored:
            key = item["file"] + item["title"]
            if key not in seen:
                seen.add(key)
                deduped.append(item)
            if len(deduped) >= top_k:
                break

        # 去掉 score 字段
        for item in deduped:
            del item["score"]

        return deduped

    def _tokenize(self, text: str) -> List[str]:
        """中文分词（简单版：按常见分隔符 + 2-gram）"""
        # 按标点分割
        tokens = re.split(r'[，。、；：！？\s,.;:!?\n]+', text.strip())
        tokens = [t for t in tokens if len(t) >= 1]

        # 补充 2-gram（对中文短词更友好）
        bigrams = []
        for token in tokens:
            if len(token) >= 2:
                for i in range(len(token) - 1):
                    bigrams.append(token[i:i+2])

        return list(set(tokens + bigrams))  # 去重

    def _split_paragraphs(self, content: str) -> List[str]:
        """按空行/标题分割段落"""
        # 先按 ## 标题分割
        sections = re.split(r'\n(?=## )', content)
        paragraphs = []
        for section in sections:
            # 再按空行分割
            parts = re.split(r'\n\n+', section)
            paragraphs.extend([p.strip() for p in parts if p.strip() and len(p.strip()) > 30])
        return paragraphs

    def _score_paragraph(self, paragraph: str, keywords: List[str], filename: str) -> float:
        """计算段落与关键词的相关性得分"""
        para_lower = paragraph.lower()
        score = 0.0

        for kw in keywords:
            kw_lower = kw.lower()
            count = para_lower.count(kw_lower)
            if count > 0:
                # 标题中的匹配权重更高
                if kw_lower in para_lower.split("\n")[0].lower():
                    score += count * 3.0
                else:
                    score += count * 1.0

        # 文件名匹配加分
        for kw in keywords:
            if kw in filename:
                score += 5.0

        return score

    def _extract_title(self, paragraph: str, filename: str) -> str:
        """从段落中提取标题"""
        first_line = paragraph.split("\n")[0]
        if first_line.startswith("## "):
            return first_line.replace("## ", "").strip()
        elif first_line.startswith("# "):
            return first_line.replace("# ", "").strip()
        return filename
