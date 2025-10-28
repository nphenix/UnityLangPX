"""
标准MCP协议适配器
处理标准MCP客户端的连接和消息格式
"""

import json
import asyncio
from typing import Dict, Any

from ..core.logger import get_logger

logger = get_logger(__name__)


class StandardMCPAdapter:
    """标准MCP协议适配器"""
    
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.stats = {
            'requests_handled': 0,
            'sse_connections': 0,
            'message_requests': 0,
            'stdio_requests': 0,
            'errors': 0
        }
    
    async def handle_request(self, handler):
        """处理标准MCP请求"""
        try:
            self.stats['requests_handled'] += 1
            
            # 根据请求类型分发
            if hasattr(handler, 'path'):
                if handler.path.startswith('/sse') or handler.path.startswith('/events'):
                    return self.handle_sse_connection(handler)
                elif handler.path.startswith('/messages'):
                    return await self.handle_message_request(handler)
                else:
                    return self.handle_http_request(handler)
            else:
                # 标准输入输出模式
                return self.handle_stdio_request(handler)
                
        except Exception as e:
            logger.error(f"标准MCP适配器处理请求失败: {str(e)}")
            self.stats['errors'] += 1
            raise
    
    def handle_sse_connection(self, handler):
        """处理SSE连接（标准MCP）"""
        try:
            self.stats['sse_connections'] += 1
            logger.info("标准MCP适配器处理SSE连接")
            
            # 标准MCP的SSE实现
            handler.send_response(200)
            handler.send_header('Content-Type', 'text/event-stream')
            handler.send_header('Cache-Control', 'no-cache')
            handler.send_header('Connection', 'keep-alive')
            handler.send_header('Access-Control-Allow-Origin', '*')
            handler.send_header('Access-Control-Allow-Headers', 'Cache-Control, Content-Type, Authorization')
            handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            handler.end_headers()
            
            # 发送简单的endpoint事件 - 修复：直接发送URL字符串而不是JSON，使用\r\n作为行结束符
            host = handler.headers.get('Host', 'localhost:4010')
            endpoint_url = f"http://{host}/messages"
            sse_data = f"event: endpoint\r\ndata: {endpoint_url}\r\n\r\n"
            handler.wfile.write(sse_data.encode('utf-8'))
            handler.wfile.flush()
            
            logger.info("标准MCP SSE连接处理完成")
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"处理标准MCP SSE连接失败: {str(e)}")
            self._send_error_response(handler, 500, f"SSE Error: {str(e)}")
    
    async def handle_message_request(self, handler):
        """处理messages端点请求（标准MCP）"""
        try:
            self.stats['message_requests'] += 1
            logger.info("标准MCP适配器处理messages请求")
            
            # 读取请求数据 - 修复：确保完整读取数据
            content_length = int(handler.headers.get('Content-Length', 0))
            logger.debug(f"Content-Length: {content_length}")
            
            # 修复：先尝试直接读取所有数据，如果失败再使用分块读取
            try:
                # 直接尝试读取所有数据
                post_data = handler.rfile.read(content_length).decode('utf-8')
                logger.info(f"[STANDARD] 直接读取数据成功，长度: {len(post_data)}")
            except Exception as direct_read_error:
                logger.warning(f"[STANDARD] 直接读取失败: {str(direct_read_error)}，尝试分块读取")
                
                # 分块读取数据，确保完整接收
                post_data = ''
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(remaining, 4096)
                    chunk_bytes = handler.rfile.read(chunk_size)
                    if not chunk_bytes:
                        break
                    # 先解码为字符串，处理可能的编码问题
                    try:
                        chunk = chunk_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        # 如果UTF-8解码失败，尝试使用latin-1解码然后忽略错误
                        chunk = chunk_bytes.decode('latin-1', errors='ignore')
                    
                    post_data += chunk
                    remaining -= len(chunk_bytes)
            
            # 记录原始请求数据以便调试
            logger.debug(f"接收到的原始请求数据: {repr(post_data)}")
            logger.debug(f"数据长度: {len(post_data)}, 期望长度: {content_length}")
            
            # 清理可能的BOM或其他不可见字符
            post_data = post_data.strip()
            if post_data.startswith('\ufeff'):
                post_data = post_data[1:]  # 移除BOM
            
            # 检查数据是否为空或只包含空白字符
            if not post_data:
                logger.warning("接收到空的请求数据")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: Empty request data"
                    }
                }
                self._send_json_response(handler, error_response)
                return
            
            # 解析JSON-RPC请求
            logger.info(f"收到标准MCP原始数据: {repr(post_data)}")
            logger.info(f"数据长度: {len(post_data)}")
            
            # 直接尝试解析JSON，不进行任何修复
            try:
                request_data = json.loads(post_data)
                logger.info(f"成功解析标准MCP JSON-RPC消息: {request_data}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                logger.error(f"原始数据: {repr(post_data)}")
                # 返回正确的JSON-RPC错误响应，而不是抛出异常
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                self._send_json_response(handler, error_response)
                return
            
            # 使用MCP服务器的消息处理器
            if self.mcp_server and hasattr(self.mcp_server, 'message_handler') and self.mcp_server.message_handler:
                # 使用异步处理
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    response = loop.run_until_complete(
                        self.mcp_server.message_handler.handle_message(request_data)
                    )
                    
                    # 发送响应
                    self._send_json_response(handler, response)
                    
                finally:
                    loop.close()
            else:
                # 如果没有消息处理器，使用内置处理逻辑
                response_data = await self._process_standard_mcp_request(request_data)
                self._send_json_response(handler, response_data)
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"处理标准MCP messages请求失败: {str(e)}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            self._send_json_response(handler, error_response)
    
    def handle_http_request(self, handler):
        """处理HTTP请求"""
        try:
            logger.info(f"标准MCP适配器处理HTTP请求: {handler.path}")
            
            if handler.path == '/' or handler.path == '/health':
                # 健康检查
                handler.send_response(200)
                handler.send_header('Content-Type', 'application/json')
                handler.end_headers()
                response = {
                    "status": "ok", 
                    "service": "UnityLangPX MCP Server",
                    "adapter": "standard"
                }
                handler.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self._send_error_response(handler, 404, "Not Found")
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"处理标准MCP HTTP请求失败: {str(e)}")
            self._send_error_response(handler, 500, f"Internal Server Error: {str(e)}")
    
    def handle_stdio_request(self, handler):
        """处理标准输入输出请求"""
        try:
            self.stats['stdio_requests'] += 1
            logger.info("标准MCP适配器处理stdio请求")
            
            # 标准输入输出模式的处理逻辑
            # 这里通常由主服务器的消息循环处理
            # 适配器主要负责统计和日志
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"处理标准MCP stdio请求失败: {str(e)}")
            raise
    
    def _send_json_response(self, handler, response_data):
        """发送JSON响应"""
        try:
            if response_data is None:
                # 对于通知消息，返回204 No Content
                handler.send_response(204)
                handler.send_header('Access-Control-Allow-Origin', '*')
                handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization')
                handler.end_headers()
                handler.wfile.flush()
            else:
                # 修复：检查response_data是否已经是字符串，避免双重序列化
                if isinstance(response_data, str):
                    # 如果已经是字符串，直接使用
                    response_json = response_data
                    logger.info(f"标准MCP响应数据已是字符串，直接使用: {response_json}")
                else:
                    # 如果是字典或对象，序列化为JSON - 确保UTF-8编码和格式化
                    response_json = json.dumps(response_data, ensure_ascii=False, separators=(',', ':'), indent=2)
                    logger.info(f"标准MCP响应数据序列化为JSON: {response_json}")
                
                # 转换为字节数组以计算长度
                response_bytes = response_json.encode('utf-8')
                content_length = len(response_bytes)
                
                # 修复：检查连接状态，避免在连接已关闭时发送数据
                try:
                    # 检查连接是否仍然有效
                    if hasattr(handler, 'connection') and handler.connection:
                        # 尝试获取连接状态
                        import socket
                        try:
                            # 检查socket是否仍然连接
                            handler.connection.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                        except (OSError, socket.error):
                            logger.warning("检测到连接已断开，跳过发送响应")
                            return
                    elif hasattr(handler, 'wfile'):
                        # 检查文件是否仍然可写
                        try:
                            handler.wfile.fileno()
                        except (OSError, ValueError):
                            logger.warning("检测到文件描述符已关闭，跳过发送响应")
                            return
                except:
                    # 如果无法检查连接状态，继续尝试发送
                    pass
                
                # 发送响应头，包含Content-Length
                handler.send_response(200)
                handler.send_header('Content-Type', 'application/json; charset=utf-8')
                handler.send_header('Content-Length', str(content_length))  # 关键修复：添加Content-Length头
                handler.send_header('Connection', 'keep-alive')  # 关键修复：保持连接活跃
                handler.send_header('Keep-Alive', 'timeout=300, max=100')  # 设置keep-alive参数
                handler.send_header('Access-Control-Allow-Origin', '*')
                handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization')
                handler.end_headers()
                
                # 发送响应体
                try:
                    handler.wfile.write(response_bytes)
                    handler.wfile.flush()
                    logger.info(f"标准MCP JSON响应已发送，长度: {content_length}")
                    
                    # 确保连接关闭 - 修复：添加更长的延迟确保客户端完全接收响应
                    import time
                    time.sleep(0.1)  # 短暂延迟确保数据完全发送
                    
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as conn_error:
                    logger.warning(f"连接在发送响应时被客户端关闭: {str(conn_error)}")
                    return  # 不抛出异常，直接返回
                except Exception as write_error:
                    logger.error(f"写入响应数据失败: {str(write_error)}")
                    raise
                
                # 修复：不要主动关闭连接，让客户端决定何时关闭
                # 这样可以避免连接中断问题，支持HTTP/1.1持久连接
                try:
                    # 只刷新缓冲区，不关闭连接
                    handler.wfile.flush()
                    logger.debug("连接保持活跃，等待客户端的下一个请求")
                except:
                    pass
                
        except Exception as e:
            logger.error(f"发送标准MCP JSON响应失败: {str(e)}")
            # 不再抛出异常，避免上层处理出错
            pass
    
    def _send_error_response(self, handler, code, message):
        """发送错误响应"""
        try:
            handler.send_response(code)
            handler.send_header('Content-Type', 'application/json')
            handler.send_header('Access-Control-Allow-Origin', '*')
            handler.end_headers()
            error_response = {"error": message}
            handler.wfile.write(json.dumps(error_response).encode('utf-8'))
        except Exception as e:
            logger.error(f"发送标准MCP错误响应失败: {str(e)}")
    
    async def _process_standard_mcp_request(self, request_data):
        """处理标准MCP协议请求（内置逻辑）"""
        try:
            method = request_data.get("method")
            request_id = request_data.get("id")
            
            if method == "ping":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"pong": True}
                }
            elif method == "initialize":
                # 根据 MCP 协议规范，initialize 响应不应包含 tools 字段
                # 工具列表应通过单独的 tools/list 请求获取
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": request_data.get("params", {}).get("protocolVersion", "2025-03-26"),
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "logging": {},
                            "roots": {"listChanged": True}
                        },
                        "serverInfo": {
                            "name": "UnityLangPX MCP Server",
                            "version": "1.0.0",
                            "adapter": "standard"
                        }
                    }
                }
            elif method == "tools/list":
                # 从服务器获取实际注册的工具列表
                try:
                    tools_list = []
                    if self.mcp_server and hasattr(self.mcp_server, 'tool_registry'):
                        # 获取工具注册表中的所有工具
                        tools_list = await self.mcp_server.tool_registry.list_tools()
                        logger.info(f"[STANDARD] 从工具注册表获取到 {len(tools_list)} 个工具")
                    else:
                        logger.warning("[STANDARD] 无法访问工具注册表，返回默认工具列表")
                        # 回退到默认工具列表
                        tools_list = [
                            {
                                "name": "translate_text",
                                "description": "翻译文本",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "source_lang": {"type": "string"},
                                        "target_lang": {"type": "string"}
                                    },
                                    "required": ["text"]
                                }
                            }
                        ]
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": tools_list
                        }
                    }
                except Exception as e:
                    logger.error(f"[STANDARD] 获取工具列表失败: {str(e)}")
                    # 即使失败，也返回基本的工具列表
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "translate_text",
                                    "description": "翻译文本",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "text": {"type": "string"},
                                            "source_lang": {"type": "string"},
                                            "target_lang": {"type": "string"}
                                        },
                                        "required": ["text"]
                                    }
                                }
                            ]
                        }
                    }
            elif method == "tools/call":
                return await self._handle_standard_tool_call(request_data)
            elif method == "notifications/initialized":
                # 这是一个通知，不需要响应
                return None
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        except Exception as e:
            logger.error(f"处理标准MCP请求失败: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"处理请求失败: {str(e)}"
                }
            }
    
    async def _handle_standard_tool_call(self, request_data):
        """处理标准工具调用"""
        try:
            params = request_data.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            request_id = request_data.get("id")
            
            if tool_name == "translate_text":
                text = arguments.get("text", "")
                source_lang = arguments.get("source_lang", "en")
                target_lang = arguments.get("target_lang", "zh")
                
                # 使用真正的翻译功能
                try:
                    if self.mcp_server and hasattr(self.mcp_server, 'translator'):
                        translator = self.mcp_server.translator
                        result = translator.translate_text(
                            text=text,
                            source_lang=source_lang,
                            target_lang=target_lang
                        )
                        
                        if result.success:
                            return {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": result.translated_text.encode('utf-8').decode('utf-8') if result.translated_text else "翻译结果为空"
                                        }
                                    ]
                                }
                            }
                        else:
                            return {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32603,
                                    "message": f"翻译失败: {result.error}"
                                }
                            }
                    else:
                        return {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32603,
                                "message": "翻译器未初始化"
                            }
                        }
                except Exception as e:
                    logger.error(f"翻译过程出错: {str(e)}")
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"翻译过程出错: {str(e)}"
                        }
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
        except Exception as e:
            logger.error(f"处理标准工具调用失败: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"工具调用失败: {str(e)}"
                }
            }
    
    def get_stats(self):
        """获取统计信息"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'requests_handled': 0,
            'sse_connections': 0,
            'message_requests': 0,
            'stdio_requests': 0,
            'errors': 0
        }
        logger.info("标准MCP适配器统计信息已重置")