"""
知识库服务

提供知识库检索能力，支持单例模式和延迟加载
"""

import os
import re
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class KnowledgeResult:
    """知识库检索结果"""
    query: str
    results: List[Dict[str, Any]]
    total_docs: int
    relevance_score: float
    
    def to_context(self, max_length: int = 2000) -> str:
        """转换为上下文文本，用于注入 prompt"""
        if not self.results:
            return ""
        
        context_parts = ["\n## 相关知识库参考"]
        current_length = 0
        
        for result in self.results:
            section = f"\n### [{result.get('filename', '未知来源')}] {result.get('section', '')}\n"
            content = result.get('content', '')
            
            if current_length + len(section) + len(content) > max_length:
                content = content[:max_length - current_length - len(section)] + "..."
            
            context_parts.append(section + content)
            current_length += len(section) + len(content)
            
            if current_length >= max_length:
                break
        
        return "\n".join(context_parts)


class KnowledgeService:
    """
    知识库服务 - 单例模式
    
    功能：
    - 延迟加载知识库文件
    - 基于关键词的快速检索
    - 线程安全的单例实现
    
    使用示例：
        service = KnowledgeService.get_instance()
        result = service.search("数值平衡测试方法")
        context = result.to_context()
    """
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls, knowledge_dir: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls, knowledge_dir: str = None) -> "KnowledgeService":
        """获取单例实例"""
        return cls(knowledge_dir)
    
    def __init__(self, knowledge_dir: str = None):
        if self._initialized and knowledge_dir is None:
            return
        
        self.knowledge_dir = knowledge_dir or os.getenv(
            "KNOWLEDGE_BASE_DIR",
            str(Path(__file__).parent.parent.parent / "knowledge_base")
        )
        self.documents: List[Dict] = []
        self.index: Dict[str, List[int]] = {}
        
        self._load_knowledge_base()
        KnowledgeService._initialized = True
    
    def _load_knowledge_base(self):
        """加载知识库文件"""
        if not os.path.exists(self.knowledge_dir):
            print(f"[KnowledgeService] 知识库目录不存在: {self.knowledge_dir}")
            return
        
        for filename in os.listdir(self.knowledge_dir):
            if filename.endswith(('.md', '.txt', '.markdown')):
                filepath = os.path.join(self.knowledge_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    doc = {
                        'filename': filename,
                        'filepath': filepath,
                        'content': content,
                        'sections': self._parse_sections(content),
                        'keywords': self._extract_keywords(content)
                    }
                    self.documents.append(doc)
                    
                except Exception as e:
                    print(f"[KnowledgeService] 加载文档失败 {filename}: {e}")
        
        self._build_index()
        print(f"[KnowledgeService] 已加载 {len(self.documents)} 个知识库文档")
    
    def _parse_sections(self, content: str) -> List[Dict]:
        """解析文档章节"""
        sections = []
        current_section = {'title': '概述', 'content': '', 'level': 0}
        
        for line in content.split('\n'):
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                if current_section['content'].strip():
                    sections.append(current_section)
                current_section = {
                    'title': header_match.group(2),
                    'content': '',
                    'level': len(header_match.group(1))
                }
            else:
                current_section['content'] += line + '\n'
        
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections
    
    def _extract_keywords(self, content: str) -> set:
        """提取关键词（简化版，不依赖 jieba）"""
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', content)
        stop_words = {'的', '是', '在', '和', '了', '有', '不', '这', '我', '他', '她', '它', '为', '以', '对', '能', '可', '也', '都', '就', '而'}
        return {w for w in words if len(w) >= 2 and w not in stop_words}
    
    def _build_index(self):
        """构建倒排索引"""
        self.index = {}
        for doc_idx, doc in enumerate(self.documents):
            for keyword in doc['keywords']:
                if keyword not in self.index:
                    self.index[keyword] = []
                self.index[keyword].append(doc_idx)
    
    def search(self, query: str, top_k: int = 3) -> KnowledgeResult:
        """
        检索相关知识
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
        
        Returns:
            KnowledgeResult 对象
        """
        if not self.documents:
            return KnowledgeResult(query=query, results=[], total_docs=0, relevance_score=0.0)
        
        query_keywords = self._extract_keywords(query)
        
        # 计算文档相关度
        scores = {}
        for keyword in query_keywords:
            if keyword in self.index:
                for doc_idx in self.index[keyword]:
                    scores[doc_idx] = scores.get(doc_idx, 0) + 1.0
        
        # 精确匹配加分
        for doc_idx, doc in enumerate(self.documents):
            if query in doc['content']:
                scores[doc_idx] = scores.get(doc_idx, 0) + 5.0
        
        # 章节级别匹配
        section_results = []
        for doc_idx, doc in enumerate(self.documents):
            for section in doc['sections']:
                section_score = sum(1 for kw in query_keywords if kw in section['content'])
                if section_score > 0:
                    section_results.append({
                        'doc_idx': doc_idx,
                        'filename': doc['filename'],
                        'section': section['title'],
                        'content': section['content'][:500] + "..." if len(section['content']) > 500 else section['content'],
                        'score': section_score
                    })
        
        section_results.sort(key=lambda x: x['score'], reverse=True)
        relevance_score = max((r['score'] for r in section_results), default=0) / max(len(query_keywords), 1)
        
        return KnowledgeResult(
            query=query,
            results=section_results[:top_k],
            total_docs=len(self.documents),
            relevance_score=relevance_score
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        return {
            'total_docs': len(self.documents),
            'total_keywords': len(self.index),
            'documents': [{'filename': doc['filename'], 'sections': len(doc['sections'])} for doc in self.documents]
        }


# 便捷函数
_knowledge_service = None

def get_knowledge_service() -> KnowledgeService:
    """获取知识库服务实例"""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService.get_instance()
    return _knowledge_service
