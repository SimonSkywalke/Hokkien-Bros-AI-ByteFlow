"""
Agent工厂 - 用于创建和管理不同类型的Agent

支持多配置文件驱动的Agent实例化：
- .env文件：固定配置（服务地址、API密钥等）
- 工作流配置文件：业务角色配置如ReportMind.yaml）
"""

import os
import yaml
from typing import Dict, Any, Optional, Type, Union, List
import sys
import re

# 添加当前目录到路径
sys.path.append(os.path.dirname(__file__))

# 先尝试绝对导入，再尝试相对导入
try:
    from base_agent import BaseAgent, AgentConfig
    from ollama_agent import OllamaAgent
    from qwen_agent import QwenAgent
    from zhipu_agent import ZhipuAgent  # 添加智谱AI Agent
    from config_manager import ConfigManager
except ImportError:
    try:
        from .base_agent import BaseAgent, AgentConfig
        from .ollama_agent import OllamaAgent
        from .qwen_agent import QwenAgent
        from .zhipu_agent import ZhipuAgent  # 添加智谱AI Agent
        from .config_manager import ConfigManager
    except ImportError as e:
        raise ImportError(f"无法导入Agent模块: {e}")


class AgentFactory:
    """Agent工厂类
    
    负责创建和管理不同类型的Agent实例，支持多配置源
    """
    
    def __init__(self, workflow_config_files: Optional[List[str]] = None):
        """初始化Agent工厂
        
        Args:
            workflow_config_files: 工作流配置文件路径列表，默认使用ReportMind.yaml
        """
        # 创建配置管理器
        self.config_manager = ConfigManager(workflow_config_files)
        
        # 注册可用的Agent类型
        self._agent_classes: Dict[str, Type[BaseAgent]] = {
            'ollama': OllamaAgent,
            'qwen': QwenAgent,
            'zhipu': ZhipuAgent  # 注册智谱AI Agent
        }
        
        print(f"✅ AgentFactory初始化完成")
        print(f"   服务提供商: {self.config_manager.list_available_providers()}")
        print(f"   可用角色: {self.config_manager.list_available_roles()}")
    
    def register_agent_type(self, agent_type: str, agent_class: Type[BaseAgent]) -> None:
        """注册新的Agent类型
        
        Args:
            agent_type: Agent类型标识
            agent_class: Agent类
        """
        self._agent_classes[agent_type] = agent_class
    
    def list_available_types(self) -> Dict[str, str]:
        """列出所有可用的Agent类型
        
        Returns:
            Agent类型字典 {类型: 类名}
        """
        return {
            agent_type: agent_class.__name__ 
            for agent_type, agent_class in self._agent_classes.items()
        }
    
    def add_workflow_config(self, config_file: str) -> None:
        """添加新的工作流配置文件
        
        Args:
            config_file: 配置文件路径
        """
        self.config_manager.add_workflow_config(config_file)
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息
        
        Returns:
            配置摘要字典
        """
        return self.config_manager.get_config_summary()
    
    def create_role_agent(
        self,
        service_type: str,
        role_name: str,
        template_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> BaseAgent:
        """创建Role Agent实例
        
        Args:
            service_type: 服务类型 ('ollama' 或 'qwen')
            role_name: 角色名称 (如 'policy_analyst', 'market_researcher')
            template_data: 初始模板参数数据
            **kwargs: 额外配置参数
            
        Returns:
            创建的Agent实例
            
        Raises:
            ValueError: 不支持的服务类型或角色
            Exception: 创建失败
        """
        if service_type not in self._agent_classes:
            raise ValueError(
                f"不支持的服务类型: {service_type}. "
                f"可用类型: {list(self._agent_classes.keys())}"
            )
        
        # 获取服务提供商配置
        service_provider = self.config_manager.get_service_provider(service_type)
        if not service_provider:
            raise ValueError(f"未找到服务类型 '{service_type}' 的配置")
        
        # 获取角色配置
        role_config = self.config_manager.get_role_config(role_name)
        if not role_config:
            available_roles = self.config_manager.list_available_roles()
            raise ValueError(f"角色配置不存在: {role_name}. 可用角色: {available_roles}")
        
        # 构建 Agent 配置（优先使用角色级别的参数）
        config_params = {
            'agent_name': role_config.get('name', role_name),
            'model_name': service_provider.default_model,
            'agent_type': service_type,
            'role_type': role_name,
            'system_prompt': role_config.get('system_prompt', ''),
            'prompt_template': role_config.get('prompt_template', '{question}'),
            'base_url': service_provider.base_url
        }
        
        # 添加 API 密钥（如果存在）
        if service_provider.api_key:
            config_params['api_key'] = service_provider.api_key
        
        # 添加角色级别的定制化参数（仅在角色配置中定义时使用）
        for param in ['temperature', 'max_tokens', 'top_p', 'timeout']:
            if param in role_config:
                config_params[param] = role_config[param]
        
        # 处理自定义参数（仅在角色配置中定义时使用）
        if 'custom_params' in role_config:
            config_params['custom_params'] = role_config['custom_params']
        
        # 应用额外参数
        config_params.update(kwargs)
        
        try:
            # 创建配置对象
            agent_config = AgentConfig(**config_params)
            
            # 创建Agent实例，传入模板参数
            agent_class = self._agent_classes[service_type]
            agent = agent_class(agent_config, template_data=template_data)
            
            return agent
            
        except Exception as e:
            raise Exception(f"创建{service_type} {role_name} Agent失败: {e}")
    
    def create_agent(
        self, 
        agent_type: str,
        agent_name: Optional[str] = None,
        model_name: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> BaseAgent:
        """创建Agent实例
        
        Args:
            agent_type: Agent类型 ('ollama' 或 'qwen')
            agent_name: Agent名称
            model_name: 模型名称
            config_override: 配置覆盖参数
            **kwargs: 其他配置参数
            
        Returns:
            创建的Agent实例
            
        Raises:
            ValueError: 不支持的Agent类型
            Exception: 创建失败
        """
        if agent_type not in self._agent_classes:
            raise ValueError(
                f"不支持的Agent类型: {agent_type}. "
                f"可用类型: {list(self._agent_classes.keys())}"
            )
        
        # 获取服务提供商配置
        service_provider = self.config_manager.get_service_provider(agent_type)
        if not service_provider:
            raise ValueError(f"未找到服务类型 '{agent_type}' 的配置")
        
        # 构建配置参数
        config_params = {
            'agent_name': agent_name or f"{agent_type}_agent",
            'model_name': model_name or service_provider.default_model,
            'agent_type': agent_type,
            'role_type': 'default',
            'base_url': service_provider.base_url
        }
        
        # 添加 API 密钥（如果存在）
        if service_provider.api_key:
            config_params['api_key'] = service_provider.api_key
        
        # 应用配置覆盖
        if config_override:
            config_params.update(config_override)
        
        # 应用额外参数
        config_params.update(kwargs)
        
        try:
            # 创建配置对象
            agent_config = AgentConfig(**config_params)
            
            # 创建Agent实例
            agent_class = self._agent_classes[agent_type]
            agent = agent_class(agent_config)
            
            return agent
            
        except Exception as e:
            raise Exception(f"创建{agent_type} Agent失败: {e}")