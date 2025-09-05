"""
配置管理器 - 支持多配置文件和环境变量的配置管理

支持以下配置源：
1. .env文件 - 固定配置（服务地址、API密钥等）
2. 工作流配置文件 - 业务角色配置（如ReportMind.yaml）
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ServiceProviderConfig:
    """服务提供商配置"""
    base_url: str
    default_model: str
    api_key: Optional[str] = None


class ConfigManager:
    """配置管理器
    
    负责加载和管理多个配置源：
    - .env文件（固定配置）
    - 工作流配置文件（业务配置）
    """
    
    def __init__(self, workflow_config_files: Optional[List[str]] = None):
        """初始化配置管理器
        
        Args:
            workflow_config_files: 工作流配置文件路径列表，默认使用ReportMind.yaml
        """
        self.env_config = {}
        self.workflow_config = {}
        self.service_providers = {}
        
        # 设置默认配置文件
        if workflow_config_files is None:
            # 使用当前目录下的workflow.yaml
            default_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'workflow.yaml')
            print(f"🔍 默认配置文件路径: {default_config}")
            workflow_config_files = [default_config]
        
        self.workflow_config_files = workflow_config_files
        
        # 加载所有配置
        self._load_env_config()
        self._load_workflow_configs()
        self._build_service_providers()
    
    def _load_env_config(self) -> None:
        """加载.env文件配置"""
        try:
            # 尝试加载python-dotenv
            try:
                from dotenv import load_dotenv
                env_file = os.path.join(os.path.dirname(__file__), '.env')
                if os.path.exists(env_file):
                    load_dotenv(env_file)
                    print(f"✅ 已加载.env文件: {env_file}")
                else:
                    print(f"⚠️ .env文件不存在: {env_file}")
            except ImportError:
                print("⚠️ python-dotenv未安装，将从系统环境变量读取配置")
            
            # 读取环境变量（仅服务连接相关的固定配置）
            self.env_config = {
                'ollama_base_url': os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
                'ollama_default_model': os.getenv('OLLAMA_DEFAULT_MODEL', 'deepseek-r1:32b'),
                'qwen_base_url': os.getenv('QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                'qwen_default_model': os.getenv('QWEN_DEFAULT_MODEL', 'qwen3-0.6b'),
                'dashscope_api_key': os.getenv('DASHSCOPE_API_KEY'),
                'zhipu_api_key': os.getenv('ZHIPU_API_KEY')  # 添加智谱API密钥支持
            }
            
            print("✅ 环境配置加载成功")
            
        except Exception as e:
            print(f"❌ 环境配置加载失败: {e}")
            # 使用默认值（仅服务连接相关）
            self.env_config = {
                'ollama_base_url': 'http://localhost:11434',
                'ollama_default_model': 'deepseek-r1:32b',
                'qwen_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                'qwen_default_model': 'qwen3-0.6b',
                'dashscope_api_key': None,
                'zhipu_api_key': None  # 添加智谱API密钥默认值
            }
    
    def _load_workflow_configs(self) -> None:
        """加载工作流配置文件"""
        self.workflow_config = {'roles': {}}
        
        for config_file in self.workflow_config_files:
            try:
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    # 合并角色配置
                    if 'roles' in config:
                        self.workflow_config['roles'].update(config['roles'])
                    
                    print(f"✅ 已加载工作流配置: {config_file}")
                else:
                    print(f"⚠️ 工作流配置文件不存在: {config_file}")
                    
            except Exception as e:
                print(f"❌ 加载工作流配置失败 {config_file}: {e}")
    
    def _build_service_providers(self) -> None:
        """构建服务提供商配置"""
        self.service_providers = {
            'ollama': ServiceProviderConfig(
                base_url=self.env_config['ollama_base_url'],
                default_model=self.env_config['ollama_default_model']
            ),
            'qwen': ServiceProviderConfig(
                base_url=self.env_config['qwen_base_url'],
                default_model=self.env_config['qwen_default_model'],
                api_key=self.env_config['dashscope_api_key']
            )
        }
        
        # 如果配置了智谱API密钥，则添加智谱服务提供商
        if self.env_config['zhipu_api_key']:
            self.service_providers['zhipu'] = ServiceProviderConfig(
                base_url='https://open.bigmodel.cn/api/paas/v4',
                default_model='glm-4-air',
                api_key=self.env_config['zhipu_api_key']
            )
    
    def get_service_provider(self, provider_name: str) -> Optional[ServiceProviderConfig]:
        """获取服务提供商配置
        
        Args:
            provider_name: 服务提供商名称
            
        Returns:
            服务提供商配置对象
        """
        return self.service_providers.get(provider_name)
    
    def get_role_config(self, role_name: str) -> Optional[Dict[str, Any]]:
        """获取角色配置
        
        Args:
            role_name: 角色名称
            
        Returns:
            角色配置字典
        """
        return self.workflow_config.get('roles', {}).get(role_name)
    
    def list_available_roles(self) -> List[str]:
        """列出所有可用角色
        
        Returns:
            角色名称列表
        """
        return list(self.workflow_config.get('roles', {}).keys())
    
    def list_available_providers(self) -> List[str]:
        """列出所有可用的服务提供商
        
        Returns:
            服务提供商名称列表
        """
        return list(self.service_providers.keys())
    

    def reload_configs(self) -> None:
        """重新加载所有配置"""
        print("🔄 重新加载配置...")
        self._load_env_config()
        self._load_workflow_configs()
        self._build_service_providers()
        print("✅ 配置重新加载完成")
    
    def add_workflow_config(self, config_file: str) -> None:
        """添加新的工作流配置文件
        
        Args:
            config_file: 配置文件路径
        """
        if config_file not in self.workflow_config_files:
            self.workflow_config_files.append(config_file)
            self._load_workflow_configs()
            self._build_service_providers()
            print(f"✅ 已添加工作流配置: {config_file}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息
        
        Returns:
            配置摘要字典
        """
        return {
            'service_providers': list(self.service_providers.keys()),
            'available_roles': self.list_available_roles(),
            'workflow_config_files': self.workflow_config_files,
            'env_config_loaded': bool(self.env_config),
            'total_roles': len(self.workflow_config.get('roles', {}))
        }