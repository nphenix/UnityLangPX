"""
UnityLangPX 模型客户端工厂

实现工厂模式，根据配置创建不同类型的模型客户端。
"""

from typing import Dict, Type, List

from .base import ModelClient
from .ollama_client import OllamaModelClient
from .openai_client import OpenAIModelClient
from ..logger import get_logger

logger = get_logger(__name__)


class ModelClientFactory:
    """模型客户端工厂"""
    
    _clients: Dict[str, Type[ModelClient]] = {
        "ollama": OllamaModelClient,
        "openai": OpenAIModelClient,
    }
    
    @classmethod
    def create_client(cls, provider: str, config) -> ModelClient:
        """
        创建指定类型的模型客户端
        
        Args:
            provider: 模型提供商名称 (ollama, openai)
            config: 对应提供商的配置对象
            
        Returns:
            模型客户端实例
            
        Raises:
            ValueError: 不支持的模型提供商
        """
        if provider not in cls._clients:
            supported = ", ".join(cls._clients.keys())
            raise ValueError(f"不支持的模型提供商: {provider}，支持的提供商: {supported}")
        
        logger.debug(f"创建 {provider} 模型客户端")
        client_class = cls._clients[provider]
        return client_class(config)
    
    @classmethod
    def register_client(cls, provider: str, client_class: Type[ModelClient]):
        """
        注册新的模型客户端类型
        
        Args:
            provider: 提供商名称
            client_class: 客户端类
        """
        cls._clients[provider] = client_class
        logger.debug(f"注册模型客户端: {provider}")
    
    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """
        获取支持的模型提供商列表
        
        Returns:
            支持的提供商名称列表
        """
        return list(cls._clients.keys())
    
    @classmethod
    def is_provider_supported(cls, provider: str) -> bool:
        """
        检查是否支持指定的提供商
        
        Args:
            provider: 提供商名称
            
        Returns:
            是否支持
        """
        return provider in cls._clients