"""
UnityLangPX 增强功能缓存模块

实现术语增强功能的专用缓存机制，包括上下文感知翻译缓存、
模糊匹配结果缓存、消歧结果缓存等，提高性能和减少大模型调用。
"""

import time
import json
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import OrderedDict
from enum import Enum

from .logger import get_logger

logger = get_logger(__name__)


class CacheType(Enum):
    """缓存类型枚举"""
    CONTEXT_TRANSLATION = "context_translation"  # 上下文感知翻译
    FUZZY_MATCHING = "fuzzy_matching"            # 模糊匹配
    DISAMBIGUATION = "disambiguation"            # 术语消歧
    COMPLEX_SCENARIO = "complex_scenario"        # 复杂场景处理
    DECISION_RESULT = "decision_result"          # 决策结果


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: float  # 生存时间(秒)
    size: int  # 缓存大小(字节)
    
    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > self.ttl
    
    @property
    def age(self) -> float:
        """获取缓存年龄(秒)"""
        return time.time() - self.created_at
    
    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheStatistics:
    """缓存统计信息"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0
        self.total_requests = 0
        self._lock = threading.Lock()
    
    def record_hit(self):
        """记录缓存命中"""
        with self._lock:
            self.hits += 1
            self.total_requests += 1
    
    def record_miss(self):
        """记录缓存未命中"""
        with self._lock:
            self.misses += 1
            self.total_requests += 1
    
    def record_eviction(self):
        """记录缓存淘汰"""
        with self._lock:
            self.evictions += 1
    
    def record_expiration(self):
        """记录缓存过期"""
        with self._lock:
            self.expirations += 1
    
    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        with self._lock:
            return {
                'hits': self.hits,
                'misses': self.misses,
                'evictions': self.evictions,
                'expirations': self.expirations,
                'total_requests': self.total_requests,
                'hit_rate': self.hit_rate
            }


class EnhancementCache:
    """增强功能缓存"""
    
    def __init__(self, cache_dir: Optional[Path] = None, 
                 max_memory_size: int = 100 * 1024 * 1024,  # 100MB
                 max_entries: int = 10000,
                 default_ttl: float = 3600):  # 1小时
        """
        初始化增强功能缓存
        
        Args:
            cache_dir: 缓存目录
            max_memory_size: 最大内存缓存大小(字节)
            max_entries: 最大缓存条目数
            default_ttl: 默认TTL(秒)
        """
        self.cache_dir = cache_dir or Path(".enhancement_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        self.max_memory_size = max_memory_size
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        
        # 内存缓存 - 使用OrderedDict实现LRU
        self._memory_cache: Dict[CacheType, OrderedDict[str, CacheEntry]] = {
            cache_type: OrderedDict() for cache_type in CacheType
        }
        
        # 当前内存使用量
        self._current_memory_size = 0
        
        # 统计信息
        self._statistics: Dict[CacheType, CacheStatistics] = {
            cache_type: CacheStatistics() for cache_type in CacheType
        }
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 加载持久化缓存
        self._load_persistent_cache()
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"增强功能缓存初始化完成，最大内存: {max_memory_size // 1024 // 1024}MB")
    
    def get(self, cache_type: CacheType, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            cache_type: 缓存类型
            key: 缓存键
            
        Returns:
            缓存值或None
        """
        with self._lock:
            cache = self._memory_cache[cache_type]
            
            if key not in cache:
                self._statistics[cache_type].record_miss()
                return None
            
            entry = cache[key]
            
            # 检查是否过期
            if entry.is_expired:
                del cache[key]
                self._current_memory_size -= entry.size
                self._statistics[cache_type].record_expiration()
                self._statistics[cache_type].record_miss()
                return None
            
            # 更新访问信息
            entry.touch()
            
            # 移到末尾(LRU)
            cache.move_to_end(key)
            
            self._statistics[cache_type].record_hit()
            logger.debug(f"缓存命中: {cache_type.value}, 键: {key}")
            
            return entry.value
    
    def set(self, cache_type: CacheType, key: str, value: Any, 
            ttl: Optional[float] = None) -> bool:
        """
        设置缓存值
        
        Args:
            cache_type: 缓存类型
            key: 缓存键
            value: 缓存值
            ttl: 生存时间(秒)，None表示使用默认TTL
            
        Returns:
            是否设置成功
        """
        try:
            # 序列化值以计算大小
            serialized_value = self._serialize_value(value)
            value_size = len(serialized_value.encode('utf-8'))
            
            # 检查值是否太大
            if value_size > self.max_memory_size // 10:  # 单个值不超过总缓存的10%
                logger.warning(f"缓存值太大，跳过缓存: {value_size} 字节")
                return False
            
            with self._lock:
                cache = self._memory_cache[cache_type]
                current_time = time.time()
                
                # 如果键已存在，更新大小
                if key in cache:
                    old_entry = cache[key]
                    self._current_memory_size -= old_entry.size
                
                # 检查是否需要清理空间
                while (self._current_memory_size + value_size > self.max_memory_size or
                       len(cache) >= self.max_entries):
                    if not self._evict_lru(cache_type):
                        break
                
                # 创建缓存条目
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=current_time,
                    last_accessed=current_time,
                    access_count=1,
                    ttl=ttl or self.default_ttl,
                    size=value_size
                )
                
                # 添加到缓存
                cache[key] = entry
                cache.move_to_end(key)
                self._current_memory_size += value_size
                
                logger.debug(f"缓存设置: {cache_type.value}, 键: {key}, 大小: {value_size} 字节")
                
                return True
                
        except Exception as e:
            logger.error(f"设置缓存失败: {str(e)}")
            return False
    
    def delete(self, cache_type: CacheType, key: str) -> bool:
        """
        删除缓存条目
        
        Args:
            cache_type: 缓存类型
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        with self._lock:
            cache = self._memory_cache[cache_type]
            
            if key not in cache:
                return False
            
            entry = cache[key]
            del cache[key]
            self._current_memory_size -= entry.size
            
            logger.debug(f"缓存删除: {cache_type.value}, 键: {key}")
            return True
    
    def clear(self, cache_type: Optional[CacheType] = None) -> int:
        """
        清空缓存
        
        Args:
            cache_type: 缓存类型，None表示清空所有
            
        Returns:
            清空的条目数
        """
        with self._lock:
            cleared_count = 0
            
            if cache_type is None:
                # 清空所有缓存
                for cache in self._memory_cache.values():
                    cleared_count += len(cache)
                    cache.clear()
                self._current_memory_size = 0
            else:
                # 清空指定类型缓存
                cache = self._memory_cache[cache_type]
                cleared_count = len(cache)
                cache.clear
                
                # 重新计算内存使用量
                self._recalculate_memory_size()
            
            logger.info(f"缓存清空: {cache_type.value if cache_type else '所有'}, "
                       f"条目数: {cleared_count}")
            
            return cleared_count
    
    def get_statistics(self, cache_type: Optional[CacheType] = None) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Args:
            cache_type: 缓存类型，None表示获取所有
            
        Returns:
            统计信息字典
        """
        with self._lock:
            stats = {
                'memory_usage': {
                    'current_size': self._current_memory_size,
                    'max_size': self.max_memory_size,
                    'usage_percentage': self._current_memory_size / self.max_memory_size * 100
                },
                'cache_types': {}
            }
            
            types_to_process = [cache_type] if cache_type else list(CacheType)
            
            for ct in types_to_process:
                cache = self._memory_cache[ct]
                type_stats = self._statistics[ct].to_dict()
                type_stats.update({
                    'entry_count': len(cache),
                    'total_size': sum(entry.size for entry in cache.values()),
                    'oldest_entry_age': min((entry.age for entry in cache.values()), default=0),
                    'newest_entry_age': max((entry.age for entry in cache.values()), default=0)
                })
                stats['cache_types'][ct.value] = type_stats
            
            return stats
    
    def save_to_disk(self, cache_type: Optional[CacheType] = None) -> bool:
        """
        保存缓存到磁盘
        
        Args:
            cache_type: 缓存类型，None表示保存所有
            
        Returns:
            是否保存成功
        """
        try:
            with self._lock:
                types_to_process = [cache_type] if cache_type else list(CacheType)
                saved_count = 0
                
                for ct in types_to_process:
                    cache_file = self.cache_dir / f"{ct.value}.json"
                    cache = self._memory_cache[ct]
                    
                    # 准备保存数据
                    save_data = {}
                    for key, entry in cache.items():
                        # 只保存未过期的条目
                        if not entry.is_expired:
                            save_data[key] = {
                                'value': entry.value,
                                'created_at': entry.created_at,
                                'last_accessed': entry.last_accessed,
                                'access_count': entry.access_count,
                                'ttl': entry.ttl
                            }
                    
                    # 保存到文件
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(save_data, f, ensure_ascii=False, indent=2)
                    
                    saved_count += len(save_data)
                
                logger.info(f"缓存保存到磁盘: {saved_count} 个条目")
                return True
                
        except Exception as e:
            logger.error(f"保存缓存到磁盘失败: {str(e)}")
            return False
    
    def load_from_disk(self, cache_type: Optional[CacheType] = None) -> bool:
        """
        从磁盘加载缓存
        
        Args:
            cache_type: 缓存类型，None表示加载所有
            
        Returns:
            是否加载成功
        """
        try:
            with self._lock:
                types_to_process = [cache_type] if cache_type else list(CacheType)
                loaded_count = 0
                
                for ct in types_to_process:
                    cache_file = self.cache_dir / f"{ct.value}.json"
                    
                    if not cache_file.exists():
                        continue
                    
                    # 加载数据
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        save_data = json.load(f)
                    
                    cache = self._memory_cache[ct]
                    current_time = time.time()
                    
                    for key, data in save_data.items():
                        # 检查是否过期
                        created_at = data['created_at']
                        ttl = data['ttl']
                        
                        if current_time - created_at > ttl:
                            continue
                        
                        # 计算值大小
                        value = data['value']
                        serialized_value = self._serialize_value(value)
                        value_size = len(serialized_value.encode('utf-8'))
                        
                        # 检查内存限制
                        if (self._current_memory_size + value_size > self.max_memory_size or
                            len(cache) >= self.max_entries):
                            break
                        
                        # 创建缓存条目
                        entry = CacheEntry(
                            key=key,
                            value=value,
                            created_at=created_at,
                            last_accessed=data['last_accessed'],
                            access_count=data['access_count'],
                            ttl=ttl,
                            size=value_size
                        )
                        
                        cache[key] = entry
                        self._current_memory_size += value_size
                        loaded_count += 1
                
                logger.info(f"从磁盘加载缓存: {loaded_count} 个条目")
                return True
                
        except Exception as e:
            logger.error(f"从磁盘加载缓存失败: {str(e)}")
            return False
    
    # 私有方法
    
    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            # 如果无法JSON序列化，转换为字符串
            return str(value)
    
    def _evict_lru(self, cache_type: CacheType) -> bool:
        """淘汰最少使用的缓存条目"""
        cache = self._memory_cache[cache_type]
        
        if not cache:
            return False
        
        # 获取最旧的条目
        lru_key, lru_entry = next(iter(cache.items()))
        
        # 删除条目
        del cache[lru_key]
        self._current_memory_size -= lru_entry.size
        self._statistics[cache_type].record_eviction()
        
        logger.debug(f"LRU淘汰: {cache_type.value}, 键: {lru_key}")
        return True
    
    def _recalculate_memory_size(self):
        """重新计算内存使用量"""
        self._current_memory_size = sum(
            sum(entry.size for entry in cache.values())
            for cache in self._memory_cache.values()
        )
    
    def _load_persistent_cache(self):
        """加载持久化缓存"""
        try:
            self.load_from_disk()
        except Exception as e:
            logger.error(f"加载持久化缓存失败: {str(e)}")
    
    def _cleanup_worker(self):
        """清理工作线程"""
        while True:
            try:
                # 每5分钟执行一次清理
                time.sleep(300)
                self._cleanup_expired_entries()
                
                # 每30分钟保存一次到磁盘
                if int(time.time()) % 1800 < 300:
                    self.save_to_disk()
                    
            except Exception as e:
                logger.error(f"清理工作线程错误: {str(e)}")
    
    def _cleanup_expired_entries(self):
        """清理过期条目"""
        with self._lock:
            current_time = time.time()
            expired_count = 0
            
            for cache_type, cache in self._memory_cache.items():
                expired_keys = [
                    key for key, entry in cache.items()
                    if current_time - entry.created_at > entry.ttl
                ]
                
                for key in expired_keys:
                    entry = cache[key]
                    del cache[key]
                    self._current_memory_size -= entry.size
                    self._statistics[cache_type].record_expiration()
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"清理过期缓存条目: {expired_count} 个")


class CacheManager:
    """缓存管理器，提供全局缓存访问接口"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, cache_dir: Optional[Path] = None, **kwargs):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            **kwargs: 其他缓存参数
        """
        if hasattr(self, '_initialized'):
            return
        
        self._cache = EnhancementCache(cache_dir, **kwargs)
        self._initialized = True
        logger.info("缓存管理器初始化完成")
    
    def get_cache(self) -> EnhancementCache:
        """获取缓存实例"""
        return self._cache
    
    def get(self, cache_type: CacheType, key: str) -> Optional[Any]:
        """获取缓存值"""
        return self._cache.get(cache_type, key)
    
    def set(self, cache_type: CacheType, key: str, value: Any, 
            ttl: Optional[float] = None) -> bool:
        """设置缓存值"""
        return self._cache.set(cache_type, key, value, ttl)
    
    def delete(self, cache_type: CacheType, key: str) -> bool:
        """删除缓存条目"""
        return self._cache.delete(cache_type, key)
    
    def clear(self, cache_type: Optional[CacheType] = None) -> int:
        """清空缓存"""
        return self._cache.clear(cache_type)
    
    def get_statistics(self, cache_type: Optional[CacheType] = None) -> Dict[str, Any]:
        """获取统计信息"""
        return self._cache.get_statistics(cache_type)
    
    def save_to_disk(self, cache_type: Optional[CacheType] = None) -> bool:
        """保存到磁盘"""
        return self._cache.save_to_disk(cache_type)
    
    def load_from_disk(self, cache_type: Optional[CacheType] = None) -> bool:
        """从磁盘加载"""
        return self._cache.load_from_disk(cache_type)


# 便捷函数
def get_cache_manager(cache_dir: Optional[Path] = None, **kwargs) -> CacheManager:
    """获取缓存管理器实例"""
    return CacheManager(cache_dir, **kwargs)


def cache_context_translation(key: str, value: Any, ttl: Optional[float] = None) -> bool:
    """缓存上下文感知翻译结果"""
    manager = get_cache_manager()
    return manager.set(CacheType.CONTEXT_TRANSLATION, key, value, ttl)


def get_cached_context_translation(key: str) -> Optional[Any]:
    """获取缓存的上下文感知翻译结果"""
    manager = get_cache_manager()
    return manager.get(CacheType.CONTEXT_TRANSLATION, key)


def cache_fuzzy_matching(key: str, value: Any, ttl: Optional[float] = None) -> bool:
    """缓存模糊匹配结果"""
    manager = get_cache_manager()
    return manager.set(CacheType.FUZZY_MATCHING, key, value, ttl)


def get_cached_fuzzy_matching(key: str) -> Optional[Any]:
    """获取缓存的模糊匹配结果"""
    manager = get_cache_manager()
    return manager.get(CacheType.FUZZY_MATCHING, key)


def cache_disambiguation(key: str, value: Any, ttl: Optional[float] = None) -> bool:
    """缓存术语消歧结果"""
    manager = get_cache_manager()
    return manager.set(CacheType.DISAMBIGUATION, key, value, ttl)


def get_cached_disambiguation(key: str) -> Optional[Any]:
    """获取缓存的术语消歧结果"""
    manager = get_cache_manager()
    return manager.get(CacheType.DISAMBIGUATION, key)


def cache_decision_result(key: str, value: Any, ttl: Optional[float] = None) -> bool:
    """缓存决策结果"""
    manager = get_cache_manager()
    return manager.set(CacheType.DECISION_RESULT, key, value, ttl)


def get_cached_decision_result(key: str) -> Optional[Any]:
    """获取缓存的决策结果"""
    manager = get_cache_manager()
    return manager.get(CacheType.DECISION_RESULT, key)