# 给 DeepSeek 的说明 - TestOwl 项目

> 如果你是通过网页版 DeepSeek 查看此项目，请阅读本文档

## 📋 项目概述

这是一个**游戏测试智能助手**项目（TestOwl），使用 Python + FastAPI + MCP 协议开发。

**核心功能**：
- 分析需求文档，提取测试要点
- 生成测试用例（Excel/XMind）
- 检查游戏配置表
- 追踪 Bug

**代码位置**：Git 仓库中（用户会提供仓库地址或代码内容）

---

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| AI 接口 | OpenAI SDK（兼容 DeepSeek/Moonshot） |
| 协议 | MCP (Model Context Protocol) |
| 文档解析 | python-docx, PyPDF2 |
| 数据处理 | pandas, openpyxl |

---

## 📁 项目结构（重点文件）

```
QA助手/
├── src/
│   ├── core/
│   │   ├── agent.py          ← 核心调度（意图识别）
│   │   └── config.py         ← 配置管理
│   │
│   ├── skills/               ← 【主要修改这里】
│   │   ├── base.py           ← 技能基类
│   │   ├── document_analyzer/    ← 需求分析技能
│   │   ├── test_case_generator/  ← 用例生成技能
│   │   ├── table_checker/        ← 表检查技能
│   │   ├── bug_tracker/          ← Bug追踪技能
│   │   └── db_checker/           ← 数据库检查技能
│   │
│   └── adapters/
│       └── llm/
│           └── client.py     ← LLM客户端（模型配置）
│
├── web/
│   └── api.py                ← Web接口（添加新API）
│
├── mcp_server.py             ← MCP服务入口
├── setup_project.py          ← 【首次运行】环境初始化
└── requirements.txt          ← 依赖清单
```

---

## 🚀 快速开始（新设备）

### 第一步：从 Git 拉取代码

```bash
# 克隆仓库（用户会提供具体地址）
git clone <仓库地址>
cd TestOwl  # 或项目目录名
```

### 第二步：初始化环境

```bash
# 在项目根目录运行
python setup_project.py
```

这会：
- 自动检测当前路径
- 创建启动脚本（路径无关）
- 生成环境变量模板

### 第三步：配置 API Key

复制 `.env.example` 为 `.env`，填入：

```env
LLM_API_KEY=your_deepseek_api_key
LLM_PROVIDER=deepseek
```

### 第四步：启动服务

```bash
# Windows 双击
start_web.bat

# 或命令行
python -m uvicorn web.api:app --reload
```

---

## 📝 常见开发任务

### 任务1：添加新技能

**步骤**：

1. **创建技能目录**
```bash
mkdir src/skills/my_skill
touch src/skills/my_skill/__init__.py
touch src/skills/my_skill/skill.py
```

2. **编写技能代码** (`skill.py`)

```python
from typing import Any, Dict, List
from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.adapters.llm.client import LLMClient

class MySkill(BaseSkill):
    """我的新技能"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.llm_client = LLMClient(config)
    
    @property
    def name(self) -> str:
        return "my_skill"
    
    @property
    def description(self) -> str:
        return "技能描述"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "input",
                "type": "string",
                "required": True,
                "description": "输入参数",
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        input_data = context.get_param("input")
        
        # 参数验证
        error = self.validate_params(context)
        if error:
            return SkillResult.fail(error)
        
        try:
            # 调用 LLM
            result = await self.llm_client.complete(f"处理: {input_data}")
            return SkillResult.ok(data={"result": result})
        except Exception as e:
            return SkillResult.fail(f"失败: {str(e)}")
```

3. **注册技能** (`mcp_server.py`)

```python
from src.skills.my_skill import MySkill

# 在 init_agent 方法中添加
self.agent.register_skill("my_skill", MySkill(config))
```

4. **添加意图识别** (`src/core/agent.py`)

```python
def _detect_intent(self, message: str) -> Dict[str, Any]:
    message_lower = message.lower()
    
    # 新技能意图
    if any(kw in message_lower for kw in ["关键词1", "关键词2"]):
        return {
            "skill": "my_skill",
            "params": {"input": message}
        }
    
    # ... 其他意图
```

---

### 任务2：修改现有技能

**示例：修改需求分析的提示词**

文件：`src/skills/document_analyzer/skill.py`

找到 `_analyze_chunk` 方法，修改 prompt：

```python
prompt = f"""你是一个专业的游戏测试专家。请分析以下需求文档片段...

【修改这里的内容】

## 需求文档片段
{content}
"""
```

---

### 任务3：添加 Web API 接口

文件：`web/api.py`

```python
from pydantic import BaseModel

class MyRequest(BaseModel):
    data: str
    session_token: Optional[str] = None

@app.post("/my_endpoint")
async def my_endpoint(req: MyRequest):
    key = get_api_key(req.session_token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    try:
        # 调用技能
        config = get_config_with_key(key)
        from src.core.agent import GameTestAgent
        agent = GameTestAgent(config)
        
        result = await agent.execute("my_skill", {"input": req.data})
        return {"success": True, "data": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

### 任务4：添加新模型支持

文件：`src/adapters/llm/client.py`

在 `PROVIDERS` 字典中添加：

```python
PROVIDERS = {
    # ... 现有配置
    "new_provider": {
        "base_url": "https://api.new.com/v1",
        "model": "default-model",
    },
}
```

然后在 `.env` 中使用：

```env
LLM_PROVIDER=new_provider
LLM_API_KEY=your_key
```

---

## 🐛 调试技巧

### 1. 查看日志

```bash
# 设置日志级别
set LOG_LEVEL=DEBUG  # Windows
export LOG_LEVEL=DEBUG  # Linux/macOS
```

### 2. 测试单个技能

创建 `test_skill.py`：

```python
import asyncio
import sys
sys.path.insert(0, '.')

from src.core.config import Config
from src.skills.my_skill import MySkill
from src.skills.base import SkillContext

async def test():
    config = Config()
    skill = MySkill(config)
    
    context = SkillContext(
        agent=None,
        config=config,
        params={"input": "测试数据"}
    )
    
    result = await skill.execute(context)
    print(f"成功: {result.success}")
    print(f"数据: {result.data}")

if __name__ == "__main__":
    asyncio.run(test())
```

运行：
```bash
python test_skill.py
```

### 3. 健康检查

```bash
python scripts/check_health.py
```

---

## ⚠️ 注意事项

### 路径问题（已解决）

- ✅ 使用 `setup_project.py` 初始化后，所有脚本自动适配当前路径
- ✅ 切换设备后，只需重新运行 `python setup_project.py`
- ✅ 代码中使用相对路径或动态检测路径

### 导入问题

如果提示 `ModuleNotFoundError: No module named 'src'`，确保：

1. 在项目根目录运行脚本
2. 或设置 `PYTHONPATH=.`
3. 或运行了 `setup_project.py`

### API Key 安全

- ❌ 不要将 API Key 提交到 Git
- ✅ 使用 `.env` 文件（已在 .gitignore 中）
- ✅ 或使用环境变量

---

## 📚 参考文档

- `docs/DEVELOPMENT_GUIDE.md` - 完整开发文档
- `docs/DEEPSEEK_DEV_GUIDE.md` - DeepSeek 专用指南
- `README.md` - 项目说明

---

## 💡 给 DeepSeek 的提示

当用户要求你修改代码时：

1. **确认文件路径** - 使用相对路径 `src/xxx/xxx.py`
2. **保持代码风格** - 遵循现有代码的格式和注释风格
3. **添加错误处理** - 使用 try/except 包装可能出错的操作
4. **更新导入** - 确保导入路径正确
5. **提供完整代码** - 不要省略关键部分

---

## 🔗 Git 工作流

### 推荐的工作流程

```bash
# 1. 从 Git 拉取最新代码
git pull origin main

# 2. 运行初始化脚本
python setup_project.py

# 3. 配置环境变量
copy .env.example .env
# 编辑 .env 填入 API Key

# 4. 开发...
# 根据 DeepSeek 生成的代码修改文件

# 5. 测试
python scripts/check_health.py

# 6. 提交代码
git add .
git commit -m "添加新功能: xxx"
git push origin main
```

### 切换设备时的操作

```bash
# 新设备上只需执行
git clone <仓库地址>
cd 项目目录
python setup_project.py
# 配置 .env 文件
```

---

**项目路径无关，任何设备都可以运行！** 🎉