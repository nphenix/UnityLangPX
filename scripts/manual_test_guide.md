# UnityLangPX MCP服务器手动测试指南

## 准备工作

1. 确保所有Python进程已停止
2. 确保端口4012和4011未被占用

## 启动服务器

```bash
python scripts/run_mcp_server.py
```

服务器启动后应该显示类似以下信息：
```
MCP服务器已启动，支持HTTP和标准输入输出
HTTP服务地址: http://192.168.5.9:4012
Docker容器访问地址: http://host.docker.internal:4012
favicon地址: http://192.168.5.9:4011/favicon.ico
```

## 测试步骤

### 1. 健康检查测试

使用浏览器或curl访问：
```bash
curl http://localhost:4012/
```

预期响应：
```json
{"status": "ok", "service": "UnityLangPX MCP Server", "version": "1.0.0"}
```

### 2. SSE端点测试

```bash
curl -N http://localhost:4012/sse --max-time 5
```

预期响应应该包含：
```
event: connect
data: {"type":"connected","message":"SSE connection established"}

event: endpoint
data: http://localhost:4012/

event: server_info
data: {"type": "server_info", "name": "UnityLangPX MCP Server", "version": "1.0.0", "capabilities": ["tools", "translation", "batch_processing"]}
```

### 3. JSON-RPC ping测试

```bash
curl -X POST http://localhost:4012/ -H "Content-Type: application/json" -d "{\"jsonrpc\": \"2.0\", \"method\": \"ping\", \"id\": 1}"
```

预期响应：
```json
{"jsonrpc": "2.0", "id": 1, "result": {"pong": true}}
```

### 4. JSON-RPC initialize测试

```bash
curl -X POST http://localhost:4012/ -H "Content-Type: application/json" -d "{\"jsonrpc\": \"2.0\", \"method\": \"initialize\", \"params\": {\"protocolVersion\": \"2025-03-26\", \"capabilities\": {\"sampling\": {}}, \"clientInfo\": {\"name\": \"Test\", \"version\": \"1.0.0\"}}, \"id\": 2}"
```

预期响应：
```json
{"jsonrpc": "2.0", "id": 2, "result": {"protocolVersion": "2025-03-26", "capabilities": {"tools": {"listChanged": true}, "logging": {}}, "serverInfo": {"name": "UnityLangPX MCP Server", "version": "1.0.0"}}}
```

### 5. notifications/initialized测试

```bash
curl -X POST http://localhost:4012/ -H "Content-Type: application/json" -d "{\"jsonrpc\": \"2.0\", \"method\": \"notifications/initialized\"}"
```

预期响应：HTTP 204 No Content（无响应体）

### 6. tools/list测试

```bash
curl -X POST http://localhost:4012/ -H "Content-Type: application/json" -d "{\"jsonrpc\": \"2.0\", \"method\": \"tools/list\", \"id\": 3}"
```

预期响应：
```json
{"jsonrpc": "2.0", "id": 3, "result": {"tools": [{"name": "translate_text", "description": "翻译文本", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "source_lang": {"type": "string"}, "target_lang": {"type": "string"}}, "required": ["text"]}}]}}
```

### 7. 错误处理测试

```bash
curl -X POST http://localhost:4012/ -H "Content-Type: application/json" -d "{\"jsonrpc\": \"2.0\", \"method\": \"nonexistent_method\", \"id\": 4}"
```

预期响应：
```json
{"jsonrpc": "2.0", "id": 4, "error": {"code": -32601, "message": "Method not found: nonexistent_method"}}
```

## 自动化测试

如果您想运行自动化测试，可以使用：

```bash
# 简单测试（推荐）
python scripts/simple_mcp_test.py

# 完整测试（可能需要更长时间）
python scripts/test_mcp_server.py
```

## Dify集成测试

1. 在Dify中配置MCP服务器
2. 服务器URL: `http://localhost:4012`
3. SSE连接URL: `http://localhost:4012/sse`
4. 协议版本: `2025-03-26`

## 故障排除

### 如果端口被占用
```bash
# 查看端口占用情况
netstat -an | findstr 4012

# 如果需要，可以终止占用进程
taskkill /F /PID <进程ID>
```

### 如果依赖缺失
```bash
# 安装依赖
pip install pydantic>=2.0.0 mcp>=1.0.0 asyncio-mqtt>=0.16.0 aiofiles>=23.0.0 fastapi>=0.104.0 uvicorn>=0.24.0
```

### 如果出现编码错误
```bash
# 设置编码环境变量
set PYTHONIOENCODING=utf-8
```

## 测试结果记录

请记录每个测试的结果：

- [ ] 健康检查测试
- [ ] SSE端点测试
- [ ] JSON-RPC ping测试
- [ ] JSON-RPC initialize测试
- [ ] notifications/initialized测试
- [ ] tools/list测试
- [ ] 错误处理测试
- [ ] Dify集成测试

## 注意事项

1. 测试时请确保防火墙允许端口4012和4011的访问
2. 如果使用Docker，请使用 `host.docker.internal:4012` 作为服务器地址
3. 服务器日志会显示在控制台中，可用于调试问题
4. 每次测试后等待几秒钟让连接完全关闭

## 完成测试

测试完成后，按 `Ctrl+C` 停止服务器。