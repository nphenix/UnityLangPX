# UnityLangPX

基于大模型技术的多平台翻译解决方案

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://img.shields.io/badge/python-3.11+-blue.svg)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://img.shields.io/badge/license-Apache%202.0-green.svg)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
[![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)](https://img.shields.io/badge/status-stable-brightgreen.svg)

## 🌟 项目简介

UnityLangPX 是一个基于大模型技术的多平台翻译解决方案，支持文本、Markdown文件和Obsidian笔记的翻译。项目采用模块化设计，提供统一的配置管理、MCP服务器接口和命令行工具。

## ✨ 核心特性

- 🧠 **智能翻译引擎** - 支持多种大模型提供商（Ollama、OpenAI）
- 📝 **Markdown支持** - 完整保留格式，支持表格、代码块和链接
- 📚 **Obsidian集成** - 原生Obsidian插件支持，直接在笔记中翻译
- 🔧 **MCP服务器** - 实现MCP协议，提供标准化的翻译服务接口
- ⚙️ **统一配置** - 基于Pydantic V2的配置系统，支持多层级覆盖
- 🧪 **完整测试** - 单元测试、集成测试和验证脚本
- 📊 **性能监控** - 内置性能监控和资源使用统计

## 🏗️ 项目结构

```
UnityLangPX/
├── src/                    # 核心源代码
│   ├── config/            # 统一配置系统
│   ├── core/             # 核心功能模块
│   ├── mcp/              # MCP服务器模块
│   ├── cli/             # 命令行接口
│   └── obsidian/         # Obsidian插件
├── config/                  # 配置文件
│   ├── unified_config.toml # 主配置文件
│   └── config_backup/    # 配置备份
├── scripts/               # 工具脚本
│   ├── run_mcp_server.py # MCP服务器启动脚本
│   └── run_tests.py      # 测试运行
├── docs/                  # 完整文档
│   ├── user_guide.md     # 用户使用指南
│   ├── api_reference.md  # API参考文档
│   └── quick_start.md    # 快速开始指南
├── input/                 # 输入目录
├── output/                # 输出目录
└── README.md              # 项目说明
```

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/nphenix/UnityLangPX.git

# 进入目录
cd UnityLangPX

# 安装依赖
pip install -e .
```

### 基本使用

```bash
# 翻译文本
python -m src.cli.main translate "Hello, world!" -o output.md

# 翻译Markdown文件
python -m src.cli.main translate document.md -o document_zh.md

# 启动MCP服务器
python scripts/run_mcp_server.py

# 查看帮助
python -m src.cli.main --help
```

### 配置

项目使用统一的TOML配置文件，支持多层级配置：

```bash
# 查看当前配置
unitylangpx config show

# 设置模型提供商
unitylangpx config set model.provider openai

# 设置API密钥
unitylangpx config set model_openai.api_key "your-api-key"
```

## 📖 文档

- [用户使用指南](docs/user_guide.md) - 详细的使用教程和配置说明
- [快速开始指南](docs/quick_start.md) - 5分钟快速上手
- [API参考文档](docs/api_reference.md) - 完整的API接口文档

## 🧪 测试

```bash
# 运行所有测试
python scripts/run_tests.py all

# 运行单元测试
python scripts/run_tests.py unit

# 生成测试覆盖率报告
python scripts/run_tests.py unit --coverage
```

## 🤝 贡献

欢迎贡献代码、报告问题或提出改进建议！请查看[贡献指南](CONTRIBUTING.md)了解详情。

## 📄 许可证

本项目采用 [Apache 2.0许可证](LICENSE)。

## 🔗 链接

- [项目仓库](https://github.com/nphenix/UnityLangPX)
- [文档站点](https://unitylangpx.readthedocs.io)
- [问题反馈](https://github.com/nphenix/UnityLangPX/issues)

---

**注意**: UnityLangPX 是一个现代化的多平台翻译解决方案，支持命令行工具、Obsidian插件和MCP服务器。项目采用模块化设计，提供完整的配置管理和性能监控功能。