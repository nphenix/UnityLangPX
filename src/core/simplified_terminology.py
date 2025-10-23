"""
UnityLangPX 简化术语库模块

基于大模型的简化术语处理架构，通过端到端的大模型处理
减少复杂的中间逻辑，提高翻译质量和一致性。
"""

import time
import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock

from .models.base import ModelClient
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class TermTranslation:
    """术语翻译结果"""
    source_term: str
    target_term: str
    confidence: float
    context: str = ""
    domain: str = "通用"


@dataclass
class ProcessResult:
    """处理结果"""
    original_text: str
    processed_text: str
    translations: List[TermTranslation]
    processing_time: float
    cache_hit: bool = False
    quality_score: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IntelligentPromptBuilder:
    """智能提示词构建器"""
    
    def __init__(self):
        # 基础提示词模板
        self.base_template = """
你是一个专业的术语翻译专家。请将以下{source_lang}文本中的术语翻译为{target_lang}。

文本：{text}

上下文：{context}

要求：
1. 识别文本中的专业术语
2. 保持术语翻译的一致性
3. 考虑上下文选择最合适的翻译
4. 返回格式：术语1:翻译1:置信度1|术语2:翻译2:置信度2|...

翻译结果："""

        # 领域特定模板
        self.domain_templates = {
            "技术": """
你是技术领域的翻译专家。请将以下{source_lang}技术文档中的术语翻译为{target_lang}。

文本：{text}
技术领域：{context}

要求：
1. 准确翻译技术术语，如API、UI、UX等
2. 保持技术术语的一致性
3. 考虑技术上下文选择最合适的翻译
4. 返回格式：术语1:翻译1:置信度1|术语2:翻译2:置信度2|...

翻译结果：""",
            
            "医学": """
你是医学领域的翻译专家。请将以下{source_lang}医学文本中的术语翻译为{target_lang}。

文本：{text}
医学背景：{context}

要求：
1. 准确翻译医学术语
2. 使用标准的医学术语翻译
3. 考虑医学上下文选择最合适的翻译
4. 返回格式：术语1:翻译1:置信度1|术语2:翻译2:置信度2|...

翻译结果：""",
            
            "法律": """
你是法律领域的翻译专家。请将以下{source_lang}法律文本中的术语翻译为{target_lang}。

文本：{text}
法律背景：{context}

要求：
1. 准确翻译法律术语
2. 使用标准的法律术语翻译
3. 考虑法律上下文选择最合适的翻译
4. 返回格式：术语1:翻译1:置信度1|术语2:翻译2:置信度2|...

翻译结果："""
        }
    
    def build_prompt(self, text: str, context: str, source_lang: str, 
                    target_lang: str, domain: str = "通用") -> str:
        """
        构建智能提示词
        
        Args:
            text: 输入文本
            context: 上下文信息
            source_lang: 源语言
            target_lang: 目标语言
            domain: 专业领域
            
        Returns:
            构建的提示词
        """
        # 检测是否需要使用领域特定模板
        if domain in self.domain_templates:
            template = self.domain_templates[domain]
        else:
            template = self.base_template
        
        # 添加术语示例（如果有）
        examples = self._get_domain_examples(domain, source_lang, target_lang)
        if examples:
            template += f"\n\n术语翻译示例：\n{examples}"
        
        # 构建最终提示词
        prompt = template.format(
            source_lang=source_lang,
            target_lang=target_lang,
            text=text,
            context=context or "无特定上下文"
        )
        
        return prompt
    
    def _get_domain_examples(self, domain: str, source_lang: str, target_lang: str) -> str:
        """获取领域特定示例"""
        examples = {
            "技术": {
                "en-zh": "API:应用程序接口|UI:用户界面|UX:用户体验",
                "zh-en": "应用程序接口:API|用户界面:UI|用户体验:UX"
            },
            "医学": {
                "en-zh": "MRI:磁共振成像|CT:计算机断层扫描|ECG:心电图",
                "zh-en": "磁共振成像:MRI|计算机断层扫描:CT|心电图:ECG"
            },
            "法律": {
                "en-zh": "Plaintiff:原告|Defendant:被告|Contract:合同",
                "zh-en": "原告:Plaintiff|被告:Defendant|合同:Contract"
            }
        }
        
        lang_pair = f"{source_lang}-{target_lang}"
        if domain in examples and lang_pair in examples[domain]:
            return examples[domain][lang_pair]
        
        return ""


class TerminologyCacheManager:
    """术语缓存管理器"""
    
    def __init__(self, cache_dir: Path = None, max_cache_size: int = 1000):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            max_cache_size: 最大缓存条目数
        """
        self.cache_dir = cache_dir or Path("data/terminology_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size
        
        # 内存缓存
        self._memory_cache: Dict[str, Dict] = {}
        self._cache_lock = Lock()
        
        # 缓存文件路径
        self.cache_file = self.cache_dir / "terminology_cache.json"
        
        # 加载现有缓存
        self._load_cache()
    
    def get(self, text_hash: str) -> Optional[Dict]:
        """获取缓存条目"""
        with self._cache_lock:
            return self._memory_cache.get(text_hash)
    
    def set(self, text_hash: str, data: Dict):
        """设置缓存条目"""
        with self._cache_lock:
            # 检查缓存大小
            if len(self._memory_cache) >= self.max_cache_size:
                self._evict_oldest()
            
            # 添加时间戳
            data["timestamp"] = time.time()
            data["hash"] = text_hash
            
            # 更新内存缓存
            self._memory_cache[text_hash] = data
            
            # 异步保存到磁盘
            self._save_cache_async()
    
    def _evict_oldest(self):
        """淘汰最旧的缓存条目"""
        if not self._memory_cache:
            return
        
        # 找到最旧的条目
        oldest_key = min(
            self._memory_cache.keys(),
            key=lambda k: self._memory_cache[k].get("timestamp", 0)
        )
        
        # 删除最旧的条目
        del self._memory_cache[oldest_key]
        logger.debug(f"淘汰缓存条目: {oldest_key}")
    
    def _load_cache(self):
        """加载缓存文件"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 加载到内存缓存
                self._memory_cache = data.get("cache", {})
                logger.debug(f"加载了 {len(self._memory_cache)} 个缓存条目")
            else:
                logger.debug("缓存文件不存在，创建新的缓存")
                
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            self._memory_cache = {}
    
    def _save_cache_async(self):
        """异步保存缓存（简化实现，实际可以用线程池）"""
        try:
            data = {
                "cache": self._memory_cache,
                "metadata": {
                    "total_entries": len(self._memory_cache),
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def clear(self):
        """清空缓存"""
        with self._cache_lock:
            self._memory_cache.clear()
            try:
                if self.cache_file.exists():
                    self.cache_file.unlink()
                logger.info("缓存已清空")
            except Exception as e:
                logger.error(f"清空缓存文件失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._cache_lock:
            total_entries = len(self._memory_cache)
            
            if total_entries == 0:
                return {
                    "total_entries": 0,
                    "oldest_entry": None,
                    "newest_entry": None,
                    "cache_hit_rate": 0.0
                }
            
            timestamps = [
                entry.get("timestamp", 0) 
                for entry in self._memory_cache.values()
            ]
            
            return {
                "total_entries": total_entries,
                "oldest_entry": min(timestamps),
                "newest_entry": max(timestamps),
                "cache_file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0
            }


class QualityAssessor:
    """质量评估器"""
    
    def __init__(self):
        # 评估权重
        self.weights = {
            "consistency": 0.4,
            "coverage": 0.3,
            "confidence": 0.3
        }
    
    def assess_quality(self, text: str, translations: List[TermTranslation]) -> float:
        """
        评估翻译质量
        
        Args:
            text: 原文
            translations: 翻译结果
            
        Returns:
            质量分数 (0-1)
        """
        if not translations:
            return 0.0
        
        # 1. 一致性评估
        consistency_score = self._assess_consistency(translations)
        
        # 2. 覆盖率评估
        coverage_score = self._assess_coverage(text, translations)
        
        # 3. 置信度评估
        confidence_score = self._assess_confidence(translations)
        
        # 综合评分
        total_score = (
            consistency_score * self.weights["consistency"] +
            coverage_score * self.weights["coverage"] +
            confidence_score * self.weights["confidence"]
        )
        
        return min(1.0, max(0.0, total_score))
    
    def _assess_consistency(self, translations: List[TermTranslation]) -> float:
        """评估翻译一致性"""
        if len(translations) <= 1:
            return 1.0
        
        # 检查是否有重复的源术语有不同的翻译
        source_terms = {}
        for translation in translations:
            source_term = translation.source_term.lower()
            if source_term not in source_terms:
                source_terms[source_term] = []
            source_terms[source_term].append(translation.target_term)
        
        # 计算一致性分数
        consistent_terms = 0
        total_terms = len(source_terms)
        
        for source_term, target_terms in source_terms.items():
            # 如果所有目标术语都相同，则认为是一致的
            if len(set(target_terms)) == 1:
                consistent_terms += 1
        
        return consistent_terms / total_terms if total_terms > 0 else 1.0
    
    def _assess_coverage(self, text: str, translations: List[TermTranslation]) -> float:
        """评估术语覆盖率"""
        # 简化的覆盖率评估：基于术语数量与文本长度的比例
        text_length = len(text.split())
        term_count = len(translations)
        
        # 期望的术语覆盖率（每10个词中有1个术语）
        expected_coverage = text_length / 10
        
        if expected_coverage == 0:
            return 1.0
        
        # 实际覆盖率
        actual_coverage = term_count / expected_coverage
        
        # 限制在0-1范围内
        return min(1.0, actual_coverage)
    
    def _assess_confidence(self, translations: List[TermTranslation]) -> float:
        """评估置信度"""
        if not translations:
            return 0.0
        
        # 计算平均置信度
        total_confidence = sum(t.confidence for t in translations)
        avg_confidence = total_confidence / len(translations)
        
        return avg_confidence


class SimplifiedTerminologyProcessor:
    """简化术语处理器"""
    
    def __init__(self, model_client: ModelClient, config: Any = None):
        """
        初始化简化术语处理器
        
        Args:
            model_client: 大模型客户端
            config: 配置对象
        """
        self.model_client = model_client
        self.config = config
        
        # 初始化组件
        self.prompt_builder = IntelligentPromptBuilder()
        self.cache_manager = TerminologyCacheManager()
        self.quality_assessor = QualityAssessor()
        
        # 配置参数
        self.max_retries = getattr(config, 'max_retries', 3)
        self.temperature = getattr(config, 'temperature', 0.1)
        self.max_tokens = getattr(config, 'max_tokens', 500)
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0.0,
            "average_quality_score": 0.0
        }
        
        logger.info("简化术语处理器初始化完成")
    
    def process_text(self, text: str, source_lang: str = "en", 
                    target_lang: str = "zh", context: str = "", 
                    domain: str = "通用") -> ProcessResult:
        """
        处理文本中的术语
        
        Args:
            text: 输入文本
            source_lang: 源语言
            target_lang: 目标语言
            context: 上下文信息
            domain: 专业领域
            
        Returns:
            处理结果
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # 生成文本哈希用于缓存
        text_hash = self._generate_text_hash(text, source_lang, target_lang, context, domain)
        
        # 检查缓存
        cached_result = self.cache_manager.get(text_hash)
        if cached_result:
            self.stats["cache_hits"] += 1
            logger.debug(f"使用缓存结果: {text_hash}")
            
            # 重建ProcessResult对象
            result = self._reconstruct_result_from_cache(text, cached_result, start_time)
            result.cache_hit = True
            return result
        
        self.stats["cache_misses"] += 1
        
        # 构建提示词
        prompt = self.prompt_builder.build_prompt(
            text, context, source_lang, target_lang, domain
        )
        
        # 调用大模型
        translations = self._call_model_with_retry(prompt)
        
        # 应用翻译到文本
        processed_text = self._apply_translations(text, translations)
        
        # 评估质量
        quality_score = self.quality_assessor.assess_quality(text, translations)
        
        # 创建结果
        result = ProcessResult(
            original_text=text,
            processed_text=processed_text,
            translations=translations,
            processing_time=time.time() - start_time,
            cache_hit=False,
            quality_score=quality_score,
            metadata={
                "source_lang": source_lang,
                "target_lang": target_lang,
                "domain": domain,
                "context_length": len(context),
                "prompt_length": len(prompt)
            }
        )
        
        # 更新缓存
        cache_data = {
            "processed_text": processed_text,
            "translations": [asdict(t) for t in translations],
            "quality_score": quality_score,
            "metadata": result.metadata
        }
        self.cache_manager.set(text_hash, cache_data)
        
        # 更新统计
        self._update_stats(result)
        
        logger.debug(f"处理完成: {len(translations)} 个术语, 质量分数: {quality_score:.2f}")
        return result
    
    def _generate_text_hash(self, text: str, source_lang: str, 
                           target_lang: str, context: str, domain: str) -> str:
        """生成文本哈希用于缓存"""
        content = f"{text}:{source_lang}:{target_lang}:{context}:{domain}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _call_model_with_retry(self, prompt: str) -> List[TermTranslation]:
        """带重试机制的模型调用"""
        for attempt in range(self.max_retries):
            try:
                response = self.model_client.generate(
                    prompt=prompt,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                translations = self._extract_translations_from_response(response)
                if translations:
                    return translations
                
            except Exception as e:
                logger.warning(f"模型调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    logger.error("所有重试均失败，返回空翻译列表")
                    return []
        
        return []
    
    def _extract_translations_from_response(self, response: str) -> List[TermTranslation]:
        """从模型响应中提取翻译结果"""
        translations = []
        
        try:
            # 解析响应格式：术语1:翻译1:置信度1|术语2:翻译2:置信度2|...
            pairs = response.strip().split('|')
            
            for pair in pairs:
                if ':' in pair:
                    parts = pair.split(':')
                    if len(parts) >= 2:
                        source_term = parts[0].strip()
                        target_term = parts[1].strip()
                        
                        # 解析置信度
                        confidence = 0.8  # 默认置信度
                        if len(parts) >= 3:
                            try:
                                confidence = float(parts[2].strip())
                                confidence = min(1.0, max(0.0, confidence))
                            except ValueError:
                                pass
                        
                        # 验证术语
                        if source_term and target_term:
                            translations.append(TermTranslation(
                                source_term=source_term,
                                target_term=target_term,
                                confidence=confidence
                            ))
            
            logger.debug(f"从响应中提取了 {len(translations)} 个翻译")
            return translations
            
        except Exception as e:
            logger.error(f"解析翻译响应失败: {e}")
            return []
    
    def _apply_translations(self, text: str, translations: List[TermTranslation]) -> str:
        """将翻译应用到文本"""
        if not translations:
            return text
        
        result = text
        
        # 按术语长度排序，确保长术语优先匹配
        sorted_translations = sorted(translations, key=lambda x: len(x.source_term), reverse=True)
        
        for translation in sorted_translations:
            # 简单的字符串替换（可以改进为更智能的匹配）
            result = result.replace(translation.source_term, translation.target_term)
        
        return result
    
    def _reconstruct_result_from_cache(self, text: str, cache_data: Dict, start_time: float) -> ProcessResult:
        """从缓存数据重建结果对象"""
        translations = [
            TermTranslation(**t_data) 
            for t_data in cache_data.get("translations", [])
        ]
        
        return ProcessResult(
            original_text=text,
            processed_text=cache_data.get("processed_text", text),
            translations=translations,
            processing_time=time.time() - start_time,
            cache_hit=True,
            quality_score=cache_data.get("quality_score", 0.0),
            metadata=cache_data.get("metadata", {})
        )
    
    def _update_stats(self, result: ProcessResult):
        """更新统计信息"""
        self.stats["total_processing_time"] += result.processing_time
        
        # 更新平均质量分数
        total_requests = self.stats["total_requests"]
        current_avg = self.stats["average_quality_score"]
        new_avg = (current_avg * (total_requests - 1) + result.quality_score) / total_requests
        self.stats["average_quality_score"] = new_avg
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        total_requests = self.stats["total_requests"]
        
        cache_hit_rate = 0.0
        if total_requests > 0:
            cache_hit_rate = self.stats["cache_hits"] / total_requests
        
        avg_processing_time = 0.0
        if total_requests > 0:
            avg_processing_time = self.stats["total_processing_time"] / total_requests
        
        return {
            **self.stats,
            "cache_hit_rate": cache_hit_rate,
            "average_processing_time": avg_processing_time,
            "cache_statistics": self.cache_manager.get_statistics()
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.cache_manager.clear()
        logger.info("处理器缓存已清空")
    
    def shutdown(self):
        """关闭处理器"""
        logger.info("正在关闭简化术语处理器...")
        # 保存最终缓存状态
        self.cache_manager._save_cache_async()
        logger.info("简化术语处理器已关闭")