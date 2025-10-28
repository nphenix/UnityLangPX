"""
统一配置管理器

提供统一的配置管理功能，支持多层级配置、环境适配、
动态加载等功能。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .models import UnifiedConfig
from .performance_models import PerformanceSettings
from .loader import ConfigLoader, ConfigSearchPath
from ..core.exceptions import ConfigurationError


class UnifiedConfigManager:
    """统一配置管理器"""
    
    def __init__(self, 
                 config_dir: Optional[Union[str, Path]] = None,
                 environment: Optional[str] = None,
                 **runtime_args):
        """
        初始化统一配置管理器
        
        Args:
            config_dir: 配置目录路径
            environment: 环境名称
            **runtime_args: 运行时参数
        """
        self.config_dir = Path(config_dir) if config_dir else ConfigSearchPath.get_config_dir()
        self.environment = environment or self._detect_environment()
        self.runtime_args = runtime_args
        self._config_cache = None
    
    def _detect_environment(self) -> str:
        """
        自动检测当前环境
        
        Returns:
            环境名称：development, testing, production
        """
        # 1. 检查环境变量
        env = os.getenv("UNITYLANGPX_ENV", "").lower()
        if env in ["development", "testing", "production"]:
            return env
        
        # 2. 检查Python环境变量
        if os.getenv("DEBUG") == "1":
            return "development"
        
        # 3. 默认为开发环境
        return "development"
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        # 从项目根目录的config/default.toml加载
        project_root = Path(__file__).parent.parent.parent
        default_config_path = project_root / "config" / "default.toml"
        
        return ConfigLoader.load_config_file(default_config_path)
    
    def _get_environment_config(self) -> Dict[str, Any]:
        """
        获取环境特定配置
        
        Returns:
            环境配置字典
        """
        # 查找环境特定配置文件
        env_config_path = self.config_dir / f"{self.environment}.toml"
        
        if env_config_path.exists():
            return ConfigLoader.load_config_file(env_config_path)
        
        return {}
    
    def _get_user_config(self) -> Dict[str, Any]:
        """
        获取用户配置
        
        Returns:
            用户配置字典
        """
        user_config_path = Path.home() / ".unitylangpx" / "config.toml"
        
        if user_config_path.exists():
            return ConfigLoader.load_config_file(user_config_path)
        
        return {}
    
    def _get_project_config(self) -> Dict[str, Any]:
        """
        获取项目配置
        
        Returns:
            项目配置字典
        """
        project_config_path = Path(".unitylangpx") / "config.toml"
        
        if project_config_path.exists():
            return ConfigLoader.load_config_file(project_config_path)
        
        return {}
    
    def _get_environment_vars(self) -> Dict[str, Any]:
        """
        获取环境变量配置
        
        Returns:
            环境变量配置字典
        """
        return ConfigLoader.load_env_vars("UNITYLANGPX_")
    
    def _get_runtime_config(self) -> Dict[str, Any]:
        """
        获取运行时配置
        
        Returns:
            运行时配置字典
        """
        return ConfigLoader.load_command_line_args(self.runtime_args)
    
    def _merge_configs(self, base_config: Dict[str, Any], 
                    override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并配置字典
        
        Args:
            base_config: 基础配置
            override_config: 覆盖配置
            
        Returns:
            合并后的配置字典
        """
        def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """深度合并字典"""
            result = base.copy()
            
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = _deep_merge(result[key], value)
                else:
                    result[key] = value
            
            return result
        
        return _deep_merge(base_config, override_config)
    
    def load_config(self, force_reload: bool = False) -> UnifiedConfig:
        """
        加载完整配置
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            统一配置对象
        """
        # 使用缓存提高性能
        if self._config_cache is not None and not force_reload:
            return self._config_cache
        
        try:
            # 1. 加载默认配置
            config_dict = self._get_default_config()
            
            # 2. 依次加载并合并配置
            config_layers = [
                ("用户配置", self._get_user_config()),
                ("项目配置", self._get_project_config()),
                ("环境配置", self._get_environment_config()),
                ("环境变量", self._get_environment_vars()),
                ("运行时参数", self._get_runtime_config())
            ]
            
            for layer_name, layer_config in config_layers:
                if layer_config:
                    config_dict = self._merge_configs(config_dict, layer_config)
            
            # 3. 应用环境特定配置
            if self.environment in config_dict.get("environments", {}):
                env_specific = config_dict["environments"][self.environment]
                config_dict = self._merge_configs(config_dict, env_specific)
            
            # 4. 创建配置对象
            config = UnifiedConfig(**config_dict)
            
            # 5. 验证配置
            config.validate()
            
            # 6. 缓存配置
            self._config_cache = config
            
            return config
            
        except Exception as e:
            raise ConfigurationError(f"加载配置失败: {str(e)}")
    
    def get_component_config(self, component: str, force_reload: bool = False) -> Any:
        """
        获取特定组件的配置
        
        Args:
            component: 组件名称
            force_reload: 是否强制重新加载
            
        Returns:
            组件配置对象
        """
        unified_config = self.load_config(force_reload)
        
        if hasattr(unified_config, component):
            return getattr(unified_config, component)
        else:
            raise ConfigurationError(f"未知的配置组件: {component}")
    
    def get_performance_config(self, force_reload: bool = False) -> PerformanceSettings:
        """
        获取性能配置
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            性能配置对象
        """
        # 加载统一配置
        unified_config = self.load_config(force_reload)
        
        # 提取性能配置部分
        performance_dict = unified_config.get("performance", {})
        
        # 创建性能配置对象
        try:
            return PerformanceSettings(**performance_dict)
        except Exception as e:
            raise ConfigurationError(f"加载性能配置失败: {str(e)}")
    
    def get(self, key: str, default: Any = None, force_reload: bool = False) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持 'section.setting' 格式
            default: 默认值
            force_reload: 是否强制重新加载
            
        Returns:
            配置值
        """
        unified_config = self.load_config(force_reload)
        return unified_config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值（仅在内存中）
        
        Args:
            key: 配置键，支持 'section.setting' 格式
            value: 配置值
        """
        if self._config_cache is None:
            self.load_config()
        
        self._config_cache.set(key, value)
    
    def save_config(self, config_path: Optional[Union[str, Path]] = None) -> None:
        """
        保存当前配置到文件
        
        Args:
            config_path: 保存路径，默认为项目配置文件
        """
        if self._config_cache is None:
            self.load_config()
        
        if config_path is None:
            config_path = self.config_dir / "config.toml"
        else:
            config_path = Path(config_path)
        
        # 转换为字典并保存
        config_dict = self._config_cache.model_dump()
        ConfigLoader.save_toml(config_dict, config_path)
    
    def reload_config(self) -> UnifiedConfig:
        """
        重新加载配置
        
        Returns:
            重新加载的配置对象
        """
        self._config_cache = None
        return self.load_config(force_reload=True)
    
    def get_config_info(self) -> Dict[str, Any]:
        """
        获取配置信息
        
        Returns:
            配置信息字典
        """
        return {
            "config_dir": str(self.config_dir),
            "environment": self.environment,
            "runtime_args": self.runtime_args,
            "cache_loaded": self._config_cache is not None,
            "default_config_file": str(ConfigSearchPath.find_config_file("default.toml")),
            "user_config_file": str(Path.home() / ".unitylangpx" / "config.toml"),
            "project_config_file": str(Path(".unitylangpx") / "config.toml"),
            "environment_config_file": str(self.config_dir / f"{self.environment}.toml"),
        }
    
    def validate_config_file(self, file_path: Union[str, Path]) -> bool:
        """
        验证配置文件格式
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            是否有效
        """
        try:
            ConfigLoader.load_config_file(file_path)
            return True
        except Exception:
            return False
    
    def create_sample_config(self, output_path: Union[str, Path]) -> None:
        """
        创建示例配置文件
        
        Args:
            output_path: 输出路径
        """
        # 创建默认配置
        default_config = UnifiedConfig()
        config_dict = default_config.model_dump()
        
        # 保存为TOML格式
        ConfigLoader.save_toml(config_dict, output_path)


# 便捷函数
def load_unified_config(config_dir: Optional[str] = None, 
                     environment: Optional[str] = None,
                     **runtime_args) -> UnifiedConfig:
    """
    加载统一配置
    
    Args:
        config_dir: 配置目录
        environment: 环境名称
        **runtime_args: 运行时参数
        
    Returns:
        统一配置对象
    """
    manager = UnifiedConfigManager(config_dir, environment, **runtime_args)
    return manager.load_config()


def get_config_manager(config_dir: Optional[str] = None,
                     environment: Optional[str] = None,
                     **runtime_args) -> UnifiedConfigManager:
    """
    获取配置管理器实例
    
    Args:
        config_dir: 配置目录
        environment: 环境名称
        **runtime_args: 运行时参数
        
    Returns:
        配置管理器实例
    """
    return UnifiedConfigManager(config_dir, environment, **runtime_args)