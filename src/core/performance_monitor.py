"""
UnityLangPX 性能监控模块

实现实时性能监控、指标收集和告警机制。
"""

import time
import asyncio
import threading
import psutil
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque
import json
from pathlib import Path

from .logger import get_logger
from .enhanced_error_handling import ErrorSeverity, create_enhanced_error, ErrorCategory
from ..config.manager import get_config_manager

logger = get_logger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """性能指标"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: float
    tags: Dict[str, str]
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class Alert:
    """性能告警"""
    name: str
    severity: AlertSeverity
    message: str
    timestamp: float
    metric_name: str
    current_value: float
    threshold: float
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class Threshold:
    """告警阈值"""
    metric_name: str
    operator: str  # ">", "<", ">=", "<=", "=="
    value: float
    severity: AlertSeverity
    message_template: str
    duration: Optional[float] = None  # 持续时间（秒），None表示立即触发
    
    def check(self, metric_value: float) -> bool:
        """检查是否触发告警"""
        if self.operator == ">":
            return metric_value > self.value
        elif self.operator == "<":
            return metric_value < self.value
        elif self.operator == ">=":
            return metric_value >= self.value
        elif self.operator == "<=":
            return metric_value <= self.value
        elif self.operator == "==":
            return metric_value == self.value
        return False
    
    def format_message(self, metric_value: float) -> str:
        """格式化告警消息"""
        return self.message_template.format(
            metric_name=self.metric_name,
            current_value=metric_value,
            threshold=self.value
        )


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, config=None):
        """
        初始化性能监控器
        
        Args:
            config: 性能监控配置，如果为None则从统一配置系统加载
        """
        # 如果没有提供配置，从统一配置系统加载
        if config is None:
            try:
                config_manager = get_config_manager()
                performance_config = config_manager.get_performance_config()
                config = performance_config.performance_monitor
            except Exception as e:
                logger.warning(f"无法加载性能监控配置，使用默认值: {str(e)}")
                # 使用默认配置
                from ..config.performance_models import PerformanceMonitorConfig
                config = PerformanceMonitorConfig()
        
        self.max_history = config.max_history
        self.monitor_interval = config.monitor_interval
        self.export_interval = config.export_interval
        self.export_dir = Path(config.export_dir)
        
        # 指标存储
        self.metrics: Dict[str, deque] = {}
        self.metric_lock = threading.RLock()
        
        # 告警配置
        self.thresholds: List[Threshold] = []
        self.alert_handlers: List[Callable] = []
        self.active_alerts: Dict[str, Alert] = {}
        
        # 系统信息
        self.system_info = self._get_system_info()
        
        # 监控状态
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 5.0  # 5秒
        self.shutdown_event = threading.Event()
        
        # 统计信息
        self.stats = {
            'metrics_collected': 0,
            'alerts_triggered': 0,
            'monitor_start_time': None,
            'last_collection_time': None
        }
        
        # 默认阈值
        self._setup_default_thresholds()
        
        logger.info("性能监控器初始化完成")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            return {
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'disk_total': psutil.disk_usage('/').total if os.name != 'nt' else psutil.disk_usage('C:').total,
                'platform': os.name,
                'python_version': os.sys.version,
                'process_id': os.getpid()
            }
        except Exception as e:
            logger.error(f"获取系统信息失败: {str(e)}")
            return {}
    
    def _setup_default_thresholds(self):
        """设置默认阈值"""
        # 从配置中获取阈值
        try:
            config_manager = get_config_manager()
            performance_config = config_manager.get_performance_config()
            monitor_config = performance_config.performance_monitor
            
            # CPU使用率
            self.add_threshold(Threshold(
                metric_name="cpu_usage_percent",
                operator=">",
                value=monitor_config.alert_cpu_threshold,
                severity=AlertSeverity.WARNING,
                message_template="CPU使用率过高: {current_value:.1f}% > {threshold:.1f}%"
            ))
            
            self.add_threshold(Threshold(
                metric_name="cpu_usage_percent",
                operator=">",
                value=monitor_config.alert_cpu_critical,
                severity=AlertSeverity.CRITICAL,
                message_template="CPU使用率严重过高: {current_value:.1f}% > {threshold:.1f}%",
                duration=10.0  # 持续10秒
            ))
            
            # 内存使用率
            self.add_threshold(Threshold(
                metric_name="memory_usage_percent",
                operator=">",
                value=monitor_config.alert_memory_threshold,
                severity=AlertSeverity.WARNING,
                message_template="内存使用率过高: {current_value:.1f}% > {threshold:.1f}%"
            ))
            
            self.add_threshold(Threshold(
                metric_name="memory_usage_percent",
                operator=">",
                value=monitor_config.alert_memory_critical,
                severity=AlertSeverity.CRITICAL,
                message_template="内存使用率严重过高: {current_value:.1f}% > {threshold:.1f}%",
                duration=10.0
            ))
            
            # 磁盘使用率
            self.add_threshold(Threshold(
                metric_name="disk_usage_percent",
                operator=">",
                value=monitor_config.alert_disk_threshold,
                severity=AlertSeverity.WARNING,
                message_template="磁盘使用率过高: {current_value:.1f}% > {threshold:.1f}%"
            ))
            
            # 翻译延迟
            self.add_threshold(Threshold(
                metric_name="translation_duration_seconds",
                operator=">",
                value=monitor_config.alert_translation_threshold,
                severity=AlertSeverity.WARNING,
                message_template="翻译延迟过高: {current_value:.1f}s > {threshold:.1f}s"
            ))
            
            self.add_threshold(Threshold(
                metric_name="translation_duration_seconds",
                operator=">",
                value=monitor_config.alert_translation_critical,
                severity=AlertSeverity.ERROR,
                message_template="翻译延迟严重过高: {current_value:.1f}s > {threshold:.1f}s"
            ))
            
            # API错误率
            self.add_threshold(Threshold(
                metric_name="api_error_rate",
                operator=">",
                value=monitor_config.alert_api_error_rate,
                severity=AlertSeverity.WARNING,
                message_template="API错误率过高: {current_value:.2%} > {threshold:.2%}"
            ))
            
            # 缓存命中率
            self.add_threshold(Threshold(
                metric_name="cache_hit_rate",
                operator="<",
                value=monitor_config.alert_cache_hit_rate,
                severity=AlertSeverity.WARNING,
                message_template="缓存命中率过低: {current_value:.2%} < {threshold:.2%}"
            ))
            
        except Exception as e:
            logger.warning(f"无法从配置加载阈值，使用默认值: {str(e)}")
            # 使用硬编码的默认值
            self._setup_fallback_thresholds()
        
        logger.debug(f"已设置 {len(self.thresholds)} 个阈值")
    
    def _setup_fallback_thresholds(self):
        """设置备用阈值（当配置加载失败时使用）"""
        # CPU使用率
        self.add_threshold(Threshold(
            metric_name="cpu_usage_percent",
            operator=">",
            value=80.0,
            severity=AlertSeverity.WARNING,
            message_template="CPU使用率过高: {current_value:.1f}% > {threshold:.1f}%"
        ))
        
        self.add_threshold(Threshold(
            metric_name="cpu_usage_percent",
            operator=">",
            value=95.0,
            severity=AlertSeverity.CRITICAL,
            message_template="CPU使用率严重过高: {current_value:.1f}% > {threshold:.1f}%",
            duration=10.0
        ))
        
        # 内存使用率
        self.add_threshold(Threshold(
            metric_name="memory_usage_percent",
            operator=">",
            value=80.0,
            severity=AlertSeverity.WARNING,
            message_template="内存使用率过高: {current_value:.1f}% > {threshold:.1f}%"
        ))
        
        # 磁盘使用率
        self.add_threshold(Threshold(
            metric_name="disk_usage_percent",
            operator=">",
            value=90.0,
            severity=AlertSeverity.WARNING,
            message_template="磁盘使用率过高: {current_value:.1f}% > {threshold:.1f}%"
        ))
        
        # 翻译延迟
        self.add_threshold(Threshold(
            metric_name="translation_duration_seconds",
            operator=">",
            value=30.0,
            severity=AlertSeverity.WARNING,
            message_template="翻译延迟过高: {current_value:.1f}s > {threshold:.1f}s"
        ))
        
        # API错误率
        self.add_threshold(Threshold(
            metric_name="api_error_rate",
            operator=">",
            value=0.1,
            severity=AlertSeverity.WARNING,
            message_template="API错误率过高: {current_value:.2%} > {threshold:.2%}"
        ))
        
        # 缓存命中率
        self.add_threshold(Threshold(
            metric_name="cache_hit_rate",
            operator="<",
            value=0.5,
            severity=AlertSeverity.WARNING,
            message_template="缓存命中率过低: {current_value:.2%} < {threshold:.2%}"
        ))
    
    def start_monitoring(self, interval: float = 5.0):
        """
        开始监控
        
        Args:
            interval: 监控间隔（秒）
        """
        if self.monitoring:
            logger.warning("性能监控已在运行")
            return
        
        self.monitoring = True
        self.monitor_interval = interval
        self.shutdown_event.clear()
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.stats['monitor_start_time'] = time.time()
        logger.info(f"性能监控已启动，间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        self.shutdown_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("性能监控已停止")
    
    def add_metric(self, name: str, value: float, metric_type: MetricType = MetricType.GAUGE,
                  tags: Optional[Dict[str, str]] = None, unit: Optional[str] = None):
        """
        添加指标
        
        Args:
            name: 指标名称
            value: 指标值
            metric_type: 指标类型
            tags: 标签
            unit: 单位
        """
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=time.time(),
            tags=tags or {},
            unit=unit
        )
        
        with self.metric_lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.max_history)
            
            self.metrics[name].append(metric)
            
            # 限制历史记录大小
            if len(self.metrics[name]) > self.max_history:
                self.metrics[name].popleft()
        
        self.stats['metrics_collected'] += 1
        self.stats['last_collection_time'] = time.time()
        
        # 检查阈值
        self._check_thresholds(metric)
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """
        增加计数器
        
        Args:
            name: 计数器名称
            value: 增加值
            tags: 标签
        """
        with self.metric_lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.max_history)
                # 初始化计数器
                self.metrics[name].append(Metric(
                    name=name,
                    value=0.0,
                    metric_type=MetricType.COUNTER,
                    timestamp=time.time(),
                    tags=tags or {}
                ))
            
            # 获取当前值并增加
            current_metric = self.metrics[name][-1]
            new_value = current_metric.value + value
            
            metric = Metric(
                name=name,
                value=new_value,
                metric_type=MetricType.COUNTER,
                timestamp=time.time(),
                tags=tags or {}
            )
            
            self.metrics[name].append(metric)
        
        self.stats['metrics_collected'] += 1
        self.stats['last_collection_time'] = time.time()
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """
        记录计时器
        
        Args:
            name: 计时器名称
            duration: 持续时间（秒）
            tags: 标签
        """
        self.add_metric(
            name=name,
            value=duration,
            metric_type=MetricType.TIMER,
            tags=tags,
            unit="seconds"
        )
    
    def add_threshold(self, threshold: Threshold):
        """
        添加告警阈值
        
        Args:
            threshold: 阈值配置
        """
        self.thresholds.append(threshold)
        logger.debug(f"添加阈值: {threshold.metric_name} {threshold.operator} {threshold.value}")
    
    def remove_threshold(self, metric_name: str):
        """
        移除指标的所有阈值
        
        Args:
            metric_name: 指标名称
        """
        self.thresholds = [t for t in self.thresholds if t.metric_name != metric_name]
        logger.debug(f"移除阈值: {metric_name}")
    
    def add_alert_handler(self, handler: Callable):
        """
        添加告警处理器
        
        Args:
            handler: 告警处理函数
        """
        self.alert_handlers.append(handler)
        logger.debug("添加告警处理器")
    
    def get_metrics(self, name: Optional[str] = None, 
                   since: Optional[float] = None, 
                   limit: Optional[int] = None) -> Dict[str, List[Metric]]:
        """
        获取指标
        
        Args:
            name: 指标名称，None表示获取所有
            since: 起始时间戳
            limit: 限制数量
            
        Returns:
            指标字典
        """
        with self.metric_lock:
            if name:
                if name in self.metrics:
                    metrics = list(self.metrics[name])
                else:
                    return {}
            else:
                metrics = []
                for metric_list in self.metrics.values():
                    metrics.extend(metric_list)
            
            # 过滤时间
            if since:
                metrics = [m for m in metrics if m.timestamp >= since]
            
            # 限制数量
            if limit:
                metrics = metrics[-limit:]
            
            # 按时间排序
            metrics.sort(key=lambda m: m.timestamp)
            
            if name:
                return {name: metrics}
            else:
                # 按名称分组
                result = {}
                for metric in metrics:
                    if metric.name not in result:
                        result[metric.name] = []
                    result[metric.name].append(metric)
                return result
    
    def get_metric_summary(self, name: str, since: Optional[float] = None) -> Dict[str, Any]:
        """
        获取指标摘要
        
        Args:
            name: 指标名称
            since: 起始时间戳
            
        Returns:
            指标摘要
        """
        metrics = self.get_metrics(name, since).get(name, [])
        
        if not metrics:
            return {
                'count': 0,
                'min': None,
                'max': None,
                'avg': None,
                'sum': None,
                'latest': None
            }
        
        values = [m.value for m in metrics]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'sum': sum(values),
            'latest': values[-1] if values else None,
            'first': values[0] if values else None,
            'timespan': metrics[-1].timestamp - metrics[0].timestamp if len(metrics) > 1 else 0
        }
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return list(self.active_alerts.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 添加系统信息
        stats['system_info'] = self.system_info
        
        # 添加监控状态
        stats['monitoring'] = self.monitoring
        stats['monitor_interval'] = self.monitor_interval
        
        # 添加指标统计
        with self.metric_lock:
            stats['metrics_count'] = len(self.metrics)
            stats['total_metrics'] = sum(len(m) for m in self.metrics.values())
        
        # 添加告警统计
        stats['thresholds_count'] = len(self.thresholds)
        stats['active_alerts_count'] = len(self.active_alerts)
        stats['alert_handlers_count'] = len(self.alert_handlers)
        
        return stats
    
    def export_metrics(self, file_path: Path, since: Optional[float] = None):
        """
        导出指标到文件
        
        Args:
            file_path: 文件路径
            since: 起始时间戳
        """
        try:
            metrics = self.get_metrics(since=since)
            
            # 转换为可序列化格式
            export_data = {
                'export_time': time.time(),
                'system_info': self.system_info,
                'metrics': {}
            }
            
            for name, metric_list in metrics.items():
                export_data['metrics'][name] = [m.to_dict() for m in metric_list]
            
            # 写入文件
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"指标已导出到: {file_path}")
            
        except Exception as e:
            logger.error(f"导出指标失败: {str(e)}")
    
    # 私有方法
    
    def _monitor_loop(self):
        """监控循环"""
        logger.info("性能监控循环启动")
        
        while self.monitoring and not self.shutdown_event.is_set():
            try:
                # 收集系统指标
                self._collect_system_metrics()
                
                # 等待下次监控
                self.shutdown_event.wait(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"监控循环错误: {str(e)}")
                time.sleep(1.0)
        
        logger.info("性能监控循环停止")
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1.0)
            self.add_metric("cpu_usage_percent", cpu_percent, unit="percent")
            
            # 内存使用率
            memory = psutil.virtual_memory()
            self.add_metric("memory_usage_bytes", memory.used, unit="bytes")
            self.add_metric("memory_usage_percent", memory.percent, unit="percent")
            
            # 磁盘使用率
            disk_path = '/' if os.name != 'nt' else 'C:'
            disk = psutil.disk_usage(disk_path)
            disk_percent = (disk.used / disk.total) * 100
            self.add_metric("disk_usage_bytes", disk.used, unit="bytes")
            self.add_metric("disk_usage_percent", disk_percent, unit="percent")
            
            # 进程信息
            process = psutil.Process()
            self.add_metric("process_cpu_percent", process.cpu_percent(), unit="percent")
            self.add_metric("process_memory_bytes", process.memory_info().rss, unit="bytes")
            
            # 网络I/O（可选）
            try:
                net_io = psutil.net_io_counters()
                self.add_metric("network_bytes_sent", net_io.bytes_sent, unit="bytes")
                self.add_metric("network_bytes_recv", net_io.bytes_recv, unit="bytes")
            except (AttributeError, OSError):
                # 某些系统可能不支持
                pass
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {str(e)}")
    
    def _check_thresholds(self, metric: Metric):
        """检查阈值"""
        for threshold in self.thresholds:
            if threshold.metric_name == metric.name:
                if threshold.check(metric.value):
                    self._trigger_alert(threshold, metric)
    
    def _trigger_alert(self, threshold: Threshold, metric: Metric):
        """触发告警"""
        alert_name = f"{threshold.metric_name}_{threshold.operator}_{threshold.value}"
        current_time = time.time()
        
        # 检查是否已有活跃告警
        if alert_name in self.active_alerts:
            existing_alert = self.active_alerts[alert_name]
            
            # 更新告警时间
            existing_alert.timestamp = current_time
            existing_alert.current_value = metric.value
            
            # 检查是否需要升级严重程度
            if threshold.severity.value > existing_alert.severity.value:
                existing_alert.severity = threshold.severity
                existing_alert.message = threshold.format_message(metric.value)
                
                # 重新触发告警
                self._notify_alert_handlers(existing_alert)
        else:
            # 创建新告警
            alert = Alert(
                name=alert_name,
                severity=threshold.severity,
                message=threshold.format_message(metric.value),
                timestamp=current_time,
                metric_name=metric.name,
                current_value=metric.value,
                threshold=threshold.value,
                tags=metric.tags
            )
            
            self.active_alerts[alert_name] = alert
            self.stats['alerts_triggered'] += 1
            
            # 通知告警处理器
            self._notify_alert_handlers(alert)
            
            logger.warning(f"触发告警: {alert.message}")
    
    def _notify_alert_handlers(self, alert: Alert):
        """通知告警处理器"""
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"告警处理器执行失败: {str(e)}")
    
    def _cleanup_expired_alerts(self):
        """清理过期告警"""
        current_time = time.time()
        expired_alerts = []
        
        for alert_name, alert in self.active_alerts.items():
            # 检查是否有持续时间要求
            threshold = next((t for t in self.thresholds if t.metric_name == alert.metric_name), None)
            
            if threshold and threshold.duration:
                # 检查是否超过持续时间
                if current_time - alert.timestamp >= threshold.duration:
                    # 检查是否仍然满足阈值条件
                    latest_metric = self.get_metrics(alert.metric_name, limit=1).get(alert.metric_name, [])
                    if latest_metric and not threshold.check(latest_metric[-1].value):
                        expired_alerts.append(alert_name)
        
        # 移除过期告警
        for alert_name in expired_alerts:
            alert = self.active_alerts.pop(alert_name)
            logger.info(f"告警已过期: {alert.message}")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop_monitoring()


# 全局性能监控实例
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def start_performance_monitoring(interval: float = 5.0):
    """启动全局性能监控"""
    monitor = get_performance_monitor()
    monitor.start_monitoring(interval)
    return monitor


def stop_performance_monitoring():
    """停止全局性能监控"""
    monitor = get_performance_monitor()
    monitor.stop_monitoring()


# 性能监控装饰器
def monitor_performance(metric_name: str, metric_type: MetricType = MetricType.TIMER):
    """性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # 记录成功指标
                if metric_type == MetricType.TIMER:
                    duration = time.time() - start_time
                    monitor.record_timer(metric_name, duration)
                else:
                    monitor.add_metric(metric_name, 1.0, metric_type)
                
                return result
                
            except Exception as e:
                # 记录失败指标
                monitor.add_metric(f"{metric_name}_error", 1.0, MetricType.COUNTER)
                
                # 创建增强错误
                error = create_enhanced_error(
                    message=f"函数执行失败: {func.__name__}",
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.MEDIUM,
                    details=str(e),
                    context={'function': func.__name__, 'args': str(args)[:100]}
                )
                
                raise error
        
        return wrapper
    return decorator


# 异步性能监控装饰器
def monitor_performance_async(metric_name: str, metric_type: MetricType = MetricType.TIMER):
    """异步性能监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # 记录成功指标
                if metric_type == MetricType.TIMER:
                    duration = time.time() - start_time
                    monitor.record_timer(metric_name, duration)
                else:
                    monitor.add_metric(metric_name, 1.0, metric_type)
                
                return result
                
            except Exception as e:
                # 记录失败指标
                monitor.add_metric(f"{metric_name}_error", 1.0, MetricType.COUNTER)
                
                # 创建增强错误
                error = create_enhanced_error(
                    message=f"异步函数执行失败: {func.__name__}",
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.MEDIUM,
                    details=str(e),
                    context={'function': func.__name__, 'args': str(args)[:100]}
                )
                
                raise error
        
        return wrapper
    return decorator