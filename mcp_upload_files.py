#!/usr/bin/env python3
"""
直接调用 TestOwl MCP 服务器的 upload_file 工具上传知识库文件
"""
import base64
import os
import asyncio
import json

# 文件列表
files = [
    '白盒测试基础知识汇总.md',
    '代码检查规范汇总.md',
    '多端互通游戏知识汇总.md',
    '接口测试知识汇总.md',
    '配置表检查规则汇总.md',
    '数据库测试知识汇总.md',
    '性能测试知识汇总.md',
    '知识库资料汇总.md',
    '捉宠游戏测试经验汇总.md'
]

base_path = r'D:\知识库文件'

async def upload_file_via_mcp(filename: str, content_base64: str):
    """生成 MCP 工具调用格式"""
    return {
        "tool": "upload_file",
        "arguments": {
            "filename": filename,
            "content_base64": content_base64
        }
    }

async def main():
    print("=" * 70)
    print("TestOwl 知识库文件 - MCP 上传工具调用生成器")
    print("=" * 70)
    print()
    
    for i, filename in enumerate(files, 1):
        filepath = os.path.join(base_path, filename)
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
                base64_content = base64.b64encode(content).decode('utf-8')
            
            # 生成 MCP 调用
            mcp_call = await upload_file_via_mcp(filename, base64_content)
            
            print(f"【{i}/9】{filename}")
            print(f"   文件大小: {len(content)} bytes")
            print(f"   Base64长度: {len(base64_content)} chars")
            print()
            print("   请在 CodeMaker 中调用 upload_file 工具，参数如下:")
            print(f"   filename: {filename}")
            print()
            print("   content_base64:")
            print(f"   {base64_content[:100]}... (共 {len(base64_content)} 字符)")
            print()
            
            # 保存完整调用到文件
            output_file = f"mcp_call_{i}_{filename}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(mcp_call, f, ensure_ascii=False, indent=2)
            print(f"   完整调用已保存到: {output_file}")
            print("-" * 70)
            print()
            
        except Exception as e:
            print(f"❌ 错误 {filename}: {e}")
            print("-" * 70)
            print()
    
    print("=" * 70)
    print("生成完成!")
    print()
    print("使用方法:")
    print("1. 打开对应的 .json 文件")
    print("2. 复制 content_base64 的值")
    print("3. 在 CodeMaker 中调用 upload_file 工具")
    print("4. 粘贴 filename 和 content_base64")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
