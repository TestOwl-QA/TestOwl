"""
技能基类模块
定义所有技能的通用接口和基础功能
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.agent import GameTestAgent
    from src.core.config import Config


@dataclass
class SkillResult:
    """
    技能执行结果
    
    Attributes:
        success: 是否成功
        data: 返回数据
        error: 错误信息
        metadata: 额外元数据
    """
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, data: Any = None, metadata: Dict[str, Any] = None) -> "SkillResult":
        """创建成功结果"""
        return cls(success=True, data=data, metadata=metadata or {})
    
    @classmethod
    def fail(cls, error: str, metadata: Dict[str, Any] = None) -> "SkillResult":
        """创建失败结果"""
        return cls(success=False, error=error, metadata=metadata or {})


@dataclass
class SkillContext:
    """
    技能执行上下文
    
    Attributes:
        agent: Agent实例
        config: 配置对象
        params: 执行参数
        history: 历史记录
        knowledge_service: 知识库服务（可选）
    """
    agent: "GameTestAgent"
    config: "Config"
    params: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_service: Optional[Any] = None  # 知识库服务，可选
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取参数值"""
        return self.params.get(key, default)
    
    def set_param(self, key: str, value: Any):
        """设置参数值"""
        self.params[key] = value
    
    def get_knowledge_context(self, query: str, max_length: int = 2000) -> str:
        """
        获取知识库上下文（便捷方法）
        
        Args:
            query: 查询关键词
            max_length: 最大长度
        
        Returns:
            知识库上下文文本，无知识库时返回空字符串
        """
        if self.knowledge_service is None:
            return ""
        
        try:
            result = self.knowledge_service.search(query)
            return result.to_context(max_length)
        except Exception:
            return ""


class BaseSkill(ABC):
    """
    技能基类
    
    所有技能都应继承此类，并实现 execute 方法
    """
    
    def __init__(self, config: "Config"):
        self.config = config
        self._initialized = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """技能名称（唯一标识）"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """技能描述"""
        pass
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """技能参数定义"""
        return []
    
    async def initialize(self):
        """异步初始化（子类可重写）"""
        self._initialized = True
    
    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """执行技能"""
        pass
    
    async def cleanup(self):
        """清理资源（子类可重写）"""
        pass
    
    def validate_params(self, context: SkillContext) -> Optional[str]:
        """验证参数"""
        for param in self.parameters:
            name = param.get("name")
            required = param.get("required", False)
            
            if required and name not in context.params:
                return f"缺少必填参数: {name}"
        
        return None
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
