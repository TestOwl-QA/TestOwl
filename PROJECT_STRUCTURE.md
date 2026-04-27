# TestOwl 项目结构说明

本文档帮助没有代码基础的用户理解项目组织结构。

## 📁 目录结构总览

```
TestOwl/
├── 📂 config/              # 配置文件目录
│   ├── config.yaml         # 主配置文件（需要手动创建）
│   └── config.yaml.example # 配置文件示例
│
├── 📂 docs/                # 文档目录
│   ├── DEVELOPMENT_GUIDE.md    # 开发指南
│   ├── DEEPSEEK_DEV_GUIDE.md   # DeepSeek开发指南
│   └── ...
│
├── 📂 examples/            # 使用示例
│   ├── basic_usage.py      # 基础使用示例
│   └── db_checker_example.py   # 数据库检查示例
│
├── 📂 knowledge_base/      # 知识库文件
│   └── *.md               # 各种测试知识文档
│
├── 📂 logs/               # 日志文件目录
│   └── *.log             # 自动生成的日志
│
├── 📂 output/             # 输出文件目录
│   └── （生成的测试用例、报告等）
│
├── 📂 scripts/            # 工具脚本
│   ├── diagnose.py        # 🔍 一键诊断工具（推荐先用）
│   ├── check_health.py    # 健康检查
│   ├── setup_project.py   # 项目初始化
│   ├── verify_code.py     # 代码验证
│   ├── windows/           # Windows批处理脚本
│   ├── unix/              # Linux/Mac脚本
│   └── powershell/        # PowerShell脚本
│
├── 📂 src/                # 核心源代码
│   ├── 📂 adapters/       # 适配器（连接外部服务）
│   │   ├── document/      # 文档解析
│   │   ├── llm/          # 大语言模型
│   │   ├── platform/     # 项目管理平台
│   │   └── storage/      # 文件导出
│   │
│   ├── 📂 core/          # 核心模块
│   │   ├── agent.py      # 智能体主类
│   │   ├── config.py     # 配置管理
│   │   └── exceptions.py # 异常定义
│   │
│   ├── 📂 quality/       # 质量保障
│   │   ├── engine.py     # 质量检查引擎
│   │   └── validators/   # 各种验证器
│   │
│   ├── 📂 services/      # 服务层
│   │   └── knowledge_service.py  # 知识库服务
│   │
│   ├── 📂 skills/        # 技能模块
│   │   ├── bug_tracker/      # Bug追踪
│   │   ├── db_checker/       # 数据库检查
│   │   ├── document_analyzer/# 文档分析
│   │   ├── table_checker/    # 配置表检查
│   │   └── test_case_generator/  # 测试用例生成
│   │
│   └── 📂 utils/         # 工具函数
│       └── logger.py     # 日志工具
│
├── 📂 tests/             # 测试文件
│   └── test_*.py        # 各种测试脚本
│
├── 📂 uploads/           # 上传文件目录
│   └── （用户上传的文档）
│
├── 📂 web/               # Web界面
│   ├── api.py           # 后端API
│   ├── chat_handler.py  # 聊天处理
│   ├── index.html       # 前端页面
│   └── assets/          # 静态资源
│
├── 📄 mcp_server.py     # MCP服务入口
├── 📄 README.md         # 项目说明
├── 📄 requirements.txt  # Python依赖
└── 📄 pyproject.toml    # 项目配置
```

## 🚀 快速开始（新手推荐）

### 第一步：诊断环境
```bash
python scripts/diagnose.py
```
这个命令会检查你的环境是否配置正确，并给出修复建议。

### 第二步：启动服务
```bash
# 启动Web界面
python web/api.py

# 或启动MCP服务
python mcp_server.py
```

## 📖 核心文件说明

### 对于使用者

| 文件/目录 | 用途 | 是否需要修改 |
|-----------|------|-------------|
| `config/config.yaml` | 配置文件（API密钥等） | ✅ 需要配置 |
| `scripts/diagnose.py` | 诊断工具 | ❌ 直接使用 |
| `examples/` | 使用示例 | ❌ 参考学习 |
| `knowledge_base/` | 知识库文档 | ❌ 可直接阅读 |
| `output/` | 生成的文件 | ❌ 自动创建 |

### 对于开发者

| 文件/目录 | 用途 | 说明 |
|-----------|------|------|
| `src/core/` | 核心逻辑 | 智能体、配置、异常 |
| `src/skills/` | 技能模块 | 各种测试功能 |
| `src/adapters/` | 适配器 | 连接外部服务 |
| `src/quality/` | 质量保障 | 检查、验证、重试 |

## 🔧 常用操作

### 1. 检查项目健康状态
```bash
python scripts/check_health.py
```

### 2. 初始化项目
```bash
python scripts/setup_project.py
```

### 3. 验证代码结构
```bash
python scripts/verify_code.py
```

## 📝 配置文件说明

### config.yaml 结构
```yaml
llm:
  provider: moonshot      # LLM提供商
  api_key: "你的API密钥"   # API密钥（必填）
  model: "kimi-k2.5"      # 模型名称

storage:
  output_dir: "./output"  # 输出目录

document:
  supported_formats:      # 支持的文档格式
    - docx
    - pdf
    - md
    - txt
```

## 🎯 模块依赖关系

```
web/api.py
    └── src/core/agent.py
        ├── src/skills/          # 各种技能
        ├── src/adapters/llm/    # LLM客户端
        └── src/services/        # 服务层

mcp_server.py
    └── src/core/agent.py
        └── (同上)
```

## 💡 最佳实践

1. **总是先运行诊断**：遇到问题先运行 `python scripts/diagnose.py`
2. **保持配置安全**：不要提交 `config.yaml` 到Git（已配置.gitignore）
3. **定期清理日志**：日志文件会自动轮转，保留30天
4. **使用示例学习**：参考 `examples/` 目录学习如何使用

## ❓ 常见问题

**Q: 我不知道该修改哪个文件？**  
A: 一般只需要修改 `config/config.yaml` 配置API密钥，其他文件不需要修改。

**Q: 如何添加新的测试功能？**  
A: 在 `src/skills/` 目录下创建新的技能模块，参考现有技能的结构。

**Q: 如何调试问题？**  
A: 查看 `logs/` 目录下的日志文件，里面有详细的运行记录。

---

*最后更新：2026-04-27*
