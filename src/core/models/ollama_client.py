"""
UnityLangPX Ollama模型客户端实现

封装原始Ollama客户端，实现统一的ModelClient接口。
"""

from typing import Optional, Dict, Any, List

from .base import ModelClient
import requests
import json
from ..exceptions import APIConnectionError, ModelNotFoundError, TranslationError
from ..logger import get_logger

logger = get_logger(__name__)

class OriginalOllamaClient:
    """原始Ollama客户端实现"""
    
    def __init__(self, config):
        """
        初始化Ollama客户端
        
        Args:
            config: Ollama配置对象
        """
        self.config = config
        self.base_url = config.host
        self.model = config.model
        self.timeout = config.timeout
        logger.debug(f"初始化Ollama客户端: {self.base_url}")
    
    def check_connection(self) -> bool:
        """检查Ollama服务连接是否正常"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama服务连接失败: {str(e)}")
            return False
    
    def check_model(self) -> bool:
        """检查指定模型是否可用"""
        try:
            models = self.list_models()
            return any(model.get("name") == self.model for model in models)
        except Exception as e:
            logger.error(f"检查Ollama模型失败: {str(e)}")
            return False
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有可用模型"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"获取Ollama模型列表失败: {str(e)}")
            raise APIConnectionError(f"获取模型列表失败: {str(e)}")
    
    def translate_text(self, text: str, context: Optional[str] = None,
                      source_lang: str = "en", target_lang: str = "zh",
                      temperature: float = 0.1) -> str:
        """翻译文本"""
        try:
            # 构建提示词
            if context:
                prompt = f"Context: {context}\n\nTranslate the following {source_lang} text to {target_lang}:\n\n{text}"
            else:
                prompt = f"Translate the following {source_lang} text to {target_lang}:\n\n{text}"
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 2000
                    }
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama翻译失败: {str(e)}")
            raise TranslationError(f"翻译失败: {str(e)}")
    
    def close(self):
        """关闭客户端连接"""
        logger.debug("Ollama客户端已关闭")
    
    @staticmethod
    def estimate_tokens(text: str, language: str = "en") -> int:
        """
        估算文本的令牌数
        
        Args:
            text: 文本内容
            language: 语言代码，默认为英语
            
        Returns:
            估算的令牌数
        """
        if language in ["zh", "ja", "ko"]:
            # 中文、日文、韩文等亚洲语言，一个字符约等于2个令牌
            return len(text) * 2
        else:
            # 英文等拉丁语言，平均1.3个字符等于1个令牌
            return int(len(text) / 1.3)
from ..exceptions import APIConnectionError, ModelNotFoundError, TranslationError
from ..logger import get_logger

logger = get_logger(__name__)


class OllamaModelClient(ModelClient):
    """Ollama模型客户端实现"""
    
    def __init__(self, config):
        """
        初始化Ollama模型客户端
        
        Args:
            config: Ollama配置对象
        """
        self.config = config
        self.client = OriginalOllamaClient(config)
        logger.debug(f"初始化Ollama模型客户端: {config.host}")
    
    def check_connection(self) -> bool:
        """检查Ollama服务连接是否正常"""
        try:
            return self.client.check_connection()
        except Exception as e:
            logger.error(f"Ollama服务连接失败: {str(e)}")
            raise APIConnectionError(f"无法连接到Ollama服务: {str(e)}")
    
    def check_model(self) -> bool:
        """检查指定模型是否可用"""
        try:
            return self.client.check_model()
        except Exception as e:
            logger.error(f"检查Ollama模型失败: {str(e)}")
            if isinstance(e, (APIConnectionError, ModelNotFoundError)):
                raise
            raise APIConnectionError(f"检查模型失败: {str(e)}")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有可用模型"""
        try:
            models = self.client.list_models()
            logger.debug(f"获取到 {len(models)} 个Ollama模型")
            return models
        except Exception as e:
            logger.error(f"获取Ollama模型列表失败: {str(e)}")
            raise APIConnectionError(f"获取模型列表失败: {str(e)}")
    
    def translate_text(self, text: str, context: Optional[str] = None,
                      source_lang: str = "en", target_lang: str = "zh",
                      temperature: float = 0.1) -> str:
        """翻译文本"""
        try:
            logger.debug(f"使用Ollama翻译文本，长度: {len(text)}")
            return self.client.translate_text(
                text, context, source_lang, target_lang, temperature
            )
        except Exception as e:
            logger.error(f"Ollama翻译失败: {str(e)}")
            if isinstance(e, (APIConnectionError, ModelNotFoundError, TranslationError)):
                raise
            raise TranslationError(f"翻译失败: {str(e)}")
    
    def close(self):
        """关闭客户端连接"""
        try:
            self.client.close()
            logger.debug("Ollama模型客户端已关闭")
        except Exception as e:
            logger.warning(f"关闭Ollama客户端时出错: {str(e)}")