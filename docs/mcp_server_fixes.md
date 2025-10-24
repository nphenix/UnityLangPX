# MCP 服务器修复记录

## 问题描述

在 Dify 中成功注册了 MCP，也获得了授权，但是无法获取工具列表。Dify 侧日志反馈：

```
api-1 | 2025-10-24T12:12:23.429739188Z Traceback (most recent call last):
api-1 | 2025-10-24T12:12:23.429740678Z   File "/app/api/core/mcp/client/sse_client.py", line 209, in _wait_for_endpoint
api-1 | 2025-10-24T12:12:23.429741962Z     status = status_queue.get(timeout=1)
api-1 | 2025-10-24T12:12:23.429743030Z              ^^^^^^^^^^^^^^^^^^^^^^^
api-1 | 2025-10-24T12:12:23.429744182Z   File "/usr/local/lib/python3.12/queue.py", line 179, in get
api-1 | 2025-10-24T12:12:23.429745301Z     raise Empty
api-1 | 2025-10-24T12:12:23.429746296Z _queue.Empty
api-1 | 2025-10-24T12:12:23.429748289Z
api-1 | 2025-10-24T12:12:23.429749331Z During handling of the above exception, another exception occurred:
api-1 | 2025-10-24T12:12:23.429750298Z Traceback (most recent call last):
api-1 | 2025-10-24T12:12:23.429751363Z   File "/app/api/core/mcp/client/sse_client.py", line 287, in sse_client
api-1 | 2025-10-24T12:12:23.429752500Z     read_queue, write_queue = transport.connect(executor, client, event_source)
api-1 | 2025-10-24T12:12:23.429753551Z                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
api-1 | 2025-10-24T12:12:23.429754670Z   File "/app/api/core/mcp/client/sse_client.py", line 244, in connect
api-1 | 2025-10-24T12:12:23.429755723Z     endpoint_url = self._wait_for_endpoint(status_queue)
api-1 | 2025-10-24T12:12:23.429756981Z                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
api-1 | 2025-10-24T12:12:23.429759072Z   File "/app/api/core/mcp/client/sse_client.py", line 211, in _wait_for_endpoint
api-1 | 2025-10-24T12:12:23.429760124Z     raise ValueError("failed to get endpoint URL")
api-1 | 2025-10-24T12:12:23.429761124Z ValueError: failed to get endpoint URL
```

## 问题分析

错误信息显示 `ValueError: failed to get endpoint URL`，这表明 Dify 无法从 MCP 服务器获取正确的端点 URL。

经过分析 Dify 的 SSE 客户端代码，发现问题出在 SSE (Server-Sent Events) 端点的实现上。Dify 的 MCP 客户端期望：

1. SSE 事件类型为 "endpoint"
2. 事件数据是一个相对路径，如 "/"
3. 客户端会使用 `urljoin(self.url, sse_data)` 来构建完整的端点 URL

我们的原始实现有两个问题：
1. 端点 URL 格式不正确（使用了完整 URL 而不是相对路径）
2. 在发送端点事件后立即发送了其他事件，可能干扰了 Dify 客户端的处理

## 修复方案

### 1. 修改 SSE 端点实现

在 `src/mcp/server.py` 文件中的 `handle_sse` 方法中，进行了以下修改：

1. 将端点 URL 从完整的 URL 改为相对路径 `/`：
   ```python
   # 修改前
   endpoint_url = f"{scheme}://{host}/"
   
   # 修改后
   endpoint_url = "/"
   ```

2. 调整事件发送顺序，确保端点事件是第一个发送的事件：
   ```python
   # 首先发送端点URL事件 - 这是Dify需要的
   self.wfile.write(b"event: endpoint\n")
   self.wfile.write(f"data: {endpoint_url}\n\n".encode('utf-8'))
   self.wfile.flush()
   
   # 等待一段时间，确保Dify客户端接收到端点事件
   time.sleep(2)  # 等待2秒，确保客户端处理完端点事件
   
   # 然后发送其他事件
   ```

### 2. 更新配置文件

在 `config/dify_mcp_config.json` 文件中，将端口从 4012 改为 4010：

```json
"UNITYLANGPX_MCP_PORT": "4010"
```

这是因为 MCP 服务器默认使用端口 4010，而不是 4012。

## 测试验证

创建了两个测试脚本验证修复：

1. `scripts/test_sse_fix.py` - 测试 SSE 端点是否正确发送端点事件
2. `scripts/test_dify_integration.py` - 测试 Dify 集成是否正常

测试结果：

```
============================================================
UnityLangPX MCP 服务器 Dify 集成测试
============================================================

1. 测试健康检查端点...
[OK] 健康检查通过
响应数据: {'status': 'ok', 'service': 'UnityLangPX MCP Server', 'version': '1.0.0'}

2. 测试 SSE 端点...
[OK] SSE 端点连接成功
收到事件: event: endpoint
[OK] 收到端点事件
收到事件: data: /
[OK] 端点数据正确
[OK] Dify 集成测试成功

3. 测试工具列表...
[OK] 获取到 1 个工具:
  - translate_text: 翻译文本

============================================================
测试结果汇总:
Dify连接: [OK] 通过
工具列表: [OK] 通过

[SUCCESS] Dify 集成测试全部通过！
```

## 下一步操作

1. 确保 Dify 配置文件中的端口设置为 4010
2. 重启 Dify 服务
3. 在 Dify 中重新尝试获取工具列表

## 相关文件

- `src/mcp/server.py` - 修复 SSE 端点实现
- `config/dify_mcp_config.json` - 更新端口配置
- `scripts/test_sse_fix.py` - SSE 端点测试脚本
- `scripts/test_dify_integration.py` - Dify 集成测试脚本