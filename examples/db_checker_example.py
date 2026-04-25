"""数据库检查工具使用示例

展示如何使用 db_checker 进行数据库连接测试、结构检查、数据验证和游戏规则检查。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.skills.db_checker import DBCheckerSkill
from src.core.config import Config


async def example_mysql_connection():
    """示例1: MySQL 连接测试"""
    print("=" * 60)
    print("示例1: MySQL 连接测试")
    print("=" * 60)
    
    config = Config()
    skill = DBCheckerSkill(config)
    
    # 方式1: 使用连接字符串
    result = await skill.execute({
        "check_type": "connection",
        "connection": {
            "conn_str": "mysql://root:password@localhost:3306/testdb"
        }
    })
    
    # 方式2: 使用详细配置
    # result = await skill.execute({
    #     "check_type": "connection",
    #     "connection": {
    #         "db_type": "mysql",
    #         "host": "localhost",
    #         "port": 3306,
    #         "database": "testdb",
    #         "user": "root",
    #         "password": "password"
    #     }
    # })
    
    print(result)
    print()


async def example_sqlite_full_check():
    """示例2: SQLite 完整检查"""
    print("=" * 60)
    print("示例2: SQLite 完整检查")
    print("=" * 60)
    
    config = Config()
    skill = DBCheckerSkill(config)
    
    result = await skill.execute({
        "check_type": "full",
        "connection": {
            "conn_str": "sqlite:///path/to/game.db"
        },
        "target_tables": ["players", "items", "quests"],
        "game_type": "rpg",
        "rule_config": {
            "max_level": 100,
            "max_enhance_level": 15
        }
    })
    
    print(result)
    print()


async def example_structure_check():
    """示例3: 仅检查数据库结构"""
    print("=" * 60)
    print("示例3: 数据库结构检查")
    print("=" * 60)
    
    config = Config()
    skill = DBCheckerSkill(config)
    
    result = await skill.execute({
        "check_type": "structure",
        "connection": {
            "conn_str": "postgres://user:pass@localhost:5432/gamedb"
        },
        "target_tables": []  # 空列表表示检查所有表
    })
    
    print(result)
    print()


async def example_rpg_rules():
    """示例4: RPG 游戏规则检查"""
    print("=" * 60)
    print("示例4: RPG 游戏规则检查")
    print("=" * 60)
    
    config = Config()
    skill = DBCheckerSkill(config)
    
    result = await skill.execute({
        "check_type": "game_rules",
        "connection": {
            "conn_str": "mysql://root:password@localhost:3306/rpg_game"
        },
        "game_type": "rpg",
        "rule_config": {
            "max_level": 120,
            "max_enhance_level": 20,
            "max_gold": 999999999
        }
    })
    
    print(result)
    print()


async def main():
    """运行所有示例"""
    print("数据库检查工具使用示例\n")
    print("注意: 请根据实际情况修改连接字符串和配置参数\n")
    
    # 取消注释要运行的示例
    # await example_mysql_connection()
    # await example_sqlite_full_check()
    # await example_structure_check()
    # await example_rpg_rules()
    
    print("提示: 编辑此文件取消注释相应的示例函数来运行")


if __name__ == "__main__":
    asyncio.run(main())
