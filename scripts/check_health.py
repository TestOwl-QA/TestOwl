#!/usr/bin/env python3
"""
TestOwl 代码健康检查脚本
验证项目核心模块是否能正常加载
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


def check_module(name: str, import_func) -> tuple:
    """检查单个模块"""
    try:
        import_func()
        return (name, True, "正常加载")
    except Exception as e:
        return (name, False, str(e))


def main():
    print("=" * 60)
    print("TestOwl 代码健康检查")
    print("=" * 60)
    
    checks = []
    
    # 检查1: 配置系统
    def check_config():
        from src.core.config import Config
        c = Config()
        assert c.llm is not None
    checks.append(check_module("配置系统", check_config))
    
    # 检查2: Agent核心
    def check_agent():
        from src.core.agent import GameTestAgent
        from src.core.config import Config
        config = Config()
        agent = GameTestAgent(config)
        assert agent is not None
    checks.append(check_module("Agent核心", check_agent))
    
    # 检查3: 技能基类
    def check_skill_base():
        from src.skills.base import BaseSkill, SkillContext, SkillResult
        assert SkillResult.ok(data="test") is not None
    checks.append(check_module("技能基类", check_skill_base))
    
    # 检查4: LLM客户端
    def check_llm():
        from src.adapters.llm.client import LLMClient
        from src.core.config import Config
        config = Config()
        # 不初始化客户端，只检查类能加载
        assert LLMClient is not None
    checks.append(check_module("LLM客户端", check_llm))
    
    # 检查5: 文档解析
    def check_document():
        from src.adapters.document.parser import DocumentParser
        from src.core.config import Config
        config = Config()
        parser = DocumentParser(config)
        assert parser is not None
    checks.append(check_module("文档解析", check_document))
    
    # 检查6: 导出功能
    def check_storage():
        from src.adapters.storage.excel_exporter import ExcelExporter
        from src.core.config import Config
        config = Config()
        exporter = ExcelExporter(config)
        assert exporter is not None
    checks.append(check_module("Excel导出", check_storage))
    
    # 检查7: 技能模块
    def check_skills():
        from src.skills.document_analyzer import DocumentAnalyzerSkill
        from src.skills.test_case_generator import TestCaseGeneratorSkill
        from src.skills.table_checker import TableCheckerSkill
        from src.skills.bug_tracker import BugTrackerSkill
        from src.skills.db_checker import DBCheckerSkill
        skills = [
            DocumentAnalyzerSkill, TestCaseGeneratorSkill,
            TableCheckerSkill, BugTrackerSkill, DBCheckerSkill
        ]
        assert len(skills) == 5
    checks.append(check_module("技能模块(5个)", check_skills))
    
    # 检查8: Web API
    def check_web():
        from web.api import app
        assert app is not None
    checks.append(check_module("Web API", check_web))
    
    # 检查9: 路径配置
    def check_paths():
        from pathlib import Path
        required_dirs = ['src', 'web', 'config', 'docs']
        for d in required_dirs:
            assert (PROJECT_ROOT / d).exists(), f"缺少目录: {d}"
    checks.append(check_module("项目结构", check_paths))
    
    # 打印结果
    print()
    for name, status, msg in checks:
        icon = "✅" if status else "❌"
        print(f"{icon} {name:<15} {msg}")
    
    # 统计
    passed = sum(1 for _, s, _ in checks if s)
    total = len(checks)
    print()
    print("=" * 60)
    print(f"检查结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 代码健康度: 优秀 (100%)")
        print("✨ 项目可以正常使用！")
        return 0
    elif passed >= total * 0.8:
        print(f"⚠️  代码健康度: 良好 ({passed/total*100:.0f}%)")
        print("🔧 建议修复上述问题")
        return 1
    else:
        print(f"❌ 代码健康度: 较差 ({passed/total*100:.0f}%)")
        print("🚨 需要修复问题后才能使用")
        return 2


if __name__ == "__main__":
    sys.exit(main())
