"""
UnityLangPX RAG智能术语推荐器

实现基于向量相似度的智能术语推荐功能。
"""

import time
import uuid
import threading
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

from .terminology import TerminologyEntry, TraditionalTerminologyStore, TerminologyMatcher
from .vector_store import SQLiteVectorStore, VectorEntry
from .embedding_client import EmbeddingClientFactory, EmbeddingClient
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class RecommendationResult:
    """推荐结果数据模型"""
    source_term: str
    suggested_target: str
    suggestion_type: str  # "exact_match", "vector_similarity", "fuzzy_match"
    confidence: float
    source_term_id: Optional[str] = None
    similarity_score: Optional[float] = None
    domain: Optional[str] = None
    context: Optional[str] = None


class RAGRecommender:
    """RAG智能术语推荐器"""
    
    def __init__(self, config, terminology_store: TraditionalTerminologyStore):
        """
        初始化RAG推荐器
        
        Args:
            config: 术语配置
            terminology_store: 传统术语存储
        """
        self.config = config
        self.terminology_store = terminology_store
        
        # 初始化组件
        self.vector_store: Optional[SQLiteVectorStore] = None
        self.embedding_client: Optional[EmbeddingClient] = None
        self.matcher = TerminologyMatcher()
        
        # 初始化RAG组件
        self._init_rag_components()
        
        # 异步处理队列
        self._vectorization_queue = Queue()
        self._vectorization_worker = None
        self._stop_worker = threading.Event()
        
        # 启动向量化工作线程
        if self.config.enable_rag:
            self._start_vectorization_worker()
        
        logger.info("RAG推荐器初始化完成")
    
    def _init_rag_components(self):
        """初始化RAG组件"""
        if not self.config.enable_rag:
            logger.info("RAG功能已禁用")
            return
        
        try:
            # 初始化向量存储
            self.vector_store = SQLiteVectorStore(
                db_path=self.config.vector_db_path,
                embedding_dim=1024  # 默认维度，将在加载嵌入客户端后更新
            )
            
            # 初始化嵌入客户端
            self.embedding_client = EmbeddingClientFactory.auto_detect_client(
                model_name=self.config.embedding_model
            )
            
            if self.embedding_client and self.embedding_client.is_available():
                logger.info(f"RAG组件初始化成功，使用嵌入模型: {self.config.embedding_model}")
            else:
                logger.warning("嵌入客户端不可用，RAG功能将受限")
                
        except Exception as e:
            logger.error(f"RAG组件初始化失败: {e}")
            self.config.enable_rag = False
    
    def _start_vectorization_worker(self):
        """启动向量化工作线程"""
        if self._vectorization_worker is None or not self._vectorization_worker.is_alive():
            self._stop_worker.clear()
            self._vectorization_worker = threading.Thread(
                target=self._vectorization_worker_loop,
                daemon=True
            )
            self._vectorization_worker.start()
            logger.debug("向量化工作线程已启动")
    
    def _stop_vectorization_worker(self):
        """停止向量化工作线程"""
        if self._vectorization_worker and self._vectorization_worker.is_alive():
            self._stop_worker.set()
            self._vectorization_worker.join(timeout=5)
            logger.debug("向量化工作线程已停止")
    
    def _vectorization_worker_loop(self):
        """向量化工作线程循环"""
        while not self._stop_worker.is_set():
            try:
                # 从队列获取向量化任务
                task = self._vectorization_queue.get(timeout=1)
                if task is None:  # 停止信号
                    break
                
                # 处理向量化任务
                self._process_vectorization_task(task)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"向量化任务处理失败: {e}")
    
    def _process_vectorization_task(self, task: Dict[str, Any]):
        """处理向量化任务"""
        task_type = task.get("type")
        
        if task_type == "vectorize_term":
            term_entry = task.get("term_entry")
            if term_entry:
                self._vectorize_term_sync(term_entry)
        
        elif task_type == "batch_vectorize":
            term_entries = task.get("term_entries", [])
            self._batch_vectorize_sync(term_entries)
        
        elif task_type == "sync_vector_store":
            self._sync_vector_store_sync()
    
    def get_smart_recommendations(self, text: str, source_lang: str = "en", 
                                target_lang: str = "zh", domain: str = None) -> List[RecommendationResult]:
        """
        获取智能术语推荐
        
        Args:
            text: 输入文本
            source_lang: 源语言
            target_lang: 目标语言
            domain: 领域过滤
            
        Returns:
            推荐结果列表
        """
        recommendations = []
        
        # 1. 传统精确匹配
        if self.config.enable_traditional:
            exact_matches = self._get_exact_matches(text, source_lang, target_lang, domain)
            recommendations.extend(exact_matches)
        
        # 2. RAG向量相似度推荐
        if self.config.enable_rag and self.embedding_client and self.vector_store:
            vector_matches = self._get_vector_similarity_matches(
                text, source_lang, target_lang, domain
            )
            recommendations.extend(vector_matches)
        
        # 3. 模糊匹配（作为降级方案）
        if not recommendations or (self.config.enable_rag and not self.embedding_client):
            fuzzy_matches = self._get_fuzzy_matches(text, source_lang, target_lang, domain)
            recommendations.extend(fuzzy_matches)
        
        # 4. 合并、去重和排序
        final_recommendations = self._merge_and_rank_recommendations(recommendations)
        
        # 5. 限制返回数量
        return final_recommendations[:self.config.max_suggestions]
    
    def _get_exact_matches(self, text: str, source_lang: str, target_lang: str, 
                          domain: str = None) -> List[RecommendationResult]:
        """获取精确匹配结果"""
        recommendations = []
        
        # 查找匹配的术语
        relevant_terms = self.terminology_store.find_terms(
            source_lang=source_lang,
            target_lang=target_lang,
            domain=domain
        )
        
        matches = self.matcher.find_exact_matches(text, relevant_terms, source_lang, target_lang)
        
        for term, matched_text in matches:
            recommendations.append(RecommendationResult(
                source_term=matched_text,
                suggested_target=term.target_term,
                suggestion_type="exact_match",
                confidence=term.confidence,
                source_term_id=term.id,
                domain=term.domain,
                context=term.context
            ))
        
        return recommendations
    
    def _get_vector_similarity_matches(self, text: str, source_lang: str, target_lang: str,
                                     domain: str = None) -> List[RecommendationResult]:
        """获取向量相似度匹配结果"""
        recommendations = []
        
        if not self.embedding_client or not self.vector_store:
            return recommendations
        
        # 提取潜在术语
        potential_terms = self.matcher.extract_potential_terms(text, source_lang)
        
        for term in potential_terms:
            # 生成查询向量
            try:
                query_embedding = self.embedding_client.encode(term)
            except Exception as e:
                logger.warning(f"生成查询向量失败: {term}, 错误: {e}")
                continue
            
            # 向量搜索
            try:
                similar_terms = self.vector_store.search_similar(
                    query_embedding,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    domain=domain,
                    top_k=self.config.max_vector_results
                )
            except Exception as e:
                logger.warning(f"向量搜索失败: {e}")
                continue
            
            # 转换为推荐结果
            for result in similar_terms:
                similarity = result.get("similarity", 0.0)
                if similarity >= self.config.similarity_threshold:
                    recommendations.append(RecommendationResult(
                        source_term=term,
                        suggested_target=result["target_term"],
                        suggestion_type="vector_similarity",
                        confidence=similarity * self.config.hybrid_search_weights["vector"],
                        source_term_id=result["term_id"],
                        similarity_score=similarity,
                        domain=result["domain"],
                        context=result.get("context", "")
                    ))
        
        return recommendations
    
    def _get_fuzzy_matches(self, text: str, source_lang: str, target_lang: str,
                          domain: str = None) -> List[RecommendationResult]:
        """获取模糊匹配结果（降级方案）"""
        recommendations = []
        
        # 获取所有相关术语
        relevant_terms = self.terminology_store.find_terms(
            source_lang=source_lang,
            target_lang=target_lang,
            domain=domain
        )
        
        # 提取潜在术语
        potential_terms = self.matcher.extract_potential_terms(text, source_lang)
        
        # 简单的字符串包含匹配
        for potential_term in potential_terms:
            for term in relevant_terms:
                # 检查是否有部分匹配
                if (potential_term.lower() in term.source_term.lower() or 
                    term.source_term.lower() in potential_term.lower()):
                    
                    # 计算简单的相似度
                    similarity = self._calculate_string_similarity(potential_term, term.source_term)
                    
                    if similarity >= 0.5:  # 较低的阈值，因为是降级方案
                        recommendations.append(RecommendationResult(
                            source_term=potential_term,
                            suggested_target=term.target_term,
                            suggestion_type="fuzzy_match",
                            confidence=similarity * self.config.hybrid_search_weights["fuzzy"],
                            source_term_id=term.id,
                            domain=term.domain,
                            context=term.context
                        ))
        
        return recommendations
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度（简单的编辑距离算法）"""
        if not str1 or not str2:
            return 0.0
        
        # 简化的相似度计算
        len1, len2 = len(str1), len(str2)
        max_len = max(len1, len2)
        
        if max_len == 0:
            return 1.0
        
        # 计算公共字符比例
        common_chars = set(str1.lower()) & set(str2.lower())
        similarity = len(common_chars) / max_len
        
        return similarity
    
    def _merge_and_rank_recommendations(self, recommendations: List[RecommendationResult]) -> List[RecommendationResult]:
        """合并和排序推荐结果"""
        if not recommendations:
            return []
        
        # 按源术语分组
        grouped = {}
        for rec in recommendations:
            key = rec.source_term.lower()
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(rec)
        
        # 为每个源术语选择最佳推荐
        final_recommendations = []
        for key, recs in grouped.items():
            # 按置信度排序
            recs.sort(key=lambda x: x.confidence, reverse=True)
            
            # 选择最佳推荐
            best_rec = recs[0]
            
            # 如果有多种类型的推荐，可以合并信息
            if len(recs) > 1:
                # 查找是否有精确匹配
                exact_matches = [r for r in recs if r.suggestion_type == "exact_match"]
                if exact_matches:
                    best_rec = exact_matches[0]
                else:
                    # 合并向量相似度信息
                    vector_matches = [r for r in recs if r.suggestion_type == "vector_similarity"]
                    if vector_matches and best_rec.similarity_score is None:
                        best_rec.similarity_score = max(r.similarity_score for r in vector_matches)
            
            final_recommendations.append(best_rec)
        
        # 按置信度排序
        final_recommendations.sort(key=lambda x: x.confidence, reverse=True)
        
        return final_recommendations
    
    def vectorize_term_async(self, term_entry: TerminologyEntry):
        """异步向量化术语"""
        if not self.config.enable_rag:
            return
        
        task = {
            "type": "vectorize_term",
            "term_entry": term_entry
        }
        
        self._vectorization_queue.put(task)
        logger.debug(f"已添加向量化任务: {term_entry.source_term}")
    
    def batch_vectorize_async(self, term_entries: List[TerminologyEntry]):
        """异步批量向量化术语"""
        if not self.config.enable_rag:
            return
        
        task = {
            "type": "batch_vectorize",
            "term_entries": term_entries
        }
        
        self._vectorization_queue.put(task)
        logger.debug(f"已添加批量向量化任务: {len(term_entries)} 个术语")
    
    def sync_vector_store_async(self):
        """异步同步向量存储"""
        if not self.config.enable_rag:
            return
        
        task = {
            "type": "sync_vector_store"
        }
        
        self._vectorization_queue.put(task)
        logger.debug("已添加向量存储同步任务")
    
    def _vectorize_term_sync(self, term_entry: TerminologyEntry) -> bool:
        """同步向量化单个术语"""
        if not self.embedding_client or not self.vector_store:
            return False
        
        try:
            # 生成源术语的向量
            source_embedding = self.embedding_client.encode(term_entry.source_term)
            
            # 创建向量条目
            vector_entry = VectorEntry(
                id=str(uuid.uuid4()),
                term_id=term_entry.id,
                source_term=term_entry.source_term,
                target_term=term_entry.target_term,
                source_lang=term_entry.source_lang,
                target_lang=term_entry.target_lang,
                domain=term_entry.domain,
                embedding=source_embedding.tolist() if hasattr(source_embedding, 'tolist') else source_embedding,
                context=term_entry.context
            )
            
            # 添加到向量存储
            success = self.vector_store.add_entry(vector_entry)
            
            if success:
                logger.debug(f"术语向量化成功: {term_entry.source_term}")
            else:
                logger.warning(f"术语向量化失败: {term_entry.source_term}")
            
            return success
            
        except Exception as e:
            logger.error(f"术语向量化异常: {term_entry.source_term}, 错误: {e}")
            return False
    
    def _batch_vectorize_sync(self, term_entries: List[TerminologyEntry]) -> Dict[str, bool]:
        """同步批量向量化术语"""
        results = {}
        
        if not self.embedding_client or not self.vector_store:
            return {term.id: False for term in term_entries}
        
        # 分批处理
        batch_size = self.config.vector_batch_size
        for i in range(0, len(term_entries), batch_size):
            batch = term_entries[i:i + batch_size]
            
            # 批量生成向量
            try:
                source_terms = [term.source_term for term in batch]
                embeddings = self.embedding_client.encode(source_terms)
                
                # 创建向量条目
                vector_entries = []
                for j, term in enumerate(batch):
                    embedding = embeddings[j]
                    vector_entry = VectorEntry(
                        id=str(uuid.uuid4()),
                        term_id=term.id,
                        source_term=term.source_term,
                        target_term=term.target_term,
                        source_lang=term.source_lang,
                        target_lang=term.target_lang,
                        domain=term.domain,
                        embedding=embedding.tolist() if hasattr(embedding, 'tolist') else embedding,
                        context=term.context
                    )
                    vector_entries.append(vector_entry)
                
                # 批量添加到向量存储
                for entry in vector_entries:
                    success = self.vector_store.add_entry(entry)
                    results[entry.term_id] = success
                    
                    if success:
                        logger.debug(f"术语向量化成功: {entry.source_term}")
                    else:
                        logger.warning(f"术语向量化失败: {entry.source_term}")
                
            except Exception as e:
                logger.error(f"批量向量化异常: {e}")
                for term in batch:
                    results[term.id] = False
        
        return results
    
    def _sync_vector_store_sync(self) -> Dict[str, int]:
        """同步向量存储与传统术语库"""
        if not self.vector_store:
            return {"error": "向量存储不可用"}
        
        try:
            # 获取所有术语
            all_terms = list(self.terminology_store.terminology.values())
            
            # 获取所有向量条目
            vector_entries = self.vector_store.get_all_entries()
            vector_term_ids = {entry.term_id for entry in vector_entries}
            
            # 找出需要向量化的术语
            terms_to_vectorize = [
                term for term in all_terms 
                if term.id not in vector_term_ids
            ]
            
            # 找出需要清理的向量条目
            all_term_ids = {term.id for term in all_terms}
            invalid_vector_ids = [
                entry.id for entry in vector_entries 
                if entry.term_id not in all_term_ids
            ]
            
            # 批量向量化新术语
            vectorize_results = {}
            if terms_to_vectorize:
                vectorize_results = self._batch_vectorize_sync(terms_to_vectorize)
            
            # 清理无效向量条目
            cleanup_count = 0
            for vector_id in invalid_vector_ids:
                if self.vector_store.delete_entry(vector_id):
                    cleanup_count += 1
            
            sync_result = {
                "total_terms": len(all_terms),
                "vectorized_terms": len(vector_entries) - len(invalid_vector_ids),
                "terms_to_vectorize": len(terms_to_vectorize),
                "successfully_vectorized": sum(1 for success in vectorize_results.values() if success),
                "invalid_vectors_cleaned": cleanup_count
            }
            
            logger.info(f"向量存储同步完成: {sync_result}")
            return sync_result
            
        except Exception as e:
            logger.error(f"向量存储同步失败: {e}")
            return {"error": str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取RAG推荐器统计信息"""
        stats = {
            "rag_enabled": self.config.enable_rag,
            "embedding_client_available": self.embedding_client is not None and self.embedding_client.is_available(),
            "vector_store_available": self.vector_store is not None,
            "pending_vectorization_tasks": self._vectorization_queue.qsize(),
            "vectorization_worker_active": self._vectorization_worker and self._vectorization_worker.is_alive()
        }
        
        if self.vector_store:
            vector_stats = self.vector_store.get_statistics()
            stats.update(vector_stats)
        
        return stats
    
    def shutdown(self):
        """关闭RAG推荐器"""
        logger.info("正在关闭RAG推荐器...")
        
        # 停止向量化工作线程
        self._stop_vectorization_worker()
        
        logger.info("RAG推荐器已关闭")