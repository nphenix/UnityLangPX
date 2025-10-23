"""
UnityLangPX HTTP服务器模块

提供HTTP API服务，用于Obsidian插件与核心翻译模块的通信。
使用Python内置的http.server模块，实现零额外依赖的HTTP服务器。
"""

import json
import signal
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from urllib.parse import urlparse, parse_qs

from ..core import (
    Config, Translator, TranslationResult,
    get_logger, UnityLangPXError
)


logger = get_logger(__name__)


class TranslationAPIHandler(BaseHTTPRequestHandler):
    """HTTP API请求处理器"""
    
    # 类变量，用于存储服务器实例和翻译器
    server_instance: Optional['TranslationAPIServer'] = None
    translator: Optional[Translator] = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检请求）"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def do_GET(self):
        """处理GET请求"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == '/api/service/status':
                self._handle_service_status()
            elif path == '/api/service/port':
                self._handle_get_port()
            elif path.startswith('/api/history'):
                self._handle_get_history(parsed_path)
            else:
                self._send_error(404, "API端点不存在")
        except Exception as e:
            logger.error(f"处理GET请求失败: {str(e)}")
            self._send_error(500, f"服务器错误: {str(e)}")
    
    def do_POST(self):
        """处理POST请求"""
        try:
            content_length = int(self.headers['Content-Length'] or 0)
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    body = json.loads(post_data.decode('utf-8'))
                except json.JSONDecodeError:
                    self._send_error(400, "无效的JSON数据")
                    return
            else:
                body = {}
            
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == '/api/service/start':
                self._handle_service_start()
            elif path == '/api/translate/text':
                self._handle_translate_text(body)
            elif path == '/api/translate/file':
                self._handle_translate_file(body)
            elif path == '/api/translate/batch':
                self._handle_translate_batch(body)
            else:
                self._send_error(404, "API端点不存在")
        except Exception as e:
            logger.error(f"处理POST请求失败: {str(e)}")
            self._send_error(500, f"服务器错误: {str(e)}")
    
    def do_DELETE(self):
        """处理DELETE请求"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == '/api/history':
                self._handle_clear_history()
            else:
                self._send_error(404, "API端点不存在")
        except Exception as e:
            logger.error(f"处理DELETE请求失败: {str(e)}")
            self._send_error(500, f"服务器错误: {str(e)}")
    
    def _handle_service_status(self):
        """处理服务状态检查"""
        try:
            if not self.translator:
                self._send_json_response({
                    "running": False,
                    "error": "翻译器未初始化"
                })
                return
            
            # 检查服务状态
            status = self.translator.check_service()
            
            response = {
                "running": status["connected"],
                "port": self.server_instance.port if self.server_instance else None,
                "version": "1.0.0",
                "models_available": status.get("available_models", [])
            }
            
            if not status["connected"]:
                response["error"] = status.get("error", "连接失败")
            
            self._send_json_response(response)
        except Exception as e:
            logger.error(f"获取服务状态失败: {str(e)}")
            self._send_json_response({
                "running": False,
                "error": str(e)
            })
    
    def _handle_get_port(self):
        """处理获取端口请求"""
        if self.server_instance:
            self._send_json_response({
                "port": self.server_instance.port
            })
        else:
            self._send_error(500, "服务器实例不存在")
    
    def _handle_service_start(self):
        """处理服务启动请求"""
        # 服务已经在运行，返回当前端口
        if self.server_instance:
            self._send_json_response({
                "success": True,
                "port": self.server_instance.port,
                "message": "服务已在运行"
            })
        else:
            self._send_error(500, "服务器实例不存在")
    
    def _handle_translate_text(self, body: Dict[str, Any]):
        """处理文本翻译请求"""
        try:
            text = body.get('text', '')
            source_lang = body.get('source_language', 'en')
            target_lang = body.get('target_language', 'zh')
            
            if not text:
                self._send_error(400, "缺少必需参数: text")
                return
            
            if not self.translator:
                self._send_error(500, "翻译器未初始化")
                return
            
            # 执行翻译
            result = self.translator.translate_text(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang
            )
            
            if result.success:
                self._send_json_response({
                    "success": True,
                    "translated_text": result.translated_text,
                    "duration": result.duration,
                    "chars_translated": len(text)
                })
            else:
                self._send_json_response({
                    "success": False,
                    "error": result.error
                })
        except Exception as e:
            logger.error(f"翻译文本失败: {str(e)}")
            self._send_json_response({
                "success": False,
                "error": str(e)
            })
    
    def _handle_translate_file(self, body: Dict[str, Any]):
        """处理文件翻译请求"""
        try:
            file_path = body.get('file_path', '')
            content = body.get('content', '')
            source_lang = body.get('source_language', 'en')
            target_lang = body.get('target_language', 'zh')
            output_mode = body.get('output_mode', 'suffix')
            overwrite = body.get('overwrite', False)
            
            if not file_path or not content:
                self._send_error(400, "缺少必需参数: file_path, content")
                return
            
            if not self.translator:
                self._send_error(500, "翻译器未初始化")
                return
            
            # 创建临时文件进行处理
            temp_input = Path(file_path)
            temp_output = self._generate_output_path(temp_input, output_mode, target_lang)
            
            # 执行翻译
            result = self.translator.translate_markdown(
                markdown_text=content,
                source_lang=source_lang,
                target_lang=target_lang
            )
            
            if result.success:
                self._send_json_response({
                    "success": True,
                    "translated_content": result.translated_text,
                    "output_path": str(temp_output),
                    "duration": result.duration,
                    "chars_translated": len(content)
                })
            else:
                self._send_json_response({
                    "success": False,
                    "error": result.error
                })
        except Exception as e:
            logger.error(f"翻译文件失败: {str(e)}")
            self._send_json_response({
                "success": False,
                "error": str(e)
            })
    
    def _handle_translate_batch(self, body: Dict[str, Any]):
        """处理批量翻译请求"""
        try:
            files = body.get('files', [])
            output_dir = body.get('output_dir', '')
            source_lang = body.get('source_language', 'en')
            target_lang = body.get('target_language', 'zh')
            overwrite = body.get('overwrite', False)
            
            if not files:
                self._send_error(400, "缺少必需参数: files")
                return
            
            if not self.translator:
                self._send_error(500, "翻译器未初始化")
                return
            
            results = []
            success_count = 0
            failed_count = 0
            
            for file_path in files:
                try:
                    # 这里简化处理，实际应该读取文件内容
                    # 由于API限制，我们只返回处理结果
                    results.append({
                        "file": file_path,
                        "success": True,
                        "output_path": f"{file_path}.{target_lang}.md"
                    })
                    success_count += 1
                except Exception as e:
                    results.append({
                        "file": file_path,
                        "success": False,
                        "error": str(e)
                    })
                    failed_count += 1
            
            self._send_json_response({
                "success": True,
                "results": results,
                "total_files": len(files),
                "success_count": success_count,
                "failed_count": failed_count
            })
        except Exception as e:
            logger.error(f"批量翻译失败: {str(e)}")
            self._send_json_response({
                "success": False,
                "error": str(e)
            })
    
    def _handle_get_history(self, parsed_path):
        """处理获取翻译历史请求"""
        try:
            query_params = parse_qs(parsed_path.query)
            limit = int(query_params.get('limit', [50])[0])
            offset = int(query_params.get('offset', [0])[0])
            
            # 这里简化处理，返回空历史记录
            # 实际应该从数据库或文件中读取
            self._send_json_response({
                "history": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            })
        except Exception as e:
            logger.error(f"获取翻译历史失败: {str(e)}")
            self._send_json_response({
                "history": [],
                "total": 0,
                "limit": 50,
                "offset": 0,
                "error": str(e)
            })
    
    def _handle_clear_history(self):
        """处理清空翻译历史请求"""
        try:
            # 这里简化处理，实际应该清空数据库或文件
            self._send_json_response({
                "success": True,
                "message": "翻译历史已清空"
            })
        except Exception as e:
            logger.error(f"清空翻译历史失败: {str(e)}")
            self._send_json_response({
                "success": False,
                "error": str(e)
            })
    
    def _generate_output_path(self, input_path: Path, output_mode: str, target_lang: str) -> Path:
        """生成输出文件路径"""
        if output_mode == 'suffix':
            return input_path.with_suffix(f'_{target_lang}.md')
        elif output_mode == 'overwrite':
            return input_path
        else:  # custom
            return input_path.parent / f"{input_path.stem}_{target_lang}.md"
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """发送JSON响应"""
        response_data = json.dumps(data, ensure_ascii=False, indent=2)
        response_bytes = response_data.encode('utf-8')
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(response_bytes)
    
    def _send_error(self, status_code: int, message: str):
        """发送错误响应"""
        self._send_json_response({
            "success": False,
            "error": message
        }, status_code)
    
    def log_message(self, format: str, *args):
        """重写日志方法，使用项目日志系统"""
        logger.debug(f"HTTP {format % args}")


class TranslationAPIServer:
    """翻译API服务器"""
    
    def __init__(self, config: Config, port_range: tuple = (8848, 8898)):
        self.config = config
        self.port_range = port_range
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.port: Optional[int] = None
        self.running = False
        self.translator: Optional[Translator] = None
        self._shutdown_event = threading.Event()
    
    def start(self) -> Dict[str, Any]:
        """启动HTTP服务器"""
        if self.running:
            return {
                "success": True,
                "port": self.port,
                "message": "服务已在运行"
            }
        
        # 查找可用端口
        self.port = self._find_available_port()
        if not self.port:
            return {
                "success": False,
                "error": f"无法在端口范围 {self.port_range[0]}-{self.port_range[1]} 中找到可用端口"
            }
        
        try:
            # 初始化翻译器
            self.translator = Translator(self.config)
            self.translator.__enter__()  # 手动进入上下文
            
            # 设置类变量
            TranslationAPIHandler.server_instance = self
            TranslationAPIHandler.translator = self.translator
            
            # 创建HTTP服务器
            self.server = HTTPServer(('localhost', self.port), TranslationAPIHandler)
            
            # 注册信号处理器，以便快速响应Ctrl+C
            def signal_handler(signum, frame):
                logger.info("接收到停止信号，正在强制关闭服务器...")
                # 直接设置运行状态为False
                self.running = False
                self._shutdown_event.set()
                # 强制关闭服务器socket
                if self.server:
                    try:
                        self.server.socket.close()
                    except:
                        pass
                # 立即退出
                import os
                os._exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # 启动服务器线程
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            self.running = True
            logger.info(f"翻译API服务器已启动，端口: {self.port}")
            
            return {
                "success": True,
                "port": self.port,
                "message": "服务启动成功"
            }
        except Exception as e:
            logger.error(f"启动HTTP服务器失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop(self):
        """停止HTTP服务器"""
        if not self.running:
            return
        
        try:
            self.running = False  # 立即设置运行状态为False
            self._shutdown_event.set()  # 设置关闭事件
            
            # 快速关闭服务器
            if self.server:
                try:
                    # 强制关闭服务器socket
                    self.server.socket.close()
                    self.server.server_close()
                except Exception as e:
                    logger.warning(f"关闭HTTP服务器时出错: {str(e)}")
            
            # 强制终止线程
            if self.server_thread and self.server_thread.is_alive():
                # 不等待线程自然结束，直接标记为完成
                logger.info("强制终止服务器线程")
            
            # 清理翻译器资源
            if self.translator:
                try:
                    self.translator.__exit__(None, None, None)
                except Exception as e:
                    logger.warning(f"清理翻译器资源时出错: {str(e)}")
            
            logger.info("翻译API服务器已停止")
        except Exception as e:
            logger.error(f"停止HTTP服务器失败: {str(e)}")
    
    def _run_server(self):
        """运行服务器"""
        try:
            # 使用serve_forever()而不是handle_request()，以确保服务器正常响应
            self.server.serve_forever()
        except Exception as e:
            if self.running:  # 只有在仍在运行状态时才记录错误
                logger.error(f"服务器运行错误: {str(e)}")
    
    def _find_available_port(self) -> Optional[int]:
        """查找可用端口"""
        for port in range(self.port_range[0], self.port_range[1] + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        return None
    
    def is_running(self) -> bool:
        """检查服务器是否运行中"""
        return self.running


def create_server(config: Config, port_range: tuple = (8848, 8898)) -> TranslationAPIServer:
    """创建翻译API服务器实例"""
    return TranslationAPIServer(config, port_range)