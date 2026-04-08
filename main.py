#!/usr/bin/env python3
"""
GameTestAgent - 游戏测试智能助手

入口文件，演示如何使用Agent进行各种测试任务
"""

import asyncio
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.agent import GameTestAgent
from src.core.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """主函数"""
    print("=" * 60)
    print("GameTestAgent - 游戏测试智能助手")
    print("=" * 60)
    print()
    
    # 1. 加载配置
    try:
        config = get_config()
        config.validate()
        print("配置加载成功")
    except Exception as e:
        print(f"配置错误: {e}")
        print("\n请检查:")
        print("1. 复制 config/config.yaml.example 为 config/config.yaml")
        print("2. 在配置文件中填入你的 LLM API 密钥")
        return
    
    # 2. 创建Agent
    agent = GameTestAgent(config)
    
    # 3. 注册技能（延迟导入，避免循环导入）
    from src.skills.document_analyzer import DocumentAnalyzerSkill
    from src.skills.test_case_generator import TestCaseGeneratorSkill
    
    agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
    agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
    
    print(f"已注册技能: {', '.join(agent.list_skills())}")
    print()
    print("Agent 初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())