#!/usr/bin/env python3
"""
TestOwl 项目环境初始化脚本
在任何设备上首次运行此脚本，自动配置项目环境
"""

import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录（脚本所在目录）"""
    return Path(__file__).parent.resolve()


def create_project_info():
    """创建项目信息文件，供其他脚本读取"""
    project_root = get_project_root()
    info_file = project_root / ".project_info"
    
    with open(info_file, "w", encoding="utf-8") as f:
        f.write(f"PROJECT_ROOT={project_root}\n")
        f.write(f"PYTHON_PATH={sys.executable}\n")
    
    print(f"✅ 项目信息已保存: {info_file}")
    return info_file


def setup_python_path():
    """设置 Python 路径，确保 src 模块可导入"""
    project_root = get_project_root()
    
    # 创建 .pth 文件（可选，用于系统级安装）
    # 或者创建启动脚本
    
    # 创建统一的启动脚本
    create_launcher_scripts(project_root)
    
    print("✅ 启动脚本已创建")


def create_launcher_scripts(project_root: Path):
    """创建跨平台启动脚本"""
    
    # Windows 批处理脚本
    win_launcher = project_root / "start_web.bat"
    with open(win_launcher, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
chcp 65001 >nul
cd /d "{project_root}"
set PYTHONPATH={project_root}
python -m uvicorn web.api:app --host 0.0.0.0 --port 8081 --reload
pause
""")
    
    # Windows MCP 服务启动脚本
    win_mcp = project_root / "start_mcp.bat"
    with open(win_mcp, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
chcp 65001 >nul
cd /d "{project_root}"
set PYTHONPATH={project_root}
python mcp_server.py --sse
pause
""")
    
    # PowerShell 脚本（更现代）
    ps_launcher = project_root / "start_web.ps1"
    with open(ps_launcher, "w", encoding="utf-8") as f:
        f.write(f"""# TestOwl Web 服务启动脚本
$ProjectRoot = "{project_root}"
Set-Location $ProjectRoot
$env:PYTHONPATH = $ProjectRoot

Write-Host "🚀 启动 TestOwl Web 服务..." -ForegroundColor Green
Write-Host "📂 项目路径: $ProjectRoot" -ForegroundColor Cyan

python -m uvicorn web.api:app --host 0.0.0.0 --port 8081 --reload
""")
    
    # Bash 脚本（Linux/macOS）
    bash_launcher = project_root / "start_web.sh"
    with open(bash_launcher, "w", encoding="utf-8") as f:
        f.write(f"""#!/bin/bash
# TestOwl Web 服务启动脚本
PROJECT_ROOT="{project_root}"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

echo "🚀 启动 TestOwl Web 服务..."
echo "📂 项目路径: $PROJECT_ROOT"

python -m uvicorn web.api:app --host 0.0.0.0 --port 8081 --reload
""")
    
    # 健康检查脚本
    health_check = project_root / "check_health.bat"
    with open(health_check, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
chcp 65001 >nul
cd /d "{project_root}"
set PYTHONPATH={project_root}
python scripts/check_health.py
pause
""")
    
    print(f"   - {win_launcher.name}")
    print(f"   - {win_mcp.name}")
    print(f"   - {ps_launcher.name}")
    print(f"   - {bash_launcher.name}")
    print(f"   - {health_check.name}")


def create_env_template():
    """创建环境变量模板文件"""
    project_root = get_project_root()
    env_file = project_root / ".env.example"
    
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("""# TestOwl 环境变量配置
# 复制此文件为 .env 并填入你的配置

# DeepSeek API 配置
LLM_API_KEY=your_deepseek_api_key_here
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

# 可选：其他模型
# LLM_PROVIDER=moonshot
# LLM_API_KEY=your_moonshot_api_key

# 日志级别
LOG_LEVEL=INFO

# Web 服务配置
WEB_HOST=0.0.0.0
WEB_PORT=8081
""")
    
    print(f"✅ 环境变量模板已创建: {env_file}")


def update_config_yaml():
    """更新配置文件中的路径"""
    project_root = get_project_root()
    config_file = project_root / "config" / "config.yaml"
    
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 确保输出目录是相对路径
        if "output_dir:" in content:
            content = content.replace(
                'output_dir: "./output"',
                f'output_dir: "{project_root}/output"'
            )
        
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"✅ 配置文件已更新: {config_file}")


def print_usage():
    """打印使用说明"""
    project_root = get_project_root()
    
    print("\n" + "=" * 60)
    print("🎉 TestOwl 项目初始化完成！")
    print("=" * 60)
    print(f"\n📂 项目路径: {project_root}")
    print("\n🚀 快速开始:")
    print("   1. 配置 API Key:")
    print("      - 复制 .env.example 为 .env")
    print("      - 填入你的 DeepSeek API Key")
    print()
    print("   2. 启动服务（任选一种）:")
    print("      - 双击 start_web.bat     (Windows CMD)")
    print("      - 双击 start_web.ps1     (Windows PowerShell)")
    print("      - ./start_web.sh         (Linux/macOS)")
    print()
    print("   3. 运行健康检查:")
    print("      - 双击 check_health.bat")
    print()
    print("💡 提示:")
    print("   - 所有脚本自动检测当前路径，无需修改")
    print("   - 切换设备后，只需重新运行 setup_project.py")
    print("=" * 60)


def main():
    print("🔧 TestOwl 项目环境初始化\n")
    
    create_project_info()
    setup_python_path()
    create_env_template()
    update_config_yaml()
    
    print_usage()


if __name__ == "__main__":
    main()
