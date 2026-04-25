import traceback

# 智能模型选择
def get_model_for_task(task_type, text_len):
    """根据任务类型和复杂度选择模型"""
    if task_type == 'chat':
        return 'kimi-k2-turbo-preview'  # 对话用快速模型
    elif task_type == 'check':
        return 'kimi-k2-turbo-preview'  # 表检查用快速模型
    elif task_type == 'analyze':
        if text_len > 3000:
            return 'kimi-k2-pro'  # 长文档用强模型
        return 'kimi-k2-turbo-preview'
    elif task_type == 'generate':
        return 'kimi-k2-pro'  # 用例生成需要高质量
    return 'kimi-k2-turbo-preview'

import re
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import secrets
import time
import tempfile
import shutil
from typing import Optional
import asyncio

# 动态添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import Config

app = FastAPI(title="TestOwl API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}

class SaveKeyRequest(BaseModel):
    api_key: str

class AnalyzeRequest(BaseModel):
    text: str
    session_token: Optional[str] = None

class UrlRequest(BaseModel):
    url: str

def get_api_key(session_token: Optional[str]) -> Optional[str]:
    if session_token and session_token in sessions:
        if time.time() - sessions[session_token]['created'] < 7 * 24 * 3600:
            return sessions[session_token]['api_key']
        else:
            del sessions[session_token]
    return None

def get_config_with_key(api_key: str):
    """创建带有指定API key的config"""
    config = Config('/root/testowl/config/config.yaml')
    config.llm.api_key = api_key
    return config

def parse_file(file_path: str, suffix: str) -> str:
    content = ""
    if suffix == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    elif suffix in ['.docx', '.doc']:
        from docx import Document
        doc = Document(file_path)
        content = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
    elif suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        content = '\n'.join([page.extract_text() or '' for page in reader.pages])
    elif suffix in ['.xlsx', '.xls']:
        from openpyxl import load_workbook
        wb = load_workbook(file_path, data_only=True)
        texts = []
        for sheet in wb.worksheets:
            texts.append(f"=== {sheet.title} ===")
            for row in sheet.iter_rows(values_only=True):
                if any(cell for cell in row):
                    texts.append(' | '.join(str(cell or '') for cell in row))
        content = '\n'.join(texts)
    elif suffix == '.pptx':
        from pptx import Presentation
        prs = Presentation(file_path)
        texts = []
        for i, slide in enumerate(prs.slides):
            texts.append(f"=== 第{i+1}页 ===")
            for shape in slide.shapes:
                if hasattr(shape, 'text') and shape.text.strip():
                    texts.append(shape.text)
        content = '\n'.join(texts)
    elif suffix in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(file_path)
            content = pytesseract.image_to_string(img, lang='chi_sim+eng')
        except:
            content = "[图片OCR失败]"
    return content.strip()

def fetch_url(url: str) -> str:
    try:
        from bs4 import BeautifulSoup
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        title = soup.title.string if soup.title else ''
        text = soup.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        return f"标题: {title}\n\n" + '\n'.join(lines)
    except Exception as e:
        raise Exception(str(e))

@app.post("/auth/save_key")
async def save_key(req: SaveKeyRequest):
    token = secrets.token_urlsafe(32)
    sessions[token] = {'api_key': req.api_key, 'created': time.time()}
    return {"success": True, "session_token": token}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        suffix = os.path.splitext(file.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        content = parse_file(tmp_path, suffix)
        os.unlink(tmp_path)
        if not content:
            return {"success": False, "error": "文件内容为空"}
        return {"success": True, "text": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/fetch_url")
async def fetch_url_endpoint(req: UrlRequest):
    try:
        content = fetch_url(req.url)
        return {"success": True, "text": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    key = get_api_key(req.session_token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    try:
        config = get_config_with_key(key)
        from src.adapters.llm.client import LLMClient
        
        text = req.text[:6000] if len(req.text) > 6000 else req.text
        model = get_model_for_task('analyze', len(text))
        config.llm.model = model
        client = LLMClient(config)
        
        prompt = "分析需求，提取测试点、风险点、待确认问题。返回JSON: " + text + " 必须包含: {document_summary,test_points:[{id,title,description,priority,category}],risk_points:[{description,impact}],questions:[{question}]}"
        result = await asyncio.wait_for(client.complete(prompt), timeout=90)
        
        import json
        clean = result.strip()
        if "```" in clean:
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else parts[0]
            clean = clean.replace("json", "", 1).strip()
        
        return {"success": True, "data": json.loads(clean)}
    except asyncio.TimeoutError:
        return {"success": False, "error": "分析超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/generate_cases")
async def generate_cases(req: AnalyzeRequest):
    key = get_api_key(req.session_token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    try:
        config = get_config_with_key(key)
        from src.adapters.llm.client import LLMClient
        
        text = req.text[:5000] if len(req.text) > 5000 else req.text
        model = get_model_for_task('generate', len(text))
        config.llm.model = model
        client = LLMClient(config)
        
        prompt = f"根据以下需求生成测试用例JSON: {text} 格式: test_cases数组"
        result = await asyncio.wait_for(client.complete(prompt), timeout=90)
        
        import json
        clean_result = result.strip()
        if "```" in clean_result:
            clean_result = clean_result.split("```")[1]
            if clean_result.startswith("json"):
                clean_result = clean_result[4:]
        
        return {"success": True, "data": json.loads(clean_result)}
    except asyncio.TimeoutError:
        return {"success": False, "error": "生成超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health():
    """真实冒烟测试"""
    import time, os, traceback
    from io import BytesIO
    from datetime import datetime
    
    checks = []
    
    # 1. API服务检查
    checks.append({"name": "API服务", "status": "pass", "message": "运行正常"})
    
    # 2. 会话管理检查
    try:
        active_count = len(sessions)
        checks.append({"name": "会话管理", "status": "pass", "message": f"正常，{active_count}个活跃会话"})
    except Exception as e:
        checks.append({"name": "会话管理", "status": "fail", "message": str(e)})
    
    # 3. 文件存储检查
    try:
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        file_count = len(os.listdir(upload_dir)) if os.path.exists(upload_dir) else 0
        checks.append({"name": "文件存储", "status": "pass", "message": f"目录正常，{file_count}个文件"})
    except Exception as e:
        checks.append({"name": "文件存储", "status": "fail", "message": str(e)})
    
    # 4. 导出功能检查 - 模拟前端实际请求参数
    export_formats = [
        ("md", "Markdown"),
        ("pdf", "PDF"),
        ("xlsx", "Excel"),  # 前端实际传的是xlsx
        ("docx", "Word")    # 前端实际传的是docx
    ]
    
    for fmt, name in export_formats:
        try:
            # 真实生成文件到内存
            if fmt == "md":
                file_bytes = "测试内容".encode('utf-8')
            elif fmt == "pdf":
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                try:
                    pdfmetrics.registerFont(TTFont('SimSun', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'))
                    font = 'SimSun'
                except:
                    font = 'Helvetica'
                buffer = BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                c.setFont(font, 10)
                c.drawString(50, 800, "测试内容")
                c.save()
                file_bytes = buffer.getvalue()
            elif fmt == "xlsx":
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.cell(row=1, column=1, value="测试内容")
                buffer = BytesIO()
                wb.save(buffer)
                file_bytes = buffer.getvalue()
            elif fmt == "docx":
                from docx import Document
                doc = Document()
                doc.add_paragraph("测试内容")
                buffer = BytesIO()
                doc.save(buffer)
                file_bytes = buffer.getvalue()
            
            checks.append({"name": f"{name}导出", "status": "pass", "message": "生成成功"})
        except Exception as e:
            tb = traceback.format_exc()
            checks.append({
                "name": f"{name}导出", 
                "status": "fail", 
                "message": str(e)[:50],
                "traceback": tb
            })
    
    # 5. 配置目录检查
    try:
        config_exists = os.path.exists("config")
        checks.append({"name": "配置目录", "status": "pass" if config_exists else "warn", "message": "存在" if config_exists else "不存在"})
    except Exception as e:
        checks.append({"name": "配置目录", "status": "fail", "message": str(e)})
    
    # 6. 前后端参数一致性检查（新增）
    try:
        with open('/root/testowl/web/index.html', 'r') as f:
            html = f.read()
        # 检查前端导出按钮传的参数（支持 exportChat 和 exportBubble）
        # 匹配 exportBubble('md') 或 exportBubble(\'md\')
        frontend_formats = re.findall(r"export(Chat|Bubble)\\?['\"](\w+)\\?['\"]", html)
        # 提取格式参数
        formats = [match[1] for match in frontend_formats]
        expected = ['md', 'pdf', 'xlsx', 'docx']
        missing = [f for f in expected if f not in formats]
        wrong = [f for f in formats if f not in expected]
        
        if missing or wrong:
            msg = f"前端参数异常: 缺少{missing}, 错误{wrong}" if (missing or wrong) else "参数一致"
            checks.append({"name": "前后端参数", "status": "warn" if (missing or wrong) else "pass", "message": msg})
        else:
            checks.append({"name": "前后端参数", "status": "pass", "message": "参数一致"})
    except Exception as e:
        checks.append({"name": "前后端参数", "status": "warn", "message": f"检查失败: {str(e)[:30]}"})
    
    return {
        "status": "ok" if all(c["status"] == "pass" for c in checks) else "warn",
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }


@app.post("/export")
async def export_report(req: AnalyzeRequest):
    key = get_api_key(req.session_token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    try:
        config = get_config_with_key(key)
        from src.adapters.llm.client import LLMClient
        client = LLMClient(config)
        
        prompt = "生成测试分析报告(Markdown格式): " + req.text[:3000]
        result = await asyncio.wait_for(client.complete(prompt), timeout=60)
        
        from datetime import datetime
        return {
            "success": True,
            "filename": f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            "content": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


from web.chat_handler import handle_chat

@app.post("/chat")
async def chat(req: dict):
    return await handle_chat(req, get_api_key, get_config_with_key)

@app.post("/export_chat")
async def export_chat(req: dict):
    """导出对话记录为报告"""
    token = req.get("session_token")
    messages = req.get("messages", [])
    fmt = req.get("format", "md")
    
    key = get_api_key(token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    try:
        config = get_config_with_key(key)
        from src.adapters.llm.client import LLMClient
        client = LLMClient(config)
        
        # 构建对话内容
        chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        if fmt == "html":
            prompt = f"将以下对话整理为HTML格式的测试报告，包含样式：\n{chat_text}"
        elif fmt == "txt":
            prompt = f"将以下对话整理为纯文本格式的测试报告：\n{chat_text}"
        else:
            prompt = f"将以下对话整理为Markdown格式的测试报告，包含标题、测试要点、结论：\n{chat_text}"
        
        result = await asyncio.wait_for(client.complete(prompt), timeout=60)
        
        from datetime import datetime
        ext = {"md": "md", "txt": "txt", "html": "html"}.get(fmt, "md")
        
        return {
            "success": True,
            "filename": f"chat_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}",
            "content": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

import base64
from datetime import datetime
from io import BytesIO

@app.post("/export_single")
async def export_single(req: dict):
    """导出单条消息"""
    key = get_api_key(req.get("session_token", ""))
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    content = req.get("content", "")
    fmt = req.get("format", "md")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if fmt == "md":
            filename = f"testowl_{timestamp}.md"
            file_bytes = content.encode('utf-8')
        
        elif fmt == "pdf":
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            # 注册中文字体（如果有的话）
            try:
                pdfmetrics.registerFont(TTFont('SimSun', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'))
                font = 'SimSun'
            except:
                font = 'Helvetica'
            
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            c.setFont(font, 10)
            
            # 简单的文本换行
            y = 800
            for line in content.split('\n'):
                if y < 50:
                    c.showPage()
                    y = 800
                c.drawString(50, y, line[:80])
                y -= 15
            
            c.save()
            file_bytes = buffer.getvalue()
            filename = f"testowl_{timestamp}.pdf"
        
        elif fmt == "xlsx":
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "导出内容"
            for i, line in enumerate(content.split('\n'), 1):
                ws.cell(row=i, column=1, value=line)
            
            buffer = BytesIO()
            wb.save(buffer)
            file_bytes = buffer.getvalue()
            filename = f"testowl_{timestamp}.xlsx"
        
        elif fmt == "docx":
            from docx import Document
            doc = Document()
            for line in content.split('\n'):
                doc.add_paragraph(line)
            
            buffer = BytesIO()
            doc.save(buffer)
            file_bytes = buffer.getvalue()
            filename = f"testowl_{timestamp}.docx"
        
        else:
            return {"success": False, "error": "不支持的格式"}
        
        return {
            "success": True,
            "file": base64.b64encode(file_bytes).decode('utf-8'),
            "filename": filename
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

import base64
from datetime import datetime
from io import BytesIO


@app.post("/test/run")
async def run_test():
    """运行Web自检（占位）"""
    return {"status": "developing", "message": "功能开发中"}

@app.get("/files/list")
async def list_files(path: str = "."):
    """获取文件列表（开发者模式）"""
    import os
    try:
        files = os.listdir(path)
        return {"files": files, "path": path}
    except Exception as e:
        return {"error": str(e)}

@app.get("/files/read")
async def read_file_api(path: str):
    """读取文件内容（开发者模式）"""
    try:
        with open(path, 'r') as f:
            content = f.read()
        return {"content": content, "path": path}
    except Exception as e:
        return {"error": str(e)}

@app.post("/files/save")
async def save_file_api(req: dict):
    """保存文件内容（开发者模式）"""
    try:
        path = req.get("path")
        content = req.get("content")
        with open(path, 'w') as f:
            f.write(content)
        return {"success": True, "path": path}
    except Exception as e:
        return {"error": str(e)}