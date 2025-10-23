"""
UnityLangPX 异常类定义

这个模块定义了UnityLangPX项目中使用的所有自定义异常类。
"""


class UnityLangPXError(Exception):
    """UnityLangPX基础异常类"""
    
    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\n详细信息: {self.details}"
        return self.message


class ConfigurationError(UnityLangPXError):
    """配置错误异常"""
    pass


class APIConnectionError(UnityLangPXError):
    """API连接错误异常"""
    pass


class ModelNotFoundError(UnityLangPXError):
    """模型未找到错误异常"""
    pass


class TranslationError(UnityLangPXError):
    """翻译错误异常"""
    pass


class MarkdownProcessingError(UnityLangPXError):
    """Markdown处理错误异常"""
    pass


class FileProcessingError(UnityLangPXError):
    """文件处理错误异常"""
    pass


class CacheError(UnityLangPXError):
    """缓存错误异常"""
    pass


class ValidationError(UnityLangPXError):
    """验证错误异常"""
    pass