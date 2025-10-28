"""
UnityLangPX 增强错误处理模块

实现分层错误处理、智能恢复机制和用户友好的错误信息。
"""

import time
import traceback
import asyncio
from typing import Optional, Dict, Any, List, Callable, Union
from enum import Enum
from dataclasses import dataclass, asdict

from .logger import get_logger
from .exceptions import UnityLangPXError

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""
    NETWORK = "network"
    API = "api"
    FILE_IO = "file_io"
    VALIDATION = "validation"
    TRANSLATION = "translation"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    CACHE = "cache"
    AUTHENTICATION = "authentication"


class RecoveryAction(Enum):
    """恢复动作"""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    USER_INTERVENTION = "user_intervention"


@dataclass
class ErrorContext:
    """错误上下文"""
    file_path: Optional[str] = None
    model_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class RecoveryStrategy:
    """恢复策略"""
    name: str
    category: ErrorCategory
    severity_range: tuple  # (min_severity, max_severity)
    max_attempts: int
    backoff_factor: float
    actions: List[RecoveryAction]
    custom_handler: Optional[Callable] = None


class EnhancedUnityLangPXError(UnityLangPXError):
    """增强的UnityLangPX错误类"""
    
    def __init__(self, 
                 message: str, 
                 category: ErrorCategory,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 details: Optional[str] = None,
                 context: Optional[ErrorContext] = None,
                 retry_suggested: bool = False,
                 user_message: Optional[str] = None,
                 recovery_actions: Optional[List[RecoveryAction]] = None,
                 error_code: Optional[str] = None,
                 timestamp: Optional[float] = None):
        super().__init__(message, details)
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext()
        self.retry_suggested = retry_suggested
        self.user_message = user_message or message
        self.recovery_actions = recovery_actions or []
        self.error_code = error_code
        self.timestamp = timestamp or time.time()
        self.stack_trace = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "context": self.context.to_dict(),
            "retry_suggested": self.retry_suggested,
            "user_message": self.user_message,
            "recovery_actions": [action.value for action in self.recovery_actions],
            "error_code": self.error_code,
            "timestamp": self.timestamp,
            "stack_trace": self.stack_trace
        }
    
    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return self.user_message


class ErrorMessageLocalizer:
    """错误信息本地化"""
    
    def __init__(self, language: str = "zh"):
        self.language = language
        self.messages = self._load_messages(language)
    
    def _load_messages(self, language: str) -> Dict[str, str]:
        """加载本地化消息"""
        messages = {
            "zh": {
                # 网络错误
                "network_connection_failed": "网络连接失败，请检查网络设置",
                "network_timeout": "网络请求超时，请稍后重试",
                "network_dns_error": "DNS解析失败，请检查网络连接",
                
                # API错误
                "api_authentication_failed": "API认证失败，请检查API密钥",
                "api_rate_limit": "API请求频率超限，请稍后重试",
                "api_quota_exceeded": "API配额已用完，请升级套餐或等待重置",
                "api_model_not_found": "指定的模型不可用，请检查模型名称",
                "api_server_error": "API服务器错误，请稍后重试",
                
                # 文件I/O错误
                "file_not_found": "文件不存在：{file_path}",
                "file_permission_denied": "文件权限不足：{file_path}",
                "file_disk_full": "磁盘空间不足",
                "file_corrupted": "文件已损坏：{file_path}",
                
                # 验证错误
                "validation_invalid_config": "配置无效：{details}",
                "validation_invalid_parameter": "参数无效：{parameter}",
                "validation_missing_required": "缺少必需参数：{parameter}",
                
                # 翻译错误
                "translation_failed": "翻译失败：{details}",
                "translation_model_error": "翻译模型错误：{details}",
                "translation_text_too_long": "文本过长，已超出限制",
                
                # 系统错误
                "system_memory_insufficient": "系统内存不足",
                "system_resource_exhausted": "系统资源已耗尽",
                "system_internal_error": "系统内部错误：{details}",
                
                # 缓存错误
                "cache_corrupted": "缓存已损坏",
                "cache_full": "缓存空间已满",
                "cache_io_error": "缓存读写错误",
                
                # 配置错误
                "config_file_not_found": "配置文件不存在：{file_path}",
                "config_invalid_format": "配置文件格式无效",
                "config_missing_section": "配置文件缺少必需节：{section}",
                
                # 认证错误
                "auth_invalid_credentials": "认证凭据无效",
                "auth_token_expired": "认证令牌已过期",
                "auth_permission_denied": "权限不足",
                
                # 通用错误
                "unknown_error": "未知错误：{details}",
                "operation_cancelled": "操作已取消",
                "operation_timeout": "操作超时"
            },
            "en": {
                # Network errors
                "network_connection_failed": "Network connection failed, please check network settings",
                "network_timeout": "Network request timeout, please try again later",
                "network_dns_error": "DNS resolution failed, please check network connection",
                
                # API errors
                "api_authentication_failed": "API authentication failed, please check API key",
                "api_rate_limit": "API rate limit exceeded, please try again later",
                "api_quota_exceeded": "API quota exceeded, please upgrade plan or wait for reset",
                "api_model_not_found": "Specified model not available, please check model name",
                "api_server_error": "API server error, please try again later",
                
                # File I/O errors
                "file_not_found": "File not found: {file_path}",
                "file_permission_denied": "File permission denied: {file_path}",
                "file_disk_full": "Disk space is full",
                "file_corrupted": "File is corrupted: {file_path}",
                
                # Validation errors
                "validation_invalid_config": "Invalid configuration: {details}",
                "validation_invalid_parameter": "Invalid parameter: {parameter}",
                "validation_missing_required": "Missing required parameter: {parameter}",
                
                # Translation errors
                "translation_failed": "Translation failed: {details}",
                "translation_model_error": "Translation model error: {details}",
                "translation_text_too_long": "Text too long, exceeds limit",
                
                # System errors
                "system_memory_insufficient": "Insufficient system memory",
                "system_resource_exhausted": "System resources exhausted",
                "system_internal_error": "System internal error: {details}",
                
                # Cache errors
                "cache_corrupted": "Cache is corrupted",
                "cache_full": "Cache space is full",
                "cache_io_error": "Cache I/O error",
                
                # Configuration errors
                "config_file_not_found": "Configuration file not found: {file_path}",
                "config_invalid_format": "Invalid configuration file format",
                "config_missing_section": "Missing required section in configuration: {section}",
                
                # Authentication errors
                "auth_invalid_credentials": "Invalid authentication credentials",
                "auth_token_expired": "Authentication token expired",
                "auth_permission_denied": "Permission denied",
                
                # Generic errors
                "unknown_error": "Unknown error: {details}",
                "operation_cancelled": "Operation cancelled",
                "operation_timeout": "Operation timeout"
            }
        }
        
        return messages.get(language, messages["en"])
    
    def get_user_message(self, error: EnhancedUnityLangPXError) -> str:
        """获取用户友好的错误信息"""
        # 生成错误键
        error_key = f"{error.category.value}_{error.error_code}" if error.error_code else error.category.value
        
        # 获取消息模板
        template = self.messages.get(error_key, self.messages.get("unknown_error"))
        
        if template:
            # 格式化消息
            try:
                return template.format(
                    message=error.message,
                    details=error.details or "",
                    file_path=error.context.file_path or "",
                    parameter=error.context.additional_data.get("parameter", "") if error.context.additional_data else "",
                    section=error.context.additional_data.get("section", "") if error.context.additional_data else "",
                    model_name=error.context.model_name or "",
                    operation=error.context.operation or ""
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"错误消息格式化失败: {str(e)}")
                return error.user_message
        
        return error.user_message


class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self):
        self.recovery_strategies: Dict[ErrorCategory, List[RecoveryStrategy]] = {}
        self.custom_handlers: Dict[str, Callable] = {}
        self.localizer = ErrorMessageLocalizer()
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认恢复策略"""
        # 网络错误恢复策略
        self.register_strategy(RecoveryStrategy(
            name="network_retry",
            category=ErrorCategory.NETWORK,
            severity_range=(ErrorSeverity.LOW, ErrorSeverity.HIGH),
            max_attempts=3,
            backoff_factor=2.0,
            actions=[RecoveryAction.RETRY],
            custom_handler=self._handle_network_error
        ))
        
        self.register_strategy(RecoveryStrategy(
            name="network_fallback",
            category=ErrorCategory.NETWORK,
            severity_range=(ErrorSeverity.CRITICAL, ErrorSeverity.CRITICAL),
            max_attempts=1,
            backoff_factor=1.0,
            actions=[RecoveryAction.FALLBACK, RecoveryAction.USER_INTERVENTION],
            custom_handler=self._handle_network_critical_error
        ))
        
        # API错误恢复策略
        self.register_strategy(RecoveryStrategy(
            name="api_retry",
            category=ErrorCategory.API,
            severity_range=(ErrorSeverity.LOW, ErrorSeverity.MEDIUM),
            max_attempts=3,
            backoff_factor=1.5,
            actions=[RecoveryAction.RETRY],
            custom_handler=self._handle_api_error
        ))
        
        self.register_strategy(RecoveryStrategy(
            name="api_rate_limit",
            category=ErrorCategory.API,
            severity_range=(ErrorSeverity.MEDIUM, ErrorSeverity.HIGH),
            max_attempts=5,
            backoff_factor=2.0,
            actions=[RecoveryAction.RETRY],
            custom_handler=self._handle_api_rate_limit
        ))
        
        # 文件I/O错误恢复策略
        self.register_strategy(RecoveryStrategy(
            name="file_io_retry",
            category=ErrorCategory.FILE_IO,
            severity_range=(ErrorSeverity.LOW, ErrorSeverity.MEDIUM),
            max_attempts=2,
            backoff_factor=1.0,
            actions=[RecoveryAction.RETRY],
            custom_handler=self._handle_file_io_error
        ))
        
        # 翻译错误恢复策略
        self.register_strategy(RecoveryStrategy(
            name="translation_retry",
            category=ErrorCategory.TRANSLATION,
            severity_range=(ErrorSeverity.LOW, ErrorSeverity.MEDIUM),
            max_attempts=2,
            backoff_factor=1.5,
            actions=[RecoveryAction.RETRY],
            custom_handler=self._handle_translation_error
        ))
        
        self.register_strategy(RecoveryStrategy(
            name="translation_fallback",
            category=ErrorCategory.TRANSLATION,
            severity_range=(ErrorSeverity.HIGH, ErrorSeverity.CRITICAL),
            max_attempts=1,
            backoff_factor=1.0,
            actions=[RecoveryAction.FALLBACK],
            custom_handler=self._handle_translation_critical_error
        ))
    
    def register_strategy(self, strategy: RecoveryStrategy):
        """注册恢复策略"""
        if strategy.category not in self.recovery_strategies:
            self.recovery_strategies[strategy.category] = []
        
        self.recovery_strategies[strategy.category].append(strategy)
        logger.debug(f"注册恢复策略: {strategy.name} for {strategy.category.value}")
    
    def register_custom_handler(self, name: str, handler: Callable):
        """注册自定义处理器"""
        self.custom_handlers[name] = handler
        logger.debug(f"注册自定义处理器: {name}")
    
    async def recover(self, error: EnhancedUnityLangPXError, context: Optional[Dict[str, Any]] = None) -> bool:
        """尝试恢复错误"""
        logger.info(f"尝试恢复错误: {error.category.value} - {error.message}")
        
        # 获取适用的恢复策略
        strategies = self.recovery_strategies.get(error.category, [])
        
        # 按严重程度筛选策略
        applicable_strategies = []
        for strategy in strategies:
            min_severity, max_severity = strategy.severity_range
            if self._severity_compare(min_severity, error.severity) <= 0 and \
               self._severity_compare(error.severity, max_severity) <= 0:
                applicable_strategies.append(strategy)
        
        # 按优先级排序（严重程度高的优先）
        applicable_strategies.sort(key=lambda s: self._severity_compare(s.severity_range[1], ErrorSeverity.LOW), reverse=True)
        
        # 尝试恢复
        for strategy in applicable_strategies:
            try:
                if strategy.custom_handler:
                    result = await strategy.custom_handler(error, context or {})
                    if result:
                        logger.info(f"错误恢复成功: {strategy.name}")
                        return True
                
                # 执行默认恢复动作
                for action in strategy.actions:
                    if await self._execute_recovery_action(action, error, context or {}):
                        logger.info(f"错误恢复成功: {strategy.name} - {action.value}")
                        return True
                
            except Exception as e:
                logger.error(f"恢复策略执行失败: {strategy.name} - {str(e)}")
                continue
        
        logger.warning(f"所有恢复策略都失败了: {error.category.value} - {error.message}")
        return False
    
    def _severity_compare(self, severity1: ErrorSeverity, severity2: ErrorSeverity) -> int:
        """比较错误严重程度"""
        severity_order = [ErrorSeverity.LOW, ErrorSeverity.MEDIUM, ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
        return severity_order.index(severity1) - severity_order.index(severity2)
    
    async def _execute_recovery_action(self, action: RecoveryAction, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """执行恢复动作"""
        if action == RecoveryAction.RETRY:
            return await self._execute_retry(error, context)
        elif action == RecoveryAction.FALLBACK:
            return await self._execute_fallback(error, context)
        elif action == RecoveryAction.SKIP:
            return await self._execute_skip(error, context)
        elif action == RecoveryAction.ABORT:
            return await self._execute_abort(error, context)
        elif action == RecoveryAction.USER_INTERVENTION:
            return await self._execute_user_intervention(error, context)
        
        return False
    
    async def _execute_retry(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """执行重试动作"""
        retry_func = context.get('retry_func')
        if not retry_func:
            logger.warning("重试动作需要提供retry_func")
            return False
        
        max_attempts = context.get('max_attempts', 3)
        current_attempt = context.get('current_attempt', 0) + 1
        
        if current_attempt > max_attempts:
            logger.warning(f"已达到最大重试次数: {max_attempts}")
            return False
        
        # 计算退避延迟
        backoff_factor = context.get('backoff_factor', 2.0)
        delay = min(60, (backoff_factor ** (current_attempt - 1)))  # 最大60秒
        
        if delay > 0:
            logger.info(f"等待 {delay:.1f} 秒后重试 (尝试 {current_attempt}/{max_attempts})")
            await asyncio.sleep(delay)
        
        # 执行重试
        try:
            await retry_func()
            return True
        except Exception as e:
            logger.warning(f"重试失败: {str(e)}")
            return False
    
    async def _execute_fallback(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """执行降级动作"""
        fallback_func = context.get('fallback_func')
        if not fallback_func:
            logger.warning("降级动作需要提供fallback_func")
            return False
        
        try:
            await fallback_func()
            return True
        except Exception as e:
            logger.error(f"降级动作失败: {str(e)}")
            return False
    
    async def _execute_skip(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """执行跳过动作"""
        skip_func = context.get('skip_func')
        if not skip_func:
            logger.warning("跳过动作需要提供skip_func")
            return False
        
        try:
            await skip_func()
            return True
        except Exception as e:
            logger.error(f"跳过动作失败: {str(e)}")
            return False
    
    async def _execute_abort(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """执行中止动作"""
        abort_func = context.get('abort_func')
        if not abort_func:
            logger.warning("中止动作需要提供abort_func")
            return False
        
        try:
            await abort_func()
            return True
        except Exception as e:
            logger.error(f"中止动作失败: {str(e)}")
            return False
    
    async def _execute_user_intervention(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """执行用户干预动作"""
        # 记录需要用户干预的错误
        logger.error(f"需要用户干预: {error.user_message}")
        
        # 可以在这里添加通知逻辑，如发送邮件、推送等
        notification_func = context.get('notification_func')
        if notification_func:
            try:
                await notification_func(error)
            except Exception as e:
                logger.error(f"用户干预通知失败: {str(e)}")
        
        return False  # 用户干预需要外部处理，这里返回False
    
    # 默认错误处理器
    
    async def _handle_network_error(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理网络错误"""
        if error.error_code == "network_connection_failed":
            # 检查网络连接
            return await self._check_network_connectivity()
        elif error.error_code == "network_timeout":
            # 增加超时时间
            return await self._adjust_timeout(context, increase=True)
        elif error.error_code == "network_dns_error":
            # 尝试使用备用DNS
            return await self._try_backup_dns(context)
        
        return False
    
    async def _handle_network_critical_error(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理严重网络错误"""
        # 切换到离线模式
        return await self._switch_to_offline_mode(context)
    
    async def _handle_api_error(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理API错误"""
        if error.error_code == "api_authentication_failed":
            # 刷新API密钥
            return await self._refresh_api_key(context)
        elif error.error_code == "api_model_not_found":
            # 切换到备用模型
            return await self._switch_to_backup_model(context)
        
        return False
    
    async def _handle_api_rate_limit(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理API限流错误"""
        # 实施请求限流
        return await self._implement_rate_limiting(context)
    
    async def _handle_file_io_error(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理文件I/O错误"""
        if error.error_code == "file_permission_denied":
            # 尝试修复权限
            return await self._fix_file_permissions(error.context.file_path, context)
        elif error.error_code == "file_disk_full":
            # 清理临时文件
            return await self._cleanup_temp_files(context)
        
        return False
    
    async def _handle_translation_error(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理翻译错误"""
        if error.error_code == "translation_text_too_long":
            # 分割文本
            return await self._split_long_text(context)
        elif error.error_code == "translation_model_error":
            # 重置模型连接
            return await self._reset_model_connection(context)
        
        return False
    
    async def _handle_translation_critical_error(self, error: EnhancedUnityLangPXError, context: Dict[str, Any]) -> bool:
        """处理严重翻译错误"""
        # 切换到备用翻译服务
        return await self._switch_to_backup_translation_service(context)
    
    # 辅助方法
    
    async def _check_network_connectivity(self) -> bool:
        """检查网络连接"""
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get('https://www.google.com') as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def _adjust_timeout(self, context: Dict[str, Any], increase: bool = True) -> bool:
        """调整超时设置"""
        timeout_adjuster = context.get('timeout_adjuster')
        if not timeout_adjuster:
            return False
        
        try:
            if increase:
                await timeout_adjuster(increase=True)
            else:
                await timeout_adjuster(increase=False)
            return True
        except Exception:
            return False
    
    async def _try_backup_dns(self, context: Dict[str, Any]) -> bool:
        """尝试使用备用DNS"""
        dns_switcher = context.get('dns_switcher')
        if not dns_switcher:
            return False
        
        try:
            await dns_switcher()
            return True
        except Exception:
            return False
    
    async def _switch_to_offline_mode(self, context: Dict[str, Any]) -> bool:
        """切换到离线模式"""
        offline_switcher = context.get('offline_switcher')
        if not offline_switcher:
            return False
        
        try:
            await offline_switcher()
            return True
        except Exception:
            return False
    
    async def _refresh_api_key(self, context: Dict[str, Any]) -> bool:
        """刷新API密钥"""
        api_key_refresher = context.get('api_key_refresher')
        if not api_key_refresher:
            return False
        
        try:
            await api_key_refresher()
            return True
        except Exception:
            return False
    
    async def _switch_to_backup_model(self, context: Dict[str, Any]) -> bool:
        """切换到备用模型"""
        model_switcher = context.get('model_switcher')
        if not model_switcher:
            return False
        
        try:
            await model_switcher()
            return True
        except Exception:
            return False
    
    async def _implement_rate_limiting(self, context: Dict[str, Any]) -> bool:
        """实施请求限流"""
        rate_limiter = context.get('rate_limiter')
        if not rate_limiter:
            return False
        
        try:
            await rate_limiter()
            return True
        except Exception:
            return False
    
    async def _fix_file_permissions(self, file_path: str, context: Dict[str, Any]) -> bool:
        """修复文件权限"""
        permission_fixer = context.get('permission_fixer')
        if not permission_fixer:
            return False
        
        try:
            await permission_fixer(file_path)
            return True
        except Exception:
            return False
    
    async def _cleanup_temp_files(self, context: Dict[str, Any]) -> bool:
        """清理临时文件"""
        temp_cleaner = context.get('temp_cleaner')
        if not temp_cleaner:
            return False
        
        try:
            await temp_cleaner()
            return True
        except Exception:
            return False
    
    async def _split_long_text(self, context: Dict[str, Any]) -> bool:
        """分割长文本"""
        text_splitter = context.get('text_splitter')
        if not text_splitter:
            return False
        
        try:
            await text_splitter()
            return True
        except Exception:
            return False
    
    async def _reset_model_connection(self, context: Dict[str, Any]) -> bool:
        """重置模型连接"""
        connection_resetter = context.get('connection_resetter')
        if not connection_resetter:
            return False
        
        try:
            await connection_resetter()
            return True
        except Exception:
            return False
    
    async def _switch_to_backup_translation_service(self, context: Dict[str, Any]) -> bool:
        """切换到备用翻译服务"""
        service_switcher = context.get('service_switcher')
        if not service_switcher:
            return False
        
        try:
            await service_switcher()
            return True
        except Exception:
            return False


class ErrorReporter:
    """错误报告器"""
    
    def __init__(self, localizer: Optional[ErrorMessageLocalizer] = None):
        self.localizer = localizer or ErrorMessageLocalizer()
        self.error_history: List[EnhancedUnityLangPXError] = []
        self.max_history_size = 1000
    
    def report_error(self, error: EnhancedUnityLangPXError) -> str:
        """报告错误"""
        # 添加到历史记录
        self.error_history.append(error)
        
        # 限制历史记录大小
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # 获取用户友好的错误信息
        user_message = self.localizer.get_user_message(error)
        
        # 记录错误
        logger.error(f"错误报告: {error.category.value} - {user_message}")
        
        # 返回用户友好的错误信息
        return user_message
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        if not self.error_history:
            return {
                'total_errors': 0,
                'error_categories': {},
                'error_severities': {},
                'recent_errors': []
            }
        
        # 统计错误类别
        category_counts = {}
        for error in self.error_history:
            category = error.category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # 统计错误严重程度
        severity_counts = {}
        for error in self.error_history:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # 获取最近的错误
        recent_errors = []
        for error in self.error_history[-10:]:  # 最近10个错误
            recent_errors.append({
                'timestamp': error.timestamp,
                'category': error.category.value,
                'severity': error.severity.value,
                'message': error.user_message
            })
        
        return {
            'total_errors': len(self.error_history),
            'error_categories': category_counts,
            'error_severities': severity_counts,
            'recent_errors': recent_errors
        }


# 全局错误处理实例
_error_recovery_manager = ErrorRecoveryManager()
_error_reporter = ErrorReporter()


def get_error_recovery_manager() -> ErrorRecoveryManager:
    """获取错误恢复管理器实例"""
    return _error_recovery_manager


def get_error_reporter() -> ErrorReporter:
    """获取错误报告器实例"""
    return _error_reporter


def create_enhanced_error(
    message: str,
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    details: Optional[str] = None,
    context: Optional[ErrorContext] = None,
    error_code: Optional[str] = None
) -> EnhancedUnityLangPXError:
    """创建增强错误实例"""
    return EnhancedUnityLangPXError(
        message=message,
        category=category,
        severity=severity,
        details=details,
        context=context,
        error_code=error_code
    )


async def handle_error_with_recovery(
    error: EnhancedUnityLangPXError,
    recovery_context: Optional[Dict[str, Any]] = None
) -> bool:
    """处理错误并尝试恢复"""
    # 报告错误
    user_message = _error_reporter.report_error(error)
    
    # 尝试恢复
    recovery_success = await _error_recovery_manager.recover(error, recovery_context)
    
    if not recovery_success:
        logger.error(f"错误恢复失败，需要用户干预: {user_message}")
    
    return recovery_success