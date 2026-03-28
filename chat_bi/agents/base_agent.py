"""
Agent基类模块
定义了所有Agent的通用接口和工具方法
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from loguru import logger
import time
from openai import OpenAI

from config.settings import MODEL_CONFIG


class BaseAgent(ABC):
    """
    所有Agent的抽象基类
    提供LLM调用、日志记录、性能监控等通用功能
    """
    
    def __init__(self, name: str, model_config: Optional[Dict] = None):
        """
        初始化Agent
        
        Args:
            name: Agent名称
            model_config: 模型配置，默认使用全局配置
        """
        self.name = name
        self.model_config = model_config or MODEL_CONFIG
        
        # 初始化OpenAI兼容客户端（用于调用vLLM服务）
        self.client = OpenAI(
            base_url=self.model_config["llm_base_url"],
            api_key="EMPTY"  # vLLM不需要真实API key
        )
        
        logger.info(f"初始化Agent: {name}")
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理输入数据的抽象方法
        所有子类必须实现此方法
        
        Args:
            input_data: 输入数据字典
            
        Returns:
            处理结果字典
        """
        pass
    
    async def call_llm(self, messages: list, temperature: float = None) -> str:
        """
        调用LLM生成回复
        
        Args:
            messages: 对话消息列表
            temperature: 温度参数，控制随机性
            
        Returns:
            模型生成的文本
        """
        start_time = time.time()
        
        try:
            # 调用vLLM服务
            response = self.client.chat.completions.create(
                model=self.model_config.get("llm_model", "default"),
                messages=messages,
                temperature=temperature or self.model_config["temperature"],
                max_tokens=self.model_config["max_tokens"]
            )
            
            result = response.choices[0].message.content
            elapsed = (time.time() - start_time) * 1000
            
            logger.debug(f"Agent {self.name} LLM调用完成，耗时: {elapsed:.2f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Agent {self.name} LLM调用失败: {str(e)}")
            raise
    
    def log_step(self, step_name: str, details: Dict[str, Any] = None):
        """
        记录处理步骤日志
        
        Args:
            step_name: 步骤名称
            details: 详细信息
        """
        log_msg = f"[{self.name}] {step_name}"
        if details:
            log_msg += f": {details}"
        logger.info(log_msg)
    
    def format_prompt(self, template: str, **kwargs) -> str:
        """
        格式化提示词模板
        
        Args:
            template: 模板字符串
            **kwargs: 模板变量
            
        Returns:
            格式化后的提示词
        """
        return template.format(**kwargs)