"""
Agent模块 - 基于LLM服务提供商的Agent架构

提供统一的Agent接口，支持不同的LLM服务提供商：
- OllamaAgent: 基于Ollama的本地模型服务
- QwenAgent: 基于通义千问的云端模型服务
- ZhipuAgent: 基于智谱AI的云端模型服务
"""

from .base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
from .ollama_agent import OllamaAgent
from .qwen_agent import QwenAgent
from .zhipu_agent import ZhipuAgent
from .agent_factory import AgentFactory

__all__ = [
    'BaseAgent',
    'AgentConfig', 
    'AgentRequest',
    'AgentResponse',
    'OllamaAgent',
    'QwenAgent',
    'ZhipuAgent',
    'AgentFactory'
]

__version__ = '1.0.0'