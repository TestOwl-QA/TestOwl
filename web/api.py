import traceback
from pathlib import Path

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
    
    # 6. 导出功能可用性检查
    try:
        # 简单检查前端是否有导出相关函数
        with open('/root/testowl/web/index.html', 'r') as f:
            html = f.read()
        has_export = 'exportBubble' in html or 'exportChat' in html
        if has_export:
            checks.append({"name": "导出功能", "status": "pass", "message": "导出功能已启用"})
        else:
            checks.append({"name": "导出功能", "status": "warn", "message": "导出功能未找到"})
    except Exception as e:
        checks.append({"name": "导出功能", "status": "warn", "message": f"检查失败: {str(e)[:30]}"})
    
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

def parse_analysis_content(content: str) -> dict:
    """解析需求分析内容，提取结构化数据"""
    result = {
        "title": "需求分析报告",
        "summary": "",
        "test_points": [],
        "risks": []
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 检测标题
        if line.startswith('需求分析') or line.startswith('测试分析'):
            result["title"] = line
            current_section = "summary"
        elif line.startswith('测试点'):
            current_section = "test_points"
        elif line.startswith('风险'):
            current_section = "risks"
        elif current_section == "summary" and not result["summary"]:
            result["summary"] = line
        elif current_section == "test_points":
            # 解析测试点 [P0] 标题 - 描述
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # 提取优先级和内容
                priority_match = re.search(r'\[([Pp]\d+)\]', line)
                priority = priority_match.group(1).upper() if priority_match else "P2"
                
                # 移除 bullet 和优先级标记
                clean_line = re.sub(r'^[•\-\*]\s*', '', line)
                clean_line = re.sub(r'\[[Pp]\d+\]\s*', '', clean_line)
                
                # 分割标题和描述
                if ' - ' in clean_line:
                    title, desc = clean_line.split(' - ', 1)
                else:
                    title, desc = clean_line, ""
                
                result["test_points"].append({
                    "priority": priority,
                    "title": title.strip(),
                    "description": desc.strip()
                })
        elif current_section == "risks":
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                risk = re.sub(r'^[•\-\*]\s*', '', line)
                result["risks"].append(risk)
    
    return result


def parse_testcase_content(content: str) -> dict:
    """解析测试用例内容，提取结构化数据"""
    result = {
        "title": "测试用例报告",
        "cases": []
    }
    
    lines = content.split('\n')
    current_case = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检测标题
        if line.startswith('测试用例'):
            result["title"] = line
        # 检测用例标题行 (TC001 xxx [P0])
        elif re.match(r'^TC\d+', line):
            # 保存上一个用例
            if current_case:
                result["cases"].append(current_case)
            
            # 解析新用例
            match = re.match(r'(TC\d+)\s+(.+?)\s*\[([Pp]\d+)\]', line)
            if match:
                case_id = match.group(1)
                title = match.group(2)
                priority = match.group(3).upper()
            else:
                case_id = re.match(r'(TC\d+)', line).group(1)
                title = line.replace(case_id, '').strip()
                priority = "P2"
            
            current_case = {
                "id": case_id,
                "title": title,
                "priority": priority,
                "steps": [],
                "expected": ""
            }
        # 检测步骤 (1. xxx 或 li 内容)
        elif current_case and (re.match(r'^\d+[\.、]\s*', line) or line.startswith('预期:') or line.startswith('预期：')):
            if line.startswith('预期:') or line.startswith('预期：'):
                current_case["expected"] = line.replace('预期:', '').replace('预期：', '').strip()
            else:
                # 移除序号前缀
                step = re.sub(r'^\d+[\.、]\s*', '', line)
                current_case["steps"].append(step)
        # 检测预期结果行
        elif current_case and ('预期' in line or 'expected' in line.lower()):
            current_case["expected"] = re.sub(r'.*预期[：:]\s*', '', line, flags=re.IGNORECASE)
    
    # 保存最后一个用例
    if current_case:
        result["cases"].append(current_case)
    
    return result


def export_analysis_report(parsed: dict, fmt: str, timestamp: str) -> dict:
    """导出需求分析报告"""
    try:
        if fmt == "md":
            md_lines = [f"# {parsed['title']}", ""]
            
            if parsed['summary']:
                md_lines.extend(["## 概述", parsed['summary'], ""])
            
            if parsed['test_points']:
                md_lines.extend(["## 测试点", ""])
                for tp in parsed['test_points']:
                    md_lines.append(f"### [{tp['priority']}] {tp['title']}")
                    if tp['description']:
                        md_lines.append(f"{tp['description']}")
                    md_lines.append("")
            
            if parsed['risks']:
                md_lines.extend(["## 风险", ""])
                for risk in parsed['risks']:
                    md_lines.append(f"- {risk}")
                md_lines.append("")
            
            file_bytes = '\n'.join(md_lines).encode('utf-8')
            filename = f"analysis_report_{timestamp}.md"
        
        elif fmt == "pdf":
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            font_name = 'Helvetica'
            font_paths = [
                '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            ]
            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                        font_name = 'ChineseFont'
                        break
                except:
                    continue
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(name='ChineseTitle', fontName=font_name, fontSize=18, spaceAfter=20))
            styles.add(ParagraphStyle(name='ChineseHeading', fontName=font_name, fontSize=14, spaceAfter=12, spaceBefore=12))
            styles.add(ParagraphStyle(name='ChineseBody', fontName=font_name, fontSize=10, spaceAfter=6))
            
            story = []
            
            story.append(Paragraph(parsed['title'], styles['ChineseTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            if parsed['summary']:
                story.append(Paragraph("概述", styles['ChineseHeading']))
                story.append(Paragraph(parsed['summary'], styles['ChineseBody']))
                story.append(Spacer(1, 0.1*inch))
            
            if parsed['test_points']:
                story.append(Paragraph("测试点", styles['ChineseHeading']))
                story.append(Spacer(1, 0.1*inch))
                
                data = [['优先级', '测试项', '描述']]
                for tp in parsed['test_points']:
                    data.append([tp['priority'], tp['title'], tp['description'][:50] + '...' if len(tp['description']) > 50 else tp['description']])
                
                table = Table(data, colWidths=[0.8*inch, 2*inch, 3*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c4a77d')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), font_name),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f0e8')]),
                ]))
                story.append(table)
                story.append(Spacer(1, 0.2*inch))
            
            if parsed['risks']:
                story.append(Paragraph("风险", styles['ChineseHeading']))
                for risk in parsed['risks']:
                    story.append(Paragraph(f"• {risk}", styles['ChineseBody']))
            
            doc.build(story)
            file_bytes = buffer.getvalue()
            filename = f"analysis_report_{timestamp}.pdf"
        
        elif fmt == "xlsx":
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            
            wb = Workbook()
            
            if parsed['test_points']:
                ws = wb.active
                ws.title = "测试点"
                
                headers = ['优先级', '测试项', '描述']
                ws.append(headers)
                
                header_fill = PatternFill(start_color='C4A77D', end_color='C4A77D', fill_type='solid')
                header_font = Font(bold=True, color='FFFFFF')
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                
                for tp in parsed['test_points']:
                    ws.append([tp['priority'], tp['title'], tp['description']])
                
                ws.column_dimensions['A'].width = 10
                ws.column_dimensions['B'].width = 30
                ws.column_dimensions['C'].width = 50
            
            if parsed['risks']:
                ws_risk = wb.create_sheet("风险")
                ws_risk.append(['序号', '风险描述'])
                
                header_fill = PatternFill(start_color='C4A77D', end_color='C4A77D', fill_type='solid')
                header_font = Font(bold=True, color='FFFFFF')
                for cell in ws_risk[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                
                for i, risk in enumerate(parsed['risks'], 1):
                    ws_risk.append([i, risk])
                
                ws_risk.column_dimensions['A'].width = 8
                ws_risk.column_dimensions['B'].width = 80
            
            buffer = BytesIO()
            wb.save(buffer)
            file_bytes = buffer.getvalue()
            filename = f"analysis_report_{timestamp}.xlsx"
        
        elif fmt == "docx":
            from docx import Document
            from docx.shared import Pt, RGBColor, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
            doc = Document()
            
            title = doc.add_heading(parsed['title'], 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            if parsed['summary']:
                doc.add_heading('概述', level=1)
                doc.add_paragraph(parsed['summary'])
            
            if parsed['test_points']:
                doc.add_heading('测试点', level=1)
                for tp in parsed['test_points']:
                    p = doc.add_paragraph()
                    p.add_run(f"[{tp['priority']}] ").bold = True
                    p.add_run(tp['title']).bold = True
                    if tp['description']:
                        doc.add_paragraph(tp['description'], style='List Bullet')
            
            if parsed['risks']:
                doc.add_heading('风险', level=1)
                for risk in parsed['risks']:
                    doc.add_paragraph(risk, style='List Bullet')
            
            buffer = BytesIO()
            doc.save(buffer)
            file_bytes = buffer.getvalue()
            filename = f"analysis_report_{timestamp}.docx"
        
        else:
            return {"success": False, "error": f"不支持的格式: {fmt}"}
        
        return {
            "success": True,
            "file": base64.b64encode(file_bytes).decode('utf-8'),
            "filename": filename
        }
    
    except Exception as e:
        import traceback
        return {"success": False, "error": f"导出失败: {str(e)}", "traceback": traceback.format_exc()}


def export_testcase_report(parsed: dict, fmt: str, timestamp: str) -> dict:
    """导出测试用例报告"""
    try:
        if fmt == "md":
            md_lines = [f"# {parsed['title']}", ""]
            
            for case in parsed['cases']:
                md_lines.append(f"## {case['id']} {case['title']} [{case['priority']}]")
                md_lines.append("")
                md_lines.append("**测试步骤：**")
                for i, step in enumerate(case['steps'], 1):
                    md_lines.append(f"{i}. {step}")
                md_lines.append("")
                md_lines.append(f"**预期结果：**{case['expected']}")
                md_lines.append("")
            
            file_bytes = '\n'.join(md_lines).encode('utf-8')
            filename = f"testcase_report_{timestamp}.md"
        
        elif fmt == "pdf":
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            font_name = 'Helvetica'
            font_paths = [
                '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            ]
            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                        font_name = 'ChineseFont'
                        break
                except:
                    continue
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(name='ChineseTitle', fontName=font_name, fontSize=18, spaceAfter=20))
            styles.add(ParagraphStyle(name='ChineseHeading', fontName=font_name, fontSize=14, spaceAfter=12, spaceBefore=12))
            styles.add(ParagraphStyle(name='ChineseSubHeading', fontName=font_name, fontSize=12, spaceAfter=8, spaceBefore=8, textColor=colors.HexColor('#5c4b37')))
            styles.add(ParagraphStyle(name='ChineseBody', fontName=font_name, fontSize=10, spaceAfter=6))
            
            story = []
            
            story.append(Paragraph(parsed['title'], styles['ChineseTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            for case in parsed['cases']:
                story.append(Paragraph(f"{case['id']} {case['title']} [{case['priority']}]", styles['ChineseHeading']))
                
                story.append(Paragraph("测试步骤：", styles['ChineseSubHeading']))
                for i, step in enumerate(case['steps'], 1):
                    story.append(Paragraph(f"{i}. {step}", styles['ChineseBody']))
                
                story.append(Paragraph("预期结果：", styles['ChineseSubHeading']))
                story.append(Paragraph(case['expected'], styles['ChineseBody']))
                story.append(Spacer(1, 0.15*inch))
            
            doc.build(story)
            file_bytes = buffer.getvalue()
            filename = f"testcase_report_{timestamp}.pdf"
        
        elif fmt == "xlsx":
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
            
            wb = Workbook()
            ws = wb.active
            ws.title = "测试用例"
            
            # 标准测试用例表格格式
            headers = ['用例编号', '所属模块', '用例标题', '前置条件', '测试步骤', '预期结果', '优先级', '执行结果', '备注']
            ws.append(headers)
            
            # 表头样式
            header_fill = PatternFill(start_color='C4A77D', end_color='C4A77D', fill_type='solid')
            header_font = Font(bold=True, color='FFFFFF', size=11)
            header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            thin_border = Border(
                left=Side(style='thin', color='d4c8b8'),
                right=Side(style='thin', color='d4c8b8'),
                top=Side(style='thin', color='d4c8b8'),
                bottom=Side(style='thin', color='d4c8b8')
            )
            
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment
                cell.border = thin_border
            
            # 设置表头行高
            ws.row_dimensions[1].height = 30
            
            # 数据行样式
            data_font = Font(size=10)
            data_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
            priority_alignment = Alignment(horizontal='center', vertical='center')
            
            # 优先级颜色映射
            priority_colors = {
                'P0': 'FF6B6B',  # 红色
                'P1': 'FFB347',  # 橙色
                'P2': '87CEEB',  # 蓝色
            }
            
            for idx, case in enumerate(parsed['cases'], start=2):
                # 格式化测试步骤（带序号换行）
                steps_text = '\n'.join([f"{i}. {step}" for i, step in enumerate(case['steps'], 1)])
                
                # 提取模块信息（从标题中尝试提取）
                module = "登录功能"  # 默认模块，可根据实际情况调整
                
                row_data = [
                    case['id'],           # 用例编号
                    module,               # 所属模块
                    case['title'],        # 用例标题
                    "",                   # 前置条件（可扩展）
                    steps_text,           # 测试步骤
                    case['expected'],     # 预期结果
                    case['priority'],     # 优先级
                    "",                   # 执行结果（空白待填写）
                    ""                    # 备注
                ]
                ws.append(row_data)
                
                # 设置数据行样式
                for col_idx, cell in enumerate(ws[idx], start=1):
                    cell.font = data_font
                    cell.border = thin_border
                    
                    # 优先级列居中并着色
                    if col_idx == 7:  # 优先级列
                        cell.alignment = priority_alignment
                        priority = case['priority'].upper()
                        if priority in priority_colors:
                            cell.fill = PatternFill(start_color=priority_colors[priority], 
                                                   end_color=priority_colors[priority], 
                                                   fill_type='solid')
                            cell.font = Font(bold=True, color='FFFFFF', size=10)
                    # 用例编号居中
                    elif col_idx == 1:
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                    else:
                        cell.alignment = data_alignment
                
                # 设置行高（根据内容自动调整）
                ws.row_dimensions[idx].height = max(40, len(case['steps']) * 15 + 10)
            
            # 设置列宽
            ws.column_dimensions['A'].width = 12  # 用例编号
            ws.column_dimensions['B'].width = 15  # 所属模块
            ws.column_dimensions['C'].width = 30  # 用例标题
            ws.column_dimensions['D'].width = 25  # 前置条件
            ws.column_dimensions['E'].width = 45  # 测试步骤
            ws.column_dimensions['F'].width = 35  # 预期结果
            ws.column_dimensions['G'].width = 10  # 优先级
            ws.column_dimensions['H'].width = 12  # 执行结果
            ws.column_dimensions['I'].width = 20  # 备注
            
            # 冻结首行
            ws.freeze_panes = 'A2'
            
            buffer = BytesIO()
            wb.save(buffer)
            file_bytes = buffer.getvalue()
            filename = f"testcase_report_{timestamp}.xlsx"
        
        elif fmt == "docx":
            from docx import Document
            from docx.shared import Pt, RGBColor, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
            doc = Document()
            
            title = doc.add_heading(parsed['title'], 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            for case in parsed['cases']:
                p = doc.add_heading(level=2)
                run = p.add_run(f"{case['id']} {case['title']} [{case['priority']}]")
                run.bold = True
                
                doc.add_paragraph("测试步骤：", style='Heading 3')
                for i, step in enumerate(case['steps'], 1):
                    doc.add_paragraph(f"{i}. {step}", style='List Number')
                
                doc.add_paragraph("预期结果：", style='Heading 3')
                doc.add_paragraph(case['expected'])
                doc.add_paragraph()  # 空行
            
            buffer = BytesIO()
            doc.save(buffer)
            file_bytes = buffer.getvalue()
            filename = f"testcase_report_{timestamp}.docx"
        
        else:
            return {"success": False, "error": f"不支持的格式: {fmt}"}
        
        return {
            "success": True,
            "file": base64.b64encode(file_bytes).decode('utf-8'),
            "filename": filename
        }
    
    except Exception as e:
        import traceback
        return {"success": False, "error": f"导出失败: {str(e)}", "traceback": traceback.format_exc()}


@app.post("/export_single")
async def export_single(req: dict):
    """导出单条消息为报告格式"""
    key = get_api_key(req.get("session_token", ""))
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    content = req.get("content", "")
    fmt = req.get("format", "md")
    bubble_type = req.get("bubble_type", "analysis")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 根据气泡类型选择解析和导出方式
    if bubble_type == "testcase":
        parsed = parse_testcase_content(content)
        return export_testcase_report(parsed, fmt, timestamp)
    else:
        # 默认需求分析
        parsed = parse_analysis_content(content)
        return export_analysis_report(parsed, fmt, timestamp)


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