# UnityLangPX 性能优化使用指南

本文档介绍如何使用UnityLangPX的性能优化功能，包括异步缓存、智能分块、性能监控和错误处理等组件。

## 目录

1. [快速开始](#快速开始)
2. [配置说明](#配置说明)
3. [异步缓存](#异步缓存)
4. [智能分块](#智能分块)
5. [性能监控](#性能监控)
6. [错误处理](#错误处理)
7. [集成使用](#集成使用)
8. [性能调优](#性能调优)
9. [故障排除](#故障排除)

## 快速开始

### 基本使用

```python
import asyncio
from src.core.performance_integration import get_performance_optimizer

async def main():
    # 获取性能优化器
    optimizer = get_performance_optimizer()
    
    # 使用上下文管理器自动初始化和清理
    async with optimizer:
        # 翻译文本
        result = await optimizer.translate_text(
            text="Hello, world!",
            source_lang="en",
            target_lang="zh"
        )
        print(result)
        
        # 翻译文件
        from pathlib import Path
        await optimizer.translate_file(
            file_path=Path("example.md"),
            source_lang="en",
            target_lang="zh"
        )
        
        # 批量翻译
        texts = ["Hello", "World", "UnityLangPX"]
        results = await optimizer.batch_translate(
            texts=texts,
            source_lang="en",
            target_lang="zh"
        )
        print(results)

if __name__ == "__main__":
    asyncio.run(main())
```

### 便捷函数

```python
from src.core.performance_integration import (
    translate_with_optimization,
    translate_file_with_optimization,
    batch_translate_with_optimization
)

# 单独翻译文本
result = await translate_with_optimization(
    text="Hello, world!",
    source_lang="en",
    target_lang="zh"
)

# 翻译文件
result_path = await translate_file_with_optimization(
    file_path=Path("example.md"),
    source_lang="en",
    target_lang="zh"
)

# 批量翻译
results = await batch_translate_with_optimization(
    texts=["Hello", "World"],
    source_lang="en",
    target_lang="zh"
)
```

## 配置说明

性能优化配置位于 `config/unified_config.toml` 文件的 `[performance]` 部分：

```toml
[performance.async_cache]
# L1缓存（内存）
l1_max_size = 1000
l1_ttl = 3600

# L2缓存（SQLite）
l2_max_size = 10000
l2_ttl = 86400
l2_db_path = "data/cache_l2.db"

# L3缓存（文件）
l3_enabled = true
l3_dir = "data/cache_l3"
l3_ttl = 604800

# 批量操作
batch_size = 100
batch_timeout = 5.0

# 压缩
enable_compression = true
compression_threshold = 1024

[performance.smart_chunker]
max_tokens = 4000
min_tokens = 200
overlap_tokens = 200
respect_code_blocks = true
respect_obsidian_syntax = true
preserve_structure = true
language = "en"

[performance.performance_monitor]
enabled = true
max_history = 1000
monitor_interval = 5.0
export_interval = 3600
export_dir = "data/performance"

# 告警配置
alert_cpu_threshold = 80.0
alert_cpu_critical = 95.0
alert_memory_threshold = 80.0
alert_memory_critical = 95.0
alert_disk_threshold = 90.0
alert_translation_threshold = 30.0
alert_translation_critical = 60.0
alert_api_error_rate = 0.1
alert_cache_hit_rate = 0.5

[performance.embedding]
enabled = true
provider = "sentence_transformer"  # sentence_transformer, ollama, openai
model_name = "bge-m3"
dimension = 1024
batch_size = 32
device = "auto"  # auto, cpu, cuda

# Ollama配置
ollama_base_url = "http://localhost:11434"

# OpenAI配置
openai_api_key = ""
openai_base_url = "https://api.openai.com/v1"
openai_model = "text-embedding-ada-002"
```

## 异步缓存

### 三级缓存架构

UnityLangPX实现了三级缓存系统：

1. **L1缓存（内存）**：最快的访问速度，使用LRU算法
2. **L2缓存（SQLite）**：中等速度，持久化存储
3. **L3缓存（文件）**：大容量存储，适合大型数据

### 直接使用缓存

```python
from src.core.async_cache import create_async_cache

async def cache_example():
    # 创建缓存实例
    cache = await create_async_cache()
    
    # 设置缓存
    await cache.set("key1", {"data": "value1"})
    
    # 获取缓存
    value = await cache.get("key1")
    print(value)
    
    # 批量设置
    await cache.batch_set({
        "key2": {"data": "value2"},
        "key3": {"data": "value3"}
    })
    
    # 获取统计信息
    stats = await cache.get_statistics()
    print(stats)
    
    # 清理缓存
    await cache.stop()
```

### 缓存配置调优

- **L1缓存大小**：根据可用内存调整，通常1000-5000个条目
- **TTL设置**：根据数据更新频率调整
- **批量大小**：根据网络延迟和吞吐量需求调整
- **压缩阈值**：大于1KB的数据启用压缩

## 智能分块

### 特性

- **语义感知**：按句子和段落边界分割
- **Obsidian语法保护**：特殊处理控制代码
- **内容类型识别**：区分可翻译和不可翻译内容
- **重叠优化**：智能添加上下文重叠

### 直接使用分块器

```python
from src.core.smart_chunker import SmartChunker
from src.config.performance_models import SmartChunkerConfig

async def chunker_example():
    # 创建配置
    config = SmartChunkerConfig(
        max_tokens=4000,
        overlap_tokens=200,
        respect_obsidian_syntax=True
    )
    
    # 创建分块器
    chunker = SmartChunker(config)
    
    # 分块文本
    text = "这是一个长文本..."
    chunks = await chunker.chunk_text(text)
    
    for chunk in chunks:
        print(f"块 {chunk.id}: {chunk.text[:100]}...")
    
    # 分块文件
    from pathlib import Path
    file_chunks = await chunker.chunk_file(Path("example.md"))
    
    # 重组文件
    await chunker.reassemble_file(file_chunks, Path("output.md"))
```

## 性能监控

### 监控指标

- **系统指标**：CPU、内存、磁盘使用率
- **应用指标**：翻译延迟、吞吐量、错误率
- **缓存指标**：命中率、大小、操作次数
- **自定义指标**：用户定义的业务指标

### 使用性能监控

```python
from src.core.performance_monitor import get_performance_monitor

async def monitor_example():
    # 获取监控器
    monitor = get_performance_monitor()
    
    # 启动监控
    monitor.start_monitoring(interval=5.0)
    
    # 添加自定义指标
    monitor.add_metric("custom_counter", 1.0, monitor.MetricType.COUNTER)
    monitor.record_timer("operation_duration", 2.5)
    
    # 获取统计信息
    stats = monitor.get_statistics()
    print(stats)
    
    # 获取活跃告警
    alerts = monitor.get_active_alerts()
    print(alerts)
    
    # 导出指标
    from pathlib import Path
    monitor.export_metrics(Path("metrics.json"))
    
    # 停止监控
    monitor.stop_monitoring()
```

### 告警配置

```python
from src.core.performance_monitor import PerformanceMonitor, Threshold, AlertSeverity

# 添加自定义告警阈值
monitor = get_performance_monitor()
monitor.add_threshold(Threshold(
    metric_name="custom_metric",
    operator=">",
    value=100.0,
    severity=AlertSeverity.WARNING,
    message_template="自定义指标过高: {current_value} > {threshold}"
))
```

## 错误处理

### 分层错误处理

- **错误分类**：按类别和严重程度分类
- **智能恢复**：自动重试、降级和用户干预
- **本地化信息**：中英文错误提示
- **错误统计**：详细的错误分析和历史记录

### 使用错误处理

```python
from src.core.enhanced_error_handling import get_error_handler

async def error_handling_example():
    # 获取错误处理器
    error_handler = get_error_handler()
    
    # 初始化
    await error_handler.initialize()
    
    try:
        # 可能出错的代码
        result = await some_risky_operation()
    except Exception as e:
        # 处理错误
        handled = await error_handler.handle_error(
            error=e,
            context={"operation": "some_risky_operation"},
            user_message="操作失败，请稍后重试"
        )
        
        if handled:
            print("错误已自动恢复")
        else:
            print("需要手动处理")
    
    # 获取错误统计
    stats = error_handler.get_statistics()
    print(stats)
```

## 集成使用

### 在MCP服务器中使用

```python
from src.core.performance_integration import get_performance_optimizer

class MCPServer:
    def __init__(self):
        self.optimizer = get_performance_optimizer()
    
    async def handle_translate_request(self, request):
        async with self.optimizer:
            # 处理翻译请求
            result = await self.optimizer.translate_text(
                text=request.text,
                source_lang=request.source_lang,
                target_lang=request.target_lang
            )
            return result
```

### 在CLI中使用

```python
from src.core.performance_integration import translate_file_with_optimization

async def cli_translate_command(file_path, source_lang, target_lang):
    try:
        result_path = await translate_file_with_optimization(
            file_path=Path(file_path),
            source_lang=source_lang,
            target_lang=target_lang
        )
        print(f"翻译完成: {result_path}")
    except Exception as e:
        print(f"翻译失败: {e}")
```

## 性能调优

### 缓存优化

1. **调整缓存大小**：
   - 增加L1缓存大小可以提高命中率，但消耗更多内存
   - L2缓存大小影响磁盘I/O性能

2. **优化TTL**：
   - 频繁更新的数据使用较短的TTL
   - 静态数据可以使用较长的TTL

3. **批量操作**：
   - 增加批量大小可以提高吞吐量
   - 但过大的批量可能增加延迟

### 分块优化

1. **令牌限制**：
   - 根据模型的最大令牌数调整
   - 考虑重叠和上下文需求

2. **重叠设置**：
   - 增加重叠可以提高翻译连贯性
   - 但会增加总工作量

### 监控优化

1. **监控间隔**：
   - 较短的间隔提供更实时的监控
   - 但会增加系统开销

2. **告警阈值**：
   - 根据历史数据设置合理的阈值
   - 避免误报和漏报

## 故障排除

### 常见问题

1. **缓存命中率低**：
   - 检查TTL设置是否过短
   - 增加缓存大小
   - 检查数据访问模式

2. **内存使用过高**：
   - 减少L1缓存大小
   - 启用压缩
   - 调整批量大小

3. **翻译速度慢**：
   - 检查网络连接
   - 优化分块策略
   - 增加并发数

4. **错误频繁**：
   - 检查错误处理配置
   - 调整重试策略
   - 检查系统资源

### 调试工具

```python
# 获取性能统计
optimizer = get_performance_optimizer()
stats = await optimizer.get_performance_stats()
print(stats)

# 健康检查
health = await optimizer.health_check()
print(health)

# 获取缓存统计
cache = get_async_cache()
cache_stats = await cache.get_statistics()
print(cache_stats)

# 获取错误统计
error_handler = get_error_handler()
error_stats = error_handler.get_statistics()
print(error_stats)
```

### 日志分析

启用详细日志：

```python
import logging
logging.getLogger("src.core").setLevel(logging.DEBUG)
```

关键日志位置：
- 缓存操作：`src.core.async_cache`
- 性能监控：`src.core.performance_monitor`
- 错误处理：`src.core.enhanced_error_handling`
- 分块操作：`src.core.smart_chunker`

## 最佳实践

1. **初始化**：使用上下文管理器确保正确的初始化和清理
2. **配置管理**：通过配置文件调整参数，避免硬编码
3. **错误处理**：始终使用try-catch包装异步操作
4. **监控**：定期检查性能指标和告警
5. **资源管理**：及时释放不需要的资源
6. **测试**：在不同负载下测试性能表现

## 更多信息

- [性能优化计划](workspace/design/performance/performance_optimization_plan.md)
- [配置参考](configuration_guide.md)
- [API文档](api_reference.md)
- [故障排除指南](troubleshooting.md)