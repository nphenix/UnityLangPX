"""
UnityLangPX 批处理器模块

实现术语增强功能的批处理机制，提高大模型调用效率，
支持异步处理、智能批处理大小调整和优先级队列。
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from queue import PriorityQueue, Empty
import uuid

from .logger import get_logger

logger = get_logger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchTask:
    """批处理任务"""
    id: str
    task_type: str
    data: Any
    priority: TaskPriority
    created_at: float
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    processing_time: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """优先级队列排序"""
        return (self.priority.value, self.created_at) < (other.priority.value, other.created_at)


@dataclass
class BatchResult:
    """批处理结果"""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    processing_time: float = 0.0
    batch_size: int = 0


@dataclass
class BatchConfig:
    """批处理配置"""
    batch_size: int = 10
    max_wait_time: float = 1.0  # 最大等待时间(秒)
    max_concurrent_batches: int = 3
    worker_threads: int = 2
    enable_adaptive_batching: bool = True
    min_batch_size: int = 2
    max_batch_size: int = 20
    target_processing_time: float = 2.0  # 目标处理时间(秒)


class BatchProcessor:
    """批处理器"""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """
        初始化批处理器
        
        Args:
            config: 批处理配置
        """
        self.config = config or BatchConfig()
        
        # 任务队列
        self._task_queue = PriorityQueue()
        self._pending_tasks: Dict[str, BatchTask] = {}
        self._processing_tasks: Dict[str, BatchTask] = {}
        self._completed_tasks: Dict[str, BatchTask] = {}
        
        # 处理器注册
        self._processors: Dict[str, Callable] = {}
        
        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=self.config.worker_threads)
        
        # 批处理统计
        self._stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_batches': 0,
            'avg_batch_size': 0.0,
            'avg_processing_time': 0.0,
            'adaptive_adjustments': 0
        }
        
        # 控制标志
        self._running = False
        self._shutdown_event = threading.Event()
        
        # 自适应批处理
        self._adaptive_metrics = {
            'recent_batch_times': [],
            'recent_batch_sizes': [],
            'adjustment_history': []
        }
        
        # 线程锁
        self._lock = threading.RLock()
        
        logger.info("批处理器初始化完成")
    
    def register_processor(self, task_type: str, processor: Callable):
        """
        注册任务处理器
        
        Args:
            task_type: 任务类型
            processor: 处理器函数
        """
        with self._lock:
            self._processors[task_type] = processor
            logger.info(f"注册处理器: {task_type}")
    
    def submit_task(self, task_type: str, data: Any, 
                   priority: TaskPriority = TaskPriority.NORMAL,
                   task_id: Optional[str] = None) -> str:
        """
        提交任务
        
        Args:
            task_type: 任务类型
            data: 任务数据
            priority: 任务优先级
            task_id: 任务ID，None表示自动生成
            
        Returns:
            任务ID
        """
        if task_type not in self._processors:
            raise ValueError(f"未注册的任务类型: {task_type}")
        
        # 生成任务ID
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 创建任务
        task = BatchTask(
            id=task_id,
            task_type=task_type,
            data=data,
            priority=priority,
            created_at=time.time()
        )
        
        with self._lock:
            self._task_queue.put(task)
            self._pending_tasks[task_id] = task
            self._stats['total_tasks'] += 1
        
        logger.debug(f"提交任务: {task_id}, 类型: {task_type}, 优先级: {priority.name}")
        return task_id
    
    def submit_batch(self, task_type: str, data_list: List[Any],
                    priority: TaskPriority = TaskPriority.NORMAL) -> List[str]:
        """
        提交批量任务
        
        Args:
            task_type: 任务类型
            data_list: 数据列表
            priority: 任务优先级
            
        Returns:
            任务ID列表
        """
        task_ids = []
        for data in data_list:
            task_id = self.submit_task(task_type, data, priority)
            task_ids.append(task_id)
        
        return task_ids
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态或None
        """
        with self._lock:
            # 检查各个阶段的任务
            if task_id in self._pending_tasks:
                return self._pending_tasks[task_id].status
            elif task_id in self._processing_tasks:
                return self._processing_tasks[task_id].status
            elif task_id in self._completed_tasks:
                return self._completed_tasks[task_id].status
            else:
                return None
    
    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[BatchResult]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间(秒)
            
        Returns:
            任务结果或None
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                if task_id in self._completed_tasks:
                    task = self._completed_tasks[task_id]
                    return BatchResult(
                        task_id=task_id,
                        success=task.status == TaskStatus.COMPLETED,
                        result=task.result,
                        error=task.error,
                        processing_time=task.processing_time,
                        batch_size=1  # 单个任务
                    )
            
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            # 短暂等待
            time.sleep(0.1)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否取消成功
        """
        with self._lock:
            # 只能取消待处理的任务
            if task_id in self._pending_tasks:
                task = self._pending_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                del self._pending_tasks[task_id]
                self._completed_tasks[task_id] = task
                logger.info(f"取消任务: {task_id}")
                return True
            else:
                return False
    
    def start(self):
        """启动批处理器"""
        with self._lock:
            if self._running:
                logger.warning("批处理器已在运行")
                return
            
            self._running = True
            self._shutdown_event.clear()
            
            # 启动批处理线程
            self._batch_thread = threading.Thread(target=self._batch_worker, daemon=True)
            self._batch_thread.start()
            
            logger.info("批处理器已启动")
    
    def stop(self, wait_for_completion: bool = True, timeout: float = 30.0):
        """
        停止批处理器
        
        Args:
            wait_for_completion: 是否等待完成
            timeout: 等待超时时间(秒)
        """
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            self._shutdown_event.set()
        
        if wait_for_completion:
            start_time = time.time()
            
            # 等待批处理线程完成
            if hasattr(self, '_batch_thread'):
                self._batch_thread.join(timeout=max(0, timeout - (time.time() - start_time)))
            
            # 等待所有任务完成
            remaining_time = max(0, timeout - (time.time() - start_time))
            self._wait_for_tasks_completion(remaining_time)
        
        # 关闭线程池
        self._executor.shutdown(wait=wait_for_completion)
        
        logger.info("批处理器已停止")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()
            
            # 添加当前状态信息
            stats.update({
                'pending_tasks': len(self._pending_tasks),
                'processing_tasks': len(self._processing_tasks),
                'completed_tasks': len(self._completed_tasks),
                'queue_size': self._task_queue.qsize(),
                'running': self._running,
                'config': {
                    'batch_size': self.config.batch_size,
                    'max_wait_time': self.config.max_wait_time,
                    'max_concurrent_batches': self.config.max_concurrent_batches,
                    'worker_threads': self.config.worker_threads
                }
            })
            
            # 添加自适应指标
            if self.config.enable_adaptive_batching:
                stats['adaptive_metrics'] = {
                    'recent_avg_batch_time': self._get_recent_avg_batch_time(),
                    'recent_avg_batch_size': self._get_recent_avg_batch_size(),
                    'adjustment_count': len(self._adaptive_metrics['adjustment_history'])
                }
            
            return stats
    
    def reset_statistics(self):
        """重置统计信息"""
        with self._lock:
            self._stats = {
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'total_batches': 0,
                'avg_batch_size': 0.0,
                'avg_processing_time': 0.0,
                'adaptive_adjustments': 0
            }
            
            self._adaptive_metrics = {
                'recent_batch_times': [],
                'recent_batch_sizes': [],
                'adjustment_history': []
            }
        
        logger.info("批处理统计已重置")
    
    # 私有方法
    
    def _batch_worker(self):
        """批处理工作线程"""
        logger.info("批处理工作线程启动")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # 收集批次
                batch = self._collect_batch()
                
                if batch:
                    # 处理批次
                    self._process_batch(batch)
                else:
                    # 没有任务，短暂等待
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"批处理工作线程错误: {str(e)}")
                time.sleep(1.0)
        
        logger.info("批处理工作线程停止")
    
    def _collect_batch(self) -> List[BatchTask]:
        """收集批次任务"""
        batch = []
        deadline = time.time() + self.config.max_wait_time
        
        while (len(batch) < self.config.batch_size and 
               time.time() < deadline and
               self._running and not self._shutdown_event.is_set()):
            
            try:
                # 获取任务（非阻塞）
                task = self._task_queue.get_nowait()
                
                with self._lock:
                    if task.id in self._pending_tasks:
                        batch.append(task)
                        del self._pending_tasks[task.id]
                        self._processing_tasks[task.id] = task
                
            except Empty:
                # 队列为空，检查是否需要等待
                if len(batch) > 0:
                    # 已有任务，不再等待
                    break
                else:
                    # 没有任务，短暂等待
                    time.sleep(0.01)
        
        return batch
    
    def _process_batch(self, batch: List[BatchTask]):
        """处理批次任务"""
        if not batch:
            return
        
        start_time = time.time()
        batch_size = len(batch)
        
        # 按任务类型分组
        task_groups = {}
        for task in batch:
            if task.task_type not in task_groups:
                task_groups[task.task_type] = []
            task_groups[task.task_type].append(task)
        
        # 提交到线程池处理
        futures = []
        for task_type, tasks in task_groups.items():
            processor = self._processors[task_type]
            future = self._executor.submit(self._process_task_group, processor, tasks)
            futures.append(future)
        
        # 等待所有任务完成
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logger.error(f"批处理任务组失败: {str(e)}")
        
        # 更新统计信息
        processing_time = time.time() - start_time
        self._update_batch_statistics(batch_size, processing_time)
        
        # 自适应调整
        if self.config.enable_adaptive_batching:
            self._adaptive_adjustment(batch_size, processing_time)
        
        logger.debug(f"批处理完成: {batch_size} 个任务, 耗时: {processing_time:.2f}秒")
    
    def _process_task_group(self, processor: Callable, tasks: List[BatchTask]):
        """处理任务组"""
        for task in tasks:
            try:
                # 更新任务状态
                task.status = TaskStatus.PROCESSING
                task_start = time.time()
                
                # 调用处理器
                result = processor(task.data)
                
                # 更新任务结果
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.processing_time = time.time() - task_start
                
                # 移动到完成队列
                with self._lock:
                    if task.id in self._processing_tasks:
                        del self._processing_tasks[task.id]
                    self._completed_tasks[task.id] = task
                    self._stats['completed_tasks'] += 1
                
            except Exception as e:
                # 处理失败
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.processing_time = time.time() - task_start
                
                # 检查是否需要重试
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING
                    
                    # 重新提交到队列
                    with self._lock:
                        if task.id in self._processing_tasks:
                            del self._processing_tasks[task.id]
                        self._pending_tasks[task.id] = task
                        self._task_queue.put(task)
                    
                    logger.warning(f"任务失败，重新提交: {task.id}, 重试次数: {task.retry_count}")
                else:
                    # 超过最大重试次数，标记为失败
                    with self._lock:
                        if task.id in self._processing_tasks:
                            del self._processing_tasks[task.id]
                        self._completed_tasks[task.id] = task
                        self._stats['failed_tasks'] += 1
                    
                    logger.error(f"任务最终失败: {task.id}, 错误: {str(e)}")
    
    def _update_batch_statistics(self, batch_size: int, processing_time: float):
        """更新批处理统计信息"""
        with self._lock:
            self._stats['total_batches'] += 1
            
            # 更新平均批次大小
            total_batches = self._stats['total_batches']
            current_avg = self._stats['avg_batch_size']
            self._stats['avg_batch_size'] = (current_avg * (total_batches - 1) + batch_size) / total_batches
            
            # 更新平均处理时间
            current_avg_time = self._stats['avg_processing_time']
            self._stats['avg_processing_time'] = (current_avg_time * (total_batches - 1) + processing_time) / total_batches
            
            # 记录最近的指标
            self._adaptive_metrics['recent_batch_times'].append(processing_time)
            self._adaptive_metrics['recent_batch_sizes'].append(batch_size)
            
            # 保持最近20个记录
            if len(self._adaptive_metrics['recent_batch_times']) > 20:
                self._adaptive_metrics['recent_batch_times'].pop(0)
            if len(self._adaptive_metrics['recent_batch_sizes']) > 20:
                self._adaptive_metrics['recent_batch_sizes'].pop(0)
    
    def _adaptive_adjustment(self, batch_size: int, processing_time: float):
        """自适应调整批处理大小"""
        if not self.config.enable_adaptive_batching:
            return
        
        # 计算最近的平均处理时间
        recent_avg_time = self._get_recent_avg_batch_time()
        
        # 如果处理时间太长，减小批次大小
        if processing_time > self.config.target_processing_time * 1.5:
            new_size = max(self.config.min_batch_size, int(batch_size * 0.8))
            if new_size != self.config.batch_size:
                self.config.batch_size = new_size
                self._adaptive_metrics['adjustment_history'].append({
                    'timestamp': time.time(),
                    'old_size': batch_size,
                    'new_size': new_size,
                    'reason': 'processing_time_too_high',
                    'processing_time': processing_time
                })
                self._stats['adaptive_adjustments'] += 1
                logger.info(f"自适应调整批次大小: {batch_size} -> {new_size} (处理时间过长)")
        
        # 如果处理时间很短且批次大小较小，可以增加批次大小
        elif (processing_time < self.config.target_processing_time * 0.5 and 
              batch_size < self.config.max_batch_size and
              recent_avg_time < self.config.target_processing_time * 0.7):
            new_size = min(self.config.max_batch_size, int(batch_size * 1.2))
            if new_size != self.config.batch_size:
                self.config.batch_size = new_size
                self._adaptive_metrics['adjustment_history'].append({
                    'timestamp': time.time(),
                    'old_size': batch_size,
                    'new_size': new_size,
                    'reason': 'processing_time_too_low',
                    'processing_time': processing_time
                })
                self._stats['adaptive_adjustments'] += 1
                logger.info(f"自适应调整批次大小: {batch_size} -> {new_size} (处理时间较短)")
    
    def _get_recent_avg_batch_time(self) -> float:
        """获取最近的平均批处理时间"""
        times = self._adaptive_metrics['recent_batch_times']
        if not times:
            return 0.0
        return sum(times) / len(times)
    
    def _get_recent_avg_batch_size(self) -> float:
        """获取最近的平均批次大小"""
        sizes = self._adaptive_metrics['recent_batch_sizes']
        if not sizes:
            return 0.0
        return sum(sizes) / len(sizes)
    
    def _wait_for_tasks_completion(self, timeout: float):
        """等待任务完成"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            with self._lock:
                if not self._processing_tasks and not self._pending_tasks:
                    break
            
            time.sleep(0.1)


class TerminologyBatchProcessor:
    """术语批处理器，专门用于术语增强功能"""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """
        初始化术语批处理器
        
        Args:
            config: 批处理配置
        """
        self.batch_processor = BatchProcessor(config)
        
        # 注册术语增强处理器
        self.batch_processor.register_processor('context_translation', self._process_context_translation)
        self.batch_processor.register_processor('fuzzy_matching', self._process_fuzzy_matching)
        self.batch_processor.register_processor('disambiguation', self._process_disambiguation)
        
        logger.info("术语批处理器初始化完成")
    
    def submit_context_translation(self, term: str, context: str, 
                                  source_lang: str, target_lang: str,
                                  priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """提交上下文感知翻译任务"""
        data = {
            'term': term,
            'context': context,
            'source_lang': source_lang,
            'target_lang': target_lang
        }
        return self.batch_processor.submit_task('context_translation', data, priority)
    
    def submit_fuzzy_matching(self, text: str, potential_terms: List[str],
                            source_lang: str, target_lang: str,
                            priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """提交模糊匹配任务"""
        data = {
            'text': text,
            'potential_terms': potential_terms,
            'source_lang': source_lang,
            'target_lang': target_lang
        }
        return self.batch_processor.submit_task('fuzzy_matching', data, priority)
    
    def submit_disambiguation(self, term: str, context: str,
                            source_lang: str, target_lang: str,
                            priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """提交术语消歧任务"""
        data = {
            'term': term,
            'context': context,
            'source_lang': source_lang,
            'target_lang': target_lang
        }
        return self.batch_processor.submit_task('disambiguation', data, priority)
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[BatchResult]:
        """获取任务结果"""
        return self.batch_processor.get_task_result(task_id, timeout)
    
    def start(self):
        """启动批处理器"""
        self.batch_processor.start()
    
    def stop(self, wait_for_completion: bool = True, timeout: float = 30.0):
        """停止批处理器"""
        self.batch_processor.stop(wait_for_completion, timeout)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.batch_processor.get_statistics()
    
    # 私有处理器方法
    
    def _process_context_translation(self, data: Dict[str, Any]) -> Any:
        """处理上下文感知翻译"""
        # 这里应该调用实际的术语增强服务
        # 为了示例，返回模拟结果
        term = data['term']
        context = data['context']
        source_lang = data['source_lang']
        target_lang = data['target_lang']
        
        # 模拟处理时间
        time.sleep(0.1)
        
        return {
            'original_term': term,
            'enhanced_translation': f"[增强]{term}",
            'confidence': 0.9,
            'processing_time': 0.1
        }
    
    def _process_fuzzy_matching(self, data: Dict[str, Any]) -> Any:
        """处理模糊匹配"""
        # 模拟处理
        time.sleep(0.05)
        
        return {
            'matches': [],
            'confidence': 0.8,
            'processing_time': 0.05
        }
    
    def _process_disambiguation(self, data: Dict[str, Any]) -> Any:
        """处理术语消歧"""
        # 模拟处理
        time.sleep(0.15)
        
        return {
            'disambiguated_term': data['term'],
            'translation': f"[消歧]{data['term']}",
            'confidence': 0.85,
            'processing_time': 0.15
        }


# 便捷函数
def get_terminology_batch_processor(config: Optional[BatchConfig] = None) -> TerminologyBatchProcessor:
    """获取术语批处理器实例"""
    processor = TerminologyBatchProcessor(config)
    processor.start()
    return processor