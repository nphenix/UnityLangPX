#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UnityLangPX MCP服务器Windows专用启动脚本
专门处理Windows下的Ctrl+C问题
"""

import sys
import os
import asyncio
import signal
import threading
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp.server import MCPServer
from src.mcp.config import load_mcp_config
from src.core.logger import get_logger

logger = get_logger(__name__)

def check_dependencies():
    """检查依赖是否满足"""
    try:
        # 检查核心依赖
        import pydantic
        import aiofiles
        import asyncio
        
        logger.info("依赖检查通过")
        return True
        
    except ImportError as e:
        logger.error(f"依赖检查失败: {str(e)}")
        logger.error("请安装MCP服务器依赖: pip install -r requirements/mcp.txt")
        return False

def create_directories():
    """创建必要的目录"""
    directories = [
        "data/mcp_cache",
        "logs"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"创建目录: {dir_path}")

def run_server_with_ctrl_c_support(config_file=None):
    """运行服务器并支持Ctrl+C"""
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 创建必要目录
    create_directories()
    
    # 设置环境变量，确保服务器监听正确接口
    os.environ["UNITYLANGPX_MCP_HOST"] = "0.0.0.0"
    os.environ["UNITYLANGPX_MCP_PORT"] = "4010"
    logger.info("SSE模式: 服务器将监听所有接口 (0.0.0.0:4010)")
    logger.info("Docker容器可使用 http://host.docker.internal:4010 访问")
    
    # 设置事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 创建关闭事件
    shutdown_event = asyncio.Event()
    server = None
    
    def signal_handler():
        """信号处理函数"""
        print("\n收到中断信号，正在停止服务器...")
        shutdown_event.set()
    
    # 设置信号处理
    try:
        if sys.platform == 'win32':
            # Windows下的信号处理
            try:
                import win32api
                def win32_handler(dwCtrlType):
                    if dwCtrlType in (0, 2):  # CTRL_C_EVENT or CTRL_BREAK_EVENT
                        signal_handler()
                        return 1  # 表示已处理
                    return 0
                win32api.SetConsoleCtrlHandler(win32_handler, True)
                print("已设置Windows控制台处理器")
            except ImportError:
                # 如果没有win32api，使用默认方式
                signal.signal(signal.SIGINT, lambda sig, frame: signal_handler())
                print("已设置SIGINT信号处理器")
        else:
            # Unix-like系统
            signal.signal(signal.SIGINT, lambda sig, frame: signal_handler())
            signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler())
    except Exception as e:
        print(f"设置信号处理器失败: {e}")
        print("将使用KeyboardInterrupt异常处理")
    
    # 创建键盘监控线程
    def keyboard_monitor():
        """键盘监控线程"""
        try:
            while not shutdown_event.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            signal_handler()
    
    if sys.platform == 'win32':
        monitor_thread = threading.Thread(target=keyboard_monitor, daemon=True)
        monitor_thread.start()
        print("已启动键盘监控线程")
    
    try:
        # 加载配置
        config = load_mcp_config(config_file)
        config.validate()
        
        # 创建并启动服务器
        server = MCPServer(config)
        
        # 创建启动任务
        start_task = loop.create_task(server.start())
        
        # 等待关闭信号
        loop.run_until_complete(shutdown_event.wait())
        
        # 取消启动任务
        if not start_task.done():
            start_task.cancel()
            try:
                loop.run_until_complete(start_task)
            except asyncio.CancelledError:
                pass
        
        # 停止服务器
        if server:
            loop.run_until_complete(server.stop())
            
    except KeyboardInterrupt:
        print("\n收到键盘中断信号，正在停止服务器...")
        if server:
            loop.run_until_complete(server.stop())
    except Exception as e:
        print(f"服务器运行异常: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
    finally:
        # 关闭事件循环
        loop.close()
        print("服务器已停止")

if __name__ == "__main__":
    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(project_root))
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="UnityLangPX MCP服务器 (Windows版)")
    parser.add_argument("--config", type=str, default="config/dify_mcp_sse_config.json", help="配置文件路径")
    parser.add_argument("--log-level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.log_level:
        os.environ["UNITYLANGPX_MCP_LOG_LEVEL"] = args.log_level
    
    # 运行服务器
    try:
        run_server_with_ctrl_c_support(args.config)
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止服务器...")
        print("服务器已停止")
    except Exception as e:
        print(f"启动失败: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        sys.exit(1)