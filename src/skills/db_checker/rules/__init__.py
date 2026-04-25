"""
游戏类型业务规则模块

提供针对不同游戏类型的数据库业务规则检查。

设计原则:
    1. 可扩展: 新增游戏类型只需添加新模块
    2. 可复用: 通用规则可在不同游戏类型间共享
    3. 可配置: 规则参数可通过配置调整

支持的类型:
    - rpg: RPG/MMO 游戏（角色、装备、任务等）
    - card: 卡牌/SLG 游戏（抽卡、卡牌、资源等）
    - casual: 休闲游戏（关卡、广告、成就等）
    - competitive: 竞技游戏（对战、赛季、排行榜等）
    - simulation: 模拟经营（建造、生产、订单等）

使用示例:
    from src.skills.db_checker.rules import get_game_rules
    
    # 获取 RPG 游戏规则
    rules = get_game_rules("rpg")
    
    # 执行检查
    for rule in rules:
        result = rule.check(connector, table_name)
        print(result)
"""

from typing import List, Type, Optional
from .base import BaseGameRule, RuleCheckResult

# 延迟导入具体规则模块
def _import_rules():
    """动态导入规则模块"""
    rules_map = {}
    
    try:
        from . import rpg_rules
        rules_map["rpg"] = rpg_rules.RPG_RULES
    except ImportError:
        pass
    
    try:
        from . import card_rules
        rules_map["card"] = card_rules.CARD_RULES
    except ImportError:
        pass
    
    try:
        from . import casual_rules
        rules_map["casual"] = casual_rules.CASUAL_RULES
    except ImportError:
        pass
    
    try:
        from . import competitive_rules
        rules_map["competitive"] = competitive_rules.COMPETITIVE_RULES
    except ImportError:
        pass
    
    try:
        from . import simulation_rules
        rules_map["simulation"] = simulation_rules.SIMULATION_RULES
    except ImportError:
        pass
    
    return rules_map


# 缓存规则映射
_rules_cache = None


def get_game_rules(game_type: str) -> List[Type[BaseGameRule]]:
    """
    获取指定游戏类型的规则列表
    
    Args:
        game_type: 游戏类型标识 (rpg/card/casual/competitive/simulation)
    
    Returns:
        规则类列表
    """
    global _rules_cache
    
    if _rules_cache is None:
        _rules_cache = _import_rules()
    
    return _rules_cache.get(game_type.lower(), [])


def list_supported_types() -> List[str]:
    """列出支持的游戏类型"""
    global _rules_cache
    
    if _rules_cache is None:
        _rules_cache = _import_rules()
    
    return list(_rules_cache.keys())


def detect_game_type(table_names: List[str]) -> Optional[str]:
    """
    根据表名推测游戏类型
    
    Args:
        table_names: 数据库中的表名列表
    
    Returns:
        推测的游戏类型，无法确定时返回 None
    """
    table_names_lower = [t.lower() for t in table_names]
    
    # RPG 特征表
    rpg_indicators = ["player", "character", "equipment", "quest", "task", "guild", "inventory", "skill"]
    rpg_score = sum(1 for t in rpg_indicators if any(t in name for name in table_names_lower))
    
    # 卡牌特征表
    card_indicators = ["card", "gacha", "deck", "draw", "pack"]
    card_score = sum(1 for t in card_indicators if any(t in name for name in table_names_lower))
    
    # 休闲特征表
    casual_indicators = ["level", "stage", "ad", "advertisement", "achievement", "star"]
    casual_score = sum(1 for t in casual_indicators if any(t in name for name in table_names_lower))
    
    # 竞技特征表
    competitive_indicators = ["match", "battle", "rank", "season", "leaderboard", "arena"]
    competitive_score = sum(1 for t in competitive_indicators if any(t in name for name in table_names_lower))
    
    # 模拟经营特征表
    simulation_indicators = ["building", "production", "order", "trade", "farm", "factory"]
    simulation_score = sum(1 for t in simulation_indicators if any(t in name for name in table_names_lower))
    
    scores = {
        "rpg": rpg_score,
        "card": card_score,
        "casual": casual_score,
        "competitive": competitive_score,
        "simulation": simulation_score,
    }
    
    best_match = max(scores, key=scores.get)
    
    # 只有当分数超过阈值才返回
    if scores[best_match] >= 2:
        return best_match
    
    return None


__all__ = [
    "BaseGameRule",
    "RuleCheckResult",
    "get_game_rules",
    "list_supported_types",
    "detect_game_type",
]
