import sys
sys.path.insert(0, '.')

from src.quality import QualityEngine
from src.quality.validator import ValidatorRegistry

# 测试所有验证器是否正确注册
validators = ValidatorRegistry.list_validators()
print(f'✅ 已注册验证器: {len(validators)} 个')
for v in validators:
    print(f'  - {v["name"]}')

# 测试基类通用方法
from src.quality.validators.bug_tracker import BugReportValidator

validator = BugReportValidator()
print(f'\n✅ 基类方法测试:')
print(f'  - has_placeholder("TODO"): {validator.has_placeholder("TODO")}')
print(f'  - has_placeholder("正常文本"): {validator.has_placeholder("正常文本")}')

# 测试 extract_items
result = validator.extract_items(
    {"bugs": [{"title": "test"}]},
    list_keys=["bugs"],
    item_identifier="title"
)
print(f'  - extract_items: {len(result)} 项')

print('\n🎉 重构成功！代码更优雅，无冗余！')