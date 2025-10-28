#!/usr/bin/env python3
"""
UnityLangPX MCP服务器启动脚本

用于启动MCP服务器，提供翻译服务接口。
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp.server import main, run_server
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


def check_ollama_service():
    """检查Ollama服务是否可用"""
    try:
        from src.core.translator import Translator
        from src.core.config import Config
        
        config = Config()
        translator = Translator(config)
        status = translator.check_service()
        
        if status.get("connected"):
            logger.info("Ollama服务连接正常")
            return True
        else:
            logger.warning(f"Ollama服务连接失败: {status.get('error', '未知错误')}")
            logger.warning("请确保Ollama服务正在运行")
            return False
            
    except Exception as e:
        logger.error(f"检查Ollama服务失败: {str(e)}")
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


async def run_with_checks(config_file=None, mode="sse", **kwargs):
    """带检查的运行函数"""
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
    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(project_root))
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="UnityLangPX MCP服务器")
    parser.add_argument("--config", type=str, default="config/dify_mcp_sse_config.json", help="配置文件路径")
    parser.add_argument("--mode", type=str, default="sse", choices=["sse", "standard"], help="运行模式: sse(HTTP)或standard(标准MCP)")
    parser.add_argument("--log-level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.log_level:
        os.environ["UNITYLANGPX_MCP_LOG_LEVEL"] = args.log_level
    
    # 运行服务器
    try:
        # 设置事件循环策略，确保在Windows上也能正常工作
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # 直接调用main函数，使用简化的信号处理
        main()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止服务器...")
        # 给服务器一些时间来清理
        import time
        time.sleep(1)
        print("服务器已停止")
    except Exception as e:
        print(f"启动失败: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        sys.exit(1)