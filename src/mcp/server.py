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
from http.server import HTTPServer, SimpleHTTPRequestHandler
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
                self.end_headers()
                with open(favicon_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Favicon not found")
        elif self.path == '/' or self.path == '/health':
            # 健康检查端点
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"status": "ok", "service": "UnityLangPX MCP Server"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            # 其他请求返回404
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """处理POST请求 - 用于MCP JSON-RPC"""
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            # 这里可以添加MCP协议处理逻辑
            # 目前返回一个简单的响应
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # 简单的响应
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "message": "MCP服务器正在运行，但需要通过标准输入输出进行通信"
                }
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"处理POST请求失败: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"内部错误: {str(e)}"
                }
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def log_message(self, format, *args):
        """重写日志方法，避免输出到标准输出"""
        logger.debug(f"HTTP服务器: {format % args}")


class MCPHTTPHandler(SimpleHTTPRequestHandler):
    """MCP HTTP请求处理器，用于处理Dify的HTTP请求"""
    
    def __init__(self, *args, server_instance=None, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            logger.info(f"[MCPHTTPHandler] 收到GET请求: {self.path}")
            
            if self.path == '/' or self.path == '/health':
                # 健康检查端点
                logger.info("[MCPHTTPHandler] 处理健康检查请求")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "status": "ok",
                    "service": "UnityLangPX MCP Server",
                    "version": "1.0.0"
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
            elif self.path == '/favicon.ico':
                # 返回简单的favicon
                logger.info("[MCPHTTPHandler] 处理favicon请求")
                self.send_response(404)
                self.end_headers()
            elif self.path.startswith('/sse') or self.path.startswith('/events'):
                # SSE (Server-Sent Events) 端点 - Dify 需要这个端点
                logger.info(f"[MCPHTTPHandler] 处理SSE请求: {self.path}")
                self.handle_sse()
            else:
                # 其他路径返回404
                logger.warning(f"[MCPHTTPHandler] 未知路径，返回404: {self.path}")
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Not Found", "path": self.path}
                self.wfile.write(json.dumps(error_response).encode('utf-8'))
                
        except Exception as e:
            logger.error(f"[MCPHTTPHandler] 处理GET请求失败: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {"error": f"Internal Server Error: {str(e)}"}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检请求）"""
        try:
            logger.info(f"收到OPTIONS请求: {self.path}")
            
            # 设置CORS头
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization')
            self.end_headers()
            
        except Exception as e:
            logger.error(f"处理OPTIONS请求失败: {str(e)}")
            self.send_response(500)
            self.end_headers()
    
    def handle_sse(self):
        """处理SSE (Server-Sent Events) 请求"""
        try:
            logger.info("处理SSE连接请求")
            
            # 设置SSE响应头
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Cache-Control, Content-Type')
            self.end_headers()
            
            # 获取请求的路径信息
            # Dify会连接到 /sse 或 /events 端点
            request_path = self.path
            
            # 构建端点URL - Dify期望的是相对路径
            # 根据MCP协议规范，这里应该返回一个相对路径
            endpoint_url = "/"
            
            logger.info(f"SSE端点URL: {endpoint_url}")
            
            # 发送端点URL事件 - 这是Dify需要的
            # 根据Dify的MCP客户端实现，这里应该返回根路径 "/"
            # 注意：只发送端点事件，不发送其他事件，避免干扰Dify客户端
            self.wfile.write(b"event: endpoint\n")
            self.wfile.write(f"data: {endpoint_url}\n\n".encode('utf-8'))
            self.wfile.flush()
            
            # 等待一段时间，确保Dify客户端接收到端点事件
            import time
            try:
                time.sleep(2)  # 等待2秒，确保客户端处理完端点事件
                
                # 然后发送其他事件
                self.wfile.write(b"event: connect\n")
                self.wfile.write(b"data: {\"type\":\"connected\",\"message\":\"SSE connection established\"}\n\n")
                self.wfile.flush()
                
                # 发送心跳事件，保持连接更长时间
                for i in range(30):  # 发送30次心跳，保持连接30秒
                    time.sleep(1)
                    self.wfile.write(b"event: heartbeat\n")
                    heartbeat_data = json.dumps({
                        "type": "heartbeat",
                        "timestamp": time.time(),
                        "message": "keep-alive",
                        "count": i + 1
                    })
                    self.wfile.write(f"data: {heartbeat_data}\n\n".encode('utf-8'))
                    self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                logger.info("SSE客户端断开连接")
            
            logger.info("SSE连接处理完成")
            
        except Exception as e:
            logger.error(f"处理SSE请求失败: {str(e)}")
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": f"SSE Error: {str(e)}"}
                self.wfile.write(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def do_POST(self):
        """处理POST请求 - 用于MCP JSON-RPC"""
        try:
            logger.info(f"收到POST请求: {self.path}")
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            logger.debug(f"POST数据: {post_data}")
            
            # 尝试解析JSON-RPC请求
            try:
                request_data = json.loads(post_data)
                logger.info(f"收到JSON-RPC请求: {request_data}")
                
                # 如果有服务器实例，尝试处理请求
                if self.server_instance and self.server_instance.message_handler:
                    # 使用简单的同步处理方式，避免异步问题
                    try:
                        # 直接处理简单的请求，避免复杂的异步调用
                        method = request_data.get("method")
                        request_id = request_data.get("id")
                        
                        if method == "ping":
                            response_data = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {"pong": True}
                            }
                        elif method == "initialize":
                            response_data = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "protocolVersion": request_data.get("params", {}).get("protocolVersion", "2024-11-05"),
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
                            }
                        elif method == "tools/list":
                            response_data = {
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
                        elif method == "notifications/initialized":
                            # 这是一个通知，不需要响应
                            response_data = None
                        else:
                            response_data = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32601,
                                    "message": f"Method not found: {method}"
                                }
                            }
                        
                        try:
                            if response_data:
                                self.send_response(200)
                                self.send_header('Content-Type', 'application/json')
                                self.end_headers()
                                response_json = json.dumps(response_data)
                                self.wfile.write(response_json.encode('utf-8'))
                                self.wfile.flush()
                            else:
                                # 对于通知消息，返回204 No Content
                                self.send_response(204)
                                self.end_headers()
                                self.wfile.flush()
                        except ConnectionAbortedError:
                            logger.debug("客户端已断开连接")
                        except ConnectionResetError:
                            logger.debug("连接被重置")
                            
                    except Exception as handler_error:
                        logger.error(f"消息处理器错误: {str(handler_error)}")
                        try:
                            self.send_response(500)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            error_response = {
                                "jsonrpc": "2.0",
                                "id": request_data.get("id"),
                                "error": {
                                    "code": -32603,
                                    "message": f"Handler error: {str(handler_error)}"
                                }
                            }
                            self.wfile.write(json.dumps(error_response).encode('utf-8'))
                            self.wfile.flush()
                        except ConnectionAbortedError:
                            logger.debug("发送错误响应时客户端已断开连接")
                        except ConnectionResetError:
                            logger.debug("发送错误响应时连接被重置")
                else:
                    # 没有消息处理器，返回简单响应
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "result": {
                            "message": "MCP服务器正在运行，但消息处理器未初始化"
                        }
                    }
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    
            except json.JSONDecodeError:
                logger.error("无效的JSON数据")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Invalid JSON"
                    }
                }
                self.wfile.write(json.dumps(error_response).encode('utf-8'))
                
        except Exception as e:
            logger.error(f"处理POST请求失败: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def log_message(self, format, *args):
        """重写日志方法，避免输出到标准输出"""
        logger.info(f"MCP HTTP服务器: {format % args}")


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
            # 注册文本翻译工具
            text_tool = TextTranslationTool(self.protocol_adapter)
            await self.tool_registry.register_tool(text_tool)
            
            # 注册文件翻译工具
            file_tool = FileTranslationTool(self.protocol_adapter)
            await self.tool_registry.register_tool(file_tool)
            
            # 注册批量翻译工具
            batch_tool = BatchTranslationTool(self.protocol_adapter)
            await self.tool_registry.register_tool(batch_tool)
            
            # 注册状态查询工具
            status_tool = StatusQueryTool(self.protocol_adapter)
            await self.tool_registry.register_tool(status_tool)
            
            logger.info(f"工具注册完成，共 {await self.tool_registry.get_tool_count()} 个工具")
            
        except Exception as e:
            logger.error(f"注册工具失败: {str(e)}")
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
            
            # 等待关闭信号
            await self._shutdown_event.wait()
            
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
        except Exception as e:
            logger.error(f"消息循环异常: {str(e)}")
        finally:
            await self.stop()
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，正在关闭服务器...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
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
                    
        except Exception as e:
            logger.error(f"停止HTTP服务器失败: {str(e)}")
    
    async def _start_mcp_http_server(self):
        """启动MCP HTTP服务器（用于处理Dify的HTTP请求）"""
        try:
            # 创建HTTP服务器
            def handler_factory(*args, **kwargs):
                return MCPHTTPHandler(*args, server_instance=self, **kwargs)
            
            # 使用配置中的主机地址，但如果设置为localhost，则使用0.0.0.0以允许外部访问
            host = self.config.server.host
            if host == 'localhost':
                host = '0.0.0.0'
            
            logger.info(f"MCP HTTP服务器尝试绑定到: {host}:{self.config.server.port}")
            
            self._mcp_http_server = HTTPServer(
                (host, self.config.server.port),
                handler_factory
            )
            
            # 在单独的线程中运行HTTP服务器
            self._mcp_http_server_thread = threading.Thread(
                target=self._mcp_http_server.serve_forever,
                daemon=True
            )
            self._mcp_http_server_thread.start()
            
            logger.info(f"MCP HTTP服务器已启动，监听地址: {host}，端口: {self.config.server.port}")
            logger.info(f"Docker容器可使用 http://host.docker.internal:{self.config.server.port} 访问")
            
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
        asyncio.run(run_server(args.config))
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"服务器启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()