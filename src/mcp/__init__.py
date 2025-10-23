"""
UnityLangPX MCP服务器模块

提供基于MCP协议的翻译服务接口，支持n8n、Dify等平台集成。
"""

__version__ = "1.0.0"
__author__ = "UnityLangPX Team"
__description__ = "UnityLangPX MCP服务器 - 基于大模型技术的翻译服务"

from .server import MCPServer
from .config import MCPConfig
from .tools import BaseTool, ToolRegistry

__all__ = [
    "MCPServer",
    "MCPConfig", 
    "BaseTool",
    "ToolRegistry"
]