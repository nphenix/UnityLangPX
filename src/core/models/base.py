"""
UnityLangPX 模型客户端基类

定义了所有模型客户端必须实现的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class ModelClient(ABC):
    """抽象模型客户端接口"""
    
    @abstractmethod
    def check_connection(self) -> bool:
        """
        检查服务连接是否正常
        
        Returns:
            连接是否正常
        """
        pass
    
    @abstractmethod
    def check_model(self) -> bool:
        """
        检查指定模型是否可用
        
        Returns:
            模型是否可用
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """
        列出所有可用模型
        
        Returns:
            模型列表，每个模型包含id、name等信息
        """
        pass
    
    @abstractmethod
    def translate_text(self, text: str, context: Optional[str] = None,
                      source_lang: str = "en", target_lang: str = "zh",
                      temperature: float = 0.1) -> str:
        """
        翻译文本
        
        Args:
            text: 待翻译文本
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            temperature: 生成温度
            
        Returns:
            翻译结果
        """
        pass
    
    @abstractmethod
    def close(self):
        """关闭客户端连接"""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()