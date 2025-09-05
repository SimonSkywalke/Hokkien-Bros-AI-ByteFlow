"""
智谱AI Agent - 基于智谱AI API的Agent实现

支持智谱AI的GLM系列模型调用
"""

import json
import time
from typing import Dict, Any, Optional, Union
from .base_agent import BaseAgent, AgentConfig, AgentResponse

class ZhipuAgent(BaseAgent):
    """智谱AI Agent实现"""
    
    def __init__(self, config: AgentConfig, template_data: Optional[Dict[str, Any]] = None):
        """初始化智谱AI Agent
        
        Args:
            config: Agent配置
            template_data: 模板数据
        """
        super().__init__(config, template_data)
        self._validate_config()
    
    def _validate_config(self) -> None:
        """验证配置"""
        if not self.config.api_key:
            raise ValueError("智谱AI Agent需要API密钥")
    
    def _build_messages(self, prompt: str) -> list:
        """构建消息列表
        
        Args:
            prompt: 用户提示
            
        Returns:
            消息列表
        """
        messages = []
        
        # 添加系统提示（如果有）
        if self.config.system_prompt:
            messages.append({
                "role": "system",
                "content": self.config.system_prompt
            })
        
        # 添加用户消息
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        return messages
    
    def _call_api(self, messages: list, **kwargs) -> Dict[str, Any]:
        """调用智谱AI API
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            API响应
        """
        try:
            from zai import ZhipuAiClient
            
            # 创建智谱AI客户端
            client = ZhipuAiClient(api_key=self.config.api_key)
            
            # 构建请求参数
            request_params = {
                "model": self.config.model_name,
                "messages": messages
            }
            
            # 添加其他参数
            if self.config.temperature is not None:
                request_params["temperature"] = self.config.temperature
                
            if self.config.max_tokens is not None:
                request_params["max_tokens"] = self.config.max_tokens
                
            if self.config.top_p is not None:
                request_params["top_p"] = self.config.top_p
            
            # 添加自定义参数
            if self.config.custom_params:
                request_params.update(self.config.custom_params)
            
            # 应用kwargs中的参数
            request_params.update(kwargs)
            
            # 调用API
            response = client.chat.completions.create(**request_params)
            return response
            
        except ImportError:
            raise ImportError("请安装zai-sdk: pip install zai-sdk")
        except Exception as e:
            raise Exception(f"调用智谱AI API失败: {str(e)}")
    
    def chat(self, prompt: str, **kwargs) -> AgentResponse:
        """与Agent对话
        
        Args:
            prompt: 用户提示
            **kwargs: 其他参数
            
        Returns:
            Agent响应
        """
        try:
            # 应用模板数据
            formatted_prompt = self._apply_template(prompt)
            
            # 构建消息
            messages = self._build_messages(formatted_prompt)
            
            # 调用API
            response = self._call_api(messages, **kwargs)
            
            # 解析响应
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    return AgentResponse(
                        success=True,
                        content=content,
                        raw_response=str(response),
                        model=self.config.model_name,
                        prompt_tokens=getattr(response, 'usage', {}).get('prompt_tokens', 0),
                        completion_tokens=getattr(response, 'usage', {}).get('completion_tokens', 0)
                    )
            
            # 如果无法解析响应内容
            return AgentResponse(
                success=False,
                content="",
                error_message="无法解析API响应",
                raw_response=str(response)
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                content="",
                error_message=str(e),
                raw_response=""
            )
    
    def stream_chat(self, prompt: str, **kwargs):
        """流式对话（智谱AI暂不支持）"""
        raise NotImplementedError("智谱AI暂不支持流式对话")