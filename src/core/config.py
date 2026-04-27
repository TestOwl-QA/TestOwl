"""
配置管理模块

支持从YAML配置文件和环境变量读取配置
修复: GT-002 配置加载异常 - 增强验证和错误提示
"""

import os
import sys
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
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
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
        # 获取项目根目录（脚本所在目录）
        script_dir = Path(__file__).parent.parent.parent.resolve()
        
        possible_paths = [
            script_dir / "config" / "config.yaml",
            script_dir / "config.yaml",
            Path("./config/config.yaml"),
            Path("./config.yaml"),
            Path("../config/config.yaml"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        # 如果没有找到配置文件，返回默认路径
        return str(script_dir / "config" / "config.yaml")
    
    def _load(self):
        """加载配置"""
        # 1. 从配置文件加载
        if self._config_path and Path(self._config_path).exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._raw_config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ConfigError(
                    f"配置文件格式错误: {e}\n"
                    f"请检查 {self._config_path} 是否为有效的YAML格式"
                )
            except Exception as e:
                raise ConfigError(
                    f"读取配置文件失败: {e}\n"
                    f"配置文件路径: {self._config_path}"
                )
        
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
        # LLM配置 - 优先使用环境变量
        llm_config = self._raw_config.get("llm", {})
        # 如果配置文件中的api_key为空，尝试从环境变量获取
        api_key = llm_config.get("api_key", "")
        if not api_key:
            api_key = os.getenv("LLM_API_KEY", "")
        
        self.llm = LLMConfig(
            provider=llm_config.get("provider", "moonshot"),
            api_key=api_key,
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
        """验证配置是否完整（带友好提示）"""
        missing = []
        
        # 检查 API Key
        if not self.llm.api_key:
            missing.append("LLM API密钥")
        
        # 检查输出目录
        if not self.storage.output_dir:
            missing.append("输出目录")
        
        if missing:
            print("\n" + "=" * 60)
            print("[!] 配置不完整，缺少以下必要项:")
            for item in missing:
                print(f"   - {item}")
            print("\n[指南] 快速修复指南:")
            print("   方式1 - 环境变量（推荐）:")
            print("      set LLM_API_KEY=你的API密钥")
            print("\n   方式2 - 配置文件:")
            print(f"      编辑: {self._config_path}")
            print("      在 llm 部分添加: api_key: 你的API密钥")
            print("=" * 60 + "\n")
            return False
        
        return True
    
    def get_friendly_error(self, error: Exception) -> str:
        """将技术错误转换为友好的提示"""
        error_msg = str(error).lower()
        
        # API Key 相关错误
        if "api key" in error_msg or "authentication" in error_msg or "unauthorized" in error_msg:
            return """
[错误] API 密钥错误

可能原因:
1. API 密钥未配置或配置错误
2. API 密钥已过期
3. API 密钥余额不足

解决方法:
1. 检查环境变量: echo %LLM_API_KEY%
2. 检查配置文件: config/config.yaml
3. 登录 Kimi/DeepSeek 官网确认密钥状态
"""
        
        # 网络相关错误
        if "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
            return """
[错误] 网络连接错误

可能原因:
1. 网络连接不稳定
2. 防火墙阻止了请求
3. API 服务暂时不可用

解决方法:
1. 检查网络连接
2. 尝试切换网络（如使用热点）
3. 稍后重试
"""
        
        # 文件相关错误
        if "file" in error_msg or "not found" in error_msg or "permission" in error_msg:
            return """
[错误] 文件操作错误

可能原因:
1. 文件路径错误
2. 文件被其他程序占用
3. 没有文件读写权限

解决方法:
1. 确认文件路径正确
2. 关闭占用该文件的程序
3. 检查文件夹权限
"""
        
        # 默认错误提示
        return f"""
[错误] 发生错误: {error}

如果问题持续存在:
1. 查看日志: logs/game_test_agent_*.log
2. 检查配置: config/config.yaml
3. 重新运行: python scripts/setup_project.py
"""
    
    def get_config_info(self) -> Dict[str, Any]:
        """
        获取配置信息摘要（用于调试，隐藏敏感信息）
        
        Returns:
            配置信息字典
        """
        return {
            "config_path": self._config_path,
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key_configured": bool(self.llm.api_key),
                "env_api_key_configured": bool(os.getenv("LLM_API_KEY")),
            },
            "storage": {
                "type": self.storage.type,
                "output_dir": self.storage.output_dir,
            },
            "document": {
                "supported_formats": self.document.supported_formats,
            },
        }


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