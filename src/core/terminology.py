"""
UnityLangPX 术语库核心模块

实现术语的数据模型、匹配算法和基础操作。
"""

import re
import time
import uuid
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class TerminologyEntry:
    """术语条目数据模型"""
    id: str
    source_term: str
    target_term: str
    source_lang: str
    target_lang: str
    domain: str = "通用"
    context: str = ""
    confidence: float = 1.0
    usage_count: int = 0
    user_preference_score: float = 0.5
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TerminologyEntry':
        """从字典创建"""
        return cls(**data)
    
    def update_usage(self):
        """更新使用统计"""
        self.usage_count += 1
        self.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def update_preference(self, score: float):
        """更新用户偏好评分"""
        self.user_preference_score = max(0.0, min(1.0, score))
        self.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")


class TerminologyMatcher:
    """术语匹配器"""
    
    def __init__(self):
        # 预编译正则表达式提高性能
        self.word_pattern = re.compile(r'\b\w+\b', re.UNICODE)
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    
    def extract_potential_terms(self, text: str, source_lang: str) -> List[str]:
        """
        从文本中提取潜在术语
        
        Args:
            text: 输入文本
            source_lang: 源语言
            
        Returns:
            潜在术语列表
        """
        if source_lang in ['zh', 'ja', 'ko']:
            # 中文、日文、韩文：提取连续的汉字
            terms = self.chinese_pattern.findall(text)
            # 过滤掉太短或太长的词
            terms = [term for term in terms if 2 <= len(term) <= 10]
        else:
            # 英文等：提取单词和词组
            words = self.word_pattern.findall(text)
            # 过滤掉太短的词
            words = [word for word in words if len(word) >= 3]
            
            # 尝试组合相邻单词形成词组
            terms = []
            for i in range(len(words)):
                # 单个词
                terms.append(words[i])
                
                # 两词组合
                if i < len(words) - 1:
                    terms.append(f"{words[i]} {words[i+1]}")
                
                # 三词组合
                if i < len(words) - 2:
                    terms.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        
        # 去重并按长度排序（长词优先）
        terms = list(set(terms))
        terms.sort(key=len, reverse=True)
        
        return terms
    
    def find_exact_matches(self, text: str, terminology: List[TerminologyEntry],
                          source_lang: str, target_lang: str) -> List[Tuple[TerminologyEntry, str]]:
        """
        查找精确匹配的术语
        
        Args:
            text: 输入文本
            terminology: 术语列表
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            匹配结果列表，每个元素为(术语条目, 匹配位置)
        """
        matches = []
        
        # 按长度排序，确保长词优先匹配
        filtered_terms = [
            term for term in terminology
            if term.source_lang == source_lang and term.target_lang == target_lang
        ]
        filtered_terms.sort(key=lambda x: len(x.source_term), reverse=True)
        
        # 记录已匹配的位置，避免重复匹配
        matched_positions = set()
        
        for term in filtered_terms:
            # 查找所有匹配位置
            start = 0
            while True:
                pos = text.find(term.source_term, start)
                if pos == -1:
                    break
                
                # 检查是否为完整词汇边界
                if self._is_word_boundary(text, term.source_term, pos):
                    # 检查是否与已匹配的位置重叠
                    term_end = pos + len(term.source_term)
                    overlap = False
                    for matched_start, matched_end in matched_positions:
                        if not (term_end <= matched_start or pos >= matched_end):
                            overlap = True
                            break
                    
                    if not overlap:
                        matches.append((term, term.source_term))
                        matched_positions.add((pos, term_end))
                        start = term_end
                    else:
                        start = pos + 1
                else:
                    start = pos + 1
        
        return matches
    
    def _is_word_boundary(self, text: str, term: str, position: int) -> bool:
        """
        检查是否为词汇边界
        
        Args:
            text: 原文本
            term: 术语
            position: 位置
            
        Returns:
            是否为词汇边界
        """
        # 检查前一个字符
        if position > 0:
            prev_char = text[position - 1]
            if self._is_word_char(prev_char):
                return False
        
        # 检查后一个字符
        end_pos = position + len(term)
        if end_pos < len(text):
            next_char = text[end_pos]
            if self._is_word_char(next_char):
                return False
        
        return True
    
    def _is_word_char(self, char: str) -> bool:
        """判断是否为词汇字符"""
        # 英文字母、数字、下划线
        if char.isalnum() or char == '_':
            return True
        
        # 中文字符
        if '\u4e00' <= char <= '\u9fff':
            return True
        
        return False


class TraditionalTerminologyStore:
    """传统术语库存储"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        初始化术语库存储
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path or Path("data/terminology.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.terminology: Dict[str, TerminologyEntry] = {}
        self.language_pairs: Dict[str, Set[str]] = {}
        self.domains: Set[str] = set()
        
        # 索引
        self.source_term_index: Dict[str, List[str]] = {}  # 源术语 -> 术语ID列表
        self.domain_index: Dict[str, List[str]] = {}      # 领域 -> 术语ID列表
        
        self.load()
    
    def load(self):
        """加载术语库"""
        if not self.storage_path.exists():
            logger.info(f"术语库文件不存在，创建新的: {self.storage_path}")
            return
        
        try:
            import json
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.terminology.clear()
            self.language_pairs.clear()
            self.domains.clear()
            self.source_term_index.clear()
            self.domain_index.clear()
            
            for term_data in data.get("terminology", []):
                entry = TerminologyEntry.from_dict(term_data)
                self.terminology[entry.id] = entry
                
                # 更新索引
                self._update_indexes(entry)
            
            logger.info(f"已加载 {len(self.terminology)} 个术语")
            
        except Exception as e:
            logger.error(f"加载术语库失败: {e}")
            self.terminology = {}
    
    def save(self):
        """保存术语库"""
        try:
            import json
            data = {
                "terminology": [entry.to_dict() for entry in self.terminology.values()],
                "metadata": {
                    "total_count": len(self.terminology),
                    "language_pairs": list(self.language_pairs.keys()),
                    "domains": list(self.domains),
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"术语库已保存到: {self.storage_path}")
            
        except Exception as e:
            logger.error(f"保存术语库失败: {e}")
    
    def add_term(self, entry: TerminologyEntry) -> bool:
        """
        添加术语
        
        Args:
            entry: 术语条目
            
        Returns:
            是否添加成功
        """
        if entry.id in self.terminology:
            logger.warning(f"术语已存在: {entry.id}")
            return False
        
        self.terminology[entry.id] = entry
        self._update_indexes(entry)
        
        logger.debug(f"已添加术语: {entry.source_term} -> {entry.target_term}")
        return True
    
    def update_term(self, entry: TerminologyEntry) -> bool:
        """
        更新术语
        
        Args:
            entry: 术语条目
            
        Returns:
            是否更新成功
        """
        if entry.id not in self.terminology:
            logger.warning(f"术语不存在: {entry.id}")
            return False
        
        # 清除旧索引
        old_entry = self.terminology[entry.id]
        self._remove_from_indexes(old_entry)
        
        # 更新术语
        entry.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.terminology[entry.id] = entry
        self._update_indexes(entry)
        
        logger.debug(f"已更新术语: {entry.source_term} -> {entry.target_term}")
        return True
    
    def delete_term(self, term_id: str) -> bool:
        """
        删除术语
        
        Args:
            term_id: 术语ID
            
        Returns:
            是否删除成功
        """
        if term_id not in self.terminology:
            logger.warning(f"术语不存在: {term_id}")
            return False
        
        entry = self.terminology[term_id]
        self._remove_from_indexes(entry)
        del self.terminology[term_id]
        
        logger.debug(f"已删除术语: {entry.source_term} -> {entry.target_term}")
        return True
    
    def get_term(self, term_id: str) -> Optional[TerminologyEntry]:
        """获取术语"""
        return self.terminology.get(term_id)
    
    def find_terms(self, source_lang: str = None, target_lang: str = None,
                  domain: str = None, source_term: str = None) -> List[TerminologyEntry]:
        """
        查找术语
        
        Args:
            source_lang: 源语言
            target_lang: 目标语言
            domain: 领域
            source_term: 源术语
            
        Returns:
            匹配的术语列表
        """
        results = []
        
        for entry in self.terminology.values():
            if source_lang and entry.source_lang != source_lang:
                continue
            if target_lang and entry.target_lang != target_lang:
                continue
            if domain and entry.domain != domain:
                continue
            if source_term and entry.source_term != source_term:
                continue
            
            results.append(entry)
        
        return results
    
    def get_terms_by_domain(self, domain: str) -> List[TerminologyEntry]:
        """根据领域获取术语"""
        return [self.terminology[term_id] for term_id in self.domain_index.get(domain, [])]
    
    def get_language_pairs(self) -> List[str]:
        """获取所有语言对"""
        return list(self.language_pairs.keys())
    
    def get_domains(self) -> List[str]:
        """获取所有领域"""
        return list(self.domains)
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = {
            "total_terms": len(self.terminology),
            "language_pairs": len(self.language_pairs),
            "domains": len(self.domains),
            "usage_stats": {}
        }
        
        # 使用统计
        for entry in self.terminology.values():
            usage = entry.usage_count
            if usage not in stats["usage_stats"]:
                stats["usage_stats"][usage] = 0
            stats["usage_stats"][usage] += 1
        
        return stats
    
    def _update_indexes(self, entry: TerminologyEntry):
        """更新索引"""
        # 语言对索引
        lang_pair = f"{entry.source_lang}-{entry.target_lang}"
        if lang_pair not in self.language_pairs:
            self.language_pairs[lang_pair] = set()
        self.language_pairs[lang_pair].add(entry.id)
        
        # 领域索引
        self.domains.add(entry.domain)
        if entry.domain not in self.domain_index:
            self.domain_index[entry.domain] = []
        if entry.id not in self.domain_index[entry.domain]:
            self.domain_index[entry.domain].append(entry.id)
        
        # 源术语索引
        source_key = entry.source_term.lower()
        if source_key not in self.source_term_index:
            self.source_term_index[source_key] = []
        if entry.id not in self.source_term_index[source_key]:
            self.source_term_index[source_key].append(entry.id)
    
    def _remove_from_indexes(self, entry: TerminologyEntry):
        """从索引中移除"""
        # 语言对索引
        lang_pair = f"{entry.source_lang}-{entry.target_lang}"
        if lang_pair in self.language_pairs:
            self.language_pairs[lang_pair].discard(entry.id)
            if not self.language_pairs[lang_pair]:
                del self.language_pairs[lang_pair]
        
        # 领域索引
        if entry.domain in self.domain_index:
            if entry.id in self.domain_index[entry.domain]:
                self.domain_index[entry.domain].remove(entry.id)
            if not self.domain_index[entry.domain]:
                del self.domain_index[entry.domain]
        
        # 源术语索引
        source_key = entry.source_term.lower()
        if source_key in self.source_term_index:
            if entry.id in self.source_term_index[source_key]:
                self.source_term_index[source_key].remove(entry.id)
            if not self.source_term_index[source_key]:
                del self.source_term_index[source_key]
        
        # 领域集合
        if not any(e.domain == entry.domain for e in self.terminology.values()):
            self.domains.discard(entry.domain)
    
    def get_all_terms(self) -> List[TerminologyEntry]:
        """获取所有术语"""
        return list(self.terminology.values())
    
    def get_terms_by_ids(self, term_ids: List[str]) -> List[TerminologyEntry]:
        """根据ID列表获取术语"""
        return [self.terminology[term_id] for term_id in term_ids if term_id in self.terminology]
    
    def get_terms_by_language_pair(self, source_lang: str, target_lang: str) -> List[TerminologyEntry]:
        """根据语言对获取术语"""
        return [
            term for term in self.terminology.values()
            if term.source_lang == source_lang and term.target_lang == target_lang
        ]
    
    def count_terms_by_domain(self) -> Dict[str, int]:
        """按领域统计术语数量"""
        domain_counts = {}
        for term in self.terminology.values():
            domain_counts[term.domain] = domain_counts.get(term.domain, 0) + 1
        return domain_counts
    
    def count_terms_by_language_pair(self) -> Dict[str, int]:
        """按语言对统计术语数量"""
        lang_pair_counts = {}
        for term in self.terminology.values():
            lang_pair = f"{term.source_lang}-{term.target_lang}"
            lang_pair_counts[lang_pair] = lang_pair_counts.get(lang_pair, 0) + 1
        return lang_pair_counts
    
    def get_recent_terms(self, limit: int = 10) -> List[TerminologyEntry]:
        """获取最近添加的术语"""
        sorted_terms = sorted(
            self.terminology.values(),
            key=lambda x: x.created_at,
            reverse=True
        )
        return sorted_terms[:limit]
    
    def get_most_used_terms(self, limit: int = 10) -> List[TerminologyEntry]:
        """获取最常用的术语"""
        sorted_terms = sorted(
            self.terminology.values(),
            key=lambda x: x.usage_count,
            reverse=True
        )
        return sorted_terms[:limit]
    
    def search_terms_by_text(self, query: str, fields: List[str] = None) -> List[TerminologyEntry]:
        """全文搜索术语"""
        if fields is None:
            fields = ["source_term", "target_term", "context", "domain"]
        
        query = query.lower()
        results = []
        
        for term in self.terminology.values():
            for field in fields:
                if hasattr(term, field):
                    field_value = getattr(term, field).lower()
                    if query in field_value:
                        results.append(term)
                        break
        
        return results


class TerminologyReplacer:
    """术语替换器"""
    
    def __init__(self, matcher: TerminologyMatcher = None):
        """
        初始化术语替换器
        
        Args:
            matcher: 术语匹配器
        """
        self.matcher = matcher or TerminologyMatcher()
    
    def apply_terminology(self, text: str, matches: List[Tuple[TerminologyEntry, str]],
                         source_lang: str, target_lang: str) -> str:
        """
        应用术语翻译
        
        Args:
            text: 原文
            matches: 匹配结果
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            应用术语后的文本
        """
        if not matches:
            return text
        
        # 按位置排序，确保从后往前替换，避免位置偏移
        # 需要先确定每个匹配的实际位置
        match_positions = []
        for term, matched_text in matches:
            start = 0
            while True:
                pos = text.find(matched_text, start)
                if pos == -1:
                    break
                
                # 检查是否为完整词汇边界
                if self.matcher._is_word_boundary(text, matched_text, pos):
                    match_positions.append((pos, pos + len(matched_text), term, matched_text))
                    start = pos + len(matched_text)
                else:
                    start = pos + 1
        
        # 按位置排序，从后往前替换
        match_positions.sort(key=lambda x: x[0], reverse=True)
        
        result = text
        for start, end, term, matched_text in match_positions:
            # 替换术语
            result = result[:start] + term.target_term + result[end:]
        
        return result
    
    def get_replacement_preview(self, text: str, matches: List[Tuple[TerminologyEntry, str]]) -> List[Dict]:
        """
        获取替换预览
        
        Args:
            text: 原文
            matches: 匹配结果
            
        Returns:
            替换预览列表
        """
        previews = []
        
        for term, matched_text in matches:
            start = 0
            while True:
                pos = text.find(matched_text, start)
                if pos == -1:
                    break
                
                if self.matcher._is_word_boundary(text, matched_text, pos):
                    previews.append({
                        "source_term": matched_text,
                        "target_term": term.target_term,
                        "position": pos,
                        "domain": term.domain,
                        "confidence": term.confidence,
                        "context": text[max(0, pos-20):pos+len(matched_text)+20]
                    })
                
                start = pos + 1
        
        return previews