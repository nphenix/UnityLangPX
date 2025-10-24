"""
UnityLangPX MCP消息处理器模块

处理MCP协议消息的路由和执行。
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable, List, Union
from collections import defaultdict

from .message import (
    MCPMessage, MCPRequest, MCPResponse, MCPError, MCPNotification,
    MCPMessageFactory, parse_message, create_success_response, create_error_response
)
from .adapter import ProtocolAdapter
from ...core.logger import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """MCP消息处理器"""
    
    def __init__(self, protocol_adapter: ProtocolAdapter):
        """
        初始化消息处理器
        
        Args:
            protocol_adapter: 协议适配器
        """
        self.protocol_adapter = protocol_adapter
        self._handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'method_stats': defaultdict(lambda: {
                'count': 0,
                'success': 0,
                'failure': 0,
                'avg_time': 0.0
            })
        }
        
        # 注册默认处理器
        self._register_default_handlers()
        
        logger.info("MCP消息处理器初始化完成")
    
    def _register_default_handlers(self):
        """注册默认处理器"""
        self.register_handler("initialize", self._handle_initialize)
        self.register_handler("notifications/initialized", self._handle_notifications_initialized)
        self.register_handler("tools/list", self._handle_tools_list)
        self.register_handler("tools/call", self._handle_tools_call)
        self.register_handler("ping", self._handle_ping)
        self.register_handler("status", self._handle_status)
    
    def register_handler(self, method: str, handler: Callable):
        """
        注册消息处理器
        
        Args:
            method: 方法名
            handler: 处理器函数
        """
        self._handlers[method] = handler
        logger.debug(f"注册消息处理器: {method}")
    
    def unregister_handler(self, method: str):
        """
        注销消息处理器
        
        Args:
            method: 方法名
        """
        if method in self._handlers:
            del self._handlers[method]
            logger.debug(f"注销消息处理器: {method}")
    
    def add_middleware(self, middleware: Callable):
        """
        添加中间件
        
        Args:
            middleware: 中间件函数
        """
        self._middleware.append(middleware)
        logger.debug(f"添加中间件: {middleware.__name__}")
    
    async def handle_message(self, message_data: Union[str, Dict[str, Any]]) -> str:
        """
        处理MCP消息
        
        Args:
            message_data: 消息数据
            
        Returns:
            响应JSON字符串
        """
        start_time = time.time()
        
        try:
            # 解析消息
            message = parse_message(message_data)
            logger.debug(f"收到消息: {type(message).__name__}")
            
            # 更新统计
            self._stats['total_requests'] += 1
            
            # 处理不同类型的消息
            if isinstance(message, MCPRequest):
                response = await self._handle_request(message)
            elif isinstance(message, MCPNotification):
                await self._handle_notification(message)
                return ""  # 通知消息不需要响应
            else:
                raise ValueError(f"不支持的消息类型: {type(message)}")
            
            # 更新统计
            response_time = time.time() - start_time
            self._update_stats(message.method if hasattr(message, 'method') else 'unknown', 
                            True, response_time)
            
            return response
            
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            
            # 更新统计
            response_time = time.time() - start_time
            self._update_stats('unknown', False, response_time)
            
            # 返回错误响应
            return create_error_response(e)
    
    async def _handle_request(self, request: MCPRequest) -> str:
        """
        处理请求消息
        
        Args:
            request: 请求消息
            
        Returns:
            响应JSON字符串
        """
        try:
            # 验证请求
            if not request.validate():
                return create_error_response(
                    "Invalid request format",
                    request.id
                )
            
            # 执行中间件
            for middleware in self._middleware:
                try:
                    await middleware(request)
                except Exception as e:
                    logger.warning(f"中间件执行失败: {str(e)}")
            
            # 查找处理器
            if request.method not in self._handlers:
                return create_error_response(
                    f"Method not found: {request.method}",
                    request.id
                )
            
            # 执行处理器
            handler = self._handlers[request.method]
            result = await handler(request.params or {})
            
            # 返回成功响应
            return create_success_response(result, request.id)
            
        except Exception as e:
            logger.error(f"处理请求失败: {str(e)}")
            return create_error_response(e, request.id)
    
    async def _handle_notification(self, notification: MCPNotification):
        """
        处理通知消息
        
        Args:
            notification: 通知消息
        """
        try:
            # 验证通知
            if not notification.validate():
                logger.warning("无效的通知消息格式")
                return
            
            # 执行中间件
            for middleware in self._middleware:
                try:
                    await middleware(notification)
                except Exception as e:
                    logger.warning(f"中间件执行失败: {str(e)}")
            
            # 查找处理器
            if notification.method not in self._handlers:
                logger.warning(f"未找到通知处理器: {notification.method}")
                return
            
            # 执行处理器
            handler = self._handlers[notification.method]
            await handler(notification.params or {})
            
            logger.debug(f"处理通知完成: {notification.method}")
            
        except Exception as e:
            logger.error(f"处理通知失败: {str(e)}")
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理初始化请求
        
        Args:
            params: 请求参数
            
        Returns:
            初始化结果
        """
        logger.info("MCP服务器初始化")
        
        # 获取协议版本
        protocol_version = params.get("protocolVersion", "2024-11-05")
        
        # 获取客户端信息
        client_info = params.get("clientInfo", {})
        client_name = client_info.get("name", "unknown")
        client_version = client_info.get("version", "unknown")
        
        logger.info(f"客户端连接: {client_name} v{client_version}")
        
        # 返回服务器信息
        return {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {
                    "listChanged": True
                },
                "logging": {}
            },
            "serverInfo": {
                "name": "UnityLangPX MCP Server",
                "version": "1.0.0"
            }
        }
    
    async def _handle_notifications_initialized(self, params: Dict[str, Any]):
        """
        处理初始化完成通知
        
        Args:
            params: 通知参数
        """
        logger.info("收到客户端初始化完成通知")
        # 这是一个通知消息，不需要返回响应
        return None
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理工具列表请求
        
        Args:
            params: 请求参数
            
        Returns:
            工具列表
        """
        logger.debug("获取工具列表")
        
        tools = await self.protocol_adapter.list_tools()
        
        return {
            "tools": tools
        }
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理工具调用请求
        
        Args:
            params: 请求参数
            
        Returns:
            工具执行结果
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            raise ValueError("工具名称不能为空")
        
        logger.info(f"调用工具: {tool_name}")
        
        try:
            result = await self.protocol_adapter.call_tool(tool_name, arguments)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result)
                    }
                ],
                "isError": False
            }
            
        except Exception as e:
            logger.error(f"工具调用失败: {tool_name}, 错误: {str(e)}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"工具调用失败: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理ping请求
        
        Args:
            params: 请求参数
            
        Returns:
            pong响应
        """
        logger.debug("收到ping请求")
        return {"pong": True}
    
    async def _handle_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理状态查询请求
        
        Args:
            params: 请求参数
            
        Returns:
            服务器状态
        """
        logger.debug("获取服务器状态")
        
        # 获取健康状态
        health_status = await self.protocol_adapter.get_health_status()
        
        # 获取统计信息
        stats = self.get_statistics()
        
        return {
            "status": "healthy" if health_status.get("status") == "healthy" else "unhealthy",
            "health": health_status,
            "statistics": stats,
            "timestamp": time.time()
        }
    
    def _update_stats(self, method: str, success: bool, response_time: float):
        """
        更新统计信息
        
        Args:
            method: 方法名
            success: 是否成功
            response_time: 响应时间
        """
        # 更新总体统计
        if success:
            self._stats['successful_requests'] += 1
        else:
            self._stats['failed_requests'] += 1
        
        # 更新平均响应时间
        total_requests = self._stats['total_requests']
        current_avg = self._stats['avg_response_time']
        self._stats['avg_response_time'] = (current_avg * (total_requests - 1) + response_time) / total_requests
        
        # 更新方法统计
        method_stats = self._stats['method_stats'][method]
        method_stats['count'] += 1
        
        if success:
            method_stats['success'] += 1
        else:
            method_stats['failure'] += 1
        
        # 更新方法平均响应时间
        current_method_avg = method_stats['avg_time']
        method_stats['avg_time'] = (current_method_avg * (method_stats['count'] - 1) + response_time) / method_stats['count']
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        total_requests = self._stats['total_requests']
        success_rate = (self._stats['successful_requests'] / total_requests 
                       if total_requests > 0 else 0.0)
        
        return {
            "total_requests": total_requests,
            "successful_requests": self._stats['successful_requests'],
            "failed_requests": self._stats['failed_requests'],
            "success_rate": success_rate,
            "avg_response_time": self._stats['avg_response_time'],
            "method_stats": dict(self._stats['method_stats'])
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'method_stats': defaultdict(lambda: {
                'count': 0,
                'success': 0,
                'failure': 0,
                'avg_time': 0.0
            })
        }
        logger.info("统计信息已重置")


# 便捷函数
def create_message_handler(protocol_adapter: ProtocolAdapter) -> MessageHandler:
    """
    创建消息处理器
    
    Args:
        protocol_adapter: 协议适配器
        
    Returns:
        消息处理器实例
    """
    return MessageHandler(protocol_adapter)