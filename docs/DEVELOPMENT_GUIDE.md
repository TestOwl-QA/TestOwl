# TestOwl 开发指南

## 📋 项目概述

TestOwl 是一个基于 MCP (Model Context Protocol) 的游戏测试智能助手，采用模块化架构设计，便于扩展和维护。

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Web UI     │  │  MCP Client │  │  Python API         │  │
│  │  (聊天界面)  │  │  (外部工具) │  │  (代码调用)         │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      API 网关层                               │
│              FastAPI + MCP Server (mcp_server.py)            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      核心调度层                               │
│              GameTestAgent (src/core/agent.py)               │
│     • 技能注册与管理    • 意图识别    • 结果格式化            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                       技能层 (Skills)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Document     │ │ TestCase     │ │ TableChecker         │ │
│  │ Analyzer     │ │ Generator    │ │ (配置表检查)          │ │
│  │ (需求分析)    │ │ (用例生成)    │ │                      │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │ BugTracker   │ │ DBChecker    │                          │
│  │ (Bug追踪)    │ │ (数据库检查)  │                          │
│  └──────────────┘ └──────────────┘                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      适配器层 (Adapters)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │ LLM Client │  │ Document   │  │ Storage    │              │
│  │ (大模型)   │  │ Parser     │  │ (导出)     │              │
│  └────────────┘  └────────────┘  └────────────┘              │
│  ┌────────────┐  ┌────────────┐                              │
│  │ Platform   │  │ Database   │                              │
│  │ (项目管理) │  │ Connector  │                              │
│  └────────────┘  └────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境准备

```bash
# 1. 克隆项目
git clone https://github.com/TestOwl-QA/TestOwl.git
cd TestOwl

# 2. 创建虚拟环境
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 配置API Key
set LLM_API_KEY=your_api_key_here  # Windows
export LLM_API_KEY=your_api_key_here  # macOS/Linux
```

### 启动服务

```bash
# 方式1: 启动MCP服务 (STDIO模式，用于Claude Desktop等)
python mcp_server.py

# 方式2: 启动MCP服务 (SSE模式，支持远程连接)
python mcp_server.py --sse --host 0.0.0.0 --port 8000

# 方式3: 启动Web服务
python -m uvicorn web.api:app --host 0.0.0.0 --port 8081

# 方式4: 同时启动多个服务
python scripts/start_all.py
```

## 📝 开发新技能

### 1. 创建技能文件

在 `src/skills/` 目录下创建新的技能模块：

```python
# src/skills/my_skill/__init__.py
from src.skills.my_skill.skill import MySkill
from src.skills.my_skill.models import MyResult

__all__ = ["MySkill", "MyResult"]
```

```python
# src/skills/my_skill/models.py
from dataclasses import dataclass
from typing import List

@dataclass
class MyResult:
    """技能结果模型"""
    title: str
    items: List[str]
    score: float = 0.0
```

```python
# src/skills/my_skill/skill.py
from typing import Any, Dict, List
from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.adapters.llm.client import LLMClient
from src.skills.my_skill.models import MyResult

class MySkill(BaseSkill):
    """我的自定义技能"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.llm_client = LLMClient(config)
    
    @property
    def name(self) -> str:
        return "my_skill"
    
    @property
    def description(self) -> str:
        return "描述这个技能的作用"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "input_data",
                "type": "string",
                "required": True,
                "description": "输入数据",
            },
            {
                "name": "option",
                "type": "string",
                "required": False,
                "default": "default_value",
                "description": "可选参数",
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """执行技能"""
        # 1. 获取参数
        input_data = context.get_param("input_data")
        option = context.get_param("option", "default_value")
        
        # 2. 验证参数
        error = self.validate_params(context)
        if error:
            return SkillResult.fail(error)
        
        # 3. 执行业务逻辑
        try:
            result = await self._process(input_data, option)
            return SkillResult.ok(data=result)
        except Exception as e:
            return SkillResult.fail(f"处理失败: {str(e)}")
    
    async def _process(self, data: str, option: str) -> MyResult:
        """实际处理逻辑"""
        # 调用LLM或其他服务
        response = await self.llm_client.complete(f"处理: {data}")
        
        return MyResult(
            title="处理结果",
            items=response.split("\n"),
            score=0.95
        )
```

### 2. 注册技能

在 `mcp_server.py` 中注册新技能：

```python
from src.skills.my_skill import MySkill

# 在 init_agent 方法中添加
self.agent.register_skill("my_skill", MySkill(config))
```

### 3. 添加意图识别

在 `src/core/agent.py` 的 `_detect_intent` 方法中添加：

```python
def _detect_intent(self, message: str) -> Dict[str, Any]:
    message_lower = message.lower()
    
    # 我的技能意图
    if any(kw in message_lower for kw in ["关键词1", "关键词2"]):
        return {
            "skill": "my_skill",
            "params": {"input_data": message}
        }
    
    # ... 其他意图
```

## 🔧 配置系统

### 配置文件结构

```yaml
# config/config.yaml

# 大模型配置
llm:
  provider: moonshot  # moonshot, openai, deepseek, siliconflow, openrouter
  api_key: ""  # 或从环境变量 LLM_API_KEY 读取
  model: ""  # 留空使用默认模型
  temperature: 0.7
  max_tokens: 4096

# 文档解析配置
document:
  supported_formats: ["docx", "pdf", "md", "txt", "html"]
  max_file_size: 52428800

# 存储配置
storage:
  type: local
  output_dir: "./output"

# 项目管理平台配置
platforms:
  - name: jira
    enabled: false
    base_url: ""
    username: ""
    api_token: ""
```

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_KEY` | 大模型API密钥 | `sk-xxx...` |
| `LLM_BASE_URL` | 自定义API地址 | `https://api.xxx.com/v1` |
| `LLM_MODEL` | 模型名称 | `gpt-4` |
| `LOG_LEVEL` | 日志级别 | `DEBUG`, `INFO`, `WARNING` |

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_document_analyzer.py

# 运行并生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 编写测试

```python
# tests/test_my_skill.py
import pytest
from src.skills.my_skill import MySkill
from src.core.config import Config

@pytest.fixture
def skill():
    config = Config()
    return MySkill(config)

@pytest.mark.asyncio
async def test_my_skill_execute(skill):
    from src.skills.base import SkillContext
    
    context = SkillContext(
        agent=None,
        config=skill.config,
        params={"input_data": "测试数据"}
    )
    
    result = await skill.execute(context)
    
    assert result.success is True
    assert result.data is not None
```

## 📦 项目结构规范

```
QA助手/
├── src/                          # 源代码
│   ├── core/                     # 核心模块
│   │   ├── agent.py              # Agent主类
│   │   ├── config.py             # 配置管理
│   │   ├── exceptions.py         # 自定义异常
│   │   └── token_optimizer.py    # Token优化
│   │
│   ├── skills/                   # 技能模块
│   │   ├── base.py               # 技能基类
│   │   ├── document_analyzer/    # 需求分析
│   │   ├── test_case_generator/  # 用例生成
│   │   ├── table_checker/        # 表检查
│   │   ├── bug_tracker/          # Bug追踪
│   │   └── db_checker/           # 数据库检查
│   │
│   ├── adapters/                 # 适配器层
│   │   ├── llm/                  # 大模型客户端
│   │   ├── document/             # 文档解析
│   │   ├── storage/              # 存储导出
│   │   └── platform/             # 项目管理平台
│   │
│   ├── services/                 # 服务层
│   │   └── knowledge_service.py  # 知识库服务
│   │
│   └── utils/                    # 工具函数
│       └── logger.py             # 日志工具
│
├── web/                          # Web界面
│   ├── api.py                    # FastAPI后端
│   ├── chat_handler.py           # 聊天处理
│   └── index.html                # 前端页面
│
├── config/                       # 配置文件
│   ├── config.yaml               # 主配置
│   └── config.yaml.example       # 配置示例
│
├── tests/                        # 测试代码
├── docs/                         # 文档
├── examples/                     # 使用示例
├── knowledge_base/               # 知识库资料
├── uploads/                      # 上传文件目录
├── output/                       # 输出目录
├── logs/                         # 日志目录
│
├── mcp_server.py                 # MCP服务入口
├── pyproject.toml                # 项目配置
├── requirements.txt              # 依赖清单
└── README.md                     # 项目说明
```

## 🔌 支持的模型提供商

| 提供商 | 配置名称 | 默认模型 | 备注 |
|--------|----------|----------|------|
| 月之暗面 | `moonshot` | `kimi-k2.5` | 国内推荐 |
| OpenAI | `openai` | `gpt-4` | 需海外API |
| DeepSeek | `deepseek` | `deepseek-chat` | 性价比高 |
| SiliconFlow | `siliconflow` | `DeepSeek-V2.5` | 国内API聚合 |
| OpenRouter | `openrouter` | `claude-3.5-sonnet` | 多模型路由 |

## 🐛 调试技巧

### 启用调试日志

```python
# 在代码开头添加
import logging
logging.basicConfig(level=logging.DEBUG)

# 或在启动时设置环境变量
set LOG_LEVEL=DEBUG  # Windows
export LOG_LEVEL=DEBUG  # macOS/Linux
```

### 使用开发模式

```bash
# Web服务热重载
python -m uvicorn web.api:app --reload --port 8081

# MCP服务调试模式
python mcp_server.py --sse --log-level debug
```

## 📚 常见问题

### Q: 如何添加新的模型支持？

A: 在 `src/adapters/llm/client.py` 的 `PROVIDERS` 字典中添加配置：

```python
PROVIDERS = {
    # ... 现有配置
    "new_provider": {
        "base_url": "https://api.new.com/v1",
        "model": "default-model",
    },
}
```

### Q: 如何扩展新的导出格式？

A: 在 `src/adapters/storage/` 中创建新的导出器，继承 `StorageAdapter` 基类。

### Q: 如何处理大文档？

A: 使用 `TokenOptimizer` 自动分块处理，参考 `src/skills/document_analyzer/skill.py` 的实现。

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
