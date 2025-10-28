# UnityLangPX MCP服务器启动指南

本指南将帮助您快速启动UnityLangPX MCP服务器，支持Dify和标准MCP客户端的连接。

## 🚀 快速启动

### 方法一：使用启动脚本（推荐）

#### Windows系统
```bash
# 双击运行或在命令行中执行
start_mcp_server.bat
```

#### Linux/macOS系统
```bash
# 在终端中执行
chmod +x start_mcp_server.sh
./start_mcp_server.sh
```

### 方法二：直接使用Python命令

```bash
# 基本启动命令（推荐）
python scripts/run_mcp_server.py

# 指定配置文件
python scripts/run_mcp_server.py --config config/unified_config.toml

# 设置日志级别
python scripts/run_mcp_server.py --log-level DEBUG
```

> **说明**：UnityLangPX MCP服务器已实现智能路由系统，**无需指定模式参数**：
> - 服务器会自动检测客户端类型（Dify或标准MCP）
> - 根据客户端类型自动选择合适的适配器
> - 同时支持Dify的SSE连接和标准MCP协议
> - 默认启动即可满足所有客户端需求

## 📋 启动前准备

### 1. 环境要求

- Python 3.8+
- 已安装项目依赖：
  ```bash
  pip install -r requirements/mcp.txt
  ```

### 2. 检查Ollama服务

确保Ollama服务正在运行：
```bash
# 检查Ollama状态
ollama list

# 如果未运行，启动Ollama
ollama serve
```

### 3. 防火墙设置

确保防火墙允许以下端口：
- **4010**：MCP服务器主端口
- **8080**：HTTP静态文件服务器端口（可选）

## 🔧 配置选项

### 环境变量配置

您可以通过环境变量配置服务器：

```bash
# 服务器基本配置
export UNITYLANGPX_MCP_HOST=0.0.0.0
export UNITYLANGPX_MCP_PORT=4010
export UNITYLANGPX_MCP_LOG_LEVEL=INFO

# 智能路由配置
export UNITYLANGPX_MCP_SMART_ROUTING_ENABLED=true
export UNITYLANGPX_MCP_AUTO_DETECT_CLIENT=true

# Dify适配器配置
export UNITYLANGPX_MCP_DIFY_ENABLED=true
export UNITYLANGPX_MCP_DIFY_DOCKER_COMPATIBLE=true

# 标准MCP配置
export UNITYLANGPX_MCP_STDIO_MODE=true
export UNITYLANGPX_MCP_HTTP_MODE=true
```

### 配置文件

使用TOML配置文件（推荐）：

```bash
# 使用默认配置文件
python scripts/run_mcp_server.py --config config/unified_config.toml

# 使用自定义配置文件
python scripts/run_mcp_server.py --config my_config.toml
```

配置文件示例：
```toml
[mcp]
enabled = true
host = "0.0.0.0"
port = 4010
log_level = "INFO"

[mcp.smart_routing]
enable_smart_routing = true
auto_detect_client = true
fallback_to_standard = true

[mcp.dify]
enable_dify_adapter = true
docker_compatible = true
endpoint_timeout = 30

[mcp.standard]
enable_stdio_mode = true
enable_http_mode = true
backward_compatible = true
```

## 🌐 访问地址

启动成功后，服务器将在以下地址提供服务：

### 本地访问
- **MCP服务器**：`http://[宿主机IP]:4010`
- **健康检查**：`http://[宿主机IP]:4010/health`
- **SSE端点**：`http://[宿主机IP]:4010/sse`

### Docker环境访问
- **Dify连接**：`http://[宿主机IP]:4010/sse`
- **消息端点**：`http://[宿主机IP]:4010/messages`

### 网络访问
- **局域网访问**：`http://[宿主机IP]:4010`
- **Docker容器访问**：`http://[宿主机IP]:4010`

> **注意**：[宿主机IP] 是您运行MCP服务器的机器的实际IP地址，可以通过以下命令获取：
> - Windows: `ipconfig`
> - Linux/macOS: `ifconfig` 或 `ip addr show`

## 🔍 验证启动

### 1. 检查服务器状态

```bash
# 健康检查（使用实际IP地址）
curl http://[宿主机IP]:4010/health

# 预期响应
{"status": "ok", "service": "UnityLangPX MCP Server"}
```

### 2. 测试SSE连接

```bash
# 测试SSE端点（使用实际IP地址）
curl -N http://[宿主机IP]:4010/sse

# 预期响应（Dify客户端）
event: endpoint
data: http://[宿主机IP]:4010/messages?session_id=xxx
```

### 3. 测试智能路由

```bash
# 模拟Dify客户端请求（使用实际IP地址）
curl -H "User-Agent: Dify/1.0.0" http://[宿主机IP]:4010/sse

# 模拟标准MCP客户端请求（使用实际IP地址）
curl -H "User-Agent: MCP-Client/1.0.0" http://[宿主机IP]:4010/health
```

## 📝 日志查看

### 控制台日志
服务器启动后，日志将直接输出到控制台，包括：
- 服务器启动信息
- 客户端连接日志
- 路由决策日志
- 错误和警告信息

### 日志级别
可通过以下方式调整日志级别：
```bash
# 方法1：命令行参数
python scripts/run_mcp_server.py --log-level DEBUG

# 方法2：环境变量
export UNITYLANGPX_MCP_LOG_LEVEL=DEBUG
python scripts/run_mcp_server.py

# 方法3：配置文件
# 在config/unified_config.toml中设置
[mcp]
log_level = "DEBUG"
```

## 🛠️ 常见问题

### 1. 端口被占用
```bash
# 错误信息
Address already in use

# 解决方案
# 更改端口
export UNITYLANGPX_MCP_PORT=4011
# 或在配置文件中修改
```

### 2. Ollama连接失败
```bash
# 错误信息
Ollama服务连接失败

# 解决方案
# 启动Ollama服务
ollama serve

# 检查Ollama状态
ollama list
```

### 3. Docker连接问题
```bash
# 确保host.docker.internal可访问
# 在Docker容器中测试
curl http://host.docker.internal:4010/health

# 如果不可用，使用主机IP
export HOST_IP=$(hostname -I | awk '{print $1}')
# 在Dify配置中使用：http://$HOST_IP:4010
```

### 4. 权限问题
```bash
# Linux/macOS权限错误
Permission denied

# 解决方案
chmod +x start_mcp_server.sh
sudo python scripts/run_mcp_server.py
```

## 🔄 停止服务器

### 方法1：键盘中断
在运行服务器的终端中按 `Ctrl+C`

### 方法2：强制停止
```bash
# Windows
taskkill /F /IM python.exe

# Linux/macOS
pkill -f "python.*run_mcp_server.py"
```

## 📊 性能监控

### 查看服务器状态
```bash
# 获取详细状态信息
curl http://localhost:4010/status

# 响应示例
{
  "running": true,
  "uptime": 3600.5,
  "request_count": 150,
  "config": {...},
  "health": {...}
}
```

### 性能测试
```bash
# 运行性能测试脚本
python scripts/performance_test.py
```

## 🎯 下一步

服务器启动成功后，您可以：

1. **配置Dify连接**：在Dify中添加MCP服务器
2. **测试翻译功能**：使用MCP客户端测试翻译
3. **查看API文档**：访问 `docs/api_reference.md`
4. **自定义配置**：根据需要调整服务器配置

## 📚 更多资源

- [Dify MCP集成指南](dify_mcp_integration_guide.md)
- [API参考文档](api_reference.md)
- [配置指南](configuration_guide.md)
- [故障排除指南](troubleshooting_guide.md)

---

如有问题，请查看日志输出或参考故障排除指南。