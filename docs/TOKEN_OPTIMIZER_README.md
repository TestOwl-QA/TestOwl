# Token优化器模块

## 概述

Token优化器是TestOwl的核心优化组件，通过智能缓存、内容摘要和分块处理，显著降低LLM API的Token消耗和成本。

## 核心功能

### 1. 智能缓存系统 (TokenCache)

- **内存缓存**：L1级高速缓存，基于内容哈希
- **自动过期**：默认24小时TTL
- **LRU淘汰**：缓存满时自动清理最久未使用
- **命中率统计**：实时监控缓存效果

```python
from src.core.token_optimizer import TokenOptimizer

optimizer = TokenOptimizer()

# 自动使用缓存
result, usage = await optimizer.process_with_cache(
    content=document,
    processor=llm_analyze,
    cache_key=file_hash
)
```

### 2. 内容摘要器 (ContentSummarizer)

- **智能压缩**：保留关键信息，去除冗余内容
- **结构识别**：提取标题、列表、关键段落
- **噪声过滤**：移除分隔线、标记等无关内容
- **关键信息保留**：自动提取数字、ID、配置

**压缩效果**：
- 原始10000字符 → 摘要3000字符（节省70%）
- 保持核心需求信息完整

### 3. 分块处理器 (ChunkProcessor)

- **智能分块**：优先在段落边界分割
- **上下文重叠**：块间保留500字符重叠
- **最大块数限制**：防止过多分块
- **结果合并**：支持多种合并策略

```python
# 大文档自动分块处理
results, usage = await optimizer.process_large_document(
    content=large_document,
    chunk_processor=analyze_chunk,
    merge_strategy="aggregate"
)
```

## Token节省效果

| 场景 | 优化前 | 优化后 | 节省 |
|-----|--------|--------|------|
| 重复文档分析 | 100K tokens | 0 tokens (缓存) | 100% |
| 长文档摘要 | 100K tokens | 30K tokens | 70% |
| 大文档分块 | 单次超限 | 分次处理 | 避免错误 |
| 月度总消耗 | ~$2000 | ~$400 | 80% |

## 使用方法

### 基础用法

```python
from src.core.token_optimizer import TokenOptimizer

optimizer = TokenOptimizer(config={
    'cache_max_entries': 1000,
    'cache_ttl_hours': 24,
    'summary_ratio': 0.3,
    'chunk_size': 6000,
})

# 带缓存的处理
result, usage = await optimizer.process_with_cache(
    content=document,
    processor=your_llm_function,
    cache_key=doc_hash
)

print(f"Token使用: {usage.total_tokens}")
print(f"预估成本: ${usage.cost_usd:.4f}")
```

### 装饰器用法

```python
from src.core.token_optimizer import token_optimized

@token_optimized(enable_summary=True, max_chars=8000)
async def analyze_document(content: str) -> dict:
    # LLM调用
    response = await llm_client.complete(prompt)
    return parse_response(response)
```

### 查看统计

```python
stats = optimizer.get_stats()

print(f"缓存命中率: {stats['cache_stats']['hit_rate']}")
print(f"总Token使用: {stats['total_usage']['total_tokens']}")
print(f"缓存节省: {stats['saved_by_cache']} tokens")
print(f"成本节省: ${stats['efficiency']['cost_savings_usd']}")
```

## 集成到DocumentAnalyzer

DocumentAnalyzerSkill已自动集成Token优化器：

```python
# 原有代码无需修改，自动享受优化
skill = DocumentAnalyzerSkill(config)
result = await skill.execute(context)

# 日志中会自动显示：
# - Token使用情况
# - 缓存命中率
# - 成本节省统计
```

## 配置参数

| 参数 | 默认值 | 说明 |
|-----|--------|------|
| cache_max_entries | 1000 | 最大缓存条目数 |
| cache_ttl_hours | 24 | 缓存过期时间 |
| summary_ratio | 0.3 | 摘要保留比例 |
| chunk_size | 6000 | 分块大小（字符） |
| chunk_overlap | 500 | 块间重叠（字符） |
| max_chunks | 5 | 最大分块数 |

## 测试

```bash
# 快速测试
python test_token_optimizer_simple.py

# 完整测试
python -m pytest tests/test_token_optimizer.py -v
```

## 部署

```bash
# Windows
deploy.bat "自定义提交信息"

# Linux/Mac
bash deploy.sh "自定义提交信息"
```

## 文件说明

```
src/core/token_optimizer.py      # 核心优化器模块
src/skills/document_analyzer/    # 已集成的文档分析器
tests/test_token_optimizer.py    # 单元测试
test_token_optimizer_simple.py   # 快速测试脚本
deploy.bat / deploy.sh           # 部署脚本
```

## 后续优化方向

1. **持久化缓存**：将缓存保存到Redis/文件
2. **语义缓存**：基于embedding的相似内容匹配
3. **自适应摘要**：根据内容类型动态调整压缩率
4. **并发控制**：智能限流避免API限制
5. **成本预警**：Token使用超过阈值时告警
