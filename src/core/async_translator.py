"""
UnityLangPX 异步翻译引擎模块

实现高性能的异步翻译引擎，整合异步缓存、智能分块和连接池，
提供非阻塞的翻译服务。
"""

import asyncio
import aiofiles
import time
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from .async_cache import AsyncMultiLevelCache, CacheConfig
from .smart_chunker import SmartChunker, ChunkConfig, TextChunk, ContentType
from .models.factory import ModelClientFactory
from .markdown_processor import MarkdownProcessor, MarkdownElement
from .exceptions import TranslationError, MarkdownProcessingError, FileProcessingError, APIConnectionError
from .logger import get_logger
from .config import Config

logger = get_logger(__name__)


class TranslationStatus(Enum):
    """翻译状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTranslationResult:
    """异步翻译结果"""
    task_id: str
    success: bool
    source_file: Optional[Path] = None
    target_file: Optional[Path] = None
    source_text: Optional[str] = None
    translated_text: Optional[str] = None
    duration: float = 0.0
    chars_translated: int = 0
    elements_processed: int = 0
    chunks_processed: int = 0
    cache_hits: int = 0
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理Path对象
        if data['source_file']:
            data['source_file'] = str(data['source_file'])
        if data['target_file']:
            data['target_file'] = str(data['target_file'])
        return data


@dataclass
class TranslationTask:
    """翻译任务"""
    task_id: str
    task_type: str  # 'text', 'markdown', 'file'
    input_data: Any
    config: Dict[str, Any]
    status: TranslationStatus = TranslationStatus.PENDING
    progress: float = 0.0
    result: Optional[AsyncTranslationResult] = None
    error: Optional[str] = None
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    callback: Optional[Callable] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class AsyncTranslator:
    """异步翻译引擎"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化异步翻译引擎
        
        Args:
            config: 配置对象
        """
        self.config = config or Config()
        
        # 初始化模型客户端
        provider = self.config.model.provider
        model_config = self.config.get_model_config()
        self.model_client = ModelClientFactory.create_client(provider, model_config)
        
        # 初始化组件
        self.markdown_processor = MarkdownProcessor()
        
        # 初始化缓存
        cache_config = CacheConfig(
            l1_max_size=getattr(self.config.cache, 'max_size_mb', 500) * 10,  # 估算条目数
            l2_max_size=getattr(self.config.cache, 'max_size_mb', 500) * 100,
            l3_enabled=self.config.cache.enable_cache,
            l3_dir=str(Path(self.config.cache.cache_dir) / "l3")
        )
        self.cache = AsyncMultiLevelCache(cache_config)
        
        # 初始化智能分块器
        chunk_config = ChunkConfig(
            max_tokens=self.config.translation.chunk_size or 4000,
            overlap_tokens=self.config.translation.overlap or 200,
            language=self.config.translation.source_language or "en",
            respect_obsidian_syntax=True
        )
        self.chunker = SmartChunker(chunk_config)
        
        # 任务管理
        self.tasks: Dict[str, TranslationTask] = {}
        self.task_queue = asyncio.Queue()
        self.worker_tasks: List[asyncio.Task] = []
        self.max_workers = getattr(self.config.cli, 'parallel_workers', 4)
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_chars_translated': 0,
            'total_cache_hits': 0,
            'avg_translation_time': 0.0,
            'active_workers': 0
        }
        
        # 控制标志
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        logger.info(f"异步翻译引擎初始化完成，提供商: {provider}")
    
    async def start(self):
        """启动异步翻译引擎"""
        if self.running:
            logger.warning("异步翻译引擎已在运行")
            return
        
        self.running = False
        self.shutdown_event.clear()
        
        # 启动缓存
        await self.cache.start()
        
        # 启动工作线程
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        
        logger.info(f"异步翻译引擎已启动，工作线程数: {self.max_workers}")
    
    async def stop(self, wait_for_completion: bool = True, timeout: float = 30.0):
        """
        停止异步翻译引擎
        
        Args:
            wait_for_completion: 是否等待完成
            timeout: 等待超时时间
        """
        if not self.running:
            return
        
        self.running = False
        self.shutdown_event.set()
        
        if wait_for_completion:
            # 等待所有任务完成
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                active_tasks = sum(1 for task in self.tasks.values() 
                                if task.status in [TranslationStatus.PENDING, TranslationStatus.IN_PROGRESS])
                if active_tasks == 0:
                    break
                await asyncio.sleep(0.1)
        
        # 取消所有工作线程
        for worker_task in self.worker_tasks:
            worker_task.cancel()
        
        # 等待工作线程结束
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # 停止缓存
        await self.cache.stop()
        
        logger.info("异步翻译引擎已停止")
    
    async def translate_text_async(self, text: str, context: Optional[str] = None,
                                source_lang: Optional[str] = None,
                                target_lang: Optional[str] = None,
                                task_id: Optional[str] = None,
                                callback: Optional[Callable] = None) -> str:
        """
        异步翻译文本
        
        Args:
            text: 待翻译文本
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            task_id: 任务ID，None表示自动生成
            callback: 完成回调函数
            
        Returns:
            任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 创建翻译任务
        task = TranslationTask(
            task_id=task_id,
            task_type='text',
            input_data={
                'text': text,
                'context': context,
                'source_lang': source_lang or self.config.translation.source_language,
                'target_lang': target_lang or self.config.translation.target_language
            },
            config={
                'temperature': self.config.translation.temperature
            },
            callback=callback
        )
        
        # 添加任务
        self.tasks[task_id] = task
        await self.task_queue.put(task)
        self.stats['total_tasks'] += 1
        
        logger.debug(f"提交文本翻译任务: {task_id}")
        return task_id
    
    async def translate_markdown_async(self, markdown_text: str, context: Optional[str] = None,
                                    source_lang: Optional[str] = None,
                                    target_lang: Optional[str] = None,
                                    task_id: Optional[str] = None,
                                    callback: Optional[Callable] = None) -> str:
        """
        异步翻译Markdown文本
        
        Args:
            markdown_text: 待翻译的Markdown文本
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            task_id: 任务ID，None表示自动生成
            callback: 完成回调函数
            
        Returns:
            任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 创建翻译任务
        task = TranslationTask(
            task_id=task_id,
            task_type='markdown',
            input_data={
                'markdown_text': markdown_text,
                'context': context,
                'source_lang': source_lang or self.config.translation.source_language,
                'target_lang': target_lang or self.config.translation.target_language
            },
            config={
                'temperature': self.config.translation.temperature
            },
            callback=callback
        )
        
        # 添加任务
        self.tasks[task_id] = task
        await self.task_queue.put(task)
        self.stats['total_tasks'] += 1
        
        logger.debug(f"提交Markdown翻译任务: {task_id}")
        return task_id
    
    async def translate_file_async(self, input_file: Path, output_file: Optional[Path] = None,
                                context: Optional[str] = None,
                                source_lang: Optional[str] = None,
                                target_lang: Optional[str] = None,
                                task_id: Optional[str] = None,
                                callback: Optional[Callable] = None) -> str:
        """
        异步翻译文件
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径，None表示自动生成
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            task_id: 任务ID，None表示自动生成
            callback: 完成回调函数
            
        Returns:
            任务ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 自动生成输出文件路径
        if output_file is None:
            output_file = self._generate_output_path(input_file)
        
        # 创建翻译任务
        task = TranslationTask(
            task_id=task_id,
            task_type='file',
            input_data={
                'input_file': input_file,
                'output_file': output_file,
                'context': context,
                'source_lang': source_lang or self.config.translation.source_language,
                'target_lang': target_lang or self.config.translation.target_language
            },
            config={
                'temperature': self.config.translation.temperature
            },
            callback=callback
        )
        
        # 添加任务
        self.tasks[task_id] = task
        await self.task_queue.put(task)
        self.stats['total_tasks'] += 1
        
        logger.debug(f"提交文件翻译任务: {task_id}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[TranslationTask]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象或None
        """
        return self.tasks.get(task_id)
    
    async def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[AsyncTranslationResult]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间
            
        Returns:
            翻译结果或None
        """
        start_time = time.time()
        
        while True:
            task = self.tasks.get(task_id)
            if not task:
                return None
            
            if task.status in [TranslationStatus.COMPLETED, TranslationStatus.FAILED, TranslationStatus.CANCELLED]:
                return task.result
            
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            # 短暂等待
            await asyncio.sleep(0.1)
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否取消成功
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in [TranslationStatus.COMPLETED, TranslationStatus.FAILED, TranslationStatus.CANCELLED]:
            return False
        
        task.status = TranslationStatus.CANCELLED
        task.completed_at = time.time()
        
        logger.info(f"任务已取消: {task_id}")
        return True
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 添加缓存统计
        cache_stats = await self.cache.get_statistics()
        stats['cache'] = cache_stats
        
        # 添加任务状态统计
        status_counts = {}
        for task in self.tasks.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        stats['task_status_counts'] = status_counts
        stats['active_tasks'] = len(self.tasks)
        stats['queue_size'] = self.task_queue.qsize()
        stats['running'] = self.running
        
        return stats
    
    # 私有方法
    
    async def _worker(self, worker_name: str):
        """工作线程"""
        logger.debug(f"工作线程启动: {worker_name}")
        
        try:
            while self.running and not self.shutdown_event.is_set():
                try:
                    # 获取任务（带超时）
                    task = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                    
                    # 处理任务
                    await self._process_task(task)
                    
                except asyncio.TimeoutError:
                    # 超时是正常的，继续循环
                    continue
                except Exception as e:
                    logger.error(f"工作线程 {worker_name} 错误: {str(e)}")
                    await asyncio.sleep(1.0)
        
        except asyncio.CancelledError:
            pass
        
        logger.debug(f"工作线程停止: {worker_name}")
    
    async def _process_task(self, task: TranslationTask):
        """处理翻译任务"""
        task.status = TranslationStatus.IN_PROGRESS
        task.started_at = time.time()
        
        try:
            if task.task_type == 'text':
                result = await self._process_text_task(task)
            elif task.task_type == 'markdown':
                result = await self._process_markdown_task(task)
            elif task.task_type == 'file':
                result = await self._process_file_task(task)
            else:
                raise ValueError(f"不支持的任务类型: {task.task_type}")
            
            task.result = result
            task.status = TranslationStatus.COMPLETED if result.success else TranslationStatus.FAILED
            
            # 更新统计
            self.stats['completed_tasks'] += 1
            self.stats['total_chars_translated'] += result.chars_translated
            self.stats['total_cache_hits'] += result.cache_hits
            
            # 计算平均翻译时间
            total_completed = self.stats['completed_tasks']
            current_avg = self.stats['avg_translation_time']
            self.stats['avg_translation_time'] = (
                (current_avg * (total_completed - 1) + result.duration) / total_completed
            )
            
        except Exception as e:
            error_msg = f"任务处理失败: {str(e)}"
            logger.error(error_msg)
            
            task.error = error_msg
            task.status = TranslationStatus.FAILED
            task.result = AsyncTranslationResult(
                task_id=task.task_id,
                success=False,
                error=error_msg,
                duration=time.time() - (task.started_at or time.time())
            )
            
            self.stats['failed_tasks'] += 1
        
        finally:
            task.completed_at = time.time()
            
            # 调用回调
            if task.callback:
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(task.result)
                    else:
                        task.callback(task.result)
                except Exception as e:
                    logger.error(f"任务回调执行失败: {str(e)}")
    
    async def _process_text_task(self, task: TranslationTask) -> AsyncTranslationResult:
        """处理文本翻译任务"""
        input_data = task.input_data
        text = input_data['text']
        context = input_data.get('context')
        source_lang = input_data['source_lang']
        target_lang = input_data['target_lang']
        temperature = task.config.get('temperature', 0.1)
        
        start_time = time.time()
        cache_hits = 0
        
        try:
            # 检查缓存
            cache_key = f"{source_lang}_{target_lang}_{hash(text)}_text"
            cached_result = await self.cache.get(cache_key)
            
            if cached_result:
                cache_hits = 1
                logger.debug(f"使用缓存结果: {task.task_id}")
                
                return AsyncTranslationResult(
                    task_id=task.task_id,
                    success=True,
                    source_text=text,
                    translated_text=cached_result,
                    duration=time.time() - start_time,
                    chars_translated=len(text),
                    cache_hits=cache_hits,
                    metadata={'from_cache': True}
                )
            
            # 执行翻译
            translated_text = await self.model_client.translate_text_async(
                text=text,
                context=context,
                source_lang=source_lang,
                target_lang=target_lang,
                temperature=temperature
            )
            
            # 保存到缓存
            await self.cache.set(cache_key, translated_text)
            
            duration = time.time() - start_time
            
            return AsyncTranslationResult(
                task_id=task.task_id,
                success=True,
                source_text=text,
                translated_text=translated_text,
                duration=duration,
                chars_translated=len(text),
                cache_hits=cache_hits,
                metadata={'from_cache': False}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"文本翻译失败: {str(e)}"
            logger.error(error_msg)
            
            return AsyncTranslationResult(
                task_id=task.task_id,
                success=False,
                source_text=text,
                duration=duration,
                error=error_msg,
                cache_hits=cache_hits
            )
    
    async def _process_markdown_task(self, task: TranslationTask) -> AsyncTranslationResult:
        """处理Markdown翻译任务"""
        input_data = task.input_data
        markdown_text = input_data['markdown_text']
        context = input_data.get('context')
        source_lang = input_data['source_lang']
        target_lang = input_data['target_lang']
        temperature = task.config.get('temperature', 0.1)
        
        start_time = time.time()
        cache_hits = 0
        chars_translated = 0
        elements_processed = 0
        
        try:
            # 检查缓存
            cache_key = f"{source_lang}_{target_lang}_{hash(markdown_text)}_markdown"
            cached_result = await self.cache.get(cache_key)
            
            if cached_result:
                cache_hits = 1
                logger.debug(f"使用缓存结果: {task.task_id}")
                
                return AsyncTranslationResult(
                    task_id=task.task_id,
                    success=True,
                    source_text=markdown_text,
                    translated_text=cached_result,
                    duration=time.time() - start_time,
                    chars_translated=len(markdown_text),
                    elements_processed=0,  # 缓存中没有元素信息
                    cache_hits=cache_hits,
                    metadata={'from_cache': True}
                )
            
            # 解析Markdown元素
            elements = self.markdown_processor.extract_translatable_elements(markdown_text)
            elements_processed = len(elements)
            
            # 翻译可翻译的元素
            translated_elements = []
            
            for element in elements:
                if element.translatable:
                    # 提取可翻译的文本
                    if element.type in ['header', 'list_item']:
                        text_to_translate = element.metadata.get('text', '')
                    else:
                        text_to_translate = element.content
                    
                    if text_to_translate.strip():
                        # 翻译文本
                        translation_result = await self.model_client.translate_text_async(
                            text=text_to_translate,
                            context=context,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            temperature=temperature
                        )
                        
                        if translation_result:
                            # 更新元素内容
                            translated_element = self.markdown_processor.translate_element_content(
                                element, translation_result
                            )
                            translated_elements.append(translated_element)
                            chars_translated += len(text_to_translate)
                        else:
                            # 翻译失败，保留原元素
                            logger.warning(f"元素翻译失败，保留原文: {task.task_id}")
                            translated_elements.append(element)
                    else:
                        # 空元素，直接添加
                        translated_elements.append(element)
                else:
                    # 不可翻译的元素，直接添加
                    translated_elements.append(element)
            
            # 重构Markdown文档
            translated_markdown = self.markdown_processor.reconstruct_markdown(translated_elements)
            
            # 保存到缓存
            await self.cache.set(cache_key, translated_markdown)
            
            duration = time.time() - start_time
            
            return AsyncTranslationResult(
                task_id=task.task_id,
                success=True,
                source_text=markdown_text,
                translated_text=translated_markdown,
                duration=duration,
                chars_translated=chars_translated,
                elements_processed=elements_processed,
                cache_hits=cache_hits,
                metadata={
                    'from_cache': False,
                    'element_stats': self.markdown_processor.get_statistics(elements)
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Markdown翻译失败: {str(e)}"
            logger.error(error_msg)
            
            return AsyncTranslationResult(
                task_id=task.task_id,
                success=False,
                source_text=markdown_text,
                duration=duration,
                error=error_msg,
                cache_hits=cache_hits
            )
    
    async def _process_file_task(self, task: TranslationTask) -> AsyncTranslationResult:
        """处理文件翻译任务"""
        input_data = task.input_data
        input_file = input_data['input_file']
        output_file = input_data['output_file']
        context = input_data.get('context')
        source_lang = input_data['source_lang']
        target_lang = input_data['target_lang']
        temperature = task.config.get('temperature', 0.1)
        
        start_time = time.time()
        
        try:
            # 检查文件是否存在
            if not input_file.exists():
                error_msg = f"输入文件不存在: {input_file}"
                logger.error(error_msg)
                
                return AsyncTranslationResult(
                    task_id=task.task_id,
                    success=False,
                    source_file=input_file,
                    target_file=output_file,
                    error=error_msg
                )
            
            # 异步读取文件内容
            async with aiofiles.open(input_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # 确定文件类型和翻译方法
            if input_file.suffix.lower() == '.md':
                # Markdown文件
                translation_result = await self.translate_markdown_async(
                    markdown_text=content,
                    context=context,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
            else:
                # 普通文本文件
                translation_result = await self.translate_text_async(
                    text=content,
                    context=context,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
            
            # 获取翻译结果
            result = await self.get_task_result(translation_result)
            if not result or not result.success:
                return AsyncTranslationResult(
                    task_id=task.task_id,
                    success=False,
                    source_file=input_file,
                    target_file=output_file,
                    error=result.error if result else "翻译失败"
                )
            
            # 确保输出目录存在
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 异步写入翻译结果
            async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
                await f.write(result.translated_text)
            
            # 验证文件写入
            async with aiofiles.open(output_file, 'r', encoding='utf-8') as f:
                written_content = await f.read()
                if not written_content:
                    raise FileProcessingError(f"写入文件失败: {output_file}")
            
            duration = time.time() - start_time
            
            return AsyncTranslationResult(
                task_id=task.task_id,
                success=True,
                source_file=input_file,
                target_file=output_file,
                source_text=content,
                translated_text=result.translated_text,
                duration=duration,
                chars_translated=result.chars_translated,
                elements_processed=result.elements_processed,
                cache_hits=result.cache_hits,
                metadata=result.metadata
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"文件翻译失败: {str(e)}"
            logger.error(error_msg)
            
            return AsyncTranslationResult(
                task_id=task.task_id,
                success=False,
                source_file=input_file,
                target_file=output_file,
                duration=duration,
                error=error_msg
            )
    
    def _generate_output_path(self, input_file: Path) -> Path:
        """生成输出文件路径"""
        # 如果输入文件在input目录下，则输出到output目录
        input_dir = Path(self.config.cli.input_dir)
        output_dir = Path(self.config.cli.output_dir)
        
        if input_file.is_relative_to(input_dir):
            relative_path = input_file.relative_to(input_dir)
            return output_dir / relative_path
        else:
            # 否则在同目录下添加后缀
            return input_file.with_suffix(f".translated{input_file.suffix}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()


# 便捷函数
async def create_async_translator(config: Optional[Config] = None) -> AsyncTranslator:
    """创建异步翻译器实例"""
    translator = AsyncTranslator(config)
    await translator.start()
    return translator