# UnityLangPX 配置管理指南

## 概述

本指南详细说明UnityLangPX项目的配置管理方案，包括使用Pydantic Settings进行类型安全的配置管理，以及Loguru和Rich库的使用。

## 配置管理架构

### Pydantic Settings 简介

Pydantic Settings是一个基于Pydantic的配置管理库，提供以下优势：
- **类型安全**：自动类型验证和转换
- **环境变量支持**：从环境变量自动加载配置
- **嵌套配置**：支持复杂的嵌套配置结构
- **默认值**：支持配置项的默认值
- **配置验证**：自动验证配置项的有效性

### 配置模型设计

```python
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class SourceLanguage(str, Enum):
    EN = "en"
    ZH = "zh"
    AUTO = "auto"

class TargetLanguage(str, Enum):
    EN = "en"
    ZH = "zh"

class OllamaConfig(BaseModel):
    """Ollama配置"""
    host: str = Field(default="http://localhost:11434", description="Ollama服务地址")
    model: str = Field(default="SimonPu/Hunyuan-MT-Chimera-7B:Q8", description="翻译模型")
    timeout: int = Field(default=60, description="请求超时时间(秒)")
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试延迟(秒)")
    
    @validator('host')
    def validate_host(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('host必须以http://或https://开头')
        return v

class TranslationConfig(BaseModel):
    """翻译配置"""
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="生成温度")
    max_tokens: int = Field(default=4000, gt=0, description="最大生成令牌数")
    chunk_size: int = Field(default=1000, gt=0, description="文本分块大小")
    overlap: int = Field(default=100, ge=0, description="分块重叠大小")
    source_language: SourceLanguage = Field(default=SourceLanguage.EN, description="源语言")
    target_language: TargetLanguage = Field(default=SourceLanguage.ZH, description="目标语言")
    preserve_format: bool = Field(default=True, description="保留原始格式")
    
    @validator('overlap')
    def validate_overlap(cls, v, values):
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('overlap必须小于chunk_size')
        return v

class CLIConfig(BaseModel):
    """CLI配置"""
    input_dir: str = Field(default="input", description="输入目录")
    output_dir: str = Field(default="output", description="输出目录")
    preserve_structure: bool = Field(default=True, description="保留目录结构")
    parallel_workers: int = Field(default=4, gt=0, description="并行工作线程数")
    show_progress: bool = Field(default=True, description="显示进度条")
    
    @validator('parallel_workers')
    def validate_parallel_workers(cls, v):
        if v > 16:
            raise ValueError('parallel_workers不应超过16')
        return v

class DesktopConfig(BaseModel):
    """桌面应用配置"""
    window_width: int = Field(default=800, gt=0, description="窗口宽度")
    window_height: int = Field(default=600, gt=0, description="窗口高度")
    theme: str = Field(default="light", description="主题(light/dark)")
    auto_save: bool = Field(default=True, description="自动保存配置")
    remember_window_state: bool = Field(default=True, description="记住窗口状态")

class CacheConfig(BaseModel):
    """缓存配置"""
    enable_cache: bool = Field(default=True, description="启用缓存")
    cache_dir: str = Field(default=".translation_cache", description="缓存目录")
    max_cache_size_mb: int = Field(default=500, gt=0, description="最大缓存大小(MB)")
    cache_ttl_days: int = Field(default=30, gt=0, description="缓存有效期(天)")

class LoggingConfig(BaseModel):
    """日志配置"""
    level: LogLevel = Field(default=LogLevel.INFO, description="日志级别")
    file: Optional[str] = Field(default="translation.log", description="日志文件路径")
    max_size_mb: int = Field(default=10, gt=0, description="日志文件最大大小(MB)")
    backup_count: int = Field(default=5, ge=0, description="日志备份数量")
    format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        description="日志格式"
    )
    enable_console: bool = Field(default=True, description="启用控制台输出")
    enable_file: bool = Field(default=True, description="启用文件输出")

class PerformanceConfig(BaseModel):
    """性能配置"""
    monitor_performance: bool = Field(default=True, description="监控性能")
    memory_limit_mb: int = Field(default=1024, gt=0, description="内存限制(MB)")
    enable_profiling: bool = Field(default=False, description="启用性能分析")
    profile_output_dir: str = Field(default="profiles", description="性能分析输出目录")

class TimeSeriesConfig(BaseModel):
    """时序数据配置(未来功能)"""
    enable_time_series: bool = Field(default=False, description="启用时序数据功能")
    data_source: str = Field(default="", description="数据源")
    update_interval: int = Field(default=5, gt=0, description="更新间隔(秒)")
    max_data_points: int = Field(default=1000, gt=0, description="最大数据点数")

class Settings(BaseSettings):
    """主配置类"""
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)
    desktop: DesktopConfig = Field(default_factory=DesktopConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    time_series: TimeSeriesConfig = Field(default_factory=TimeSeriesConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False

# 全局配置实例
settings = Settings()
```

## 日志管理

### Loguru 简介

Loguru是一个旨在使Python日志记录变得简单、更强大的库，提供以下特性：
- **简洁的API**：无需配置即可使用
- **丰富的处理器**：支持文件、控制台、网络等多种输出
- **自动轮转**：自动处理日志轮转和压缩
- **异常捕获**：自动捕获和记录异常
- **结构化日志**：支持添加额外上下文信息

### 日志配置

```python
import sys
from pathlib import Path
from loguru import logger
from typing import Optional

def setup_logging(config: LoggingConfig) -> None:
    """设置日志配置"""
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    if config.enable_console:
        logger.add(
            sys.stderr,
            level=config.level,
            format=config.format,
            colorize=True
        )
    
    # 添加文件处理器
    if config.enable_file and config.file:
        log_path = Path(config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_path,
            level=config.level,
            format=config.format,
            rotation=f"{config.max_size_mb} MB",
            retention=config.backup_count,
            compression="zip",
            encoding="utf-8"
        )

# 使用示例
def log_example():
    """日志使用示例"""
    # 基本日志
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")
    
    # 带上下文的日志
    logger.bind(user_id=123, action="translate").info("开始翻译文件")
    
    # 异常捕获
    try:
        result = 1 / 0
    except ZeroDivisionError:
        logger.exception("除零错误")
    
    # 性能测量
    with logger.level("DEBUG"):
        logger.debug("调试信息")
```

## CLI美化

### Rich 简介

Rich是一个Python库，用于在终端中创建美观的输出，提供以下特性：
- **丰富的文本样式**：支持颜色、粗体、斜体等
- **进度条**：多种样式的进度条
- **表格**：美观的表格显示
- **语法高亮**：代码语法高亮
- **树形结构**：文件树和目录树显示

### Rich配置

```python
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from typing import List, Dict, Any

class RichUI:
    """Rich UI管理类"""
    
    def __init__(self):
        self.console = Console()
    
    def create_progress(self, description: str = "处理中...") -> Progress:
        """创建进度条"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )
    
    def create_table(self, headers: List[str], data: List[List[Any]]) -> Table:
        """创建表格"""
        table = Table(show_header=True, header_style="bold magenta")
        
        # 添加列
        for header in headers:
            table.add_column(header)
        
        # 添加行
        for row in data:
            table.add_row(*[str(cell) for cell in row])
        
        return table
    
    def create_panel(self, content: str, title: str = "") -> Panel:
        """创建面板"""
        return Panel(content, title=title, border_style="blue")
    
    def create_tree(self, label: str) -> Tree:
        """创建树形结构"""
        return Tree(label, guide_style="bold bright_blue")
    
    def print_success(self, message: str) -> None:
        """打印成功消息"""
        self.console.print(f"✅ {message}", style="bold green")
    
    def print_error(self, message: str) -> None:
        """打印错误消息"""
        self.console.print(f"❌ {message}", style="bold red")
    
    def print_warning(self, message: str) -> None:
        """打印警告消息"""
        self.console.print(f"⚠️ {message}", style="bold yellow")
    
    def print_info(self, message: str) -> None:
        """打印信息消息"""
        self.console.print(f"ℹ️ {message}", style="bold blue")

# 全局Rich UI实例
rich_ui = RichUI()
```

## 配置使用示例

### 基本使用

```python
from src.config import settings, setup_logging
from src.logging import logger
from src.ui import rich_ui

def main():
    # 设置日志
    setup_logging(settings.logging)
    
    # 使用配置
    logger.info(f"Ollama服务地址: {settings.ollama.host}")
    logger.info(f"翻译模型: {settings.ollama.model}")
    
    # 使用Rich UI
    rich_ui.print_success("配置加载成功")
    
    # 显示配置表格
    config_data = [
        ["配置项", "值"],
        ["Ollama主机", settings.ollama.host],
        ["翻译模型", settings.ollama.model],
        ["日志级别", settings.logging.level],
        ["并行工作线程", settings.cli.parallel_workers]
    ]
    
    table = rich_ui.create_table(config_data[0], config_data[1:])
    rich_ui.console.print(table)
```

### 环境变量配置

```bash
# .env文件示例
OLLAMA__HOST=http://localhost:11434
OLLAMA__MODEL=SimonPu/Hunyuan-MT-Chimera-7B:Q8
TRANSLATION__TEMPERATURE=0.1
TRANSLATION__MAX_TOKENS=4000
CLI__PARALLEL_WORKERS=4
LOGGING__LEVEL=INFO
LOGGING__FILE=translation.log
```

### 配置验证

```python
from pydantic import ValidationError

def validate_config():
    """验证配置"""
    try:
        # 创建配置实例会自动验证
        settings = Settings()
        rich_ui.print_success("配置验证通过")
        return True
    except ValidationError as e:
        rich_ui.print_error(f"配置验证失败: {e}")
        return False
```

## 配置文件管理

### 配置文件模板

```python
def create_config_template(file_path: str = "config/.env.template"):
    """创建配置文件模板"""
    template = """# UnityLangPX 配置文件模板
# 复制此文件为.env并修改相应值

# Ollama配置
OLLAMA__HOST=http://localhost:11434
OLLAMA__MODEL=SimonPu/Hunyuan-MT-Chimera-7B:Q8
OLLAMA__TIMEOUT=60
OLLAMA__MAX_RETRIES=3
OLLAMA__RETRY_DELAY=1.0

# 翻译配置
TRANSLATION__TEMPERATURE=0.1
TRANSLATION__MAX_TOKENS=4000
TRANSLATION__CHUNK_SIZE=1000
TRANSLATION__OVERLAP=100
TRANSLATION__SOURCE_LANGUAGE=en
TRANSLATION__TARGET_LANGUAGE=zh
TRANSLATION__PRESERVE_FORMAT=true

# CLI配置
CLI__INPUT_DIR=input
CLI__OUTPUT_DIR=output
CLI__PRESERVE_STRUCTURE=true
CLI__PARALLEL_WORKERS=4
CLI__SHOW_PROGRESS=true

# 桌面应用配置
DESKTOP__WINDOW_WIDTH=800
DESKTOP__WINDOW_HEIGHT=600
DESKTOP__THEME=light
DESKTOP__AUTO_SAVE=true
DESKTOP__REMEMBER_WINDOW_STATE=true

# 缓存配置
CACHE__ENABLE_CACHE=true
CACHE__CACHE_DIR=.translation_cache
CACHE__MAX_CACHE_SIZE_MB=500
CACHE__CACHE_TTL_DAYS=30

# 日志配置
LOGGING__LEVEL=INFO
LOGGING__FILE=translation.log
LOGGING__MAX_SIZE_MB=10
LOGGING__BACKUP_COUNT=5
LOGGING__ENABLE_CONSOLE=true
LOGGING__ENABLE_FILE=true

# 性能配置
PERFORMANCE__MONITOR_PERFORMANCE=true
PERFORMANCE__MEMORY_LIMIT_MB=1024
PERFORMANCE__ENABLE_PROFILING=false
PERFORMANCE__PROFILE_OUTPUT_DIR=profiles

# 时序数据配置(未来功能)
TIME_SERIES__ENABLE_TIME_SERIES=false
TIME_SERIES__DATA_SOURCE=
TIME_SERIES__UPDATE_INTERVAL=5
TIME_SERIES__MAX_DATA_POINTS=1000
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(template)
    
    rich_ui.print_success(f"配置模板已创建: {file_path}")
```

## 最佳实践

1. **配置分层**：使用嵌套配置结构，将相关配置组织在一起
2. **环境变量**：敏感配置使用环境变量，避免硬编码
3. **配置验证**：使用Pydantic的验证器确保配置有效性
4. **默认值**：为所有配置项提供合理的默认值
5. **配置文档**：为每个配置项提供清晰的描述和示例
6. **日志级别**：根据环境调整日志级别，开发环境使用DEBUG，生产环境使用INFO或WARNING
7. **日志轮转**：配置日志轮转，避免日志文件过大
8. **Rich UI**：使用Rich美化CLI输出，提升用户体验

## 总结

通过使用Pydantic Settings、Loguru和Rich库，UnityLangPX项目获得了：
- 类型安全的配置管理
- 强大的日志功能
- 美观的CLI界面

这些工具不仅提高了开发效率，还增强了用户体验和系统的可维护性。