"""
Agent基类定义

定义所有Agent的基础接口和通用功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import time
import asyncio


@dataclass
class AgentConfig:
    """Agent配置类"""
    # 基础配置
    agent_name: str
    model_name: str
    
    # 服务连接配置
    base_url: Optional[str] = None  # 服务提供商的base_url
    api_key: Optional[str] = None   # API密钥（仅云端服务需要）
    
    # 业务配置
    agent_type: str = "basic"  # 服务提供商类型：ollama, qwen
    role_type: str = "analyst"  # 业务角色类型：conclusion_generator, policy_analyst等
    
    # 可选配置
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    
    # 执行配置
    timeout: int = 60
    
    # 业务数据和提示词模板
    system_prompt: Optional[str] = None
    prompt_template: Optional[str] = None
    business_data: Optional[Dict[str, Any]] = None
    template_data: Optional[Dict[str, Any]] = None  # 模板参数数据
    
    # 自定义参数
    custom_params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}
        if self.business_data is None:
            self.business_data = {}
        if self.template_data is None:
            self.template_data = {}


@dataclass
class AgentRequest:
    """Agent请求对象"""
    prompt: str
    system_prompt: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass  
class AgentResponse:
    """Agent响应对象"""
    content: str
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseAgent(ABC):
    """Agent基类
    
    定义所有Agent必须实现的基本接口，支持不同的LLM服务提供商
    """
    
    def __init__(self, config: AgentConfig, template_data: Optional[Dict[str, Any]] = None):
        """初始化Agent
        
        Args:
            config: Agent配置对象
            template_data: 模板参数数据（可选）
        """
        self.config = config
        # 初始化模板参数数据
        if template_data:
            self.config.template_data.update(template_data)
        self.logger = self._setup_logger()
        self._initialized = False
    
    def _setup_logger(self) -> logging.Logger:
        """设置Agent专用日志器"""
        logger = logging.getLogger(f"Agent.{self.__class__.__name__}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化Agent，建立与LLM服务的连接"""
        pass
    
    @abstractmethod
    def generate(self, request: AgentRequest) -> AgentResponse:
        """同步生成响应
        
        Args:
            request: 请求对象
            
        Returns:
            响应对象
        """
        pass
    
    @abstractmethod
    async def generate_async(self, request: AgentRequest) -> AgentResponse:
        """异步生成响应
        
        Args:
            request: 请求对象
            
        Returns:
            响应对象
        """
        pass
    
    def validate_request(self, request: AgentRequest) -> bool:
        """验证请求是否有效
        
        Args:
            request: 请求对象
            
        Returns:
            是否有效
        """
        if not request.prompt or not request.prompt.strip():
            return False
        return True
    
    def update_template_data(self, data: Dict[str, Any]) -> None:
        """更新模板参数数据
        
        Args:
            data: 要更新的参数数据
        """
        self.config.template_data.update(data)
        self.logger.info(f"已更新模板参数: {list(data.keys())}")
    
    def get_template_data(self) -> Dict[str, Any]:
        """获取当前模板参数数据
        
        Returns:
            模板参数数据副本
        """
        return self.config.template_data.copy()
    
    def clear_template_data(self) -> None:
        """清除所有模板参数数据"""
        self.config.template_data.clear()
        self.logger.info("已清除所有模板参数数据")
    
    def validate_template_params(self, template: Optional[str] = None) -> tuple[bool, List[str]]:
        """验证模板参数是否完整
        
        Args:
            template: 要验证的模板，默认使用prompt_template
            
        Returns:
            (is_valid, missing_params): 是否有效和缺失的参数列表
        """
        import re
        
        if template is None:
            template = self.config.prompt_template
        
        if not template:
            return True, []  # 没有模板则认为有效
        
        # 提取模板中的所有参数
        pattern = r'\{([^}]+)\}'
        required_params = set(re.findall(pattern, template))
        
        # 检查缺失的参数
        current_params = set(self.config.template_data.keys())
        missing_params = list(required_params - current_params)
        
        is_valid = len(missing_params) == 0
        return is_valid, missing_params
    
    def _validate_template_with_data(self, template_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """使用指定的数据验证模板参数
        
        Args:
            template_data: 要验证的模板数据
            
        Returns:
            (is_valid, missing_params): 是否有效和缺失的参数列表
        """
        import re
        
        template = self.config.prompt_template
        if not template:
            return True, []  # 没有模板则认为有效
        
        # 提取模板中的所有参数
        pattern = r'\{([^}]+)\}'
        required_params = set(re.findall(pattern, template))
        
        # 检查缺失的参数
        current_params = set(template_data.keys())
        missing_params = list(required_params - current_params)
        
        is_valid = len(missing_params) == 0
        return is_valid, missing_params
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查
        
        Returns:
            健康状态信息
        """
        try:
            # 执行一个简单的测试请求
            test_request = AgentRequest(prompt="测试连接")
            start_time = time.time()
            response = self.generate(test_request)
            response_time = time.time() - start_time
            
            return {
                "status": "healthy" if response.success else "unhealthy",
                "agent_name": self.config.agent_name,
                "model_name": self.config.model_name,
                "response_time": response_time,
                "error": response.error_message if not response.success else None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "agent_name": self.config.agent_name,
                "model_name": self.config.model_name,
                "error": str(e)
            }
    
    def chat(
        self,
        message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """简单对话接口，使用模板参数渲染提示词
        
        Args:
            message: 用户消息
            additional_data: 额外的模板参数数据
            
        Returns:
            响应结果
        """
        if not self.config.prompt_template:
            # 如果没有模板，直接使用消息
            request = AgentRequest(
                prompt=message,
                system_prompt=self.config.system_prompt
            )
            return self.generate(request)
        
        try:
            # 准备模板数据
            template_data = self.config.template_data.copy()
            template_data['message'] = message  # 添加用户消息
            template_data['question'] = message  # 也支持question参数
            
            # 添加额外数据
            if additional_data:
                template_data.update(additional_data)
            
            # 验证模板参数（使用完整的数据进行验证）
            is_valid, missing_params = self._validate_template_with_data(template_data)
            if not is_valid:
                return AgentResponse(
                    content="",
                    success=False,
                    error_message=f"模板参数不完整，缺少: {', '.join(missing_params)}"
                )
            
            # 渲染模板
            formatted_prompt = self.config.prompt_template.format(**template_data)
            
            # 创建请求
            request = AgentRequest(
                prompt=formatted_prompt,
                system_prompt=self.config.system_prompt,
                context=template_data
            )
            
            return self.generate(request)
            
        except KeyError as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"模板参数错误: {e}"
            )
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"对话失败: {e}"
            )
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息
        
        Returns:
            Agent信息字典
        """
        return {
            "agent_type": self.__class__.__name__,
            "agent_name": self.config.agent_name,
            "model_name": self.config.model_name,
            "role_type": getattr(self.config, 'role_type', 'unknown'),
            "initialized": self._initialized,
            "config": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "top_p": self.config.top_p,
                "timeout": self.config.timeout
            }
        }