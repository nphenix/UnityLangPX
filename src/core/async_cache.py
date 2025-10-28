"""
UnityLangPX 异步缓存模块

实现高性能的多级异步缓存系统，支持L1（内存）、L2（SQLite）、L3（文件）三级缓存。
"""

import asyncio
import sqlite3
import json
import pickle
import time
import hashlib
from pathlib import Path
from typing import Any, Optional, Dict, List, Union
from dataclasses import dataclass, asdict
from collections import OrderedDict
import threading
import weakref

from .logger import get_logger
from .exceptions import CacheError
from ..config.manager import get_config_manager

logger = get_logger(__name__)


class LRUCache:
    """线程安全的LRU缓存"""
    
    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                value = self.cache.pop(key)
                self.cache[key] = value
                self.hits += 1
                return value
            else:
                self.misses += 1
                return None
    
    def put(self, key: str, value: Any):
        with self.lock:
            if key in self.cache:
                # 更新现有项
                self.cache.pop(key)
            elif len(self.cache) >= self.maxsize:
                # 移除最久未使用的项
                self.cache.popitem(last=False)
            
            self.cache[key] = value
    
    def remove(self, key: str) -> bool:
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self):
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def size(self) -> int:
        with self.lock:
            return len(self.cache)
    
    def get_hit_rate(self) -> float:
        with self.lock:
            total = self.hits + self.misses
            return self.hits / total if total > 0 else 0.0


class AsyncMultiLevelCache:
    """异步多级缓存系统"""
    
    def __init__(self, config=None):
        # 如果没有提供配置，从统一配置系统加载
        if config is None:
            try:
                config_manager = get_config_manager()
                performance_config = config_manager.get_performance_config()
                config = performance_config.async_cache
            except Exception as e:
                logger.warning(f"无法加载性能配置，使用默认值: {str(e)}")
                # 使用默认配置
                from ..config.performance_models import AsyncCacheConfig
                config = AsyncCacheConfig()
        
        self.config = config
        
        # L1缓存：内存LRU缓存
        self.l1_cache = LRUCache(config.l1_max_size)
        
        # L2缓存：SQLite数据库
        self.l2_conn = None
        self.l2_lock = threading.RLock()
        
        # L3缓存：文件系统
        self.l3_dir = Path(config.l3_dir)
        self.l3_lock = threading.RLock()
        
        # 批量操作队列
        self.batch_queue = asyncio.Queue()
        self.batch_task = None
        self.running = False
        
        # 统计信息
        self.stats = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'l3_hits': 0,
            'l3_misses': 0,
            'total_requests': 0,
            'batch_operations': 0
        }
        
        logger.info("异步多级缓存初始化完成")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()
    
    async def start(self):
        """启动缓存系统"""
        if self.running:
            return
        
        self.running = True
        
        # 初始化L2缓存
        await self._init_l2_cache()
        
        # 初始化L3缓存
        if self.config.l3_enabled:
            await self._init_l3_cache()
        
        # 启动批量处理任务
        self.batch_task = asyncio.create_task(self._batch_worker())
        
        logger.info("异步多级缓存已启动")
    
    async def stop(self):
        """停止缓存系统"""
        if not self.running:
            return
        
        self.running = False
        
        # 处理剩余的批量操作
        await self._flush_batch_queue()
        
        # 停止批量处理任务
        if self.batch_task:
            self.batch_task.cancel()
            try:
                await self.batch_task
            except asyncio.CancelledError:
                pass
        
        # 关闭L2缓存连接
        if self.l2_conn:
            self.l2_conn.close()
        
        logger.info("异步多级缓存已停止")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        self.stats['total_requests'] += 1
        
        # L1缓存查找
        value = self.l1_cache.get(key)
        if value is not None:
            self.stats['l1_hits'] += 1
            logger.debug(f"L1缓存命中: {key}")
            return value
        
        self.stats['l1_misses'] += 1
        
        # L2缓存查找
        value = await self._get_l2(key)
        if value is not None:
            self.stats['l2_hits'] += 1
            # 提升到L1
            self.l1_cache.put(key, value)
            logger.debug(f"L2缓存命中: {key}")
            return value
        
        self.stats['l2_misses'] += 1
        
        # L3缓存查找
        if self.config.l3_enabled:
            value = await self._get_l3(key)
            if value is not None:
                self.stats['l3_hits'] += 1
                # 提升到L2和L1
                await self._set_l2(key, value)
                self.l1_cache.put(key, value)
                logger.debug(f"L3缓存命中: {key}")
                return value
        
        self.stats['l3_misses'] += 1
        logger.debug(f"缓存未命中: {key}")
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        # 同时设置到所有级别
        self.l1_cache.put(key, value)
        await self._set_l2(key, value, ttl)
        
        if self.config.l3_enabled:
            await self._set_l3(key, value, ttl)
        
        logger.debug(f"缓存设置: {key}")
    
    async def batch_set(self, items: Dict[str, Any], ttl: Optional[int] = None):
        """批量设置缓存值"""
        if not items:
            return
        
        # 添加到批量队列
        batch_item = {
            'operation': 'set',
            'items': items,
            'ttl': ttl,
            'timestamp': time.time()
        }
        
        try:
            await asyncio.wait_for(
                self.batch_queue.put(batch_item),
                timeout=self.config.batch_timeout
            )
        except asyncio.TimeoutError:
            logger.warning("批量设置操作超时，直接执行")
            await self._execute_batch_set(items, ttl)
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        deleted = False
        
        # 从所有级别删除
        if self.l1_cache.remove(key):
            deleted = True
        
        if await self._delete_l2(key):
            deleted = True
        
        if self.config.l3_enabled:
            if await self._delete_l3(key):
                deleted = True
        
        if deleted:
            logger.debug(f"缓存删除: {key}")
        
        return deleted
    
    async def clear(self, level: Optional[str] = None):
        """清空缓存"""
        if level is None or level == 'l1':
            self.l1_cache.clear()
            logger.info("L1缓存已清空")
        
        if level is None or level == 'l2':
            await self._clear_l2()
            logger.info("L2缓存已清空")
        
        if self.config.l3_enabled and (level is None or level == 'l3'):
            await self._clear_l3()
            logger.info("L3缓存已清空")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = self.stats.copy()
        
        # 计算命中率
        total_requests = stats['total_requests']
        if total_requests > 0:
            stats['l1_hit_rate'] = stats['l1_hits'] / total_requests
            stats['l2_hit_rate'] = stats['l2_hits'] / total_requests
            stats['l3_hit_rate'] = stats['l3_hits'] / total_requests
            stats['overall_hit_rate'] = (
                stats['l1_hits'] + stats['l2_hits'] + stats['l3_hits']
            ) / total_requests
        else:
            stats['l1_hit_rate'] = 0.0
            stats['l2_hit_rate'] = 0.0
            stats['l3_hit_rate'] = 0.0
            stats['overall_hit_rate'] = 0.0
        
        # 添加缓存大小信息
        stats['l1_size'] = self.l1_cache.size()
        stats['l1_max_size'] = self.config.l1_max_size
        
        if self.l2_conn:
            stats['l2_size'] = await self._get_l2_size()
            stats['l2_max_size'] = self.config.l2_max_size
        
        if self.config.l3_enabled:
            stats['l3_size'] = await self._get_l3_size()
        
        stats['queue_size'] = self.batch_queue.qsize()
        stats['running'] = self.running
        
        return stats
    
    # 私有方法
    
    async def _init_l2_cache(self):
        """初始化L2缓存（SQLite）"""
        with self.l2_lock:
            try:
                self.l2_conn = sqlite3.connect(
                    self.config.l2_db_path,
                    check_same_thread=False,
                    timeout=30.0
                )
                
                # 创建表
                self.l2_conn.execute('''
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value BLOB,
                        created_at REAL,
                        expires_at REAL,
                        size INTEGER
                    )
                ''')
                
                # 创建索引
                self.l2_conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(expires_at)
                ''')
                
                # 启用WAL模式提高并发性能
                self.l2_conn.execute('PRAGMA journal_mode=WAL')
                self.l2_conn.execute('PRAGMA synchronous=NORMAL')
                self.l2_conn.execute('PRAGMA cache_size=10000')
                
                self.l2_conn.commit()
                logger.debug("L2缓存初始化完成")
                
            except Exception as e:
                logger.error(f"L2缓存初始化失败: {str(e)}")
                raise CacheError(f"L2缓存初始化失败: {str(e)}")
    
    async def _init_l3_cache(self):
        """初始化L3缓存（文件系统）"""
        with self.l3_lock:
            try:
                self.l3_dir.mkdir(parents=True, exist_ok=True)
                logger.debug("L3缓存初始化完成")
            except Exception as e:
                logger.error(f"L3缓存初始化失败: {str(e)}")
                raise CacheError(f"L3缓存初始化失败: {str(e)}")
    
    async def _get_l2(self, key: str) -> Optional[Any]:
        """从L2缓存获取值"""
        if not self.l2_conn:
            return None
        
        try:
            cursor = self.l2_conn.cursor()
            cursor.execute('''
                SELECT value, expires_at FROM cache 
                WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)
            ''', (key, time.time()))
            
            row = cursor.fetchone()
            if row:
                value_data, expires_at = row
                if self.config.enable_compression:
                    value = pickle.loads(value_data)
                else:
                    value = pickle.loads(value_data)
                
                # 更新访问时间（可选）
                # cursor.execute('UPDATE cache SET accessed_at = ? WHERE key = ?', 
                #                (time.time(), key))
                # self.l2_conn.commit()
                
                return value
            
            return None
            
        except Exception as e:
            logger.warning(f"L2缓存读取失败: {str(e)}")
            return None
    
    async def _set_l2(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置L2缓存值"""
        if not self.l2_conn:
            return
        
        try:
            # 序列化值
            if self.config.enable_compression:
                import gzip
                value_data = gzip.compress(pickle.dumps(value))
            else:
                value_data = pickle.dumps(value)
            
            # 计算过期时间
            ttl = ttl or self.config.l2_ttl
            expires_at = time.time() + ttl if ttl > 0 else None
            
            cursor = self.l2_conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO cache (key, value, created_at, expires_at, size)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, value_data, time.time(), expires_at, len(value_data)))
            
            self.l2_conn.commit()
            
        except Exception as e:
            logger.warning(f"L2缓存写入失败: {str(e)}")
    
    async def _delete_l2(self, key: str) -> bool:
        """从L2缓存删除值"""
        if not self.l2_conn:
            return False
        
        try:
            cursor = self.l2_conn.cursor()
            cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
            self.l2_conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.warning(f"L2缓存删除失败: {str(e)}")
            return False
    
    async def _clear_l2(self):
        """清空L2缓存"""
        if not self.l2_conn:
            return
        
        try:
            cursor = self.l2_conn.cursor()
            cursor.execute('DELETE FROM cache')
            self.l2_conn.commit()
            
        except Exception as e:
            logger.warning(f"L2缓存清空失败: {str(e)}")
    
    async def _get_l2_size(self) -> int:
        """获取L2缓存大小"""
        if not self.l2_conn:
            return 0
        
        try:
            cursor = self.l2_conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM cache')
            return cursor.fetchone()[0]
            
        except Exception:
            return 0
    
    async def _get_l3(self, key: str) -> Optional[Any]:
        """从L3缓存获取值"""
        if not self.config.l3_enabled:
            return None
        
        try:
            # 生成文件路径
            file_path = self._get_l3_file_path(key)
            
            if not file_path.exists():
                return None
            
            # 检查文件是否过期
            stat = file_path.stat()
            if self.config.l3_ttl > 0:
                if time.time() - stat.st_mtime > self.config.l3_ttl:
                    file_path.unlink(missing_ok=True)
                    return None
            
            # 读取文件
            with open(file_path, 'rb') as f:
                if self.config.enable_compression:
                    import gzip
                    data = gzip.decompress(f.read())
                else:
                    data = f.read()
                
                return pickle.loads(data)
            
        except Exception as e:
            logger.warning(f"L3缓存读取失败: {str(e)}")
            return None
    
    async def _set_l3(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置L3缓存值"""
        if not self.config.l3_enabled:
            return
        
        try:
            # 生成文件路径
            file_path = self._get_l3_file_path(key)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 序列化值
            if self.config.enable_compression:
                import gzip
                data = gzip.compress(pickle.dumps(value))
            else:
                data = pickle.dumps(value)
            
            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(data)
            
        except Exception as e:
            logger.warning(f"L3缓存写入失败: {str(e)}")
    
    async def _delete_l3(self, key: str) -> bool:
        """从L3缓存删除值"""
        if not self.config.l3_enabled:
            return False
        
        try:
            file_path = self._get_l3_file_path(key)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
            
        except Exception as e:
            logger.warning(f"L3缓存删除失败: {str(e)}")
            return False
    
    async def _clear_l3(self):
        """清空L3缓存"""
        if not self.config.l3_enabled:
            return
        
        try:
            import shutil
            if self.l3_dir.exists():
                shutil.rmtree(self.l3_dir)
                self.l3_dir.mkdir(parents=True, exist_ok=True)
                
        except Exception as e:
            logger.warning(f"L3缓存清空失败: {str(e)}")
    
    async def _get_l3_size(self) -> int:
        """获取L3缓存大小"""
        if not self.config.l3_enabled:
            return 0
        
        try:
            return len(list(self.l3_dir.glob('*')))
        except Exception:
            return 0
    
    def _get_l3_file_path(self, key: str) -> Path:
        """获取L3缓存文件路径"""
        # 使用MD5哈希作为文件名，避免文件名过长或包含特殊字符
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return self.l3_dir / f"{key_hash}.cache"
    
    async def _batch_worker(self):
        """批量处理工作线程"""
        logger.debug("批量处理工作线程启动")
        
        while self.running:
            try:
                # 等待批量操作
                batch_item = await asyncio.wait_for(
                    self.batch_queue.get(),
                    timeout=1.0
                )
                
                # 处理批量操作
                if batch_item['operation'] == 'set':
                    await self._execute_batch_set(
                        batch_item['items'],
                        batch_item['ttl']
                    )
                
                self.stats['batch_operations'] += 1
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                logger.error(f"批量处理错误: {str(e)}")
        
        logger.debug("批量处理工作线程停止")
    
    async def _execute_batch_set(self, items: Dict[str, Any], ttl: Optional[int] = None):
        """执行批量设置操作"""
        if not items:
            return
        
        # 分批处理
        batch_size = self.config.batch_size
        items_list = list(items.items())
        
        for i in range(0, len(items_list), batch_size):
            batch = dict(items_list[i:i + batch_size])
            
            # 并行设置到所有级别
            tasks = []
            
            # L1缓存（同步操作）
            for key, value in batch.items():
                self.l1_cache.put(key, value)
            
            # L2缓存（异步操作）
            l2_tasks = []
            for key, value in batch.items():
                l2_tasks.append(self._set_l2(key, value, ttl))
            
            if l2_tasks:
                tasks.extend(l2_tasks)
            
            # L3缓存（异步操作）
            if self.config.l3_enabled:
                l3_tasks = []
                for key, value in batch.items():
                    l3_tasks.append(self._set_l3(key, value, ttl))
                
                if l3_tasks:
                    tasks.extend(l3_tasks)
            
            # 等待所有异步操作完成
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # 短暂休息，避免阻塞其他操作
            await asyncio.sleep(0.01)
        
        logger.debug(f"批量设置完成: {len(items)} 个项目")
    
    async def _flush_batch_queue(self):
        """刷新批量队列"""
        while not self.batch_queue.empty():
            try:
                batch_item = self.batch_queue.get_nowait()
                
                if batch_item['operation'] == 'set':
                    await self._execute_batch_set(
                        batch_item['items'],
                        batch_item['ttl']
                    )
                
            except Exception as e:
                logger.error(f"刷新批量队列错误: {str(e)}")


# 便捷函数
async def create_async_cache(config=None) -> AsyncMultiLevelCache:
    """创建异步缓存实例"""
    cache = AsyncMultiLevelCache(config)
    await cache.start()
    return cache


def get_async_cache() -> AsyncMultiLevelCache:
    """获取全局异步缓存实例"""
    # 使用单例模式
    if not hasattr(get_async_cache, '_instance'):
        get_async_cache._instance = AsyncMultiLevelCache()
    return get_async_cache._instance