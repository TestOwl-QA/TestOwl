"""
自定义异常类

所有异常都继承自 GameTestAgentError，方便统一捕获和处理
"""


class GameTestAgentError(Exception):
    """Agent基础异常"""
    
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
    
    def __str__(self):
        return f"[{self.error_code}] {self.message}"


class ConfigError(GameTestAgentError):
    """配置相关错误"""
    
    def __init__(self, message: str):
        super().__init__(message, error_code="CONFIG_ERROR")


class SkillError(GameTestAgentError):
    """技能执行错误"""
    
    def __init__(self, skill_name: str, message: str):
        super().__init__(f"Skill '{skill_name}': {message}", error_code="SKILL_ERROR")
        self.skill_name = skill_name


class AdapterError(GameTestAgentError):
    """适配器错误"""
    
    def __init__(self, adapter_name: str, message: str):
        super().__init__(f"Adapter '{adapter_name}': {message}", error_code="ADAPTER_ERROR")
        self.adapter_name = adapter_name


class LLMError(AdapterError):
    """大模型调用错误"""
    
    def __init__(self, message: str):
        super().__init__("LLM", message)
        self.error_code = "LLM_ERROR"


class DocumentParseError(AdapterError):
    """文档解析错误"""
    
    def __init__(self, message: str):
        super().__init__("DocumentParser", message)
        self.error_code = "DOCUMENT_PARSE_ERROR"


class PlatformAPIError(AdapterError):
    """项目管理平台API错误"""
    
    def __init__(self, platform: str, message: str):
        super().__init__(f"Platform-{platform}", message)
        self.error_code = "PLATFORM_API_ERROR"
        self.platform = platform


class TableCheckError(SkillError):
    """表检查错误"""
    
    def __init__(self, message: str):
        super().__init__("TableChecker", message)
        self.error_code = "TABLE_CHECK_ERROR"


class PlatformError(GameTestAgentError):
    """平台适配器错误（用于平台初始化、连接等问题）"""
    
    def __init__(self, message: str):
        super().__init__(message, error_code="PLATFORM_ERROR")
