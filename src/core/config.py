"""
配置管理模块

支持从YAML配置文件和环境变量读取配置
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

from src.core.exceptions import ConfigError

# 加载环境变量
load_dotenv()


@dataclass
class LLMConfig:
    """大模型配置"""
    provider: str = "moonshot"  # 默认使用月之暗面
    api_key: str = ""
    base_url: str = ""
    model: str = "kimi-k2.5"
    temperature: float = 1
    max_tokens: int = 4096
    timeout: int = 60


@dataclass
class DocumentConfig:
    """文档解析配置"""
    supported_formats: List[str] = field(default_factory=lambda: [
        "docx", "pdf", "md", "txt", "html"
    ])
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    encoding: str = "utf-8"


@dataclass
class StorageConfig:
    """存储配置"""
    type: str = "local"  # local, s3, oss
    output_dir: str = "./output"
    
    # S3/OSS配置
    access_key: str = ""
    secret_key: str = ""
    bucket: str = ""
    endpoint: str = ""


@dataclass
class PlatformConfig:
    """项目管理平台配置"""
    name: str = ""  # jira, zentao, redmine, tapd
    enabled: bool = False
    base_url: str = ""
    username: str = ""
    password: str = ""
    api_token: str = ""
    project_key: str = ""


@dataclass
class TableCheckConfig:
    """表检查配置"""
    enabled_rules: List[str] = field(default_factory=lambda: [
        "unique_check",      # 唯一性检查
        "null_check",        # 空值检查
        "format_check",      # 格式检查
        "range_check",       # 范围检查
        "reference_check",   # 引用检查
    ])
    custom_rules_dir: str = "./custom_rules"
    batch_size: int = 1000


@dataclass
class TestCaseConfig:
    """测试用例生成配置"""
    output_format: str = "excel"  # excel, xmind
    template_dir: str = "./templates"
    default_priority: str = "P2"
    include_precondition: bool = True
    include_test_data: bool = True


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径，默认查找 ./config/config.yaml
        """
        self._config_path = config_path or self._find_config_file()
        self._raw_config: Dict[str, Any] = {}
        
        # 各模块配置
        self.llm: LLMConfig = LLMConfig()
        self.document: DocumentConfig = DocumentConfig()
        self.storage: StorageConfig = StorageConfig()
        self.platforms: List[PlatformConfig] = []
        self.table_check: TableCheckConfig = TableCheckConfig()
        self.test_case: TestCaseConfig = TestCaseConfig()
        
        self._load()
    
    def _find_config_file(self) -> str:
        """查找配置文件"""
        possible_paths = [
            "./config/config.yaml",
            "./config.yaml",
            "../config/config.yaml",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        # 如果没有找到配置文件，使用默认配置
        return ""
    
    def _load(self):
        """加载配置"""
        # 1. 从配置文件加载
        if self._config_path and Path(self._config_path).exists():
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._raw_config = yaml.safe_load(f) or {}
        
        # 2. 从环境变量加载（优先级更高）
        self._load_from_env()
        
        # 3. 解析配置到各模块
        self._parse_config()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # LLM配置
        if os.getenv("LLM_API_KEY"):
            self._raw_config.setdefault("llm", {})
            self._raw_config["llm"]["api_key"] = os.getenv("LLM_API_KEY")
        
        if os.getenv("LLM_BASE_URL"):
            self._raw_config.setdefault("llm", {})
            self._raw_config["llm"]["base_url"] = os.getenv("LLM_BASE_URL")
        
        if os.getenv("LLM_MODEL"):
            self._raw_config.setdefault("llm", {})
            self._raw_config["llm"]["model"] = os.getenv("LLM_MODEL")
    
    def _parse_config(self):
        """解析配置到各模块"""
        # LLM配置
        llm_config = self._raw_config.get("llm", {})
        self.llm = LLMConfig(
            provider=llm_config.get("provider", "moonshot"),
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", ""),
            model=llm_config.get("model", "kimi-k2.5"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 4096),
            timeout=llm_config.get("timeout", 60),
        )
        
        # 文档配置
        doc_config = self._raw_config.get("document", {})
        self.document = DocumentConfig(
            supported_formats=doc_config.get("supported_formats", ["docx", "pdf", "md", "txt", "html"]),
            max_file_size=doc_config.get("max_file_size", 50 * 1024 * 1024),
            encoding=doc_config.get("encoding", "utf-8"),
        )
        
        # 存储配置
        storage_config = self._raw_config.get("storage", {})
        self.storage = StorageConfig(
            type=storage_config.get("type", "local"),
            output_dir=storage_config.get("output_dir", "./output"),
            access_key=storage_config.get("access_key", ""),
            secret_key=storage_config.get("secret_key", ""),
            bucket=storage_config.get("bucket", ""),
            endpoint=storage_config.get("endpoint", ""),
        )
        
        # 平台配置
        platforms_config = self._raw_config.get("platforms", [])
        self.platforms = [
            PlatformConfig(
                name=p.get("name", ""),
                enabled=p.get("enabled", False),
                base_url=p.get("base_url", ""),
                username=p.get("username", ""),
                password=p.get("password", ""),
                api_token=p.get("api_token", ""),
                project_key=p.get("project_key", ""),
            )
            for p in platforms_config
        ]
        
        # 表检查配置
        table_config = self._raw_config.get("table_check", {})
        self.table_check = TableCheckConfig(
            enabled_rules=table_config.get("enabled_rules", [
                "unique_check", "null_check", "format_check", 
                "range_check", "reference_check"
            ]),
            custom_rules_dir=table_config.get("custom_rules_dir", "./custom_rules"),
            batch_size=table_config.get("batch_size", 1000),
        )
        
        # 测试用例配置
        tc_config = self._raw_config.get("test_case", {})
        self.test_case = TestCaseConfig(
            output_format=tc_config.get("output_format", "excel"),
            template_dir=tc_config.get("template_dir", "./templates"),
            default_priority=tc_config.get("default_priority", "P2"),
            include_precondition=tc_config.get("include_precondition", True),
            include_test_data=tc_config.get("include_test_data", True),
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取原始配置值
        
        Args:
            key: 配置键，支持点号分隔（如 "llm.api_key"）
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._raw_config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def validate(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            是否有效
        
        Raises:
            ConfigError: 配置无效时抛出
        """
        # 验证LLM配置
        if not self.llm.api_key:
            raise ConfigError("LLM API密钥未配置，请设置 llm.api_key 或环境变量 LLM_API_KEY")
        
        # 验证存储目录
        output_path = Path(self.storage.output_dir)
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
        
        return True


# 全局配置实例
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    获取全局配置实例（单例模式）
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        Config实例
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config(config_path)
    
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> Config:
    """
    重新加载配置
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        新的Config实例
    """
    global _config_instance
    _config_instance = Config(config_path)
    return _config_instance
