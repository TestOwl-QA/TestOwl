"""
GameTestAgent 主类

Agent的核心协调器，负责管理技能、处理请求、协调各模块工作
"""

import asyncio
from typing import Any, Dict, List, Optional, Type, Callable
from dataclasses import dataclass
from enum import Enum

from src.core.config import Config, get_config
from src.core.exceptions import GameTestAgentError, SkillError
from src.skills.base import BaseSkill, SkillContext, SkillResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 运行中
    ERROR = "error"         # 错误
    STOPPED = "stopped"     # 已停止


@dataclass
class AgentContext:
    """Agent上下文"""
    request_id: str
    user_input: str
    metadata: Dict[str, Any]
    history: List[Dict[str, Any]]


class GameTestAgent:
    """
    游戏测试Agent主类
    
    使用示例：
        ```python
        agent = GameTestAgent()
        
        # 分析需求文档
        result = await agent.execute(
            skill_name="document_analyzer",
            params={"file_path": "需求文档.docx"}
        )
        
        # 生成测试用例
        result = await agent.execute(
            skill_name="test_case_generator",
            params={"requirements": result.data}
        )
        ```
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化Agent
        
        Args:
            config: 配置对象，默认使用全局配置
        """
        self.config = config or get_config()
        self.config.validate()
        
        self.status = AgentStatus.IDLE
        self._skills: Dict[str, BaseSkill] = {}
        self._hooks: Dict[str, List[Callable]] = {
            "before_execute": [],
            "after_execute": [],
            "on_error": [],
        }
        
        logger.info("GameTestAgent initialized")
    
    def register_skill(self, name: str, skill: BaseSkill) -> "GameTestAgent":
        """
        注册技能
        
        Args:
            name: 技能名称
            skill: 技能实例
        
        Returns:
            self，支持链式调用
        """
        if name in self._skills:
            logger.warning(f"Skill '{name}' already registered, will be overwritten")
        
        self._skills[name] = skill
        logger.info(f"Skill '{name}' registered")
        
        return self
    
    def register_skill_class(self, name: str, skill_class: Type[BaseSkill]) -> "GameTestAgent":
        """
        通过类注册技能（自动实例化）
        
        Args:
            name: 技能名称
            skill_class: 技能类
        
        Returns:
            self，支持链式调用
        """
        skill = skill_class(self.config)
        return self.register_skill(name, skill)
    
    def unregister_skill(self, name: str) -> "GameTestAgent":
        """
        注销技能
        
        Args:
            name: 技能名称
        
        Returns:
            self，支持链式调用
        """
        if name in self._skills:
            del self._skills[name]
            logger.info(f"Skill '{name}' unregistered")
        
        return self
    
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        获取技能
        
        Args:
            name: 技能名称
        
        Returns:
            技能实例，不存在返回None
        """
        return self._skills.get(name)
    
    def list_skills(self) -> List[str]:
        """
        列出所有已注册技能
        
        Returns:
            技能名称列表
        """
        return list(self._skills.keys())
    
    def add_hook(self, event: str, callback: Callable) -> "GameTestAgent":
        """
        添加事件钩子
        
        Args:
            event: 事件名称（before_execute, after_execute, on_error）
            callback: 回调函数
        
        Returns:
            self，支持链式调用
        """
        if event in self._hooks:
            self._hooks[event].append(callback)
        
        return self
    
    async def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: Optional[SkillContext] = None
    ) -> SkillResult:
        """
        执行技能
        
        Args:
            skill_name: 技能名称
            params: 技能参数
            context: 技能上下文
        
        Returns:
            技能执行结果
        
        Raises:
            SkillError: 技能不存在或执行失败
        """
        # 检查技能是否存在
        skill = self._skills.get(skill_name)
        if not skill:
            raise SkillError(skill_name, f"Skill '{skill_name}' not found")
        
        # 创建上下文
        if context is None:
            context = SkillContext(
                agent=self,
                config=self.config,
                params=params,
            )
        
        # 执行前钩子
        for hook in self._hooks["before_execute"]:
            try:
                await hook(skill_name, params, context)
            except Exception as e:
                logger.warning(f"Before execute hook failed: {e}")
        
        self.status = AgentStatus.RUNNING
        logger.info(f"Executing skill '{skill_name}'")
        
        try:
            # 执行技能
            result = await skill.execute(context)
            
            # 执行后钩子
            for hook in self._hooks["after_execute"]:
                try:
                    await hook(skill_name, result, context)
                except Exception as e:
                    logger.warning(f"After execute hook failed: {e}")
            
            self.status = AgentStatus.IDLE
            logger.info(f"Skill '{skill_name}' executed successfully")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"Skill '{skill_name}' execution failed: {e}")
            
            # 错误钩子
            for hook in self._hooks["on_error"]:
                try:
                    await hook(skill_name, e, context)
                except Exception as hook_e:
                    logger.warning(f"Error hook failed: {hook_e}")
            
            raise SkillError(skill_name, str(e))
    
    async def execute_pipeline(
        self,
        steps: List[Dict[str, Any]]
    ) -> List[SkillResult]:
        """
        执行技能流水线
        
        Args:
            steps: 步骤列表，每个步骤包含 skill_name 和 params
                例如：[
                    {"skill_name": "document_analyzer", "params": {...}},
                    {"skill_name": "test_case_generator", "params": {...}},
                ]
        
        Returns:
            各步骤执行结果列表
        """
        results = []
        
        for step in steps:
            skill_name = step["skill_name"]
            params = step.get("params", {})
            
            # 上一步的结果可以作为参数
            if results and "use_previous_result" in step:
                prev_result = results[-1]
                if prev_result.success:
                    params["previous_result"] = prev_result.data
            
            result = await self.execute(skill_name, params)
            results.append(result)
            
            # 如果某一步失败，停止流水线
            if not result.success:
                logger.error(f"Pipeline stopped at step '{skill_name}'")
                break
        
        return results
    
    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        对话接口（简化使用）
        
        Args:
            message: 用户消息
            context: 额外上下文
        
        Returns:
            Agent回复
        """
        # 简单的意图识别，路由到对应技能
        intent = self._detect_intent(message)
        
        if intent["skill"]:
            try:
                result = await self.execute(
                    skill_name=intent["skill"],
                    params=intent["params"]
                )
                
                if result.success:
                    return self._format_response(result)
                else:
                    return f"执行失败：{result.error}"
                    
            except Exception as e:
                return f"发生错误：{str(e)}"
        
        return "我不太理解您的需求，请尝试描述您想要：\n1. 分析需求文档\n2. 生成测试用例\n3. 检查数据表\n4. 分析Bug"
    
    def _detect_intent(self, message: str) -> Dict[str, Any]:
        """
        检测用户意图
        
        Args:
            message: 用户消息
        
        Returns:
            意图识别结果，包含 skill 和 params
        """
        message_lower = message.lower()
        
        # 文档分析意图
        if any(kw in message_lower for kw in ["分析文档", "解析需求", "文档", "需求"]):
            return {
                "skill": "document_analyzer",
                "params": {"query": message}
            }
        
        # 测试用例生成意图
        if any(kw in message_lower for kw in ["生成用例", "测试用例", "用例", "测试点"]):
            return {
                "skill": "test_case_generator",
                "params": {"query": message}
            }
        
        # 表检查意图
        if any(kw in message_lower for kw in ["检查表", "表检查", "数据检查", "配置检查"]):
            return {
                "skill": "table_checker",
                "params": {"query": message}
            }
        
        # Bug分析意图
        if any(kw in message_lower for kw in ["bug", "缺陷", "问题分析", "提交bug"]):
            return {
                "skill": "bug_tracker",
                "params": {"query": message}
            }
        
        return {"skill": None, "params": {}}
    
    def _format_response(self, result: SkillResult) -> str:
        """
        格式化响应
        
        Args:
            result: 技能执行结果
        
        Returns:
            格式化后的字符串
        """
        if isinstance(result.data, str):
            return result.data
        
        if isinstance(result.data, dict):
            if "summary" in result.data:
                return result.data["summary"]
            if "message" in result.data:
                return result.data["message"]
        
        return str(result.data)
    
    async def start(self):
        """启动Agent"""
        self.status = AgentStatus.IDLE
        logger.info("GameTestAgent started")
    
    async def stop(self):
        """停止Agent"""
        self.status = AgentStatus.STOPPED
        logger.info("GameTestAgent stopped")
