"""
适配器模块

提供与外部系统交互的统一接口：
- llm: 大模型适配器
- document: 文档解析适配器
- storage: 存储导出适配器
- platform: 项目管理平台适配器

注意：为避免循环导入，请直接从子模块导入
例如：
    from src.adapters.llm import LLMClient
    from src.adapters.storage import ExcelExporter
"""

# 不在这里导入，避免循环导入
# 使用时请直接从子模块导入

__all__ = [
    'LLMClient',
    'DocumentParser',
    'ExcelExporter',
    'XmindExporter',
    'PlatformAdapter',
    'PlatformBug',
    'SubmitResult',
    'get_platform_adapter',
    'JiraAdapter',
    'ZentaoAdapter',
    'TapdAdapter',
    'RedmineAdapter',
]