"""
Dify专用SSE适配器
处理Dify客户端的SSE连接和消息格式
"""

import json
import uuid
import time
import socket
from typing import Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger(__name__)


class DifySSEAdapter:
    """Dify专用SSE适配器"""
    
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.stats = {
            'sse_connections': 0,
            'message_requests': 0,
            'errors': 0,
            'active_sessions': 0
        }
        self.active_sessions = {}
        self.endpoint_url_generator = EndpointURLGenerator()
        self.message_formatter = DifyMessageFormatter()
    
    def handle_sse_connection(self, handler):
        """处理SSE连接请求 - 实现真正的SSE长连接"""
        try:
            self.stats['sse_connections'] += 1
            logger.info("Dify适配器处理SSE连接")
            
            # 记录详细的请求信息
            host = handler.headers.get('Host', 'localhost:4010')
            origin = handler.headers.get('Origin', 'unknown')
            auth_header = handler.headers.get('Authorization', '')
            user_agent = handler.headers.get('User-Agent', '')
            
            logger.info(f"Dify SSE请求详情:")
            logger.info(f"  Host: {host}")
            logger.info(f"  Origin: {origin}")
            logger.info(f"  Authorization: {auth_header[:20]}..." if len(auth_header) > 20 else f"  Authorization: {auth_header}")
            logger.info(f"  User-Agent: {user_agent}")
            
            # 检查授权（如果启用）
            if not self._check_authorization(handler):
                return
            
            # 生成session ID
            session_id = str(uuid.uuid4())
            
            # 生成端点URL
            endpoint_url = self.endpoint_url_generator.generate_endpoint_url(handler, session_id)
            
            logger.info(f"Dify SSE端点URL: {endpoint_url}")
            
            # 设置SSE响应头
            self._set_sse_headers(handler)
            
            # 发送endpoint事件
            self._send_endpoint_event(handler, endpoint_url)
            
            # 记录活跃会话
            self.active_sessions[session_id] = {
                'start_time': time.time(),
                'host': host,
                'user_agent': user_agent
            }
            self.stats['active_sessions'] = len(self.active_sessions)
            
            # 修复：保持SSE连接并发送简单心跳，而不是立即完成
            logger.info("Dify SSE连接处理完成，endpoint已发送，开始保持连接和心跳")
            
            # 保持连接并发送心跳
            try:
                # 保持连接并定期发送简单心跳
                while True:
                    try:
                        # 每15秒发送一次简单心跳
                        time.sleep(15)
                        heartbeat_data = ": ping\n\n"
                        handler.wfile.write(heartbeat_data.encode('utf-8'))
                        handler.wfile.flush()
                        logger.debug(f"Dify SSE发送心跳")
                    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                        logger.info(f"Dify SSE客户端断开连接: {str(e)}")
                        break
                    except Exception as e:
                        logger.error(f"Dify SSE发送心跳失败: {str(e)}")
                        break
                        
            except Exception as e:
                logger.warning(f"Dify SSE保持连接失败: {str(e)}")
            
            logger.info("Dify SSE连接已结束")
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"处理Dify SSE请求失败: {str(e)}")
            self._send_error_response(handler, 500, f"SSE Error: {str(e)}")
    
    async def handle_message_request(self, handler, post_data=None):
        """处理messages端点请求"""
        try:
            self.stats['message_requests'] += 1
            logger.info("=" * 60)
            logger.info("Dify适配器处理messages请求")
            logger.info("=" * 60)
            
            # 记录详细的请求信息
            host = handler.headers.get('Host', 'localhost:4010')
            origin = handler.headers.get('Origin', 'unknown')
            auth_header = handler.headers.get('Authorization', '')
            user_agent = handler.headers.get('User-Agent', '')
            
            logger.info(f"Dify Messages请求详情:")
            logger.info(f"  Host: {host}")
            logger.info(f"  Origin: {origin}")
            logger.info(f"  Authorization: {auth_header[:20]}..." if len(auth_header) > 20 else f"  Authorization: {auth_header}")
            logger.info(f"  User-Agent: {user_agent}")
            
            # 解析session_id，支持路径型和查询参数型
            path = getattr(handler, 'path', '')
            session_id = None
            
            # 支持 /messages/<session_id>
            parts = path.split('?')[0].split('/')
            if len(parts) >= 3 and parts[1] == 'messages':
                session_id = parts[2]
                logger.info(f"从路径解析session_id: {session_id}")
            
            # 支持 ?session_id=...
            if not session_id:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(path).query)
                session_id = qs.get('session_id', [None])[0]
                if session_id:
                    logger.info(f"从查询参数解析session_id: {session_id}")
            
            # 检查授权（如果启用）
            if not self._check_authorization(handler):
                return
            
            # 获取Content-Length
            content_length = int(handler.headers.get('Content-Length', 0))
            logger.info(f"[DIFY] Content-Length: {content_length}")
            logger.info(f"[DIFY] 请求方法: {getattr(handler, 'command', 'UNKNOWN')}")
            logger.info(f"[DIFY] 请求路径: {getattr(handler, 'path', 'UNKNOWN')}")
            
            # 如果没有传递数据，尝试读取
            if post_data is None:
                logger.warning("[DIFY] 没有传递post_data，尝试读取数据流")
                if content_length > 0:
                    # 修复：先尝试直接读取所有数据，如果失败再使用分块读取
                    try:
                        # 直接尝试读取所有数据
                        post_data = handler.rfile.read(content_length).decode('utf-8')
                        logger.info(f"[DIFY] 直接读取数据成功，长度: {len(post_data)}")
                        
                        # 如果读取到的数据为空，尝试使用server.py中的方法
                        if not post_data:
                            logger.warning(f"[DIFY] 直接读取数据为空，尝试重新读取")
                            # 使用与server.py相同的方法
                            post_data = handler.rfile.read(int(content_length)).decode('utf-8')
                            logger.info(f"[DIFY] 重新读取数据成功，长度: {len(post_data)}")
                            
                    except Exception as direct_read_error:
                        logger.warning(f"[DIFY] 直接读取失败: {str(direct_read_error)}，尝试分块读取")
                        
                        # 设置读取超时，防止阻塞
                        import socket
                        if hasattr(handler.rfile, '_sock'):
                            # 尝试设置底层socket的超时
                            try:
                                handler.rfile._sock.settimeout(30.0)  # 30秒超时
                            except:
                                pass
                        elif hasattr(handler, 'connection') and hasattr(handler.connection, 'settimeout'):
                            try:
                                handler.connection.settimeout(30.0)  # 30秒超时
                            except:
                                pass
                        elif hasattr(handler, 'rfile') and hasattr(handler.rfile, 'settimeout'):
                            try:
                                handler.rfile.settimeout(30.0)  # 30秒超时
                            except:
                                pass
                        
                        # 分块读取数据，确保完整接收
                        post_data = ''
                        remaining = content_length
                        total_read = 0
                        
                        while remaining > 0 and total_read < content_length:
                            chunk_size = min(remaining, 4096)
                            try:
                                chunk_bytes = handler.rfile.read(chunk_size)
                                if not chunk_bytes:
                                    logger.warning(f"Dify读取数据时遇到EOF，已读取{total_read}字节，期望{content_length}字节")
                                    break
                                
                                # 先解码为字符串，处理可能的编码问题
                                try:
                                    chunk = chunk_bytes.decode('utf-8')
                                except UnicodeDecodeError:
                                    # 如果UTF-8解码失败，尝试使用latin-1解码然后忽略错误
                                    chunk = chunk_bytes.decode('latin-1', errors='ignore')
                                
                                post_data += chunk
                                remaining -= len(chunk_bytes)
                                total_read += len(chunk_bytes)
                                
                            except socket.timeout:
                                logger.error(f"Dify读取数据超时，已读取{total_read}字节，期望{content_length}字节")
                                break
                            except Exception as e:
                                logger.error(f"Dify读取数据时发生错误: {str(e)}")
                                break
                else:
                    # 修复：处理Content-Length为0但可能有数据的情况
                    logger.warning(f"[DIFY] Content-Length为0，但可能存在数据，尝试读取")
                    try:
                        # 尝试读取可能的数据
                        post_data = handler.rfile.read(1024).decode('utf-8')  # 读取最多1KB
                        if post_data:
                            logger.info(f"[DIFY] 在Content-Length为0的情况下读取到数据，长度: {len(post_data)}")
                        else:
                            logger.info(f"[DIFY] 在Content-Length为0的情况下也没有读取到数据")
                    except Exception as e:
                        logger.warning(f"[DIFY] 尝试读取额外数据失败: {str(e)}")
                        post_data = ''
            else:
                logger.info(f"[DIFY] 使用传递的post_data，长度: {len(post_data)}")
            
            # 立即尝试解析JSON，避免阻塞
            logger.info(f"[DIFY] 收到原始数据: {repr(post_data)}")
            logger.info(f"[DIFY] 数据长度: {len(post_data)}")
            logger.info(f"[DIFY] 数据类型: {type(post_data)}")
            
            # 清理可能的BOM或其他不可见字符
            post_data = post_data.strip()
            if post_data.startswith('\ufeff'):
                post_data = post_data[1:]  # 移除BOM
            
            # 检查数据是否为空或只包含空白字符
            if not post_data:
                logger.warning("Dify接收到空的请求数据")
                error_response = self.message_formatter.format_error_response(-32600, "Invalid Request: Empty request data")
                self._send_json_response(handler, error_response)
                return
            
            # 直接尝试解析JSON，不进行任何修复
            try:
                request_data = json.loads(post_data)
                logger.info(f"成功解析Dify JSON-RPC消息: {request_data}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                logger.error(f"原始数据: {repr(post_data)}")
                self.stats['errors'] += 1
                # 返回正确的JSON-RPC错误响应
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}",
                        "_dify_adapter": True
                    }
                }
                self._send_json_response(handler, error_response)
                return
            
            # 处理MCP协议请求
            try:
                logger.info(f"[DIFY] 开始处理MCP协议请求")
                response_data = await self._process_mcp_request(request_data)
                logger.info(f"[DIFY] MCP请求处理结果: {response_data}")
                logger.info(f"[DIFY] 响应数据类型: {type(response_data)}")
                
                # 格式化响应
                formatted_response = self.message_formatter.format_response(response_data)
                logger.info(f"[DIFY] 格式化响应: {formatted_response}")
                logger.info(f"[DIFY] 格式化响应类型: {type(formatted_response)}")
                
                # 修复：对于通知消息，不返回响应
                if formatted_response is None:
                    logger.info("[DIFY] 通知消息，不返回响应")
                    logger.info("=" * 60)
                    return
                
                # 发送响应
                logger.info(f"[DIFY] 准备发送响应...")
                self._send_json_response(handler, formatted_response)
                logger.info("[DIFY] Messages响应发送完成")
                logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"处理MCP请求失败: {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                self.stats['errors'] += 1
                error_response = self.message_formatter.format_error_response(-32603, f"Internal error: {str(e)}")
                self._send_json_response(handler, error_response)
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"处理Dify messages请求失败: {str(e)}")
            error_response = self.message_formatter.format_error_response(-32603, f"Internal error: {str(e)}")
            self._send_json_response(handler, error_response)
    
    async def handle_request(self, handler, post_data=None):
        """处理通用请求"""
        path = getattr(handler, 'path', '')
        if path.startswith('/sse') or path.startswith('/events'):
            return self.handle_sse_connection(handler)
        elif path.startswith('/messages'):
            return await self.handle_message_request(handler, post_data=post_data)
        else:
            self._send_error_response(handler, 404, "Not Found")
    
    def _check_authorization(self, handler) -> bool:
        """检查授权"""
        try:
            if self.mcp_server and hasattr(self.mcp_server, 'config') and self.mcp_server.config.security.enable_auth:
                auth_header = handler.headers.get('Authorization', '')
                if not auth_header or not auth_header.startswith('Bearer '):
                    logger.warning("Dify授权失败：缺少或无效的Authorization头")
                    self._send_error_response(handler, 401, "Unauthorized: Missing or invalid Bearer token")
                    return False
                
                # 验证token
                token = auth_header[7:]  # 移除 "Bearer " 前缀
                expected_token = self.mcp_server.config.security.api_key
                if token != expected_token:
                    logger.warning("Dify授权失败：token不匹配")
                    self._send_error_response(handler, 401, "Unauthorized: Invalid token")
                    return False
                
                logger.info("Dify授权验证通过")
            return True
        except Exception as e:
            logger.error(f"授权检查失败: {str(e)}")
            return False
    
    def _set_sse_headers(self, handler):
        """设置SSE响应头"""
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        handler.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        handler.send_header('Connection', 'keep-alive')
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Headers', 'Cache-Control, Content-Type, Authorization')
        handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        # 添加额外的SSE相关头，确保Dify能正确处理
        handler.send_header('X-Accel-Buffering', 'no')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('X-XSS-Protection', '1; mode=block')
        
        # 关键修复：强制使用HTTP/1.1协议，支持持久连接
        if hasattr(handler, 'protocol_version'):
            handler.protocol_version = "HTTP/1.1"
        
        # 关键修复：必须调用end_headers()来完成HTTP响应头的发送
        handler.end_headers()
        logger.info("Dify SSE响应头设置完成，使用HTTP/1.1")
    
    def _send_endpoint_event(self, handler, endpoint_url):
        """发送endpoint事件 - 修复格式为JSON格式"""
        # 确保SSE格式完全符合Dify期望
        # 使用标准JSON格式的data字段，确保Dify能正确解析
        try:
            # 直接发送endpoint URL，不嵌套在JSON对象中
            # Dify期望直接收到URL，而不是包含URL的JSON对象
            endpoint_data = f"event: endpoint\r\ndata: {endpoint_url}\r\n\r\n"
            
            handler.wfile.write(endpoint_data.encode('utf-8'))
            handler.wfile.flush()
            logger.info(f"已发送Dify endpoint数据: {repr(endpoint_data)}")
            
            # 立即再次刷新，确保数据被发送
            handler.wfile.flush()
            # 修复：减少延迟时间，避免客户端超时
            import time
            time.sleep(0.05)  # 减少延迟时间
            handler.wfile.flush()
        except Exception as e:
            logger.error(f"发送endpoint事件失败: {str(e)}")
            pass
    
    def _send_json_response(self, handler, response_data):
        """发送JSON响应"""
        try:
            # 修复：检查response_data是否已经是字符串，避免双重序列化
            if isinstance(response_data, str):
                # 如果已经是字符串，直接使用
                response_json = response_data
                logger.info(f"Dify响应数据已是字符串，直接使用: {response_json}")
            else:
                # 如果是字典或对象，序列化为JSON - 确保UTF-8编码和格式化
                response_json = json.dumps(response_data, ensure_ascii=False, separators=(',', ':'), indent=2)
                logger.info(f"Dify响应数据序列化为JSON: {response_json}")
            
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
            handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization, X-Requested-With')
            handler.end_headers()
            
            # 发送响应体
            try:
                handler.wfile.write(response_bytes)
                handler.wfile.flush()
                logger.info(f"Dify JSON响应已发送，长度: {content_length}")
                
                # 修复：减少延迟时间，避免客户端超时
                import time
                time.sleep(0.05)  # 减少延迟时间
                
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as conn_error:
                logger.info(f"客户端正常关闭连接: {str(conn_error)}")
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
            logger.error(f"发送JSON响应失败: {str(e)}")
            # 不再抛出异常，避免上层处理出错
            pass
    
    def _send_health_response(self, handler):
        """发送健康检查响应"""
        response = {
            "status": "ok",
            "service": "UnityLangPX MCP Server Dify Adapter"
        }
        response_json = json.dumps(response)
        response_bytes = response_json.encode('utf-8')
        
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/json; charset=utf-8')
        handler.send_header('Content-Length', str(len(response_bytes)))
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization')
        handler.send_header('Connection', 'close')
        handler.end_headers()
        
        handler.wfile.write(response_bytes)
        handler.wfile.flush()
        
        # 确保连接关闭
        try:
            if hasattr(handler.wfile, 'close'):
                handler.wfile.close()
            if hasattr(handler, 'connection') and handler.connection:
                handler.connection.close()
        except:
            pass
    
    def _send_error_response(self, handler, code, message):
        """发送错误响应"""
        try:
            error_response = {"error": message}
            error_json = json.dumps(error_response)
            error_bytes = error_json.encode('utf-8')
            
            handler.send_response(code)
            handler.send_header('Content-Type', 'application/json; charset=utf-8')
            handler.send_header('Content-Length', str(len(error_bytes)))
            handler.send_header('Access-Control-Allow-Origin', '*')
            handler.send_header('Connection', 'close')
            handler.end_headers()
            
            handler.wfile.write(error_bytes)
            handler.wfile.flush()
            
            # 确保连接关闭
            try:
                if hasattr(handler.wfile, 'close'):
                    handler.wfile.close()
                if hasattr(handler, 'connection') and handler.connection:
                    handler.connection.close()
            except:
                pass
        except Exception as e:
            logger.error(f"发送Dify错误响应失败: {str(e)}")
    
    async def _process_mcp_request(self, request_data):
        """处理MCP协议请求 - 完善协议处理逻辑"""
        try:
            method = request_data.get("method")
            request_id = request_data.get("id")
            logger.info(f"[DIFY] 处理MCP请求: method={method}, id={request_id}")
            
            if method == "ping":
                logger.info("[DIFY] 处理ping请求")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"pong": True, "timestamp": time.time()}
                }
            elif method == "initialize":
                logger.info("[DIFY] 处理initialize请求")
                # 解析协议版本参数
                protocol_version = request_data.get("params", {}).get("protocolVersion", "2025-06-18")
                
                # 根据 MCP 协议规范，initialize 响应不应包含 tools 字段
                # 工具列表应通过单独的 tools/list 请求获取
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": protocol_version,
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "logging": {},
                            "roots": {"listChanged": True},
                            "publishDiagnostics": {"relatedInformation": True},
                            "completionProvider": {"resolveProvider": True}
                        },
                        "serverInfo": {
                            "name": "UnityLangPX MCP Server",
                            "version": "1.0.0",
                            "difyCompatible": True
                        }
                    }
                }
                
                logger.info(f"[DIFY] 初始化响应: {response}")
                return response
            elif method in ("tools/list", "tools.list"):
                logger.info(f"[DIFY] 处理{method}请求")
                # 从服务器获取实际注册的工具列表
                try:
                    tools_list = []
                    if self.mcp_server and hasattr(self.mcp_server, 'tool_registry'):
                        import asyncio
                        # 获取工具注册表中的所有工具
                        tools_list = await self.mcp_server.tool_registry.list_tools()
                        logger.info(f"[DIFY] 从工具注册表获取到 {len(tools_list)} 个工具")
                        
                        # 确保工具列表格式正确
                        if tools_list:
                            logger.info(f"[DIFY] 工具列表详情: {tools_list}")
                        else:
                            logger.warning("[DIFY] 工具注册表为空，使用默认工具列表")
                            tools_list = self._get_default_tools()
                    else:
                        logger.warning("[DIFY] 无法访问工具注册表，返回默认工具列表")
                        # 回退到默认工具列表
                        tools_list = self._get_default_tools()
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": tools_list
                        }
                    }
                except Exception as e:
                    logger.error(f"[DIFY] 获取工具列表失败: {str(e)}")
                    import traceback
                    logger.error(f"[DIFY] 错误详情: {traceback.format_exc()}")
                    # 即使失败，也返回基本的工具列表
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": self._get_default_tools()
                        }
                    }
            elif method == "tools/call":
                logger.info("[DIFY] 处理tools/call请求")
                return await self._handle_tool_call(request_data)
            elif method == "tools.call":
                logger.info("[DIFY] 处理tools.call请求")
                return await self._handle_tool_call(request_data)
            elif method == "notifications/initialized":
                # 这是一个通知，不需要响应
                logger.info("[DIFY] 收到初始化通知")
                return None
            else:
                logger.warning(f"[DIFY] 未知方法: {method}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        except Exception as e:
            logger.error(f"处理MCP请求失败: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"处理请求失败: {str(e)}"
                }
            }
    
    async def _handle_tool_call(self, request_data):
        """处理工具调用"""
        try:
            params = request_data.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            request_id = request_data.get("id")
            
            logger.info(f"[DIFY] 调用工具: {tool_name}, 参数: {arguments}")
            
            # 尝试使用工具注册表调用工具
            if self.mcp_server and hasattr(self.mcp_server, 'tool_registry'):
                try:
                    tool = await self.mcp_server.tool_registry.get_tool(tool_name)
                    if tool:
                        logger.info(f"[DIFY] 从工具注册表找到工具: {tool_name}")
                        result = await tool.safe_execute(arguments)
                        
                        if result.success:
                            return {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": str(result.data) if result.data else "工具执行成功".encode('utf-8').decode('utf-8')
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
                                    "message": f"工具执行失败: {result.error}"
                                }
                            }
                    else:
                        logger.warning(f"[DIFY] 工具注册表中未找到工具: {tool_name}")
                except Exception as e:
                    logger.error(f"[DIFY] 从工具注册表调用工具失败: {str(e)}")
            
            # 回退到硬编码的工具处理
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
            logger.error(f"处理工具调用失败: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"工具调用失败: {str(e)}"
                }
            }
    
    def _get_default_tools(self):
        """获取默认工具列表"""
        return [
            {
                "name": "translate_text",
                "description": "翻译文本从源语言到目标语言",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "需要翻译的文本"},
                        "source_lang": {"type": "string", "description": "源语言代码，例如 'en', 'zh'", "default": "en"},
                        "target_lang": {"type": "string", "description": "目标语言代码，例如 'zh', 'en'", "default": "zh"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "translate_file",
                "description": "翻译单个文件，支持Markdown和纯文本文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "需要翻译的文件路径"},
                        "output_path": {"type": "string", "description": "输出文件路径，如果不指定则自动生成"},
                        "source_lang": {"type": "string", "description": "源语言代码，例如 'en', 'zh'", "default": "en"},
                        "target_lang": {"type": "string", "description": "目标语言代码，例如 'zh', 'en'", "default": "zh"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "translate_directory",
                "description": "批量翻译目录中的文件，支持递归处理",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input_directory": {"type": "string", "description": "输入目录路径"},
                        "output_directory": {"type": "string", "description": "输出目录路径"},
                        "file_pattern": {"type": "string", "description": "文件匹配模式，如'*.md'、'*.txt'", "default": "*.md"},
                        "recursive": {"type": "boolean", "description": "是否递归处理子目录", "default": False},
                        "source_lang": {"type": "string", "description": "源语言代码，例如 'en', 'zh'", "default": "en"},
                        "target_lang": {"type": "string", "description": "目标语言代码，例如 'zh', 'en'", "default": "zh"}
                    },
                    "required": ["input_directory", "output_directory"]
                }
            },
            {
                "name": "get_translation_status",
                "description": "查询翻译服务器状态和统计信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query_type": {"type": "string", "description": "查询类型", "enum": ["health", "statistics", "full"], "default": "health"},
                        "verbose": {"type": "boolean", "description": "是否返回详细信息", "default": False}
                    },
                    "required": []
                }
            }
        ]
    
    def get_stats(self):
        """获取统计信息"""
        return {
            **self.stats,
            'active_sessions': len(self.active_sessions)
        }
    
    def cleanup_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session_info in self.active_sessions.items():
            if current_time - session_info['start_time'] > 3600:  # 1小时过期
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        if expired_sessions:
            logger.info(f"清理了 {len(expired_sessions)} 个过期会话")
            self.stats['active_sessions'] = len(self.active_sessions)


class EndpointURLGenerator:
    """端点URL生成器"""
    
    def generate_endpoint_url(self, handler, session_id):
        """生成messages端点URL"""
        try:
            host = handler.headers.get('Host', 'localhost:4010')
            
            # 确保URL格式正确，避免双斜杠问题
            if host.startswith('http://'):
                base_url = host.rstrip('/')
            else:
                base_url = f"http://{host}".rstrip('/')
            
            # 特殊处理：如果无法解析host.docker.internal，使用实际的IP地址
            if 'host.docker.internal' in host:
                logger.info("检测到Dify Docker连接请求")
                try:
                    # 获取本机IP地址
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                    
                    # 替换host.docker.internal为实际IP
                    base_url = base_url.replace('host.docker.internal', local_ip)
                    logger.info(f"将host.docker.internal替换为实际IP: {local_ip}")
                except Exception as e:
                    logger.warning(f"获取本机IP失败，使用原host: {e}")
            
            # 构建messages端点URL - 使用路径型而不是查询参数型
            endpoint_url = f"{base_url}/messages/{session_id}"
            
            # 确保URL格式正确，特别是http://部分
            if not endpoint_url.startswith('http://') and not endpoint_url.startswith('https://'):
                endpoint_url = f"http://{endpoint_url}"
            
            logger.info(f"生成的endpoint URL: {endpoint_url}")
            return endpoint_url
            
        except Exception as e:
            logger.error(f"生成端点URL失败: {str(e)}")
            # 回退到默认URL
            return f"http://192.168.5.9:4010/messages?session_id={session_id}"


class DifyMessageFormatter:
    """Dify消息格式化器"""
    
    def format_response(self, response_data):
        """格式化响应消息"""
        if response_data is None:
            # 对于通知消息，返回None
            return None
        
        # 确保响应符合Dify期望的格式
        if isinstance(response_data, dict):
            # 添加Dify特定的元数据
            if 'result' in response_data and isinstance(response_data['result'], dict):
                response_data['result']['_dify_adapter'] = True
            
            logger.info(f"Dify格式化响应: {response_data}")
            return response_data
        
        return response_data
    
    def format_error_response(self, code, message):
        """格式化错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": code,
                "message": message,
                "_dify_adapter": True
            }
        }