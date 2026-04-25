"""
LLM客户端适配器

统一封装各种大模型API的调用，支持：
- 月之暗面 Kimi
- OpenAI GPT
- 其他兼容OpenAI API的模型
"""

import asyncio
from typing import Any, Dict, List, Optional, AsyncGenerator

import httpx
from openai import AsyncOpenAI

from src.core.config import Config
from src.core.exceptions import LLMError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    LLM客户端
    
    使用示例：
        ```python
        client = LLMClient(config)
        
        # 简单调用
        response = await client.complete("你好")
        
        # 流式调用
        async for chunk in client.complete_stream("你好"):
            print(chunk, end="")
        ```
    """
    
    # 预配置的提供商
    PROVIDERS = {
        "moonshot": {
            "base_url": "https://api.moonshot.cn/v1",
            "model": "kimi-k2.5",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
        "siliconflow": {
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "deepseek-ai/DeepSeek-V2.5",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "model": "anthropic/claude-3.5-sonnet",
        },
    }
    
    def __init__(self, config: Config):
        """
        初始化LLM客户端
        
        Args:
            config: 配置对象
        """
        self.config = config.llm
        
        # 获取提供商配置
        provider_config = self.PROVIDERS.get(self.config.provider, {})
        
        # 确定base_url和model
        base_url = self.config.base_url or provider_config.get("base_url", "")
        model = self.config.model or provider_config.get("model", "")
        
        # 无API密钥时创建空客户端（后续调用会提示）
        if not self.config.api_key:
            logger.warning("LLM API密钥未配置，AI功能将不可用")
            self.client = None
        else:
            # 初始化OpenAI客户端
            self.client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=base_url,
                timeout=self.config.timeout,
            )
        self.model = model
        
        logger.info(f"LLMClient initialized with provider: {self.config.provider}, model: {self.model}")
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        完成一次对话
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
        
        Returns:
            模型回复文本
        
        Raises:
            LLMError: 调用失败
        """
        if self.client is None:
            raise LLMError("LLM API密钥未配置，无法调用AI功能")
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
            )
            
            result = response.choices[0].message.content
            logger.debug(f"LLM response received, length: {len(result)}")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise LLMError(f"API调用失败: {str(e)}")
    
    async def complete_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式完成对话
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
        
        Yields:
            模型回复的文本片段
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM streaming API call failed: {e}")
            raise LLMError(f"流式API调用失败: {str(e)}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        多轮对话
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            temperature: 温度参数
            max_tokens: 最大token数
        
        Returns:
            模型回复文本
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM chat API call failed: {e}")
            raise LLMError(f"对话API调用失败: {str(e)}")