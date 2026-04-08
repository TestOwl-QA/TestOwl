# TestOwl - 游戏测试智能助手

一个基于MCP协议的通用游戏测试Agent，支持需求分析、测试用例生成、Bug分析和表检查等功能。

## 🌟 核心特性

- **多格式文档支持**：Word、PDF、Markdown、文本、HTML
- **智能测试用例生成**：基于需求文档自动提取测试要点并生成用例
- **Bug分析与记录**：支持多平台Bug反馈接入（Jira、禅道、Redmine、Tapd）
- **灵活表检查**：支持游戏配置表、数据表的规则检查
- **多格式输出**：Excel、Xmind测试用例导出
- **云模型支持**：默认支持Kimi K2.5，可配置其他云服务商（OpenAI、DeepSeek等）
- **Web API服务**：提供HTTP REST API接口，支持远程调用
- **零扣子依赖**：完全独立，可部署到任何支持MCP的平台

## 📁 项目结构

```
TestOwl/
├── src/
│   ├── core/              # 核心框架
│   │   ├── __init__.py
│   │   ├── agent.py       # Agent主类
│   │   ├── config.py      # 配置管理
│   │   └── exceptions.py  # 自定义异常
│   ├── skills/            # 技能模块
│   │   ├── __init__.py
│   │   ├── base.py        # 技能基类
│   │   ├── document_analyzer/  # 需求文档分析
│   │   ├── test_case_generator/ # 测试用例生成
│   │   ├── bug_tracker/   # Bug追踪
│   │   └── table_checker/ # 表检查
│   ├── adapters/          # 适配器层
│   │   ├── __init__.py
│   │   ├── llm/           # 大模型适配器
│   │   ├── document/      # 文档解析适配器
│   │   ├── storage/       # 存储适配器
│   │   └── platform/      # 项目管理平台适配器
│   └── utils/             # 工具函数
│       ├── __init__.py
│       └── logger.py      # 日志工具
├── config/                # 配置文件
│   ├── config.yaml.example # 配置模板
│   └── config.yaml        # 实际配置文件（需创建）
├── examples/              # 使用示例
│   └── basic_usage.py
├── requirements.txt       # 依赖
├── main.py               # 命令行入口（本地测试用）
├── web_api.py            # 🆕 TestOwl Web API服务入口（推荐）
├── start_server.py       # 🆕 TestOwl 一键启动脚本（推荐）
├── mcp_server.py         # MCP 服务入口（支持 STDIO/SSE 双模式）
└── README.md             # 说明文档
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API密钥

```bash
# 复制配置模板
cp config/config.yaml.example config/config.yaml

# 编辑 config.yaml 填入你的API密钥
```

**必填项**：
```yaml
llm:
  provider: moonshot        # 使用Kimi
  api_key: "your-api-key"   # 填入你的Kimi API密钥
```

**可选配置**：
- 项目管理平台（Jira/禅道/Tapd/Redmine）
- XMind导出支持

### 3. 运行方式

#### ✅ 方式一：Web API服务（推荐）

**使用 TestOwl 一键启动脚本（最简单）：**

```bash
# 生产模式启动
python start_server.py

# 开发模式启动（自动热重载）
python start_server.py --dev

# 停止服务
python start_server.py --stop

# 测试服务是否正常
python start_server.py --test
```

**手动启动：**

```bash
# 必须在项目根目录执行
uvicorn web_api:app --host 0.0.0.0 --port 8000

# 开发模式（热重载）
uvicorn web_api:app --host 0.0.0.0 --port 8000 --reload
```

**访问服务：**
- 服务状态：`http://localhost:8000/`
- API文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

#### 方式二：本地命令行运行

```bash
python main.py
```

#### 方式三：作为MCP服务运行

**STDIO 模式**（用于 Claude Desktop 等本地客户端）：

```json
{
  "mcpServers": {
    "game-test-agent": {
      "command": "python",
      "args": ["/path/to/game_test_agent/mcp_server.py"]
    }
  }
}
```

**SSE 模式**（用于远程连接，支持文件上传和 API Key 验证）：

```bash
# 启动 SSE 服务器
python mcp_server.py --sse
python mcp_server.py --sse --host 0.0.0.0 --port 8000
```

## 📖 API接口说明

### Web API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务状态 |
| `/health` | GET | 健康检查 |
| `/skills` | GET | 列出所有技能 |
| `/analyze` | POST | 分析需求文档 |
| `/generate` | POST | 生成测试用例 |
| `/bug/track` | POST | 记录和追踪Bug |
| `/table/check` | POST | 检查表格数据 |

### 示例请求

```bash
# 分析文档
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"file_path": "需求文档.docx"}'

# 生成测试用例
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"document_path": "需求文档.docx", "output_format": "excel"}'
```

## 📖 功能说明

### 1. 需求文档分析

```python
# 分析需求文档，提取测试点
result = await agent.execute_skill(
    "document_analyzer",
    {
        "content": "需求文档内容或文件路径",
        "document_type": "docx"  # 支持 docx/pdf/md/txt
    }
)
```

### 2. 测试用例生成

```python
# 基于测试点生成测试用例
result = await agent.execute_skill(
    "test_case_generator",
    {
        "test_points": [...],       # 测试点列表
        "output_format": "excel",   # 支持 excel/xmind/json
        "output_path": "test_cases.xlsx"
    }
)
```

### 3. Bug分析与提交

```python
# 分析Bug并提交到平台
result = await agent.execute_skill(
    "bug_tracker",
    {
        "title": "登录失败",
        "description": "输入正确密码后无法登录",
        "reproduction_steps": ["打开登录界面", "输入账号密码", "点击登录"],
        "platform": "jira",         # 可选：jira/zentao/tapd/redmine
        "analyze_only": False       # False表示提交到平台
    }
)
```

### 4. 表检查

```python
# 检查配置表数据
result = await agent.execute_skill(
    "table_checker",
    {
        "data": [...],              # 要检查的数据
        "rules": [                  # 检查规则
            {"type": "not_null", "column": "id"},
            {"type": "unique", "column": "name"},
            {"type": "range", "column": "level", "min": 1, "max": 100}
        ]
    }
)
```

## 🔧 支持的项目管理平台

| 平台 | 状态 | 说明 |
|------|------|------|
| Jira | ✅ 已实现 | 支持Bug提交、查询、更新 |
| 禅道 | ✅ 已实现 | 支持Bug提交、查询、更新 |
| Tapd | ✅ 已实现 | 支持Bug提交、查询、更新 |
| Redmine | ✅ 已实现 | 支持Bug提交、查询、更新 |

## 🔧 支持的大模型

| 模型 | 提供商 | 配置方式 |
|------|--------|---------|
| Kimi K2.5 | 月之暗面 | `provider: moonshot` |
| GPT-4 | OpenAI | `provider: openai` |
| DeepSeek | 深度求索 | `provider: deepseek` |
| 其他 | 自定义 | 配置 `base_url` 和 `model` |

## 📋 配置说明

### 完整配置示例

```yaml
# 大模型配置
llm:
  provider: moonshot
  api_key: "your-api-key"
  model: "kimi-k2.5"

# 项目管理平台配置
platforms:
  - name: jira
    enabled: true
    base_url: "https://your-domain.atlassian.net"
    username: "your-email@example.com"
    api_token: "your-api-token"
    project_key: "PROJ"

# 表检查配置
table_check:
  enabled_rules:
    - unique_check
    - null_check
    - range_check
```

## 🐛 常见问题排查

### 问题1：服务启动失败

**现象**：执行启动命令后无响应或立即退出

**解决方案**：
```bash
# 使用 TestOwl 一键启动脚本，自动处理路径和依赖
python start_server.py
```

### 问题2：配置加载异常

**现象**：报错 `config.yaml not found` 或 `API key validation failed`

**解决方案**：
```bash
# 1. 创建配置文件
cp config/config.yaml.example config/config.yaml

# 2. 编辑 config.yaml，填入API密钥
# 3. 或使用环境变量
export LLM_API_KEY=your_api_key
```

### 问题3：路由404错误

**现象**：访问 `http://localhost:8000/` 返回 `{"detail":"Not Found"}`

**原因**：启动了错误的入口文件

**解决方案**：
```bash
# ✅ 正确：启动Web API服务
python start_server.py
# 或
uvicorn web_api:app --host 0.0.0.0 --port 8000

# ❌ 错误：不要这样启动
# uvicorn mcp_server:app  # MCP服务不是Web服务
# python mcp_server.py     # 这是MCP服务，不是HTTP服务
```

**入口文件区别**：

| 入口文件 | 用途 | 启动方式 | 协议 |
|----------|------|----------|------|
| `web_api.py` | **Web API服务** | `python start_server.py` | HTTP |
| `mcp_server.py` | MCP 服务 | `python mcp_server.py` / `python mcp_server.py --sse` | STDIO / SSE |
| `main.py` | 命令行工具 | `python main.py` | - |

### 问题4：依赖缺失

**现象**：`ModuleNotFoundError: No module named 'fastapi'`

**解决方案**：
```bash
pip install -r requirements.txt
```

## ⚠️ 注意事项

1. **API密钥安全**：不要将 `config.yaml` 提交到代码仓库，已添加到 `.gitignore`
2. **平台配置**：使用Bug提交功能前，需要先配置对应平台
3. **XMind导出**：需要安装 `xmind` 库，否则会回退到JSON格式
4. **端口占用**：如果8000端口被占用，可使用 `--port 8080` 指定其他端口

## 📄 License

MIT License