# UnityLangPX 用户使用指南

## 概述

UnityLangPX 是一个基于大模型技术的多平台翻译解决方案，支持高质量的文档翻译，特别适合Markdown格式的技术文档。

### 主要特性

- 🌐 **多语言支持**: 基于先进的翻译模型，支持多种语言对
- 📝 **格式保持**: 完美保留Markdown格式和代码块
- ⚡ **高效处理**: 智能分块和并行处理，提高翻译效率
- 🔧 **多平台支持**: 命令行工具、Obsidian插件、MCP服务器
- 🎯 **专业翻译**: 针对技术文档优化的翻译质量

## 系统要求

### 基础要求
- **Python**: 3.11 或更高版本
- **操作系统**: Windows 10/11, Ubuntu 20.04+, macOS 12+
- **内存**: 4GB RAM（推荐8GB）
- **存储**: 10GB可用空间

### 依赖服务
- **Ollama**: 本地部署的大模型服务
- **翻译模型**: SimonPu/Hunyuan-MT-Chimera-7B:Q8

## 安装指南

### 1. 环境准备

#### 安装Python
```bash
# Windows
# 从 https://python.org 下载并安装Python 3.11+

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv

# macOS
brew install python@3.11
```

#### 安装Ollama
```bash
# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# macOS
brew install ollama

# Windows
# 从 https://ollama.ai 下载并安装
```

### 2. 下载翻译模型

```bash
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8
```

### 3. 安装UnityLangPX

```bash
# 克隆仓库
git clone https://gitee.com/unitylangpx/unitylangpx.git
cd unitylangpx

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements/cli.txt
```

## 使用方法

### 1. 命令行工具

#### 基础命令
```bash
# 查看帮助
python -m src.cli.main --help

# 检查服务状态
python -m src.cli.main status

# 翻译单个文件
python -m src.cli.main translate input.md -o output.md

# 翻译目录（递归处理）
python -m src.cli.main translate input_dir/ -o output_dir/ -r

# 指定语言对
python -m src.cli.main translate input.md -o output.md -s en -t zh
```

#### 高级选项
```bash
# 覆盖已存在的文件
python -m src.cli.main translate input.md -o output.md --overwrite

# 详细输出
python -m src.cli.main translate input.md -o output.md -v

# 静默模式
python -m src.cli.main translate input.md -o output.md -q
```

### 2. HTTP API服务器

#### 启动服务器
```bash
# 自动端口启动
python -m src.cli.main serve

# 指定端口启动
python -m src.cli.main serve -p 8848

# 后台运行
python -m src.cli.main serve -d
```

#### API接口
- **POST /api/translate/text** - 翻译文本
- **POST /api/translate/file** - 翻译文件
- **POST /api/translate/batch** - 批量翻译
- **GET /api/status** - 服务状态

### 3. MCP服务器

#### 启动MCP服务器
```bash
# 使用启动脚本
python scripts/run_mcp_server.py

# 或直接运行
python -m src.mcp.server
```

#### 配置MCP客户端
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

## 配置说明

### 配置文件位置
- **默认配置**: `config/default.toml`
- **用户配置**: `~/.unitylangpx/config.toml`

### 主要配置项

#### 翻译配置
```toml
[translation]
source_language = "en"
target_language = "zh"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
preserve_formatting = true
```

#### Ollama配置
```toml
[model_ollama]
host = "http://localhost:11434"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
timeout = 60
```

#### MCP服务器配置
```toml
[mcp]
enabled = true
host = "localhost"
port = 8080
max_connections = 10
request_timeout = 120
log_level = "INFO"
```

## 使用示例

### 示例1：翻译技术文档

```bash
# 翻译单个Markdown文件
python -m src.cli.main translate README.md -o README_zh.md

# 翻译整个文档目录
python -m src.cli.main translate docs/ -o docs_zh/ -r
```

### 示例2：批量处理

```bash
# 翻译特定类型的文件
python -m src.cli.main translate src/ -o src_zh/ --overwrite

# 递归翻译并保持目录结构
python -m src.cli.main translate project/ -o project_zh/ -r
```

### 示例3：集成到工作流

```bash
# 在脚本中使用
#!/bin/bash
for file in *.md; do
    python -m src.cli.main translate "$file" -o "zh_$file"
done
```

## 最佳实践

### 1. 翻译质量优化
- 确保源文档格式规范
- 避免过长的段落（建议<2000字符）
- 检查专业术语的一致性

### 2. 性能优化
- 使用SSD存储提高I/O性能
- 合理设置并发数量
- 定期清理翻译缓存

### 3. 批量处理建议
- 先测试少量文件
- 使用`--overwrite`谨慎
- 保留原文备份

## 故障排除

### 常见问题

#### 1. Ollama连接失败
```bash
# 检查Ollama服务状态
ollama list

# 重启Ollama服务
sudo systemctl restart ollama  # Linux
# 或重新启动Ollama应用
```

#### 2. 模型未找到
```bash
# 下载模型
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8

# 检查可用模型
ollama list
```

#### 3. 翻译质量问题
- 检查源文档格式
- 尝试分段翻译
- 调整分块大小

#### 4. 内存不足
- 减少并发数量
- 使用较小的批处理大小
- 增加系统内存

### 日志查看

```bash
# 查看详细日志
python -m src.cli.main translate input.md -o output.md -v

# 查看MCP服务器日志
tail -f logs/mcp.log
```

## 高级功能

### 1. 自定义配置
```bash
# 使用自定义配置文件
python -m src.cli.main -c custom.toml translate input.md -o output.md
```

### 2. 环境变量
```bash
# 设置环境变量
export OLLAMA_HOST="http://localhost:11434"
export UNITYLANGPX_MCP_LOG_LEVEL="DEBUG"

# 使用环境变量运行
python -m src.cli.main translate input.md -o output.md
```

### 3. 缓存管理
```bash
# 清空翻译缓存
python -m src.cli.main clear-cache

# 查看缓存状态
python -m src.cli.main status
```

## 支持与反馈

### 获取帮助
- **文档**: [项目文档](docs/)
- **问题反馈**: [GitHub Issues](https://gitee.com/unitylangpx/unitylangpx/issues)
- **社区讨论**: [项目讨论区](https://gitee.com/unitylangpx/unitylangpx/discussions)

### 贡献指南
欢迎贡献代码、报告问题或提出改进建议！

---

**版本**: 0.1.0  
**更新日期**: 2025-10-22  
**文档维护**: UnityLangPX开发团队