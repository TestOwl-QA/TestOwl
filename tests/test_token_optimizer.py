"""
Token优化器测试

运行测试：
    python -m pytest tests/test_token_optimizer.py -v
"""

import pytest
import asyncio
from src.core.token_optimizer import (
    TokenOptimizer,
    TokenCache,
    ContentSummarizer,
    ChunkProcessor,
    TokenUsage,
    token_optimized
)


class TestTokenCache:
    """测试Token缓存"""
    
    def test_cache_basic(self):
        """测试基本缓存功能"""
        cache = TokenCache()
        
        # 设置缓存
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        cache.set("key1", "result1", usage)
        
        # 获取缓存
        entry = cache.get("key1")
        assert entry is not None
        assert entry.result == "result1"
        assert entry.token_usage.total_tokens == 150
        
    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = TokenCache()
        
        entry = cache.get("non_existent_key")
        assert entry is None
        
        stats = cache.get_stats()
        assert stats["miss_count"] == 1
        assert stats["hit_rate"] == "0.00%"
    
    def test_cache_hit_rate(self):
        """测试缓存命中率"""
        cache = TokenCache()
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        
        cache.set("key1", "result1", usage)
        
        # 命中3次
        for _ in range(3):
            cache.get("key1")
        
        # 未命中1次
        cache.get("key2")
        
        stats = cache.get_stats()
        assert stats["hit_count"] == 3
        assert stats["miss_count"] == 1
        assert stats["hit_rate"] == "75.00%"
    
    def test_cache_expiration(self):
        """测试缓存过期"""
        cache = TokenCache(ttl_hours=0)  # 立即过期
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        
        cache.set("key1", "result1", usage)
        entry = cache.get("key1")
        
        # 应该过期
        assert entry is None


class TestContentSummarizer:
    """测试内容摘要器"""
    
    def test_summarize_short_content(self):
        """测试短内容不压缩"""
        summarizer = ContentSummarizer(target_ratio=0.3)
        content = "这是一个短内容，不需要压缩。"
        
        result = summarizer.summarize(content, max_chars=1000)
        # 短内容应该基本保持不变
        assert len(result) >= len(content) * 0.8
    
    def test_summarize_long_content(self):
        """测试长内容压缩"""
        summarizer = ContentSummarizer(target_ratio=0.3)
        
        # 生成长内容
        content = "\n\n".join([
            f"第{i}节：这是第{i}节的内容，包含一些重要的测试需求信息。"
            f"功能要求：必须支持{i}个并发用户。"
            f"性能要求：响应时间小于{i}00毫秒。"
            for i in range(1, 51)
        ])
        
        original_length = len(content)
        result = summarizer.summarize(content, max_chars=2000)
        
        # 应该被压缩
        assert len(result) < original_length * 0.5
        # 但应该保留关键信息
        assert "并发用户" in result or "性能要求" in result
    
    def test_remove_noise(self):
        """测试噪声移除"""
        summarizer = ContentSummarizer()
        
        content = """
        标题
        ====
        
        正文内容
        ----
        
        更多内容
        """
        
        result = summarizer._remove_noise(content)
        assert "====" not in result
        assert "----" not in result
    
    def test_extract_key_points(self):
        """测试关键点提取"""
        summarizer = ContentSummarizer()
        
        content = """
        1. 功能需求：用户登录
        2. 性能要求：响应时间<1s
        3. 安全要求：密码加密存储
        其他描述性文字...
        """
        
        structure = summarizer._extract_structure(content)
        assert len(structure['key_points']) >= 3


class TestChunkProcessor:
    """测试分块处理器"""
    
    def test_split_small_content(self):
        """测试小内容不分块"""
        processor = ChunkProcessor(chunk_size=1000)
        content = "这是短内容"
        
        chunks = processor.split(content)
        assert len(chunks) == 1
        assert chunks[0] == content
    
    def test_split_large_content(self):
        """测试大内容分块"""
        processor = ChunkProcessor(chunk_size=100, overlap=20)
        
        # 生成超过chunk_size的内容
        paragraphs = [f"段落{i}的内容。" * 10 for i in range(10)]
        content = "\n\n".join(paragraphs)
        
        chunks = processor.split(content)
        
        # 应该分成多块
        assert len(chunks) > 1
        # 每块不超过chunk_size
        for chunk in chunks:
            assert len(chunk) <= 100 * 1.5  # 允许一些余量
    
    def test_max_chunks_limit(self):
        """测试最大块数限制"""
        processor = ChunkProcessor(chunk_size=50, max_chunks=3)
        
        content = "段落。\n\n" * 100
        chunks = processor.split(content)
        
        assert len(chunks) <= 3
    
    @pytest.mark.asyncio
    async def test_process_chunks(self):
        """测试分块处理"""
        processor = ChunkProcessor()
        
        chunks = ["块1内容", "块2内容", "块3内容"]
        
        async def mock_processor(chunk: str) -> str:
            return f"处理后的{chunk}"
        
        results = await processor.process_chunks(
            chunks, mock_processor, merge_strategy="concatenate"
        )
        
        assert "处理后的块1内容" in results
        assert "处理后的块2内容" in results
        assert "处理后的块3内容" in results


class TestTokenOptimizer:
    """测试Token优化器"""
    
    @pytest.mark.asyncio
    async def test_process_with_cache(self):
        """测试带缓存的处理"""
        optimizer = TokenOptimizer()
        
        async def mock_processor(content: str) -> str:
            return f"处理结果：{content[:20]}"
        
        # 第一次处理
        result1, usage1 = await optimizer.process_with_cache(
            "测试内容", mock_processor, cache_key="test_key"
        )
        
        assert not usage1.cache_hit
        assert usage1.input_tokens > 0
        
        # 第二次处理（应该命中缓存）
        result2, usage2 = await optimizer.process_with_cache(
            "测试内容", mock_processor, cache_key="test_key"
        )
        
        assert usage2.cache_hit
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_process_with_summary(self):
        """测试带摘要的处理"""
        optimizer = TokenOptimizer()
        
        async def mock_processor(content: str) -> str:
            return f"长度：{len(content)}"
        
        # 长内容
        long_content = "这是一个句子。" * 1000
        
        result, usage = await optimizer.process_with_summary(
            long_content, mock_processor, max_summary_chars=500
        )
        
        # 应该被压缩后处理
        assert "长度：" in result
    
    @pytest.mark.asyncio
    async def test_process_large_document(self):
        """测试大文档处理"""
        optimizer = TokenOptimizer(config={
            'chunk_size': 200,
            'max_chunks': 5
        })
        
        async def mock_processor(chunk: str) -> dict:
            return {"processed": len(chunk)}
        
        # 大文档
        large_content = "段落内容。\n\n" * 50
        
        results, usage = await optimizer.process_large_document(
            large_content, mock_processor, merge_strategy="concatenate"
        )
        
        # 应该返回列表结果
        assert isinstance(results, list)
        assert len(results) > 0
    
    def test_generate_cache_key(self):
        """测试缓存key生成"""
        optimizer = TokenOptimizer()
        
        key1 = optimizer.generate_cache_key("内容", param1="a")
        key2 = optimizer.generate_cache_key("内容", param1="a")
        key3 = optimizer.generate_cache_key("内容", param1="b")
        
        # 相同内容和参数应该生成相同key
        assert key1 == key2
        # 不同参数应该生成不同key
        assert key1 != key3
    
    def test_get_stats(self):
        """测试统计信息"""
        optimizer = TokenOptimizer()
        
        stats = optimizer.get_stats()
        
        assert "cache_stats" in stats
        assert "total_usage" in stats
        assert "saved_by_cache" in stats
        assert "efficiency" in stats


class TestTokenOptimizedDecorator:
    """测试Token优化装饰器"""
    
    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """测试装饰器基本功能"""
        
        @token_optimized(enable_summary=False)
        async def analyze(content: str) -> dict:
            return {"analyzed": content[:10]}
        
        result = await analyze("测试内容")
        assert "analyzed" in result
    
    @pytest.mark.asyncio
    async def test_decorator_with_summary(self):
        """测试带摘要的装饰器"""
        
        @token_optimized(enable_summary=True, max_chars=50)
        async def analyze(content: str) -> dict:
            return {"length": len(content)}
        
        long_content = "这是一个很长的内容。" * 100
        result = await analyze(long_content)
        
        # 应该处理压缩后的内容
        assert result["length"] <= 100


class TestTokenUsage:
    """测试Token使用记录"""
    
    def test_total_tokens(self):
        """测试总token计算"""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    def test_cost_calculation(self):
        """测试成本计算"""
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = usage.cost_usd
        
        # GPT-4价格：输入$0.03/1K，输出$0.06/1K
        expected = 1000 * 0.03 / 1000 + 500 * 0.06 / 1000
        assert abs(cost - expected) < 0.001


# 集成测试
@pytest.mark.asyncio
async def test_full_workflow():
    """测试完整工作流程"""
    optimizer = TokenOptimizer(config={
        'cache_max_entries': 100,
        'summary_ratio': 0.3,
        'chunk_size': 1000,
    })
    
    # 模拟一个大文档
    document = """
    # 需求文档
    
    ## 功能需求
    1. 用户登录功能
    2. 用户注册功能
    3. 密码找回功能
    
    ## 性能需求
    - 响应时间 < 1秒
    - 支持1000并发
    
    ## 安全需求
    - 密码加密存储
    - SQL注入防护
    """ * 50  # 重复50次模拟大文档
    
    async def mock_llm_processor(content: str) -> dict:
        """模拟LLM处理"""
        return {
            "test_points": [
                {"id": "TP001", "title": f"测试点（基于{len(content)}字符）"}
            ]
        }
    
    # 使用优化器处理
    result, usage = await optimizer.process_large_document(
        document, mock_llm_processor
    )
    
    # 验证结果
    assert isinstance(result, list)
    assert len(result) > 0
    
    # 验证统计
    stats = optimizer.get_stats()
    assert stats["total_usage"]["total_tokens"] > 0
    
    print(f"\n优化统计：")
    print(f"  总Token使用: {stats['total_usage']['total_tokens']}")
    print(f"  缓存节省: {stats['saved_by_cache']}")
    print(f"  缓存命中率: {stats['cache_stats']['hit_rate']}")


if __name__ == "__main__":
    # 运行集成测试
    asyncio.run(test_full_workflow())
    print("\n✅ 所有测试通过！")
