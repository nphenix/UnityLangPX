# UnityLangPX

基于大模型技术的多平台翻译解决方案，支持多种翻译模型，专为Markdown文档翻译而设计。

## 🌟 项目概述

UnityLangPX 是一个现代化的翻译解决方案，提供多种使用方式：

1. ✅ **命令行工具**：强大的CLI工具，支持批量翻译和自动化处理
2. ✅ **Obsidian 插件**：无缝集成到Obsidian笔记软件
3. ✅ **MCP 服务器**：标准化接口，支持多平台集成

### 核心特性

- 🌐 **多模型支持**：兼容Ollama、OpenAI等多种大模型服务
- 📝 **格式保持**：完美保留Markdown格式，包括代码块、表格和链接
- ⚡ **批量处理**：支持批量翻译多个文件，提高工作效率
- 🧠 **智能分块**：自动将长文档分块处理，确保翻译质量
- 📚 **术语管理**：支持自定义术语词典，确保专业术语一致性
- 💾 **缓存机制**：智能缓存，避免重复翻译

## 🚀 快速开始

### 环境要求

- Python 3.11+
- 大模型服务（Ollama、OpenAI API等）

### 安装和配置

#### 1. 环境配置

```bash
# 克隆仓库
git clone https://gitee.com/unitylangpx/unitylangpx.git
cd unitylangpx

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements/cli.txt
```

#### 2. 配置翻译模型

UnityLangPX支持多种翻译模型，您可以根据需要选择：

**选项1：使用Ollama本地模型**
```bash
# 下载推荐模型
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8

# 或使用其他兼容模型
ollama pull llama2
ollama pull qwen:7b

# 检查模型是否可用
ollama list
```

**选项2：使用OpenAI API**
```bash
# 设置API密钥
export OPENAI_API_KEY="your-api-key-here"
# 或在配置文件中设置
```

#### 3. 验证安装

```bash
# 检查服务状态
python -m src.cli.main status
```

### CLI使用指南

#### 基本命令

```bash
# 显示帮助信息
python -m src.cli.main --help

# 翻译单个文件
python -m src.cli.main translate input/example.md

# 翻译指定输出文件
python -m src.cli.main translate input/example.md --output output/example.md

# 翻译整个目录
python -m src.cli.main translate input/ --recursive

# 翻译目录到指定输出目录
python -m src.cli.main translate input/ --output output/ --recursive
```

#### 高级选项

```bash
# 指定源语言和目标语言
python -m src.cli.main translate input.md --source-lang en --target-lang zh

# 指定翻译模型
python -m src.cli.main translate input.md --model SimonPu/Hunyuan-MT-Chimera-7B:Q8

# 使用OpenAI模型
python -m src.cli.main translate input.md --model gpt-3.5-turbo

# 覆盖已存在的文件
python -m src.cli.main translate input.md --overwrite

# 详细输出模式
python -m src.cli.main translate input.md --verbose

# 静默模式
python -m src.cli.main translate input.md --quiet

# 使用自定义配置文件
python -m src.cli.main --config custom.toml translate input.md
```

#### 其他命令

```bash
# 查看当前配置
python -m src.cli.main config

# 查看缓存信息
python -m src.cli.main config --show-cache

# 清空翻译缓存
python -m src.cli.main clear-cache

# 演示翻译功能
python -m src.cli.main demo "Hello world"
```

## ⚙️ 配置文件

项目使用TOML格式的配置文件，默认配置位于 `config/default.toml`。您可以创建自定义配置文件：

```toml
[ollama]
host = "http://localhost:11434"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
timeout = 60

[openai]
api_key = "your-api-key-here"
model = "gpt-3.5-turbo"
base_url = "https://api.openai.com/v1"

[translation]
temperature = 0.1
max_tokens = 4000
chunk_size = 1000
source_language = "en"
target_language = "zh"

[cli]
input_dir = "input"
output_dir = "output"
parallel_workers = 4

[cache]
enable_cache = true
cache_dir = ".translation_cache"
max_cache_size_mb = 500
```

## 📁 项目结构

```
UnityLangPX/
├── README.md                    # 项目说明
├── CHANGELOG.md                 # 更新日志
├── RELEASE_NOTES.md             # 发布说明
├── pyproject.toml              # 项目配置
├── .pre-commit-config.yaml     # 代码质量配置
├── .gitignore                  # Git忽略文件
├── scripts/                    # 脚本文件
│   └── run_mcp_server.py      # MCP服务器启动脚本
├── requirements/               # 依赖管理
│   ├── base.txt               # 基础依赖
│   ├── cli.txt                # CLI工具依赖
│   ├── obsidian.txt           # Obsidian插件依赖
│   ├── mcp.txt                # MCP服务器依赖
│   └── dev.txt                # 开发依赖
├── config/                    # 配置文件
│   └── default.toml           # 默认配置
├── src/                       # 源代码
│   ├── core/                  # 核心翻译模块
│   ├── cli/                   # 命令行工具
│   ├── obsidian/              # Obsidian插件
│   └── mcp/                   # MCP服务器
├── docs/                      # 用户文档
│   ├── documentation_index.md  # 文档导航
│   ├── user_guide.md          # 用户使用指南
│   ├── quick_start.md         # 快速开始指南
│   ├── api_reference.md       # API参考文档
│   └── ...                    # 其他用户文档
├── data/                      # 数据文件
│   └── font/                  # 字体文件
├── input/                     # 输入文件目录
├── output/                    # 输出文件目录
├── logs/                      # 日志目录
└── deprecated/                # 废弃文件存档
```

## 📚 文档

### 📖 用户文档
- [快速开始指南](docs/quick_start.md) - 5分钟快速上手 ⭐ **推荐**
- [用户使用指南](docs/user_guide.md) - 完整的使用说明
- [API参考文档](docs/api_reference.md) - 命令行、HTTP和MCP API参考
- [配置管理指南](docs/configuration_guide.md) - 详细的配置说明

### 🔧 平台特定指南
- [Obsidian插件使用指南](docs/obsidian_plugin_usage.md) - 插件使用说明
- [MCP服务器部署指南](docs/mcp_server_deployment.md) - 部署和配置指南

### 📋 功能指南
- [自定义翻译模板功能指南](docs/template_feature_guide.md) - 模板功能使用
- [术语库功能指南](docs/terminology_guide.md) - 术语管理功能

## 🎯 支持的翻译模型

### Ollama本地模型
- SimonPu/Hunyuan-MT-Chimera-7B:Q8（推荐）
- llama2系列
- qwen系列
- 其他兼容Ollama的翻译模型

### OpenAI API模型
- gpt-3.5-turbo
- gpt-4
- gpt-4-turbo

### 其他模型
UnityLangPX采用模块化设计，可以轻松扩展支持其他大模型服务。

## 🚀 快速体验

```bash
# 1. 安装模型（以Ollama为例）
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8

# 2. 创建测试文件
echo "# Hello World\n\nThis is a test document." > test.md

# 3. 翻译文件
python -m src.cli.main translate test.md -o test_zh.md

# 4. 查看结果
cat test_zh.md
```

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！请查看[贡献指南](CONTRIBUTING.md)了解详细信息。

## 📄 许可证

Apache License 2.0

## 📝 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本更新详情。

## 🔗 相关链接

- **项目主页**：https://gitee.com/unitylangpx/unitylangpx
- **问题反馈**：https://gitee.com/unitylangpx/unitylangpx/issues

---

**提示**：如果您需要查看开发文档或历史记录，请参考`deprecated/`目录中的存档文件。