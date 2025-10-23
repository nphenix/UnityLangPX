# UnityLangPX MCP服务器部署指南

## 1. 概述

UnityLangPX MCP服务器是基于MCP协议的翻译服务接口，支持n8n、Dify等平台集成。本指南将详细介绍如何部署和配置MCP服务器。

## 2. 系统要求

### 2.1 硬件要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 2核心 | 4核心或更多 |
| 内存 | 4GB | 8GB或更多 |
| 存储 | 10GB可用空间 | 20GB或更多 |
| GPU | 可选 | NVIDIA GPU（推荐，用于加速翻译） |

### 2.2 软件要求

| 软件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.11 | 3.12 |
| Ollama | 0.1.0 | 最新版本 |
| 操作系统 | Windows 10/11, Ubuntu 20.04+, macOS 12+ | 最新LTS版本 |

## 3. 安装步骤

### 3.1 环境准备

1. **安装Python**
   ```bash
   # Windows
   # 从 https://python.org 下载并安装Python 3.11+
   
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.11 python3.11-pip python3.11-venv
   
   # macOS
   brew install python@3.11
   ```

2. **安装Ollama**
   ```bash
   # Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # macOS
   brew install ollama
   
   # Windows
   # 从 https://ollama.ai 下载并安装
   ```

3. **下载翻译模型**
   ```bash
   ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8
   ```

### 3.2 获取源代码

```bash
# 克隆仓库
git clone https://gitee.com/unitylangpx/unitylangpx.git
cd unitylangpx

# 或者下载发布版本
wget https://gitee.com/unitylangpx/unitylangpx/archive/v1.0.0.tar.gz
tar -xzf v1.0.0.tar.gz
cd unitylangpx-1.0.0
```

### 3.3 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装MCP服务器依赖
pip install -r requirements/mcp.txt
```

## 4. 配置

### 4.1 基础配置

编辑 `config/default.toml` 文件：

```toml
[mcp]
# MCP服务器配置
enabled = true
host = "localhost"
port = 4010
max_connections = 10
request_timeout = 120
log_level = "INFO"

[mcp.tools]
# 工具配置
translate_text_enabled = true
translate_file_enabled = true
batch_translation_enabled = true
max_file_size_mb = 10
max_batch_size = 50
allowed_extensions = [".md", ".txt"]

[mcp.security]
# 安全配置
enable_auth = false
api_key = ""
allowed_ips = ["127.0.0.1", "::1"]
rate_limit = 100
enable_cors = true

[model_ollama]
# Ollama配置
host = "http://localhost:11434"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
timeout = 60
```

### 4.2 环境变量配置

创建 `.env` 文件：

```bash
# MCP服务器配置
UNITYLANGPX_MCP_ENABLED=true
UNITYLANGPX_MCP_HOST=localhost
UNITYLANGPX_MCP_PORT=4010
UNITYLANGPX_MCP_LOG_LEVEL=INFO

# Ollama配置
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=SimonPu/Hunyuan-MT-Chimera-7B:Q8

# 安全配置
UNITYLANGPX_MCP_API_KEY=your_api_key_here
```

## 5. 启动服务器

### 5.1 直接启动

```bash
# 使用启动脚本
python scripts/run_mcp_server.py

# 或直接运行模块
python -m src.mcp.server

# 或指定配置文件
python -m src.mcp.server --config config/custom.toml
```

### 5.2 作为系统服务启动

#### Linux (systemd)

1. 创建服务文件 `/etc/systemd/system/unitylangpx-mcp.service`：

```ini
[Unit]
Description=UnityLangPX MCP Server
After=network.target

[Service]
Type=simple
User=unitylangpx
WorkingDirectory=/opt/unitylangpx
Environment=PATH=/opt/unitylangpx/venv/bin
ExecStart=/opt/unitylangpx/venv/bin/python -m src.mcp.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. 启用并启动服务：

```bash
sudo systemctl enable unitylangpx-mcp
sudo systemctl start unitylangpx-mcp
```

#### Windows (NSSM)

1. 安装NSSM：
```bash
# 下载并安装NSSM
# https://nssm.cc/download
```

2. 创建服务：
```bash
nssm install UnityLangPX-MCP "C:\opt\unitylangpx\venv\Scripts\python.exe" "-m src.mcp.server"
nssm set UnityLangPX-MCP DisplayName "UnityLangPX MCP Server"
nssm set UnityLangPX-MCP Start SERVICE_AUTO_START
nssm start UnityLangPX-MCP
```

### 5.3 Docker部署

1. 创建 `Dockerfile`：

```dockerfile
FROM python:3.12-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements/mcp.txt .
RUN pip install --no-cache-dir -r mcp.txt

# 复制源代码
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# 创建非root用户
RUN useradd -m -u 1000 unitylangpx && chown -R unitylangpx:unitylangpx /app
USER unitylangpx

# 暴露端口
EXPOSE 4010

# 启动命令
CMD ["python", "-m", "src.mcp.server"]
```

2. 创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  unitylangpx-mcp:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    ports:
      - "4010:4010"
    environment:
      - UNITYLANGPX_MCP_ENABLED=true
      - UNITYLANGPX_MCP_HOST=0.0.0.0
      - UNITYLANGPX_MCP_PORT=4010
      - OLLAMA_HOST=http://ollama:11434
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    depends_on:
      - ollama
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  ollama_data:
```

3. 构建并运行：

```bash
# 构建镜像
docker build -f Dockerfile.mcp -t unitylangpx-mcp .

# 运行容器
docker-compose up -d

# 查看日志
docker-compose logs -f unitylangpx-mcp
```

## 6. 验证部署

### 6.1 运行测试脚本

```bash
python test_mcp_server.py
```

### 6.2 手动测试

1. **测试服务器启动**
   ```bash
   # 启动服务器
   python scripts/run_mcp_server.py
   
   # 在另一个终端测试
   echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | python -m src.mcp.server
   ```

2. **测试工具列表**
   ```bash
   echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python -m src.mcp.server
   ```

3. **测试文本翻译**
   ```bash
   echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"translate_text","arguments":{"text":"Hello, world!"}}}' | python -m src.mcp.server
   ```

## 7. 集成到平台

### 7.1 n8n集成

1. 安装MCP节点插件
2. 配置MCP服务器连接：
   ```json
   {
     "mcpServers": {
       "unitylangpx": {
         "command": "python",
         "args": ["/path/to/unitylangpx/scripts/run_mcp_server.py"],
         "env": {
           "OLLAMA_HOST": "http://localhost:11434",
           "UNITYLANGPX_MCP_LOG_LEVEL": "INFO"
         }
       }
     }
   }
   ```
3. 创建工作流并添加MCP节点

### 7.2 Dify集成

1. 在Dify中配置MCP工具
2. 添加MCP服务器地址：`http://localhost:4010`
3. 选择可用的翻译工具

## 8. 监控和维护

### 8.1 日志管理

日志文件位置：
- 应用日志：`logs/translation.log`
- MCP服务器日志：`logs/mcp.log`

查看日志：
```bash
tail -f logs/mcp.log
```

### 8.2 性能监控

使用内置状态查询工具：
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_translation_status","arguments":{"query_type":"full","verbose":true}}}' | python -m src.mcp.server
```

### 8.3 健康检查

创建健康检查脚本：

```bash
#!/bin/bash
# health_check.sh

RESPONSE=$(echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | python -m src.mcp.server 2>/dev/null)

if echo "$RESPONSE" | grep -q '"pong":true'; then
    echo "MCP服务器运行正常"
    exit 0
else
    echo "MCP服务器运行异常"
    exit 1
fi
```

## 9. 故障排除

### 9.1 常见问题

**问题1：服务器启动失败**
```
错误：ImportError: No module named 'src.mcp'
解决：检查Python路径和虚拟环境激活状态
```

**问题2：Ollama连接失败**
```
错误：Connection refused
解决：确保Ollama服务正在运行，检查配置中的host和port
```

**问题3：翻译质量差**
```
解决：检查模型是否正确下载，考虑使用更大的模型或调整temperature参数
```

**问题4：内存不足**
```
解决：增加系统内存或减少max_connections和max_batch_size配置
```

### 9.2 调试模式

启用调试模式：
```bash
export UNITYLANGPX_MCP_LOG_LEVEL=DEBUG
python scripts/run_mcp_server.py
```

### 9.3 性能优化

1. **增加连接池大小**
   ```toml
   [mcp]
   max_connections = 20
   ```

2. **启用缓存**
   ```toml
   [mcp.cache]
   enabled = true
   max_cache_size_mb = 500
   ```

3. **使用GPU加速**
   确保Ollama使用GPU：
   ```bash
   ollama run SimonPu/Hunyuan-MT-Chimera-7B:Q8 --gpu
   ```

## 10. 安全建议

### 10.1 网络安全

1. 使用防火墙限制访问端口
2. 启用API密钥认证
3. 配置IP白名单

### 10.2 数据安全

1. 定期备份配置文件
2. 限制文件上传大小和类型
3. 使用HTTPS（在生产环境中）

### 10.3 访问控制

```toml
[mcp.security]
enable_auth = true
api_key = "your_secure_api_key"
allowed_ips = ["192.168.1.0/24"]
rate_limit = 100
```

## 11. 升级指南

### 11.1 版本升级

1. 备份当前配置和数据
2. 下载新版本代码
3. 更新依赖：`pip install -r requirements/mcp.txt --upgrade`
4. 运行测试脚本验证
5. 重启服务

### 11.2 配置迁移

检查配置文件是否有新选项，参考 `config/default.toml` 更新自定义配置。

## 12. 总结

通过本指南，您应该能够成功部署和运行UnityLangPX MCP服务器。如果遇到问题，请参考故障排除部分或查看项目文档获取更多信息。

---

**文档版本**：1.0  
**创建日期**：2025-10-22  
**最后更新**：2025-10-22  
**维护者**：UnityLangPX团队