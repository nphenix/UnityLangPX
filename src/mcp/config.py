"""
UnityLangPX MCP服务器配置管理模块

扩展核心配置系统，添加MCP服务器特定的配置选项。
"""

import os
from typing import Optional, Dict, Any, List
from pathlib import Path

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..core.config import Config as CoreConfig
from ..core.exceptions import ConfigurationError


class MCPServerConfig(BaseModel):
    """MCP服务器配置"""
    enabled: bool = Field(default=True, description="是否启用MCP服务器")
    host: str = Field(default="localhost", description="服务器主机地址")
    port: int = Field(default=4010, description="服务器端口")
    max_connections: int = Field(default=10, description="最大连接数")
    request_timeout: int = Field(default=120, description="请求超时时间(秒)")
    log_level: str = Field(default="INFO", description="日志级别")
    enable_http_server: bool = Field(default=True, description="是否启用HTTP服务器提供静态文件")
    http_port: int = Field(default=4011, description="HTTP服务器端口")
    static_dir: str = Field(default="static", description="静态文件目录")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('端口号必须在1-65535范围内')
        return v
    
    @validator('http_port')
    def validate_http_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('HTTP服务器端口必须在1-65535范围内')
        return v
    
    @validator('log_level')
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
    
    @validator('max_file_size_mb')
    def validate_max_file_size(cls, v):
        if v <= 0:
            raise ValueError('最大文件大小必须大于0')
        return v
    
    @validator('max_batch_size')
    def validate_max_batch_size(cls, v):
        if v <= 0:
            raise ValueError('最大批处理大小必须大于0')
        return v


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
    
    @validator('rate_limit')
    def validate_rate_limit(cls, v):
        if v <= 0:
            raise ValueError('请求限制必须大于0')
        return v


class MCPCacheConfig(BaseModel):
    """MCP缓存配置"""
    enabled: bool = Field(default=True, description="是否启用缓存")
    cache_dir: str = Field(default="data/mcp_cache", description="缓存目录")
    max_cache_size_mb: int = Field(default=100, description="最大缓存大小(MB)")
    ttl_seconds: int = Field(default=3600, description="缓存过期时间(秒)")
    
    @validator('max_cache_size_mb')
    def validate_max_cache_size(cls, v):
        if v <= 0:
            raise ValueError('最大缓存大小必须大于0')
        return v
    
    @validator('ttl_seconds')
    def validate_ttl(cls, v):
        if v <= 0:
            raise ValueError('缓存过期时间必须大于0')
        return v


class MCPConfig(BaseSettings):
    """MCP配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )
    
    # MCP配置节
    server: MCPServerConfig = Field(default_factory=MCPServerConfig)
    tools: MCPToolsConfig = Field(default_factory=MCPToolsConfig)
    security: MCPSecurityConfig = Field(default_factory=MCPSecurityConfig)
    cache: MCPCacheConfig = Field(default_factory=MCPCacheConfig)
    
    def __init__(self, config_file: Optional[str] = None, **kwargs):
        """
        初始化MCP配置
        
        Args:
            config_file: 配置文件路径
            **kwargs: 额外的配置参数
        """
        super().__init__(**kwargs)
        
        # 加载TOML配置文件
        if config_file is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / "config" / "default.toml"
        
        self._load_toml_config(config_file)
        
        # 应用环境变量
        self._apply_env_vars()
        
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
            raise ConfigurationError(f"加载MCP配置文件失败: {str(e)}")
    
    def _update_nested_config(self, config_obj: BaseModel, config_dict: Dict[str, Any]) -> None:
        """递归更新嵌套配置"""
        for key, value in config_dict.items():
            if hasattr(config_obj, key):
                attr = getattr(config_obj, key)
                if isinstance(attr, BaseModel) and isinstance(value, dict):
                    self._update_nested_config(attr, value)
                else:
                    setattr(config_obj, key, value)
    
    def _apply_env_vars(self) -> None:
        """应用环境变量"""
        # 服务器配置
        if os.getenv("UNITYLANGPX_MCP_ENABLED"):
            self.server.enabled = os.getenv("UNITYLANGPX_MCP_ENABLED").lower() == "true"
        
        if os.getenv("UNITYLANGPX_MCP_HOST"):
            self.server.host = os.getenv("UNITYLANGPX_MCP_HOST")
        
        if os.getenv("UNITYLANGPX_MCP_PORT"):
            self.server.port = int(os.getenv("UNITYLANGPX_MCP_PORT"))
        
        if os.getenv("UNITYLANGPX_MCP_LOG_LEVEL"):
            self.server.log_level = os.getenv("UNITYLANGPX_MCP_LOG_LEVEL")
        
        if os.getenv("UNITYLANGPX_MCP_ENABLE_HTTP_SERVER"):
            self.server.enable_http_server = os.getenv("UNITYLANGPX_MCP_ENABLE_HTTP_SERVER").lower() == "true"
        
        if os.getenv("UNITYLANGPX_MCP_HTTP_PORT"):
            self.server.http_port = int(os.getenv("UNITYLANGPX_MCP_HTTP_PORT"))
        
        if os.getenv("UNITYLANGPX_MCP_STATIC_DIR"):
            self.server.static_dir = os.getenv("UNITYLANGPX_MCP_STATIC_DIR")
        
        # 安全配置
        if os.getenv("UNITYLANGPX_MCP_API_KEY"):
            self.security.api_key = os.getenv("UNITYLANGPX_MCP_API_KEY")
        
        if os.getenv("UNITYLANGPX_MCP_RATE_LIMIT"):
            self.security.rate_limit = int(os.getenv("UNITYLANGPX_MCP_RATE_LIMIT"))
        
        # Ollama配置
        if os.getenv("OLLAMA_HOST"):
            # 这里会传递给核心配置
            pass
        
        if os.getenv("OLLAMA_MODEL"):
            # 这里会传递给核心配置
            pass
    
    def _apply_kwargs(self, kwargs: Dict[str, Any]) -> None:
        """应用通过kwargs传入的配置参数"""
        for key, value in kwargs.items():
            if '__' in key:
                # 处理嵌套配置，如 server__host
                parts = key.split('__')
                if len(parts) == 2:
                    section, setting = parts
                    if hasattr(self, section):
                        section_obj = getattr(self, section)
                        if hasattr(section_obj, setting):
                            setattr(section_obj, setting, value)
            elif hasattr(self, key):
                setattr(self, key, value)
    
    def get_core_config(self) -> CoreConfig:
        """获取核心配置"""
        # 创建核心配置，应用MCP特定的设置
        core_config = CoreConfig()
        
        # 应用Ollama配置
        if os.getenv("OLLAMA_HOST"):
            core_config.model_ollama.host = os.getenv("OLLAMA_HOST")
        
        if os.getenv("OLLAMA_MODEL"):
            core_config.model_ollama.model = os.getenv("OLLAMA_MODEL")
        
        return core_config
    
    def validate(self) -> None:
        """验证配置的有效性"""
        try:
            # 验证服务器配置
            if self.server.enabled:
                if not self.server.host:
                    raise ConfigurationError("服务器主机地址不能为空")
                
                if not 1 <= self.server.port <= 65535:
                    raise ConfigurationError("服务器端口必须在1-65535范围内")
            
            # 验证安全配置
            if self.security.enable_auth and not self.security.api_key:
                raise ConfigurationError("启用认证时API密钥不能为空")
            
            # 验证工具配置
            if self.tools.max_file_size_mb <= 0:
                raise ConfigurationError("最大文件大小必须大于0")
            
            if self.tools.max_batch_size <= 0:
                raise ConfigurationError("最大批处理大小必须大于0")
            
            # 验证缓存配置
            if self.cache.enabled:
                cache_dir = Path(self.cache.cache_dir)
                if not cache_dir.exists():
                    cache_dir.mkdir(parents=True, exist_ok=True)
                
                if self.cache.max_cache_size_mb <= 0:
                    raise ConfigurationError("最大缓存大小必须大于0")
                
                if self.cache.ttl_seconds <= 0:
                    raise ConfigurationError("缓存过期时间必须大于0")
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"MCP配置验证失败: {str(e)}")
    
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
                    setattr(section_obj, setting)
                    return
        
        raise ConfigurationError(f"无效的配置键: {key}")
    
    def save(self, config_file: Optional[Path] = None) -> None:
        """
        保存配置到TOML文件
        
        Args:
            config_file: 配置文件路径
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
            raise ConfigurationError(f"保存MCP配置文件失败: {str(e)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"MCPConfig(server={self.server.host}:{self.server.port}, enabled={self.server.enabled})"


# 便捷函数
def load_mcp_config(config_file: Optional[str] = None, **kwargs) -> MCPConfig:
    """
    加载MCP配置
    
    Args:
        config_file: 配置文件路径
        **kwargs: 额外的配置参数
        
    Returns:
        MCP配置实例
    """
    config = MCPConfig(config_file, **kwargs)
    config.validate()
    return config


def get_default_mcp_config() -> MCPConfig:
    """
    获取默认MCP配置
    
    Returns:
        默认MCP配置实例
    """
    return load_mcp_config()