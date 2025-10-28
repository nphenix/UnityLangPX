"""
Dify兼容的SSE处理器
专门针对Dify的MCP SSE客户端实现优化
"""

import json
import time
import socket
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

class DifyCompatibleSSEHandler:
    """专门为Dify SSE客户端设计的处理器"""
    
    @staticmethod
    def handle_sse_request(handler, server_instance=None):
        """
        处理Dify的SSE请求
        
        Args:
            handler: HTTP请求处理器实例
            server_instance: MCP服务器实例
        """
        try:
            handler.server_instance = server_instance
            
            # 记录请求信息
            handler.logger.info(f"[DifyCompatibleSSEHandler] 处理SSE请求: {handler.path}")
            handler.logger.info(f"请求头: {dict(handler.headers)}")
            
            # 生成session ID
            import uuid
            session_id = str(uuid.uuid4())
            
            # 构建端点URL
            host = handler.headers.get('Host', 'localhost:4010')
            if host.startswith('http://'):
                base_url = host.rstrip('/')
            else:
                base_url = f"http://{host}".rstrip('/')
            
            # Docker特殊处理
            if 'host.docker.internal' in host:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                    base_url = base_url.replace('host.docker.internal', local_ip)
                    handler.logger.info(f"替换host.docker.internal为: {local_ip}")
                except:
                    pass
            
            endpoint_url = f"{base_url}/messages?session_id={session_id}"
            
            handler.logger.info(f"生成的endpoint URL: {endpoint_url}")
            
            # 设置响应头 - 严格遵循HTTP SSE规范
            handler.send_response(200)
            handler.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            handler.send_header('Cache-Control', 'no-cache')
            handler.send_header('Connection', 'keep-alive')  # 使用keep-alive避免连接中断
            handler.send_header('Access-Control-Allow-Origin', '*')
            handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization')
            handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            handler.send_header('X-Content-Type-Options', 'nosniff')
            handler.end_headers()
            
            # 发送SSE数据 - 严格格式
            # 关键修复：使用标准的SSE数据格式
            # 官方规范：event: endpoint\ndata: {"endpoint": "url"}\n\n
            endpoint_data = {
                "endpoint": endpoint_url
            }
            
            sse_data = f"event: endpoint\ndata: {json.dumps(endpoint_data)}\n\n"
            handler.wfile.write(sse_data.encode('utf-8'))
            handler.wfile.flush()
            
            handler.logger.info(f"已发送SSE数据: {sse_data.strip()}")
            
            # 保持连接短暂时间，然后优雅关闭
            time.sleep(0.1)  # 给客户端时间读取数据
            
            # 发送结束标记
            try:
                handler.wfile.write(b"\n")
                handler.wfile.flush()
            except:
                pass
            
            handler.logger.info("SSE响应完成")
            
        except Exception as e:
            handler.logger.error(f"SSE处理失败: {type(e).__name__}: {str(e)}")
            try:
                handler.send_response(500)
                handler.send_header('Content-Type', 'application/json')
                handler.end_headers()
                error_response = {"error": f"SSE处理失败: {str(e)}"}
                handler.wfile.write(json.dumps(error_response).encode('utf-8'))
            except:
                pass


class DifyCompatibleHTTPHandler(BaseHTTPRequestHandler):
    """兼容Dify的HTTP处理器"""
    
    def __init__(self, *args, server_instance=None, **kwargs):
        self.server_instance = server_instance
        self.logger = getattr(server_instance, 'logger', None) or __import__('logging').getLogger(__name__)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            self.logger.info(f"收到GET请求: {self.path}")
            
            if self.path == '/' or self.path == '/health':
                # 健康检查
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {"status": "ok", "service": "UnityLangPX MCP Server", "version": "1.0.0"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            elif self.path == '/sse':
                # SSE端点 - 使用Dify兼容处理器
                DifyCompatibleSSEHandler.handle_sse_request(self, self.server_instance)
                
            else:
                # 404处理
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {"error": "Not Found", "path": self.path}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            self.logger.error(f"GET请求处理失败: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"error": f"Internal Server Error: {str(e)}"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def do_POST(self):
        """处理POST请求"""
        try:
            self.logger.info(f"收到POST请求: {self.path}")
            
            if self.path.startswith('/messages'):
                # Messages端点
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length).decode('utf-8')
                
                self.logger.info(f"收到JSON-RPC请求数据: {post_data[:200]}...")
                
                # 解析JSON-RPC请求
                try:
                    request_data = json.loads(post_data)
                    
                    # 处理请求
                    method = request_data.get("method")
                    request_id = request_data.get("id")
                    
                    if method == "initialize":
                        response_data = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "protocolVersion": "2025-03-26",
                                "capabilities": {
                                    "tools": {"listChanged": True},
                                    "logging": {},
                                    "roots": {"listChanged": True}
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
                                "tools": [{
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
                                }]
                            }
                        }
                    else:
                        response_data = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {method}"
                            }
                        }
                    
                    # 发送响应
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode('utf-8'))
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON解析失败: {e}")
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
                    
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"error": "Not Found", "path": self.path}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            self.logger.error(f"POST请求处理失败: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"error": f"Internal Server Error: {str(e)}"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def do_OPTIONS(self):
        """处理OPTIONS请求"""
        try:
            self.logger.info(f"收到OPTIONS请求: {self.path}")
            
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Cache-Control, Authorization, X-Requested-With')
            self.send_header('Access-Control-Max-Age', '86400')
            self.end_headers()
            
        except Exception as e:
            self.logger.error(f"OPTIONS请求处理失败: {str(e)}")
            self.send_response(500)
            self.end_headers()
    
    def log_message(self, format, *args):
        """日志记录"""
        if self.logger:
            self.logger.info(f"MCP HTTP服务器: {format % args}")
        else:
            super().log_message(format, *args)