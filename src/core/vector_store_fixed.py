"""
UnityLangPX 向量存储模块（修复版）

基于SQLite-VSS实现术语向量存储和检索。
修复了删除操作的返回值逻辑和数据库初始化问题。
"""

import sqlite3
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class VectorEntry:
    """向量条目数据模型"""
    id: str
    term_id: str
    source_term: str
    target_term: str
    source_lang: str
    target_lang: str
    domain: str
    embedding: List[float]
    context: str = ""
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "term_id": self.term_id,
            "source_term": self.source_term,
            "target_term": self.target_term,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "domain": self.domain,
            "embedding": json.dumps(self.embedding),
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VectorEntry':
        """从字典创建"""
        if "embedding" in data and isinstance(data["embedding"], str):
            data["embedding"] = json.loads(data["embedding"])
        return cls(**data)


class SQLiteVectorStoreFixed:
    """基于SQLite-VSS的向量存储（修复版）"""
    
    def __init__(self, db_path: str = "data/terminology_vectors.db", 
                 embedding_dim: int = 1024):
        """
        初始化向量存储
        
        Args:
            db_path: 数据库路径
            embedding_dim: 嵌入向量维度
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"向量存储初始化完成: {self.db_path}")
    
    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            # 启用VSS扩展
            conn.enable_load_extension(True)
            
            try:
                # 加载VSS扩展（假设已安装）
                conn.load_extension("vss")
                logger.debug("VSS扩展加载成功")
            except sqlite3.OperationalError as e:
                logger.warning(f"VSS扩展加载失败: {e}")
                logger.info("将使用标准SQLite进行向量存储")
            
            # 创建术语表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS terminology_vectors (
                    id TEXT PRIMARY KEY,
                    term_id TEXT NOT NULL,
                    source_term TEXT NOT NULL,
                    target_term TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 如果VSS可用，创建虚拟表
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vss_terminology USING vss(
                        embedding({embedding_dim})
                    )
                """.format(embedding_dim=self.embedding_dim))
                logger.debug("VSS虚拟表创建成功")
            except sqlite3.OperationalError as e:
                logger.warning(f"VSS虚拟表创建失败: {e}")
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_term_id ON terminology_vectors(term_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_term ON terminology_vectors(source_term)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_lang_pair ON terminology_vectors(source_lang, target_lang)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_domain ON terminology_vectors(domain)
            """)
            
            conn.commit()
    
    def add_entry(self, entry: VectorEntry) -> bool:
        """
        添加向量条目
        
        Args:
            entry: 向量条目
            
        Returns:
            是否添加成功
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 启用VSS扩展
                conn.enable_load_extension(True)
                try:
                    conn.load_extension("vss")
                except sqlite3.OperationalError:
                    pass
                
                # 插入到主表
                conn.execute("""
                    INSERT OR REPLACE INTO terminology_vectors
                    (id, term_id, source_term, target_term, source_lang, target_lang, 
                     domain, embedding, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.id, entry.term_id, entry.source_term, entry.target_term,
                    entry.source_lang, entry.target_lang, entry.domain,
                    json.dumps(entry.embedding), entry.context
                ))
                
                # 如果VSS可用，插入到虚拟表
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO vss_terminology(rowid, embedding)
                        VALUES (
                            (SELECT rowid FROM terminology_vectors WHERE id = ?),
                            ?
                        )
                    """, (entry.id, json.dumps(entry.embedding)))
                except sqlite3.OperationalError:
                    pass
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"添加向量条目失败: {e}")
            return False
    
    def search_similar(self, query_embedding: List[float], 
                      source_lang: str = None, target_lang: str = None,
                      domain: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_embedding: 查询向量
            source_lang: 源语言过滤
            target_lang: 目标语言过滤
            domain: 领域过滤
            top_k: 返回结果数量
            
        Returns:
            相似结果列表
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 启用VSS扩展
                conn.enable_load_extension(True)
                try:
                    conn.load_extension("vss")
                except sqlite3.OperationalError:
                    return self._fallback_search(query_embedding, source_lang, target_lang, domain, top_k)
                
                # 构建查询条件
                conditions = []
                params = []
                
                if source_lang:
                    conditions.append("source_lang = ?")
                    params.append(source_lang)
                
                if target_lang:
                    conditions.append("target_lang = ?")
                    params.append(target_lang)
                
                if domain:
                    conditions.append("domain = ?")
                    params.append(domain)
                
                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)
                
                # 使用VSS进行相似度搜索
                query = f"""
                    SELECT tv.id, tv.term_id, tv.source_term, tv.target_term,
                           tv.source_lang, tv.target_lang, tv.domain, tv.context,
                           distance
                    FROM vss_terminology(vs, ?)
                    JOIN terminology_vectors tv ON tv.rowid = vs.rowid
                    {where_clause}
                    ORDER BY distance
                    LIMIT ?
                """
                
                params = [json.dumps(query_embedding)] + params + [top_k]
                
                cursor = conn.execute(query, params)
                results = []
                
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "term_id": row[1],
                        "source_term": row[2],
                        "target_term": row[3],
                        "source_lang": row[4],
                        "target_lang": row[5],
                        "domain": row[6],
                        "context": row[7],
                        "similarity": 1.0 - float(row[8]),  # 转换距离为相似度
                        "distance": float(row[8])
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return self._fallback_search(query_embedding, source_lang, target_lang, domain, top_k)
    
    def _fallback_search(self, query_embedding: List[float], 
                        source_lang: str = None, target_lang: str = None,
                        domain: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        降级搜索方法（当VSS不可用时使用余弦相似度）
        
        Args:
            query_embedding: 查询向量
            source_lang: 源语言过滤
            target_lang: 目标语言过滤
            domain: 领域过滤
            top_k: 返回结果数量
            
        Returns:
            相似结果列表
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 构建查询条件
                conditions = []
                params = []
                
                if source_lang:
                    conditions.append("source_lang = ?")
                    params.append(source_lang)
                
                if target_lang:
                    conditions.append("target_lang = ?")
                    params.append(target_lang)
                
                if domain:
                    conditions.append("domain = ?")
                    params.append(domain)
                
                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)
                
                # 获取所有候选向量
                query = f"""
                    SELECT id, term_id, source_term, target_term, source_lang, 
                           target_lang, domain, context, embedding
                    FROM terminology_vectors
                    {where_clause}
                """
                
                cursor = conn.execute(query, params)
                candidates = []
                
                for row in cursor.fetchall():
                    embedding = json.loads(row[8])
                    similarity = self._cosine_similarity(query_embedding, embedding)
                    
                    candidates.append({
                        "id": row[0],
                        "term_id": row[1],
                        "source_term": row[2],
                        "target_term": row[3],
                        "source_lang": row[4],
                        "target_lang": row[5],
                        "domain": row[6],
                        "context": row[7],
                        "similarity": similarity,
                        "distance": 1.0 - similarity
                    })
                
                # 按相似度排序
                candidates.sort(key=lambda x: x["similarity"], reverse=True)
                
                return candidates[:top_k]
                
        except Exception as e:
            logger.error(f"降级搜索失败: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_entry(self, entry_id: str) -> Optional[VectorEntry]:
        """获取向量条目"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT id, term_id, source_term, target_term, source_lang,
                           target_lang, domain, embedding, context
                    FROM terminology_vectors
                    WHERE id = ?
                """, (entry_id,))
                
                row = cursor.fetchone()
                if row:
                    return VectorEntry(
                        id=row[0],
                        term_id=row[1],
                        source_term=row[2],
                        target_term=row[3],
                        source_lang=row[4],
                        target_lang=row[5],
                        domain=row[6],
                        embedding=json.loads(row[7]),
                        context=row[8] or ""
                    )
                
        except Exception as e:
            logger.error(f"获取向量条目失败: {e}")
        
        return None
    
    def update_entry(self, entry: VectorEntry) -> bool:
        """更新向量条目"""
        return self.add_entry(entry)  # 使用INSERT OR REPLACE
    
    def delete_entry(self, entry_id: str) -> bool:
        """
        删除向量条目（修复版）
        
        Args:
            entry_id: 条目ID
            
        Returns:
            是否删除成功（修复：只有当条目存在且删除成功时才返回True）
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 启用VSS扩展
                conn.enable_load_extension(True)
                try:
                    conn.load_extension("vss")
                except sqlite3.OperationalError:
                    pass
                
                # 修复：先检查条目是否存在
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM terminology_vectors WHERE id = ?
                """, (entry_id,))
                
                count = cursor.fetchone()[0]
                if count == 0:
                    # 条目不存在，返回False
                    return False
                
                # 从主表删除
                cursor = conn.execute("""
                    DELETE FROM terminology_vectors WHERE id = ?
                """, (entry_id,))
                
                # 检查是否真的删除了条目
                if cursor.rowcount == 0:
                    return False
                
                # 从VSS虚拟表删除
                try:
                    conn.execute("""
                        DELETE FROM vss_terminology 
                        WHERE rowid = (SELECT rowid FROM terminology_vectors WHERE id = ?)
                    """, (entry_id,))
                except sqlite3.OperationalError:
                    pass
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"删除向量条目失败: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        COUNT(DISTINCT term_id) as unique_terms,
                        COUNT(DISTINCT source_lang || '-' || target_lang) as language_pairs,
                        COUNT(DISTINCT domain) as domains
                    FROM terminology_vectors
                """)
                
                row = cursor.fetchone()
                
                return {
                    "total_entries": row[0],
                    "unique_terms": row[1],
                    "language_pairs": row[2],
                    "domains": row[3],
                    "embedding_dimension": self.embedding_dim
                }
                
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def clear_all(self) -> bool:
        """清空所有数据"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 启用VSS扩展
                conn.enable_load_extension(True)
                try:
                    conn.load_extension("vss")
                except sqlite3.OperationalError:
                    pass
                
                # 清空主表
                conn.execute("DELETE FROM terminology_vectors")
                
                # 清空VSS虚拟表
                try:
                    conn.execute("DELETE FROM vss_terminology")
                except sqlite3.OperationalError:
                    pass
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"清空向量存储失败: {e}")
            return False
    
    def optimize(self) -> bool:
        """优化数据库"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"优化向量存储失败: {e}")
            return False
    
    def get_all_entries(self) -> List[VectorEntry]:
        """
        获取所有向量条目
        
        Returns:
            所有向量条目列表
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT id, term_id, source_term, target_term, source_lang,
                           target_lang, domain, embedding, context
                    FROM terminology_vectors
                    ORDER BY created_at DESC
                """)
                
                entries = []
                for row in cursor.fetchall():
                    entry = VectorEntry(
                        id=row[0],
                        term_id=row[1],
                        source_term=row[2],
                        target_term=row[3],
                        source_lang=row[4],
                        target_lang=row[5],
                        domain=row[6],
                        embedding=json.loads(row[7]),
                        context=row[8] or ""
                    )
                    entries.append(entry)
                
                return entries
                
        except Exception as e:
            logger.error(f"获取所有向量条目失败: {e}")
            return []
    
    def get_entries_by_term_ids(self, term_ids: List[str]) -> List[VectorEntry]:
        """
        根据术语ID获取向量条目
        
        Args:
            term_ids: 术语ID列表
            
        Returns:
            向量条目列表
        """
        if not term_ids:
            return []
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                placeholders = ','.join(['?' for _ in term_ids])
                cursor = conn.execute(f"""
                    SELECT id, term_id, source_term, target_term, source_lang,
                           target_lang, domain, embedding, context
                    FROM terminology_vectors
                    WHERE term_id IN ({placeholders})
                    ORDER BY created_at DESC
                """, term_ids)
                
                entries = []
                for row in cursor.fetchall():
                    entry = VectorEntry(
                        id=row[0],
                        term_id=row[1],
                        source_term=row[2],
                        target_term=row[3],
                        source_lang=row[4],
                        target_lang=row[5],
                        domain=row[6],
                        embedding=json.loads(row[7]),
                        context=row[8] or ""
                    )
                    entries.append(entry)
                
                return entries
                
        except Exception as e:
            logger.error(f"根据术语ID获取向量条目失败: {e}")
            return []
    
    def batch_add_entries(self, entries: List[VectorEntry]) -> Dict[str, bool]:
        """
        批量添加向量条目
        
        Args:
            entries: 向量条目列表
            
        Returns:
            添加结果字典 {term_id: success}
        """
        results = {}
        
        if not entries:
            return results
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 启用VSS扩展
                conn.enable_load_extension(True)
                try:
                    conn.load_extension("vss")
                except sqlite3.OperationalError:
                    pass
                
                # 开始事务
                conn.execute("BEGIN TRANSACTION")
                
                try:
                    for entry in entries:
                        # 插入到主表
                        conn.execute("""
                            INSERT OR REPLACE INTO terminology_vectors
                            (id, term_id, source_term, target_term, source_lang, target_lang,
                             domain, embedding, context)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            entry.id, entry.term_id, entry.source_term, entry.target_term,
                            entry.source_lang, entry.target_lang, entry.domain,
                            json.dumps(entry.embedding), entry.context
                        ))
                        
                        # 如果VSS可用，插入到虚拟表
                        try:
                            conn.execute("""
                                INSERT OR REPLACE INTO vss_terminology(rowid, embedding)
                                VALUES (
                                    (SELECT rowid FROM terminology_vectors WHERE id = ?),
                                    ?
                                )
                            """, (entry.id, json.dumps(entry.embedding)))
                        except sqlite3.OperationalError:
                            pass
                        
                        results[entry.term_id] = True
                    
                    # 提交事务
                    conn.commit()
                    logger.debug(f"批量添加 {len(entries)} 个向量条目成功")
                    
                except Exception as e:
                    # 回滚事务
                    conn.rollback()
                    logger.error(f"批量添加向量条目失败，已回滚: {e}")
                    
                    # 标记所有为失败
                    for entry in entries:
                        results[entry.term_id] = False
                
        except Exception as e:
            logger.error(f"批量添加向量条目异常: {e}")
            for entry in entries:
                results[entry.term_id] = False
        
        return results
    
    def get_statistics_by_domain(self) -> Dict[str, Dict[str, Any]]:
        """
        按领域获取统计信息
        
        Returns:
            领域统计信息字典
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT
                        domain,
                        COUNT(*) as total_entries,
                        COUNT(DISTINCT term_id) as unique_terms,
                        COUNT(DISTINCT source_lang || '-' || target_lang) as language_pairs
                    FROM terminology_vectors
                    GROUP BY domain
                    ORDER BY total_entries DESC
                """)
                
                stats = {}
                for row in cursor.fetchall():
                    domain = row[0] or "未分类"
                    stats[domain] = {
                        "total_entries": row[1],
                        "unique_terms": row[2],
                        "language_pairs": row[3]
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"获取领域统计信息失败: {e}")
            return {}
    
    def get_statistics_by_language_pair(self) -> Dict[str, Dict[str, Any]]:
        """
        按语言对获取统计信息
        
        Returns:
            语言对统计信息字典
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT
                        source_lang || '-' || target_lang as lang_pair,
                        source_lang,
                        target_lang,
                        COUNT(*) as total_entries,
                        COUNT(DISTINCT term_id) as unique_terms,
                        COUNT(DISTINCT domain) as domains
                    FROM terminology_vectors
                    GROUP BY source_lang, target_lang
                    ORDER BY total_entries DESC
                """)
                
                stats = {}
                for row in cursor.fetchall():
                    lang_pair = row[0]
                    stats[lang_pair] = {
                        "source_lang": row[1],
                        "target_lang": row[2],
                        "total_entries": row[3],
                        "unique_terms": row[4],
                        "domains": row[5]
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"获取语言对统计信息失败: {e}")
            return {}