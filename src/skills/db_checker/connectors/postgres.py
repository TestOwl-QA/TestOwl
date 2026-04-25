"""
PostgreSQL 数据库连接器

基于 psycopg2 实现。

依赖安装:
    pip install psycopg2-binary

特性:
    - 支持 SSL 连接
    - 完整的元数据获取
    - 支持 schema 命名空间
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


class PostgreSQLConnector(BaseConnector):
    """
    PostgreSQL 数据库连接器
    
    使用示例:
        >>> conn = PostgreSQLConnector(
        ...     ConnectionInfo(db_type="postgres", host="localhost", database="test"),
        ...     password="secret"
        ... )
        >>> with conn:
        ...     tables = conn.get_tables()
    """
    
    def __init__(self, conn_info: ConnectionInfo, password: Optional[str] = None):
        super().__init__(conn_info, password)
        self.schema = "public"  # 默认 schema
    
    def connect(self) -> None:
        """建立 PostgreSQL 连接"""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise ImportError(
                "psycopg2 未安装。请执行: pip install psycopg2-binary"
            )
        
        try:
            self._connection = psycopg2.connect(
                host=self.conn_info.host or "localhost",
                port=self.conn_info.port or 5432,
                user=self.conn_info.user or "postgres",
                password=self._password or "",
                dbname=self.conn_info.database,
                connect_timeout=self.conn_info.connect_timeout,
                sslmode="require" if self.conn_info.ssl_enabled else "prefer",
            )
            self._connected = True
        except psycopg2.Error as e:
            self._connected = False
            raise ConnectionError(f"PostgreSQL 连接失败: {e}")
    
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
            # 执行简单查询检查连接
            with self._connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def test_connection(self) -> ConnectionTestResult:
        """测试连接"""
        start_time = time.time()
        
        try:
            self._ensure_connected()
            
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
            
            latency = (time.time() - start_time) * 1000
            
            return ConnectionTestResult(
                success=True,
                latency_ms=latency,
                server_version=version.split()[1] if version else "unknown",
                message=f"PostgreSQL 连接成功",
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            error_type = type(e).__name__
            
            error_msg = str(e)
            if "password authentication" in error_msg:
                error_type = "AUTH_ERROR"
                message = "认证失败：用户名或密码错误"
            elif "database" in error_msg and "does not exist" in error_msg:
                error_type = "DB_NOT_FOUND"
                message = f"数据库不存在: {self.conn_info.database}"
            elif "could not connect" in error_msg:
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
            
            # 获取列名
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            return []
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行非查询 SQL"""
        self._ensure_connected()
        
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            self._connection.commit()
            return cursor.rowcount
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        self._ensure_connected()
        
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        results = self.execute_query(sql, (self.schema,))
        return [row["table_name"] for row in results]
    
    def get_table_schema(self, table_name: str) -> TableSchema:
        """获取表结构"""
        self._ensure_connected()
        
        columns = self._get_columns(table_name)
        indexes = self._get_indexes(table_name)
        table_info = self._get_table_info(table_name)
        
        return TableSchema(
            name=table_name,
            columns=columns,
            indexes=indexes,
            comment=table_info.get("comment", ""),
            row_count=table_info.get("row_count"),
        )
    
    def _get_columns(self, table_name: str) -> List[ColumnInfo]:
        """获取列信息"""
        sql = """
            SELECT
                column_name as name,
                data_type,
                udt_name as native_type,
                column_default as default_value,
                is_nullable,
                character_maximum_length as max_length,
                col_description(pgc.oid, a.attnum) as comment
            FROM information_schema.columns c
            JOIN pg_class pgc ON pgc.relname = c.table_name
            JOIN pg_attribute a ON a.attrelid = pgc.oid AND a.attname = c.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        results = self.execute_query(sql, (self.schema, table_name))
        
        # 获取主键信息
        pk_columns = self._get_primary_key_columns(table_name)
        
        columns = []
        for row in results:
            col = ColumnInfo(
                name=row["name"],
                data_type=row["data_type"].upper(),
                nullable=row["is_nullable"] == "YES",
                default=row["default_value"],
                is_primary_key=row["name"] in pk_columns,
                is_auto_increment="serial" in (row["native_type"] or "").lower() or
                               "nextval" in str(row["default_value"] or ""),
                max_length=row["max_length"],
                comment=row["comment"] or "",
            )
            columns.append(col)
        
        return columns
    
    def _get_primary_key_columns(self, table_name: str) -> List[str]:
        """获取主键列名"""
        sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_schema = %s
            AND tc.table_name = %s
            AND tc.constraint_type = 'PRIMARY KEY'
        """
        results = self.execute_query(sql, (self.schema, table_name))
        return [row["column_name"] for row in results]
    
    def _get_indexes(self, table_name: str) -> List[IndexInfo]:
        """获取索引信息"""
        sql = """
            SELECT
                indexname as name,
                indexdef as definition
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
        """
        results = self.execute_query(sql, (self.schema, table_name))
        
        indexes = []
        for row in results:
            # 解析 indexdef 提取列名
            # 格式: CREATE [UNIQUE] INDEX name ON table USING method (col1, col2)
            definition = row["definition"]
            is_unique = "UNIQUE" in definition.upper()
            is_primary = row["name"].endswith("_pkey")
            
            # 提取括号内的列名
            import re
            match = re.search(r'\(([^)]+)\)', definition)
            columns = []
            if match:
                columns = [c.strip() for c in match.group(1).split(",")]
            
            indexes.append(IndexInfo(
                name=row["name"],
                columns=columns,
                is_unique=is_unique,
                is_primary=is_primary,
            ))
        
        return indexes
    
    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表基本信息"""
        # 表注释
        sql = """
            SELECT obj_description(oid) as comment
            FROM pg_class
            WHERE relname = %s AND relkind = 'r'
        """
        result = self.execute_query(sql, (table_name,))
        comment = result[0].get("comment") if result else ""
        
        # 行数（近似值）
        sql = f"""
            SELECT reltuples::BIGINT as row_count
            FROM pg_class
            WHERE relname = %s
        """
        result = self.execute_query(sql, (table_name,))
        row_count = result[0].get("row_count") if result else None
        
        return {
            "comment": comment or "",
            "row_count": row_count,
        }
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        info = super().get_server_info()
        
        try:
            self._ensure_connected()
            
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                
                cursor.execute("SHOW server_encoding")
                charset = cursor.fetchone()[0]
                
                cursor.execute("SHOW timezone")
                timezone = cursor.fetchone()[0]
            
            info.update({
                "server_version": version.split()[1] if version else "unknown",
                "charset": charset,
                "timezone": timezone,
            })
            
        except Exception:
            pass
        
        return info
