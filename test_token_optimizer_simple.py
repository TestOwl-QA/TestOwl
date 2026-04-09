"""
Token优化器简单测试脚本

运行方式：
    python test_token_optimizer_simple.py
"""

import asyncio
import sys
sys.path.insert(0, 'd:\\QA助手')

from src.core.token_optimizer import (
    TokenOptimizer,
    TokenCache,
    ContentSummarizer,
    ChunkProcessor,
    TokenUsage
)


def test_cache():
    """测试缓存功能"""
    print("\n=== 测试 TokenCache ===")
    cache = TokenCache()
    
    # 设置缓存
    usage = TokenUsage(input_tokens=100, output_tokens=50)
    cache.set("key1", {"result": "test"}, usage)
    
    # 获取缓存
    entry = cache.get("key1")
    if entry:
        print(f"✅ 缓存命中: {entry.result}")
        print(f"   Token使用: {entry.token_usage.total_tokens}")
    else:
        print("❌ 缓存未命中")
    
    # 获取统计
    stats = cache.get_stats()
    print(f"   命中率: {stats['hit_rate']}")
    

def test_summarizer():
    """测试摘要功能"""
    print("\n=== 测试 ContentSummarizer ===")
    summarizer = ContentSummarizer(target_ratio=0.3)
    
    # 长内容
    content = "\n\n".join([
        f"第{i}节：功能需求{i}，必须支持{i}个并发用户。性能要求：响应时间小于{i}00毫秒。"
        for i in range(1, 21)
    ])
    
    original_len = len(content)
    result = summarizer.summarize(content, max_chars=1000)
    result_len = len(result)
    
    print(f"✅ 原始长度: {original_len}")
    print(f"✅ 摘要长度: {result_len}")
    print(f"✅ 压缩比例: {result_len/original_len:.1%}")
    print(f"   摘要预览: {result[:200]}...")


def test_chunk_processor():
    """测试分块功能"""
    print("\n=== 测试 ChunkProcessor ===")
    processor = ChunkProcessor(chunk_size=200, max_chunks=5)
    
    content = "段落内容。\n\n" * 20
    chunks = processor.split(content)
    
    print(f"✅ 分块数量: {len(chunks)}")
    for i, chunk in enumerate(chunks[:3]):
        print(f"   块{i+1}长度: {len(chunk)}")


async def test_optimizer():
    """测试优化器"""
    print("\n=== 测试 TokenOptimizer ===")
    optimizer = TokenOptimizer()
    
    async def mock_processor(content: str):
        return {"processed": len(content), "data": f"Result for {content[:20]}"}
    
    # 测试缓存
    content = "测试内容" * 100
    
    # 第一次处理
    result1, usage1 = await optimizer.process_with_cache(
        content, mock_processor, cache_key="test"
    )
    print(f"✅ 第一次处理: {result1}")
    print(f"   Token使用: {usage1.total_tokens}")
    
    # 第二次处理（应该命中缓存）
    result2, usage2 = await optimizer.process_with_cache(
        content, mock_processor, cache_key="test"
    )
    print(f"✅ 第二次处理（缓存）: cache_hit={usage2.cache_hit}")
    
    # 获取统计
    stats = optimizer.get_stats()
    print(f"\n📊 优化统计:")
    print(f"   总Token使用: {stats['total_usage']['total_tokens']}")
    print(f"   缓存节省: {stats['saved_by_cache']}")
    print(f"   缓存命中率: {stats['cache_stats']['hit_rate']}")
    print(f"   预估成本: {stats['total_usage']['estimated_cost_usd']}")


async def main():
    """主函数"""
    print("=" * 60)
    print("Token优化器测试")
    print("=" * 60)
    
    try:
        test_cache()
        test_summarizer()
        test_chunk_processor()
        await test_optimizer()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
