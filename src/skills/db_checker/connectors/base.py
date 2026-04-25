"""
数据库连接器抽象基类

定义所有数据库连接器的统一接口和数据结构。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager
import time


@dataclass
class ConnectionInfo:
    """连接信息"""
    db_type: str                          # 数据库类型: mysql/postgres/sqlite/...
    host: Optional[str] = None           # 主机地址
    port: Optional[int] = None           # 端口
    database: Optional[str] = None       # 数据库名
    user: Optional[str] = None           # 用户名
    # 注意: 密码不存储在此，由连接器内部管理
    ssl_enabled: bool = False            # 是否启用SSL
    charset: str = "utf8mb4"             # 字符集
    connect_timeout: int = 30            # 连接超时(秒)
    
    def to_safe_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏敏感信息）"""
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "ssl_enabled": self.ssl_enabled,
            "charset": self.charset,
        }


@dataclass
class ColumnInfo:
    """列信息"""
    name: str                           # 列名
    data_type: str                      # 数据类型
    nullable: bool = True              # 是否可为空
    default: Any = None                # 默认值
    is_primary_key: bool = False       # 是否主键
    is_auto_increment: bool = False    # 是否自增
    max_length: Optional[int] = None   # 最大长度(字符串类型)
    comment: str = ""                  # 注释
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "nullable": self.nullable,
            "default": str(self.default) if self.default is not None else None,
            "is_primary_key": self.is_primary_key,
            "is_auto_increment": self.is_auto_increment,
            "max_length": self.max_length,
            "comment": self.comment,
        }


@dataclass
class IndexInfo:
    """索引信息"""
    name: str                           # 索引名
    columns: List[str] = field(default_factory=list)  # 索引列
    is_unique: bool = False            # 是否唯一索引
    is_primary: bool = False           # 是否主键索引
    index_type: str = "BTREE"          # 索引类型
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "columns": self.columns,
            "is_unique": self.is_unique,
            "is_primary": self.is_primary,
            "index_type": self.index_type,
        }


@dataclass
class TableSchema:
    """表结构信息"""
    name: str                                   # 表名
    columns: List[ColumnInfo] = field(default_factory=list)      # 列列表
    indexes: List[IndexInfo] = field(default_factory=list)       # 索引列表
    comment: str = ""                          # 表注释
    engine: Optional[str] = None              # 存储引擎(MySQL)
    charset: Optional[str] = None             # 字符集
    row_count: Optional[int] = None           # 行数(估算)
    
    def get_column(self, name: str) -> Optional[ColumnInfo]:
        """根据名称获取列信息"""
        for col in self.columns:
            if col.name == name:
                return col
        return None
    
    def get_primary_key(self) -> Optional[ColumnInfo]:
        """获取主键列"""
        for col in self.columns:
            if col.is_primary_key:
                return col
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "columns": [c.to_dict() for c in self.columns],
            "indexes": [i.to_dict() for i in self.indexes],
            "comment": self.comment,
            "engine": self.engine,
            "charset": self.charset,
            "row_count": self.row_count,
        }


@dataclass
class ConnectionTestResult:
    """连接测试结果"""
    success: bool                      # 是否成功
    latency_ms: float                 # 连接延迟(毫秒)
    server_version: str = ""          # 服务器版本
    message: str = ""                 # 结果消息
    error_type: Optional[str] = None  # 错误类型
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "latency_ms": round(self.latency_ms, 2),
            "server_version": self.server_version,
            "message": self.message,
            "error_type": self.error_type,
        }


class BaseConnector(ABC):
    """
    数据库连接器抽象基类
    
    所有具体数据库连接器必须继承此类并实现抽象方法。
    
    使用示例:
        connector = MySQLConnector(host="localhost", user="root", ...)
        
        # 方式1: 上下文管理器（推荐）
        with connector:
            result = connector.test_connection()
            tables = connector.get_tables()
        
        # 方式2: 手动管理
        connector.connect()
        try:
            result = connector.test_connection()
        finally:
            connector.close()
    """
    
    def __init__(self, conn_info: ConnectionInfo, password: Optional[str] = None):
        """
        初始化连接器
        
        Args:
            conn_info: 连接信息（不含密码）
            password: 密码（单独传入，避免在日志中泄露）
        """
        self.conn_info = conn_info
        self._password = password
        self._connection = None
        self._connected = False
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False
    
    @abstractmethod
    def connect(self) -> None:
        """
        建立数据库连接
        
        Raises:
            ConnectionError: 连接失败时抛出
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接是否有效"""
        pass
    
    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """
        测试连接
        
        Returns:
            包含延迟、版本等信息的测试结果
        """
        pass
    
    @abstractmethod
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        执行查询SQL
        
        Args:
            sql: SQL语句
            params: 查询参数（防SQL注入）
        
        Returns:
            查询结果列表，每行是一个字典
        """
        pass
    
    @abstractmethod
    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        """
        执行非查询SQL
        
        Args:
            sql: SQL语句
            params: 执行参数
        
        Returns:
            影响的行数
        """
        pass
    
    @abstractmethod
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        pass
    
    @abstractmethod
    def get_table_schema(self, table_name: str) -> TableSchema:
        """
        获取表结构
        
        Args:
            table_name: 表名
        
        Returns:
            表结构信息
        """
        pass
    
    def get_table_row_count(self, table_name: str) -> int:
        """
        获取表行数
        
        默认实现执行 COUNT(*)，子类可覆盖以优化性能
        """
        result = self.execute_query(f"SELECT COUNT(*) as count FROM `{table_name}`")
        return result[0].get("count", 0) if result else 0
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        获取服务器信息
        
        Returns:
            包含版本、字符集等信息的字典
        """
        return {
            "db_type": self.conn_info.db_type,
            "server_version": "unknown",
            "charset": self.conn_info.charset,
        }
    
    def _ensure_connected(self):
        """确保连接已建立（懒连接）"""
        if not self._connected or not self.is_connected():
            self.connect()


class MockConnector(BaseConnector):
    """
    模拟连接器（用于测试）
    
    不连接真实数据库，返回模拟数据。
    """
    
    def connect(self) -> None:
        self._connected = True
    
    def close(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            success=True,
            latency_ms=0.1,
            server_version="mock-1.0",
            message="模拟连接成功"
        )
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        return []
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        return 0
    
    def get_tables(self) -> List[str]:
        return ["mock_table_1", "mock_table_2"]
    
    def get_table_schema(self, table_name: str) -> TableSchema:
        return TableSchema(
            name=table_name,
            columns=[
                ColumnInfo(name="id", data_type="INT", is_primary_key=True, is_auto_increment=True),
                ColumnInfo(name="name", data_type="VARCHAR", max_length=100, nullable=False),
            ],
            indexes=[
                IndexInfo(name="PRIMARY", columns=["id"], is_primary=True, is_unique=True),
            ]
        )
