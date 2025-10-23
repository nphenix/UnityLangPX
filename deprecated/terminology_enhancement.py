"""
UnityLangPX 术语增强服务模块

实现基于大模型的术语增强功能，包括上下文感知翻译、模糊匹配增强、
多义词消歧和复杂场景处理。
"""

import re
import time
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path

from .models.base import ModelClient
from .terminology import TerminologyEntry, TraditionalTerminologyStore
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class EnhancementResult:
    """术语增强结果"""
    original_term: str
    enhanced_translation: str
    confidence: float
    enhancement_type: str  # 'context_aware', 'fuzzy_match', 'disambiguation', 'complex_scenario'
    processing_time: float
    metadata: Dict[str, Any]


@dataclass
class FuzzyMatchResult:
    """模糊匹配结果"""
    term: str
    confidence: float
    match_type: str  # 'exact', 'edit_distance', 'abbreviation', 'morphological', 'semantic'


class TerminologyEnhancementService:
    """术语增强服务类，利用大模型能力提升术语翻译质量"""
    
    def __init__(self, model_client: ModelClient, config: Any):
        """
        初始化术语增强服务
        
        Args:
            model_client: 模型客户端
            config: 配置对象
        """
        self.model_client = model_client
        self.config = config
        
        # 初始化组件
        self.traditional_store = TraditionalTerminologyStore()
        
        # 缓存
        self._context_cache = {}
        self._fuzzy_cache = {}
        self._disambiguation_cache = {}
        
        # 配置参数
        self.context_window_size = getattr(config, 'context_window_size', 200)
        self.max_cache_size = getattr(config, 'max_cache_size', 1000)
        self.fuzzy_threshold = getattr(config, 'fuzzy_threshold', 0.7)
        
        logger.info("术语增强服务初始化完成")
    
    def enhance_term_translation(self, term: str, context: str, 
                               source_lang: str = "en", target_lang: str = "zh") -> EnhancementResult:
        """
        增强术语翻译，考虑上下文信息
        
        Args:
            term: 源术语
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            增强结果
        """
        start_time = time.time()
        
        # 检查缓存
        cache_key = f"{term}_{hash(context)}_{source_lang}_{target_lang}"
        if cache_key in self._context_cache:
            logger.debug(f"使用上下文缓存: {term}")
            result = self._context_cache[cache_key]
            return result
        
        try:
            # 构建上下文感知的提示词
            prompt = self._build_context_prompt(term, context, source_lang, target_lang)
            
            # 调用大模型
            response = self.model_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            # 提取翻译结果
            enhanced_translation = self._extract_translation_from_response(response)
            
            # 计算置信度
            confidence = self._calculate_confidence(response, term, context)
            
            # 创建结果
            result = EnhancementResult(
                original_term=term,
                enhanced_translation=enhanced_translation,
                confidence=confidence,
                enhancement_type='context_aware',
                processing_time=time.time() - start_time,
                metadata={
                    'context_length': len(context),
                    'prompt_length': len(prompt),
                    'response_length': len(response)
                }
            )
            
            # 更新缓存
            self._update_cache(self._context_cache, cache_key, result)
            
            logger.debug(f"上下文感知翻译完成: {term} -> {enhanced_translation}")
            return result
            
        except Exception as e:
            logger.error(f"上下文感知翻译失败: {term}, 错误: {e}")
            # 返回基础结果
            return EnhancementResult(
                original_term=term,
                enhanced_translation=term,
                confidence=0.0,
                enhancement_type='context_aware',
                processing_time=time.time() - start_time,
                metadata={'error': str(e)}
            )
    
    def enhance_fuzzy_matching(self, text: str, potential_terms: List[str], 
                             source_lang: str = "en", target_lang: str = "zh") -> List[FuzzyMatchResult]:
        """
        增强模糊匹配，返回候选术语及其置信度
        
        Args:
            text: 输入文本
            potential_terms: 潜在术语列表
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            模糊匹配结果列表
        """
        # 检查缓存
        cache_key = f"fuzzy_{hash(text)}_{len(potential_terms)}_{source_lang}_{target_lang}"
        if cache_key in self._fuzzy_cache:
            logger.debug(f"使用模糊匹配缓存: {len(text)} 字符")
            return self._fuzzy_cache[cache_key]
        
        results = []
        
        try:
            # 1. 精确匹配
            exact_matches = self._find_exact_matches(text, potential_terms)
            for match in exact_matches:
                results.append(FuzzyMatchResult(
                    term=match,
                    confidence=1.0,
                    match_type='exact'
                ))
            
            # 2. 编辑距离匹配
            edit_matches = self._find_edit_distance_matches(text, potential_terms)
            for match, score in edit_matches:
                if score >= self.fuzzy_threshold:
                    results.append(FuzzyMatchResult(
                        term=match,
                        confidence=score,
                        match_type='edit_distance'
                    ))
            
            # 3. 缩写匹配
            abbreviation_matches = self._find_abbreviation_matches(text, potential_terms)
            for match, score in abbreviation_matches:
                results.append(FuzzyMatchResult(
                    term=match,
                    confidence=score,
                    match_type='abbreviation'
                ))
            
            # 4. 词形变化匹配
            morphological_matches = self._find_morphological_matches(text, potential_terms, source_lang)
            for match, score in morphological_matches:
                results.append(FuzzyMatchResult(
                    term=match,
                    confidence=score,
                    match_type='morphological'
                ))
            
            # 5. 语义匹配（使用大模型）
            semantic_matches = self._find_semantic_matches(text, potential_terms, source_lang, target_lang)
            for match, score in semantic_matches:
                results.append(FuzzyMatchResult(
                    term=match,
                    confidence=score,
                    match_type='semantic'
                ))
            
            # 去重并按置信度排序
            unique_results = self._deduplicate_results(results)
            unique_results.sort(key=lambda x: x.confidence, reverse=True)
            
            # 更新缓存
            self._update_cache(self._fuzzy_cache, cache_key, unique_results)
            
            logger.debug(f"模糊匹配完成，找到 {len(unique_results)} 个候选")
            return unique_results
            
        except Exception as e:
            logger.error(f"模糊匹配失败: {str(e)}")
            return []
    
    def disambiguate_term(self, term: str, context: str, 
                         source_lang: str = "en", target_lang: str = "zh") -> EnhancementResult:
        """
        术语消歧，根据上下文确定最佳翻译
        
        Args:
            term: 源术语
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            消歧结果
        """
        start_time = time.time()
        
        # 检查缓存
        cache_key = f"disamb_{term}_{hash(context)}_{source_lang}_{target_lang}"
        if cache_key in self._disambiguation_cache:
            logger.debug(f"使用消歧缓存: {term}")
            result = self._disambiguation_cache[cache_key]
            return result
        
        try:
            # 检测是否为多义词
            if not self._is_polysemous_term(term, source_lang, target_lang):
                # 不是多义词，直接返回传统翻译
                traditional_translation = self._get_traditional_translation(term, source_lang, target_lang)
                result = EnhancementResult(
                    original_term=term,
                    enhanced_translation=traditional_translation or term,
                    confidence=0.9,
                    enhancement_type='disambiguation',
                    processing_time=time.time() - start_time,
                    metadata={'polysemous': False}
                )
                return result
            
            # 构建消歧提示词
            prompt = self._build_disambiguation_prompt(term, context, source_lang, target_lang)
            
            # 调用大模型
            response = self.model_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            # 提取消歧结果
            disambiguated_translation = self._extract_disambiguation_result(response)
            
            # 计算置信度
            confidence = self._calculate_disambiguation_confidence(response, context)
            
            # 创建结果
            result = EnhancementResult(
                original_term=term,
                enhanced_translation=disambiguated_translation,
                confidence=confidence,
                enhancement_type='disambiguation',
                processing_time=time.time() - start_time,
                metadata={
                    'polysemous': True,
                    'context_length': len(context),
                    'response_length': len(response)
                }
            )
            
            # 更新缓存
            self._update_cache(self._disambiguation_cache, cache_key, result)
            
            logger.debug(f"术语消歧完成: {term} -> {disambiguated_translation}")
            return result
            
        except Exception as e:
            logger.error(f"术语消歧失败: {term}, 错误: {e}")
            # 返回传统翻译作为降级
            traditional_translation = self._get_traditional_translation(term, source_lang, target_lang)
            return EnhancementResult(
                original_term=term,
                enhanced_translation=traditional_translation or term,
                confidence=0.5,
                enhancement_type='disambiguation',
                processing_time=time.time() - start_time,
                metadata={'error': str(e), 'fallback': True}
            )
    
    def handle_complex_scenario(self, text: str, source_lang: str = "en", 
                              target_lang: str = "zh") -> EnhancementResult:
        """
        处理复杂场景，如HTML标签、代码片段等
        
        Args:
            text: 输入文本
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            处理结果
        """
        start_time = time.time()
        
        try:
            # 检测复杂元素
            complex_elements = self._detect_complex_elements(text)
            
            if not complex_elements:
                # 没有复杂元素，直接返回
                return EnhancementResult(
                    original_term=text,
                    enhanced_translation=text,
                    confidence=1.0,
                    enhancement_type='complex_scenario',
                    processing_time=time.time() - start_time,
                    metadata={'complex_elements': False}
                )
            
            # 隔离元素
            isolated_elements = self._isolate_elements(text, complex_elements)
            
            # 分别处理
            processed_elements = []
            for element in isolated_elements:
                if element['type'] == 'text':
                    # 翻译文本元素
                    translation = self.model_client.translate_text(
                        text=element['content'],
                        source_lang=source_lang,
                        target_lang=target_lang,
                        temperature=0.1
                    )
                    processed_elements.append({
                        'type': 'text',
                        'content': translation,
                        'original': element['content']
                    })
                else:
                    # 保留非文本元素
                    processed_elements.append(element)
            
            # 合并结果
            result_text = self._merge_processed_elements(processed_elements)
            
            # 创建结果
            result = EnhancementResult(
                original_term=text,
                enhanced_translation=result_text,
                confidence=0.9,
                enhancement_type='complex_scenario',
                processing_time=time.time() - start_time,
                metadata={
                    'complex_elements': True,
                    'element_count': len(complex_elements),
                    'element_types': [e['type'] for e in complex_elements]
                }
            )
            
            logger.debug(f"复杂场景处理完成，处理了 {len(complex_elements)} 个复杂元素")
            return result
            
        except Exception as e:
            logger.error(f"复杂场景处理失败: {str(e)}")
            return EnhancementResult(
                original_term=text,
                enhanced_translation=text,
                confidence=0.0,
                enhancement_type='complex_scenario',
                processing_time=time.time() - start_time,
                metadata={'error': str(e)}
            )
    
    def should_use_enhancement(self, text: str, traditional_matches: List, 
                             source_lang: str = "en", target_lang: str = "zh") -> bool:
        """
        判断是否应该使用增强功能
        
        Args:
            text: 输入文本
            traditional_matches: 传统匹配结果
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            是否使用增强功能
        """
        try:
            # 1. 如果传统匹配率很高，不使用增强
            if traditional_matches:
                match_rate = len(traditional_matches) / len(text.split())
                if match_rate > 0.8:
                    return False
            
            # 2. 检测复杂元素
            complex_elements = self._detect_complex_elements(text)
            if complex_elements:
                return True
            
            # 3. 检测可能的模糊匹配
            fuzzy_candidates = self._detect_fuzzy_candidates(text)
            if fuzzy_candidates:
                return True
            
            # 4. 检测多义词
            potential_polysems = self._detect_potential_polysems(text, source_lang, target_lang)
            if potential_polysems:
                return True
            
            # 5. 文本复杂度分析
            complexity_score = self._analyze_text_complexity(text)
            if complexity_score > 0.7:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"判断增强使用失败: {str(e)}")
            return True  # 默认使用增强
    
    # 私有方法
    
    def _build_context_prompt(self, term: str, context: str, 
                             source_lang: str, target_lang: str) -> str:
        """构建上下文感知的翻译提示词"""
        return f"""请将以下{source_lang}术语翻译为{target_lang}，考虑提供的上下文信息，确保翻译的一致性和准确性。

术语：{term}

上下文信息：
{context}

要求：
1. 根据上下文选择最合适的翻译
2. 如果上下文中已有相关术语的翻译，请保持一致性
3. 考虑术语的专业领域和语境
4. 只返回翻译结果，不要解释

翻译："""
    
    def _build_disambiguation_prompt(self, term: str, context: str, 
                                   source_lang: str, target_lang: str) -> str:
        """构建消歧提示词"""
        return f"""术语"{term}"是一个多义词，请根据以下上下文信息确定其在{target_lang}中的最佳翻译。

术语：{term}

上下文：
{context}

请分析：
1. 术语在当前上下文中的具体含义
2. 考虑专业领域和语境
3. 选择最准确的翻译

要求：
1. 只返回最合适的翻译结果
2. 不要包含解释或分析过程

翻译："""
    
    def _extract_translation_from_response(self, response: str) -> str:
        """从响应中提取翻译结果"""
        # 简单提取，可以根据需要优化
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('翻译') and not line.startswith('翻译：'):
                return line
        return response.strip()
    
    def _extract_disambiguation_result(self, response: str) -> str:
        """从消歧响应中提取结果"""
        return self._extract_translation_from_response(response)
    
    def _calculate_confidence(self, response: str, term: str, context: str) -> float:
        """计算置信度"""
        # 简单的置信度计算，可以根据需要优化
        base_confidence = 0.8
        
        # 根据响应长度调整
        if len(response) > 100:
            base_confidence -= 0.1
        
        # 根据上下文长度调整
        if len(context) > 50:
            base_confidence += 0.1
        
        return min(1.0, max(0.0, base_confidence))
    
    def _calculate_disambiguation_confidence(self, response: str, context: str) -> float:
        """计算消歧置信度"""
        base_confidence = 0.7
        
        # 根据上下文丰富度调整
        if len(context) > 100:
            base_confidence += 0.2
        
        return min(1.0, max(0.0, base_confidence))
    
    def _update_cache(self, cache: Dict, key: str, value: Any):
        """更新缓存"""
        if len(cache) >= self.max_cache_size:
            # 简单的LRU：删除第一个元素
            first_key = next(iter(cache))
            del cache[first_key]
        
        cache[key] = value
    
    def _find_exact_matches(self, text: str, potential_terms: List[str]) -> List[str]:
        """查找精确匹配"""
        matches = []
        text_lower = text.lower()
        
        for term in potential_terms:
            if term.lower() in text_lower:
                matches.append(term)
        
        return matches
    
    def _find_edit_distance_matches(self, text: str, potential_terms: List[str]) -> List[Tuple[str, float]]:
        """查找编辑距离匹配"""
        matches = []
        text_words = text.lower().split()
        
        for term in potential_terms:
            term_lower = term.lower()
            for word in text_words:
                distance = self._calculate_edit_distance(word, term_lower)
                if distance > 0:
                    similarity = 1.0 - (distance / max(len(word), len(term_lower)))
                    if similarity >= self.fuzzy_threshold:
                        matches.append((term, similarity))
        
        return matches
    
    def _calculate_edit_distance(self, s1: str, s2: str) -> int:
        """计算编辑距离"""
        if len(s1) < len(s2):
            return self._calculate_edit_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _find_abbreviation_matches(self, text: str, potential_terms: List[str]) -> List[Tuple[str, float]]:
        """查找缩写匹配"""
        matches = []
        
        # 简单的缩写检测：首字母匹配
        text_words = text.split()
        for term in potential_terms:
            if ' ' in term:
                term_words = term.split()
                # 生成缩写
                abbreviation = ''.join([word[0].upper() for word in term_words])
                for word in text_words:
                    if word.upper() == abbreviation:
                        matches.append((term, 0.9))
        
        return matches
    
    def _find_morphological_matches(self, text: str, potential_terms: List[str], 
                                  source_lang: str) -> List[Tuple[str, float]]:
        """查找词形变化匹配"""
        matches = []
        
        # 简单的词形变化检测：常见后缀
        text_words = text.lower().split()
        
        for term in potential_terms:
            term_lower = term.lower()
            
            for word in text_words:
                # 检查常见后缀变化
                if word.endswith('ing') and term_lower.endswith('e'):
                    if word[:-3] + 'e' == term_lower:
                        matches.append((term, 0.8))
                elif word.endswith('ed') and term_lower.endswith('e'):
                    if word[:-2] + 'e' == term_lower:
                        matches.append((term, 0.8))
                elif word.endswith('s') and term_lower.endswith('y'):
                    if word[:-1] + 'y' == term_lower:
                        matches.append((term, 0.8))
        
        return matches
    
    def _find_semantic_matches(self, text: str, potential_terms: List[str], 
                             source_lang: str, target_lang: str) -> List[Tuple[str, float]]:
        """使用大模型进行语义匹配"""
        matches = []
        
        try:
            # 构建语义匹配提示词
            prompt = f"""请分析以下文本中的术语，并从候选术语列表中选择最匹配的术语。

文本：{text}

候选术语：{', '.join(potential_terms)}

要求：
1. 分析文本的语义和语境
2. 从候选术语中选择最相关的
3. 返回格式：术语:置信度(0-1)
4. 每行一个术语，按置信度排序

匹配结果："""
            
            response = self.model_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            # 解析响应
            for line in response.strip().split('\n'):
                if ':' in line:
                    term, confidence_str = line.split(':', 1)
                    term = term.strip()
                    try:
                        confidence = float(confidence_str.strip())
                        if confidence >= self.fuzzy_threshold:
                            matches.append((term, confidence))
                    except ValueError:
                        continue
        
        except Exception as e:
            logger.error(f"语义匹配失败: {str(e)}")
        
        return matches
    
    def _deduplicate_results(self, results: List[FuzzyMatchResult]) -> List[FuzzyMatchResult]:
        """去重结果"""
        seen_terms = set()
        unique_results = []
        
        for result in results:
            if result.term not in seen_terms:
                seen_terms.add(result.term)
                unique_results.append(result)
        
        return unique_results
    
    def _is_polysemous_term(self, term: str, source_lang: str, target_lang: str) -> bool:
        """检测是否为多义词"""
        # 简单检测：查找多个翻译
        translations = self.traditional_store.find_terms(
            source_lang=source_lang,
            target_lang=target_lang,
            source_term=term
        )
        
        return len(translations) > 1
    
    def _get_traditional_translation(self, term: str, source_lang: str, target_lang: str) -> Optional[str]:
        """获取传统翻译"""
        translations = self.traditional_store.find_terms(
            source_lang=source_lang,
            target_lang=target_lang,
            source_term=term
        )
        
        if translations:
            # 返回置信度最高的翻译
            best_translation = max(translations, key=lambda x: x.confidence)
            return best_translation.target_term
        
        return None
    
    def _detect_complex_elements(self, text: str) -> List[Dict]:
        """检测复杂元素"""
        elements = []
        
        # HTML标签检测
        html_pattern = re.compile(r'<[^>]+>')
        html_matches = html_pattern.finditer(text)
        for match in html_matches:
            elements.append({
                'type': 'html',
                'content': match.group(),
                'start': match.start(),
                'end': match.end()
            })
        
        # 代码片段检测
        code_patterns = [
            re.compile(r'```[^`]+```'),  # 代码块
            re.compile(r'`[^`]+`'),      # 行内代码
            re.compile(r'import\s+\w+'), # import语句
            re.compile(r'function\s+\w+\s*\('), # 函数定义
        ]
        
        for pattern in code_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                elements.append({
                    'type': 'code',
                    'content': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
        
        return elements
    
    def _isolate_elements(self, text: str, complex_elements: List[Dict]) -> List[Dict]:
        """隔离元素"""
        if not complex_elements:
            return [{'type': 'text', 'content': text}]
        
        # 按位置排序
        complex_elements.sort(key=lambda x: x['start'])
        
        elements = []
        last_end = 0
        
        for element in complex_elements:
            # 添加前面的文本
            if element['start'] > last_end:
                text_content = text[last_end:element['start']]
                if text_content.strip():
                    elements.append({
                        'type': 'text',
                        'content': text_content
                    })
            
            # 添加复杂元素
            elements.append(element)
            last_end = element['end']
        
        # 添加最后的文本
        if last_end < len(text):
            text_content = text[last_end:]
            if text_content.strip():
                elements.append({
                    'type': 'text',
                    'content': text_content
                })
        
        return elements
    
    def _merge_processed_elements(self, elements: List[Dict]) -> str:
        """合并处理后的元素"""
        result = ""
        
        for element in elements:
            if element['type'] == 'text':
                result += element['content']
            else:
                result += element['content']
        
        return result
    
    def _detect_fuzzy_candidates(self, text: str) -> bool:
        """检测模糊匹配候选"""
        # 简单检测：检查是否有拼写错误的迹象
        words = text.split()
        
        for word in words:
            # 检查是否有连续重复字符
            if re.search(r'(.)\1{2,}', word):
                return True
            
            # 检查是否有不常见的字符组合
            if re.search(r'[qjxzk]', word.lower()):
                return True
        
        return False
    
    def _detect_potential_polysems(self, text: str, source_lang: str, target_lang: str) -> bool:
        """检测潜在多义词"""
        # 简单检测：检查常见多义词
        common_polysems = ['light', 'bank', 'book', 'run', 'set', 'get', 'spring', 'mine']
        
        words = text.lower().split()
        for word in words:
            if word in common_polysems:
                return True
        
        return False
    
    def _analyze_text_complexity(self, text: str) -> float:
        """分析文本复杂度"""
        complexity = 0.0
        
        # 长度复杂度
        if len(text) > 500:
            complexity += 0.2
        
        # 句子复杂度
        sentences = text.split('.')
        if len(sentences) > 5:
            complexity += 0.2
        
        # 词汇复杂度
        words = text.split()
        long_words = [w for w in words if len(w) > 10]
        if len(long_words) / len(words) > 0.1:
            complexity += 0.2
        
        # 标点复杂度
        if re.search(r'[;:()\[\]{}]', text):
            complexity += 0.2
        
        # 数字和符号复杂度
        if re.search(r'\d+[^a-zA-Z\s]', text):
            complexity += 0.2
        
        return min(1.0, complexity)