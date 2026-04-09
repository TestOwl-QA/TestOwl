#!/usr/bin/env python3
"""
代码验证脚本

用于验证代码结构是否正确，不依赖外部服务
运行方式：python verify_code.py
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))


def verify_imports():
    """验证所有模块是否能正常导入"""
    print("=" * 60)
    print("📦 验证模块导入")
    print("=" * 60)
    
    modules_to_test = [
        ("核心模块", [
            "src.core.config",
            "src.core.agent", 
            "src.core.exceptions",
        ]),
        ("适配器模块", [
            "src.adapters.llm.client",
            "src.adapters.document.parser",
            "src.adapters.storage.excel_exporter",
            "src.adapters.storage.xmind_exporter",
            "src.adapters.platform.base",
            "src.adapters.platform.jira",
            "src.adapters.platform.zentao",
            "src.adapters.platform.tapd",
            "src.adapters.platform.redmine",
        ]),
        ("技能模块", [
            "src.skills.base",
            "src.skills.document_analyzer.skill",
            "src.skills.test_case_generator.skill",
            "src.skills.bug_tracker.skill",
            "src.skills.table_checker.skill",
        ]),
    ]
    
    all_passed = True
    
    for category, modules in modules_to_test:
        print(f"\n[{category}]")
        for module in modules:
            try:
                __import__(module)
                print(f"  ✅ {module}")
            except ImportError as e:
                print(f"  ❌ {module} - 导入失败: {e}")
                all_passed = False
            except Exception as e:
                print(f"  ⚠️ {module} - 其他错误: {e}")
    
    return all_passed


def verify_class_structure():
    """验证类结构是否正确"""
    print("\n" + "=" * 60)
    print("🏗️ 验证类结构")
    print("=" * 60)
    
    all_passed = True
    
    try:
        # 验证平台适配器继承关系
        from src.adapters.platform.base import PlatformAdapter
        from src.adapters.platform.jira import JiraAdapter
        from src.adapters.platform.zentao import ZentaoAdapter
        from src.adapters.platform.tapd import TapdAdapter
        from src.adapters.platform.redmine import RedmineAdapter
        
        adapters = [
            ("JiraAdapter", JiraAdapter),
            ("ZentaoAdapter", ZentaoAdapter),
            ("TapdAdapter", TapdAdapter),
            ("RedmineAdapter", RedmineAdapter),
        ]
        
        print("\n[平台适配器继承检查]")
        for name, adapter_class in adapters:
            if issubclass(adapter_class, PlatformAdapter):
                print(f"  ✅ {name} 正确继承 PlatformAdapter")
            else:
                print(f"  ❌ {name} 未正确继承 PlatformAdapter")
                all_passed = False
        
        # 验证必要方法存在
        print("\n[必要方法检查]")
        required_methods = ['connect', 'test_connection', 'submit_bug', 'get_bug', 'update_bug', 'search_bugs']
        for name, adapter_class in adapters:
            missing = []
            for method in required_methods:
                if not hasattr(adapter_class, method):
                    missing.append(method)
            
            if missing:
                print(f"  ❌ {name} 缺少方法: {missing}")
                all_passed = False
            else:
                print(f"  ✅ {name} 包含所有必要方法")
                
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
        all_passed = False
    
    return all_passed


def verify_data_models():
    """验证数据模型"""
    print("\n" + "=" * 60)
    print("📊 验证数据模型")
    print("=" * 60)
    
    all_passed = True
    
    try:
        from src.adapters.platform.base import PlatformBug, SubmitResult
        from src.skills.bug_tracker.models import BugReport, BugAnalysis
        
        # 测试 PlatformBug
        print("\n[PlatformBug 测试]")
        bug = PlatformBug(
            title="测试Bug",
            description="这是一个测试Bug",
            severity="high",
            priority="p1"
        )
        print(f"  ✅ 创建成功: {bug.title}")
        
        # 测试 SubmitResult
        print("\n[SubmitResult 测试]")
        result = SubmitResult(
            success=True,
            bug_id="TEST-123",
            bug_url="https://example.com/bug/TEST-123"
        )
        print(f"  ✅ 创建成功: bug_id={result.bug_id}")
        
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
        all_passed = False
    
    return all_passed


def verify_config():
    """验证配置模块"""
    print("\n" + "=" * 60)
    print("⚙️ 验证配置模块")
    print("=" * 60)
    
    all_passed = True
    
    try:
        from src.core.config import Config, LLMConfig, PlatformConfig
        
        # 测试默认配置
        print("\n[默认配置测试]")
        config = Config()
        print(f"  ✅ LLM Provider: {config.llm.provider}")
        print(f"  ✅ LLM Model: {config.llm.model}")
        print(f"  ✅ Output Dir: {config.storage.output_dir}")
        
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
        all_passed = False
    
    return all_passed


def main():
    """主验证流程"""
    print("\n🔍 GameTestAgent 代码验证工具")
    print("此脚本验证代码结构是否正确，不需要连接外部服务\n")
    
    results = []
    
    # 1. 验证导入
    results.append(("模块导入", verify_imports()))
    
    # 2. 验证类结构
    results.append(("类结构", verify_class_structure()))
    
    # 3. 验证数据模型
    results.append(("数据模型", verify_data_models()))
    
    # 4. 验证配置
    results.append(("配置模块", verify_config()))
    
    # 总结
    print("\n" + "=" * 60)
    print("📋 验证总结")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有验证通过！代码结构正确。")
        print("\n下一步:")
        print("1. 复制 config/config.yaml.example 为 config/config.yaml")
        print("2. 填入你的 Kimi API 密钥")
        print("3. 运行 python main.py 测试完整功能")
    else:
        print("⚠️ 部分验证失败，请检查上述错误信息。")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
