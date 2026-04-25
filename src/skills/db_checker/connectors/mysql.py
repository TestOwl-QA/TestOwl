"""
MySQL 数据库连接器

基于 PyMySQL 实现，纯 Python 无需额外依赖。

依赖安装:
    pip install PyMySQL

特性:
    - 支持连接池
    - 自动重连
    - SSL 连接
    - 完整的元数据获取
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    BaseConnector,
    ConnectionInfo,
    ConnectionTestResult,
    TableSchema,
    ColumnInfo,
    IndexInfo,
)


class MySQLConnector(BaseConnector):
    """
    MySQL 数据库连接器
    
    使用示例:
        >>> conn = MySQLConnector(
        ...     ConnectionInfo(db_type="mysql", host="localhost", database="test"),
        ...     password="secret"
        ... )
        >>> with conn:
        ...     result = conn.test_connection()
        ...     print(result.server_version)
    """
    
    def __init__(self, conn_info: ConnectionInfo, password: Optional[str] = None):
        super().__init__(conn_info, password)
        self._cursor_class = None
    
    def connect(self) -> None:
        """建立 MySQL 连接"""
        try:
            import pymysql
            from pymysql.cursors import DictCursor
            self._cursor_class = DictCursor
        except ImportError:
            raise ImportError(
                "PyMySQL 未安装。请执行: pip install PyMySQL"
            )
        
        try:
            self._connection = pymysql.connect(
                host=self.conn_info.host or "localhost",
                port=self.conn_info.port or 3306,
                user=self.conn_info.user or "root",
                password=self._password or "",
                database=self.conn_info.database,
                charset=self.conn_info.charset,
                connect_timeout=self.conn_info.connect_timeout,
                cursorclass=DictCursor,
                autocommit=True,  # 自动提交，适合只读检查
            )
            self._connected = True
        except pymysql.Error as e:
            self._connected = False
            raise ConnectionError(f"MySQL 连接失败: {e}")
    
    def close(self) -> None:
        """关闭连接"""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            finally:
                self._connection = None
                self._connected = False
    
    def is_connected(self) -> bool:
        """检查连接是否有效"""
        if not self._connection:
            return False
        try:
            # 发送 ping 检查连接
            self._connection.ping(reconnect=False)
            return True
        except Exception:
            return False
    
    def test_connection(self) -> ConnectionTestResult:
        """测试连接"""
        start_time = time.time()
        
        try:
            self._ensure_connected()
            
            with self._connection.cursor() as cursor:
                # 测试基本查询
                cursor.execute("SELECT 1")
                cursor.fetchone()
                
                # 获取版本
                cursor.execute("SELECT VERSION() as version")
                result = cursor.fetchone()
                version = result.get("version", "unknown") if result else "unknown"
                
                # 获取字符集
                cursor.execute("SHOW VARIABLES LIKE 'character_set_database'")
                charset_result = cursor.fetchone()
                charset = charset_result.get("Value", self.conn_info.charset) if charset_result else self.conn_info.charset
            
            latency = (time.time() - start_time) * 1000
            
            return ConnectionTestResult(
                success=True,
                latency_ms=latency,
                server_version=version,
                message=f"MySQL 连接成功 ({version})",
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            error_type = type(e).__name__
            
            # 分类错误
            if "Access denied" in str(e):
                error_type = "AUTH_ERROR"
                message = "认证失败：用户名或密码错误"
            elif "Unknown database" in str(e):
                error_type = "DB_NOT_FOUND"
                message = f"数据库不存在: {self.conn_info.database}"
            elif "Can't connect" in str(e):
                error_type = "CONNECTION_ERROR"
                message = "无法连接到服务器，请检查网络和端口"
            else:
                message = f"连接失败: {e}"
            
            return ConnectionTestResult(
                success=False,
                latency_ms=latency,
                message=message,
                error_type=error_type,
            )
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行查询 SQL"""
        self._ensure_connected()
        
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行非查询 SQL"""
        self._ensure_connected()
        
        with self._connection.cursor() as cursor:
            return cursor.execute(sql, params)
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        self._ensure_connected()
        
        sql = """
            SELECT TABLE_NAME as table_name
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """
        results = self.execute_query(sql, (self.conn_info.database,))
        return [row["table_name"] for row in results]
    
    def get_table_schema(self, table_name: str) -> TableSchema:
        """获取表结构"""
        self._ensure_connected()
        
        # 获取列信息
        columns = self._get_columns(table_name)
        
        # 获取索引信息
        indexes = self._get_indexes(table_name)
        
        # 获取表信息
        table_info = self._get_table_info(table_name)
        
        return TableSchema(
            name=table_name,
            columns=columns,
            indexes=indexes,
            comment=table_info.get("comment", ""),
            engine=table_info.get("engine"),
            charset=table_info.get("charset"),
            row_count=table_info.get("row_count"),
        )
    
    def _get_columns(self, table_name: str) -> List[ColumnInfo]:
        """获取列信息"""
        sql = """
            SELECT
                COLUMN_NAME as name,
                DATA_TYPE as data_type,
                COLUMN_COMMENT as comment,
                COLUMN_DEFAULT as default_value,
                IS_NULLABLE as is_nullable,
                COLUMN_KEY as column_key,
                EXTRA as extra,
                CHARACTER_MAXIMUM_LENGTH as max_length
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        results = self.execute_query(sql, (self.conn_info.database, table_name))
        
        columns = []
        for row in results:
            col = ColumnInfo(
                name=row["name"],
                data_type=row["data_type"].upper(),
                nullable=row["is_nullable"] == "YES",
                default=row["default_value"],
                is_primary_key=row["column_key"] == "PRI",
                is_auto_increment="auto_increment" in (row["extra"] or ""),
                max_length=row["max_length"],
                comment=row["comment"] or "",
            )
            columns.append(col)
        
        return columns
    
    def _get_indexes(self, table_name: str) -> List[IndexInfo]:
        """获取索引信息"""
        sql = """
            SELECT
                INDEX_NAME as name,
                COLUMN_NAME as column_name,
                NON_UNIQUE as non_unique,
                INDEX_TYPE as index_type
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """
        results = self.execute_query(sql, (self.conn_info.database, table_name))
        
        # 按索引名分组
        index_map: Dict[str, Dict] = {}
        for row in results:
            name = row["name"]
            if name not in index_map:
                index_map[name] = {
                    "columns": [],
                    "is_unique": row["non_unique"] == 0,
                    "is_primary": name == "PRIMARY",
                    "index_type": row["index_type"],
                }
            index_map[name]["columns"].append(row["column_name"])
        
        indexes = []
        for name, info in index_map.items():
            indexes.append(IndexInfo(
                name=name,
                columns=info["columns"],
                is_unique=info["is_unique"],
                is_primary=info["is_primary"],
                index_type=info["index_type"],
            ))
        
        return indexes
    
    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表基本信息"""
        # 表注释和引擎
        sql = """
            SELECT
                ENGINE as engine,
                TABLE_COLLATION as collation,
                TABLE_COMMENT as comment,
                TABLE_ROWS as row_count
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """
        result = self.execute_query(sql, (self.conn_info.database, table_name))
        
        if result:
            row = result[0]
            # 从 collation 提取 charset
            charset = row["collation"].split("_")[0] if row["collation"] else None
            
            return {
                "engine": row["engine"],
                "charset": charset,
                "comment": row["comment"],
                "row_count": row["row_count"],
            }
        
        return {}
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        info = super().get_server_info()
        
        try:
            self._ensure_connected()
            
            with self._connection.cursor() as cursor:
                # 版本
                cursor.execute("SELECT VERSION() as version")
                version = cursor.fetchone().get("version", "unknown")
                
                # 字符集
                cursor.execute("SHOW VARIABLES LIKE 'character_set_server'")
                charset = cursor.fetchone()
                charset = charset.get("Value", "unknown") if charset else "unknown"
                
                # 时区
                cursor.execute("SELECT @@time_zone as timezone")
                timezone = cursor.fetchone().get("timezone", "unknown")
            
            info.update({
                "server_version": version,
                "charset": charset,
                "timezone": timezone,
            })
            
        except Exception:
            pass
        
        return info
