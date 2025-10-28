"""
性能监控和异步缓存相关配置模型
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator

from .models import BaseSettings


class AsyncCacheConfig(BaseModel):
    """异步缓存配置"""
    # L1缓存（内存）
    l1_max_size: int = Field(default=1000, ge=1, description="L1缓存最大条目数")
    l1_ttl: int = Field(default=3600, ge=60, description="L1缓存TTL(秒)")
    
    # L2缓存（SQLite）
    l2_max_size: int = Field(default=10000, ge=1, description="L2缓存最大条目数")
    l2_ttl: int = Field(default=86400, ge=60, description="L2缓存TTL(秒)")
    l2_db_path: str = Field(default="data/cache_l2.db", description="L2缓存数据库路径")
    
    # L3缓存（文件）
    l3_enabled: bool = Field(default=True, description="是否启用L3缓存")
    l3_dir: str = Field(default="data/cache_l3", description="L3缓存目录")
    l3_ttl: int = Field(default=604800, ge=60, description="L3缓存TTL(秒)")
    
    # 批量操作
    batch_size: int = Field(default=100, ge=1, le=1000, description="批量操作大小")
    batch_timeout: float = Field(default=5.0, ge=0.1, le=60.0, description="批量操作超时(秒)")
    
    # 压缩
    enable_compression: bool = Field(default=True, description="是否启用压缩")
    compression_threshold: int = Field(default=1024, ge=256, description="压缩阈值(字节)")


class SmartChunkerConfig(BaseModel):
    """智能分块器配置"""
    max_tokens: int = Field(default=4000, ge=100, le=32000, description="最大令牌数")
    min_tokens: int = Field(default=200, ge=50, le=1000, description="最小令牌数")
    overlap_tokens: int = Field(default=200, ge=0, le=1000, description="重叠令牌数")
    respect_code_blocks: bool = Field(default=True, description="是否尊重代码块")
    respect_obsidian_syntax: bool = Field(default=True, description="是否尊重Obsidian语法")
    preserve_structure: bool = Field(default=True, description="是否保持结构")
    language: str = Field(default="en", description="默认语言")


class PerformanceMonitorConfig(BaseModel):
    """性能监控配置"""
    enabled: bool = Field(default=True, description="是否启用性能监控")
    max_history: int = Field(default=1000, ge=100, le=10000, description="最大历史记录数")
    monitor_interval: float = Field(default=5.0, ge=0.1, le=60.0, description="监控间隔(秒)")
    export_interval: int = Field(default=3600, ge=60, description="导出间隔(秒)")
    export_dir: str = Field(default="data/performance", description="导出目录")
    
    # 告警配置
    alert_cpu_threshold: float = Field(default=80.0, ge=50.0, le=100.0, description="CPU使用率告警阈值(%)")
    alert_cpu_critical: float = Field(default=95.0, ge=80.0, le=100.0, description="CPU使用率严重告警阈值(%)")
    alert_memory_threshold: float = Field(default=80.0, ge=50.0, le=100.0, description="内存使用率告警阈值(%)")
    alert_memory_critical: float = Field(default=95.0, ge=80.0, le=100.0, description="内存使用率严重告警阈值(%)")
    alert_disk_threshold: float = Field(default=90.0, ge=70.0, le=100.0, description="磁盘使用率告警阈值(%)")
    alert_translation_threshold: float = Field(default=30.0, ge=5.0, le=300.0, description="翻译延迟告警阈值(秒)")
    alert_translation_critical: float = Field(default=60.0, ge=10.0, le=600.0, description="翻译延迟严重告警阈值(秒)")
    alert_api_error_rate: float = Field(default=0.1, ge=0.01, le=1.0, description="API错误率告警阈值")
    alert_cache_hit_rate: float = Field(default=0.5, ge=0.1, le=1.0, description="缓存命中率告警阈值")


class EmbeddingConfig(BaseModel):
    """嵌入模型配置"""
    enabled: bool = Field(default=True, description="是否启用嵌入模型")
    provider: str = Field(default="sentence_transformer", description="嵌入模型提供商")
    model_name: str = Field(default="bge-m3", description="嵌入模型名称")
    dimension: int = Field(default=1024, ge=128, le=4096, description="向量维度")
    batch_size: int = Field(default=32, ge=1, le=256, description="批处理大小")
    device: str = Field(default="auto", description="设备类型(auto/cpu/cuda)")
    
    # Ollama配置
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama服务地址")
    
    # OpenAI配置
    openai_api_key: str = Field(default="", description="OpenAI API密钥")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI API基础URL")
    openai_model: str = Field(default="text-embedding-ada-002", description="OpenAI嵌入模型名称")
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        valid_providers = ["sentence_transformer", "ollama", "openai"]
        if v not in valid_providers:
            raise ValueError(f'嵌入模型提供商必须是以下之一: {", ".join(valid_providers)}')
        return v
    
    @field_validator('device')
    @classmethod
    def validate_device(cls, v):
        valid_devices = ["auto", "cpu", "cuda"]
        if v not in valid_devices:
            raise ValueError(f'设备类型必须是以下之一: {", ".join(valid_devices)}')
        return v


class ConnectionPoolConfig(BaseModel):
    """连接池配置"""
    enabled: bool = Field(default=True, description="是否启用连接池")
    max_connections: int = Field(default=100, ge=10, le=1000, description="最大连接数")
    max_connections_per_host: int = Field(default=20, ge=5, le=100, description="每个主机最大连接数")
    ttl_dns_cache: int = Field(default=300, ge=60, le=3600, description="DNS缓存TTL(秒)")
    use_dns_cache: bool = Field(default=True, description="是否使用DNS缓存")
    keepalive_timeout: int = Field(default=60, ge=10, le=300, description="保持连接超时(秒)")
    enable_cleanup_closed: bool = Field(default=True, description="是否清理已关闭连接")
    connect_timeout: int = Field(default=10, ge=1, le=60, description="连接超时(秒)")
    sock_read_timeout: int = Field(default=30, ge=5, le=300, description="套接字读取超时(秒)")


class ErrorHandlingConfig(BaseModel):
    """错误处理配置"""
    enabled: bool = Field(default=True, description="是否启用增强错误处理")
    max_retries: int = Field(default=3, ge=1, le=10, description="最大重试次数")
    backoff_factor: float = Field(default=2.0, ge=1.0, le=5.0, description="退避因子")
    retry_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="重试延迟(秒)")
    enable_fallback: bool = Field(default=True, description="是否启用降级")
    language: str = Field(default="zh", description="错误信息语言")
    enable_error_reporting: bool = Field(default=True, description="是否启用错误报告")
    error_report_dir: str = Field(default="data/errors", description="错误报告目录")


class PerformanceSettings(BaseSettings):
    """性能相关设置"""
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
        "extra": "ignore"
    }
    
    # 配置节
    async_cache: AsyncCacheConfig = Field(default_factory=AsyncCacheConfig)
    smart_chunker: SmartChunkerConfig = Field(default_factory=SmartChunkerConfig)
    performance_monitor: PerformanceMonitorConfig = Field(default_factory=PerformanceMonitorConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    connection_pool: ConnectionPoolConfig = Field(default_factory=ConnectionPoolConfig)
    error_handling: ErrorHandlingConfig = Field(default_factory=ErrorHandlingConfig)
    
    def get_embedding_config(self) -> Dict[str, Any]:
        """获取嵌入模型配置"""
        provider = self.embedding.provider
        
        config = {
            "provider": provider,
            "model_name": self.embedding.model_name,
            "dimension": self.embedding.dimension,
            "batch_size": self.embedding.batch_size,
            "device": self.embedding.device
        }
        
        if provider == "ollama":
            config["base_url"] = self.embedding.ollama_base_url
        elif provider == "openai":
            config["api_key"] = self.embedding.openai_api_key
            config["base_url"] = self.embedding.openai_base_url
            config["model"] = self.embedding.openai_model
        
        return config