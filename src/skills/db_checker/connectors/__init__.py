"""
数据库连接器模块

提供统一的数据库连接接口，支持多种数据库类型。

设计原则:
    1. 统一接口: 所有连接器实现相同的抽象基类
    2. 懒连接: 首次查询时才建立真实连接
    3. 自动重连: 连接断开时自动重试
    4. 资源管理: 支持上下文管理器确保连接关闭

支持的驱动:
    - MySQL: PyMySQL (纯Python, 无需额外依赖)
    - PostgreSQL: psycopg2-binary
    - SQLite: 内置 sqlite3
    - SQL Server: pyodbc (可选)
    - MongoDB: pymongo (可选)

使用示例:
    from src.skills.db_checker.connectors import create_connector
    
    # 通过连接字符串创建
    conn = create_connector("mysql://user:pass@localhost:3306/dbname")
    
    # 或通过参数创建
    conn = create_connector(
        db_type="mysql",
        host="localhost",
        port=3306,
        user="root",
        password="pass",
        database="test"
    )
    
    # 使用
    with conn:
        tables = conn.get_tables()
        schema = conn.get_table_schema("users")
"""

from .base import BaseConnector, ConnectionInfo, TableSchema, ColumnInfo, IndexInfo
from .factory import create_connector, supported_drivers

__all__ = [
    "BaseConnector",
    "ConnectionInfo", 
    "TableSchema",
    "ColumnInfo",
    "IndexInfo",
    "create_connector",
    "supported_drivers",
]

# 可选: 延迟导入具体实现，避免强制依赖
# 实际驱动在 factory 中按需导入
try:
    from .mysql import MySQLConnector
    __all__.append("MySQLConnector")
except ImportError:
    pass

try:
    from .postgres import PostgreSQLConnector
    __all__.append("PostgreSQLConnector")
except ImportError:
    pass

try:
    from .sqlite import SQLiteConnector
    __all__.append("SQLiteConnector")
except ImportError:
    pass
