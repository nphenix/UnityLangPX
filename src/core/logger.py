"""
UnityLangPX 日志管理模块

这个模块使用Loguru提供结构化日志记录功能，支持文件和控制台输出，
以及日志轮转和性能监控。
"""

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger

from .config import Config, LoggingConfig
from .exceptions import ConfigurationError


class LoggerManager:
    """日志管理器"""
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        初始化日志管理器
        
        Args:
            config: 日志配置，如果为None则使用默认配置
        """
        self.config = config or LoggingConfig()
        self._setup_logger()
        self._performance_data = {}
    
    def _setup_logger(self) -> None:
        """设置日志器"""
        # 移除默认处理器
        logger.remove()
        
        # 添加控制台处理器
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            level=self.config.level,
            colorize=True
        )
        
        # 添加文件处理器
        if self.config.file:
            log_file = Path(self.config.file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_file,
                format="{time:YYYY-MM-DD HH:mm:ss} | "
                       "{level: <8} | "
                       "{name}:{function}:{line} | "
                       "{message}",
                level=self.config.level,
                rotation=f"{self.config.max_size_mb} MB",
                retention=self.config.backup_count,
                compression="zip",
                encoding="utf-8"
            )
    
    def get_logger(self, name: Optional[str] = None):
        """
        获取日志器实例
        
        Args:
            name: 日志器名称，如果为None则使用调用模块名
            
        Returns:
            日志器实例
        """
        if name:
            return logger.bind(name=name)
        return logger
    
    def start_performance_monitoring(self, operation: str) -> str:
        """
        开始性能监控
        
        Args:
            operation: 操作名称
            
        Returns:
            操作ID，用于结束监控时使用
        """
        operation_id = f"{operation}_{int(time.time() * 1000)}"
        self._performance_data[operation_id] = {
            "operation": operation,
            "start_time": time.time(),
            "start_memory": self._get_memory_usage()
        }
        
        logger.debug(f"开始监控操作: {operation} (ID: {operation_id})")
        return operation_id
    
    def end_performance_monitoring(self, operation_id: str, 
                                 extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        结束性能监控
        
        Args:
            operation_id: 操作ID
            extra_data: 额外的性能数据
            
        Returns:
            性能数据字典
        """
        if operation_id not in self._performance_data:
            logger.warning(f"未找到操作ID: {operation_id}")
            return {}
        
        data = self._performance_data.pop(operation_id)
        end_time = time.time()
        end_memory = self._get_memory_usage()
        
        duration = end_time - data["start_time"]
        memory_delta = end_memory - data["start_memory"]
        
        performance_data = {
            "operation": data["operation"],
            "duration_seconds": duration,
            "memory_usage_mb": end_memory,
            "memory_delta_mb": memory_delta,
            "timestamp": end_time
        }
        
        if extra_data:
            performance_data.update(extra_data)
        
        logger.info(
            f"操作完成: {data['operation']} | "
            f"耗时: {duration:.2f}秒 | "
            f"内存变化: {memory_delta:+.2f}MB"
        )
        
        return performance_data
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量(MB)"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def log_translation_start(self, file_path: str, file_size: int) -> None:
        """记录翻译开始"""
        logger.info(f"开始翻译文件: {file_path} ({file_size} 字节)")
    
    def log_translation_end(self, file_path: str, duration: float, 
                          chars_translated: int) -> None:
        """记录翻译结束"""
        logger.info(
            f"翻译完成: {file_path} | "
            f"耗时: {duration:.2f}秒 | "
            f"翻译字符: {chars_translated} | "
            f"速度: {chars_translated/duration:.1f} 字符/秒"
        )
    
    def log_translation_error(self, file_path: str, error: Exception) -> None:
        """记录翻译错误"""
        logger.error(f"翻译失败: {file_path} - {str(error)}")
    
    def log_batch_progress(self, processed: int, total: int, 
                          current_file: str) -> None:
        """记录批处理进度"""
        percentage = (processed / total * 100) if total > 0 else 0
        logger.info(f"批处理进度: {processed}/{total} ({percentage:.1f}%) - {current_file}")
    
    def log_api_call(self, endpoint: str, duration: float, 
                    success: bool, error: Optional[str] = None) -> None:
        """记录API调用"""
        status = "成功" if success else "失败"
        message = f"API调用: {endpoint} | 耗时: {duration:.2f}秒 | 状态: {status}"
        
        if error:
            message += f" | 错误: {error}"
        
        if success:
            logger.debug(message)
        else:
            logger.warning(message)
    
    def log_cache_operation(self, operation: str, key: str, 
                          hit: Optional[bool] = None) -> None:
        """记录缓存操作"""
        if hit is not None:
            status = "命中" if hit else "未命中"
            logger.debug(f"缓存{operation}: {key} - {status}")
        else:
            logger.debug(f"缓存{operation}: {key}")
    
    def log_configuration(self, config: Config) -> None:
        """记录配置信息"""
        logger.info("配置信息:")
        logger.info(f"  Ollama服务: {config.ollama.host}")
        logger.info(f"  翻译模型: {config.ollama.model}")
        logger.info(f"  源语言: {config.translation.source_language}")
        logger.info(f"  目标语言: {config.translation.target_language}")
        logger.info(f"  并行工作线程: {config.cli.parallel_workers}")
        logger.info(f"  缓存启用: {'是' if config.cache.enable_cache else '否'}")
    
    def create_file_logger(self, file_path: Path, level: str = "INFO") -> None:
        """
        为特定文件创建日志处理器
        
        Args:
            file_path: 日志文件路径
            level: 日志级别
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            file_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level=level,
            rotation="10 MB",
            retention=5,
            compression="zip",
            encoding="utf-8"
        )


# 全局日志管理器实例
_logger_manager: Optional[LoggerManager] = None


def init_logger(config: Optional[LoggingConfig] = None) -> LoggerManager:
    """
    初始化全局日志管理器
    
    Args:
        config: 日志配置
        
    Returns:
        日志管理器实例
    """
    global _logger_manager
    _logger_manager = LoggerManager(config)
    return _logger_manager


def get_logger(name: Optional[str] = None):
    """
    获取日志器实例
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    if _logger_manager is None:
        init_logger()
    
    return _logger_manager.get_logger(name)


def log_performance(operation: str):
    """
    性能监控装饰器
    
    Args:
        operation: 操作名称
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if _logger_manager is None:
                init_logger()
            
            operation_id = _logger_manager.start_performance_monitoring(operation)
            try:
                result = func(*args, **kwargs)
                _logger_manager.end_performance_monitoring(operation_id)
                return result
            except Exception as e:
                _logger_manager.end_performance_monitoring(
                    operation_id, {"error": str(e)}
                )
                raise
        
        return wrapper
    return decorator