"""
UnityLangPX 嵌入模型客户端

支持多种嵌入模型，包括本地模型和远程API。
"""

import os
import time
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from abc import ABC, abstractmethod
from .logger import get_logger
from ..config.manager import get_config_manager

logger = get_logger(__name__)


class EmbeddingClient(ABC):
    """嵌入模型客户端抽象基类"""
    
    @abstractmethod
    def encode(self, texts: Union[str, List[str]], 
              batch_size: int = 32) -> Union[List[float], List[List[float]]]:
        """
        编码文本为向量
        
        Args:
            texts: 文本或文本列表
            batch_size: 批处理大小
            
        Returns:
            向量或向量列表
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """获取向量维度"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查模型是否可用"""
        pass


class SentenceTransformerClient(EmbeddingClient):
    """SentenceTransformer模型客户端"""
    
    def __init__(self, model_name: str = "bge-m3"):
        """
        初始化SentenceTransformer客户端
        
        Args:
            model_name: 模型名称
        """
        self.model_name = model_name
        self.model = None
        self.dimension = 1024  # bge-m3的默认维度
        
        # 尝试加载模型
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            # 检查CUDA是否可用
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"使用设备: {device}")
            
            # 加载模型
            model_path = self._get_model_path()
            self.model = SentenceTransformer(model_path, device=device)
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            logger.info(f"SentenceTransformer模型加载成功: {self.model_name}, 维度: {self.dimension}")
            
        except ImportError:
            logger.error("sentence-transformers库未安装，无法使用SentenceTransformer客户端")
        except Exception as e:
            logger.error(f"加载SentenceTransformer模型失败: {e}")
    
    def _get_model_path(self) -> str:
        """获取模型路径"""
        # 检查是否为本地模型
        if self.model_name.endswith(":latest") or "/" not in self.model_name:
            # 可能是Ollama本地模型
            return self.model_name
        
        return self.model_name
    
    def encode(self, texts: Union[str, List[str]], 
              batch_size: int = 32) -> Union[List[float], List[List[float]]]:
        """
        编码文本为向量
        
        Args:
            texts: 文本或文本列表
            batch_size: 批处理大小
            
        Returns:
            向量或向量列表
        """
        if self.model is None:
            raise RuntimeError("模型未加载")
        
        # 统一输入为列表
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        
        try:
            # 批量编码
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            
            # 转换为列表格式
            result = embeddings.tolist()
            
            # 如果是单个输入，返回单个向量
            if is_single:
                return result[0]
            
            return result
            
        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            # 返回零向量作为降级方案
            if is_single:
                return [0.0] * self.dimension
            else:
                return [[0.0] * self.dimension] * len(texts)
    
    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return self.model is not None


class OllamaEmbeddingClient(EmbeddingClient):
    """Ollama嵌入模型客户端"""
    
    def __init__(self, model_name: str = "bge-m3:latest", 
                 base_url: str = "http://localhost:11434"):
        """
        初始化Ollama嵌入客户端
        
        Args:
            model_name: 模型名称
            base_url: Ollama服务地址
        """
        self.model_name = model_name
        self.base_url = base_url
        self.dimension = 1024  # bge-m3的默认维度
        
        # 检查服务可用性
        self._check_service()
    
    def _check_service(self):
        """检查Ollama服务可用性"""
        try:
            import requests
            
            # 检查服务状态
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]
                
                if self.model_name in model_names:
                    logger.info(f"Ollama模型可用: {self.model_name}")
                else:
                    logger.warning(f"Ollama模型不可用: {self.model_name}")
                    logger.info(f"可用模型: {', '.join(model_names)}")
            else:
                logger.error(f"Ollama服务不可用: {self.base_url}")
                
        except Exception as e:
            logger.error(f"检查Ollama服务失败: {e}")
    
    def encode(self, texts: Union[str, List[str]], 
              batch_size: int = 32) -> Union[List[float], List[List[float]]]:
        """
        编码文本为向量
        
        Args:
            texts: 文本或文本列表
            batch_size: 批处理大小（Ollama客户端忽略此参数）
            
        Returns:
            向量或向量列表
        """
        try:
            import requests
            
            # 统一输入为列表
            is_single = isinstance(texts, str)
            if is_single:
                texts = [texts]
            
            results = []
            
            # 逐个处理（Ollama API通常不支持批量处理）
            for text in texts:
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model_name,
                        "prompt": text
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    embedding = response.json().get("embedding", [])
                    if embedding:
                        results.append(embedding)
                        if not self.dimension:
                            self.dimension = len(embedding)
                    else:
                        logger.warning(f"获取空嵌入: {text}")
                        results.append([0.0] * self.dimension)
                else:
                    logger.error(f"嵌入请求失败: {response.status_code}")
                    results.append([0.0] * self.dimension)
            
            # 如果是单个输入，返回单个向量
            if is_single:
                return results[0]
            
            return results
            
        except Exception as e:
            logger.error(f"Ollama文本编码失败: {e}")
            # 返回零向量作为降级方案
            if is_single:
                return [0.0] * self.dimension
            else:
                return [[0.0] * self.dimension] * len(texts)
    
    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        try:
            import requests
            
            # 简单测试
            test_text = "test"
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": test_text
                },
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception:
            return False


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI嵌入模型客户端"""
    
    def __init__(self, model_name: str = "text-embedding-ada-002",
                 api_key: str = None, base_url: str = None):
        """
        初始化OpenAI嵌入客户端
        
        Args:
            model_name: 模型名称
            api_key: API密钥
            base_url: API基础URL
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or "https://api.openai.com/v1"
        self.dimension = 1536  # text-embedding-ada-002的维度
        
        if not self.api_key:
            logger.warning("未设置OpenAI API密钥")
    
    def encode(self, texts: Union[str, List[str]], 
              batch_size: int = 32) -> Union[List[float], List[List[float]]]:
        """
        编码文本为向量
        
        Args:
            texts: 文本或文本列表
            batch_size: 批处理大小
            
        Returns:
            向量或向量列表
        """
        try:
            import openai
            
            # 设置客户端
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # 统一输入为列表
            is_single = isinstance(texts, str)
            if is_single:
                texts = [texts]
            
            results = []
            
            # 批量处理
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = client.embeddings.create(
                    model=self.model_name,
                    input=batch
                )
                
                batch_results = [item.embedding for item in response.data]
                results.extend(batch_results)
            
            # 如果是单个输入，返回单个向量
            if is_single:
                return results[0]
            
            return results
            
        except ImportError:
            logger.error("openai库未安装，无法使用OpenAI客户端")
            return self._fallback_result(texts)
        except Exception as e:
            logger.error(f"OpenAI文本编码失败: {e}")
            return self._fallback_result(texts)
    
    def _fallback_result(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """降级结果"""
        is_single = isinstance(texts, str)
        if is_single:
            return [0.0] * self.dimension
        else:
            return [[0.0] * self.dimension] * len(texts) if isinstance(texts, list) else [[0.0] * self.dimension]
    
    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        if not self.api_key:
            return False
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            # 简单测试
            response = client.embeddings.create(
                model=self.model_name,
                input="test"
            )
            
            return len(response.data) > 0
            
        except Exception:
            return False


class EmbeddingClientFactory:
    """嵌入客户端工厂"""
    
    @staticmethod
    def create_client(client_type: str, **kwargs) -> EmbeddingClient:
        """
        创建嵌入客户端
        
        Args:
            client_type: 客户端类型 ("sentence_transformer", "ollama", "openai")
            **kwargs: 客户端参数
            
        Returns:
            嵌入客户端实例
        """
        if client_type == "sentence_transformer":
            model_name = kwargs.get("model_name", "bge-m3")
            return SentenceTransformerClient(model_name)
        
        elif client_type == "ollama":
            model_name = kwargs.get("model_name", "bge-m3:latest")
            base_url = kwargs.get("base_url", "http://localhost:11434")
            return OllamaEmbeddingClient(model_name, base_url)
        
        elif client_type == "openai":
            model_name = kwargs.get("model_name", "text-embedding-ada-002")
            api_key = kwargs.get("api_key")
            base_url = kwargs.get("base_url")
            return OpenAIEmbeddingClient(model_name, api_key, base_url)
        
        else:
            raise ValueError(f"不支持的客户端类型: {client_type}")
    
    @staticmethod
    def get_available_clients() -> List[str]:
        """获取可用的客户端类型"""
        return ["sentence_transformer", "ollama", "openai"]
    
    @staticmethod
    def auto_detect_client(**kwargs) -> EmbeddingClient:
        """
        自动检测并创建可用的客户端
        
        Args:
            **kwargs: 客户端参数
            
        Returns:
            可用的嵌入客户端实例
        """
        # 尝试从统一配置系统获取配置
        try:
            config_manager = get_config_manager()
            performance_config = config_manager.get_performance_config()
            embedding_config = performance_config.embedding
            
            # 使用配置中的提供商
            preferred_provider = embedding_config.provider
            
            # 合并配置参数
            config_kwargs = embedding_config.get_embedding_config()
            config_kwargs.update(kwargs)
            
            # 首先尝试首选提供商
            try:
                client = EmbeddingClientFactory.create_client(preferred_provider, **config_kwargs)
                if client.is_available():
                    logger.info(f"使用配置的嵌入客户端: {preferred_provider}")
                    return client
            except Exception as e:
                logger.warning(f"无法使用配置的 {preferred_provider} 客户端: {e}")
            
            # 如果首选提供商不可用，尝试其他提供商
            other_providers = ["sentence_transformer", "ollama", "openai"]
            other_providers.remove(preferred_provider)
            
            for provider in other_providers:
                try:
                    client = EmbeddingClientFactory.create_client(provider, **config_kwargs)
                    if client.is_available():
                        logger.info(f"使用备用嵌入客户端: {provider}")
                        return client
                except Exception as e:
                    logger.warning(f"无法使用 {provider} 客户端: {e}")
                    
        except Exception as e:
            logger.warning(f"无法加载嵌入配置，使用默认检测: {e}")
        
        # 如果配置加载失败，使用默认检测顺序
        clients_to_try = [
            ("ollama", kwargs),
            ("sentence_transformer", kwargs),
            ("openai", kwargs)
        ]
        
        for client_type, client_kwargs in clients_to_try:
            try:
                client = EmbeddingClientFactory.create_client(client_type, **client_kwargs)
                if client.is_available():
                    logger.info(f"使用嵌入客户端: {client_type}")
                    return client
            except Exception as e:
                logger.warning(f"无法使用 {client_type} 客户端: {e}")
        
        # 如果所有客户端都不可用，创建一个降级客户端
        logger.error("所有嵌入客户端都不可用，使用降级客户端")
        return FallbackEmbeddingClient()


class FallbackEmbeddingClient(EmbeddingClient):
    """降级嵌入客户端（返回零向量）"""
    
    def __init__(self, dimension: int = 1024):
        """初始化降级客户端"""
        self.dimension = dimension
    
    def encode(self, texts: Union[str, List[str]], 
              batch_size: int = 32) -> Union[List[float], List[List[float]]]:
        """编码文本为向量（返回零向量）"""
        is_single = isinstance(texts, str)
        if is_single:
            return [0.0] * self.dimension
        else:
            texts_list = texts if isinstance(texts, list) else [texts]
            return [[0.0] * self.dimension] * len(texts_list)
    
    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return True  # 降级客户端总是可用