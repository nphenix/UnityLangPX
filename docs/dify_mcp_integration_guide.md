# Dify MCP集成指南

## 概述

UnityLangPX MCP服务器现在支持智能路由系统，可以自动识别并适配不同类型的MCP客户端，包括Dify和标准MCP客户端。本指南将详细介绍如何配置和使用Dify MCP集成功能。

## 🚀 功能特性

### 智能路由系统
- **自动客户端检测**：根据请求特征自动识别客户端类型
- **动态适配器选择**：根据客户端类型自动选择最佳适配器
- **回退机制**：检测失败时自动回退到标准适配器
- **缓存优化**：缓存客户端检测结果，提高性能

### Dify专用适配器
- **SSE支持**：完全符合Dify的SSE集成要求
- **Docker兼容**：支持Docker环境下的网络连接
- **会话管理**：自动管理Dify客户端会话
- **特殊格式化**：确保响应格式符合Dify期望

### 标准MCP适配器
- **向后兼容**：保持与现有MCP客户端的兼容性
- **多模式支持**：支持HTTP和标准输入输出模式
- **协议完整**：完整实现MCP协议规范

## 📋 配置指南

### 基本配置

在 `config/unified_config.toml` 中添加以下配置：

```toml
[mcp]
# MCP服务器基本配置
enabled = true
host = "0.0.0.0"
port = 4010
enable_http_server = true
http_port = 8080

# 智能路由配置
[mcp.smart_routing]
enable_smart_routing = true
auto_detect_client = true
fallback_to_standard = true
log_routing_decisions = true
cache_client_detection = true
cache_ttl_seconds = 300

# Dify专用配置
[mcp.dify]
enable_dify_adapter = true
docker_compatible = true
endpoint_timeout = 30
sse_read_timeout = 300
session_timeout = 3600
max_active_sessions = 100

# 标准MCP配置
[mcp.standard]
enable_stdio_mode = true
enable_http_mode = true
backward_compatible = true
strict_protocol_mode = false
```

### 环境变量配置

也可以通过环境变量进行配置：

```bash
# 智能路由配置
export UNITYLANGPX_MCP_SMART_ROUTING_ENABLED=true
export UNITYLANGPX_MCP_AUTO_DETECT_CLIENT=true
export UNITYLANGPX_MCP_LOG_ROUTING_DECISIONS=true

# Dify配置
export UNITYLANGPX_MCP_DIFY_ENABLED=true
export UNITYLANGPX_MCP_DIFY_DOCKER_COMPATIBLE=true

# 标准MCP配置
export UNITYLANGPX_MCP_STDIO_MODE=true
export UNITYLANGPX_MCP_HTTP_MODE=true
```

## 🔧 使用指南

### 启动服务器

```bash
# 使用默认配置启动
python -m src.mcp.server

# 使用自定义配置启动
python -m src.mcp.server --config config/custom_config.toml

# 设置日志级别
python -m src.mcp.server --log-level DEBUG
```

### Dify客户端连接

Dify客户端可以通过以下方式连接：

1. **SSE连接**：
   ```
   GET http://localhost:4010/sse
   ```

2. **消息端点**：
   ```
   POST http://localhost:4010/messages
   Content-Type: application/json
   Authorization: Bearer <token>
   
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "initialize",
     "params": {
       "protocolVersion": "2025-03-26"
     }
   }
   ```

### 标准MCP客户端连接

标准MCP客户端可以通过以下方式连接：

1. **HTTP模式**：
   ```
   GET http://localhost:4010/health
   ```

2. **标准输入输出模式**：
   ```bash
   python -m src.mcp.server
   ```

## 🔍 客户端检测机制

智能路由系统使用以下特征检测客户端类型：

### Dify客户端特征
- User-Agent包含"dify"
- 请求路径为"/sse"或"/events"
- 请求头包含"x-dify"
- 包含Bearer token认证
- Origin或Referer包含dify相关内容

### 标准MCP客户端特征
- 不符合Dify特征的客户端
- 标准MCP协议请求
- 常规HTTP请求

## 📊 监控和统计

### 获取适配器统计信息

```python
from src.mcp.smart_router import SmartRouter

# 创建智能路由器
router = SmartRouter(server)

# 获取适配器统计信息
stats = router.get_adapter_stats()
print(f"Dify适配器统计: {stats['dify']}")
print(f"标准适配器统计: {stats['standard']}")
```

### 日志监控

服务器会记录以下关键信息：

- 客户端检测结果
- 路由决策
- 适配器调用
- 错误和异常

示例日志：
```
INFO: 检测到客户端类型: dify
INFO: 路由请求到Dify适配器
INFO: Dify适配器处理SSE连接
```

## 🐛 故障排除

### 常见问题

1. **Dify客户端无法连接**
   - 检查端口配置是否正确
   - 确认防火墙设置
   - 验证Docker网络配置

2. **客户端检测错误**
   - 检查请求头是否完整
   - 验证User-Agent字符串
   - 查看路由决策日志

3. **适配器回退**
   - 确认适配器初始化成功
   - 检查配置是否正确
   - 查看错误日志

### 调试模式

启用调试模式获取详细信息：

```bash
# 设置调试日志级别
export UNITYLANGPX_MCP_LOG_LEVEL=DEBUG

# 启用路由决策日志
export UNITYLANGPX_MCP_LOG_ROUTING_DECISIONS=true

# 启动服务器
python -m src.mcp.server
```

## 🧪 测试

### 运行单元测试

```bash
# 运行智能路由测试
python -m pytest tests/mcp/test_smart_router.py -v

# 运行Dify适配器测试
python -m pytest tests/mcp/test_dify_adapter.py -v

# 运行标准适配器测试
python -m pytest tests/mcp/test_standard_adapter.py -v
```

### 运行集成测试

```bash
# 运行集成测试
python -m pytest tests/mcp/test_integration.py -v
```

### 手动测试

1. **测试Dify连接**：
   ```bash
   curl -H "User-Agent: Dify/1.0.0" \
        -H "Content-Type: application/json" \
        http://localhost:4010/sse
   ```

2. **测试标准连接**：
   ```bash
   curl -H "User-Agent: MCP-Client/1.0.0" \
        http://localhost:4010/health
   ```

## 🔧 高级配置

### 自定义客户端检测

可以通过修改 `src/mcp/smart_router.py` 中的 `ClientDetector` 类来自定义客户端检测逻辑：

```python
class CustomClientDetector(ClientDetector):
    def detect_client_type(self, handler) -> str:
        # 自定义检测逻辑
        if 'custom-header' in handler.headers:
            return 'custom'
        
        # 回退到父类检测
        return super().detect_client_type(handler)
```

### 自定义适配器

可以创建自定义适配器：

```python
from src.mcp.dify_adapter import DifySSEAdapter

class CustomAdapter(DifySSEAdapter):
    def handle_sse_connection(self, handler):
        # 自定义SSE处理逻辑
        super().handle_sse_connection(handler)
        
        # 添加自定义逻辑
        pass
```

## 📈 性能优化

### 缓存配置

优化客户端检测缓存：

```toml
[mcp.smart_routing]
cache_client_detection = true
cache_ttl_seconds = 300  # 5分钟缓存
```

### 连接管理

优化连接管理：

```toml
[mcp]
max_connections = 50
request_timeout = 60

[mcp.dify]
max_active_sessions = 200
session_timeout = 1800  # 30分钟
```

## 🔒 安全考虑

### 认证配置

启用认证：

```toml
[mcp_security]
enable_auth = true
api_key = "your-secret-api-key"
allowed_ips = ["127.0.0.1", "::1"]
rate_limit = 100
```

### CORS配置

配置CORS：

```toml
[mcp_security]
enable_cors = true
```

## 📚 API参考

### 智能路由器API

```python
class SmartRouter:
    def route_request(self, handler, request_type='http'):
        """路由请求到合适的适配器"""
        pass
    
    def get_adapter_stats(self):
        """获取适配器统计信息"""
        pass
```

### Dify适配器API

```python
class DifySSEAdapter:
    def handle_sse_connection(self, handler):
        """处理SSE连接请求"""
        pass
    
    def handle_message_request(self, handler):
        """处理messages端点请求"""
        pass
    
    def get_stats(self):
        """获取统计信息"""
        pass
```

### 标准适配器API

```python
class StandardMCPAdapter:
    def handle_request(self, handler):
        """处理标准MCP请求"""
        pass
    
    def get_stats(self):
        """获取统计信息"""
        pass
```

## 🤝 贡献指南

欢迎贡献代码和改进建议！

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/your-repo/UnityLangPX.git
cd UnityLangPX

# 安装依赖
pip install -r requirements/dev.txt

# 运行测试
python -m pytest tests/
```

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 🆘 支持

如有问题或建议，请通过以下方式联系：

- 创建GitHub Issue
- 发送邮件至support@example.com
- 查看文档：https://docs.example.com

---

*最后更新：2025年10月25日*