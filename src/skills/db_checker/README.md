# 数据库检查工具 (DB Checker)

一个通用的数据库测试和表检查工具，支持多种数据库类型和游戏业务规则验证。

## 特性

- **多数据库支持**: MySQL, PostgreSQL, SQLite
- **多种检查类型**: 连接测试、结构检查、数据验证、游戏规则检查
- **游戏类型支持**: RPG、卡牌、休闲、竞技、模拟经营
- **易于扩展**: 模块化设计，方便添加新的数据库连接器和游戏规则

## 快速开始

### 1. 连接测试

```python
from src.skills.db_checker import DBCheckerSkill
from src.core.config import Config

skill = DBCheckerSkill(Config())

# 使用连接字符串
result = await skill.execute({
    "check_type": "connection",
    "connection": {
        "conn_str": "mysql://user:pass@host:3306/db"
    }
})

# 或使用详细配置
result = await skill.execute({
    "check_type": "connection",
    "connection": {
        "db_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "testdb",
        "user": "root",
        "password": "password"
    }
})
```

### 2. 完整检查

```python
result = await skill.execute({
    "check_type": "full",
    "connection": {"conn_str": "sqlite:///game.db"},
    "target_tables": ["players", "items"],
    "game_type": "rpg",
    "rule_config": {"max_level": 100}
})
```

## 检查类型

| 类型 | 说明 |
|------|------|
| `connection` | 仅测试数据库连接 |
| `structure` | 检查表结构、索引、约束 |
| `data_validation` | 验证数据完整性（空值、唯一性、范围等） |
| `game_rules` | 执行游戏业务规则检查 |
| `full` | 执行所有检查 |

## 支持的数据库

| 数据库 | 连接字符串格式 | 依赖 |
|--------|---------------|------|
| MySQL | `mysql://user:pass@host:port/db` | PyMySQL |
| PostgreSQL | `postgres://user:pass@host:port/db` | psycopg2 |
| SQLite | `sqlite:///path/to/db.sqlite` | 内置 |

## 游戏规则类型

### RPG 规则 (`rpg`)
- 玩家等级范围检查
- 装备强化等级上限
- 金币/货币平衡性
- 任务状态一致性

### 卡牌规则 (`card`)
- 卡牌稀有度分布
- 卡包概率验证
- 卡组数量限制
- 抽卡记录完整性

### 休闲规则 (`casual`)
- 关卡解锁顺序
- 分数/星级合理性
- 道具数量上限
- 每日奖励领取记录

### 竞技规则 (`competitive`)
- 段位积分计算
- 匹配历史记录
- 赛季数据一致性
- 排行榜数据验证

### 模拟经营规则 (`simulation`)
- 资源产出/消耗平衡
- 建筑升级依赖
- 订单/交易记录
- 时间戳连续性

## 项目结构

```
src/skills/db_checker/
├── __init__.py          # 导出 DBCheckerSkill
├── skill.py             # 主 Skill 类
├── connectors/          # 数据库连接器
│   ├── base.py          # 抽象基类
│   ├── factory.py       # 工厂模式
│   ├── mysql.py         # MySQL 实现
│   ├── postgres.py      # PostgreSQL 实现
│   └── sqlite.py        # SQLite 实现
└── rules/               # 游戏规则模块
    ├── base.py          # 规则基类
    ├── rpg_rules.py     # RPG 规则
    ├── card_rules.py    # 卡牌规则
    ├── casual_rules.py  # 休闲规则
    ├── competitive_rules.py  # 竞技规则
    └── simulation_rules.py   # 模拟经营规则
```

## 扩展指南

### 添加新的数据库支持

1. 在 `connectors/` 目录创建新的连接器类
2. 继承 `BaseConnector`
3. 在 `factory.py` 中注册

```python
# connectors/oracle.py
from .base import BaseConnector

class OracleConnector(BaseConnector):
    def _get_connection(self):
        import cx_Oracle
        return cx_Oracle.connect(self.user, self.password, f"{self.host}:{self.port}/{self.database}")
    
    def get_tables(self) -> List[str]:
        # 实现获取表列表
        pass
```

### 添加新的游戏规则

1. 在 `rules/` 目录创建新的规则文件
2. 继承 `BaseGameRule`
3. 在 `skill.py` 中加载

```python
# rules/custom_rules.py
from .base import BaseGameRule, RuleCheckResult

class CheckCustomRule(BaseGameRule):
    def check(self, connector, config: Dict[str, Any]) -> RuleCheckResult:
        # 实现检查逻辑
        pass
```

## 依赖安装

```bash
# MySQL 支持
pip install pymysql

# PostgreSQL 支持
pip install psycopg2-binary

# 基础依赖（项目已包含）
pip install pandas numpy
```

## 注意事项

1. **安全性**: 生产环境建议使用只读账号
2. **性能**: 大数据量检查建议指定 `target_tables` 分批执行
3. **连接池**: 当前实现为简单连接，高并发场景建议添加连接池
4. **错误处理**: 所有数据库操作都有异常捕获和详细错误信息

## 示例

详见 `examples/db_checker_example.py`
