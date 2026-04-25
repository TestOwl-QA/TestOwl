# DeepSeek 开发指南 - TestOwl 项目

> 本指南专为使用 DeepSeek 进行 TestOwl 项目后续开发而编写

## 🎯 快速开始（5分钟上手）

### 1. 环境准备

```bash
# 进入项目目录
cd "d:\QA助手"

# 创建虚拟环境（推荐）
python -m venv venv

# Windows 激活
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 或使用 pyproject.toml 安装（推荐）
pip install -e ".[dev]"
```

### 2. 配置 DeepSeek API

**方式一：环境变量（推荐）**
```bash
# Windows
set LLM_API_KEY=your_deepseek_api_key
set LLM_PROVIDER=deepseek

# Linux/macOS
export LLM_API_KEY=your_deepseek_api_key
export LLM_PROVIDER=deepseek
```

**方式二：配置文件**
编辑 `config/config.yaml`：
```yaml
llm:
  provider: deepseek
  api_key: "your_deepseek_api_key"
  model: "deepseek-chat"  # 或 deepseek-coder
  temperature: 0.7
  max_tokens: 4096
```

### 3. 验证环境

```bash
# 运行健康检查
python scripts/check_health.py

# 预期输出：
# ✅ 配置系统            正常加载
# ✅ Agent核心         正常加载
# ✅ 技能基类            正常加载
# ...
# 🎉 代码健康度: 优秀 (100%)
```

---

## 🏗️ 项目架构速览

```
┌─────────────────────────────────────────────────────────────┐
│  你主要修改的文件                                              │
├─────────────────────────────────────────────────────────────┤
│  src/skills/              ← 添加新技能（核心）                 │
│  src/adapters/llm/        ← 添加新模型支持                     │
│  src/core/agent.py        ← 修改意图识别                       │
│  web/api.py               ← 添加新接口                         │
│  config/config.yaml       ← 修改配置                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 常见开发任务

### 任务1：添加新技能

**场景**：添加一个"性能测试分析"技能

**步骤**：

1. **创建技能目录和文件**
```bash
mkdir src/skills/performance_analyzer
touch src/skills/performance_analyzer/__init__.py
touch src/skills/performance_analyzer/models.py
touch src/skills/performance_analyzer/skill.py
```

2. **编写模型** (`models.py`)
```python
from dataclasses import dataclass
from typing import List

@dataclass
class PerformanceMetric:
    name: str
    value: float
    threshold: float
    status: str  # "pass", "warning", "fail"

@dataclass
class PerformanceReport:
    total_score: float
    metrics: List[PerformanceMetric]
    suggestions: List[str]
```

3. **编写技能** (`skill.py`)
```python
from typing import Any, Dict, List
from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.adapters.llm.client import LLMClient
from src.skills.performance_analyzer.models import PerformanceMetric, PerformanceReport

class PerformanceAnalyzerSkill(BaseSkill):
    """性能测试分析技能"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.llm_client = LLMClient(config)
    
    @property
    def name(self) -> str:
        return "performance_analyzer"
    
    @property
    def description(self) -> str:
        return "分析性能测试数据，生成报告和优化建议"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "test_data",
                "type": "string",
                "required": True,
                "description": "性能测试数据（JSON格式）",
            },
            {
                "name": "app_type",
                "type": "string",
                "required": False,
                "default": "game",
                "description": "应用类型: game/web/app",
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """执行性能分析"""
        test_data = context.get_param("test_data")
        app_type = context.get_param("app_type", "game")
        
        # 验证参数
        error = self.validate_params(context)
        if error:
            return SkillResult.fail(error)
        
        try:
            # 调用DeepSeek分析
            report = await self._analyze_with_llm(test_data, app_type)
            return SkillResult.ok(data=report)
        except Exception as e:
            return SkillResult.fail(f"分析失败: {str(e)}")
    
    async def _analyze_with_llm(self, data: str, app_type: str) -> PerformanceReport:
        """使用LLM分析性能数据"""
        prompt = f"""分析以下{app_type}应用的性能测试数据：

{data}

请提供：
1. 总体评分（0-100）
2. 关键指标分析
3. 性能瓶颈识别
4. 优化建议

以JSON格式返回。"""
        
        response = await self.llm_client.complete(prompt)
        # 解析JSON并构建报告...
        return PerformanceReport(
            total_score=85.0,
            metrics=[],
            suggestions=["建议优化内存使用"]
        )
```

4. **注册技能** (`mcp_server.py`)
```python
from src.skills.performance_analyzer import PerformanceAnalyzerSkill

# 在 init_agent 方法中添加
self.agent.register_skill("performance_analyzer", PerformanceAnalyzerSkill(config))
```

5. **添加意图识别** (`src/core/agent.py`)
```python
def _detect_intent(self, message: str) -> Dict[str, Any]:
    message_lower = message.lower()
    
    # 性能分析意图
    if any(kw in message_lower for kw in ["性能", "压测", "负载", "fps", "卡顿"]):
        return {
            "skill": "performance_analyzer",
            "params": {"test_data": message}
        }
    
    # ... 其他意图
```

---

### 任务2：添加新模型支持

**场景**：添加新的 LLM 提供商

**步骤**：

1. **修改 LLM 客户端** (`src/adapters/llm/client.py`)
```python
PROVIDERS = {
    # ... 现有配置
    "new_provider": {
        "base_url": "https://api.new.com/v1",
        "model": "default-model",
    },
}
```

2. **使用新模型**
```yaml
# config/config.yaml
llm:
  provider: new_provider
  api_key: "your_api_key"
```

---

### 任务3：修改 Web 接口

**场景**：添加新的 API 端点

**步骤**：

1. **修改 Web API** (`web/api.py`)
```python
from pydantic import BaseModel

class NewFeatureRequest(BaseModel):
    data: str
    option: str = "default"

@app.post("/new_feature")
async def new_feature(req: NewFeatureRequest):
    key = get_api_key(req.session_token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    try:
        # 调用技能
        config = get_config_with_key(key)
        from src.core.agent import GameTestAgent
        agent = GameTestAgent(config)
        
        result = await agent.execute("my_skill", {
            "data": req.data,
            "option": req.option
        })
        
        return {"success": True, "data": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## 🔧 DeepSeek 使用技巧

### 1. 模型选择

| 场景 | 推荐模型 | 说明 |
|------|----------|------|
| 通用对话 | `deepseek-chat` | 平衡性能和质量 |
| 代码生成 | `deepseek-coder` | 擅长编程任务 |
| 长文档分析 | `deepseek-chat` | 支持长上下文 |

### 2. 提示词优化

```python
# 不好的提示词
prompt = "分析这个需求"

# 好的提示词
prompt = """你是一位专业的游戏测试专家。请分析以下需求文档：

## 分析要求
1. 提取所有功能测试点
2. 识别边界条件和异常情况
3. 评估测试优先级（P0/P1/P2/P3）
4. 列出潜在风险

## 输出格式
请以JSON格式返回，包含以下字段：
- test_points: 测试点列表
- risks: 风险列表
- priority: 优先级分布

## 需求内容
{content}
"""
```

### 3. 流式输出

```python
# 如果需要流式响应
async def stream_analysis():
    async for chunk in llm_client.complete_stream(prompt):
        yield chunk
```

---

## 🐛 调试技巧

### 1. 查看日志

```bash
# 设置日志级别
set LOG_LEVEL=DEBUG  # Windows
export LOG_LEVEL=DEBUG  # Linux/macOS

# 运行后查看 logs/ 目录
```

### 2. 单步调试

```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用 IPython
from IPython import embed; embed()
```

### 3. 测试单个技能

```python
# test_skill.py
import asyncio
import sys
sys.path.insert(0, '.')

from src.core.config import Config
from src.skills.performance_analyzer import PerformanceAnalyzerSkill
from src.skills.base import SkillContext

async def test():
    config = Config()
    skill = PerformanceAnalyzerSkill(config)
    
    context = SkillContext(
        agent=None,
        config=config,
        params={
            "test_data": '{"fps": 30, "memory": 1024}',
            "app_type": "game"
        }
    )
    
    result = await skill.execute(context)
    print(f"成功: {result.success}")
    print(f"数据: {result.data}")

if __name__ == "__main__":
    asyncio.run(test())
```

---

## 📚 常用代码模板

### 模板1：新技能框架

```python
"""
XXX 技能

功能：
1. ...
2. ...
"""

from typing import Any, Dict, List
from src.core.config import Config
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.adapters.llm.client import LLMClient

class XXXSkill(BaseSkill):
    """XXX技能"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.llm_client = LLMClient(config)
    
    @property
    def name(self) -> str:
        return "xxx_skill"
    
    @property
    def description(self) -> str:
        return "描述"
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "param1",
                "type": "string",
                "required": True,
                "description": "参数说明",
            },
        ]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        param1 = context.get_param("param1")
        
        error = self.validate_params(context)
        if error:
            return SkillResult.fail(error)
        
        try:
            result = await self._process(param1)
            return SkillResult.ok(data=result)
        except Exception as e:
            return SkillResult.fail(f"失败: {str(e)}")
    
    async def _process(self, data: str):
        # 实现逻辑
        pass
```

### 模板2：API 端点

```python
from pydantic import BaseModel

class XXXRequest(BaseModel):
    data: str
    session_token: Optional[str] = None

@app.post("/xxx")
async def xxx_endpoint(req: XXXRequest):
    key = get_api_key(req.session_token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    try:
        config = get_config_with_key(key)
        # 处理逻辑
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## ⚠️ 常见错误

### 错误1：导入错误
```
ModuleNotFoundError: No module named 'src'
```
**解决**：确保在项目根目录运行，或添加 `sys.path.insert(0, '.')`

### 错误2：API Key 未配置
```
LLMError: API调用失败
```
**解决**：检查环境变量或配置文件中的 `LLM_API_KEY`

### 错误3：循环导入
```
ImportError: cannot import name 'XXX'
```
**解决**：使用 `TYPE_CHECKING` 延迟导入，或调整导入顺序

---

## 🔗 相关文档

- [项目开发指南](./DEVELOPMENT_GUIDE.md) - 完整开发文档
- [README.md](../README.md) - 项目说明
- [配置示例](../config/config.yaml.example) - 配置参考

---

## 💡 最佳实践

1. **每次修改后运行健康检查**
   ```bash
   python scripts/check_health.py
   ```

2. **使用类型注解**
   ```python
   def process(data: str) -> dict:
       ...
   ```

3. **添加错误处理**
   ```python
   try:
       result = await risky_operation()
   except SpecificError as e:
       logger.error(f"特定错误: {e}")
       return fallback_result
   except Exception as e:
       logger.exception("未知错误")
       raise
   ```

4. **编写测试**
   ```python
   # tests/test_my_skill.py
   import pytest
   
   @pytest.mark.asyncio
   async def test_my_skill():
       # 测试代码
       pass
   ```

---

**祝你开发顺利！** 🚀
