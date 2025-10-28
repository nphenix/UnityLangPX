"""
UnityLangPX 翻译引擎模块

这个模块实现了翻译引擎的核心逻辑，整合了Ollama客户端和Markdown处理器，
提供完整的文档翻译功能。
"""

import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from .models.ollama_client import OriginalOllamaClient

from .config import Config
from .models.factory import ModelClientFactory
from .markdown_processor import MarkdownProcessor, MarkdownElement
from .exceptions import TranslationError, MarkdownProcessingError, FileProcessingError
from .logger import get_logger, log_performance
from .terminology import TerminologyMatcher, TraditionalTerminologyStore, TerminologyReplacer
from .simplified_terminology_manager import SimplifiedTerminologyManager, SimplifiedTerminologyAdapterFactory

logger = get_logger(__name__)


@dataclass
class TranslationResult:
    """翻译结果数据类"""
    success: bool
    source_file: Optional[Path] = None
    target_file: Optional[Path] = None
    source_text: Optional[str] = None
    translated_text: Optional[str] = None
    duration: float = 0.0
    chars_translated: int = 0
    elements_processed: int = 0
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FileTranslationStatus:
    """文件翻译状态数据类"""
    file_path: Path
    status: str  # 'pending', 'in_progress', 'completed', 'failed', 'partial'
    chunks_total: int = 0
    chunks_completed: int = 0
    chunks_failed: int = 0
    error_message: Optional[str] = None
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.last_updated == 0.0:
            self.last_updated = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 将Path对象转换为字符串
        if 'file_path' in data and isinstance(data['file_path'], Path):
            data['file_path'] = str(data['file_path'])
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileTranslationStatus':
        """从字典创建"""
        # 处理Path对象
        if 'file_path' in data and not isinstance(data['file_path'], Path):
            data['file_path'] = Path(data['file_path'])
        return cls(**data)


class TranslationCache:
    """翻译缓存"""
    
    def __init__(self, cache_dir: Path = None):
        """
        初始化翻译缓存
        
        Args:
            cache_dir: 缓存目录
        """
        self.cache_dir = cache_dir or Path(".translation_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self._cache_db = self._init_cache_db()
    
    def _init_cache_db(self) -> Dict[str, str]:
        """初始化缓存数据库"""
        cache_file = self.cache_dir / "translation_cache.json"
        if cache_file.exists():
            try:
                import json
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载缓存失败: {str(e)}")
        
        return {}
    
    def _save_cache_db(self):
        """保存缓存数据库"""
        cache_file = self.cache_dir / "translation_cache.json"
        try:
            import json
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存失败: {str(e)}")
    
    def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        return self._cache_db.get(key)
    
    def set(self, key: str, value: str):
        """设置缓存值"""
        self._cache_db[key] = value
        self._save_cache_db()
    
    def clear(self):
        """清空缓存"""
        self._cache_db.clear()
        self._save_cache_db()


class Translator:
    """翻译引擎"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化翻译引擎
        
        Args:
            config: 配置对象
        """
        self.config = config or Config()
        
        # 根据配置创建模型客户端
        provider = self.config.model.provider
        model_config = self.config.get_model_config()
        
        # 检查是否启用增强功能
        self.enhancement_enabled = getattr(self.config, 'enhancement_enabled', False)
        
        if self.enhancement_enabled:
            # 使用传统工厂创建模型客户端
            self.model_client = ModelClientFactory.create_client(provider, model_config)
            
            # 初始化简化术语管理器
            terminology_config = getattr(self.config, 'terminology', type('Config', (), {})())
            self.terminology_manager = SimplifiedTerminologyAdapterFactory.create_hybrid_manager(
                self.model_client, terminology_config
            )
        else:
            # 使用传统工厂
            self.model_client = ModelClientFactory.create_client(provider, model_config)
            self.terminology_manager = None
        
        self.markdown_processor = MarkdownProcessor()
        self.cache = TranslationCache(Path(self.config.cache.cache_dir)) if self.config.cache.enable_cache else None
        
        # 不初始化术语库组件，MCP服务器不需要术语库功能
        self.terminology_matcher = None
        self.terminology_store = None
        self.terminology_replacer = None
        
        # 初始化翻译状态管理
        self.translation_status_file = Path(".translation_status.json")
        self.file_statuses: Dict[str, FileTranslationStatus] = {}
        self._load_translation_status()
        
        # 验证配置
        self.config.validate()
        
        # 记录配置信息
        logger.info(f"翻译引擎初始化完成，使用模型提供商: {provider}")
    
    def _load_translation_status(self):
        """加载翻译状态"""
        if self.translation_status_file.exists():
            try:
                with open(self.translation_status_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning("翻译状态文件为空，初始化为空状态")
                        self.file_statuses = {}
                        return
                    
                    data = json.loads(content)
                
                self.file_statuses = {}
                for file_path_str, status_data in data.items():
                    try:
                        # 验证状态数据完整性
                        if not isinstance(status_data, dict) or 'file_path' not in status_data:
                            logger.warning(f"跳过无效的状态数据: {file_path_str}")
                            continue
                        
                        file_path = Path(file_path_str)
                        self.file_statuses[file_path_str] = FileTranslationStatus.from_dict(status_data)
                    except Exception as e:
                        logger.warning(f"跳过无效文件状态 {file_path_str}: {str(e)}")
                        continue
                
                logger.debug(f"加载了 {len(self.file_statuses)} 个文件的翻译状态")
            except json.JSONDecodeError as e:
                logger.error(f"翻译状态文件JSON格式错误: {str(e)}，将重新创建")
                # 备份损坏的文件
                backup_file = self.translation_status_file.with_suffix('.json.backup')
                try:
                    import shutil
                    shutil.copy2(self.translation_status_file, backup_file)
                    logger.info(f"已备份损坏的状态文件到: {backup_file}")
                except Exception as backup_error:
                    logger.warning(f"备份状态文件失败: {str(backup_error)}")
                
                # 重新创建空的状态文件
                self.file_statuses = {}
                self._save_translation_status()
            except Exception as e:
                logger.warning(f"加载翻译状态失败: {str(e)}")
                self.file_statuses = {}
        else:
            self.file_statuses = {}
    
    def _save_translation_status(self):
        """保存翻译状态"""
        try:
            data = {}
            for file_path_str, status in self.file_statuses.items():
                data[file_path_str] = status.to_dict()
            
            with open(self.translation_status_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"保存了 {len(self.file_statuses)} 个文件的翻译状态")
        except Exception as e:
            logger.warning(f"保存翻译状态失败: {str(e)}")
    
    def _get_file_status(self, file_path: Path) -> FileTranslationStatus:
        """获取文件翻译状态"""
        file_path_str = str(file_path)
        if file_path_str not in self.file_statuses:
            self.file_statuses[file_path_str] = FileTranslationStatus(
                file_path=file_path,
                status='pending'
            )
        return self.file_statuses[file_path_str]
    
    def _update_file_status(self, file_path: Path, status: str,
                           chunks_completed: int = 0, chunks_failed: int = 0,
                           error_message: Optional[str] = None):
        """更新文件翻译状态"""
        file_status = self._get_file_status(file_path)
        file_status.status = status
        file_status.chunks_completed += chunks_completed
        file_status.chunks_failed += chunks_failed
        file_status.last_updated = time.time()
        
        if error_message:
            file_status.error_message = error_message
        
        self._save_translation_status()
    
    @log_performance("translate_text")
    def translate_text(self, text: str, context: Optional[str] = None,
                      source_lang: Optional[str] = None,
                      target_lang: Optional[str] = None,
                      apply_terminology: bool = True,
                      use_enhancement: Optional[bool] = None) -> TranslationResult:
        """
        翻译文本
        
        Args:
            text: 待翻译文本
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            翻译结果
        """
        source_lang = source_lang or self.config.translation.source_language
        target_lang = target_lang or self.config.translation.target_language
        
        # 确定是否使用增强功能
        if use_enhancement is None:
            use_enhancement = self.enhancement_enabled
        
        start_time = time.time()
        
        try:
            logger.debug(f"开始翻译文本，长度: {len(text)}, 增强功能: {use_enhancement}")
            
            # 如果启用增强功能，使用简化术语管理器
            if use_enhancement and self.terminology_manager:
                return self._translate_with_enhancement(
                    text, context, source_lang, target_lang, apply_terminology, start_time
                )
            
            # 传统翻译流程
            return self._translate_traditional(
                text, context, source_lang, target_lang, apply_terminology, start_time
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"文本翻译失败: {str(e)}"
            logger.error(error_msg)
            
            return TranslationResult(
                success=False,
                source_text=text,
                duration=duration,
                error=error_msg
            )
    
    def _translate_with_enhancement(self, text: str, context: Optional[str],
                                   source_lang: str, target_lang: str,
                                   apply_terminology: bool, start_time: float) -> TranslationResult:
        """使用简化术语管理器进行翻译"""
        try:
            # 使用简化术语管理器处理文本
            result = self.terminology_manager.process_text(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                context=context or "",
                domain="通用"
            )
            
            duration = time.time() - start_time
            
            # 构建元数据
            metadata = {
                "from_cache": result.cache_hit,
                "enhancement_used": True,
                "quality_score": result.quality_score,
                "processing_time": result.processing_time,
                "translations_count": len(result.translations)
            }
            
            logger.info(f"简化术语翻译完成，耗时: {duration:.2f}秒，质量分数: {result.quality_score:.2f}")
            
            return TranslationResult(
                success=True,
                source_text=text,
                translated_text=result.processed_text,
                duration=duration,
                chars_translated=len(text),
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"简化术语翻译失败，降级到传统翻译: {str(e)}")
            # 降级到传统翻译
            return self._translate_traditional(
                text, context, source_lang, target_lang, apply_terminology, start_time
            )
    
    def _translate_traditional(self, text: str, context: Optional[str],
                              source_lang: str, target_lang: str,
                              apply_terminology: bool, start_time: float) -> TranslationResult:
        """传统翻译流程"""
        original_text = text
        
        # MCP服务器不使用术语库功能，直接使用原文本
        final_text = text
        terminology_matches = []
            
        # 检查缓存
        cache_key = None
        if self.cache:
            cache_key = f"{source_lang}_{target_lang}_{hash(text)}_{apply_terminology}"
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.debug("使用缓存结果")
                return TranslationResult(
                    success=True,
                    source_text=text,
                    translated_text=cached_result,
                    duration=time.time() - start_time,
                    chars_translated=len(text),
                    metadata={"from_cache": True}
                )
            
            # 动态计算分块大小
            chunk_size = self.config.translation.chunk_size
            if chunk_size == 0:
                # 自动计算分块大小，考虑4k上下文窗口限制
                # 估算令牌数，预留空间给系统提示和响应
                estimated_tokens = OriginalOllamaClient.estimate_tokens(text, source_lang)
                # 目标是使用约一半的上下文窗口，留出空间给系统提示和响应
                target_tokens = 4096 // 2  # 默认上下文窗口大小
                # 根据令牌数反推字符数，英文约1.3字符=1令牌，中文约1字符=2令牌
                if source_lang in ["zh", "ja", "ko"]:
                    chunk_size = target_tokens // 2  # 中文
                else:
                    chunk_size = int(target_tokens * 1.3)  # 英文
                
                # 确保分块大小在合理范围内
                chunk_size = max(200, min(chunk_size, 2000))
                logger.info(f"自动计算分块大小: {chunk_size} 字符 (估算令牌数: {estimated_tokens})")
            
            # 执行翻译
            if len(text) > chunk_size:
                # 长文本分块翻译
                logger.info(f"文本过长({len(text)}字符)，使用分块翻译，分块大小: {chunk_size}")
                translated_text = self._translate_with_chunks(
                    text=text,
                    chunk_size=chunk_size,
                    overlap=self.config.translation.overlap,
                    context=context,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    temperature=self.config.translation.temperature
                )
            else:
                # 短文本直接翻译
                logger.info(f"文本较短({len(text)}字符)，直接翻译")
                translated_text = self.model_client.translate_text(
                    text=final_text,
                    context=context,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    temperature=self.config.translation.temperature
                )
            
            # MCP服务器不使用术语库功能，跳过后处理
            pass
            
            # 保存到缓存
            if self.cache and cache_key:
                self.cache.set(cache_key, translated_text)
            
            duration = time.time() - start_time
            
            logger.info(f"文本翻译完成，耗时: {duration:.2f}秒，字符数: {len(text)}")
            
        # 构建元数据
        metadata = {"from_cache": False, "enhancement_used": False}
        if apply_terminology and terminology_matches:
            metadata["terminology_matches"] = len(terminology_matches)
            metadata["terminology_applied"] = True
        
        return TranslationResult(
            success=True,
            source_text=original_text,
            translated_text=translated_text,
            duration=duration,
            chars_translated=len(text),
            metadata=metadata
        )
    
    def _apply_traditional_terminology(self, text: str, source_lang: str,
                                      target_lang: str) -> Tuple[str, List]:
        """应用传统术语库（MCP服务器中禁用）"""
        # MCP服务器不使用术语库功能，直接返回原文本
        return text, []
    
    def get_enhancement_statistics(self) -> Dict[str, Any]:
        """获取增强功能统计信息"""
        if not self.enhancement_enabled:
            return {"enhancement_enabled": False}
        
        stats = {"enhancement_enabled": True}
        
        if self.terminology_manager:
            stats["terminology_manager"] = self.terminology_manager.get_statistics()
        
        return stats
    
    def enable_enhancement(self, config: Optional[Any] = None) -> bool:
        """启用增强功能"""
        try:
            if self.enhancement_enabled:
                logger.info("增强功能已启用")
                return True
            
            # 初始化简化术语管理器
            terminology_config = config or getattr(self.config, 'terminology', type('Config', (), {})())
            self.terminology_manager = SimplifiedTerminologyAdapterFactory.create_hybrid_manager(
                self.model_client, terminology_config
            )
            
            self.enhancement_enabled = True
            logger.info("增强功能已启用")
            return True
            
        except Exception as e:
            logger.error(f"启用增强功能失败: {str(e)}")
            return False
    
    def disable_enhancement(self) -> bool:
        """禁用增强功能"""
        try:
            if not self.enhancement_enabled:
                logger.info("增强功能已禁用")
                return True
            
            # 清理增强组件
            self.terminology_manager = None
            
            self.enhancement_enabled = False
            logger.info("增强功能已禁用")
            return True
            
        except Exception as e:
            logger.error(f"禁用增强功能失败: {str(e)}")
            return False
    
    @log_performance("translate_markdown")
    def translate_markdown(self, markdown_text: str, context: Optional[str] = None,
                          source_lang: Optional[str] = None,
                          target_lang: Optional[str] = None,
                          apply_terminology: bool = True) -> TranslationResult:
        """
        翻译Markdown文本
        
        Args:
            markdown_text: 待翻译的Markdown文本
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            翻译结果
        """
        source_lang = source_lang or self.config.translation.source_language
        target_lang = target_lang or self.config.translation.target_language
        
        start_time = time.time()
        
        try:
            logger.debug(f"开始翻译Markdown文本，长度: {len(markdown_text)}")
            
            # 解析Markdown元素
            elements = self.markdown_processor.extract_translatable_elements(markdown_text)
            
            # 获取统计信息
            stats = self.markdown_processor.get_statistics(elements)
            logger.debug(f"Markdown元素统计: {stats}")
            
            # 翻译可翻译的元素
            translated_elements = []
            chars_translated = 0
            
            for element in elements:
                if element.translatable:
                    # 提取可翻译的文本
                    if element.type in ['header', 'list_item']:
                        text_to_translate = element.metadata.get('text', '')
                    else:
                        text_to_translate = element.content
                    
                    if text_to_translate.strip():
                        # 翻译文本
                        translation_result = self.translate_text(
                            text=text_to_translate,
                            context=context,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            apply_terminology=apply_terminology
                        )
                        
                        if translation_result.success:
                            # 更新元素内容
                            translated_element = self.markdown_processor.translate_element_content(
                                element, translation_result.translated_text
                            )
                            translated_elements.append(translated_element)
                            chars_translated += len(text_to_translate)
                        else:
                            # 翻译失败，保留原元素
                            logger.warning(f"元素翻译失败，保留原文: {translation_result.error}")
                            translated_elements.append(element)
                    else:
                        # 空元素，直接添加
                        translated_elements.append(element)
                else:
                    # 不可翻译的元素，直接添加
                    translated_elements.append(element)
            
            # 重构Markdown文档
            translated_markdown = self.markdown_processor.reconstruct_markdown(translated_elements)
            
            duration = time.time() - start_time
            
            logger.info(f"Markdown翻译完成，耗时: {duration:.2f}秒，"
                       f"翻译字符: {chars_translated}，处理元素: {len(elements)}")
            
            return TranslationResult(
                success=True,
                source_text=markdown_text,
                translated_text=translated_markdown,
                duration=duration,
                chars_translated=chars_translated,
                elements_processed=len(elements),
                metadata={
                    "element_stats": stats,
                    "translated_elements": len([e for e in elements if e.translatable])
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Markdown翻译失败: {str(e)}"
            logger.error(error_msg)
            
            return TranslationResult(
                success=False,
                source_text=markdown_text,
                duration=duration,
                error=error_msg
            )
    
    @log_performance("translate_file")
    def translate_file(self, input_file: Path, output_file: Optional[Path] = None,
                      context: Optional[str] = None,
                      source_lang: Optional[str] = None,
                      target_lang: Optional[str] = None,
                      apply_terminology: bool = True) -> TranslationResult:
        """
        翻译文件
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径，如果为None则自动生成
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            翻译结果
        """
        import threading
        import queue
        
        if not input_file.exists():
            error_msg = f"输入文件不存在: {input_file}"
            logger.error(error_msg)
            return TranslationResult(
                success=False,
                source_file=input_file,
                error=error_msg
            )
        
        # 自动生成输出文件路径
        if output_file is None:
            output_file = self._generate_output_path(input_file)
        
        # 更新文件状态为进行中
        self._update_file_status(input_file, 'in_progress')
        
        start_time = time.time()
        
        # 创建结果队列和异常队列
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        # 定义翻译函数
        def _translate_with_timeout():
            try:
                logger.info(f"开始翻译文件: {input_file} -> {output_file}")
                
                # 读取文件内容
                with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                # 确定文件类型和翻译方法
                if input_file.suffix.lower() == '.md':
                    # Markdown文件
                    translation_result = self.translate_markdown(
                        markdown_text=content,
                        context=context,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        apply_terminology=apply_terminology
                    )
                else:
                    # 普通文本文件
                    translation_result = self.translate_text(
                        text=content,
                        context=context,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        apply_terminology=apply_terminology
                    )
                
                result_queue.put(translation_result)
            except Exception as e:
                exception_queue.put(e)
        
        # 创建并启动翻译线程
        translate_thread = threading.Thread(target=_translate_with_timeout)
        translate_thread.daemon = True
        translate_thread.start()
        
        # 设置超时时间（5分钟）
        timeout = 300  # 5分钟
        
        try:
            # 等待翻译完成或超时
            translate_thread.join(timeout)
            
            # 检查线程是否还在运行（超时）
            if translate_thread.is_alive():
                error_msg = f"文件翻译超时(>{timeout}秒): {input_file}"
                logger.error(error_msg)
                
                # 更新文件状态为失败
                self._update_file_status(input_file, 'failed', error_message=error_msg)
                
                return TranslationResult(
                    success=False,
                    source_file=input_file,
                    target_file=output_file,
                    duration=time.time() - start_time,
                    error=error_msg
                )
            
            # 检查是否有异常
            if not exception_queue.empty():
                e = exception_queue.get()
                duration = time.time() - start_time
                error_msg = f"文件翻译失败: {str(e)}"
                logger.error(error_msg)
                
                # 更新文件状态为失败
                self._update_file_status(input_file, 'failed', error_message=error_msg)
                
                return TranslationResult(
                    success=False,
                    source_file=input_file,
                    target_file=output_file,
                    duration=duration,
                    error=error_msg
                )
            
            # 获取翻译结果
            translation_result = result_queue.get()
            
            if translation_result.success:
                # 确保输出目录存在
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 写入翻译结果
                with open(output_file, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(translation_result.translated_text)
                
                # 确保文件已正确写入
                with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    # 验证内容是否正确写入
                    if not content:
                        raise FileProcessingError(f"写入文件失败: {output_file}")
                
                # 更新结果信息
                translation_result.source_file = input_file
                translation_result.target_file = output_file
                
                # 更新文件状态为完成
                self._update_file_status(input_file, 'completed')
                
                logger.info(f"文件翻译完成: {input_file} -> {output_file}")
            else:
                # 更新文件状态为失败
                self._update_file_status(input_file, 'failed', error_message=translation_result.error)
                logger.error(f"文件翻译失败: {input_file} - {translation_result.error}")
            
            return translation_result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"文件翻译失败: {str(e)}"
            logger.error(error_msg)
            
            # 更新文件状态为失败
            self._update_file_status(input_file, 'failed', error_message=error_msg)
            
            return TranslationResult(
                success=False,
                source_file=input_file,
                target_file=output_file,
                duration=duration,
                error=error_msg
            )
    
    def _generate_output_path(self, input_file: Path) -> Path:
        """生成输出文件路径"""
        # 如果输入文件在input目录下，则输出到output目录
        if input_file.is_relative_to(Path(self.config.cli.input_dir)):
            relative_path = input_file.relative_to(Path(self.config.cli.input_dir))
            return Path(self.config.cli.output_dir) / relative_path
        else:
            # 否则在同目录下添加后缀
            return input_file.with_suffix(f".translated{input_file.suffix}")
    
    def _translate_with_chunks(self, text: str, chunk_size: int,
                             overlap: int, context: Optional[str] = None,
                             source_lang: str = "en", target_lang: str = "zh",
                             temperature: float = 0.1) -> str:
        """
        分块翻译长文本
        
        Args:
            text: 待翻译文本
            chunk_size: 分块大小
            overlap: 重叠大小
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            temperature: 生成温度
            
        Returns:
            翻译结果
        """
        if len(text) <= chunk_size:
            return self.model_client.translate_text(text, context, source_lang, target_lang, temperature)
        
        logger.debug(f"文本过长，开始分块翻译，总长度: {len(text)}, "
                    f"分块大小: {chunk_size}, 重叠: {overlap}")
        
        # 简单分块实现，可以根据需要优化
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # 尝试在句子边界分割
            sentence_end = text.rfind('. ', start, end)
            if sentence_end > start:
                end = sentence_end + 2
            else:
                # 尝试在换行符处分割
                line_end = text.rfind('\n', start, end)
                if line_end > start:
                    end = line_end + 1
            
            chunks.append(text[start:end])
            start = end - overlap if end < len(text) else end
        
        translated_chunks = []
        
        # 翻译第一个块
        first_chunk_context = context
        translated_chunk = self.model_client.translate_text(
            chunks[0], first_chunk_context, source_lang, target_lang, temperature
        )
        translated_chunks.append(translated_chunk)
        
        # 翻译后续块，提供前一个块的上下文
        for i in range(1, len(chunks)):
            # 使用前一个块的末尾作为上下文
            chunk_context = chunks[i-1][-200:] if i > 0 else ""
            
            translated_chunk = self.model_client.translate_text(
                chunks[i], chunk_context, source_lang, target_lang, temperature
            )
            translated_chunks.append(translated_chunk)
        
        # 合并翻译结果
        result = "".join(translated_chunks)
        logger.debug(f"分块翻译完成，结果长度: {len(result)}")
        
        return result
    
    def check_service(self) -> Dict[str, Any]:
        """
        检查服务状态
        
        Returns:
            服务状态信息
        """
        provider = self.config.model.provider
        status = {
            "provider": provider,
            "connected": False,
            "model_available": False,
            "available_models": [],
            "error": None
        }
        
        try:
            # 检查连接
            if self.model_client.check_connection():
                status["connected"] = True
                
                # 获取可用模型
                models = self.model_client.list_models()
                status["available_models"] = [model.get("id", model.get("name", "")) for model in models]
                
                # 检查指定模型
                if self.model_client.check_model():
                    status["model_available"] = True
                else:
                    model_config = self.config.get_model_config()
                    status["error"] = f"模型 {model_config.model} 不可用"
            else:
                status["error"] = f"无法连接到{provider}服务"
                
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"检查服务状态失败: {str(e)}")
        
        return status
    
    def clear_cache(self):
        """清空翻译缓存"""
        if self.cache:
            self.cache.clear()
            logger.info("翻译缓存已清空")
        else:
            logger.info("缓存未启用，无需清空")
    
    def close(self):
        """关闭翻译引擎"""
        if self.model_client:
            self.model_client.close()
            logger.debug("翻译引擎已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()