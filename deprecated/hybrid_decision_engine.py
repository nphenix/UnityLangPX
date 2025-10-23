"""
UnityLangPX 混合决策引擎模块

实现智能决策机制，根据文本特征和场景选择最优的术语处理策略：
- 简单场景：优先使用传统术语库
- 复杂场景：使用大模型增强功能
- 混合场景：结合两者优势
"""

import time
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .terminology_enhancement import TerminologyEnhancementService, EnhancementResult
from .terminology import TerminologyMatcher, TraditionalTerminologyStore, TerminologyEntry
from .logger import get_logger

logger = get_logger(__name__)


class ProcessingStrategy(Enum):
    """处理策略枚举"""
    TRADITIONAL_ONLY = "traditional_only"      # 仅使用传统术语库
    ENHANCEMENT_ONLY = "enhancement_only"      # 仅使用增强功能
    HYBRID = "hybrid"                          # 混合策略
    FALLBACK = "fallback"                      # 降级策略


@dataclass
class DecisionResult:
    """决策结果"""
    strategy: ProcessingStrategy
    confidence: float
    reasoning: str
    complexity_score: float
    traditional_matches: List
    enhancement_suggested: bool
    metadata: Dict[str, Any]


class HybridDecisionEngine:
    """混合决策引擎"""
    
    def __init__(self, config: Any, 
                 enhancement_service: Optional[TerminologyEnhancementService] = None):
        """
        初始化混合决策引擎
        
        Args:
            config: 配置对象
            enhancement_service: 术语增强服务
        """
        self.config = config
        self.enhancement_service = enhancement_service
        
        # 初始化传统组件
        self.traditional_store = TraditionalTerminologyStore()
        self.terminology_matcher = TerminologyMatcher()
        
        # 配置参数
        self.complexity_threshold = getattr(config, 'complexity_threshold', 0.7)
        self.traditional_threshold = getattr(config, 'traditional_threshold', 0.8)
        self.enhancement_threshold = getattr(config, 'enhancement_threshold', 0.5)
        self.fallback_enabled = getattr(config, 'fallback_enabled', True)
        
        # 决策统计
        self.decision_stats = {
            'total_decisions': 0,
            'traditional_decisions': 0,
            'enhancement_decisions': 0,
            'hybrid_decisions': 0,
            'fallback_decisions': 0
        }
        
        logger.info("混合决策引擎初始化完成")
    
    def decide_processing_strategy(self, text: str, source_lang: str = "en", 
                                 target_lang: str = "zh", context: str = "") -> DecisionResult:
        """
        决定处理策略
        
        Args:
            text: 输入文本
            source_lang: 源语言
            target_lang: 目标语言
            context: 上下文信息
            
        Returns:
            决策结果
        """
        start_time = time.time()
        
        try:
            # 1. 分析文本复杂度
            complexity_score = self.analyze_text_complexity(text)
            
            # 2. 查找传统匹配
            traditional_matches = self._find_traditional_matches(text, source_lang, target_lang)
            
            # 3. 分析传统匹配质量
            traditional_quality = self._analyze_traditional_quality(text, traditional_matches)
            
            # 4. 检测增强需求
            enhancement_needed = self._detect_enhancement_needs(text, context)
            
            # 5. 综合决策
            strategy, confidence, reasoning = self._make_decision(
                complexity_score, traditional_quality, enhancement_needed, 
                traditional_matches, text, context
            )
            
            # 创建决策结果
            result = DecisionResult(
                strategy=strategy,
                confidence=confidence,
                reasoning=reasoning,
                complexity_score=complexity_score,
                traditional_matches=traditional_matches,
                enhancement_suggested=enhancement_needed,
                metadata={
                    'processing_time': time.time() - start_time,
                    'text_length': len(text),
                    'traditional_quality': traditional_quality,
                    'context_length': len(context)
                }
            )
            
            # 更新统计
            self._update_decision_stats(strategy)
            
            logger.debug(f"决策完成: {strategy.value}, 置信度: {confidence:.2f}, "
                        f"复杂度: {complexity_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"决策失败: {str(e)}")
            # 返回降级策略
            return DecisionResult(
                strategy=ProcessingStrategy.FALLBACK,
                confidence=0.0,
                reasoning=f"决策失败: {str(e)}",
                complexity_score=0.0,
                traditional_matches=[],
                enhancement_suggested=False,
                metadata={'error': str(e)}
            )
    
    def process_with_strategy(self, text: str, strategy: ProcessingStrategy,
                            source_lang: str = "en", target_lang: str = "zh",
                            context: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        根据策略处理文本
        
        Args:
            text: 输入文本
            strategy: 处理策略
            source_lang: 源语言
            target_lang: 目标语言
            context: 上下文
            
        Returns:
            (处理后的文本, 处理信息)
        """
        processing_info = {
            'strategy': strategy.value,
            'enhancement_used': False,
            'traditional_matches': 0,
            'enhancement_results': [],
            'processing_time': 0
        }
        
        start_time = time.time()
        
        try:
            if strategy == ProcessingStrategy.TRADITIONAL_ONLY:
                # 仅使用传统术语库
                result_text, matches = self._process_traditional_only(
                    text, source_lang, target_lang
                )
                processing_info['traditional_matches'] = len(matches)
                
            elif strategy == ProcessingStrategy.ENHANCEMENT_ONLY:
                # 仅使用增强功能
                result_text = self._process_enhancement_only(
                    text, source_lang, target_lang, context
                )
                processing_info['enhancement_used'] = True
                
            elif strategy == ProcessingStrategy.HYBRID:
                # 混合策略
                result_text = self._process_hybrid(
                    text, source_lang, target_lang, context
                )
                processing_info['enhancement_used'] = True
                processing_info['traditional_matches'] = len(
                    self._find_traditional_matches(text, source_lang, target_lang)
                )
                
            elif strategy == ProcessingStrategy.FALLBACK:
                # 降级策略
                result_text = self._process_fallback(text, source_lang, target_lang)
                
            else:
                # 未知策略，使用降级
                logger.warning(f"未知策略: {strategy}, 使用降级策略")
                result_text = self._process_fallback(text, source_lang, target_lang)
            
            processing_info['processing_time'] = time.time() - start_time
            
            return result_text, processing_info
            
        except Exception as e:
            logger.error(f"策略处理失败: {str(e)}")
            # 降级处理
            result_text = self._process_fallback(text, source_lang, target_lang)
            processing_info['processing_time'] = time.time() - start_time
            processing_info['error'] = str(e)
            
            return result_text, processing_info
    
    def analyze_text_complexity(self, text: str) -> float:
        """
        分析文本复杂度
        
        Args:
            text: 输入文本
            
        Returns:
            复杂度分数 (0-1)
        """
        complexity = 0.0
        
        # 1. 长度复杂度
        length_score = min(1.0, len(text) / 1000)  # 1000字符为满分
        complexity += length_score * 0.2
        
        # 2. 句子复杂度
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if sentences:
            avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
            sentence_score = min(1.0, avg_sentence_length / 100)  # 100字符为满分
            complexity += sentence_score * 0.15
        
        # 3. 词汇复杂度
        words = text.split()
        if words:
            long_words = [w for w in words if len(w) > 10]
            word_score = len(long_words) / len(words)
            complexity += word_score * 0.15
        
        # 4. 标点复杂度
        complex_punctuation = len(re.findall(r'[;:()\[\]{}"\'—–]', text))
        punctuation_score = min(1.0, complex_punctuation / 20)  # 20个复杂标点为满分
        complexity += punctuation_score * 0.1
        
        # 5. 数字和符号复杂度
        numbers_symbols = len(re.findall(r'\d+|[^\w\s]', text))
        symbol_score = min(1.0, numbers_symbols / 30)  # 30个数字符号为满分
        complexity += symbol_score * 0.1
        
        # 6. 专业术语复杂度
        technical_terms = len(re.findall(r'\b(AI|API|CPU|GPU|RAM|ROM|HTTP|HTTPS|HTML|CSS|JS|SQL|NoSQL|UI|UX)\b', text))
        technical_score = min(1.0, technical_terms / 10)  # 10个技术术语为满分
        complexity += technical_score * 0.15
        
        # 7. 结构复杂度
        structure_indicators = [
            r'\*\*.*?\*\*',  # 粗体
            r'\*.*?\*',      # 斜体
            r'`.*?`',        # 代码
            r'>.*',          # 引用
            r'^#{1,6}\s',    # 标题
            r'^\s*[-*+]\s',  # 列表
            r'^\s*\d+\.\s',  # 有序列表
        ]
        
        structure_score = 0
        for pattern in structure_indicators:
            structure_score += len(re.findall(pattern, text, re.MULTILINE))
        
        structure_score = min(1.0, structure_score / 15)  # 15个结构元素为满分
        complexity += structure_score * 0.15
        
        return min(1.0, complexity)
    
    def get_decision_statistics(self) -> Dict[str, Any]:
        """获取决策统计信息"""
        total = self.decision_stats['total_decisions']
        
        if total > 0:
            return {
                **self.decision_stats,
                'traditional_percentage': self.decision_stats['traditional_decisions'] / total * 100,
                'enhancement_percentage': self.decision_stats['enhancement_decisions'] / total * 100,
                'hybrid_percentage': self.decision_stats['hybrid_decisions'] / total * 100,
                'fallback_percentage': self.decision_stats['fallback_decisions'] / total * 100,
            }
        else:
            return self.decision_stats
    
    def reset_statistics(self):
        """重置统计信息"""
        self.decision_stats = {
            'total_decisions': 0,
            'traditional_decisions': 0,
            'enhancement_decisions': 0,
            'hybrid_decisions': 0,
            'fallback_decisions': 0
        }
        logger.info("决策统计已重置")
    
    # 私有方法
    
    def _find_traditional_matches(self, text: str, source_lang: str, target_lang: str) -> List:
        """查找传统匹配"""
        try:
            relevant_terms = self.traditional_store.find_terms(
                source_lang=source_lang,
                target_lang=target_lang
            )
            
            matches = self.terminology_matcher.find_exact_matches(
                text, relevant_terms, source_lang, target_lang
            )
            
            return matches
        except Exception as e:
            logger.error(f"查找传统匹配失败: {str(e)}")
            return []
    
    def _analyze_traditional_quality(self, text: str, matches: List) -> float:
        """分析传统匹配质量"""
        if not matches:
            return 0.0
        
        try:
            # 计算匹配覆盖率
            total_words = len(text.split())
            matched_words = sum(len(match[0].source_term.split()) for match in matches)
            coverage = min(1.0, matched_words / total_words)
            
            # 计算匹配置信度
            avg_confidence = sum(match[0].confidence for match in matches) / len(matches)
            
            # 综合质量分数
            quality = coverage * 0.6 + avg_confidence * 0.4
            
            return quality
        except Exception as e:
            logger.error(f"分析传统匹配质量失败: {str(e)}")
            return 0.0
    
    def _detect_enhancement_needs(self, text: str, context: str) -> bool:
        """检测是否需要增强功能"""
        try:
            # 1. 检测复杂元素
            if self._has_complex_elements(text):
                return True
            
            # 2. 检测可能的模糊匹配
            if self._has_fuzzy_candidate_terms(text):
                return True
            
            # 3. 检测多义词
            if self._has_potential_polysems(text):
                return True
            
            # 4. 检测上下文依赖
            if context and self._is_context_dependent(text, context):
                return True
            
            return False
        except Exception as e:
            logger.error(f"检测增强需求失败: {str(e)}")
            return True  # 默认使用增强
    
    def _make_decision(self, complexity_score: float, traditional_quality: float,
                      enhancement_needed: bool, traditional_matches: List,
                      text: str, context: str) -> Tuple[ProcessingStrategy, float, str]:
        """制定决策"""
        
        # 1. 检查是否使用增强服务
        if not self.enhancement_service:
            if traditional_quality >= self.traditional_threshold:
                return ProcessingStrategy.TRADITIONAL_ONLY, 0.8, "增强服务不可用，使用传统术语库"
            else:
                return ProcessingStrategy.FALLBACK, 0.5, "增强服务不可用且传统匹配质量不足"
        
        # 2. 决策逻辑
        if traditional_quality >= self.traditional_threshold and not enhancement_needed:
            # 传统匹配质量高且无需增强
            return ProcessingStrategy.TRADITIONAL_ONLY, 0.9, "传统匹配质量高，无需增强"
        
        elif complexity_score >= self.complexity_threshold:
            # 文本复杂度高，使用增强功能
            if traditional_quality >= self.enhancement_threshold:
                return ProcessingStrategy.HYBRID, 0.8, "文本复杂但传统匹配尚可，使用混合策略"
            else:
                return ProcessingStrategy.ENHANCEMENT_ONLY, 0.8, "文本复杂度高，使用增强功能"
        
        elif enhancement_needed:
            # 需要增强功能
            if traditional_quality >= self.enhancement_threshold:
                return ProcessingStrategy.HYBRID, 0.7, "需要增强但传统匹配尚可，使用混合策略"
            else:
                return ProcessingStrategy.ENHANCEMENT_ONLY, 0.7, "需要增强功能"
        
        elif traditional_quality < self.enhancement_threshold:
            # 传统匹配质量低
            return ProcessingStrategy.ENHANCEMENT_ONLY, 0.6, "传统匹配质量低，使用增强功能"
        
        else:
            # 默认使用传统策略
            return ProcessingStrategy.TRADITIONAL_ONLY, 0.6, "默认使用传统策略"
    
    def _process_traditional_only(self, text: str, source_lang: str, target_lang: str) -> Tuple[str, List]:
        """仅使用传统术语库处理"""
        try:
            relevant_terms = self.traditional_store.find_terms(
                source_lang=source_lang,
                target_lang=target_lang
            )
            
            matches = self.terminology_matcher.find_exact_matches(
                text, relevant_terms, source_lang, target_lang
            )
            
            if matches:
                from .terminology import TerminologyReplacer
                replacer = TerminologyReplacer(self.terminology_matcher)
                result_text = replacer.apply_terminology(text, matches, source_lang, target_lang)
                return result_text, matches
            else:
                return text, []
                
        except Exception as e:
            logger.error(f"传统处理失败: {str(e)}")
            return text, []
    
    def _process_enhancement_only(self, text: str, source_lang: str, target_lang: str, context: str) -> str:
        """仅使用增强功能处理"""
        if not self.enhancement_service:
            logger.warning("增强服务不可用，返回原文")
            return text
        
        try:
            # 检测是否需要复杂场景处理
            if self._has_complex_elements(text):
                result = self.enhancement_service.handle_complex_scenario(
                    text, source_lang, target_lang
                )
                return result.enhanced_translation
            
            # 使用上下文感知翻译
            result = self.enhancement_service.enhance_term_translation(
                text, context, source_lang, target_lang
            )
            return result.enhanced_translation
            
        except Exception as e:
            logger.error(f"增强处理失败: {str(e)}")
            return text
    
    def _process_hybrid(self, text: str, source_lang: str, target_lang: str, context: str) -> str:
        """混合策略处理"""
        try:
            # 1. 先应用传统术语库
            traditional_text, traditional_matches = self._process_traditional_only(
                text, source_lang, target_lang
            )
            
            # 2. 对未匹配的部分应用增强功能
            if not self.enhancement_service:
                return traditional_text
            
            # 检测需要增强的部分
            enhancement_needed_parts = self._identify_enhancement_parts(
                traditional_text, traditional_matches
            )
            
            if not enhancement_needed_parts:
                return traditional_text
            
            # 对需要增强的部分进行处理
            enhanced_text = traditional_text
            for part in enhancement_needed_parts:
                if self._has_complex_elements(part):
                    result = self.enhancement_service.handle_complex_scenario(
                        part, source_lang, target_lang
                    )
                else:
                    result = self.enhancement_service.enhance_term_translation(
                        part, context, source_lang, target_lang
                    )
                
                # 替换原文中的部分
                enhanced_text = enhanced_text.replace(part, result.enhanced_translation)
            
            return enhanced_text
            
        except Exception as e:
            logger.error(f"混合处理失败: {str(e)}")
            # 降级到传统处理
            return self._process_traditional_only(text, source_lang, target_lang)[0]
    
    def _process_fallback(self, text: str, source_lang: str, target_lang: str) -> str:
        """降级处理"""
        try:
            # 尝试传统处理
            result_text, _ = self._process_traditional_only(text, source_lang, target_lang)
            return result_text
        except Exception as e:
            logger.error(f"降级处理也失败: {str(e)}")
            return text
    
    def _has_complex_elements(self, text: str) -> bool:
        """检测是否有复杂元素"""
        complex_patterns = [
            r'<[^>]+>',           # HTML标签
            r'```[^`]+```',       # 代码块
            r'`[^`]+`',           # 行内代码
            r'\$\$[^$]+\$\$',     # 数学公式
            r'\$[^$]+\$',         # 行内数学
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def _has_fuzzy_candidate_terms(self, text: str) -> bool:
        """检测是否有模糊匹配候选"""
        # 简单检测：检查可能的拼写错误
        words = text.split()
        
        for word in words:
            # 检查连续重复字符
            if re.search(r'(.)\1{2,}', word):
                return True
            
            # 检查常见拼写错误模式
            if re.search(r'[aeiou]{3,}', word.lower()):  # 连续元音
                return True
        
        return False
    
    def _has_potential_polysems(self, text: str) -> bool:
        """检测是否有潜在多义词"""
        common_polysems = [
            'light', 'dark', 'bank', 'book', 'run', 'set', 'get', 'spring', 
            'mine', 'watch', 'table', 'key', 'lock', 'block', 'chain', 'star'
        ]
        
        words = re.findall(r'\b\w+\b', text.lower())
        for word in words:
            if word in common_polysems:
                return True
        
        return False
    
    def _is_context_dependent(self, text: str, context: str) -> bool:
        """检测是否依赖上下文"""
        if not context:
            return False
        
        # 简单检测：检查文本中是否有需要上下文的词汇
        context_dependent_words = [
            'it', 'this', 'that', 'these', 'those', 'he', 'she', 'they',
            'here', 'there', 'now', 'then', 'above', 'below'
        ]
        
        words = re.findall(r'\b\w+\b', text.lower())
        for word in words:
            if word in context_dependent_words:
                return True
        
        return False
    
    def _identify_enhancement_parts(self, text: str, traditional_matches: List) -> List[str]:
        """识别需要增强的部分"""
        if not traditional_matches:
            return [text]
        
        # 获取已匹配的位置
        matched_positions = set()
        for term, matched_text in traditional_matches:
            start = 0
            while True:
                pos = text.find(matched_text, start)
                if pos == -1:
                    break
                matched_positions.add((pos, pos + len(matched_text)))
                start = pos + 1
        
        # 找出未匹配的部分
        unmatched_parts = []
        last_end = 0
        
        for start, end in sorted(matched_positions):
            if start > last_end:
                unmatched_part = text[last_end:start]
                if unmatched_part.strip():
                    unmatched_parts.append(unmatched_part)
            last_end = end
        
        # 处理最后的部分
        if last_end < len(text):
            final_part = text[last_end:]
            if final_part.strip():
                unmatched_parts.append(final_part)
        
        return unmatched_parts
    
    def _update_decision_stats(self, strategy: ProcessingStrategy):
        """更新决策统计"""
        self.decision_stats['total_decisions'] += 1
        
        if strategy == ProcessingStrategy.TRADITIONAL_ONLY:
            self.decision_stats['traditional_decisions'] += 1
        elif strategy == ProcessingStrategy.ENHANCEMENT_ONLY:
            self.decision_stats['enhancement_decisions'] += 1
        elif strategy == ProcessingStrategy.HYBRID:
            self.decision_stats['hybrid_decisions'] += 1
        elif strategy == ProcessingStrategy.FALLBACK:
            self.decision_stats['fallback_decisions'] += 1