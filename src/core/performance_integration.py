"""
UnityLangPX 性能优化集成模块

整合所有性能优化组件，提供统一的性能优化接口。
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from .async_cache import AsyncMultiLevelCache, get_async_cache
from .smart_chunker import SmartChunker
from .async_translator import AsyncTranslator
from .performance_monitor import PerformanceMonitor, get_performance_monitor
from .enhanced_error_handling import ErrorHandler, get_error_handler
from .embedding_client import EmbeddingClientFactory
from .logger import get_logger
from ..config.manager import get_config_manager

logger = get_logger(__name__)


class PerformanceOptimizer:
    """性能优化器 - 整合所有性能优化组件"""
    
    def __init__(self):
        """初始化性能优化器"""
        self.config_manager = get_config_manager()
        self.performance_config = self.config_manager.get_performance_config()
        
        # 组件实例
        self.cache: Optional[AsyncMultiLevelCache] = None
        self.chunker: Optional[SmartChunker] = None
        self.translator: Optional[AsyncTranslator] = None
        self.monitor: Optional[PerformanceMonitor] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.embedding_client = None
        
        # 状态
        self.initialized = False
        self.start_time = None
        
        logger.info("性能优化器初始化完成")
    
    async def initialize(self):
        """初始化所有性能优化组件"""
        if self.initialized:
            return
        
        self.start_time = time.time()
        logger.info("开始初始化性能优化组件...")
        
        try:
            # 1. 初始化错误处理器
            self.error_handler = get_error_handler()
            await self.error_handler.initialize()
            logger.info("错误处理器初始化完成")
            
            # 2. 初始化性能监控
            if self.performance_config.performance_monitor.enabled:
                self.monitor = get_performance_monitor()
                self.monitor.start_monitoring(
                    interval=self.performance_config.performance_monitor.monitor_interval
                )
                logger.info("性能监控启动完成")
            
            # 3. 初始化异步缓存
            self.cache = get_async_cache()
            await self.cache.start()
            logger.info("异步缓存启动完成")
            
            # 4. 初始化智能分块器
            self.chunker = SmartChunker(self.performance_config.smart_chunker)
            logger.info("智能分块器初始化完成")
            
            # 5. 初始化嵌入客户端
            if self.performance_config.embedding.enabled:
                self.embedding_client = EmbeddingClientFactory.auto_detect_client()
                logger.info(f"嵌入客户端初始化完成: {type(self.embedding_client).__name__}")
            
            # 6. 初始化异步翻译器
            self.translator = AsyncTranslator(
                cache=self.cache,
                error_handler=self.error_handler,
                monitor=self.monitor
            )
            await self.translator.initialize()
            logger.info("异步翻译器初始化完成")
            
            self.initialized = True
            init_time = time.time() - self.start_time
            
            if self.monitor:
                self.monitor.add_metric(
                    "performance_optimizer_init_time",
                    init_time,
                    tags={"component": "performance_optimizer"}
                )
            
            logger.info(f"性能优化组件初始化完成，耗时: {init_time:.2f}秒")
            
        except Exception as e:
            logger.error(f"性能优化组件初始化失败: {str(e)}")
            if self.error_handler:
                await self.error_handler.handle_error(
                    error=e,
                    context={"component": "performance_optimizer", "action": "initialize"}
                )
            raise
    
    async def shutdown(self):
        """关闭所有性能优化组件"""
        if not self.initialized:
            return
        
        logger.info("开始关闭性能优化组件...")
        
        try:
            # 关闭翻译器
            if self.translator:
                await self.translator.shutdown()
                logger.info("异步翻译器已关闭")
            
            # 关闭缓存
            if self.cache:
                await self.cache.stop()
                logger.info("异步缓存已关闭")
            
            # 关闭性能监控
            if self.monitor:
                self.monitor.stop_monitoring()
                logger.info("性能监控已停止")
            
            # 关闭错误处理器
            if self.error_handler:
                await self.error_handler.shutdown()
                logger.info("错误处理器已关闭")
            
            self.initialized = False
            logger.info("性能优化组件关闭完成")
            
        except Exception as e:
            logger.error(f"关闭性能优化组件失败: {str(e)}")
    
    async def translate_text(self, text: str, source_lang: str = "en", 
                          target_lang: str = "zh", **kwargs) -> str:
        """
        翻译文本（使用性能优化）
        
        Args:
            text: 源文本
            source_lang: 源语言
            target_lang: 目标语言
            **kwargs: 其他参数
            
        Returns:
            翻译后的文本
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # 使用异步翻译器
            result = await self.translator.translate_text(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                **kwargs
            )
            
            # 记录性能指标
            if self.monitor:
                duration = time.time() - start_time
                self.monitor.record_timer(
                    "optimized_translation_duration",
                    duration,
                    tags={
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "text_length": str(len(text))
                    }
                )
            
            return result
            
        except Exception as e:
            if self.error_handler:
                await self.error_handler.handle_error(
                    error=e,
                    context={
                        "component": "performance_optimizer",
                        "action": "translate_text",
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "text_length": len(text)
                    }
                )
            raise
    
    async def translate_file(self, file_path: Path, source_lang: str = "en",
                          target_lang: str = "zh", output_path: Optional[Path] = None,
                          **kwargs) -> Path:
        """
        翻译文件（使用性能优化）
        
        Args:
            file_path: 源文件路径
            source_lang: 源语言
            target_lang: 目标语言
            output_path: 输出文件路径
            **kwargs: 其他参数
            
        Returns:
            翻译后的文件路径
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # 使用智能分块器分块
            chunks = await self.chunker.chunk_file(file_path)
            logger.info(f"文件分块完成: {len(chunks)} 个块")
            
            # 批量翻译
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                translated_text = await self.translate_text(
                    text=chunk.text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    **kwargs
                )
                
                # 保留原始块的结构信息
                translated_chunk = chunk.copy()
                translated_chunk.text = translated_text
                translated_chunks.append(translated_chunk)
                
                # 记录进度
                if self.monitor:
                    self.monitor.add_metric(
                        "translation_progress",
                        (i + 1) / len(chunks),
                        tags={"file": str(file_path)}
                    )
            
            # 重组文件
            if output_path is None:
                output_path = file_path.with_suffix(f".{target_lang}{file_path.suffix}")
            
            await self.chunker.reassemble_file(translated_chunks, output_path)
            
            # 记录性能指标
            if self.monitor:
                duration = time.time() - start_time
                file_size = file_path.stat().st_size
                self.monitor.record_timer(
                    "optimized_file_translation_duration",
                    duration,
                    tags={
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "file_size": str(file_size),
                        "chunks": str(len(chunks))
                    }
                )
                
                # 计算翻译速度
                if duration > 0:
                    speed = file_size / duration  # 字节/秒
                    self.monitor.add_metric(
                        "translation_speed",
                        speed,
                        tags={"unit": "bytes_per_second"}
                    )
            
            logger.info(f"文件翻译完成: {file_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            if self.error_handler:
                await self.error_handler.handle_error(
                    error=e,
                    context={
                        "component": "performance_optimizer",
                        "action": "translate_file",
                        "file_path": str(file_path),
                        "source_lang": source_lang,
                        "target_lang": target_lang
                    }
                )
            raise
    
    async def batch_translate(self, texts: List[str], source_lang: str = "en",
                          target_lang: str = "zh", **kwargs) -> List[str]:
        """
        批量翻译文本（使用性能优化）
        
        Args:
            texts: 文本列表
            source_lang: 源语言
            target_lang: 目标语言
            **kwargs: 其他参数
            
        Returns:
            翻译后的文本列表
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # 使用异步翻译器的批量翻译功能
            results = await self.translator.batch_translate(
                texts=texts,
                source_lang=source_lang,
                target_lang=target_lang,
                **kwargs
            )
            
            # 记录性能指标
            if self.monitor:
                duration = time.time() - start_time
                self.monitor.record_timer(
                    "optimized_batch_translation_duration",
                    duration,
                    tags={
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "batch_size": str(len(texts))
                    }
                )
                
                # 计算吞吐量
                if duration > 0:
                    throughput = len(texts) / duration  # 文本/秒
                    self.monitor.add_metric(
                        "batch_translation_throughput",
                        throughput,
                        tags={"unit": "texts_per_second"}
                    )
            
            return results
            
        except Exception as e:
            if self.error_handler:
                await self.error_handler.handle_error(
                    error=e,
                    context={
                        "component": "performance_optimizer",
                        "action": "batch_translate",
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "batch_size": len(texts)
                    }
                )
            raise
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = {
            "optimizer": {
                "initialized": self.initialized,
                "init_time": self.start_time,
                "uptime": time.time() - self.start_time if self.start_time else 0
            }
        }
        
        # 添加各组件的统计信息
        if self.cache:
            cache_stats = await self.cache.get_statistics()
            stats["cache"] = cache_stats
        
        if self.monitor:
            monitor_stats = self.monitor.get_statistics()
            stats["monitor"] = monitor_stats
        
        if self.error_handler:
            error_stats = self.error_handler.get_statistics()
            stats["error_handler"] = error_stats
        
        if self.translator:
            translator_stats = self.translator.get_statistics()
            stats["translator"] = translator_stats
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            "overall": "healthy",
            "components": {}
        }
        
        # 检查各组件状态
        if self.cache:
            try:
                cache_stats = await self.cache.get_statistics()
                health["components"]["cache"] = {
                    "status": "healthy" if cache_stats["running"] else "unhealthy",
                    "details": cache_stats
                }
            except Exception as e:
                health["components"]["cache"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["overall"] = "degraded"
        
        if self.monitor:
            try:
                monitor_stats = self.monitor.get_statistics()
                health["components"]["monitor"] = {
                    "status": "healthy" if monitor_stats["monitoring"] else "unhealthy",
                    "details": monitor_stats
                }
            except Exception as e:
                health["components"]["monitor"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["overall"] = "degraded"
        
        if self.error_handler:
            try:
                error_stats = self.error_handler.get_statistics()
                health["components"]["error_handler"] = {
                    "status": "healthy",
                    "details": error_stats
                }
            except Exception as e:
                health["components"]["error_handler"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["overall"] = "degraded"
        
        if self.embedding_client:
            try:
                available = self.embedding_client.is_available()
                health["components"]["embedding_client"] = {
                    "status": "healthy" if available else "unhealthy",
                    "details": {
                        "type": type(self.embedding_client).__name__,
                        "available": available
                    }
                }
                if not available:
                    health["overall"] = "degraded"
            except Exception as e:
                health["components"]["embedding_client"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["overall"] = "degraded"
        
        return health
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.shutdown()


# 全局性能优化器实例
_performance_optimizer = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器实例"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer


# 便捷函数
async def translate_with_optimization(text: str, source_lang: str = "en",
                                 target_lang: str = "zh", **kwargs) -> str:
    """使用性能优化翻译文本"""
    optimizer = get_performance_optimizer()
    return await optimizer.translate_text(
        text=text,
        source_lang=source_lang,
        target_lang=target_lang,
        **kwargs
    )


async def translate_file_with_optimization(file_path: Path, source_lang: str = "en",
                                       target_lang: str = "zh", **kwargs) -> Path:
    """使用性能优化翻译文件"""
    optimizer = get_performance_optimizer()
    return await optimizer.translate_file(
        file_path=file_path,
        source_lang=source_lang,
        target_lang=target_lang,
        **kwargs
    )


async def batch_translate_with_optimization(texts: List[str], source_lang: str = "en",
                                       target_lang: str = "zh", **kwargs) -> List[str]:
    """使用性能优化批量翻译文本"""
    optimizer = get_performance_optimizer()
    return await optimizer.batch_translate(
        texts=texts,
        source_lang=source_lang,
        target_lang=target_lang,
        **kwargs
    )