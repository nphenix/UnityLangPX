"""
统一配置模型定义

基于Pydantic V2的强类型配置模型，支持多层级配置、
环境适配等功能。
"""

from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..core.exceptions import ConfigurationError


class ProjectConfig(BaseModel):
    """项目基础配置"""
    name: str = Field(default="UnityLangPX", description="项目名称")
    version: str = Field(default="1.0.0", description="项目版本")
    description: str = Field(
        default="基于大模型技术的多平台翻译解决方案", 
        description="项目描述"
    )


class EnvironmentsConfig(BaseModel):
    """环境配置"""
    development: Dict[str, Any] = Field(default_factory=dict, description="开发环境配置")
    testing: Dict[str, Any] = Field(default_factory=dict, description="测试环境配置")
    production: Dict[str, Any] = Field(default_factory=dict, description="生产环境配置")


class ModelConfig(BaseModel):
    """模型相关配置"""
    provider: str = Field(default="ollama", description="模型提供商")
    default_provider: str = Field(default="ollama", description="默认模型提供商")
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        valid_providers = ["ollama", "openai"]
        if v not in valid_providers:
            raise ValueError(f'模型提供商必须是以下之一: {", ".join(valid_providers)}')
        return v


class OllamaModelConfig(BaseModel):
    """Ollama模型配置"""
    host: str = Field(default="http://localhost:11434", description="Ollama服务地址")
    model: str = Field(default="SimonPu/Hunyuan-MT-Chimera-7B:Q8", description="翻译模型名称")
    timeout: int = Field(default=60, description="请求超时时间(秒)")
    
    @field_validator('host')
    @classmethod
    def validate_host(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Ollama主机地址必须以http://或https://开头')
        return v


class OpenAIModelConfig(BaseModel):
    """OpenAI兼容API配置"""
    base_url: str = Field(default="https://api.openai.com/v1", description="API基础URL")
    api_key: str = Field(default="", description="API密钥")
    model: str = Field(default="gpt-3.5-turbo", description="模型名称")
    max_tokens: int = Field(default=4000, description="最大生成令牌数")
    timeout: int = Field(default=60, description="请求超时时间(秒)")
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('API基础URL必须以http://或https://开头')
        return v
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        # 允许空值，但在使用OpenAI提供商时会检查
        return v


class TranslationConfig(BaseModel):
    """翻译相关配置"""
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(default=4000, ge=1, description="最大生成令牌数")
    chunk_size: int = Field(default=1000, ge=0, description="文本分块大小，0表示自动计算")
    overlap: int = Field(default=100, ge=0, description="分块重叠大小")
    source_language: str = Field(default="en", description="源语言")
    target_language: str = Field(default="zh", description="目标语言")
    
    @field_validator('overlap')
    @classmethod
    def validate_overlap(cls, v, info):
        # 只有当chunk_size > 0时才验证
        if info.data and 'chunk_size' in info.data and info.data['chunk_size'] > 0 and v >= info.data['chunk_size']:
            raise ValueError('重叠大小不能大于等于分块大小')
        return v


class CLIConfig(BaseModel):
    """命令行工具配置"""
    input_dir: str = Field(default="input", description="输入目录")
    output_dir: str = Field(default="output", description="输出目录")
    preserve_structure: bool = Field(default=True, description="保持目录结构")
    parallel_workers: int = Field(default=4, ge=1, le=16, description="并行工作线程数")
    
    @field_validator('input_dir', 'output_dir')
    @classmethod
    def validate_dir(cls, v):
        if not v.strip():
            raise ValueError('目录名不能为空')
        return v.strip()


class CacheConfig(BaseModel):
    """缓存相关配置"""
    enable_cache: bool = Field(default=True, description="是否启用缓存")
    cache_dir: str = Field(default=".translation_cache", description="缓存目录")
    max_cache_size_mb: int = Field(default=500, ge=1, description="最大缓存大小(MB)")
    cache_ttl_days: int = Field(default=30, ge=1, description="缓存过期时间(天)")


class LoggingConfig(BaseModel):
    """日志相关配置"""
    level: str = Field(default="INFO", description="日志级别")
    file: str = Field(default="translation.log", description="日志文件名")
    max_size_mb: int = Field(default=10, ge=1, description="日志文件最大大小(MB)")
    backup_count: int = Field(default=5, ge=1, description="日志文件备份数量")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'日志级别必须是以下之一: {", ".join(valid_levels)}')
        return v.upper()


class PerformanceConfig(BaseModel):
    """性能相关配置"""
    monitor_performance: bool = Field(default=True, description="是否监控性能")
    memory_limit_mb: int = Field(default=1024, ge=128, description="内存限制(MB)")
    enable_profiling: bool = Field(default=False, description="是否启用性能分析")


class MCPServerConfig(BaseModel):
    """MCP服务器配置"""
    enabled: bool = Field(default=True, description="是否启用MCP服务器")
    host: str = Field(default="0.0.0.0", description="服务器主机地址")
    port: int = Field(default=4010, description="服务器端口")
    max_connections: int = Field(default=10, description="最大连接数")
    request_timeout: int = Field(default=120, description="请求超时时间(秒)")
    log_level: str = Field(default="INFO", description="日志级别")
    enable_http_server: bool = Field(default=True, description="是否启用HTTP服务器提供静态文件")
    http_port: int = Field(default=4011, description="HTTP服务器端口")
    static_dir: str = Field(default="static", description="静态文件目录")
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('端口号必须在1-65535范围内')
        return v
    
    @field_validator('http_port')
    @classmethod
    def validate_http_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('HTTP服务器端口必须在1-65535范围内')
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'日志级别必须是以下之一: {", ".join(valid_levels)}')
        return v.upper()


class MCPToolsConfig(BaseModel):
    """MCP工具配置"""
    translate_text_enabled: bool = Field(default=True, description="是否启用文本翻译工具")
    translate_file_enabled: bool = Field(default=True, description="是否启用文件翻译工具")
    batch_translation_enabled: bool = Field(default=True, description="是否启用批量翻译工具")
    max_file_size_mb: int = Field(default=10, description="最大文件大小(MB)")
    max_batch_size: int = Field(default=50, description="最大批处理文件数")
    allowed_extensions: List[str] = Field(
        default=[".md", ".txt"], 
        description="允许的文件扩展名"
    )


class MCPSecurityConfig(BaseModel):
    """MCP安全配置"""
    enable_auth: bool = Field(default=False, description="是否启用认证")
    api_key: str = Field(default="", description="API密钥")
    allowed_ips: List[str] = Field(
        default=["127.0.0.1", "::1"], 
        description="允许的IP地址列表"
    )
    rate_limit: int = Field(default=100, description="每分钟请求数限制")
    enable_cors: bool = Field(default=True, description="是否启用CORS")


class MCPCacheConfig(BaseModel):
    """MCP缓存配置"""
    enabled: bool = Field(default=True, description="是否启用缓存")
    cache_dir: str = Field(default="data/mcp_cache", description="缓存目录")
    max_cache_size_mb: int = Field(default=100, description="最大缓存大小(MB)")
    ttl_seconds: int = Field(default=3600, description="缓存过期时间(秒)")


# DesktopConfig 已移除，因为桌面应用模块已取消


class TerminologyConfig(BaseModel):
    """术语库配置"""
    enhancement_enabled: bool = Field(default=True, description="是否启用简化术语库增强功能")
    enable_hybrid_mode: bool = Field(default=True, description="是否启用混合模式")
    fallback_to_traditional: bool = Field(default=True, description="是否降级到传统术语库")
    max_cache_size: int = Field(default=1000, ge=1, description="最大缓存条目数")
    cache_dir: str = Field(default="data/terminology_cache", description="缓存目录")
    quality_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="质量评估阈值")


class UnifiedConfig(BaseSettings):
    """统一配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )
    
    # 配置节
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    environments: EnvironmentsConfig = Field(default_factory=EnvironmentsConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    model_ollama: OllamaModelConfig = Field(default_factory=OllamaModelConfig)
    model_openai: OpenAIModelConfig = Field(default_factory=OpenAIModelConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    mcp: MCPServerConfig = Field(default_factory=MCPServerConfig)
    mcp_tools: MCPToolsConfig = Field(default_factory=MCPToolsConfig)
    mcp_security: MCPSecurityConfig = Field(default_factory=MCPSecurityConfig)
    mcp_cache: MCPCacheConfig = Field(default_factory=MCPCacheConfig)
    # desktop: DesktopConfig = Field(default_factory=DesktopConfig)  # 已移除
    terminology: TerminologyConfig = Field(default_factory=TerminologyConfig)
    
    def get_model_config(self) -> Union[OllamaModelConfig, OpenAIModelConfig]:
        """获取当前模型提供商的配置"""
        provider = self.model.provider
        
        if provider == "ollama":
            return self.model_ollama
        elif provider == "openai":
            return self.model_openai
        else:
            raise ConfigurationError(f"不支持的模型提供商: {provider}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的嵌套键
        
        Args:
            key: 配置键，支持 'section.setting' 格式
            default: 默认值
            
        Returns:
            配置值
        """
        if '.' in key:
            section, setting = key.split('.', 1)
            if hasattr(self, section):
                section_obj = getattr(self, section)
                if hasattr(section_obj, setting):
                    return getattr(section_obj, setting)
        elif hasattr(self, key):
            return getattr(self, key)
        
        return default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值，支持点号分隔的嵌套键
        
        Args:
            key: 配置键，支持 'section.setting' 格式
            value: 配置值
        """
        if '.' in key:
            section, setting = key.split('.', 1)
            if hasattr(self, section):
                section_obj = getattr(self, section)
                if hasattr(section_obj, setting):
                    setattr(section_obj, setting, value)
                    return
        
        raise ConfigurationError(f"无效的配置键: {key}")
    
    def validate(self) -> None:
        """验证配置的有效性"""
        try:
            # 验证模型配置
            provider = self.model.provider
            
            # 验证对应提供商的配置
            if provider == "ollama":
                if not self.model_ollama.host:
                    raise ConfigurationError("Ollama主机地址不能为空")
            elif provider == "openai":
                if not self.model_openai.api_key.strip():
                    raise ConfigurationError("OpenAI API密钥不能为空")
            
            # 验证翻译配置
            if self.translation.chunk_size < 0:
                raise ConfigurationError("文本分块大小不能小于0")
            
            # 验证CLI配置
            if self.cli.parallel_workers <= 0:
                raise ConfigurationError("并行工作线程数必须大于0")
            
            # 验证MCP配置
            if self.mcp.enabled:
                if not 1 <= self.mcp.port <= 65535:
                    raise ConfigurationError("MCP服务器端口必须在1-65535范围内")
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"配置验证失败: {str(e)}")