"""
OllamaAgent - 基于Ollama本地模型服务的Agent实现

直接集成Ollama调用逻辑，使用agents_config.yaml配置
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


class OllamaAgent(BaseAgent):
    """Ollama Agent实现
    
    直接集成Ollama调用逻辑，无需依赖外部服务类
    """
    
    def __init__(self, config: AgentConfig, template_data: Optional[Dict[str, Any]] = None):
        """初始化OllamaAgent
        
        Args:
            config: Agent配置对象
            template_data: 初始模板参数数据
        """
        super().__init__(config, template_data=template_data)
        self.model = None
        
    def initialize(self) -> None:
        """初始化Ollama服务连接"""
        try:
            self.logger.info(f"初始化OllamaAgent: {self.config.agent_name}")
            
            # 加载依赖库
            try:
                from langchain_ollama import OllamaLLM
            except ImportError as e:
                self.logger.error("langchain-ollama依赖未安装")
                raise ImportError("请安装langchain-ollama依赖: pip install langchain-ollama") from e
            
            # 从 Agent 配置中获取参数
            model_name = self.config.model_name
            base_url = self.config.base_url
            
            # 验证必要参数
            if not model_name:
                raise ValueError("必须配置 model_name")
            if not base_url:
                raise ValueError("必须配置 base_url")
            
            self.logger.info(f"初始化Ollama服务 - 模型: {model_name}，服务地址: {base_url}")
            
            # 构建参数，只传入用户配置的参数
            kwargs = {
                "model": model_name,
                "base_url": base_url,
            }
            
            # 从 Agent 配置中获取可选参数（仅在配置中显式设置时传入）
            if self.config.temperature is not None:
                kwargs["temperature"] = self.config.temperature
            if self.config.max_tokens is not None:
                kwargs["max_tokens"] = self.config.max_tokens
            if self.config.top_p is not None:
                kwargs["top_p"] = self.config.top_p
            
            # 创建 Ollama 客户端
            self.model = OllamaLLM(**kwargs)
            
            self._initialized = True
            self.logger.info("OllamaAgent初始化成功")
                
        except Exception as e:
            self.logger.error(f"OllamaAgent初始化失败: {e}")
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
            
            # 日志截断长提示
            log_prompt = request.prompt[:50] + "..." if len(request.prompt) > 50 else request.prompt
            self.logger.debug(f"Ollama接收提示: {log_prompt}")
            
            # 调用Ollama模型
            result = self.model.invoke(request.prompt)
            
            # 处理不同格式的响应
            if isinstance(result, str):
                content = result
            elif hasattr(result, 'content'):
                content = result.content
            else:
                content = str(result)
            
            # 日志截断长响应
            log_result = content[:50] + "..." if len(content) > 50 else content
            self.logger.debug(f"Ollama返回响应: {log_result}")
            
            return AgentResponse(
                content=content,
                success=True,
                metadata={
                    "model_name": self.config.model_name,
                    "agent_type": "ollama",
                    "service_type": "local"
                }
            )
            
        except Exception as e:
            self.logger.error(f"Ollama生成失败: {e}")
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
        """获取可用的Ollama模型列表
        
        Returns:
            模型列表
        """
        try:
            # 返回一个示例列表，实际情况下可以通过API获取
            return [
                "deepseek-r1:32b",
                "llama3.1:8b", 
                "qwen2.5:7b",
                "mixtral:8x7b"
            ]
        except Exception as e:
            self.logger.error(f"获取Ollama模型列表失败: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Ollama Agent健康检查
        
        Returns:
            健康状态信息
        """
        base_health = super().health_check()
        
        # 添加Ollama特定的健康信息
        try:
            available_models = self.get_available_models()
            base_health.update({
                "service_type": "ollama",
                "available_models_count": len(available_models),
                "sample_models": available_models[:3] if available_models else []
            })
        except Exception as e:
            base_health.update({
                "service_type": "ollama",
                "model_check_error": str(e)
            })
        
        return base_health