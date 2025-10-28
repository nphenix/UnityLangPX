# UnityLangPX MCP API参考

## 概述

UnityLangPX MCP服务器提供了一套完整的API，支持多种客户端类型，包括Dify和标准MCP客户端。本文档详细描述了所有可用的API端点、请求格式和响应格式。

## 🌐 端点列表

### HTTP端点

| 端点 | 方法 | 描述 | 适配器 |
|--------|------|------|--------|
| `/` | GET | 服务器状态信息 | 标准 |
| `/health` | GET | 健康检查 | 标准 |
| `/favicon.ico` | GET | 网站图标 | 标准 |
| `/sse` | GET | Server-Sent Events端点 | Dify/标准 |
| `/events` | GET | Server-Sent Events端点（别名） | Dify/标准 |
| `/messages` | POST | MCP消息处理端点 | Dify/标准 |

### 标准输入输出端点

| 端点 | 方法 | 描述 | 适配器 |
|--------|------|------|--------|
| `stdin/stdout` | N/A | 标准输入输出通信 | 标准 |

## 📋 请求格式

### JSON-RPC请求格式

所有MCP消息都使用JSON-RPC 2.0格式：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "method_name",
  "params": {
    "parameter1": "value1",
    "parameter2": "value2"
  }
}
```

### SSE请求格式

SSE连接使用标准的HTTP GET请求：

```http
GET /sse HTTP/1.1
Host: localhost:4010
User-Agent: Dify/1.0.0
Accept: text/event-stream
Cache-Control: no-cache
```

## 🔧 支持的方法

### 服务器方法

#### `ping`

检查服务器是否响应。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "ping"
}
```

**响应：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "pong": true
  }
}
```

#### `initialize`

初始化MCP连接。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "tools": {}
    },
    "clientInfo": {
      "name": "client_name",
      "version": "1.0.0"
    }
  }
}
```

**响应：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "tools": {
        "listChanged": true
      },
      "logging": {},
      "roots": {
        "listChanged": true
      }
    },
    "serverInfo": {
      "name": "UnityLangPX MCP Server",
      "version": "1.0.0"
    }
  }
}
```

### 工具方法

#### `tools/list`

列出所有可用工具。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

**响应：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "translate_text",
        "description": "翻译文本",
        "inputSchema": {
          "type": "object",
          "properties": {
            "text": {
              "type": "string",
              "description": "要翻译的文本"
            },
            "source_lang": {
              "type": "string",
              "description": "源语言代码"
            },
            "target_lang": {
              "type": "string",
              "description": "目标语言代码"
            }
          },
          "required": ["text"]
        }
      }
    ]
  }
}
```

#### `tools/call`

调用指定工具。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "translate_text",
    "arguments": {
      "text": "Hello World",
      "source_lang": "en",
      "target_lang": "zh"
    }
  }
}
```

**响应：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "你好世界"
      }
    ]
  }
}
```

### 通知方法

#### `notifications/initialized`

通知服务器客户端已初始化完成。

**请求：**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

**响应：**
无响应（通知消息）。

## 🛠 可用工具

### translate_text

翻译文本内容。

**参数：**
- `text` (string, 必需): 要翻译的文本
- `source_lang` (string, 可选): 源语言代码，默认为"en"
- `target_lang` (string, 可选): 目标语言代码，默认为"zh"

**示例：**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "translate_text",
    "arguments": {
      "text": "Hello World",
      "source_lang": "en",
      "target_lang": "zh"
    }
  }
}
```

## 📊 响应格式

### 成功响应

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    // 响应数据
  }
}
```

### 错误响应

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "错误描述",
    "data": {
      // 额外的错误数据
    }
  }
}
```

### 错误代码

| 代码 | 描述 |
|------|------|
| -32700 | 解析错误：无效的JSON |
| -32600 | 无效请求 |
| -32601 | 方法未找到 |
| -32602 | 无效参数 |
| -32603 | 内部错误 |
| -32000 | 服务器错误 |

## 🔐 认证

如果启用了认证，需要在请求头中包含API密钥：

```http
Authorization: Bearer your-api-key
```

## 🌍 CORS

服务器支持跨域资源共享（CORS），响应头包括：

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Cache-Control, Authorization, X-Requested-With
Access-Control-Max-Age: 86400
```

## 📝 示例

### Dify客户端示例

#### 1. 建立SSE连接

```bash
curl -H "User-Agent: Dify/1.0.0" \
     -H "Accept: text/event-stream" \
     http://localhost:4010/sse
```

#### 2. 发送翻译请求

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -H "User-Agent: Dify/1.0.0" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "translate_text",
         "arguments": {
           "text": "Hello World",
           "source_lang": "en",
           "target_lang": "zh"
         }
       }
     }' \
     http://localhost:4010/messages
```

### 标准MCP客户端示例

#### 1. 健康检查

```bash
curl http://localhost:4010/health
```

#### 2. 获取工具列表

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/list"
     }' \
     http://localhost:4010/messages
```

## 🔧 配置选项

### 服务器配置

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `host` | string | "localhost" | 服务器主机地址 |
| `port` | integer | 4010 | 服务器端口 |
| `enable_http_server` | boolean | true | 是否启用HTTP服务器 |
| `http_port` | integer | 8080 | HTTP服务器端口 |
| `max_connections` | integer | 10 | 最大连接数 |
| `request_timeout` | integer | 120 | 请求超时时间(秒) |

### 智能路由配置

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `enable_smart_routing` | boolean | true | 是否启用智能路由 |
| `auto_detect_client` | boolean | true | 是否自动检测客户端类型 |
| `fallback_to_standard` | boolean | true | 是否回退到标准适配器 |
| `log_routing_decisions` | boolean | true | 是否记录路由决策 |
| `cache_client_detection` | boolean | true | 是否缓存客户端检测结果 |
| `cache_ttl_seconds` | integer | 300 | 客户端检测缓存TTL(秒) |

### Dify适配器配置

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `enable_dify_adapter` | boolean | true | 是否启用Dify适配器 |
| `docker_compatible` | boolean | true | 是否启用Docker兼容性 |
| `endpoint_timeout` | integer | 30 | 端点超时时间(秒) |
| `sse_read_timeout` | integer | 300 | SSE读取超时时间(秒) |
| `session_timeout` | integer | 3600 | 会话超时时间(秒) |
| `max_active_sessions` | integer | 100 | 最大活跃会话数 |

### 标准适配器配置

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `enable_stdio_mode` | boolean | true | 是否启用标准输入输出模式 |
| `enable_http_mode` | boolean | true | 是否启用HTTP模式 |
| `backward_compatible` | boolean | true | 是否保持向后兼容 |
| `strict_protocol_mode` | boolean | false | 是否启用严格协议模式 |

## 🚨 错误处理

### 常见错误

1. **连接被拒绝**
   - 检查服务器是否运行
   - 验证端口配置
   - 检查防火墙设置

2. **认证失败**
   - 验证API密钥
   - 检查认证头格式
   - 确认认证已启用

3. **方法未找到**
   - 检查方法名称拼写
   - 确认方法已实现
   - 查看可用工具列表

4. **无效参数**
   - 检查参数类型
   - 验证必需参数
   - 查看工具架构

### 调试技巧

1. **启用调试日志**
   ```bash
   export UNITYLANGPX_MCP_LOG_LEVEL=DEBUG
   python -m src.mcp.server
   ```

2. **查看路由决策**
   ```bash
   export UNITYLANGPX_MCP_LOG_ROUTING_DECISIONS=true
   python -m src.mcp.server
   ```

3. **使用curl测试**
   ```bash
   curl -v http://localhost:4010/health
   ```

## 📈 性能考虑

### 优化建议

1. **连接池化**
   - 重用HTTP连接
   - 设置合适的连接超时
   - 限制最大连接数

2. **缓存策略**
   - 启用客户端检测缓存
   - 设置合适的缓存TTL
   - 定期清理过期缓存

3. **并发控制**
   - 设置合适的最大连接数
   - 使用异步处理
   - 实现请求队列

### 监控指标

- 请求处理时间
- 连接数
- 错误率
- 内存使用
- CPU使用

## 🔮 未来扩展

### 计划功能

1. **WebSocket支持**
2. **更多工具类型**
3. **插件系统**
4. **负载均衡**
5. **集群支持**

### API版本控制

- 当前版本：v1.0.0
- 版本策略：语义化版本控制
- 向后兼容性：保持主版本内的兼容性

---

*最后更新：2025年10月25日*