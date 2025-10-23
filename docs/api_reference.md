# UnityLangPX API 参考文档

## 概述

UnityLangPX 提供了多种API接口，包括命令行接口、HTTP API和MCP协议接口，满足不同场景的使用需求。

## 命令行API

### 基础命令结构

```bash
python -m src.cli.main [OPTIONS] COMMAND [ARGS]...
```

### 全局选项

| 选项 | 简写 | 描述 | 默认值 |
|------|------|------|--------|
| `--config` | `-c` | 配置文件路径 | 无 |
| `--verbose` | `-v` | 详细输出 | False |
| `--quiet` | `-q` | 静默模式 | False |
| `--help` | 无 | 显示帮助信息 | 无 |

### 主要命令

#### 1. translate - 翻译文件或目录

```bash
python -m src.cli.main translate [OPTIONS] INPUT_PATH
```

**参数**:
- `INPUT_PATH` (必需): 输入文件或目录路径

**选项**:
| 选项 | 简写 | 描述 | 默认值 |
|------|------|------|--------|
| `--output` | `-o` | 输出文件或目录路径 | 无 |
| `--source-lang` | `-s` | 源语言 | en |
| `--target-lang` | `-t` | 目标语言 | zh |
| `--recursive` | `-r` | 递归处理目录 | False |
| `--overwrite` | 无 | 覆盖已存在的文件 | False |

**示例**:
```bash
# 翻译单个文件
python -m src.cli.main translate input.md -o output.md

# 翻译目录
python -m src.cli.main translate docs/ -o docs_zh/ -r

# 指定语言对
python -m src.cli.main translate input.md -o output.md -s en -t zh
```

#### 2. serve - 启动HTTP API服务器

```bash
python -m src.cli.main serve [OPTIONS]
```

**选项**:
| 选项 | 简写 | 描述 | 默认值 |
|------|------|------|--------|
| `--port` | `-p` | 指定端口 | 自动分配 |
| `--host` | 无 | 绑定地址 | localhost |
| `--daemon` | `-d` | 后台运行 | False |

**示例**:
```bash
# 自动端口启动
python -m src.cli.main serve

# 指定端口启动
python -m src.cli.main serve -p 8848

# 后台运行
python -m src.cli.main serve -d
```

#### 3. status - 检查服务状态

```bash
python -m src.cli.main status [OPTIONS]
```

**示例**:
```bash
python -m src.cli.main status
```

#### 4. clear-cache - 清空翻译缓存

```bash
python -m src.cli.main clear-cache [OPTIONS]
```

**示例**:
```bash
python -m src.cli.main clear-cache
```

#### 5. config-cmd - 配置管理

```bash
python -m src.cli.main config-cmd [OPTIONS] COMMAND [ARGS]...
```

**子命令**:
- `show`: 显示当前配置
- `set KEY VALUE`: 设置配置项
- `reset KEY`: 重置配置项

**示例**:
```bash
# 显示配置
python -m src.cli.main config-cmd show

# 设置配置
python -m src.cli.main config-cmd set translation.target_language ja

# 重置配置
python -m src.cli.main config-cmd reset translation.target_language
```

#### 6. demo - 演示翻译功能

```bash
python -m src.cli.main demo [OPTIONS]
```

**示例**:
```bash
python -m src.cli.main demo
```

## HTTP API

### 基础URL

```
http://localhost:8848/api
```

### 认证

当前版本不需要认证，生产环境建议配置API密钥。

### 接口列表

#### 1. 翻译文本

**请求**:
```http
POST /api/translate/text
Content-Type: application/json

{
    "text": "Hello, world!",
    "source_language": "en",
    "target_language": "zh",
    "preserve_formatting": true
}
```

**响应**:
```json
{
    "success": true,
    "result": {
        "translated_text": "你好，世界！",
        "source_language": "en",
        "target_language": "zh",
        "character_count": 13,
        "processing_time": 2.5
    },
    "message": "翻译完成"
}
```

#### 2. 翻译文件

**请求**:
```http
POST /api/translate/file
Content-Type: multipart/form-data

file: [文件内容]
output_path: "output.md"
source_language: "en"
target_language: "zh"
preserve_formatting: true
```

**响应**:
```json
{
    "success": true,
    "result": {
        "output_path": "output.md",
        "character_count": 500,
        "processing_time": 15.2,
        "file_size": 1024
    },
    "message": "文件翻译完成"
}
```

#### 3. 批量翻译

**请求**:
```http
POST /api/translate/batch
Content-Type: application/json

{
    "input_directory": "docs/",
    "output_directory": "docs_zh/",
    "file_pattern": "*.md",
    "recursive": true,
    "source_language": "en",
    "target_language": "zh",
    "parallel_workers": 4
}
```

**响应**:
```json
{
    "success": true,
    "result": {
        "total_files": 10,
        "processed_files": 10,
        "failed_files": 0,
        "total_characters": 5000,
        "processing_time": 120.5,
        "files": [
            {
                "input_path": "docs/readme.md",
                "output_path": "docs_zh/readme.md",
                "status": "success",
                "character_count": 500,
                "processing_time": 12.3
            }
        ]
    },
    "message": "批量翻译完成"
}
```

#### 4. 服务状态

**请求**:
```http
GET /api/status
```

**响应**:
```json
{
    "success": true,
    "result": {
        "service_status": "running",
        "ollama_status": "connected",
        "available_models": [
            "SimonPu/Hunyuan-MT-Chimera-7B:Q8",
            "nomic-embed-text:latest"
        ],
        "current_model": "SimonPu/Hunyuan-MT-Chimera-7B:Q8",
        "version": "0.1.0",
        "uptime": "2h 30m"
    },
    "message": "服务状态正常"
}
```

### 错误响应

所有错误响应都遵循统一格式：

```json
{
    "success": false,
    "error": {
        "code": "TRANSLATION_ERROR",
        "message": "翻译失败：模型不可用",
        "details": {
            "model": "invalid-model",
            "suggestion": "请检查模型名称是否正确"
        }
    },
    "message": "请求处理失败"
}
```

### 错误代码

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| `INVALID_REQUEST` | 400 | 请求参数无效 |
| `TRANSLATION_ERROR` | 500 | 翻译过程失败 |
| `FILE_NOT_FOUND` | 404 | 文件不存在 |
| `MODEL_UNAVAILABLE` | 503 | 模型不可用 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |

## MCP协议API

### 连接配置

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

### 可用工具

#### 1. translate_text

**描述**: 翻译单个文本片段

**参数**:
```json
{
    "text": "Hello, world!",
    "source_language": "en",
    "target_language": "zh",
    "preserve_formatting": true
}
```

**返回**:
```json
{
    "success": true,
    "translated_text": "你好，世界！",
    "source_language": "en",
    "target_language": "zh",
    "character_count": 13,
    "processing_time": 2.5
}
```

#### 2. translate_file

**描述**: 翻译单个文件

**参数**:
```json
{
    "file_path": "input.md",
    "output_path": "output.md",
    "source_language": "en",
    "target_language": "zh",
    "preserve_formatting": true
}
```

**返回**:
```json
{
    "success": true,
    "output_path": "output.md",
    "character_count": 500,
    "processing_time": 15.2
}
```

#### 3. translate_directory

**描述**: 批量翻译目录中的文件

**参数**:
```json
{
    "input_directory": "docs/",
    "output_directory": "docs_zh/",
    "file_pattern": "*.md",
    "recursive": true,
    "source_language": "en",
    "target_language": "zh",
    "parallel_workers": 4
}
```

**返回**:
```json
{
    "success": true,
    "total_files": 10,
    "processed_files": 10,
    "failed_files": 0,
    "total_characters": 5000,
    "processing_time": 120.5
}
```

#### 4. get_translation_status

**描述**: 获取翻译服务状态

**参数**:
```json
{
    "query_type": "full",
    "verbose": true
}
```

**返回**:
```json
{
    "service_status": "running",
    "ollama_status": "connected",
    "available_models": [
        "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
    ],
    "current_model": "SimonPu/Hunyuan-MT-Chimera-7B:Q8",
    "version": "0.1.0",
    "uptime": "2h 30m"
}
```

## 配置API

### 配置文件结构

```toml
[translation]
source_language = "en"
target_language = "zh"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
preserve_formatting = true

[model_ollama]
host = "http://localhost:11434"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
timeout = 60

[mcp]
enabled = true
host = "localhost"
port = 8080
max_connections = 10
request_timeout = 120
log_level = "INFO"

[mcp.tools]
translate_text_enabled = true
translate_file_enabled = true
batch_translation_enabled = true
max_file_size_mb = 10
max_batch_size = 50

[mcp.security]
enable_auth = false
api_key = ""
allowed_ips = ["127.0.0.1", "::1"]
rate_limit = 100

[mcp.cache]
enabled = true
cache_dir = "data/mcp_cache"
max_cache_size_mb = 100
ttl_seconds = 3600
```

### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `UNITYLANGPX_CONFIG` | 配置文件路径 | 无 |
| `OLLAMA_HOST` | Ollama服务地址 | http://localhost:11434 |
| `OLLAMA_MODEL` | 翻译模型名称 | SimonPu/Hunyuan-MT-Chimera-7B:Q8 |
| `UNITYLANGPX_MCP_ENABLED` | 启用MCP服务器 | true |
| `UNITYLANGPX_MCP_HOST` | MCP服务器主机 | localhost |
| `UNITYLANGPX_MCP_PORT` | MCP服务器端口 | 8080 |
| `UNITYLANGPX_MCP_LOG_LEVEL` | 日志级别 | INFO |

## 使用示例

### Python客户端示例

```python
import requests
import json

# 翻译文本
def translate_text(text, source_lang="en", target_lang="zh"):
    url = "http://localhost:8848/api/translate/text"
    data = {
        "text": text,
        "source_language": source_lang,
        "target_language": target_lang
    }
    
    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        return result["result"]["translated_text"]
    else:
        raise Exception(f"翻译失败: {response.text}")

# 使用示例
translated = translate_text("Hello, world!")
print(f"翻译结果: {translated}")
```

### JavaScript客户端示例

```javascript
// 翻译文本
async function translateText(text, sourceLang = 'en', targetLang = 'zh') {
    const response = await fetch('http://localhost:8848/api/translate/text', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text: text,
            source_language: sourceLang,
            target_language: targetLang
        })
    });
    
    const result = await response.json();
    if (result.success) {
        return result.result.translated_text;
    } else {
        throw new Error(`翻译失败: ${result.message}`);
    }
}

// 使用示例
translateText('Hello, world!').then(translated => {
    console.log(`翻译结果: ${translated}`);
});
```

---

**文档版本**: 0.1.0  
**更新日期**: 2025-10-22  
**维护团队**: UnityLangPX开发团队