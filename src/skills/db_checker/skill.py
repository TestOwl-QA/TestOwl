"""
数据库检查技能 - 主模块

功能:
    1. 数据库连接测试
    2. 表结构检查
    3. 数据完整性验证
    4. 游戏业务规则检查（按类型扩展）

与 table_checker 的区别:
    - table_checker: 检查内存/文件中的表格数据
    - db_checker: 连接真实数据库，支持结构检查和业务规则

架构:
    - 分层设计: 连接器层(connectors) + 规则层(rules)
    - 可扩展: 新增数据库类型只需添加连接器
    - 可配置: 游戏规则通过配置参数调整

使用示例:
    ```python
    from src.skills.db_checker import DBCheckerSkill, DBCheckType
    from src.core.config import Config
    
    config = Config("config.yaml")
    skill = DBCheckerSkill(config)
    
    # 执行连接测试
    context = SkillContext(
        agent=agent,
        config=config,
        params={
            "check_type": DBCheckType.CONNECTION.value,
            "connection": {
                "db_type": "mysql",
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pass",
                "database": "game_db"
            }
        }
    )
    result = await skill.execute(context)
    ```

作者: TestOwl Team
版本: 1.0.0
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.utils.logger import get_logger

# 导入连接器
from .connectors import create_connector, BaseConnector, supported_drivers
from .connectors.base import ConnectionTestResult, TableSchema

# 导入游戏规则
from .rules import get_game_rules, list_supported_types, detect_game_type
from .rules.base import RuleCheckResult

logger = get_logger(__name__)


class DBCheckType(Enum):
    """检查类型枚举"""
    CONNECTION = "connection"           # 连接测试
    STRUCTURE = "structure"             # 表结构检查
    DATA_VALIDATION = "data_validation" # 数据验证
    GAME_RULES = "game_rules"           # 游戏业务规则
    FULL = "full"                       # 完整检查（全部）


@dataclass
class DBCheckConfig:
    """数据库检查配置"""
    # 连接配置
    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    conn_str: Optional[str] = None      # 连接字符串（优先级高于分开的参数）
    
    # 检查配置
    check_type: DBCheckType = DBCheckType.FULL
    target_tables: Optional[List[str]] = None  # 指定检查的表，None表示全部
    game_type: Optional[str] = None     # 游戏类型，用于加载业务规则
    
    # 规则配置
    rule_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_connector_params(self) -> Dict[str, Any]:
        """转换为连接器参数"""
        if self.conn_str:
            return {"conn_str": self.conn_str}
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }


class DBCheckerSkill(BaseSkill):
    """
    数据库检查技能
    
    支持多种数据库类型和游戏业务规则检查。
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        self._connector: Optional[BaseConnector] = None
    
    @property
    def name(self) -> str:
        return "db_checker"
    
    @property
    def description(self) -> str:
        return "数据库连接测试、结构检查、数据验证和游戏业务规则检查"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "check_type",
                "type": "string",
                "required": False,
                "description": "检查类型: connection/structure/data_validation/game_rules/full",
                "default": "full",
            },
            {
                "name": "connection",
                "type": "object",
                "required": True,
                "description": "数据库连接配置",
            },
            {
                "name": "target_tables",
                "type": "array",
                "required": False,
                "description": "指定检查的表名列表",
            },
            {
                "name": "game_type",
                "type": "string",
                "required": False,
                "description": "游戏类型: rpg/card/casual/competitive/simulation",
            },
            {
                "name": "rule_config",
                "type": "object",
                "required": False,
                "description": "规则配置参数",
                "default": {},
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行数据库检查
        
        Args:
            context: 包含检查参数
        
        Returns:
            检查结果
        """
        try:
            # 解析配置
            check_config = self._parse_config(context)
            
            # 创建连接器
            self._connector = create_connector(**check_config.to_connector_params())
            
            # 根据检查类型执行
            check_type = check_config.check_type
            
            if check_type == DBCheckType.CONNECTION:
                result = self._check_connection()
            elif check_type == DBCheckType.STRUCTURE:
                result = self._check_structure(check_config.target_tables)
            elif check_type == DBCheckType.DATA_VALIDATION:
                result = self._check_data_validation(check_config.target_tables)
            elif check_type == DBCheckType.GAME_RULES:
                result = self._check_game_rules(
                    check_config.target_tables,
                    check_config.game_type,
                    check_config.rule_config
                )
            elif check_type == DBCheckType.FULL:
                result = self._check_full(check_config)
            else:
                return SkillResult.fail(f"未知的检查类型: {check_type}")
            
            return SkillResult.ok(data=result)
            
        except Exception as e:
            logger.exception("数据库检查执行失败")
            return SkillResult.fail(f"检查失败: {str(e)}")
        finally:
            # 确保关闭连接
            if self._connector:
                try:
                    self._connector.close()
                except Exception:
                    pass
    
    def _parse_config(self, context: SkillContext) -> DBCheckConfig:
        """解析检查配置"""
        conn_params = context.get_param("connection", {})
        
        # 解析检查类型
        check_type_str = context.get_param("check_type", "full")
        try:
            check_type = DBCheckType(check_type_str)
        except ValueError:
            check_type = DBCheckType.FULL
        
        return DBCheckConfig(
            db_type=conn_params.get("db_type", "mysql"),
            host=conn_params.get("host"),
            port=conn_params.get("port"),
            database=conn_params.get("database"),
            user=conn_params.get("user"),
            password=conn_params.get("password"),
            conn_str=conn_params.get("conn_str"),
            check_type=check_type,
            target_tables=context.get_param("target_tables"),
            game_type=context.get_param("game_type"),
            rule_config=context.get_param("rule_config", {}),
        )
    
    def _check_connection(self) -> Dict[str, Any]:
        """执行连接测试"""
        with self._connector:
            result = self._connector.test_connection()
            
            if result.success:
                server_info = self._connector.get_server_info()
                
                return {
                    "check": "connection",
                    "status": "success",
                    "connection": result.to_dict(),
                    "server_info": server_info,
                }
            else:
                return {
                    "check": "connection",
                    "status": "failed",
                    "connection": result.to_dict(),
                }
    
    def _check_structure(self, target_tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """执行表结构检查"""
        with self._connector:
            # 获取所有表
            all_tables = self._connector.get_tables()
            
            # 确定要检查的表
            if target_tables:
                tables_to_check = [t for t in target_tables if t in all_tables]
                missing_tables = [t for t in target_tables if t not in all_tables]
            else:
                tables_to_check = all_tables
                missing_tables = []
            
            # 检查每个表的结构
            table_schemas = []
            issues = []
            
            for table_name in tables_to_check:
                try:
                    schema = self._connector.get_table_schema(table_name)
                    table_schemas.append(schema.to_dict())
                    
                    # 检查结构问题
                    table_issues = self._analyze_structure_issues(schema)
                    if table_issues:
                        issues.extend(table_issues)
                        
                except Exception as e:
                    issues.append({
                        "table": table_name,
                        "issue": f"获取结构失败: {e}",
                        "severity": "error",
                    })
            
            return {
                "check": "structure",
                "status": "completed",
                "summary": {
                    "total_tables": len(all_tables),
                    "checked_tables": len(tables_to_check),
                    "missing_tables": missing_tables,
                    "issues_count": len(issues),
                },
                "tables": table_schemas,
                "issues": issues,
            }
    
    def _analyze_structure_issues(self, schema: TableSchema) -> List[Dict]:
        """分析表结构问题"""
        issues = []
        
        # 检查主键
        pk_columns = [c for c in schema.columns if c.is_primary_key]
        if not pk_columns:
            issues.append({
                "table": schema.name,
                "issue": "缺少主键",
                "severity": "warning",
                "suggestion": "建议为表添加主键",
            })
        
        # 检查索引
        if len(schema.indexes) <= 1:  # 只有主键索引
            issues.append({
                "table": schema.name,
                "issue": "索引较少",
                "severity": "info",
                "suggestion": "根据查询需求添加适当索引",
            })
        
        # 检查大表
        if schema.row_count and schema.row_count > 1000000:
            issues.append({
                "table": schema.name,
                "issue": f"大表警告: {schema.row_count} 行",
                "severity": "warning",
                "suggestion": "考虑分表或归档策略",
            })
        
        return issues
    
    def _check_data_validation(self, target_tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """执行数据验证（复用 table_checker 的规则引擎）"""
        # 导入 table_checker 的规则引擎
        from src.skills.table_checker.skill import RuleEngine, CheckRule, RuleType
        
        with self._connector:
            # 获取要检查的表
            all_tables = self._connector.get_tables()
            tables_to_check = target_tables if target_tables else all_tables
            
            rule_engine = RuleEngine()
            all_results = []
            
            for table_name in tables_to_check:
                if table_name not in all_tables:
                    continue
                
                # 获取表结构
                schema = self._connector.get_table_schema(table_name)
                
                # 构建默认规则
                rules = self._build_default_rules(schema)
                
                # 获取数据样本（限制数量）
                sample_data = self._connector.execute_query(
                    f"SELECT * FROM `{table_name}` LIMIT 1000"
                )
                
                if sample_data:
                    # 执行检查
                    results = rule_engine.check(sample_data, rules)
                    
                    for r in results:
                        all_results.append({
                            "table": table_name,
                            **r.to_dict(),
                        })
            
            # 汇总
            errors = [r for r in all_results if r.get("severity") == "error"]
            warnings = [r for r in all_results if r.get("severity") == "warning"]
            
            return {
                "check": "data_validation",
                "status": "completed",
                "summary": {
                    "checked_tables": len(tables_to_check),
                    "total_issues": len(all_results),
                    "errors": len(errors),
                    "warnings": len(warnings),
                },
                "results": all_results,
            }
    
    def _build_default_rules(self, schema: TableSchema) -> List:
        """为表构建默认检查规则"""
        from src.skills.table_checker.skill import CheckRule, RuleType
        
        rules = []
        
        for col in schema.columns:
            # 主键唯一性
            if col.is_primary_key:
                rules.append(CheckRule(
                    name=f"{col.name}_唯一性",
                    rule_type=RuleType.UNIQUE,
                    column=col.name,
                    severity="error",
                ))
            
            # 非空检查
            if not col.nullable and not col.default:
                rules.append(CheckRule(
                    name=f"{col.name}_非空",
                    rule_type=RuleType.NOT_NULL,
                    column=col.name,
                    severity="error",
                ))
        
        return rules
    
    def _check_game_rules(
        self,
        target_tables: Optional[List[str]],
        game_type: Optional[str],
        rule_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行游戏业务规则检查"""
        with self._connector:
            # 获取所有表
            all_tables = self._connector.get_tables()
            
            # 自动检测游戏类型
            if not game_type:
                game_type = detect_game_type(all_tables)
                logger.info(f"自动检测到游戏类型: {game_type}")
            
            if not game_type:
                return {
                    "check": "game_rules",
                    "status": "skipped",
                    "message": "无法自动检测游戏类型，请手动指定",
                    "supported_types": list_supported_types(),
                }
            
            # 获取游戏规则
            rule_classes = get_game_rules(game_type)
            if not rule_classes:
                return {
                    "check": "game_rules",
                    "status": "skipped",
                    "message": f"未找到 {game_type} 类型的规则",
                    "supported_types": list_supported_types(),
                }
            
            # 确定要检查的表
            tables_to_check = target_tables if target_tables else all_tables
            
            # 执行规则检查
            all_results = []
            
            for rule_class in rule_classes:
                rule = rule_class(rule_config)
                
                for table_name in tables_to_check:
                    if rule.is_applicable(table_name):
                        try:
                            result = rule.check(self._connector, table_name)
                            all_results.append(result.to_dict())
                        except Exception as e:
                            logger.warning(f"规则 {rule.name} 检查表 {table_name} 失败: {e}")
                            all_results.append({
                                "rule_name": rule.name,
                                "passed": False,
                                "message": f"检查执行失败: {e}",
                                "severity": "error",
                                "table_name": table_name,
                            })
            
            # 汇总
            passed = sum(1 for r in all_results if r.get("passed"))
            failed = len(all_results) - passed
            
            return {
                "check": "game_rules",
                "status": "completed",
                "game_type": game_type,
                "summary": {
                    "total_rules": len(all_results),
                    "passed": passed,
                    "failed": failed,
                },
                "results": all_results,
            }
    
    def _check_full(self, config: DBCheckConfig) -> Dict[str, Any]:
        """执行完整检查"""
        results = {
            "check": "full",
            "connection": None,
            "structure": None,
            "data_validation": None,
            "game_rules": None,
        }
        
        # 1. 连接测试
        conn_result = self._check_connection()
        results["connection"] = conn_result
        
        if conn_result.get("status") != "success":
            results["status"] = "failed"
            results["message"] = "连接测试失败，中止后续检查"
            return results
        
        # 2. 结构检查
        results["structure"] = self._check_structure(config.target_tables)
        
        # 3. 数据验证
        results["data_validation"] = self._check_data_validation(config.target_tables)
        
        # 4. 游戏业务规则
        results["game_rules"] = self._check_game_rules(
            config.target_tables,
            config.game_type,
            config.rule_config
        )
        
        # 汇总
        results["status"] = "completed"
        
        return results
    
    def get_supported_drivers(self) -> Dict[str, Any]:
        """获取支持的驱动列表"""
        return supported_drivers()
    
    def get_supported_game_types(self) -> List[str]:
        """获取支持的游戏类型"""
        return list_supported_types()
