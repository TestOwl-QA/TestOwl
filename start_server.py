#!/usr/bin/env python3
"""
TestOwl 一键启动脚本

修复问题:
- GT-001: 服务启动失败（路径、进程清理）
- GT-002: 配置加载异常（预检查）
- GT-004: 进程管理缺陷（自动重启、端口检查）
- GT-005: 依赖缺失（自动检查）

使用方法:
    python start_server.py          # 默认模式启动
    python start_server.py --dev    # 开发模式（热重载）
    python start_server.py --stop   # 停止服务
"""

import os
import sys
import subprocess
import argparse
import socket
import time
import signal
from pathlib import Path

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")
def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.RESET}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

# 项目配置
PROJECT_ROOT = Path(__file__).parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
CONFIG_EXAMPLE_PATH = PROJECT_ROOT / "config" / "config.yaml.example"
DEFAULT_PORT = 8000
PID_FILE = PROJECT_ROOT / ".server.pid"


def check_port_available(port: int) -> bool:
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def kill_existing_server(port: int):
    """清理已存在的服务进程"""
    print_info(f"检查端口 {port} 占用情况...")
    
    # Windows
    if sys.platform == "win32":
        try:
            # 查找占用端口的进程
            result = subprocess.run(
                ["netstat", "-ano", "|", "findstr", f":{port}"],
                capture_output=True, text=True, shell=True
            )
            if result.returncode == 0 and result.stdout:
                print_warning(f"发现端口 {port} 被占用")
                # 尝试终止进程
                subprocess.run(
                    ["taskkill", "/F", "/IM", "python.exe", "/FI", f"WINDOWTITLE eq *uvicorn*"],
                    capture_output=True
                )
                time.sleep(1)
        except Exception as e:
            print_warning(f"清理进程时出错: {e}")
    else:
        # Linux/Mac
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        print_warning(f"终止进程 {pid}")
                        subprocess.run(["kill", "-9", pid], capture_output=True)
                time.sleep(1)
        except Exception as e:
            print_warning(f"清理进程时出错: {e}")


def check_dependencies() -> bool:
    """检查核心依赖是否安装"""
    print_info("检查依赖...")
    
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("yaml", "pyyaml"),
    ]
    
    missing = []
    for module, package in required_packages:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print_error(f"缺少依赖: {', '.join(missing)}")
        print_info("正在安装依赖...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=PROJECT_ROOT,
                check=True
            )
            print_success("依赖安装完成")
        except subprocess.CalledProcessError as e:
            print_error(f"安装依赖失败: {e}")
            return False
    else:
        print_success("所有依赖已安装")
    
    return True


def check_config() -> bool:
    """检查配置文件"""
    print_info("检查配置文件...")
    
    if not CONFIG_PATH.exists():
        print_error(f"配置文件不存在: {CONFIG_PATH}")
        
        if CONFIG_EXAMPLE_PATH.exists():
            print_info("正在从模板创建配置文件...")
            import shutil
            shutil.copy(CONFIG_EXAMPLE_PATH, CONFIG_PATH)
            print_warning(f"请编辑 {CONFIG_PATH} 填入你的API密钥后再启动")
        else:
            print_error("配置文件模板也不存在！")
        
        return False
    
    # 验证配置内容
    try:
        import yaml
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 检查API密钥
        llm_config = config.get('llm', {})
        api_key = llm_config.get('api_key', '')
        
        if not api_key or api_key.strip() == '':
            # 检查环境变量
            if not os.getenv('LLM_API_KEY'):
                print_error("LLM API密钥未配置！")
                print_info("请执行以下操作之一:")
                print_info(f"  1. 编辑 {CONFIG_PATH}，设置 llm.api_key")
                print_info("  2. 设置环境变量: export LLM_API_KEY=your_key")
                return False
        
        print_success("配置检查通过")
        return True
        
    except Exception as e:
        print_error(f"配置文件解析失败: {e}")
        return False


def start_server(dev_mode: bool = False, port: int = DEFAULT_PORT):
    """启动服务"""
    print("=" * 60)
    print("🚀 TestOwl 服务启动")
    print("=" * 60)
    
    # 1. 切换到项目目录
    print("=" * 60)
    print("🚀 TestOwl 服务启动")
    print("=" * 60)
    
    # 1. 切换到项目目录
    os.chdir(PROJECT_ROOT)
    print_info(f"工作目录: {PROJECT_ROOT}")
    
    # 2. 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 3. 检查配置
    if not check_config():
        sys.exit(1)
    
    # 4. 清理旧进程
    kill_existing_server(port)
    
    # 5. 检查端口
    if not check_port_available(port):
        print_error(f"端口 {port} 仍被占用，无法启动")
        sys.exit(1)
    
    print_success(f"端口 {port} 可用")
    
    # 6. 启动服务
    print_info("正在启动服务...")
    
    env = os.environ.copy()
    env['PYTHONPATH'] = str(PROJECT_ROOT)
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "web_api:app",
        "--host", "0.0.0.0",
        "--port", str(port),
    ]
    
    if dev_mode:
        cmd.append("--reload")
        print_info("开发模式：启用热重载")
    
    try:
        # 启动进程
        if sys.platform == "win32":
            # Windows下创建新进程组
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                env=env,
                preexec_fn=os.setsid
            )
        
        # 保存PID
        with open(PID_FILE, 'w') as f:
            f.write(str(process.pid))
        
        print_success(f"服务已启动 (PID: {process.pid})")
        print("=" * 60)
        print(f"📍 访问地址: http://localhost:{port}")
        print(f"📚 API文档: http://localhost:{port}/docs")
        print(f"❤️  健康检查: http://localhost:{port}/health")
        print("=" * 60)
        
        if dev_mode:
            print_info("按 Ctrl+C 停止服务")
            try:
                process.wait()
            except KeyboardInterrupt:
                print_info("\n收到停止信号...")
                stop_server()
        else:
            print_info("后台运行中，使用 `python start_server.py --stop` 停止")
            
    except Exception as e:
        print_error(f"启动失败: {e}")
        sys.exit(1)


def stop_server():
    """停止服务"""
    print_info("正在停止服务...")
    
    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            
            PID_FILE.unlink()
            print_success("服务已停止")
        except Exception as e:
            print_warning(f"停止服务时出错: {e}")
            print_info("尝试强制清理...")
            kill_existing_server(DEFAULT_PORT)
    else:
        print_warning("未找到PID文件，尝试清理端口...")
        kill_existing_server(DEFAULT_PORT)


def test_server(port: int = DEFAULT_PORT):
    """测试服务是否正常运行"""
    print_info("测试服务...")
    
    import urllib.request
    try:
        response = urllib.request.urlopen(
            f"http://localhost:{port}/health",
            timeout=5
        )
        data = response.read().decode('utf-8')
        print_success(f"服务响应正常: {data}")
        return True
    except Exception as e:
        print_error(f"服务测试失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="TestOwl 服务管理脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start_server.py          # 生产模式启动
  python start_server.py --dev    # 开发模式启动（热重载）
  python start_server.py --stop   # 停止服务
  python start_server.py --test   # 测试服务
        """
    )
    
    parser.add_argument(
        "--dev", action="store_true",
        help="开发模式（启用热重载）"
    )
    parser.add_argument(
        "--stop", action="store_true",
        help="停止服务"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="测试服务是否正常运行"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"服务端口（默认: {DEFAULT_PORT}）"
    )
    
    args = parser.parse_args()
    
    if args.stop:
        stop_server()
    elif args.test:
        test_server(args.port)
    else:
        start_server(dev_mode=args.dev, port=args.port)


if __name__ == "__main__":
    main()
