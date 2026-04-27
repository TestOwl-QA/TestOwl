#!/usr/bin/env python3
"""
TestOwl 一键诊断工具
专为没有代码基础的用户设计，自动检测问题并给出解决方案
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"📋 {title}")
    print("=" * 60)


def print_success(msg: str):
    """打印成功信息"""
    print(f"  ✅ {msg}")


def print_error(msg: str):
    """打印错误信息"""
    print(f"  ❌ {msg}")


def print_info(msg: str):
    """打印提示信息"""
    print(f"  💡 {msg}")


def print_step(step: int, msg: str):
    """打印步骤"""
    print(f"\n  {step}. {msg}")


def check_python_version():
    """检查 Python 版本"""
    print_section("Python 版本检查")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} - 符合要求")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} - 版本过低")
        print_info("需要 Python 3.10 或更高版本")
        print_info("下载地址: https://www.python.org/downloads/")
        return False


def check_dependencies():
    """检查依赖安装"""
    print_section("依赖包检查")
    required = [
        ("yaml", "PyYAML"),
        ("pydantic", "pydantic"),
        ("fastapi", "fastapi"),
        ("loguru", "loguru"),
        ("openpyxl", "openpyxl"),
    ]
    
    missing = []
    for module, package in required:
        try:
            __import__(module)
            print_success(f"{package} - 已安装")
        except ImportError:
            print_error(f"{package} - 未安装")
            missing.append(package)
    
    if missing:
        print("\n  🔧 修复方法:")
        print("     在终端运行以下命令:")
        print(f"     pip install {' '.join(missing)}")
        return False
    return True


def check_api_key():
    """检查 API 密钥配置"""
    print_section("API 密钥检查")
    
    # 检查环境变量
    env_key = os.getenv("LLM_API_KEY", "")
    if env_key:
        masked = env_key[:8] + "..." if len(env_key) > 8 else "***"
        print_success(f"环境变量 LLM_API_KEY 已配置 ({masked})")
        return True
    
    # 检查配置文件
    config_file = PROJECT_ROOT / "config" / "config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
                if cfg.get('llm', {}).get('api_key'):
                    print_success("配置文件已配置 API 密钥")
                    return True
        except:
            pass
    
    print_error("API 密钥未配置")
    print("\n  🔧 修复方法（任选一种）:")
    print_step(1, "设置环境变量（推荐，临时有效）:")
    print("     set LLM_API_KEY=你的API密钥")
    print_step(2, "编辑配置文件（永久有效）:")
    print(f"     文件路径: {config_file}")
    print("     在 llm 部分添加: api_key: 你的API密钥")
    print("\n  📖 获取 API 密钥:")
    print("     1. 访问 https://platform.moonshot.cn/ (Kimi)")
    print("     2. 注册账号并创建 API 密钥")
    print("     3. 复制密钥并配置到项目")
    return False


def check_directories():
    """检查必要目录"""
    print_section("项目目录检查")
    dirs = ['output', 'logs', 'uploads']
    all_ok = True
    
    for d in dirs:
        dir_path = PROJECT_ROOT / d
        try:
            dir_path.mkdir(exist_ok=True)
            print_success(f"{d}/ - 已就绪")
        except Exception as e:
            print_error(f"{d}/ - 创建失败: {e}")
            all_ok = False
    
    return all_ok


def check_config_file():
    """检查配置文件"""
    print_section("配置文件检查")
    
    config_file = PROJECT_ROOT / "config" / "config.yaml"
    example_file = PROJECT_ROOT / "config" / "config.yaml.example"
    
    if config_file.exists():
        print_success(f"config.yaml - 已存在")
        return True
    
    if example_file.exists():
        print_error("config.yaml - 不存在")
        print("\n  🔧 修复方法:")
        print(f"     复制 {example_file.name} 为 config.yaml")
        print(f"     命令: copy config\\config.yaml.example config\\config.yaml")
        return False
    
    print_error("config.yaml 和 config.yaml.example 都不存在")
    return False


def run_module_check():
    """运行模块加载检查"""
    print_section("核心模块检查")
    
    checks = [
        ("配置系统", "from src.core.config import Config"),
        ("Agent核心", "from src.core.agent import GameTestAgent"),
        ("技能模块", "from src.skills.base import BaseSkill"),
        ("LLM客户端", "from src.adapters.llm.client import LLMClient"),
        ("文档解析", "from src.adapters.document.parser import DocumentParser"),
    ]
    
    all_ok = True
    for name, import_stmt in checks:
        try:
            exec(import_stmt)
            print_success(f"{name} - 正常加载")
        except Exception as e:
            print_error(f"{name} - 加载失败: {e}")
            all_ok = False
    
    return all_ok


def print_final_report(results: dict):
    """打印最终报告"""
    print("\n" + "=" * 60)
    print("📊 诊断总结")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\n  检查项: {passed}/{total} 通过")
    
    if passed == total:
        print("\n  🎉 恭喜！所有检查通过")
        print("  ✨ 项目已就绪，可以正常使用！")
        print("\n  🚀 快速开始:")
        print("     启动Web界面: python web/api.py")
        print("     启动MCP服务: python mcp_server.py")
        print("     运行示例: python examples/basic_usage.py")
    elif passed >= total * 0.7:
        print("\n  ⚠️  项目基本可用，但有一些问题")
        print("  🔧 建议修复上述问题以获得更好体验")
    else:
        print("\n  ❌ 项目存在问题，需要修复")
        print("  📖 请按照上面的提示逐步修复")
        print("\n  💡 一键修复:")
        print("     python scripts/setup_project.py")
    
    print("\n" + "=" * 60)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🔍 TestOwl 一键诊断工具")
    print("=" * 60)
    print("\n  这个工具会检查项目配置并给出修复建议")
    print("  专为没有代码经验的用户设计 😊")
    
    results = {
        "Python版本": check_python_version(),
        "依赖包": check_dependencies(),
        "API密钥": check_api_key(),
        "项目目录": check_directories(),
        "配置文件": check_config_file(),
        "核心模块": run_module_check(),
    }
    
    print_final_report(results)
    
    # 如果全部通过，返回0，否则返回1
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
