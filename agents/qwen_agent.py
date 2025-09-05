"""
QwenAgent - 基于通义千问云端服务的Agent实现

直接集成通义千问调用逻辑，使用agents_config.yaml配置
"""

from typing import Dict, Any, Optional
import logging

# 先尝试绝对导入，再尝试相对导入
try:
    from base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
except ImportError:
    try:
        from .base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
    except ImportError as e:
        raise ImportError(f"无法导入BaseAgent模块: {e}")


class QwenAgent(BaseAgent):
    """通义千问 Agent实现
    
    直接集成通义千问调用逻辑，无需依赖外部服务类
    """
    
    def __init__(self, config: AgentConfig, template_data: Optional[Dict[str, Any]] = None):
        """初始化QwenAgent
        
        Args:
            config: Agent配置对象
            template_data: 初始模板参数数据
        """
        super().__init__(config, template_data=template_data)
        self.model = None
        
    def initialize(self) -> None:
        """初始化通义千问服务连接"""
        try:
            self.logger.info(f"初始化QwenAgent: {self.config.agent_name}")
            
            # 加载依赖库
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as e:
                self.logger.error("langchain-openai依赖未安装")
                raise ImportError("请安装langchain-openai依赖: pip install langchain-openai") from e
            
            # 从 Agent 配置中获取参数
            model_name = self.config.model_name
            base_url = self.config.base_url
            api_key = self.config.api_key
            
            # 验证必要参数
            if not model_name:
                raise ValueError("必须配置 model_name")
            if not base_url:
                raise ValueError("必须配置 base_url")
            if not api_key:
                self.logger.error("未设置 DASHSCOPE_API_KEY 环境变量")
                raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")
            
            self.logger.info(f"初始化通义千问服务 - 模型: {model_name}，服务地址: {base_url}")
            
            # 构建参数，只传入用户配置的参数
            kwargs = {
                "model": model_name,
                "base_url": base_url,
                "api_key": api_key,
            }
            
            # 从 Agent 配置中获取可选参数（仅在配置中显式设置时传入）
            if self.config.temperature is not None:
                kwargs["temperature"] = self.config.temperature
            if self.config.max_tokens is not None:
                kwargs["max_tokens"] = self.config.max_tokens
            if self.config.top_p is not None:
                kwargs["top_p"] = self.config.top_p
            if self.config.timeout is not None:
                kwargs["timeout"] = self.config.timeout
            
            # 处理 enable_thinking 参数
            if self.config.custom_params and 'enable_thinking' in self.config.custom_params:
                enable_thinking = self.config.custom_params['enable_thinking']
                # 安全转换为布尔值
                if isinstance(enable_thinking, str):
                    enable_thinking = enable_thinking.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(enable_thinking, bool):
                    pass  # 已经是布尔值
                else:
                    enable_thinking = False
                
                kwargs["extra_body"] = {"enable_thinking": enable_thinking}
            
            # 创建 ChatOpenAI 客户端
            self.model = ChatOpenAI(**kwargs)
            
            self._initialized = True
            self.logger.info("QwenAgent初始化成功")
                
        except Exception as e:
            self.logger.error(f"QwenAgent初始化失败: {e}")
            raise
    
    def generate(self, request: AgentRequest) -> AgentResponse:
        """同步生成响应
        
        Args:
            request: 请求对象
            
        Returns:
            响应对象
        """
        if not self.validate_request(request):
            return AgentResponse(
                content="",
                success=False,
                error_message="无效的请求：提示词不能为空"
            )
        
        try:
            # 确保服务已初始化
            if not self._initialized or not self.model:
                self.initialize()
            
            from langchain_core.messages import HumanMessage, SystemMessage
            
            # 日志截断长提示
            log_prompt = request.prompt[:50] + "..." if len(request.prompt) > 50 else request.prompt
            self.logger.debug(f"通义千问接收提示: {log_prompt}")
            
            # 构建消息列表
            messages = []
            
            # 添加系统提示词
            if request.system_prompt:
                messages.append(SystemMessage(content=request.system_prompt))
            
            # 添加用户提示词
            messages.append(HumanMessage(content=request.prompt))
            
            # 使用流式获取响应（兼容 enable_thinking=True/False）
            full_response = ""
            for chunk in self.model.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                    full_response += content
            
            # 日志截断长响应
            log_result = full_response[:50] + "..." if len(full_response) > 50 else full_response
            self.logger.debug(f"通义千问返回响应: {log_result}")
            
            return AgentResponse(
                content=full_response,
                success=True,
                metadata={
                    "model_name": self.config.model_name,
                    "agent_type": "qwen",
                    "service_type": "cloud",
                    "enable_thinking": self.get_thinking_mode()
                }
            )
            
        except Exception as e:
            self.logger.error(f"通义千问生成失败: {e}")
            return AgentResponse(
                content="",
                success=False,
                error_message=str(e)
            )
    
    async def generate_async(self, request: AgentRequest) -> AgentResponse:
        """异步生成响应（在线程池中运行同步方法）
        
        Args:
            request: 请求对象
            
        Returns:
            响应对象
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, request)
    
    def get_available_models(self) -> list:
        """获取可用的通义千问模型列表
        
        Returns:
            模型列表
        """
        try:
            # 通义千问可用模型列表
            return [
                "qwen-turbo",
                "qwen-plus", 
                "qwen-max",
                "qwen3-0.6b",
                "qwen2.5-72b-instruct",
                "qwen2.5-32b-instruct",
                "qwen2.5-14b-instruct",
                "qwen2.5-7b-instruct"
            ]
        except Exception as e:
            self.logger.error(f"获取通义千问模型列表失败: {e}")
            return []
    
    def set_thinking_mode(self, enabled: bool) -> None:
        """设置思维链模式
        
        Args:
            enabled: 是否启用思维链
        """
        if not self.config.custom_params:
            self.config.custom_params = {}
        
        self.config.custom_params['enable_thinking'] = enabled
        self.logger.info(f"思维链模式已{'启用' if enabled else '禁用'}")
    
    def get_thinking_mode(self) -> bool:
        """获取当前思维链模式状态
        
        Returns:
            是否启用思维链
        """
        if self.config.custom_params and 'enable_thinking' in self.config.custom_params:
            return self.config.custom_params['enable_thinking']
        return False