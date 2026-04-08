"""
存储适配器基类

定义所有存储导出器的通用接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pathlib import Path

from src.core.config import Config


class StorageAdapter(ABC):
    """
    存储适配器基类
    
    所有导出器（Excel、Xmind、JSON等）都应继承此类
    """
    
    def __init__(self, config: Config):
        """
        初始化存储适配器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.output_dir = Path(config.storage.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    async def export(self, data: Any, output_path: str, **kwargs) -> Dict[str, Any]:
        """
        导出数据
        
        Args:
            data: 要导出的数据
            output_path: 输出文件路径
            **kwargs: 额外参数
        
        Returns:
            导出结果，包含文件路径等信息
        """
        pass
    
    def get_full_path(self, filename: str) -> Path:
        """
        获取完整的输出路径
        
        Args:
            filename: 文件名
        
        Returns:
            完整路径
        """
        return self.output_dir / filename
