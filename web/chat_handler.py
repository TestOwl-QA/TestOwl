import asyncio
import json
import os
import re
from pathlib import Path

# 动态添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
import sys
sys.path.insert(0, str(PROJECT_ROOT))

async def detect_intent(client, user_msg, history):
    """自然对话中识别意图"""
    prompt = """从用户输入中识别意图。返回JSON:
{"intent":"analyze|generate|check_table|analyze_bug|chat","target":"具体内容"}

意图:
- analyze: 分析需求/功能/设计
- generate: 生成测试用例
- check_table: 检查配置表/数据表
- analyze_bug: 分析bug/崩溃/错误
- chat: 普通聊天/问答/闲聊

示例:
"帮我分析登录功能" → {"intent":"analyze","target":"登录功能"}
"写个支付的测试用例" → {"intent":"generate","target":"支付功能"}
"这张表有问题吗" → {"intent":"check_table","target":"配置表"}
"这个报错是什么原因" → {"intent":"analyze_bug","target":"报错分析"}
"你好" → {"intent":"chat","target":""}

输入: """ + user_msg
    
    try:
        result = await asyncio.wait_for(client.complete(prompt), timeout=8)
        clean = result.strip()
        if "```" in clean:
            clean = clean.split("```")[1].replace("json", "").strip()
        return json.loads(clean)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        # 降级：当AI解析失败时，使用关键词匹配
        if "分析" in user_msg:
            return {"intent": "analyze", "target": user_msg.replace("分析", "").strip()}
        elif "用例" in user_msg:
            return {"intent": "generate", "target": user_msg.replace("生成用例", "").replace("写个", "").strip()}
        elif "表" in user_msg or "配置" in user_msg:
            return {"intent": "check_table", "target": "配置表"}
        elif "报错" in user_msg or "崩溃" in user_msg or "bug" in user_msg.lower():
            return {"intent": "analyze_bug", "target": user_msg}
        return {"intent": "chat", "target": ""}

async def handle_chat(req, get_api_key, get_config_with_key, file_contents=None):
    """处理聊天请求
    
    Args:
        req: 请求数据
        get_api_key: 获取API key的函数
        get_config_with_key: 获取配置的函数
        file_contents: 文件内容字典 {file_id: {filename, content, ...}}
    """
    user_msg = req.get("message", "")
    token = req.get("session_token", "")
    history = req.get("history", [])
    file_id = req.get("file_id", "")  # 获取关联的文件ID
    key = get_api_key(token)
    
    if not key:
        return {"success": False, "error": "请先配置API Key"}
    
    try:
        config = get_config_with_key(key)
        config.llm.model = 'kimi-k2-turbo-preview'
        from src.adapters.llm.client import LLMClient
        client = LLMClient(config)
        
        # 意图识别
        intent_data = await detect_intent(client, user_msg, history)
        intent = intent_data.get("intent", "chat")
        target = intent_data.get("target", "")
        
        # 检查是否有上传的文件
        file_content = ""
        file_name = ""
        if file_id and file_contents and file_id in file_contents:
            file_info = file_contents[file_id]
            file_content = file_info.get("content", "")
            file_name = file_info.get("filename", "")
        
        # 检查用户是否指代文件（如"这个需求"、"该文件"等）
        referential_words = ["这个", "该", "此", "上传的", "刚才的", "文档", "文件", "需求"]
        is_referring_to_file = any(word in user_msg for word in referential_words)
        
        # 如果有文件内容，且用户可能指代文件，将文件内容加入上下文
        if file_content and (is_referring_to_file or len(target) < 50 or intent in ["analyze", "generate"]):
            # 构建文件上下文
            file_context = f"文件《{file_name}》的内容：\n{file_content[:4000]}"
            if target:
                target = f"{target}\n\n{file_context}"
            else:
                target = file_context
        
        # 需求分析
        if intent == "analyze" and target:
            prompt = """分析以下测试需求，提取测试点和风险。JSON格式:
{"summary":"概述","test_points":[{"title":"场景","desc":"说明","pri":"P0/P1/P2"}],"risks":["风险1","风险2"]}

需求: """ + target
            
            result = await asyncio.wait_for(client.complete(prompt), timeout=60)
            try:
                clean = result.strip()
                if "```" in clean:
                    clean = clean.split("```")[1].replace("json", "").strip()
                data = json.loads(clean)
                
                output = f"<h3>需求分析</h3><p>{data.get('summary', '')}</p>"
                points = data.get('test_points', [])
                if points:
                    output += "<h4>测试点</h4><ul>"
                    for p in points:
                        output += f"<li>[{p.get('pri','P2')}] {p.get('title','')} - {p.get('desc','')}</li>"
                    output += "</ul>"
                risks = data.get('risks', [])
                if risks:
                    output += "<h4>风险</h4><ul>"
                    for r in risks:
                        output += f"<li>{r}</li>"
                    output += "</ul>"
                return {"success": True, "response": output}
            except (json.JSONDecodeError, Exception):
                # JSON解析失败时直接返回原始结果
                return {"success": True, "response": result}
        
        # 生成用例
        elif intent == "generate" and target:
            prompt = """为以下需求生成测试用例。JSON格式:
{"cases":[{"id":"TC001","title":"标题","steps":["步骤1","步骤2"],"expected":"预期","pri":"P0/P1/P2"}]}

需求: """ + target
            
            result = await asyncio.wait_for(client.complete(prompt), timeout=60)
            try:
                clean = result.strip()
                if "```" in clean:
                    clean = clean.split("```")[1].replace("json", "").strip()
                data = json.loads(clean)
                
                output = "<h3>测试用例</h3>"
                for c in data.get('cases', []):
                    output += f"<h4>{c.get('id','')} {c.get('title','')} [{c.get('pri','P2')}]</h4>"
                    output += "<ol>"
                    for s in c.get('steps', []):
                        # 移除步骤中已有的序号前缀（如 "1. "、"2. "）
                        clean_step = re.sub(r'^\d+[\.、]\s*', '', s)
                        output += f"<li>{clean_step}</li>"
                    output += f"</ol><p><b>预期:</b>{c.get('expected','')}</p>"
                return {"success": True, "response": output}
            except (json.JSONDecodeError, Exception):
                # JSON解析失败时直接返回原始结果
                return {"success": True, "response": result}
        
        # 表检查 - 自然引导
        elif intent == "check_table":
            return {
                "success": True,
                "response": "好的，把配置表发给我，我帮你看一下有没有问题。"
            }
        
        # Bug分析 - 自然引导
        elif intent == "analyze_bug":
            return {
                "success": True,
                "response": "把报错信息或崩溃日志发我看看，帮你分析下原因。"
            }
        
        # 普通对话 - 自然交流
        else:
            context = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in history[-3:]])
            prompt = f"""简洁自然地回复用户。你是测试领域的专业人士，但不要强调身份，直接说事。

对话:
{context}
用户: {user_msg}"""
            
            result = await asyncio.wait_for(client.complete(prompt), timeout=60)
            return {"success": True, "response": result}
    
    except asyncio.TimeoutError:
        return {"success": False, "error": "响应超时了，稍后再试"}
    except Exception as e:
        return {"success": False, "error": f"出错了: {str(e)}"}