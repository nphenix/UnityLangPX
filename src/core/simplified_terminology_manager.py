"""
UnityLangPX 简化术语管理器

作为简化术语库与现有系统之间的适配器，提供兼容的接口
同时保持简化架构的优势。
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from .simplified_terminology import SimplifiedTerminologyProcessor, ProcessResult, TermTranslation
from .terminology import TerminologyEntry, TraditionalTerminologyStore, TerminologyMatcher
from .models.base import ModelClient
from .logger import get_logger

logger = get_logger(__name__)


class SimplifiedTerminologyManager:
    """简化术语管理器"""
    
    def __init__(self, model_client: ModelClient, config: Any = None, 
                 traditional_store: Optional[TraditionalTerminologyStore] = None):
        """
        初始化简化术语管理器
        
        Args:
            model_client: 大模型客户端
            config: 配置对象
            traditional_store: 传统术语存储（可选，用于兼容性）
        """
        self.model_client = model_client
        self.config = config
        self.traditional_store = traditional_store or TraditionalTerminologyStore()
        
        # 初始化简化处理器
        self.simplified_processor = SimplifiedTerminologyProcessor(model_client, config)
        
        # 兼容性组件
        self.matcher = TerminologyMatcher()
        
        # 配置参数
        self.enable_hybrid_mode = getattr(config, 'enable_hybrid_mode', True)
        self.fallback_to_traditional = getattr(config, 'fallback_to_traditional', True)
        
        logger.info("简化术语管理器初始化完成")
    
    def process_text(self, text: str, source_lang: str = "en", 
                    target_lang: str = "zh", context: str = "", 
                    domain: str = "通用") -> ProcessResult:
        """
        处理文本中的术语（主要接口）
        
        Args:
            text: 输入文本
            source_lang: 源语言
            target_lang: 目标语言
            context: 上下文信息
            domain: 专业领域
            
        Returns:
            处理结果
        """
        try:
            # 使用简化处理器处理
            result = self.simplified_processor.process_text(
                text, source_lang, target_lang, context, domain
            )
            
            # 如果启用了混合模式且有传统术语库，尝试增强结果
            if self.enable_hybrid_mode and self.traditional_store:
                result = self._enhance_with_traditional(result, source_lang, target_lang)
            
            return result
            
        except Exception as e:
            logger.error(f"简化处理失败: {e}")
            
            # 降级到传统处理
            if self.fallback_to_traditional:
                logger.info("降级到传统术语库处理")
                return self._fallback_to_traditional(text, source_lang, target_lang, context)
            else:
                # 返回原始文本
                return ProcessResult(
                    original_text=text,
                    processed_text=text,
                    translations=[],
                    processing_time=0.0,
                    cache_hit=False,
                    quality_score=0.0,
                    metadata={"error": str(e), "fallback": False}
                )
    
    def _enhance_with_traditional(self, result: ProcessResult, 
                                 source_lang: str, target_lang: str) -> ProcessResult:
        """使用传统术语库增强结果"""
        try:
            # 获取传统术语匹配
            traditional_matches = self._get_traditional_matches(
                result.original_text, source_lang, target_lang
            )
            
            if not traditional_matches:
                return result
            
            # 合并翻译结果
            enhanced_translations = self._merge_translations(
                result.translations, traditional_matches
            )
            
            # 重新应用翻译
            enhanced_text = self._apply_merged_translations(
                result.original_text, enhanced_translations
            )
            
            # 重新评估质量
            quality_score = self.simplified_processor.quality_assessor.assess_quality(
                result.original_text, enhanced_translations
            )
            
            # 创建增强结果
            enhanced_result = ProcessResult(
                original_text=result.original_text,
                processed_text=enhanced_text,
                translations=enhanced_translations,
                processing_time=result.processing_time,
                cache_hit=result.cache_hit,
                quality_score=quality_score,
                metadata={
                    **result.metadata,
                    "enhanced_with_traditional": True,
                    "traditional_matches_count": len(traditional_matches)
                }
            )
            
            logger.debug(f"传统增强完成: +{len(traditional_matches)} 个传统术语")
            return enhanced_result
            
        except Exception as e:
            logger.error(f"传统增强失败: {e}")
            return result
    
    def _get_traditional_matches(self, text: str, source_lang: str, target_lang: str) -> List[TermTranslation]:
        """获取传统术语匹配"""
        try:
            # 查找相关术语
            relevant_terms = self.traditional_store.find_terms(
                source_lang=source_lang,
                target_lang=target_lang
            )
            
            # 精确匹配
            matches = self.matcher.find_exact_matches(
                text, relevant_terms, source_lang, target_lang
            )
            
            # 转换为TermTranslation
            translations = []
            for term, matched_text in matches:
                translations.append(TermTranslation(
                    source_term=matched_text,
                    target_term=term.target_term,
                    confidence=term.confidence,
                    context=term.context,
                    domain=term.domain
                ))
            
            return translations
            
        except Exception as e:
            logger.error(f"获取传统匹配失败: {e}")
            return []
    
    def _merge_translations(self, simplified_translations: List[TermTranslation], 
                           traditional_translations: List[TermTranslation]) -> List[TermTranslation]:
        """合并简化翻译和传统翻译"""
        # 按源术语分组
        merged = {}
        
        # 添加简化翻译
        for translation in simplified_translations:
            key = translation.source_term.lower()
            merged[key] = translation
        
        # 添加传统翻译（如果不存在或置信度更高）
        for translation in traditional_translations:
            key = translation.source_term.lower()
            if key not in merged or translation.confidence > merged[key].confidence:
                # 标记为传统翻译
                translation.metadata = getattr(translation, 'metadata', {})
                translation.metadata["source"] = "traditional"
                merged[key] = translation
        
        return list(merged.values())
    
    def _apply_merged_translations(self, text: str, translations: List[TermTranslation]) -> str:
        """应用合并后的翻译"""
        if not translations:
            return text
        
        result = text
        
        # 按术语长度排序，确保长术语优先匹配
        sorted_translations = sorted(translations, key=lambda x: len(x.source_term), reverse=True)
        
        for translation in sorted_translations:
            # 简单的字符串替换
            result = result.replace(translation.source_term, translation.target_term)
        
        return result
    
    def _fallback_to_traditional(self, text: str, source_lang: str, 
                                target_lang: str, context: str) -> ProcessResult:
        """降级到传统术语库处理"""
        start_time = time.time()
        
        try:
            # 获取传统匹配
            traditional_matches = self._get_traditional_matches(text, source_lang, target_lang)
            
            # 应用翻译
            processed_text = self._apply_merged_translations(text, traditional_matches)
            
            # 评估质量
            quality_score = self.simplified_processor.quality_assessor.assess_quality(
                text, traditional_matches
            )
            
            return ProcessResult(
                original_text=text,
                processed_text=processed_text,
                translations=traditional_matches,
                processing_time=time.time() - start_time,
                cache_hit=False,
                quality_score=quality_score,
                metadata={
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "fallback": True,
                    "traditional_only": True
                }
            )
            
        except Exception as e:
            logger.error(f"传统处理也失败: {e}")
            return ProcessResult(
                original_text=text,
                processed_text=text,
                translations=[],
                processing_time=time.time() - start_time,
                cache_hit=False,
                quality_score=0.0,
                metadata={"error": str(e), "fallback": True, "traditional_failed": True}
            )
    
    # 兼容性接口方法
    
    def find_exact_matches(self, text: str, terminology: List[TerminologyEntry],
                          source_lang: str, target_lang: str) -> List[Tuple[TerminologyEntry, str]]:
        """
        兼容性方法：查找精确匹配
        
        Args:
            text: 输入文本
            terminology: 术语列表
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            匹配结果列表
        """
        try:
            # 使用传统匹配器
            return self.matcher.find_exact_matches(text, terminology, source_lang, target_lang)
        except Exception as e:
            logger.error(f"精确匹配失败: {e}")
            return []
    
    def apply_terminology(self, text: str, matches: List[Tuple[TerminologyEntry, str]],
                         source_lang: str, target_lang: str) -> str:
        """
        兼容性方法：应用术语翻译
        
        Args:
            text: 原文
            matches: 匹配结果
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            应用术语后的文本
        """
        try:
            from .terminology import TerminologyReplacer
            replacer = TerminologyReplacer(self.matcher)
            return replacer.apply_terminology(text, matches, source_lang, target_lang)
        except Exception as e:
            logger.error(f"应用术语失败: {e}")
            return text
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "simplified_processor": self.simplified_processor.get_statistics(),
            "hybrid_mode_enabled": self.enable_hybrid_mode,
            "fallback_enabled": self.fallback_to_traditional
        }
        
        # 添加传统术语库统计
        if self.traditional_store:
            stats["traditional_store"] = self.traditional_store.get_statistics()
        
        return stats
    
    def clear_cache(self):
        """清空缓存"""
        self.simplified_processor.clear_cache()
        logger.info("术语管理器缓存已清空")
    
    def add_traditional_term(self, entry: TerminologyEntry) -> bool:
        """
        添加传统术语（兼容性方法）
        
        Args:
            entry: 术语条目
            
        Returns:
            是否添加成功
        """
        if self.traditional_store:
            return self.traditional_store.add_term(entry)
        return False
    
    def get_traditional_terms(self, source_lang: str = None, target_lang: str = None,
                             domain: str = None) -> List[TerminologyEntry]:
        """
        获取传统术语（兼容性方法）
        
        Args:
            source_lang: 源语言
            target_lang: 目标语言
            domain: 领域
            
        Returns:
            术语列表
        """
        if self.traditional_store:
            return self.traditional_store.find_terms(source_lang, target_lang, domain)
        return []
    
    def shutdown(self):
        """关闭管理器"""
        logger.info("正在关闭简化术语管理器...")
        self.simplified_processor.shutdown()
        logger.info("简化术语管理器已关闭")


class SimplifiedTerminologyAdapterFactory:
    """简化术语管理器适配器工厂"""
    
    @staticmethod
    def create_manager(model_client: ModelClient, config: Any = None,
                      use_traditional_store: bool = True) -> SimplifiedTerminologyManager:
        """
        创建简化术语管理器
        
        Args:
            model_client: 大模型客户端
            config: 配置对象
            use_traditional_store: 是否使用传统术语存储
            
        Returns:
            简化术语管理器实例
        """
        traditional_store = None
        if use_traditional_store:
            traditional_store = TraditionalTerminologyStore()
        
        return SimplifiedTerminologyManager(
            model_client=model_client,
            config=config,
            traditional_store=traditional_store
        )
    
    @staticmethod
    def create_hybrid_manager(model_client: ModelClient, config: Any = None) -> SimplifiedTerminologyManager:
        """
        创建混合模式管理器
        
        Args:
            model_client: 大模型客户端
            config: 配置对象
            
        Returns:
            混合模式管理器实例
        """
        if config:
            config.enable_hybrid_mode = True
            config.fallback_to_traditional = True
        
        return SimplifiedTerminologyAdapterFactory.create_manager(
            model_client, config, use_traditional_store=True
        )
    
    @staticmethod
    def create_simplified_only_manager(model_client: ModelClient, config: Any = None) -> SimplifiedTerminologyManager:
        """
        创建仅简化模式管理器
        
        Args:
            model_client: 大模型客户端
            config: 配置对象
            
        Returns:
            仅简化模式管理器实例
        """
        if config:
            config.enable_hybrid_mode = False
            config.fallback_to_traditional = False
        
        return SimplifiedTerminologyAdapterFactory.create_manager(
            model_client, config, use_traditional_store=False
        )