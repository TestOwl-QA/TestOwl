#!/usr/bin/env python3
"""
GameTestAgent 基础使用示例

展示如何使用Agent进行各种测试任务
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent import GameTestAgent
from src.core.config import get_config
from src.skills import DocumentAnalyzerSkill, TestCaseGeneratorSkill


async def example_1_analyze_document():
    """示例1：分析需求文档"""
    print("=" * 60)
    print("示例1：分析需求文档")
    print("=" * 60)
    
    # 创建Agent
    config = get_config()
    agent = GameTestAgent(config)
    agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
    
    # 示例需求
    requirement = """
# 背包系统需求

## 功能概述
玩家可以查看、使用、丢弃、整理背包中的物品。

## 功能详情
1. 背包格子数：初始50格，可通过道具扩展到200格
2. 物品堆叠：同类物品最多堆叠99个
3. 物品分类：装备、消耗品、材料、任务道具
4. 支持拖拽整理、一键整理
5. 物品过期：限时道具过期后自动消失

## 边界条件
- 背包满时无法获得新物品
- 绑定物品无法交易
- 任务道具无法丢弃
"""
    
    # 执行分析
    result = await agent.execute(
        skill_name="document_analyzer",
        params={"content": requirement}
    )
    
    if result.success:
        analysis = result.data
        print(f"✅ 分析完成！")
        print(f"文档标题: {analysis.document_title}")
        print(f"测试要点数量: {len(analysis.test_points)}")
        print(f"\n测试要点列表:")
        for tp in analysis.test_points:
            print(f"  [{tp.priority.value}] {tp.title}")
    else:
        print(f"❌ 失败: {result.error}")


async def example_2_generate_test_cases():
    """示例2：生成测试用例"""
    print("\n" + "=" * 60)
    print("示例2：生成测试用例")
    print("=" * 60)
    
    config = get_config()
    agent = GameTestAgent(config)
    agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
    
    # 直接提供需求文本生成用例
    requirement = """
充值功能需求：
1. 支持支付宝、微信支付
2. 充值金额：6元、30元、68元、128元、328元、648元
3. 首充双倍奖励
4. 充值失败原路退款
5. 充值记录保存90天
"""
    
    result = await agent.execute(
        skill_name="test_case_generator",
        params={
            "requirements_text": requirement,
            "output_format": "json",
            "module_name": "充值系统"
        }
    )
    
    if result.success:
        test_suite = result.data
        print(f"✅ 用例生成完成！")
        print(f"模块: {test_suite.name}")
        print(f"用例总数: {len(test_suite.test_cases)}")
        
        print(f"\n用例列表示例:")
        for tc in test_suite.test_cases[:3]:
            print(f"\n【{tc.id}】{tc.title}")
            print(f"  优先级: {tc.priority}")
            if tc.steps:
                print(f"  步骤:")
                for step in tc.steps:
                    print(f"    {step.step_number}. {step.action}")
                    print(f"       预期: {step.expected_result}")
    else:
        print(f"❌ 失败: {result.error}")


async def example_3_pipeline():
    """示例3：流水线执行（文档分析 -> 生成用例）"""
    print("\n" + "=" * 60)
    print("示例3：流水线执行")
    print("=" * 60)
    
    config = get_config()
    agent = GameTestAgent(config)
    agent.register_skill("document_analyzer", DocumentAnalyzerSkill(config))
    agent.register_skill("test_case_generator", TestCaseGeneratorSkill(config))
    
    requirement = """
邮件系统需求：
1. 支持接收系统邮件和玩家邮件
2. 邮件保存30天，过期自动删除
3. 附件一键领取
4. 支持邮件标记、批量删除
5. 未读邮件有红点提示
"""
    
    # 定义流水线步骤
    pipeline = [
        {
            "skill_name": "document_analyzer",
            "params": {"content": requirement},
            "use_previous_result": True,
        },
        {
            "skill_name": "test_case_generator",
            "params": {
                "output_format": "json",
                "module_name": "邮件系统"
            },
        },
    ]
    
    results = await agent.execute_pipeline(pipeline)
    
    print(f"✅ 流水线执行完成，共{len(results)}步")
    for i, result in enumerate(results, 1):
        status = "✅" if result.success else "❌"
        print(f"  步骤{i}: {status}")


async def main():
    """运行所有示例"""
    print("🎮 GameTestAgent 使用示例\n")
    
    try:
        await example_1_analyze_document()
        await example_2_generate_test_cases()
        await example_3_pipeline()
        
        print("\n" + "=" * 60)
        print("所有示例执行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        print("\n请确保：")
        print("1. 已安装依赖: pip install -r requirements.txt")
        print("2. 已配置API密钥: 复制 config/config.yaml.example 为 config.yaml 并填入密钥")


if __name__ == "__main__":
    asyncio.run(main())
