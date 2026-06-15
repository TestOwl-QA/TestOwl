"""
适配器模块

提供与外部系统交互的统一接口：
- llm: 大模型适配器
- document: 文档解析适配器

注意：为避免循环导入，请直接从子模块导入
例如：
    from src.adapters.llm import LLMClient
"""

__all__ = [
    'LLMClient',
    'DocumentParser',
]