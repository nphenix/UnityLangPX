"""
UnityLangPX 增强型模型客户端工厂

扩展基础工厂类，实现策略模式、缓存机制和智能选择功能，
支持术语增强功能的模型客户端创建和管理。
"""

import time
import hashlib
from typing import Dict, Type, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass

from .base import ModelClient
from .factory import ModelClientFactory
from .ollama_client import OllamaModelClient
from .openai_client import OpenAIModelClient
from ..logger import get_logger

logger = get_logger(__name__)


class ClientStrategy(Enum):
    """客户端策略枚举"""
    PERFORMANCE = "performance"      # 性能优先
    QUALITY = "quality"            # 质量优先
    COST = "cost"                  # 成本优先
    BALANCED = "balanced"          # 平衡策略
    ENHANCEMENT = "enhancement"    # 增强功能专用


class ClientType(Enum):
    """客户端类型枚举"""
    TRANSLATION = "translation"    # 翻译专用
    ENHANCEMENT = "enhancement"    # 增强功能专用
    GENERAL = "general"            # 通用型


@dataclass
class ClientMetrics:
    """客户端指标"""
    client_id: str
    provider: str
    model: str
    response_times: List[float]
    success_count: int
    error_count: int
    last_used: float
    total_requests: int
    cache_hits: int
    cache_misses: int
    
    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.error_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total


class EnhancedModelClientFactory(ModelClientFactory):
    """增强型模型客户端工厂，支持策略模式和缓存机制"""
    
    def __init__(self):
        """初始化增强型工厂"""
        super().__init__()
        
        # 客户端缓存
        self._client_cache: Dict[str, ModelClient] = {}
        self._client_metrics: Dict[str, ClientMetrics] = {}
        
        # 策略配置
        self._strategy_config = {
            ClientStrategy.PERFORMANCE: {
                'priority': ['response_time', 'success_rate'],
                'weights': {'response_time': 0.6, 'success_rate': 0.3, 'cost': 0.1}
            },
            ClientStrategy.QUALITY: {
                'priority': ['success_rate', 'model_capability'],
                'weights': {'success_rate': 0.5, 'model_capability': 0.4, 'response_time': 0.1}
            },
            ClientStrategy.COST: {
                'priority': ['cost', 'response_time'],
                'weights': {'cost': 0.7, 'response_time': 0.2, 'success_rate': 0.1}
            },
            ClientStrategy.BALANCED: {
                'priority': ['success_rate', 'response_time', 'cost'],
                'weights': {'success_rate': 0.4, 'response_time': 0.3, 'cost': 0.3}
            },
            ClientStrategy.ENHANCEMENT: {
                'priority': ['model_capability', 'context_understanding'],
                'weights': {'model_capability': 0.6, 'context_understanding': 0.3, 'response_time': 0.1}
            }
        }
        
        # 模型能力评分
        self._model_capabilities = {
            # Ollama模型
            'simonpu/hunyuan-mt-chimera-7b:q8': {
                'translation': 0.9,
                'context_understanding': 0.8,
                'terminology_enhancement': 0.7,
                'cost_efficiency': 0.9
            },
            'llama2': {
                'translation': 0.6,
                'context_understanding': 0.7,
                'terminology_enhancement': 0.5,
                'cost_efficiency': 0.8
            },
            # OpenAI模型
            'gpt-3.5-turbo': {
                'translation': 0.8,
                'context_understanding': 0.9,
                'terminology_enhancement': 0.8,
                'cost_efficiency': 0.6
            },
            'gpt-4': {
                'translation': 0.95,
                'context_understanding': 0.95,
                'terminology_enhancement': 0.9,
                'cost_efficiency': 0.4
            }
        }
        
        # 缓存配置
        self._cache_enabled = True
        self._max_cache_size = 100
        self._cache_ttl = 3600  # 1小时
        
        logger.info("增强型模型客户端工厂初始化完成")
    
    def create_client_with_strategy(self, provider: str, config: Any, 
                                   strategy: ClientStrategy = ClientStrategy.BALANCED,
                                   client_type: ClientType = ClientType.GENERAL) -> ModelClient:
        """
        根据策略创建模型客户端
        
        Args:
            provider: 模型提供商
            config: 配置对象
            strategy: 客户端策略
            client_type: 客户端类型
            
        Returns:
            模型客户端实例
        """
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(provider, config, strategy, client_type)
            
            # 检查缓存
            if self._cache_enabled and cache_key in self._client_cache:
                logger.debug(f"使用客户端缓存: {cache_key}")
                client = self._client_cache[cache_key]
                self._update_metrics(cache_key, success=True)
                return client
            
            # 创建客户端
            client = self._create_client_by_type(provider, config, client_type)
            
            # 应用策略配置
            self._apply_strategy_config(client, strategy, config)
            
            # 缓存客户端
            if self._cache_enabled:
                self._cache_client(cache_key, client)
            
            # 初始化指标
            self._init_metrics(cache_key, provider, config.model, strategy, client_type)
            
            logger.info(f"创建策略客户端: {provider}, 策略: {strategy.value}, 类型: {client_type.value}")
            return client
            
        except Exception as e:
            logger.error(f"创建策略客户端失败: {str(e)}")
            # 降级到基础工厂
            return super().create_client(provider, config)
    
    def get_optimal_client(self, task_type: str, complexity: float, 
                          source_lang: str = "en", target_lang: str = "zh") -> ModelClient:
        """
        根据任务类型和复杂度获取最优客户端
        
        Args:
            task_type: 任务类型 (translation, enhancement, disambiguation)
            complexity: 复杂度 (0-1)
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            最优模型客户端
        """
        try:
            # 分析任务需求
            requirements = self._analyze_task_requirements(task_type, complexity)
            
            # 选择策略
            strategy = self._select_strategy_by_requirements(requirements)
            
            # 选择模型
            provider, model = self._select_optimal_model(requirements, strategy)
            
            # 创建配置
            config = self._create_optimized_config(provider, model, requirements)
            
            # 选择客户端类型
            client_type = self._select_client_type(task_type)
            
            # 创建客户端
            return self.create_client_with_strategy(provider, config, strategy, client_type)
            
        except Exception as e:
            logger.error(f"获取最优客户端失败: {str(e)}")
            # 降级到默认客户端
            return self._get_default_client()
    
    def create_terminology_enhancement_client(self, config: Any) -> ModelClient:
        """
        创建专门用于术语增强的客户端
        
        Args:
            config: 配置对象
            
        Returns:
            术语增强专用客户端
        """
        try:
            # 选择最适合增强的模型
            provider, model = self._select_best_enhancement_model()
            
            # 创建增强专用配置
            enhanced_config = self._create_enhancement_config(provider, model, config)
            
            # 创建客户端
            return self.create_client_with_strategy(
                provider, enhanced_config, 
                ClientStrategy.ENHANCEMENT, 
                ClientType.ENHANCEMENT
            )
            
        except Exception as e:
            logger.error(f"创建术语增强客户端失败: {str(e)}")
            # 降级到基础客户端
            return super().create_client(config.model.provider, config)
    
    def get_client_metrics(self, client_id: Optional[str] = None) -> Dict[str, ClientMetrics]:
        """
        获取客户端指标
        
        Args:
            client_id: 客户端ID，None表示获取所有
            
        Returns:
            客户端指标字典
        """
        if client_id:
            return {client_id: self._client_metrics.get(client_id)}
        else:
            return self._client_metrics.copy()
    
    def update_client_performance(self, client_id: str, response_time: float, 
                                 success: bool, cache_hit: bool = False):
        """
        更新客户端性能指标
        
        Args:
            client_id: 客户端ID
            response_time: 响应时间
            success: 是否成功
            cache_hit: 是否命中缓存
        """
        if client_id not in self._client_metrics:
            return
        
        metrics = self._client_metrics[client_id]
        metrics.last_used = time.time()
        metrics.total_requests += 1
        
        if cache_hit:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1
        
        if success:
            metrics.success_count += 1
        else:
            metrics.error_count += 1
        
        # 更新响应时间列表（保留最近100次）
        metrics.response_times.append(response_time)
        if len(metrics.response_times) > 100:
            metrics.response_times = metrics.response_times[-100:]
    
    def clear_cache(self):
        """清空客户端缓存"""
        self._client_cache.clear()
        logger.info("客户端缓存已清空")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'cache_enabled': self._cache_enabled,
            'cache_size': len(self._client_cache),
            'max_cache_size': self._max_cache_size,
            'cached_clients': list(self._client_cache.keys())
        }
    
    # 私有方法
    
    def _generate_cache_key(self, provider: str, config: Any, 
                           strategy: ClientStrategy, client_type: ClientType) -> str:
        """生成缓存键"""
        config_str = f"{provider}_{config.model}_{strategy.value}_{client_type.value}"
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def _create_client_by_type(self, provider: str, config: Any, 
                              client_type: ClientType) -> ModelClient:
        """根据类型创建客户端"""
        # 基础创建
        client = super().create_client(provider, config)
        
        # 根据类型进行特殊配置
        if client_type == ClientType.ENHANCEMENT:
            # 增强功能专用配置
            if hasattr(client, 'set_temperature'):
                client.set_temperature(0.1)  # 降低随机性
            if hasattr(client, 'set_max_tokens'):
                client.set_max_tokens(500)   # 限制输出长度
        
        elif client_type == ClientType.TRANSLATION:
            # 翻译专用配置
            if hasattr(client, 'set_temperature'):
                client.set_temperature(0.2)
            if hasattr(client, 'set_max_tokens'):
                client.set_max_tokens(2000)
        
        return client
    
    def _apply_strategy_config(self, client: ModelClient, strategy: ClientStrategy, config: Any):
        """应用策略配置"""
        strategy_config = self._strategy_config.get(strategy, {})
        
        # 根据策略调整配置
        if strategy == ClientStrategy.PERFORMANCE:
            # 性能优先：减少输出长度，降低温度
            if hasattr(client, 'set_max_tokens'):
                client.set_max_tokens(min(config.max_tokens or 1000, 500))
            if hasattr(client, 'set_temperature'):
                client.set_temperature(0.1)
        
        elif strategy == ClientStrategy.QUALITY:
            # 质量优先：增加输出长度，适当提高温度
            if hasattr(client, 'set_max_tokens'):
                client.set_max_tokens(max(config.max_tokens or 1000, 1500))
            if hasattr(client, 'set_temperature'):
                client.set_temperature(0.3)
        
        elif strategy == ClientStrategy.COST:
            # 成本优先：严格控制输出长度
            if hasattr(client, 'set_max_tokens'):
                client.set_max_tokens(min(config.max_tokens or 1000, 300))
            if hasattr(client, 'set_temperature'):
                client.set_temperature(0.1)
        
        elif strategy == ClientStrategy.ENHANCEMENT:
            # 增强功能：平衡质量和性能
            if hasattr(client, 'set_max_tokens'):
                client.set_max_tokens(800)
            if hasattr(client, 'set_temperature'):
                client.set_temperature(0.1)
    
    def _cache_client(self, cache_key: str, client: ModelClient):
        """缓存客户端"""
        if len(self._client_cache) >= self._max_cache_size:
            # 简单LRU：删除最旧的客户端
            oldest_key = min(self._client_cache.keys(), 
                           key=lambda k: self._client_metrics.get(k, ClientMetrics('', '', '', [], 0, 0, 0, 0, 0, 0)).last_used)
            del self._client_cache[oldest_key]
            if oldest_key in self._client_metrics:
                del self._client_metrics[oldest_key]
        
        self._client_cache[cache_key] = client
    
    def _init_metrics(self, cache_key: str, provider: str, model: str, 
                     strategy: ClientStrategy, client_type: ClientType):
        """初始化指标"""
        if cache_key not in self._client_metrics:
            self._client_metrics[cache_key] = ClientMetrics(
                client_id=cache_key,
                provider=provider,
                model=model,
                response_times=[],
                success_count=0,
                error_count=0,
                last_used=time.time(),
                total_requests=0,
                cache_hits=0,
                cache_misses=0
            )
    
    def _update_metrics(self, cache_key: str, success: bool):
        """更新指标"""
        if cache_key in self._client_metrics:
            metrics = self._client_metrics[cache_key]
            metrics.last_used = time.time()
            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1
    
    def _analyze_task_requirements(self, task_type: str, complexity: float) -> Dict[str, Any]:
        """分析任务需求"""
        requirements = {
            'task_type': task_type,
            'complexity': complexity,
            'quality_priority': 0.5,
            'speed_priority': 0.5,
            'cost_priority': 0.5
        }
        
        # 根据任务类型调整优先级
        if task_type == 'enhancement':
            requirements['quality_priority'] = 0.8
            requirements['speed_priority'] = 0.1
            requirements['cost_priority'] = 0.1
        elif task_type == 'translation':
            requirements['quality_priority'] = 0.6
            requirements['speed_priority'] = 0.3
            requirements['cost_priority'] = 0.1
        elif task_type == 'disambiguation':
            requirements['quality_priority'] = 0.9
            requirements['speed_priority'] = 0.05
            requirements['cost_priority'] = 0.05
        
        # 根据复杂度调整
        if complexity > 0.8:
            requirements['quality_priority'] += 0.2
            requirements['speed_priority'] -= 0.1
            requirements['cost_priority'] -= 0.1
        elif complexity < 0.3:
            requirements['speed_priority'] += 0.2
            requirements['quality_priority'] -= 0.1
            requirements['cost_priority'] -= 0.1
        
        return requirements
    
    def _select_strategy_by_requirements(self, requirements: Dict[str, Any]) -> ClientStrategy:
        """根据需求选择策略"""
        quality_priority = requirements['quality_priority']
        speed_priority = requirements['speed_priority']
        cost_priority = requirements['cost_priority']
        
        if quality_priority > 0.7:
            return ClientStrategy.QUALITY
        elif speed_priority > 0.7:
            return ClientStrategy.PERFORMANCE
        elif cost_priority > 0.7:
            return ClientStrategy.COST
        elif requirements['task_type'] == 'enhancement':
            return ClientStrategy.ENHANCEMENT
        else:
            return ClientStrategy.BALANCED
    
    def _select_optimal_model(self, requirements: Dict[str, Any], 
                             strategy: ClientStrategy) -> Tuple[str, str]:
        """选择最优模型"""
        best_score = 0
        best_provider = "ollama"
        best_model = "simonpu/hunyuan-mt-chimera-7b:q8"
        
        for provider_model, capabilities in self._model_capabilities.items():
            # 计算综合评分
            score = self._calculate_model_score(capabilities, requirements, strategy)
            
            if score > best_score:
                best_score = score
                # 简单的提供商判断
                if 'gpt' in provider_model:
                    best_provider = "openai"
                else:
                    best_provider = "ollama"
                best_model = provider_model
        
        return best_provider, best_model
    
    def _calculate_model_score(self, capabilities: Dict[str, float], 
                              requirements: Dict[str, Any], 
                              strategy: ClientStrategy) -> float:
        """计算模型评分"""
        strategy_weights = self._strategy_config[strategy]['weights']
        
        score = 0.0
        
        # 根据策略权重计算评分
        if 'model_capability' in strategy_weights:
            task_type = requirements['task_type']
            if task_type == 'translation':
                score += capabilities['translation'] * strategy_weights['model_capability']
            elif task_type == 'enhancement':
                score += capabilities['terminology_enhancement'] * strategy_weights['model_capability']
            else:
                score += capabilities['context_understanding'] * strategy_weights['model_capability']
        
        if 'context_understanding' in strategy_weights:
            score += capabilities['context_understanding'] * strategy_weights['context_understanding']
        
        if 'cost' in strategy_weights:
            score += capabilities['cost_efficiency'] * strategy_weights['cost']
        
        # 根据复杂度调整评分
        if requirements['complexity'] > 0.7:
            score *= (1 + capabilities['context_understanding'] * 0.2)
        
        return score
    
    def _create_optimized_config(self, provider: str, model: str, 
                                requirements: Dict[str, Any]) -> Any:
        """创建优化配置"""
        # 这里需要根据实际的配置类来实现
        # 简化实现，返回基本配置
        class SimpleConfig:
            def __init__(self, provider, model):
                self.provider = provider
                self.model = model
                self.max_tokens = 1000
                self.temperature = 0.2
        
        return SimpleConfig(provider, model)
    
    def _select_client_type(self, task_type: str) -> ClientType:
        """选择客户端类型"""
        if task_type == 'enhancement':
            return ClientType.ENHANCEMENT
        elif task_type == 'translation':
            return ClientType.TRANSLATION
        else:
            return ClientType.GENERAL
    
    def _select_best_enhancement_model(self) -> Tuple[str, str]:
        """选择最适合增强的模型"""
        best_score = 0
        best_provider = "ollama"
        best_model = "simonpu/hunyuan-mt-chimera-7b:q8"
        
        for provider_model, capabilities in self._model_capabilities.items():
            # 重点关注术语增强能力
            score = (capabilities['terminology_enhancement'] * 0.6 + 
                    capabilities['context_understanding'] * 0.3 +
                    capabilities['translation'] * 0.1)
            
            if score > best_score:
                best_score = score
                if 'gpt' in provider_model:
                    best_provider = "openai"
                else:
                    best_provider = "ollama"
                best_model = provider_model
        
        return best_provider, best_model
    
    def _create_enhancement_config(self, provider: str, model: str, base_config: Any) -> Any:
        """创建增强专用配置"""
        class EnhancementConfig:
            def __init__(self, provider, model, base_config):
                self.provider = provider
                self.model = model
                self.max_tokens = 800
                self.temperature = 0.1
                # 继承基础配置的其他属性
                if hasattr(base_config, 'host'):
                    self.host = base_config.host
                if hasattr(base_config, 'port'):
                    self.port = base_config.port
                if hasattr(base_config, 'api_key'):
                    self.api_key = base_config.api_key
        
        return EnhancementConfig(provider, model, base_config)
    
    def _get_default_client(self) -> ModelClient:
        """获取默认客户端"""
        try:
            # 尝试创建Ollama客户端
            class DefaultConfig:
                def __init__(self):
                    self.provider = "ollama"
                    self.model = "simonpu/hunyuan-mt-chimera-7b:q8"
                    self.host = "localhost"
                    self.port = 11434
                    self.max_tokens = 1000
                    self.temperature = 0.2
            
            return super().create_client("ollama", DefaultConfig())
        except Exception as e:
            logger.error(f"创建默认客户端失败: {str(e)}")
            raise