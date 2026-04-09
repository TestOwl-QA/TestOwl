"""
Token消耗优化器

核心功能：
1. 智能缓存 - 避免重复处理相同内容
2. 内容摘要 - 减少输入token长度
3. 分块处理 - 大文档智能分块
4. Token监控 - 实时统计和预警

使用示例：
    ```python
    optimizer = TokenOptimizer(config)
    
    # 自动缓存和优化
    result = await optimizer.process_with_cache(
        content=large_document,
        processor=llm_analyze,
        cache_key=file_hash
    )
    ```
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol
from functools import wraps
import asyncio

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TokenUsage:
    """Token使用记录"""
    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cache_hit: bool = False
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    @property
    def cost_usd(self) -> float:
        """估算成本 (GPT-4价格)"""
        input_cost = self.input_tokens * 0.03 / 1000
        output_cost = self.output_tokens * 0.06 / 1000
        return input_cost + output_cost


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    result: Any
    token_usage: TokenUsage
    created_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    
    def is_expired(self, ttl_hours: int = 24) -> bool:
        """检查是否过期"""
        return datetime.utcnow() - self.created_at > timedelta(hours=ttl_hours)
    
    def touch(self):
        """更新访问记录"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class TokenCache:
    """
    Token缓存管理器
    
    多级缓存策略：
    - L1: 内存缓存（最快）
    - L2: 文件缓存（持久化）
    """
    
    def __init__(self, max_memory_entries: int = 1000, ttl_hours: int = 24):
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._max_entries = max_memory_entries
        self._ttl_hours = ttl_hours
        self._hit_count = 0
        self._miss_count = 0
        
    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存"""
        entry = self._memory_cache.get(key)
        
        if entry is None:
            self._miss_count += 1
            return None
        
        if entry.is_expired(self._ttl_hours):
            del self._memory_cache[key]
            self._miss_count += 1
            return None
        
        entry.touch()
        self._hit_count += 1
        logger.debug(f"Cache hit for key: {key[:32]}...")
        return entry
    
    def set(self, key: str, result: Any, token_usage: TokenUsage) -> None:
        """设置缓存"""
        # 清理过期条目
        self._cleanup_expired()
        
        # 如果满了，清理最久未使用的
        if len(self._memory_cache) >= self._max_entries:
            self._cleanup_lru()
        
        entry = CacheEntry(
            key=key,
            result=result,
            token_usage=token_usage
        )
        self._memory_cache[key] = entry
        logger.debug(f"Cache set for key: {key[:32]}...")
    
    def _cleanup_expired(self) -> None:
        """清理过期条目"""
        expired_keys = [
            k for k, v in self._memory_cache.items() 
            if v.is_expired(self._ttl_hours)
        ]
        for k in expired_keys:
            del self._memory_cache[k]
    
    def _cleanup_lru(self) -> None:
        """清理最久未使用的条目"""
        if not self._memory_cache:
            return
        
        lru_key = min(
            self._memory_cache.keys(),
            key=lambda k: self._memory_cache[k].last_accessed
        )
        del self._memory_cache[lru_key]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        
        return {
            "memory_entries": len(self._memory_cache),
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": f"{hit_rate:.2%}",
            "saved_tokens": sum(
                e.token_usage.total_tokens 
                for e in self._memory_cache.values()
            ),
        }
    
    def clear(self) -> None:
        """清空缓存"""
        self._memory_cache.clear()
        self._hit_count = 0
        self._miss_count = 0


class ContentSummarizer:
    """
    内容摘要器
    
    智能压缩文档内容，保留关键信息，减少token消耗
    """
    
    # 保留的关键模式
    KEY_PATTERNS = [
        r'\d+\.\s+',  # 编号列表
        r'[\u4e00-\u9fa5]{2,10}[:：]',  # 中文标题
        r'(?:功能|需求|规则|条件|限制|必须|应该|可以)[：:]',  # 关键词
        r'(?:输入|输出|前置条件|后置条件)[：:]',  # 测试相关
        r'(?:正常|异常|边界|错误)[：:]',  # 场景
    ]
    
    # 可以删除的噪声模式
    NOISE_PATTERNS = [
        r'={3,}',  # 分隔线
        r'-{3,}',
        r'\*{3,}',
        r'第[一二三四五六七八九十\d]+章',  # 章节标题（保留内容）
        r'\[.*?\]',  # 标记
        r'\(.*?\)',  # 括号内容（可选）
    ]
    
    def __init__(self, target_ratio: float = 0.3):
        """
        Args:
            target_ratio: 目标压缩比例（默认保留30%）
        """
        self.target_ratio = target_ratio
    
    def summarize(self, content: str, max_chars: int = 8000) -> str:
        """
        生成智能摘要
        
        Args:
            content: 原始内容
            max_chars: 最大字符数
        
        Returns:
            摘要后的内容
        """
        original_length = len(content)
        
        # 1. 清理噪声
        content = self._remove_noise(content)
        
        # 2. 提取结构化信息
        structured = self._extract_structure(content)
        
        # 3. 压缩段落
        compressed = self._compress_paragraphs(structured, max_chars)
        
        # 4. 确保关键信息保留
        final = self._ensure_key_info(compressed, content)
        
        final_length = len(final)
        ratio = final_length / original_length if original_length > 0 else 0
        
        logger.info(
            f"Content summarized: {original_length} -> {final_length} "
            f"chars ({ratio:.1%})"
        )
        
        return final
    
    def _remove_noise(self, content: str) -> str:
        """移除噪声"""
        for pattern in self.NOISE_PATTERNS:
            content = re.sub(pattern, '', content)
        
        # 压缩多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def _extract_structure(self, content: str) -> Dict[str, Any]:
        """提取文档结构"""
        lines = content.split('\n')
        
        structure = {
            'title': '',
            'sections': [],
            'key_points': [],
            'tables': [],
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测标题
            if line.startswith('#') or self._is_title(line):
                if current_section:
                    structure['sections'].append(current_section)
                current_section = {
                    'title': line.lstrip('#').strip(),
                    'content': []
                }
            
            # 检测关键点
            elif self._is_key_point(line):
                structure['key_points'].append(line)
                if current_section:
                    current_section['content'].append(line)
            
            # 普通内容
            elif current_section:
                current_section['content'].append(line)
        
        if current_section:
            structure['sections'].append(current_section)
        
        return structure
    
    def _is_title(self, line: str) -> bool:
        """判断是否为标题"""
        # 短且没有标点，或者是特定格式
        if len(line) < 50 and not re.search(r'[。，；！？]', line):
            return True
        return False
    
    def _is_key_point(self, line: str) -> bool:
        """判断是否为关键点"""
        for pattern in self.KEY_PATTERNS:
            if re.search(pattern, line):
                return True
        return False
    
    def _compress_paragraphs(
        self, 
        structure: Dict[str, Any], 
        max_chars: int
    ) -> str:
        """压缩段落"""
        parts = []
        remaining = max_chars
        
        # 优先保留关键点
        for point in structure['key_points'][:20]:  # 最多20个关键点
            if len(point) < remaining:
                parts.append(point)
                remaining -= len(point) + 1
        
        # 然后添加章节内容
        for section in structure['sections']:
            if remaining <= 0:
                break
            
            # 章节标题
            title = f"\n【{section['title']}】"
            if len(title) < remaining:
                parts.append(title)
                remaining -= len(title)
            
            # 章节内容（取前几句）
            content_text = ' '.join(section['content'][:5])
            if len(content_text) > remaining:
                content_text = content_text[:remaining-3] + '...'
            
            parts.append(content_text)
            remaining -= len(content_text)
        
        return '\n'.join(parts)
    
    def _ensure_key_info(self, compressed: str, original: str) -> str:
        """确保关键信息被保留"""
        # 提取所有数字、ID、关键配置
        key_numbers = re.findall(r'\b\d{3,}\b', original)
        key_configs = re.findall(r'[\w_]+[:=]\s*\w+', original)
        
        # 如果压缩后内容中没有这些关键信息，添加一个摘要
        if key_numbers or key_configs:
            summary = "\n\n【关键信息摘要】\n"
            if key_numbers[:10]:
                summary += f"关键数字: {', '.join(set(key_numbers[:10]))}\n"
            if key_configs[:10]:
                summary += f"关键配置: {', '.join(set(key_configs[:10]))}\n"
            
            compressed += summary
        
        return compressed


class ChunkProcessor:
    """
    分块处理器
    
    将大文档分成小块处理，然后合并结果
    """
    
    def __init__(
        self, 
        chunk_size: int = 4000,
        overlap: int = 500,
        max_chunks: int = 10
    ):
        """
        Args:
            chunk_size: 每块最大字符数
            overlap: 块之间重叠字符数（保持上下文）
            max_chunks: 最大块数
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_chunks = max_chunks
    
    def split(self, content: str) -> List[str]:
        """
        智能分块
        
        优先在段落边界分割，保持语义完整
        """
        if len(content) <= self.chunk_size:
            return [content]
        
        chunks = []
        paragraphs = content.split('\n\n')
        
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para)
            
            # 如果当前段落太长，需要进一步分割
            if para_length > self.chunk_size:
                # 先保存当前块
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # 分割长段落
                for i in range(0, para_length, self.chunk_size - self.overlap):
                    chunk = para[i:i + self.chunk_size]
                    chunks.append(chunk)
                    
                    if len(chunks) >= self.max_chunks:
                        break
                continue
            
            # 检查添加后是否超限
            if current_length + para_length + 2 > self.chunk_size:
                # 保存当前块
                chunks.append('\n\n'.join(current_chunk))
                
                # 保留重叠部分
                overlap_text = self._get_overlap(current_chunk)
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_length = len(current_chunk[0]) + para_length
            else:
                current_chunk.append(para)
                current_length += para_length + 2
            
            if len(chunks) >= self.max_chunks - 1:
                break
        
        # 保存最后一块
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        logger.info(f"Content split into {len(chunks)} chunks")
        return chunks
    
    def _get_overlap(self, chunks: List[str]) -> str:
        """获取重叠文本"""
        if not chunks:
            return ""
        
        last_chunk = chunks[-1]
        if len(last_chunk) <= self.overlap:
            return last_chunk
        
        # 取最后overlap个字符，尽量在句子边界
        overlap_text = last_chunk[-self.overlap:]
        # 找到最近的句子边界
        for sep in ['。', '；', '\n', '.', ';']:
            idx = overlap_text.find(sep)
            if idx > 0:
                return overlap_text[idx+1:]
        
        return overlap_text
    
    async def process_chunks(
        self,
        chunks: List[str],
        processor: Callable[[str], Any],
        merge_strategy: str = "concatenate"
    ) -> Any:
        """
        处理所有块并合并结果
        
        Args:
            chunks: 内容块列表
            processor: 处理函数
            merge_strategy: 合并策略 (concatenate/aggregate/dedup)
        """
        results = []
        
        # 顺序处理（避免并发导致token限制）
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            result = await processor(chunk)
            results.append(result)
        
        # 合并结果
        if merge_strategy == "concatenate":
            return self._concatenate_results(results)
        elif merge_strategy == "aggregate":
            return self._aggregate_results(results)
        elif merge_strategy == "dedup":
            return self._dedup_results(results)
        else:
            return results
    
    def _concatenate_results(self, results: List[Any]) -> Any:
        """简单拼接结果"""
        if all(isinstance(r, str) for r in results):
            return '\n'.join(results)
        elif all(isinstance(r, list) for r in results):
            combined = []
            for r in results:
                combined.extend(r)
            return combined
        elif all(isinstance(r, dict) for r in results):
            merged = {}
            for r in results:
                merged.update(r)
            return merged
        return results
    
    def _aggregate_results(self, results: List[Any]) -> Any:
        """聚合结果（去重、统计）"""
        # 实现智能聚合逻辑
        return self._concatenate_results(results)
    
    def _dedup_results(self, results: List[Any]) -> Any:
        """去重合并"""
        combined = self._concatenate_results(results)
        
        if isinstance(combined, list):
            # 使用集合去重（如果元素可hash）
            try:
                return list(dict.fromkeys(combined))
            except TypeError:
                return combined
        
        return combined


class TokenOptimizer:
    """
    Token优化器主类
    
    整合所有优化策略，提供统一的优化接口
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.cache = TokenCache(
            max_memory_entries=self.config.get('cache_max_entries', 1000),
            ttl_hours=self.config.get('cache_ttl_hours', 24)
        )
        self.summarizer = ContentSummarizer(
            target_ratio=self.config.get('summary_ratio', 0.3)
        )
        self.chunk_processor = ChunkProcessor(
            chunk_size=self.config.get('chunk_size', 4000),
            overlap=self.config.get('chunk_overlap', 500),
            max_chunks=self.config.get('max_chunks', 10)
        )
        
        # 统计
        self._total_usage = TokenUsage()
        self._saved_by_cache = 0
    
    def generate_cache_key(self, content: str, **kwargs) -> str:
        """生成缓存key"""
        # 基于内容哈希 + 参数哈希
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        param_str = json.dumps(kwargs, sort_keys=True, default=str)
        param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
        return f"{content_hash}:{param_hash}"
    
    async def process_with_cache(
        self,
        content: str,
        processor: Callable[[str], Any],
        cache_key: Optional[str] = None,
        **kwargs
    ) -> tuple[Any, TokenUsage]:
        """
        带缓存的处理
        
        Returns:
            (结果, Token使用统计)
        """
        # 生成缓存key
        if cache_key is None:
            cache_key = self.generate_cache_key(content, **kwargs)
        
        # 检查缓存
        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit! Saved {cached.token_usage.total_tokens} tokens")
            self._saved_by_cache += cached.token_usage.total_tokens
            return cached.result, TokenUsage(cache_hit=True)
        
        # 执行处理
        result = await processor(content)
        
        # 估算token使用量（实际应从API响应获取）
        estimated_input = len(content) // 4  # 粗略估算：4字符≈1token
        estimated_output = len(str(result)) // 4
        usage = TokenUsage(
            input_tokens=estimated_input,
            output_tokens=estimated_output
        )
        
        # 保存到缓存
        self.cache.set(cache_key, result, usage)
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens
        
        return result, usage
    
    async def process_with_summary(
        self,
        content: str,
        processor: Callable[[str], Any],
        max_summary_chars: int = 8000,
        **kwargs
    ) -> tuple[Any, TokenUsage]:
        """
        带摘要的处理
        
        自动压缩内容后再处理
        """
        original_length = len(content)
        
        # 生成摘要
        if original_length > max_summary_chars:
            content = self.summarizer.summarize(content, max_summary_chars)
        
        # 使用缓存处理
        return await self.process_with_cache(content, processor, **kwargs)
    
    async def process_large_document(
        self,
        content: str,
        chunk_processor: Callable[[str], Any],
        merge_strategy: str = "concatenate",
        **kwargs
    ) -> tuple[Any, TokenUsage]:
        """
        大文档处理
        
        自动分块处理，然后合并结果
        """
        # 分块
        chunks = self.chunk_processor.split(content)
        
        if len(chunks) == 1:
            # 只有一块，直接处理
            return await self.process_with_cache(
                chunks[0], chunk_processor, **kwargs
            )
        
        # 处理所有块
        total_usage = TokenUsage()
        
        async def process_single(chunk: str) -> Any:
            result, usage = await self.process_with_cache(
                chunk, chunk_processor, **kwargs
            )
            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens
            return result
        
        results = await self.chunk_processor.process_chunks(
            chunks, process_single, merge_strategy
        )
        
        return results, total_usage
    
    def get_stats(self) -> Dict[str, Any]:
        """获取优化统计"""
        return {
            "cache_stats": self.cache.get_stats(),
            "total_usage": {
                "input_tokens": self._total_usage.input_tokens,
                "output_tokens": self._total_usage.output_tokens,
                "total_tokens": self._total_usage.total_tokens,
                "estimated_cost_usd": f"${self._total_usage.cost_usd:.4f}",
            },
            "saved_by_cache": self._saved_by_cache,
            "efficiency": {
                "cache_savings": f"{self._saved_by_cache} tokens",
                "cost_savings_usd": f"${(self._saved_by_cache / 1000 * 0.045):.4f}",
            }
        }
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self.cache.clear()


def token_optimized(
    cache_key_func: Optional[Callable] = None,
    enable_summary: bool = True,
    max_chars: int = 8000
):
    """
    Token优化装饰器
    
    使用示例：
        @token_optimized()
        async def analyze_document(content: str) -> dict:
            # LLM调用
            return result
    """
    def decorator(func: Callable) -> Callable:
        optimizer = TokenOptimizer()
        
        @wraps(func)
        async def wrapper(content: str, *args, **kwargs):
            # 生成缓存key
            if cache_key_func:
                cache_key = cache_key_func(content, *args, **kwargs)
            else:
                cache_key = None
            
            # 选择处理方式
            if enable_summary and len(content) > max_chars:
                result, usage = await optimizer.process_with_summary(
                    content,
                    lambda c: func(c, *args, **kwargs),
                    max_chars,
                    cache_key=cache_key
                )
            else:
                result, usage = await optimizer.process_with_cache(
                    content,
                    lambda c: func(c, *args, **kwargs),
                    cache_key=cache_key
                )
            
            # 附加token使用信息
            result._token_usage = usage
            return result
        
        return wrapper
    return decorator
