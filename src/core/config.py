"""
UnityLangPX 配置管理模块

这个模块使用Pydantic Settings来管理应用配置，支持从TOML文件、
环境变量和命令行参数加载配置。
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ConfigurationError


class ModelConfig(BaseModel):
    """模型相关配置"""
    provider: str = Field(default="ollama", description="模型提供商")
    
    @validator('provider')
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
    
    @validator('host')
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
    
    @validator('base_url')
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('API基础URL必须以http://或https://开头')
        return v
    
    @validator('api_key')
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
    
    @validator('overlap')
    def validate_overlap(cls, v, values):
        # 只有当chunk_size > 0时才验证
        if 'chunk_size' in values and values['chunk_size'] > 0 and v >= values['chunk_size']:
            raise ValueError('重叠大小不能大于等于分块大小')
        return v


class CLIConfig(BaseModel):
    """命令行工具配置"""
    input_dir: str = Field(default="input", description="输入目录")
    output_dir: str = Field(default="output", description="输出目录")
    preserve_structure: bool = Field(default=True, description="保持目录结构")
    parallel_workers: int = Field(default=4, ge=1, le=16, description="并行工作线程数")
    
    @validator('input_dir', 'output_dir')
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
    
    @validator('level')
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


class TranslationStatusConfig(BaseModel):
    """翻译状态管理配置"""
    enable_status_tracking: bool = Field(default=True, description="是否启用状态跟踪")
    status_file: str = Field(default=".translation_status.json", description="状态文件路径")
    auto_retry_failed: bool = Field(default=True, description="是否自动重试失败的文件")
    max_retry_attempts: int = Field(default=2, ge=0, description="最大重试次数")


class TerminologyConfig(BaseModel):
    """术语库配置"""
    enhancement_enabled: bool = Field(default=True, description="是否启用简化术语库增强功能")
    enable_hybrid_mode: bool = Field(default=True, description="是否启用混合模式")
    fallback_to_traditional: bool = Field(default=True, description="是否降级到传统术语库")
    max_cache_size: int = Field(default=1000, ge=1, description="最大缓存条目数")
    cache_dir: str = Field(default="data/terminology_cache", description="缓存目录")
    quality_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="质量评估阈值")


class Config(BaseSettings):
    """UnityLangPX主配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )
    
    # 模型配置
    model: ModelConfig = Field(default_factory=ModelConfig)
    model_ollama: OllamaModelConfig = Field(default_factory=OllamaModelConfig)
    model_openai: OpenAIModelConfig = Field(default_factory=OpenAIModelConfig)
    
    # 其他配置
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    translation_status: TranslationStatusConfig = Field(default_factory=TranslationStatusConfig)
    terminology: TerminologyConfig = Field(default_factory=TerminologyConfig)
    
    def __init__(self, config_file: Optional[str] = None, **kwargs):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径，默认为 config/default.toml
            **kwargs: 额外的配置参数，会覆盖配置文件中的设置
        """
        super().__init__(**kwargs)
        
        # 加载TOML配置文件
        if config_file is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / "config" / "default.toml"
        
        self._load_toml_config(config_file)
        
        # 应用通过kwargs传入的配置
        self._apply_kwargs(kwargs)
    
    def _load_toml_config(self, config_file: Path) -> None:
        """从TOML文件加载配置"""
        if not config_file.exists():
            return
        
        try:
            import toml
            with open(config_file, 'r', encoding='utf-8') as f:
                toml_config = toml.load(f)
            
            # 递归更新配置
            self._update_nested_config(self, toml_config)
            
        except Exception as e:
            raise ConfigurationError(f"加载配置文件失败: {str(e)}")
    
    def _update_nested_config(self, config_obj: BaseModel, config_dict: Dict[str, Any]) -> None:
        """递归更新嵌套配置"""
        for key, value in config_dict.items():
            if hasattr(config_obj, key):
                attr = getattr(config_obj, key)
                if isinstance(attr, BaseModel) and isinstance(value, dict):
                    self._update_nested_config(attr, value)
                else:
                    setattr(config_obj, key, value)
    
    def _apply_kwargs(self, kwargs: Dict[str, Any]) -> None:
        """应用通过kwargs传入的配置参数"""
        for key, value in kwargs.items():
            if '__' in key:
                # 处理嵌套配置，如 ollama__host
                parts = key.split('__')
                if len(parts) == 2:
                    section, setting = parts
                    if hasattr(self, section):
                        section_obj = getattr(self, section)
                        if hasattr(section_obj, setting):
                            setattr(section_obj, setting, value)
            elif hasattr(self, key):
                setattr(self, key, value)
    
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
    
    def save(self, config_file: Optional[Path] = None) -> None:
        """
        保存配置到TOML文件
        
        Args:
            config_file: 配置文件路径，默认为原配置文件
        """
        if config_file is None:
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / "config" / "default.toml"
        
        try:
            import toml
            
            # 转换为字典
            config_dict = self.model_dump()
            
            # 确保目录存在
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(config_file, 'w', encoding='utf-8') as f:
                toml.dump(config_dict, f)
                
        except Exception as e:
            raise ConfigurationError(f"保存配置文件失败: {str(e)}")
    
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
            # 允许chunk_size为0，表示自动计算
            if self.translation.chunk_size < 0:
                raise ConfigurationError("文本分块大小不能小于0")
            
            # 验证CLI配置
            if self.cli.parallel_workers <= 0:
                raise ConfigurationError("并行工作线程数必须大于0")
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"配置验证失败: {str(e)}")
    
    def get_model_config(self):
        """获取当前模型提供商的配置"""
        provider = self.model.provider
        
        if provider == "ollama":
            return self.model_ollama
        elif provider == "openai":
            return self.model_openai
        else:
            raise ConfigurationError(f"不支持的模型提供商: {provider}")