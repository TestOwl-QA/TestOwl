import asyncio
import json

async def handle_chat(req, get_api_key, get_config_with_key):
    """智能对话接口"""
    token = req.get("session_token")
    user_msg = req.get("message", "")
    history = req.get("history", [])
    
    key = get_api_key(token)
    if not key:
        return {"success": False, "error": "未配置API Key"}
    
    thoughts = []
    
    try:
        config = get_config_with_key(key)
        config.llm.model = 'kimi-k2-turbo-preview'
        from src.adapters.llm.client import LLMClient
        client = LLMClient(config)
        
        # 意图识别
        thoughts.append({"step": "意图识别", "status": "done", "content": "分析用户输入..."})
        
        intent = "chat"
        target = ""
        
        if user_msg.startswith("分析") or "分析需求" in user_msg:
            intent = "analyze"
            target = user_msg.replace("分析", "").replace("需求：", "").replace("需求:", "").strip()
        elif user_msg.startswith("生成用例") or "生成测试用例" in user_msg:
            intent = "generate"
            target = user_msg.replace("生成用例", "").replace("：", ":").strip()
        
        thoughts[-1]["content"] = f"意图: {intent}"
        
        # 分析需求
        if intent == "analyze" and target:
            thoughts.append({"step": "需求分析", "status": "thinking", "content": "正在分析..."})
            
            prompt = """作为资深测试专家，深入分析测试需求。返回JSON格式:
{
  "summary": "需求核心功能描述",
  "test_points": [{"id": "T001", "title": "测试场景", "description": "测试什么", "priority": "P0/P1/P2", "category": "功能/性能/安全"}],
  "risks": [{"scenario": "风险场景", "impact": "影响", "suggestion": "测试建议"}],
  "questions": ["待确认问题"]
}

需求: """ + target
            
            result = await asyncio.wait_for(client.complete(prompt), timeout=60)
            
            try:
                clean = result.strip()
                if "```" in clean:
                    clean = clean.split("```")[1].replace("json", "").strip()
                data = json.loads(clean)
                
                thoughts[-1]["status"] = "done"
                thoughts[-1]["content"] = f"识别{len(data.get('test_points', []))}个测试点"
                
                # 直接返回HTML格式
                output = "<b>需求分析结果</b><br><br>"
                output += "<b>概述:</b> " + data.get('summary', '') + "<br><br>"
                
                points = data.get('test_points', [])
                if points:
                    output += "<b>测试点 (" + str(len(points)) + "个)</b><br>"
                    for p in points:
                        output += "• <b>[" + p.get('priority', 'P2') + "] " + p.get('title', '') + "</b><br>"
                        output += "&nbsp;&nbsp;" + p.get('description', '') + "<br>"
                
                risks = data.get('risks', [])
                if risks:
                    output += "<br><b>风险点 (" + str(len(risks)) + "个)</b><br>"
                    for r in risks:
                        output += "• " + r.get('scenario', '') + "<br>"
                
                questions = data.get('questions', [])
                if questions:
                    output += "<br><b>待确认 (" + str(len(questions)) + "个)</b><br>"
                    for q in questions:
                        output += "• " + q + "<br>"
                
                return {"success": True, "response": output, "thoughts": thoughts}
            except:
                return {"success": True, "response": result, "thoughts": thoughts}
        
        # 生成用例
        elif intent == "generate" and target:
            thoughts.append({"step": "用例生成", "status": "thinking", "content": "正在生成..."})
            
            prompt = """作为资深测试专家，生成测试用例。返回JSON格式:
{"test_cases": [{"id": "TC001", "title": "用例标题", "precondition": "前置条件", "steps": ["步骤1", "步骤2"], "expected": "预期结果", "priority": "P0/P1/P2"}]}

需求: """ + target
            
            result = await asyncio.wait_for(client.complete(prompt), timeout=60)
            
            try:
                clean = result.strip()
                if "```" in clean:
                    clean = clean.split("```")[1].replace("json", "").strip()
                data = json.loads(clean)
                
                thoughts[-1]["status"] = "done"
                thoughts[-1]["content"] = f"生成{len(data.get('test_cases', []))}个用例"
                
                output = "<b>测试用例</b><br><br>"
                for c in data.get('test_cases', []):
                    output += "<b>" + c.get('id', '') + " " + c.get('title', '') + " [" + c.get('priority', 'P2') + "]</b><br>"
                    output += "前置: " + c.get('precondition', '无') + "<br>"
                    output += "步骤:<br>"
                    for i, s in enumerate(c.get('steps', []), 1):
                        output += "&nbsp;&nbsp;" + str(i) + ". " + s + "<br>"
                    output += "预期: " + c.get('expected', '') + "<br><br>"
                
                return {"success": True, "response": output, "thoughts": thoughts}
            except:
                return {"success": True, "response": result, "thoughts": thoughts}
        
        # 普通对话
        else:
            thoughts.append({"step": "生成回复", "status": "done", "content": "思考中..."})
            
            context = "\n".join([m.get("role", "") + ": " + m.get("content", "") for m in history[-5:]])
            prompt = "你是TestOwl，10年资深测试专家。专业严谨务实，善于发现风险。可用功能: 分析xxx、生成用例xxx。\n历史:\n" + context + "\n用户: " + user_msg
            
            result = await asyncio.wait_for(client.complete(prompt), timeout=60)
            return {"success": True, "response": result, "thoughts": thoughts}
    
    except asyncio.TimeoutError:
        return {"success": False, "error": "请求超时", "thoughts": thoughts}
    except Exception as e:
        return {"success": False, "error": str(e), "thoughts": thoughts}
