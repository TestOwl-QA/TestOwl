"""
RPG/MMO 游戏业务规则

针对角色扮演类游戏的数据库检查规则。

适用表:
    - player/character: 玩家/角色表
    - equipment: 装备表
    - item/inventory: 物品/背包表
    - quest/task: 任务表
    - skill: 技能表
    - guild: 公会表
"""

from typing import List, Optional

from .base import BaseGameRule, RuleCheckResult, RuleSeverity


class CheckPlayerLevelRangeRule(BaseGameRule):
    """检查玩家等级范围是否合理"""
    
    @property
    def name(self) -> str:
        return "玩家等级范围检查"
    
    @property
    def description(self) -> str:
        return "检查玩家等级是否在合理范围内（1-999）"
    
    def applicable_tables(self) -> List[str]:
        return ["player", "character", "hero", "avatar"]
    
    def check(self, connector, table_name: str) -> RuleCheckResult:
        level_column = None
        
        # 检测等级列名
        for col in ["level", "lvl", "player_level", "char_level"]:
            if self.column_exists(connector, table_name, col):
                level_column = col
                break
        
        if not level_column:
            return RuleCheckResult.warning(
                rule_name=self.name,
                message=f"表 {table_name} 未找到等级列",
                table_name=table_name,
                suggestions=["确认等级列命名是否为 level/lvl/player_level/char_level"]
            )
        
        # 检查异常等级
        min_level = self.config.get("min_level", 1)
        max_level = self.config.get("max_level", 999)
        
        result = connector.execute_query(
            f"SELECT COUNT(*) as cnt FROM {table_name} "
            f"WHERE {level_column} < {min_level} OR {level_column} > {max_level}"
        )
        
        abnormal_count = result[0].get("cnt", 0)
        
        if abnormal_count > 0:
            # 获取具体异常数据
            details = connector.execute_query(
                f"SELECT id, {level_column} FROM {table_name} "
                f"WHERE {level_column} < {min_level} OR {level_column} > {max_level} "
                f"LIMIT 10"
            )
            
            return RuleCheckResult.failure(
                rule_name=self.name,
                message=f"发现 {abnormal_count} 条异常等级记录",
                severity=RuleSeverity.ERROR,
                table_name=table_name,
                details={"abnormal_records": details, "level_column": level_column},
                suggestions=[
                    f"检查等级列 {level_column} 的数据合法性",
                    "确认等级上限配置是否正确",
                    "修复异常数据或调整等级上限"
                ]
            )
        
        return RuleCheckResult.success(
            rule_name=self.name,
            message=f"所有玩家等级在合理范围内 ({min_level}-{max_level})",
            table_name=table_name
        )


class CheckEquipmentEnhanceLevelRule(BaseGameRule):
    """检查装备强化等级是否越界"""
    
    @property
    def name(self) -> str:
        return "装备强化等级检查"
    
    @property
    def description(self) -> str:
        return "检查装备强化等级是否超过上限"
    
    def applicable_tables(self) -> List[str]:
        return ["equipment", "equip", "item"]
    
    def check(self, connector, table_name: str) -> RuleCheckResult:
        # 检测强化等级列
        enhance_col = None
        for col in ["enhance_level", "enhance_lvl", "strengthen_level", "refine_level"]:
            if self.column_exists(connector, table_name, col):
                enhance_col = col
                break
        
        if not enhance_col:
            return RuleCheckResult.success(
                rule_name=self.name,
                message=f"表 {table_name} 无强化等级列，跳过检查",
                table_name=table_name
            )
        
        # 检测最大强化等级列
        max_enhance_col = None
        for col in ["max_enhance_level", "max_enhance", "enhance_limit"]:
            if self.column_exists(connector, table_name, col):
                max_enhance_col = col
                break
        
        if max_enhance_col:
            # 检查超过上限的记录
            result = connector.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table_name} "
                f"WHERE {enhance_col} > {max_enhance_col}"
            )
        else:
            # 使用默认上限检查
            default_max = self.config.get("default_max_enhance", 15)
            result = connector.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table_name} "
                f"WHERE {enhance_col} > {default_max}"
            )
        
        abnormal_count = result[0].get("cnt", 0)
        
        if abnormal_count > 0:
            details = connector.execute_query(
                f"SELECT id, {enhance_col}, {max_enhance_col or 'NULL as max_level'} "
                f"FROM {table_name} WHERE {enhance_col} > {max_enhance_col or default_max} "
                f"LIMIT 10"
            )
            
            return RuleCheckResult.failure(
                rule_name=self.name,
                message=f"发现 {abnormal_count} 条装备强化等级超限记录",
                severity=RuleSeverity.ERROR,
                table_name=table_name,
                details={"abnormal_records": details},
                suggestions=[
                    "检查装备强化逻辑是否存在漏洞",
                    "修复异常强化等级数据",
                    "加强服务器端强化等级校验"
                ]
            )
        
        return RuleCheckResult.success(
            rule_name=self.name,
            message="装备强化等级检查通过",
            table_name=table_name
        )


class CheckQuestStatusTransitionRule(BaseGameRule):
    """检查任务状态流转合法性"""
    
    @property
    def name(self) -> str:
        return "任务状态流转检查"
    
    @property
    def description(self) -> str:
        return "检查任务状态是否符合正常流转逻辑"
    
    def applicable_tables(self) -> List[str]:
        return ["quest", "task", "mission", "player_quest", "player_task"]
    
    def check(self, connector, table_name: str) -> RuleCheckResult:
        # 检测状态列
        status_col = None
        for col in ["status", "quest_status", "task_status", "state"]:
            if self.column_exists(connector, table_name, col):
                status_col = col
                break
        
        if not status_col:
            return RuleCheckResult.success(
                rule_name=self.name,
                message=f"表 {table_name} 无状态列，跳过检查",
                table_name=table_name
            )
        
        issues = []
        
        # 检查1: 非法状态值
        valid_statuses = self.config.get("valid_statuses", [0, 1, 2, 3, "not_started", "in_progress", "completed", "rewarded"])
        
        # 构建状态值检查条件
        if all(isinstance(s, int) for s in valid_statuses):
            # 数字状态
            status_list = ",".join(str(s) for s in valid_statuses)
            result = connector.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table_name} WHERE {status_col} NOT IN ({status_list})"
            )
        else:
            # 字符串状态
            status_list = ",".join(f"'{s}'" for s in valid_statuses)
            result = connector.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table_name} WHERE {status_col} NOT IN ({status_list})"
            )
        
        invalid_count = result[0].get("cnt", 0)
        if invalid_count > 0:
            issues.append(f"发现 {invalid_count} 条非法状态值")
        
        # 检查2: 状态与时间戳一致性
        time_checks = []
        
        if self.column_exists(connector, table_name, "accepted_at"):
            time_checks.append(("accepted_at", [0, "not_started"], f"{status_col} > 0"))
        
        if self.column_exists(connector, table_name, "completed_at"):
            time_checks.append(("completed_at", [0, 1, "not_started", "in_progress"], 
                              f"{status_col} IN (2, 3, 'completed', 'rewarded')"))
        
        for time_col, invalid_statuses, should_have_time in time_checks:
            # 检查应该有完成时间但没有的
            result = connector.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table_name} "
                f"WHERE {should_have_time} AND {time_col} IS NULL"
            )
            count = result[0].get("cnt", 0)
            if count > 0:
                issues.append(f"{count} 条记录状态与时间戳不一致({time_col})")
        
        if issues:
            return RuleCheckResult.failure(
                rule_name=self.name,
                message="; ".join(issues),
                severity=RuleSeverity.ERROR,
                table_name=table_name,
                suggestions=[
                    "检查任务状态机实现逻辑",
                    "修复状态与时间戳不一致的数据",
                    "加强服务器端状态流转校验"
                ]
            )
        
        return RuleCheckResult.success(
            rule_name=self.name,
            message="任务状态流转检查通过",
            table_name=table_name
        )


class CheckInventoryCapacityRule(BaseGameRule):
    """检查背包容量是否超限"""
    
    @property
    def name(self) -> str:
        return "背包容量检查"
    
    @property
    def description(self) -> str:
        return "检查玩家背包物品数量是否超过容量上限"
    
    def applicable_tables(self) -> List[str]:
        return ["inventory", "bag", "backpack", "player_item"]
    
    def check(self, connector, table_name: str) -> RuleCheckResult:
        # 检测玩家ID列
        player_col = None
        for col in ["player_id", "user_id", "char_id", "character_id"]:
            if self.column_exists(connector, table_name, col):
                player_col = col
                break
        
        if not player_col:
            return RuleCheckResult.warning(
                rule_name=self.name,
                message=f"表 {table_name} 未找到玩家ID列",
                table_name=table_name
            )
        
        # 检查是否有容量配置表
        has_capacity_table = self.config.get("capacity_table") is not None
        
        if has_capacity_table:
            # 从配置表读取容量
            capacity_table = self.config["capacity_table"]
            capacity_col = self.config.get("capacity_column", "max_slots")
            
            result = connector.execute_query(
                f"SELECT {player_col}, COUNT(*) as item_count, "
                f"(SELECT {capacity_col} FROM {capacity_table} WHERE {player_col} = inv.{player_col}) as max_slots "
                f"FROM {table_name} inv GROUP BY {player_col} "
                f"HAVING item_count > max_slots"
            )
        else:
            # 使用默认容量
            default_capacity = self.config.get("default_capacity", 100)
            
            result = connector.execute_query(
                f"SELECT {player_col}, COUNT(*) as item_count, {default_capacity} as max_slots "
                f"FROM {table_name} GROUP BY {player_col} "
                f"HAVING item_count > {default_capacity}"
            )
        
        if result:
            return RuleCheckResult.failure(
                rule_name=self.name,
                message=f"发现 {len(result)} 个玩家背包超限",
                severity=RuleSeverity.ERROR,
                table_name=table_name,
                details={"over_limit_players": result[:10]},
                suggestions=[
                    "检查背包扩容逻辑",
                    "修复超容量数据",
                    "加强服务器端容量校验"
                ]
            )
        
        return RuleCheckResult.success(
            rule_name=self.name,
            message="所有玩家背包容量正常",
            table_name=table_name
        )


class CheckGoldBalanceRule(BaseGameRule):
    """检查金币产出消耗平衡"""
    
    @property
    def name(self) -> str:
        return "金币流水平衡检查"
    
    @property
    def description(self) -> str:
        return "检查金币总产出与总消耗是否平衡（允许一定误差）"
    
    def applicable_tables(self) -> List[str]:
        return ["gold_log", "currency_log", "money_log", "resource_log"]
    
    def check(self, connector, table_name: str) -> RuleCheckResult:
        # 检测金额列
        amount_col = None
        for col in ["amount", "delta", "change", "value"]:
            if self.column_exists(connector, table_name, col):
                amount_col = col
                break
        
        if not amount_col:
            return RuleCheckResult.warning(
                rule_name=self.name,
                message=f"表 {table_name} 未找到金额列",
                table_name=table_name
            )
        
        # 计算总产出和总消耗
        result = connector.execute_query(
            f"SELECT "
            f"SUM(CASE WHEN {amount_col} > 0 THEN {amount_col} ELSE 0 END) as total_produce, "
            f"SUM(CASE WHEN {amount_col} < 0 THEN ABS({amount_col}) ELSE 0 END) as total_consume "
            f"FROM {table_name}"
        )
        
        if not result:
            return RuleCheckResult.success(
                rule_name=self.name,
                message="无金币流水数据",
                table_name=table_name
            )
        
        total_produce = result[0].get("total_produce") or 0
        total_consume = result[0].get("total_consume") or 0
        
        # 计算差值比例
        if total_produce > 0:
            diff_ratio = abs(total_produce - total_consume) / total_produce
        else:
            diff_ratio = 0
        
        # 允许的误差阈值
        threshold = self.config.get("balance_threshold", 0.1)  # 默认10%
        
        if diff_ratio > threshold:
            return RuleCheckResult.warning(
                rule_name=self.name,
                message=f"金币流水平衡异常: 产出 {total_produce}, 消耗 {total_consume}, 差值 {diff_ratio*100:.2f}%",
                severity=RuleSeverity.WARNING,
                table_name=table_name,
                details={
                    "total_produce": total_produce,
                    "total_consume": total_consume,
                    "difference": total_produce - total_consume,
                    "difference_ratio": diff_ratio,
                },
                suggestions=[
                    "检查是否存在金币产出漏洞",
                    "分析玩家金币获取/消耗行为",
                    "考虑调整经济系统参数"
                ]
            )
        
        return RuleCheckResult.success(
            rule_name=self.name,
            message=f"金币流水平衡正常 (产出: {total_produce}, 消耗: {total_consume}, 差值: {diff_ratio*100:.2f}%)",
            table_name=table_name
        )


# RPG 规则列表
RPG_RULES = [
    CheckPlayerLevelRangeRule,
    CheckEquipmentEnhanceLevelRule,
    CheckQuestStatusTransitionRule,
    CheckInventoryCapacityRule,
    CheckGoldBalanceRule,
]
