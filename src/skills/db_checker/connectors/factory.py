"""
数据库连接器工厂

负责根据配置创建对应的数据库连接器。
支持连接字符串解析和参数字典两种方式。
"""

import re
from typing import Dict, List, Optional, Type
from urllib.parse import urlparse

from .base import BaseConnector, ConnectionInfo

# 驱动可用性缓存
_driver_availability: Dict[str, bool] = {}


def _check_driver(module_name: str) -> bool:
    """检查驱动是否可用（带缓存）"""
    if module_name not in _driver_availability:
        try:
            __import__(module_name)
            _driver_availability[module_name] = True
        except ImportError:
            _driver_availability[module_name] = False
    return _driver_availability[module_name]


def supported_drivers() -> Dict[str, Dict[str, any]]:
    """
    获取支持的驱动列表
    
    Returns:
        驱动信息字典，包含可用状态和安装命令
    """
    return {
        "mysql": {
            "available": _check_driver("pymysql"),
            "package": "PyMySQL",
            "install": "pip install PyMySQL",
            "connector_class": "MySQLConnector",
        },
        "postgres": {
            "available": _check_driver("psycopg2"),
            "package": "psycopg2-binary",
            "install": "pip install psycopg2-binary",
            "connector_class": "PostgreSQLConnector",
        },
        "sqlite": {
            "available": True,  # 内置支持
            "package": "sqlite3",
            "install": "无需安装（Python内置）",
            "connector_class": "SQLiteConnector",
        },
        "mssql": {
            "available": _check_driver("pyodbc"),
            "package": "pyodbc",
            "install": "pip install pyodbc",
            "connector_class": "SQLServerConnector",
        },
        "mongodb": {
            "available": _check_driver("pymongo"),
            "package": "pymongo",
            "install": "pip install pymongo",
            "connector_class": "MongoDBConnector",
        },
    }


def _parse_connection_string(conn_str: str) -> tuple:
    """
    解析连接字符串
    
    支持的格式:
        - mysql://user:pass@host:port/dbname?charset=utf8mb4
        - postgres://user:pass@host:port/dbname
        - sqlite:///path/to/db.sqlite3
        - sqlite://:memory:
    
    Returns:
        (conn_info, password) 元组
    """
    parsed = urlparse(conn_str)
    
    # 提取数据库类型
    db_type = parsed.scheme.lower()
    
    # 处理 SQLite 特殊情况
    if db_type == "sqlite":
        # sqlite:///path 或 sqlite://:memory:
        path = parsed.path
        if path.startswith("/"):
            path = path[1:]  # 去掉开头的 /
        
        conn_info = ConnectionInfo(
            db_type="sqlite",
            database=path if path else ":memory:",
        )
        return conn_info, None
    
    # 提取主机、端口、数据库
    host = parsed.hostname or "localhost"
    port = parsed.port
    database = parsed.path.lstrip("/") if parsed.path else None
    
    # 提取用户名和密码
    user = parsed.username
    password = parsed.password
    
    # 从查询参数提取额外配置
    charset = "utf8mb4"
    if parsed.query:
        query_params = dict(param.split("=") for param in parsed.query.split("&") if "=" in param)
        charset = query_params.get("charset", charset)
    
    # 设置默认端口
    if port is None:
        default_ports = {
            "mysql": 3306,
            "postgres": 5432,
            "postgresql": 5432,
            "mssql": 1433,
            "mongodb": 27017,
        }
        port = default_ports.get(db_type, 3306)
    
    # 统一数据库类型名称
    db_type_map = {
        "postgresql": "postgres",
        "mongodb": "mongo",
    }
    db_type = db_type_map.get(db_type, db_type)
    
    conn_info = ConnectionInfo(
        db_type=db_type,
        host=host,
        port=port,
        database=database,
        user=user,
        charset=charset,
    )
    
    return conn_info, password


def create_connector(
    conn_str: Optional[str] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs
) -> BaseConnector:
    """
    创建数据库连接器
    
    支持两种方式:
        1. 连接字符串: create_connector("mysql://user:pass@localhost/db")
        2. 参数方式: create_connector(db_type="mysql", host="localhost", ...)
    
    Args:
        conn_str: 连接字符串（优先级最高）
        db_type: 数据库类型
        host: 主机地址
        port: 端口
        database: 数据库名
        user: 用户名
        password: 密码
        **kwargs: 额外参数
    
    Returns:
        数据库连接器实例
    
    Raises:
        ValueError: 参数无效
        ImportError: 驱动未安装
    
    Examples:
        >>> # 连接字符串方式
        >>> conn = create_connector("mysql://root:pass@localhost:3306/game_db")
        
        >>> # 参数方式
        >>> conn = create_connector(
        ...     db_type="mysql",
        ...     host="localhost",
        ...     port=3306,
        ...     user="root",
        ...     password="pass",
        ...     database="game_db"
        ... )
    """
    # 方式1: 连接字符串
    if conn_str:
        conn_info, parsed_password = _parse_connection_string(conn_str)
        # 连接字符串中的密码优先级高于参数
        if parsed_password:
            password = parsed_password
    
    # 方式2: 参数方式
    elif db_type:
        # 设置默认端口
        if port is None:
            default_ports = {
                "mysql": 3306,
                "postgres": 5432,
                "sqlite": None,
                "mssql": 1433,
                "mongodb": 27017,
            }
            port = default_ports.get(db_type)
        
        conn_info = ConnectionInfo(
            db_type=db_type.lower(),
            host=host,
            port=port,
            database=database,
            user=user,
            **kwargs
        )
    
    else:
        raise ValueError("必须提供 conn_str 或 db_type 参数")
    
    # 检查驱动可用性
    drivers = supported_drivers()
    if conn_info.db_type not in drivers:
        raise ValueError(f"不支持的数据库类型: {conn_info.db_type}。支持的类型: {list(drivers.keys())}")
    
    driver_info = drivers[conn_info.db_type]
    if not driver_info["available"]:
        raise ImportError(
            f"{conn_info.db_type} 驱动未安装。"
            f"请执行: {driver_info['install']}"
        )
    
    # 动态导入并创建连接器
    connector_class_name = driver_info["connector_class"]
    
    try:
        if conn_info.db_type == "mysql":
            from .mysql import MySQLConnector
            return MySQLConnector(conn_info, password)
        elif conn_info.db_type == "postgres":
            from .postgres import PostgreSQLConnector
            return PostgreSQLConnector(conn_info, password)
        elif conn_info.db_type == "sqlite":
            from .sqlite import SQLiteConnector
            return SQLiteConnector(conn_info, password)
        elif conn_info.db_type == "mssql":
            from .mssql import SQLServerConnector
            return SQLServerConnector(conn_info, password)
        elif conn_info.db_type == "mongodb":
            from .mongodb import MongoDBConnector
            return MongoDBConnector(conn_info, password)
    except ImportError as e:
        raise ImportError(f"导入 {connector_class_name} 失败: {e}")
    
    raise ValueError(f"无法创建 {conn_info.db_type} 连接器")


def create_mock_connector() -> BaseConnector:
    """创建模拟连接器（用于测试）"""
    from .base import MockConnector, ConnectionInfo
    return MockConnector(ConnectionInfo(db_type="mock"))
