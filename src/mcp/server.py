"""
UnityLangPX MCP服务器主模块

实现MCP协议服务器，提供翻译服务接口。
"""

import asyncio
import sys
import json
import signal
import time
import threading
from typing import Optional, Dict, Any
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler, BaseHTTPRequestHandler
import socket

from .config import MCPConfig, load_mcp_config
from .protocol.handler import MessageHandler, create_message_handler
from .protocol.adapter import ProtocolAdapter, create_protocol_adapter
from .tools import (
    ToolRegistry, create_tool_registry,
    TextTranslationTool, FileTranslationTool, 
    BatchTranslationTool, StatusQueryTool
)
from ..core.logger import get_logger, init_logger
from ..core.config import Config

logger = get_logger(__name__)


class FaviconHandler(SimpleHTTPRequestHandler):
    """简单的HTTP请求处理器，专门用于提供favicon.ico"""
    
    def __init__(self, *args, static_dir="static", **kwargs):
        self.static_dir = static_dir
        super().__init__(*args, directory=static_dir, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        if self.path == '/favicon.ico':
            # 提供favicon.ico文件
            favicon_path = Path(self.static_dir) / 'favicon.ico'
            if favicon_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'image/x-icon')
                self.send_header('Content-Length', str(favicon_path.stat().st_size))
                self.send_header('Connection', 'close')
                self.end_headers()
                with open(favicon_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', '0')
                self.send_header('Connection', 'close')
                self.end_headers()
        elif self.path == '/' or self.path == '/health':
            # 健康检查端点
            response = {"status": "ok", "service": "UnityLangPX MCP Server"}
            response_json = json.dumps(response)
            response_bytes = response_json.encode('utf-8')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(response_bytes)
        else:
            # 其他请求返回404
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
    
    def do_POST(self):
        """处理POST请求 - 用于MCP JSON-RPC"""
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            # 这里可以添加MCP协议处理逻辑
            # 目前返回一个简单的响应
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "message": "MCP服务器正在运行，但需要通过标准输入输出进行通信"
                }
            }
            response_json = json.dumps(response)
            response_bytes = response_json.encode('utf-8')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(response_bytes)
            
        except Exception as e:
            logger.error(f"处理POST请求失败: {str(e)}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"内部错误: {str(e)}"
                }
            }
            error_json = json.dumps(error_response)
            error_bytes = error_json.encode('utf-8')
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(error_bytes)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(error_bytes)
    
    def log_message(self, format, *args):
        """重写日志方法，避免输出到标准输出"""
        logger.debug(f"HTTP服务器: {format % args}")


from .smart_router import SmartRouter

class MCPHTTPHandler(BaseHTTPRequestHandler):
    """MCP HTTP请求处理器，集成智能路由"""
    
    def __init__(self, *args, server_instance=None, **kwargs):
        self.server_instance = server_instance
        self.logger = getattr(server_instance, 'logger', None) or __import__('logging').getLogger(__name__)
        
        # 初始化智能路由器
        if server_instance:
            self.smart_router = SmartRouter(server_instance)
        else:
            self.smart_router = None
            
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            logger.info("=" * 50)
            logger.info(f"[MCPHTTPHandler] 收到GET请求: {self.path}")
            logger.info(f"[MCPHTTPHandler] 客户端地址: {self.client_address}")
            logger.info(f"[MCPHTTPHandler] 请求头: {dict(self.headers)}")
            
            # 特殊处理健康检查请求
            if self.path == '/' or self.path == '/health':
                logger.info("[MCPHTTPHandler] 处理健康检查请求")
                self._handle_default_get()
                return
            
            # 检查服务器实例状态
            if not self.server_instance:
                logger.error(f"[MCPHTTPHandler] 服务器实例状态: 异常 - server_instance为None")
                self._send_error_response(502, "Bad Gateway: Server instance not available")
                return
            
            if self.smart_router:
                logger.info("[MCPHTTPHandler] 使用智能路由器处理请求")
                # 使用智能路由器处理请求
                if self.path.startswith('/sse') or self.path.startswith('/events'):
                    logger.info("[MCPHTTPHandler] 路由到SSE处理器")
                    try:
                        import asyncio
                        asyncio.run(self.smart_router.route_request(self, 'sse'))
                        logger.info("[MCPHTTPHandler] SSE处理器执行完成")
                    except Exception as sse_error:
                        logger.error(f"[MCPHTTPHandler] SSE处理失败: {str(sse_error)}")
                        import traceback
                        logger.error(f"[MCPHTTPHandler] SSE错误详情: {traceback.format_exc()}")
                        self._send_error_response(502, f"Bad Gateway: SSE processing failed: {str(sse_error)}")
                else:
                    logger.info("[MCPHTTPHandler] 路由到HTTP处理器")
                    import asyncio
                    asyncio.run(self.smart_router.route_request(self, 'http'))
            else:
                logger.warning("[MCPHTTPHandler] 智能路由器不可用，使用默认处理")
                # 回退到原有逻辑
                self._handle_default_get()
                
        except Exception as e:
            logger.error(f"[MCPHTTPHandler] 处理GET请求失败: {str(e)}")
            import traceback
            logger.error(f"[MCPHTTPHandler] 错误详情: {traceback.format_exc()}")
            self._send_error_response(502, f"Bad Gateway: {str(e)}")
    
    def do_OPTIONS(self):
        """处理OPTIONS请求"""
        try:
            self.logger.info(f"收到OPTIONS请求: {self.path}")
            self.logger.info(f"OPTIONS请求头: {dict(self.headers)}")
            
            # 设置CORS头
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization, X-Requested-With')
            self.send_header('Access-Control-Max-Age', '86400')
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            self.logger.info("OPTIONS请求处理完成")
            
        except Exception as e:
            self.logger.error(f"处理OPTIONS请求失败: {str(e)}")
            self._send_error_response(500, f"Internal Server Error: {str(e)}")
    
    def handle_sse(self):
        """处理SSE (Server-Sent Events) 请求"""
        try:
            logger.info("处理SSE连接请求")
            
            # 记录详细的请求信息
            host = self.headers.get('Host', 'localhost:4010')
            origin = self.headers.get('Origin', 'unknown')
            auth_header = self.headers.get('Authorization', '')
            user_agent = self.headers.get('User-Agent', '')
            
            logger.info(f"SSE请求详情:")
            logger.info(f"  Host: {host}")
            logger.info(f"  Origin: {origin}")
            logger.info(f"  Authorization: {auth_header[:20]}..." if len(auth_header) > 20 else f"  Authorization: {auth_header}")
            logger.info(f"  User-Agent: {user_agent}")
            
            # 检查授权（如果启用）
            if self.server_instance and hasattr(self.server_instance, 'config') and self.server_instance.config.security.enable_auth:
                if not auth_header or not auth_header.startswith('Bearer '):
                    logger.warning(f"授权失败：缺少或无效的Authorization头")
                    error_response = {"error": "Unauthorized: Missing or invalid Bearer token"}
                    error_json = json.dumps(error_response)
                    error_bytes = error_json.encode('utf-8')
                    
                    self.send_response(401)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(error_bytes)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(error_bytes)
                    return
                
                # 这里可以添加更详细的token验证逻辑
                token = auth_header[7:]  # 移除 "Bearer " 前缀
                expected_token = self.server_instance.config.security.api_key
                if token != expected_token:
                    logger.warning(f"授权失败：token不匹配")
                    error_response = {"error": "Unauthorized: Invalid token"}
                    error_json = json.dumps(error_response)
                    error_bytes = error_json.encode('utf-8')
                    
                    self.send_response(401)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(error_bytes)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(error_bytes)
                    return
                
                logger.info("授权验证通过")
            
            # 生成session ID
            import uuid
            session_id = str(uuid.uuid4())
            
            # 构建端点URL - 根据MCP SSE协议规范，需要返回完整的绝对URL
            # 使用Host头或回退到默认值
            
            # 确保URL格式正确，避免双斜杠问题
            if host.startswith('http://'):
                base_url = host.rstrip('/')
            else:
                base_url = f"http://{host}".rstrip('/')
            
            # 特殊处理：如果无法解析host.docker.internal，使用实际的IP地址
            if 'host.docker.internal' in host:
                logger.info("检测到Dify Docker连接请求")
                # 尝试使用实际的IP地址替代
                try:
                    # 获取本机IP地址
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                    
                    # 替换host.docker.internal为实际IP
                    base_url = base_url.replace('host.docker.internal', local_ip)
                    logger.info(f"将host.docker.internal替换为实际IP: {local_ip}")
                except Exception as e:
                    logger.warning(f"获取本机IP失败，使用原host: {e}")
            
            # 构建messages端点URL - 确保格式正确
            endpoint_url = f"{base_url}/messages?session_id={session_id}"
            
            logger.info(f"SSE端点URL: {endpoint_url}")
            
            # 设置SSE响应头 - 修复：使用keep-alive而不是close，添加charset
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Connection', 'keep-alive')  # 修复：使用keep-alive保持连接
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Cache-Control, Content-Type, Authorization')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            # 添加额外的头帮助Dify识别
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Accel-Buffering', 'no')
            
            # 关键修复：强制使用HTTP/1.1协议，支持持久连接
            if hasattr(self, 'protocol_version'):
                self.protocol_version = "HTTP/1.1"
            
            # 关键修复：必须调用end_headers()来完成HTTP响应头的发送
            self.end_headers()
            logger.info(f"SSE响应头设置完成: 使用Connection=keep-alive, HTTP/1.1")
            
            # 根据MCP SSE协议规范，只发送endpoint事件
            # 针对Dify的特殊处理：确保格式完全符合预期
            logger.info("准备发送endpoint事件给Dify")
            
            # 发送endpoint事件 - 严格遵循SSE格式，使用\r\n作为行结束符
            endpoint_data = f"event: endpoint\r\ndata: {endpoint_url}\r\n\r\n"
            self.wfile.write(endpoint_data.encode('utf-8'))
            self.wfile.flush()
            logger.info(f"已发送endpoint数据: {repr(endpoint_data)}")
            
            # 修复：保持SSE连接并发送简单心跳，而不是立即完成
            logger.info("SSE连接处理完成，endpoint已发送，开始保持连接和心跳")
            
            # 保持连接并发送心跳
            try:
                # 保持连接并定期发送简单心跳
                while True:
                    try:
                        # 每15秒发送一次简单心跳
                        time.sleep(15)
                        heartbeat_data = ": ping\n\n"
                        self.wfile.write(heartbeat_data.encode('utf-8'))
                        self.wfile.flush()
                        logger.debug(f"SSE发送心跳")
                    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                        logger.info(f"SSE客户端断开连接: {str(e)}")
                        break
                    except Exception as e:
                        logger.error(f"SSE发送心跳失败: {str(e)}")
                        break
                        
            except Exception as e:
                logger.warning(f"SSE保持连接失败: {str(e)}")
            
            logger.info("SSE连接已结束")
            
        except Exception as e:
            logger.error(f"处理SSE请求失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            try:
                error_response = {"error": f"SSE Error: {str(e)}"}
                error_json = json.dumps(error_response)
                error_bytes = error_json.encode('utf-8')
                
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(error_bytes)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(error_bytes)
                self.wfile.flush()
                
                # 确保连接关闭
                try:
                    if hasattr(self.wfile, 'close'):
                        self.wfile.close()
                    if hasattr(self, 'connection') and self.connection:
                        self.connection.close()
                except:
                    pass
            except:
                pass
    
    def do_POST(self):
        """处理POST请求"""
        try:
            logger.info("=" * 50)
            logger.info(f"[MCPHTTPHandler] 收到POST请求: {self.path}")
            logger.info(f"[MCPHTTPHandler] 客户端地址: {self.client_address}")
            logger.info(f"[MCPHTTPHandler] 请求头: {dict(self.headers)}")
            
            # 记录Content-Length
            content_length = self.headers.get('Content-Length', '0')
            logger.info(f"[MCPHTTPHandler] Content-Length: {content_length}")
            
            # 检查连接状态
            if hasattr(self, 'connection') and self.connection:
                logger.info(f"[MCPHTTPHandler] 连接状态: {self.connection}")
            
            # 记录请求体数据
            if content_length != '0':
                try:
                    post_data = self.rfile.read(int(content_length)).decode('utf-8')
                    logger.info(f"[MCPHTTPHandler] 请求体数据: {repr(post_data)}")
                except Exception as e:
                    logger.error(f"[MCPHTTPHandler] 读取请求体失败: {str(e)}")
                    post_data = ""
            else:
                post_data = ""
                logger.info("[MCPHTTPHandler] 空请求体")
            
            # 检查服务器实例状态
            if self.server_instance:
                logger.info(f"[MCPHTTPHandler] 服务器实例状态: 正常")
            else:
                logger.error(f"[MCPHTTPHandler] 服务器实例状态: 异常 - server_instance为None")
                self._send_error_response(502, "Bad Gateway: Server instance not available")
                return
            
            if self.smart_router:
                logger.info("[MCPHTTPHandler] 使用智能路由器处理请求")
                # 使用智能路由器处理请求
                if self.path.startswith('/messages'):
                    logger.info("[MCPHTTPHandler] 路由到message处理器")
                    try:
                        # 将已读取的数据传递给适配器
                        import asyncio
                        asyncio.run(self.smart_router.route_request(self, 'message', post_data=post_data))
                        logger.info("[MCPHTTPHandler] message处理器执行完成")
                    except Exception as route_error:
                        logger.error(f"[MCPHTTPHandler] message路由处理失败: {str(route_error)}")
                        import traceback
                        logger.error(f"[MCPHTTPHandler] 路由错误详情: {traceback.format_exc()}")
                        self._send_error_response(502, f"Bad Gateway: Route processing failed: {str(route_error)}")
                else:
                    logger.info("[MCPHTTPHandler] 路由到http处理器")
                    import asyncio
                    asyncio.run(self.smart_router.route_request(self, 'http'))
            else:
                logger.warning("[MCPHTTPHandler] 智能路由器不可用，使用默认处理")
                # 回退到原有逻辑
                self._handle_default_post()
                
        except Exception as e:
            logger.error(f"[MCPHTTPHandler] 处理POST请求失败: {str(e)}")
            import traceback
            logger.error(f"[MCPHTTPHandler] 错误详情: {traceback.format_exc()}")
            self._send_error_response(502, f"Bad Gateway: {str(e)}")
    
    def log_message(self, format, *args):
        """重写日志方法，避免输出到标准输出"""
        if self.logger:
            self.logger.info(f"MCP HTTP服务器: {format % args}")
        else:
            super().log_message(format, args)
    
    def _handle_default_get(self):
        """默认GET处理逻辑"""
        if self.path == '/' or self.path == '/health':
            response = {
                "status": "ok",
                "service": "UnityLangPX MCP Server",
                "version": "1.0.0",
                "adapter": "default"
            }
            response_json = json.dumps(response)
            response_bytes = response_json.encode('utf-8')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            self.wfile.write(response_bytes)
            self.wfile.flush()
            
            # 确保连接关闭
            try:
                if hasattr(self.wfile, 'close'):
                    self.wfile.close()
                if hasattr(self, 'connection') and self.connection:
                    self.connection.close()
            except:
                pass
        elif self.path == '/favicon.ico':
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
        else:
            self._send_error_response(404, "Not Found")
    
    def _handle_default_post(self):
        """默认POST处理逻辑"""
        self._send_error_response(404, "Not Found")
    
    def _send_error_response(self, code, message):
        """发送错误响应"""
        try:
            error_response = {"error": message}
            error_json = json.dumps(error_response)
            error_bytes = error_json.encode('utf-8')
            
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(error_bytes)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            self.wfile.write(error_bytes)
            self.wfile.flush()
            
            # 确保连接关闭
            try:
                if hasattr(self.wfile, 'close'):
                    self.wfile.close()
                if hasattr(self, 'connection') and self.connection:
                    self.connection.close()
            except:
                pass
        except Exception as e:
            if self.logger:
                self.logger.error(f"发送错误响应失败: {str(e)}")
    


class MCPServer:
    """MCP服务器"""
    
    def __init__(self, config: Optional[MCPConfig] = None):
        """
        初始化MCP服务器
        
        Args:
            config: MCP配置对象
        """
        self.config = config or load_mcp_config()
        self.core_config = self.config.get_core_config()
        
        # 初始化日志系统
        log_config = self.core_config.logging
        init_logger(log_config)
        
        # 初始化组件
        self.tool_registry: Optional[ToolRegistry] = None
        self.protocol_adapter: Optional[ProtocolAdapter] = None
        self.message_handler: Optional[MessageHandler] = None
        
        # 初始化翻译器
        self.translator = None
        
        # 服务器状态
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # HTTP服务器相关
        self._http_server: Optional[HTTPServer] = None
        self._http_server_thread: Optional[threading.Thread] = None
        self._mcp_http_server: Optional[HTTPServer] = None
        self._mcp_http_server_thread: Optional[threading.Thread] = None
        
        # 统计信息
        self._start_time = None
        self._request_count = 0
        
        logger.info("MCP服务器初始化完成")
    
    async def initialize(self):
        """初始化服务器组件"""
        try:
            logger.info("初始化MCP服务器组件...")
            
            # 初始化翻译器
            from ..core.translator import Translator
            self.translator = Translator(self.core_config)
            logger.info("翻译器初始化完成")
            
            # 初始化工具注册表
            self.tool_registry = create_tool_registry()
            
            # 初始化协议适配器
            self.protocol_adapter = create_protocol_adapter(
                self.core_config,
                self.tool_registry
            )
            
            # 初始化消息处理器
            self.message_handler = create_message_handler(self.protocol_adapter)
            
            # 注册工具
            await self._register_tools()
            
            # 添加中间件
            await self._add_middleware()
            
            logger.info("MCP服务器组件初始化完成")
            
        except Exception as e:
            logger.error(f"初始化服务器组件失败: {str(e)}")
            raise
    
    async def _register_tools(self):
        """注册工具"""
        try:
            logger.info("开始注册MCP工具...")
            
            # 确保工具注册表已初始化
            if not self.tool_registry:
                logger.error("工具注册表未初始化")
                return
            
            # 注册文本翻译工具
            text_tool = TextTranslationTool(self.protocol_adapter)
            await self.tool_registry.register_tool(text_tool)
            logger.info(f"注册工具: {text_tool.name}")
            
            # 注册文件翻译工具
            file_tool = FileTranslationTool(self.protocol_adapter)
            await self.tool_registry.register_tool(file_tool)
            logger.info(f"注册工具: {file_tool.name}")
            
            # 注册批量翻译工具
            batch_tool = BatchTranslationTool(self.protocol_adapter)
            await self.tool_registry.register_tool(batch_tool)
            logger.info(f"注册工具: {batch_tool.name}")
            
            # 注册状态查询工具
            status_tool = StatusQueryTool(self.protocol_adapter)
            await self.tool_registry.register_tool(status_tool)
            logger.info(f"注册工具: {status_tool.name}")
            
            # 验证工具注册
            tool_count = await self.tool_registry.get_tool_count()
            tool_names = await self.tool_registry.get_tool_names()
            logger.info(f"工具注册完成，共 {tool_count} 个工具: {tool_names}")
            
            # 验证工具定义
            validation_result = await self.tool_registry.validate_tools()
            if validation_result["invalid"]:
                logger.warning(f"发现 {len(validation_result['invalid'])} 个无效工具: {validation_result['invalid']}")
            else:
                logger.info("所有工具验证通过")
            
        except Exception as e:
            logger.error(f"注册工具失败: {str(e)}")
            import traceback
            logger.error(f"工具注册错误详情: {traceback.format_exc()}")
            raise
    
    async def _add_middleware(self):
        """添加中间件"""
        try:
            # 添加请求日志中间件
            async def request_logging_middleware(request):
                self._request_count += 1
                logger.debug(f"处理请求 #{self._request_count}: {request.method}")
            
            # 添加认证中间件（如果启用）
            if self.config.security.enable_auth:
                async def auth_middleware(request):
                    # 这里可以实现认证逻辑
                    pass
                
                self.message_handler.add_middleware(auth_middleware)
            
            # 添加限流中间件（如果启用）
            if self.config.security.rate_limit > 0:
                async def rate_limit_middleware(request):
                    # 这里可以实现限流逻辑
                    pass
                
                self.message_handler.add_middleware(rate_limit_middleware)
            
            self.message_handler.add_middleware(request_logging_middleware)
            logger.info("中间件添加完成")
            
        except Exception as e:
            logger.error(f"添加中间件失败: {str(e)}")
            raise
    
    async def start(self):
        """启动服务器"""
        try:
            if self._running:
                logger.warning("服务器已在运行")
                return
            
            # 初始化组件
            await self.initialize()
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            # 启动服务器
            self._running = True
            self._start_time = time.time()
            
            # 获取本机IP地址
            import socket
            try:
                # 获取本机IP地址 - 连接到外部地址获取实际IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # 连接到一个公共DNS服务器地址，这不会实际发送数据
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                # 如果失败，尝试获取所有网络接口
                try:
                    hostname = socket.gethostname()
                    local_ip = socket.gethostbyname(hostname)
                except Exception:
                    local_ip = "localhost"
            
            # 启动HTTP服务器（如果启用）
            if self.config.server.enable_http_server:
                await self._start_http_server()
            
            # 启动MCP HTTP服务器（用于处理Dify的HTTP请求）
            await self._start_mcp_http_server()
            
            # 显示服务地址
            server_address = f"http://{local_ip}:{self.config.server.port}"
            http_address = f"http://{local_ip}:{self.config.server.http_port}" if self.config.server.enable_http_server else "未启用"
            docker_address = f"http://host.docker.internal:{self.config.server.port}"
            console_message = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UnityLangPX MCP 服务器                        ║
╠══════════════════════════════════════════════════════════════╣
║  状态: 运行中                                                   ║
║  HTTP服务地址: {server_address:<49} ║
║  favicon地址: {http_address+'/favicon.ico':<39} ║
║  Docker访问地址: {docker_address:<43} ║
║  主端口: {self.config.server.port:<55} ║
║  favicon端口: {self.config.server.http_port if self.config.server.enable_http_server else 'N/A':<51} ║
║  主机: {self.config.server.host:<55} ║
║  协议: HTTP (Dify集成) + MCP (标准输入输出)                     ║
╚══════════════════════════════════════════════════════════════╝
"""
            print(console_message)
            logger.info(f"MCP服务器已启动，支持HTTP和标准输入输出")
            logger.info(f"HTTP服务地址: {server_address}")
            logger.info(f"Docker容器访问地址: {docker_address}")
            if self.config.server.enable_http_server:
                logger.info(f"favicon地址: {http_address}/favicon.ico")
            
            # 开始处理消息（在后台运行）
            # 不阻塞主线程，让HTTP服务器能够继续处理请求
            logger.info("MCP服务器已启动，等待消息...")
            
            # 等待关闭信号，添加异常处理以支持Ctrl+C
            try:
                # 使用更简单的方式等待关闭信号
                while self._running and not self._shutdown_event.is_set():
                    try:
                        # 使用短超时，这样可以定期检查状态
                        await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                        break
                    except asyncio.TimeoutError:
                        # 超时是正常的，继续循环
                        continue
            except KeyboardInterrupt:
                logger.info("收到键盘中断信号，正在关闭服务器...")
                self._running = False
                self._shutdown_event.set()
            except Exception as e:
                logger.info(f"收到关闭信号: {str(e)}")
                self._running = False
                self._shutdown_event.set()
            except asyncio.CancelledError:
                logger.info("启动任务被取消，正在关闭服务器...")
                self._running = False
                self._shutdown_event.set()
            
        except Exception as e:
            logger.error(f"启动服务器失败: {str(e)}")
            raise
    
    async def _run_message_loop(self):
        """运行消息循环"""
        try:
            while self._running and not self._shutdown_event.is_set():
                # 从标准输入读取消息
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                
                if not line:
                    # EOF，停止服务器
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # 处理消息
                    response = await self.message_handler.handle_message(line)
                    
                    if response:
                        # 发送响应到标准输出
                        print(response, flush=True)
                
                except Exception as e:
                    logger.error(f"处理消息失败: {str(e)}")
                    # 发送错误响应
                    error_response = json.dumps({
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32603,
                            "message": str(e)
                        }
                    }, ensure_ascii=False)
                    print(error_response, flush=True)
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭服务器...")
            self._running = False
            self._shutdown_event.set()
        except Exception as e:
            logger.error(f"消息循环异常: {str(e)}")
            self._running = False
            self._shutdown_event.set()
        finally:
            await self.stop()
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，正在关闭服务器...")
            # 设置停止标志
            self._running = False
            self._shutdown_event.set()
            
            # 创建新的事件循环来处理关闭
            try:
                # 获取当前事件循环
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果循环正在运行，创建任务来关闭服务器
                    loop.create_task(self.stop())
                else:
                    # 如果循环没有运行，直接运行关闭任务
                    loop.run_until_complete(self.stop())
            except Exception as e:
                logger.error(f"信号处理失败: {str(e)}")
                # 强制退出
                import sys
                sys.exit(0)
            finally:
                # 确保进程退出
                import sys
                sys.exit(0)
        
        # 设置信号处理器
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # 在某些环境中（如Windows），可能无法设置信号处理器
            logger.warning("无法设置信号处理器，将使用默认的异常处理")
    
    async def stop(self):
        """停止服务器"""
        try:
            if not self._running:
                return
            
            logger.info("正在停止MCP服务器...")
            
            # 设置停止标志
            self._running = False
            self._shutdown_event.set()
            
            # 停止HTTP服务器
            await self._stop_http_server()
            
            # 停止MCP HTTP服务器
            await self._stop_mcp_http_server()
            
            # 关闭协议适配器
            if self.protocol_adapter:
                await self.protocol_adapter.close()
            
            # 计算运行时间
            uptime = 0.0
            if self._start_time:
                uptime = time.time() - self._start_time
            
            # 显示停止消息
            console_message = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UnityLangPX MCP 服务器                        ║
╠══════════════════════════════════════════════════════════════╣
║  状态: 已停止                                                   ║
║  运行时间: {uptime:.2f} 秒{' ' * (44 - len(f'{uptime:.2f} 秒'))}║
║  处理请求: {self._request_count} 个{' ' * (44 - len(f'{self._request_count} 个'))}║
╚══════════════════════════════════════════════════════════════╝
"""
            print(console_message)
            logger.info(f"MCP服务器已停止，运行时间: {uptime:.2f}秒，处理请求: {self._request_count}个")
            
        except Exception as e:
            logger.error(f"停止服务器失败: {str(e)}")
    
    async def _start_http_server(self):
        """启动HTTP服务器"""
        try:
            # 创建HTTP服务器
            def handler_factory(*args, **kwargs):
                return FaviconHandler(*args, static_dir=self.config.server.static_dir, **kwargs)
            
            self._http_server = HTTPServer(
                (self.config.server.host, self.config.server.http_port),
                handler_factory
            )
            
            # 在单独的线程中运行HTTP服务器
            self._http_server_thread = threading.Thread(
                target=self._http_server.serve_forever,
                daemon=True
            )
            self._http_server_thread.start()
            
            logger.info(f"HTTP服务器已启动，地址: http://{self.config.server.host}:{self.config.server.http_port}/favicon.ico")
            
        except Exception as e:
            logger.error(f"启动HTTP服务器失败: {str(e)}")
            # 不抛出异常，允许MCP服务器继续运行
    
    async def _stop_http_server(self):
        """停止HTTP服务器"""
        try:
            if self._http_server:
                self._http_server.shutdown()
                self._http_server.server_close()
                logger.info("HTTP服务器已停止")
                
                # 等待线程结束
                if self._http_server_thread and self._http_server_thread.is_alive():
                    self._http_server_thread.join(timeout=5)
                    if self._http_server_thread.is_alive():
                        logger.warning("HTTP服务器线程未能在超时时间内停止")
                    
        except Exception as e:
            logger.error(f"停止HTTP服务器失败: {str(e)}")
    
    async def _start_mcp_http_server(self):
        """启动MCP HTTP服务器（用于处理Dify的HTTP请求）"""
        try:
            # 创建HTTP服务器
            def handler_factory(*args, **kwargs):
                logger.info(f"[MCPHTTPServer] 创建处理器实例，server_instance={self}")
                return MCPHTTPHandler(*args, server_instance=self, **kwargs)
            
            # 获取本机IP地址
            try:
                import socket as sock
                s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                logger.info(f"检测到本机IP地址: {local_ip}")
            except Exception as e:
                logger.warning(f"获取本机IP失败: {str(e)}")
                local_ip = "192.168.5.9"  # 使用诊断结果中的IP
            
            # 使用配置中的主机地址，但如果设置为localhost，则使用实际IP地址
            host = self.config.server.host
            if host == 'localhost' or host == '0.0.0.0':
                # 优先使用实际IP地址，确保Docker可以访问
                host = local_ip
                logger.info(f"将localhost/0.0.0.0替换为实际IP: {host}")
            
            logger.info(f"MCP HTTP服务器尝试绑定到: {host}:{self.config.server.port}")
            logger.info(f"网络配置详情:")
            logger.info(f"  - 原始host配置: {self.config.server.host}")
            logger.info(f"  - 实际绑定host: {host}")
            logger.info(f"  - 端口: {self.config.server.port}")
            logger.info(f"  - Docker访问地址: http://host.docker.internal:{self.config.server.port}")
            logger.info(f"  - 局域网访问地址: http://{local_ip}:{self.config.server.port}")
            
            try:
                # 修复：设置socket选项，允许地址重用，避免绑定失败
                self._mcp_http_server = HTTPServer(
                    (host, self.config.server.port),
                    handler_factory
                )
                
                # 设置更长的超时时间，避免Dify请求超时
                self._mcp_http_server.timeout = 300
                self._mcp_http_server.socket.settimeout(300)
                # 修复：设置socket选项，允许地址重用
                import socket as sock
                self._mcp_http_server.socket.setsockopt(sock.SOL_SOCKET, sock.SO_REUSEADDR, 1)
                
                # 关键修复：强制使用HTTP/1.1协议，支持持久连接
                self._mcp_http_server.protocol_version = "HTTP/1.1"
                
                # 在单独的线程中运行HTTP服务器
                self._mcp_http_server_thread = threading.Thread(
                    target=self._mcp_http_server.serve_forever,
                    daemon=True
                )
                self._mcp_http_server_thread.start()
                
                logger.info(f"MCP HTTP服务器已启动，监听地址: {host}，端口: {self.config.server.port}")
                logger.info(f"Docker容器可使用 http://host.docker.internal:{self.config.server.port} 访问")
                
                # 验证服务器是否真正启动
                import time
                time.sleep(1)  # 给服务器一点时间启动
                
                # 检查端口是否真正监听
                import socket as sock
                try:
                    test_socket = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
                    test_socket.settimeout(5)
                    result = test_socket.connect_ex((host, self.config.server.port))
                    test_socket.close()
                    
                    if result == 0:
                        logger.info(f"✓ 端口 {self.config.server.port} 验证成功，服务器正在监听")
                    else:
                        logger.error(f"✗ 端口 {self.config.server.port} 验证失败，错误代码: {result}")
                        logger.error("这可能是502错误的原因：服务器未正确绑定到端口")
                except Exception as e:
                    logger.error(f"端口验证失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"启动MCP HTTP服务器失败: {str(e)}")
                logger.error(f"这可能是502错误的原因：无法绑定到 {host}:{self.config.server.port}")
                raise
            
        except Exception as e:
            logger.error(f"启动MCP HTTP服务器失败: {str(e)}")
            raise
    
    async def _stop_mcp_http_server(self):
        """停止MCP HTTP服务器"""
        try:
            if self._mcp_http_server:
                self._mcp_http_server.shutdown()
                self._mcp_http_server.server_close()
                logger.info("MCP HTTP服务器已停止")
                
                # 等待线程结束
                if self._mcp_http_server_thread and self._mcp_http_server_thread.is_alive():
                    self._mcp_http_server_thread.join(timeout=5)
                    if self._mcp_http_server_thread.is_alive():
                        logger.warning("MCP HTTP服务器线程未能在超时时间内停止")
                    
        except Exception as e:
            logger.error(f"停止MCP HTTP服务器失败: {str(e)}")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        获取服务器状态
        
        Returns:
            服务器状态信息
        """
        try:
            status = {
                "running": self._running,
                "uptime": time.time() - self._start_time if self._start_time else 0,
                "request_count": self._request_count,
                "config": {
                    "server": self.config.server.model_dump(),
                    "tools": self.config.tools.model_dump(),
                    "security": self.config.security.model_dump()
                }
            }
            
            # 添加健康状态
            if self.protocol_adapter:
                health = await self.protocol_adapter.get_health_status()
                status["health"] = health
            
            return status
            
        except Exception as e:
            logger.error(f"获取服务器状态失败: {str(e)}")
            return {
                "running": self._running,
                "error": str(e)
            }
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        asyncio.create_task(self.stop())


# 便捷函数
async def run_server(config_file: Optional[str] = None, **kwargs):
    """
    运行MCP服务器
    
    Args:
        config_file: 配置文件路径
        **kwargs: 额外的配置参数
    """
    # 加载配置
    config = load_mcp_config(config_file, **kwargs)
    
    # 验证配置
    config.validate()
    
    # 创建并启动服务器
    server = MCPServer(config)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行异常: {str(e)}")
    finally:
        await server.stop()


def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="UnityLangPX MCP服务器")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--log-level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.log_level:
        import os
        os.environ["UNITYLANGPX_MCP_LOG_LEVEL"] = args.log_level
    
    # 运行服务器
    try:
        # 设置事件循环策略，确保在Windows上也能正常工作
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # 直接运行服务器，使用最简单的方式
        asyncio.run(run_server(args.config))
            
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止服务器...")
        print("服务器已停止")
    except Exception as e:
        print(f"服务器启动失败: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        sys.exit(1)


async def main_with_checks(config_file=None, mode="sse", **kwargs):
    """带检查的主函数，用于启动脚本"""
    # 导入检查函数
    from pathlib import Path
    import sys
    
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # 导入检查函数
    from scripts.run_mcp_server import check_dependencies, create_directories, check_ollama_service
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 创建必要目录
    create_directories()
    
    # 检查Ollama服务
    ollama_available = check_ollama_service()
    if not ollama_available:
        logger.warning("Ollama服务不可用，翻译功能可能无法正常工作")
    
    # 设置环境变量，确保服务器监听正确接口
    if mode == "sse":
        # 对于SSE模式，监听所有接口，允许Docker连接
        import os
        os.environ["UNITYLANGPX_MCP_HOST"] = "0.0.0.0"
        os.environ["UNITYLANGPX_MCP_PORT"] = "4010"
        logger.info("SSE模式: 服务器将监听所有接口 (0.0.0.0:4010)")
        logger.info("Docker容器可使用 http://host.docker.internal:4010 访问")
    
    # 运行服务器
    try:
        logger.info(f"准备运行服务器，配置文件: {config_file}")
        
        # 确保配置文件路径正确
        if config_file and not Path(config_file).exists():
            logger.warning(f"配置文件不存在: {config_file}")
            # 尝试使用默认配置
            config_file = None
        
        await run_server(config_file, **kwargs)
    except Exception as e:
        logger.error(f"服务器运行失败: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()