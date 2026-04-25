"""
SQLite 数据库连接器

基于 Python 内置 sqlite3 模块，无需额外依赖。

特性:
    - 零依赖（Python 内置）
    - 支持内存数据库
    - 支持文件数据库
"""

import sqlite3
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


class SQLiteConnector(BaseConnector):
    """
    SQLite 数据库连接器
    
    使用示例:
        >>> # 文件数据库
        >>> conn = SQLiteConnector(
        ...     ConnectionInfo(db_type="sqlite", database="/path/to/db.sqlite3")
        ... )
        
        >>> # 内存数据库
        >>> conn = SQLiteConnector(
        ...     ConnectionInfo(db_type="sqlite", database=":memory:")
        ... )
        
        >>> with conn:
        ...     tables = conn.get_tables()
    """
    
    def connect(self) -> None:
        """建立 SQLite 连接"""
        try:
            db_path = self.conn_info.database or ":memory:"
            
            # 配置连接
            self._connection = sqlite3.connect(
                db_path,
                timeout=self.conn_info.connect_timeout,
                check_same_thread=False,  # 允许多线程访问
            )
            
            # 设置行工厂为字典形式
            self._connection.row_factory = sqlite3.Row
            
            self._connected = True
            
        except sqlite3.Error as e:
            self._connected = False
            raise ConnectionError(f"SQLite 连接失败: {e}")
    
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
            # 执行简单查询检查
            self._connection.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def test_connection(self) -> ConnectionTestResult:
        """测试连接"""
        start_time = time.time()
        
        try:
            self._ensure_connected()
            
            # 获取版本
            cursor = self._connection.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            
            latency = (time.time() - start_time) * 1000
            
            db_type = "内存数据库" if self.conn_info.database == ":memory:" else "文件数据库"
            
            return ConnectionTestResult(
                success=True,
                latency_ms=latency,
                server_version=version,
                message=f"SQLite {db_type}连接成功 (版本 {version})",
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            
            error_type = type(e).__name__
            if "unable to open" in str(e).lower():
                error_type = "FILE_ERROR"
                message = f"无法打开数据库文件: {self.conn_info.database}"
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
        
        cursor = self._connection.execute(sql, params or ())
        
        # 转换为字典列表
        rows = cursor.fetchall()
        if rows:
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行非查询 SQL"""
        self._ensure_connected()
        
        cursor = self._connection.execute(sql, params or ())
        self._connection.commit()
        return cursor.rowcount
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        self._ensure_connected()
        
        sql = """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """
        results = self.execute_query(sql)
        return [row["name"] for row in results]
    
    def get_table_schema(self, table_name: str) -> TableSchema:
        """获取表结构"""
        self._ensure_connected()
        
        columns = self._get_columns(table_name)
        indexes = self._get_indexes(table_name)
        
        return TableSchema(
            name=table_name,
            columns=columns,
            indexes=indexes,
        )
    
    def _get_columns(self, table_name: str) -> List[ColumnInfo]:
        """获取列信息"""
        # 使用 PRAGMA 获取表信息
        cursor = self._connection.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        
        columns = []
        for row in rows:
            # PRAGMA table_info 返回: (cid, name, type, notnull, dflt_value, pk)
            col = ColumnInfo(
                name=row["name"],
                data_type=row["type"].upper() if row["type"] else "TEXT",
                nullable=not row["notnull"],
                default=row["dflt_value"],
                is_primary_key=bool(row["pk"]),
                is_auto_increment=False,  # SQLite 的 rowid 自动递增，但这里检测不到
            )
            columns.append(col)
        
        return columns
    
    def _get_indexes(self, table_name: str) -> List[IndexInfo]:
        """获取索引信息"""
        # 获取索引列表
        cursor = self._connection.execute(f"PRAGMA index_list({table_name})")
        index_rows = cursor.fetchall()
        
        indexes = []
        for idx_row in index_rows:
            # PRAGMA index_list 返回: (seq, name, unique, origin, partial)
            index_name = idx_row["name"]
            is_unique = bool(idx_row["unique"])
            
            # 获取索引列
            cursor = self._connection.execute(f"PRAGMA index_info({index_name})")
            col_rows = cursor.fetchall()
            # PRAGMA index_info 返回: (seqno, cid, name)
            columns = [col_row["name"] for col_row in col_rows]
            
            indexes.append(IndexInfo(
                name=index_name,
                columns=columns,
                is_unique=is_unique,
                is_primary=index_name.startswith("sqlite_autoindex"),
            ))
        
        return indexes
    
    def get_table_row_count(self, table_name: str) -> int:
        """获取表行数"""
        result = self.execute_query(f"SELECT COUNT(*) as count FROM [{table_name}]")
        return result[0].get("count", 0) if result else 0
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        info = super().get_server_info()
        
        try:
            self._ensure_connected()
            
            cursor = self._connection.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            
            info.update({
                "server_version": version,
                "database_path": self.conn_info.database,
                "is_memory": self.conn_info.database == ":memory:",
            })
            
        except Exception:
            pass
        
        return info
