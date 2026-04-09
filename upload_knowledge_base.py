import base64
import os
import sys

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

print("=" * 60)
print("TestOwl 知识库文件上传脚本")
print("=" * 60)
print()

for filename in files:
    filepath = os.path.join(base_path, filename)
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            base64_content = base64.b64encode(content).decode('utf-8')
        
        print(f"✅ {filename}")
        print(f"   文件大小: {len(content)} bytes")
        print(f"   Base64长度: {len(base64_content)} chars")
        print()
        
        # 生成 MCP 调用格式
        print("   请在 CodeMaker 中调用 upload_file 工具，参数如下:")
        print(f"   filename: {filename}")
        print(f"   content_base64: (已生成，长度 {len(base64_content)})")
        print()
        
        # 保存到临时文件
        temp_file = f"upload_{filename}.b64.txt"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(base64_content)
        print(f"   Base64 内容已保存到: {temp_file}")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ 错误 {filename}: {e}")
        print("-" * 60)

print()
print("=" * 60)
print("上传说明:")
print("1. 在 CodeMaker 中调用 upload_file 工具")
print("2. 从对应的 .b64.txt 文件中复制 content_base64 内容")
print("3. 或者使用 analyze_document 工具直接分析本地文件")
print("=" * 60)
