```
# TestOwl - 游戏测试智能助手

基于 MCP (Model Context Protocol) 的游戏测试辅助工具，专注于数值测试和关卡测试领域。

## 功能特性

### 1. 智能对话
- 与 AI 助手进行自然语言交互
- 支持测试问题咨询、测试技巧学习
- 上下文记忆，持续对话

### 2. 需求分析
- 输入文本或上传文档（txt/docx/pdf/xlsx/pptx）
- 自动提取测试点、风险点、待确认问题
- 支持导出 Markdown/PDF/Excel/Word 格式

### 3. 测试用例生成
- 根据需求描述自动生成测试用例
- 包含用例ID、标题、步骤、预期结果
- JSON 格式输出，便于导入测试管理系统

### 4. 配置表检查
- 上传 Excel/CSV 配置表
- 自动检查常见问题（空值、格式、逻辑错误）
- 输出检查报告

### 5. 多格式导出
- 每条对话消息可单独导出
- 支持 Markdown、PDF、Excel、Word 四种格式
- 一键下载，方便分享和归档

## 技术架构

```
├── web/                    # Web 界面
│   ├── index.html         # 前端页面
│   └── api.py             # FastAPI 后端
├── src/                   # 核心代码
│   ├── adapters/          # LLM 适配器
│   ├── skills/            # 技能模块
│   └── utils/             # 工具函数
├── knowledge_base/        # 知识库
└── config/               # 配置文件
```

## 部署说明

### 环境要求
- Python 3.10+
- 依赖：`pip install fastapi uvicorn openpyxl python-docx reportlab`

### 启动服务

```bash
# 启动 MCP 服务（8000 端口）
python3 mcp_server.py

# 启动 Web API（8081 端口）
python3 -m uvicorn web.api:app --host 0.0.0.0 --port 8081

# 启动静态文件服务（8080 端口）
python3 -m http.server 8080 --directory web/
```

### Systemd 服务配置

```bash
# MCP 服务
sudo systemctl enable testowl
sudo systemctl start testowl

# Web API 服务
sudo systemctl enable testowl-api
sudo systemctl start testowl-api

# 静态文件服务
sudo systemctl enable testowl-web
sudo systemctl start testowl-web
```

## 配置

### API Key
1. 访问 Web 界面设置页面
2. 输入 Kimi API Key（或其他支持的 LLM API Key）
3. 点击保存，自动生成 session token

### 支持的模型
- Kimi (kimi-k2-turbo-preview / kimi-k2-pro)
- DeepSeek
- 自动识别（根据任务复杂度智能选择）

## 界面设计规范

- **风格**：扁平化设计
- **色系**：
  - 米色背景：#FAF8F5
  - 深灰文字：#4A4A4A
  - 棕色主色：#5D4E37
  - 浅棕按钮：#B8A090 / #A89070
- **字体**：PingFang SC / Microsoft YaHei（黑体）

## 服务器信息

- **服务器 IP**：121.41.36.197
- **MCP 服务**：8000 端口
- **Web 界面**：http://121.41.36.197:8080
- **API 服务**：8081 端口

## GitHub 仓库

https://github.com/TestOwl-QA/TestOwl

## 更新日志

### 2026-04-09
- Web 界面重构：气泡式对话界面
- 固定底部输入框，高度 80px
- 左下角上传按钮（浅金棕色）
- 发送按钮扁平化整合
- 每条消息支持导出（MD/PDF/Excel/Word）
- 黑体字
- 用户气泡浅色化（#A89070）
- 导出按钮淡色（#D4C4B0）
- Session 持久化存储
- 智能模型选择路由

