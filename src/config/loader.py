"""
配置加载器模块

提供多种格式的配置文件加载功能，包括TOML、JSON、
环境变量等。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union

from ..core.exceptions import ConfigurationError


class ConfigLoader:
    """配置加载器类"""
    
    @staticmethod
    def load_toml(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载TOML配置文件
        
        Args:
            file_path: TOML文件路径
            
        Returns:
            配置字典
            
        Raises:
            ConfigurationError: 加载失败时抛出
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {}
        
        try:
            import toml
            with open(file_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            raise ConfigurationError(f"加载TOML文件失败 {file_path}: {str(e)}")
    
    @staticmethod
    def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载JSON配置文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            配置字典
            
        Raises:
            ConfigurationError: 加载失败时抛出
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise ConfigurationError(f"加载JSON文件失败 {file_path}: {str(e)}")
    
    @staticmethod
    def load_env_vars(prefix: str = "UNITYLANGPX_") -> Dict[str, Any]:
        """
        加载环境变量
        
        Args:
            prefix: 环境变量前缀
            
        Returns:
            环境变量配置字典
        """
        env_config = {}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                
                # 处理嵌套键，如 UNITYLANGPX_MCP__HOST
                if '__' in config_key:
                    parts = config_key.split('__')
                    if len(parts) == 2:
                        section, setting = parts
                        if section not in env_config:
                            env_config[section] = {}
                        env_config[section][setting] = value
                else:
                    env_config[config_key] = value
        
        return env_config
    
    @staticmethod
    def load_command_line_args(args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        加载命令行参数
        
        Args:
            args: 命令行参数字典
            
        Returns:
            命令行参数配置字典
        """
        if args is None:
            return {}
        
        return args.copy()
    
    @staticmethod
    def detect_config_format(file_path: Union[str, Path]) -> str:
        """
        检测配置文件格式
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            配置格式：'toml', 'json', 或 'unknown'
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        
        if suffix == '.toml':
            return 'toml'
        elif suffix == '.json':
            return 'json'
        else:
            return 'unknown'
    
    @staticmethod
    def load_config_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        自动检测格式并加载配置文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            配置字典
            
        Raises:
            ConfigurationError: 不支持的格式或加载失败时抛出
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {}
        
        format_type = ConfigLoader.detect_config_format(file_path)
        
        if format_type == 'toml':
            return ConfigLoader.load_toml(file_path)
        elif format_type == 'json':
            return ConfigLoader.load_json(file_path)
        else:
            raise ConfigurationError(f"不支持的配置文件格式: {file_path}")
    
    @staticmethod
    def save_toml(config: Dict[str, Any], file_path: Union[str, Path]) -> None:
        """
        保存配置为TOML格式
        
        Args:
            config: 配置字典
            file_path: 保存路径
            
        Raises:
            ConfigurationError: 保存失败时抛出
        """
        file_path = Path(file_path)
        
        try:
            import toml
            
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                toml.dump(config, f)
                
        except Exception as e:
            raise ConfigurationError(f"保存TOML文件失败 {file_path}: {str(e)}")
    
    @staticmethod
    def save_json(config: Dict[str, Any], file_path: Union[str, Path], indent: int = 2) -> None:
        """
        保存配置为JSON格式
        
        Args:
            config: 配置字典
            file_path: 保存路径
            indent: JSON缩进空格数
            
        Raises:
            ConfigurationError: 保存失败时抛出
        """
        file_path = Path(file_path)
        
        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=indent, ensure_ascii=False)
                
        except Exception as e:
            raise ConfigurationError(f"保存JSON文件失败 {file_path}: {str(e)}")


class ConfigSearchPath:
    """配置文件搜索路径管理"""
    
    DEFAULT_SEARCH_PATHS = [
        Path("config/default.toml"),
        Path(".unitylangpx/config.toml"),
        Path("~/.unitylangpx/config.toml").expanduser(),
    ]
    
    @staticmethod
    def find_config_file(name: str = "default.toml") -> Optional[Path]:
        """
        查找配置文件
        
        Args:
            name: 配置文件名
            
        Returns:
            找到的配置文件路径，未找到返回None
        """
        search_paths = [
            Path(f"config/{name}"),
            Path(f".unitylangpx/{name}"),
            Path(f"~/.unitylangpx/{name}").expanduser(),
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    @staticmethod
    def get_config_dir() -> Path:
        """
        获取配置目录路径
        
        Returns:
            配置目录路径
        """
        # 优先使用项目配置目录
        project_config = Path(".unitylangpx")
        if project_config.exists():
            return project_config
        
        # 其次使用用户配置目录
        user_config = Path("~/.unitylangpx").expanduser()
        return user_config