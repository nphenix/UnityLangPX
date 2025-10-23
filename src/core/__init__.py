"""
UnityLangPX 核心翻译模块

这个模块包含了UnityLangPX项目的核心翻译功能，包括：
- Ollama客户端：与本地Ollama服务交互
- Markdown处理器：解析和重构Markdown文档
- 翻译引擎：协调翻译流程
- 配置管理：管理应用配置
"""

__version__ = "0.1.0"
__author__ = "UnityLangPX Team"

from .config import Config
from .exceptions import (
    UnityLangPXError,
    ConfigurationError,
    APIConnectionError,
    ModelNotFoundError,
    TranslationError,
    MarkdownProcessingError,
)
from .logger import LoggerManager, init_logger, get_logger, log_performance
from .models.ollama_client import OllamaModelClient as OllamaClient
from .markdown_processor import MarkdownProcessor, MarkdownElement
from .translator import Translator, TranslationResult, TranslationCache
from .batch_processor import BatchProcessor

__all__ = [
    "Config",
    "UnityLangPXError",
    "ConfigurationError",
    "APIConnectionError",
    "ModelNotFoundError",
    "TranslationError",
    "MarkdownProcessingError",
    "LoggerManager",
    "init_logger",
    "get_logger",
    "log_performance",
    "OllamaClient",
    "MarkdownProcessor",
    "MarkdownElement",
    "Translator",
    "TranslationResult",
    "TranslationCache",
    "BatchProcessor",
]