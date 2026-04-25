"""
数据库检查技能模块

提供真实数据库的连接测试、结构检查、数据验证功能。
支持多种数据库类型和游戏业务规则扩展。

与 table_checker 的关系：
- table_checker: 检查内存/文件中的表格数据
- db_checker: 连接真实数据库进行检查，可复用 table_checker 的规则引擎

作者: TestOwl Team
版本: 1.0.0
创建日期: 2025-01

快速开始:
    from src.skills.db_checker import DBCheckerSkill
    
    skill = DBCheckerSkill(config)
    result = await skill.execute(context)

架构说明:
    - skill.py: 主技能类，协调各组件
    - connectors/: 数据库连接适配器
    - rules/: 游戏类型业务规则
"""

from .skill import DBCheckerSkill, DBCheckType

__all__ = ["DBCheckerSkill", "DBCheckType"]
