# MCP服务器修复记录

## 问题描述

Dify与MCP服务器集成时遇到以下问题：

1. **SSE事件问题**：Dify报告"Unknown SSE event: initialized"警告
2. **URL格式问题**：Dify收到的endpoint URL格式不正确，导致无法正确连接到messages端点

## 问题分析

### 1. SSE事件问题

从Dify日志中可以看到：
```
2025-10-24T14:26:34.456815987Z 2025-10-24 14:26:34.456 WARNING [ThreadPoolExecutor-87_0] [sse_client.py:127] - Unknown SSE event: initialized
```

这表明Dify不认识`initialized`事件。根据MCP协议规范，SSE端点应该只发送`endpoint`事件，而不需要发送`initialized`事件。

### 2. URL格式问题

从Dify日志中可以看到：
```
Received endpoint URL: http://host.docker.internal:4010/{"url": "http:/host.docker.internal:4010/messages?session_id=90c2db37-9226-4fa3-a28b-0ef4634747a8"}
```

这表明Dify收到的URL格式不正确。问题在于我们将URL包装在JSON中，而Dify期望直接接收URL字符串。

## 修复方案

### 1. 修复SSE事件处理

在`src/mcp/server.py`的`handle_sse`方法中，移除了不必要的`initialized`事件：

```python
# 修复前：
# 发送初始化完成事件 - 根据MCP协议，这是必需的
init_data = json.dumps({})
init_event = f"event: initialized\ndata: {init_data}\n\n"
self.wfile.write(init_event.encode('utf-8'))
self.wfile.flush()

# 修复后：
# 移除了initialized事件，只保留endpoint事件
```

### 2. 修复URL格式

在`src/mcp/server.py`的`handle_sse`方法中，修改了SSE响应格式：

```python
# 修复前：
endpoint_data = json.dumps({"url": endpoint_url})
endpoint_event = f"event: endpoint\ndata: {endpoint_data}\n\n"

# 修复后：
endpoint_event = f"event: endpoint\ndata: {endpoint_url}\n\n"
```

直接发送URL字符串，而不是包装在JSON中。

## 测试验证

创建了以下测试脚本验证修复效果：

1. `scripts/test_sse_fix.py` - 测试SSE端点修复
2. `scripts/test_dify_integration.py` - 模拟Dify完整集成流程
3. `scripts/test_sse_response.py` - 验证SSE响应格式
4. `scripts/start_and_test.py` - 启动服务器并运行集成测试

## 使用方法

1. 启动MCP服务器：
```bash
python scripts/run_mcp_server.py
```

2. 运行集成测试：
```bash
python scripts/test_dify_integration.py
```

3. 或者使用一键启动和测试：
```bash
python scripts/start_and_test.py
```

## Dify配置

在Dify中添加MCP服务时，使用以下配置：

- **服务地址**: `http://localhost:4010`
- **图标地址**: `http://localhost:4011/favicon.ico`

如果Dify运行在Docker容器中，而MCP服务器运行在宿主机上，请使用：

- **服务地址**: `http://host.docker.internal:4010`
- **图标地址**: `http://host.docker.internal:4011/favicon.ico`

## 注意事项

1. 确保MCP服务器已启动并监听在正确的端口
2. 如果使用Docker，确保网络配置正确
3. 检查防火墙设置，确保Dify可以访问MCP服务器
4. 查看MCP服务器日志，确认没有错误信息

## 额外修复：服务器退出问题

### 问题描述

启动MCP服务器后，使用Ctrl+C无法正常退出，只能关闭窗口。

### 问题分析

1. **信号处理不正确**：KeyboardInterrupt信号没有被正确捕获和处理
2. **线程未正确关闭**：HTTP服务器线程没有在收到信号时正确关闭
3. **事件循环策略问题**：在Windows上可能需要特殊的事件循环策略

### 修复方案

1. **改进信号处理**：
   - 在`_setup_signal_handlers`方法中改进信号处理逻辑
   - 确保在不同情况下都能正确处理关闭信号

2. **修复线程关闭**：
   - 在`_stop_http_server`和`_stop_mcp_http_server`方法中添加超时检查
   - 确保线程能够在合理时间内关闭

3. **设置事件循环策略**：
   - 在Windows上使用`WindowsSelectorEventLoopPolicy`
   - 确保异步操作能够正常工作

### 修改的文件

1. **src/mcp/server.py**：
   - 改进`_setup_signal_handlers`方法
   - 修复`_stop_http_server`和`_stop_mcp_http_server`方法
   - 在`main`函数中添加事件循环策略设置

2. **scripts/run_mcp_server.py**：
   - 在主函数中添加事件循环策略设置
   - 改进KeyboardInterrupt处理

## 相关文件

- `src/mcp/server.py` - 修复 SSE 端点实现和服务器退出问题
- `config/dify_mcp_config.json` - 更新端口配置
- `scripts/test_sse_fix.py` - SSE 端点测试脚本
- `scripts/test_dify_integration.py` - Dify 集成测试脚本
- `scripts/test_sse_response.py` - SSE 响应格式验证脚本
- `scripts/start_and_test.py` - 一键启动和测试脚本
- `scripts/run_mcp_server.py` - 改进信号处理和事件循环策略