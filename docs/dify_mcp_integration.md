# Dify 与 MCP 集成指南

本文档介绍如何将 Dify 与 Model Context Protocol (MCP) 服务器集成，使 Dify 能够通过 MCP 协议访问外部工具和服务。

## 概述

Model Context Protocol (MCP) 是一种开放协议，允许 AI 模型安全地连接到外部数据源和工具。通过将 MCP 服务器与 Dify 集成，您可以：

- 扩展 Dify 应用的功能，访问外部 API 和服务
- 在 Dify 工作流中使用 MCP 提供的工具
- 实现 Dify 与外部系统的无缝集成

## 前提条件

- 已部署的 Dify 实例（本地或云端）
- 运行中的 UnityLangPX MCP 服务器（已启用 HTTP 服务）
- Dify 管理员权限
- 基本的 API 和工具集成知识

## 集成方法

### 方法一：通过自定义工具集成

1. **准备 MCP 服务器**

   确保您的 UnityLangPX MCP 服务器已启动并启用了 HTTP 服务。您需要以下信息：
   - MCP 服务器的地址（通常是 `localhost:4010`）
   - HTTP 服务器地址（用于提供 favicon，通常是 `localhost:4011`）
   - 认证凭据（如果需要）
   - 可用工具列表及其参数

   **重要提示**：UnityLangPX MCP 服务器现在内置了 HTTP 服务器，专门用于提供 favicon.ico 文件，解决 Dify 尝试从 Google 获取图标的问题。

2. **在 Dify 中创建自定义工具**

   - 登录 Dify 管理界面
   - 导航到"工具"或"Tools"部分
   - 点击"创建自定义工具"或"Create Custom Tool"

3. **配置工具 API**

   - **工具名称**：为您的 MCP 工具集指定一个描述性名称
   - **API 端点**：输入 MCP 服务器的 URL（通常是 `http://localhost:4010`）
   - **图标地址**：输入 HTTP 服务器的 favicon 地址（`http://localhost:4011/favicon.ico`）
   - **认证方法**：根据 MCP 服务器配置选择适当的认证方式
   - **请求方法**：通常为 POST

4. **定义工具模式**

   根据 MCP 服务器的工具定义，创建相应的工具模式。例如：

   ```json
   {
     "name": "mcp_tool",
     "description": "通过 MCP 协议访问外部工具",
     "parameters": {
       "type": "object",
       "properties": {
         "tool_name": {
           "type": "string",
           "description": "要调用的 MCP 工具名称"
         },
         "arguments": {
           "type": "object",
           "description": "工具参数"
         }
       },
       "required": ["tool_name"]
     }
   }
   ```

5. **测试工具集成**

   使用 Dify 的测试功能验证工具是否正确连接到 MCP 服务器并能成功调用。

### 方法二：通过工作流集成

1. **创建新工作流**

   - 在 Dify 中，创建一个新的工作流应用
   - 选择"从空白开始"或使用适当的模板

2. **添加工具节点**

   - 在工作流画布上，添加一个"工具"或"Tool"节点
   - 选择您之前创建的 MCP 自定义工具

3. **配置输入和输出**

   - 将工作流中的变量连接到工具节点
   - 配置工具输出如何传递到工作流的其他部分

4. **测试工作流**

   运行工作流并验证 MCP 工具是否按预期工作。

### 方法三：通过 API 集成

对于更高级的集成，您可以直接使用 Dify 的 API 与 MCP 服务器交互：

1. **获取 Dify API 密钥**

   - 在 Dify 设置中生成 API 密钥
   - 记录您的应用 ID 和 API 密钥

2. **开发中间件服务**

   创建一个中间件服务，该服务：
   - 接收来自 Dify 的 API 请求
   - 将请求转换为 MCP 协议格式
   - 调用 MCP 服务器
   - 将响应转换回 Dify 期望的格式

3. **在 Dify 中配置外部 API**

   - 使用 Dify 的外部 API 功能指向您的中间件服务
   - 确保数据格式正确映射

## 最佳实践

1. **错误处理**

   - 实现健壮的错误处理机制，以处理 MCP 服务器不可用或返回错误的情况
   - 在 Dify 工作流中添加适当的错误处理节点

2. **安全性**

   - 使用 HTTPS 保护 MCP 服务器与 Dify 之间的通信
   - 实施适当的认证和授权机制
   - 限制 MCP 工具的权限，只授予必要的访问权限

3. **性能优化**

   - 考虑 MCP 调用的延迟，并在工作流设计中予以考虑
   - 实现适当的缓存策略，减少重复的 MCP 调用

4. **监控和日志**

   - 设置监控以跟踪 MCP 工具的使用情况
   - 记录详细的日志，以便在出现问题时进行故障排除

## 示例：集成文件系统 MCP 工具

以下是一个将文件系统 MCP 工具集成到 Dify 的示例：

1. **MCP 工具定义**

   ```json
   {
     "name": "file_system",
     "description": "访问和管理文件系统",
     "tools": [
       {
         "name": "read_file",
         "description": "读取文件内容",
         "inputSchema": {
           "type": "object",
           "properties": {
             "path": {
               "type": "string",
               "description": "文件路径"
             }
           },
           "required": ["path"]
         }
       },
       {
         "name": "write_file",
         "description": "写入文件内容",
         "inputSchema": {
           "type": "object",
           "properties": {
             "path": {
               "type": "string",
               "description": "文件路径"
             },
             "content": {
               "type": "string",
               "description": "文件内容"
             }
           },
           "required": ["path", "content"]
         }
       }
     ]
   }
   ```

2. **Dify 自定义工具配置**

   - **工具名称**：文件系统工具
   - **API 端点**：`https://your-mcp-server.com/api/tools`
   - **请求方法**：POST
   - **请求体**：
     ```json
     {
       "tool": "file_system",
       "action": "{{tool_name}}",
       "parameters": "{{arguments}}"
     }
     ```

3. **在 Dify 工作流中使用**

   - 添加一个工具节点，选择"文件系统工具"
   - 配置 `tool_name` 参数为 "read_file" 或 "write_file"
   - 传递适当的文件路径和内容参数

## 故障排除

### 常见问题

1. **连接超时**

   - 检查 MCP 服务器是否正在运行
   - 验证网络连接和防火墙设置
   - 考虑增加超时时间

2. **认证失败**

   - 验证 API 密钥和认证凭据
   - 检查认证方法是否正确配置

3. **工具调用失败**

   - 检查工具名称和参数是否正确
   - 验证 MCP 服务器日志以获取详细错误信息

4. **数据格式不匹配**

   - 确保 Dify 发送的数据格式与 MCP 服务器期望的格式匹配
   - 考虑实现数据转换逻辑

5. **Google 服务访问问题**

   - **问题原因**：Dify 在注册 MCP 服务时会尝试获取工具的 favicon 图标，默认会访问 Google 服务
   - **解决方案**：UnityLangPX MCP 服务器已内置 HTTP 服务器专门提供 favicon.ico 文件
   - **配置方法**：
     - 在 Dify 的「添加 MCP 服务」表单中，图标地址一栏手动填入：`http://<your-mcp-host>:<http-port>/favicon.ico`
     - 例如：`http://localhost:4011/favicon.ico`（默认端口）
     - **Docker 环境注意事项**：
       - 如果 Dify 运行在 Docker 容器中，而 MCP 服务器运行在宿主机上，请使用：
       - MCP 服务地址：`http://host.docker.internal:4010`
       - 图标地址：`http://host.docker.internal:4011/favicon.ico`
       - `host.docker.internal` 是 Docker 提供的特殊 DNS 名称，用于从容器访问宿主机服务
     - **验证方法**：保存并授权后，Dify 前端会直接使用您提供的图标地址，不再尝试访问 Google 服务
     - **配置示例**：
       ```json
       {
         "name": "UnityLangPX MCP 服务",
         "url": "http://host.docker.internal:4010",
         "icon": "http://host.docker.internal:4011/favicon.ico"
       }
       ```

## 进阶用法

### 动态工具发现

对于支持动态工具发现的 MCP 服务器，您可以：

1. 创建一个"工具发现"工具，查询 MCP 服务器可用工具列表
2. 根据返回的工具列表动态更新 Dify 中的工具配置
3. 实现工具缓存，减少重复发现请求

### 流式响应

如果 MCP 服务器支持流式响应：

1. 在 Dify 中配置流式 API 调用
2. 处理分块响应并将其传递给用户
3. 实现适当的错误处理和重试机制

## 配置参考

### MCP 服务器配置文件

创建或修改 `config/dify_mcp_config.json` 文件：

```json
{
  "server": {
    "enabled": true,
    "host": "localhost",
    "port": 4010,
    "enable_http_server": true,
    "http_port": 4011,
    "static_dir": "static"
  },
  "tools": {
    "translate_text_enabled": true,
    "translate_file_enabled": true,
    "batch_translation_enabled": true
  },
  "security": {
    "enable_auth": false,
    "rate_limit": 100
  }
}
```

### 环境变量配置

您也可以通过环境变量配置 MCP 服务器：

```bash
# 启用 HTTP 服务器
export UNITYLANGPX_MCP_ENABLE_HTTP_SERVER=true

# 设置 HTTP 服务器端口
export UNITYLANGPX_MCP_HTTP_PORT=4011

# 设置静态文件目录
export UNITYLANGPX_MCP_STATIC_DIR=static
```

### 启动命令

```bash
# 使用默认配置启动（推荐方式）
python scripts/run_mcp_server.py

# 使用自定义配置文件
python scripts/run_mcp_server.py --config config/dify_mcp_simple.json

# 设置日志级别
python scripts/run_mcp_server.py --log-level DEBUG

# 或者直接使用模块方式
python -m src.mcp.server --config config/dify_mcp_config.json
```

在Windows上，也可以使用批处理文件：
```cmd
scripts\run_mcp_server.bat
```

在Linux/macOS上，可以使用shell脚本：
```bash
chmod +x scripts/run_mcp_server.sh
./scripts/run_mcp_server.sh
```

## 结论

通过将 MCP 服务器与 Dify 集成，您可以显著扩展 Dify 应用的功能，使其能够访问外部系统和服务。UnityLangPX MCP 服务器现在内置了 HTTP 服务器，专门解决 Dify 尝试从 Google 获取图标的问题，使集成更加顺畅。

这种集成提供了灵活性和可扩展性，使您能够根据特定需求定制 AI 应用。

## 参考资料

- [Model Context Protocol (MCP) 规范](https://modelcontextprotocol.io/)
- [Dify 文档 - 工具](https://docs.dify.ai/guides/tools)
- [Dify API 参考](https://docs.dify.ai/api-reference)
- [Dify 工作流指南](https://docs.dify.ai/guides/workflow)