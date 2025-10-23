"""
UnityLangPX MCP服务器主模块

实现MCP协议服务器，提供翻译服务接口。
"""

import asyncio
import sys
import json
import signal
import time
from typing import Optional, Dict, Any
from pathlib import Path

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
                # 获取本机IP地址
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                local_ip = "localhost"
            
            # 显示服务地址
            server_address = f"http://{local_ip}:{self.config.server.port}"
            console_message = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UnityLangPX MCP 服务器                        ║
╠══════════════════════════════════════════════════════════════╣
║  状态: 运行中                                                   ║
║  地址: {server_address:<55} ║
║  端口: {self.config.server.port:<55} ║
║  主机: {self.config.server.host:<55} ║
║  协议: MCP (标准输入输出)                                        ║
╚══════════════════════════════════════════════════════════════╝
"""
            print(console_message)
            logger.info(f"MCP服务器已启动，监听标准输入输出")
            logger.info(f"服务地址: {server_address}")
            
            # 开始处理消息
            await self._run_message_loop()
            
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