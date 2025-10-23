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


async def run_with_checks(config_file=None, **kwargs):
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
    
    # 运行服务器
    try:
        await run_server(config_file, **kwargs)
    except Exception as e:
        logger.error(f"服务器运行失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(project_root))
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="UnityLangPX MCP服务器")
    parser.add_argument("--config", type=str, default="config/dify_mcp_config.json", help="配置文件路径")
    parser.add_argument("--log-level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.log_level:
        os.environ["UNITYLANGPX_MCP_LOG_LEVEL"] = args.log_level
    
    # 运行服务器
    try:
        asyncio.run(run_with_checks(args.config))
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"启动失败: {str(e)}")
        sys.exit(1)