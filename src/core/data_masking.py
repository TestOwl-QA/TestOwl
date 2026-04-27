"""
数据脱敏模块 - 自动识别并替换敏感信息
"""
import re
from typing import Dict, List, Tuple

class DataMasker:
    """数据脱敏器"""
    
    # 默认脱敏规则
    DEFAULT_RULES = {
        # IP地址
        'ip': {
            'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'replacement': '[IP]',
            'description': 'IP地址'
        },
        # 端口号（紧跟IP或单独出现）
        'port': {
            'pattern': r':(\d{2,5})\b',
            'replacement': ':[PORT]',
            'description': '端口号'
        },
        # 手机号
        'phone': {
            'pattern': r'1[3-9]\d{9}',
            'replacement': '[PHONE]',
            'description': '手机号'
        },
        # 邮箱
        'email': {
            'pattern': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'replacement': '[EMAIL]',
            'description': '邮箱'
        },
        # 玩家ID（各种常见格式）
        'player_id': {
            'pattern': r'(?:player[_-]?id|uid|user[_-]?id)["\']?\s*[:=]\s*["\']?(\w+)',
            'replacement': lambda m: m.group(0).replace(m.group(1), '[PLAYER_ID]'),
            'description': '玩家ID'
        },
        # 服务器名称（特定格式）
        'server_name': {
            'pattern': r'(?:server|svr|s)[_-]?(?:name|id)?["\']?\s*[:=]\s*["\']?([\w-]+)',
            'replacement': lambda m: m.group(0).replace(m.group(1), '[SERVER]'),
            'description': '服务器标识'
        },
        # 密钥/Token（简单检测）
        'secret': {
            'pattern': r'(?:api[_-]?key|token|secret|password)["\']?\s*[:=]\s*["\']?([\w-]{8,})',
            'replacement': lambda m: m.group(0).replace(m.group(1), '[SECRET]'),
            'description': '密钥/Token'
        },
        # 路径中的用户名
        'username_in_path': {
            'pattern': r'/home/(\w+)/|/Users/(\w+)/|C:\\\\Users\\\\(\w+)',
            'replacement': lambda m: m.group(0).replace(m.group(1) or m.group(2) or m.group(3), '[USER]'),
            'description': '用户名'
        },
        # 数值（游戏数值脱敏）
        'game_value': {
            'pattern': r'(?:damage|atk|def|hp|price|cost|reward)["\']?\s*[:=]\s*(\d+)',
            'replacement': lambda m: m.group(0).replace(m.group(1), '[NUM]'),
            'description': '游戏数值'
        },
    }
    
    def __init__(self, custom_rules: Dict = None):
        """
        初始化脱敏器
        
        Args:
            custom_rules: 自定义脱敏规则，会覆盖默认规则
        """
        self.rules = self.DEFAULT_RULES.copy()
        if custom_rules:
            self.rules.update(custom_rules)
        
        # 记录脱敏映射（用于可能的还原）
        self.mask_map: Dict[str, str] = {}
        self.counter = 0
    
    def mask(self, text: str) -> Tuple[str, List[Dict]]:
        """
        对文本进行脱敏处理
        
        Args:
            text: 原始文本
            
        Returns:
            (脱敏后文本, 脱敏记录列表)
        """
        if not text:
            return text, []
        
        masked_text = text
        records = []
        
        for rule_name, rule in self.rules.items():
            pattern = rule['pattern']
            replacement = rule['replacement']
            
            def replace_match(match):
                self.counter += 1
                mask_id = f"[MASK_{self.counter}]"
                original = match.group(0)
                
                # 处理lambda或字符串替换
                if callable(replacement):
                    masked = replacement(match)
                else:
                    masked = re.sub(pattern, replacement, original)
                
                self.mask_map[mask_id] = original
                records.append({
                    'id': mask_id,
                    'rule': rule_name,
                    'description': rule['description'],
                    'original': original,
                    'masked': masked
                })
                return masked
            
            masked_text = re.sub(pattern, replace_match, masked_text)
        
        return masked_text, records
    
    def unmask(self, text: str) -> str:
        """
        将脱敏后的文本还原（尽可能）
        
        Args:
            text: 脱敏后的文本
            
        Returns:
            还原后的文本
        """
        result = text
        for mask_id, original in self.mask_map.items():
            result = result.replace(mask_id, original)
        return result
    
    def get_mask_summary(self) -> str:
        """获取脱敏摘要"""
        if not self.mask_map:
            return "未进行脱敏处理"
        
        rule_counts = {}
        for record in self.get_records():
            rule = record['rule']
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
        
        lines = ["脱敏摘要："]
        for rule, count in sorted(rule_counts.items()):
            desc = self.rules.get(rule, {}).get('description', rule)
            lines.append(f"  - {desc}: {count}处")
        return "\n".join(lines)
    
    def get_records(self) -> List[Dict]:
        """获取所有脱敏记录"""
        return [
            {'id': k, 'original': v}
            for k, v in self.mask_map.items()
        ]


# 便捷函数
def mask_text(text: str) -> Tuple[str, List[Dict]]:
    """快速脱敏函数"""
    masker = DataMasker()
    return masker.mask(text)


def mask_for_bug_analysis(text: str) -> Tuple[str, List[Dict]]:
    """
    专为报错分析优化的脱敏
    保留错误类型、类名、方法名，只脱敏敏感数据
    """
    # 针对报错分析的特定规则
    rules = {
        'ip': DataMasker.DEFAULT_RULES['ip'],
        'phone': DataMasker.DEFAULT_RULES['phone'],
        'email': DataMasker.DEFAULT_RULES['email'],
        'player_id': DataMasker.DEFAULT_RULES['player_id'],
        'secret': DataMasker.DEFAULT_RULES['secret'],
        # 保留路径结构，只脱敏用户名
        'username_in_path': DataMasker.DEFAULT_RULES['username_in_path'],
    }
    
    masker = DataMasker(rules)
    return masker.mask(text)


def mask_for_table_check(text: str) -> Tuple[str, List[Dict]]:
    """
    专为配置表检查优化的脱敏
    保留表结构、字段名，脱敏具体数值
    """
    # 针对配置表的特定规则
    rules = {
        # 只脱敏看起来像ID的长数字
        'long_id': {
            'pattern': r'\b\d{10,}\b',
            'replacement': '[ID]',
            'description': '长ID'
        },
        # 脱敏大数值（可能是游戏数值）
        'large_number': {
            'pattern': r'\b\d{5,}\b',
            'replacement': '[NUM]',
            'description': '大数值'
        },
        # 脱敏特定字段的值
        'sensitive_field': {
            'pattern': r'(?:password|secret|token|key)["\']?\s*[:=]\s*["\']?([^,}\s]+)',
            'replacement': lambda m: m.group(0).replace(m.group(1), '[SECRET]'),
            'description': '敏感字段值'
        },
    }
    
    masker = DataMasker(rules)
    return masker.mask(text)
