# GameTestAgent - 游戏测试智能助手

一个基于MCP协议的通用游戏测试Agent，支持需求分析、测试用例生成、Bug分析和表检查等功能。

## 🌟 核心特性

- **多格式文档支持**：Word、PDF、Markdown、文本、HTML
- **智能测试用例生成**：基于需求文档自动提取测试要点并生成用例
- **Bug分析与记录**：支持多平台Bug反馈接入（Jira、禅道、Redmine、Tapd）
- **灵活表检查**：支持游戏配置表、数据表的规则检查
- **多格式输出**：Excel、Xmind测试用例导出
- **云模型支持**：默认支持Kimi K2.5，可配置其他云服务商（OpenAI、DeepSeek等）
- **零扣子依赖**：完全独立，可部署到任何支持MCP的平台

## 📁 项目结构

```
game_test_agent/
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
│   └── config.yaml.example # 配置模板
├── examples/              # 使用示例
│   └── basic_usage.py
├── requirements.txt       # 依赖
├── main.py               # 本地入口文件
├── mcp_server.py         # MCP服务入口
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

#### 方式一：本地命令行运行

```bash
python main.py
```

#### 方式二：作为MCP服务运行

在支持MCP的平台（如Claude Desktop、Cursor、Windsurf）中配置：

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

## ⚠️ 注意事项

1. **API密钥安全**：不要将 `config.yaml` 提交到代码仓库
2. **平台配置**：使用Bug提交功能前，需要先配置对应平台
3. **XMind导出**：需要安装 `xmind` 库，否则会回退到JSON格式

## 📄 License

MIT License
