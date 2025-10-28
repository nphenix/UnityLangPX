# UnityLangPX v1.0.0 正式发布

我们很高兴地宣布 UnityLangPX v1.0.0 正式发布！这是一个基于大模型技术的多平台翻译解决方案，专为Markdown文档翻译而设计。

## 🎉 主要特性

### 🌐 多平台支持
- **命令行工具**：强大的CLI工具，支持批量翻译和自动化处理
- **Obsidian插件**：无缝集成到Obsidian笔记软件
- **MCP服务器**：标准化接口，支持多平台集成
- **HTTP API**：RESTful API，便于集成到各种应用

### ⚡ 核心功能
- **高质量翻译**：基于先进的大模型技术，提供准确流畅的翻译
- **格式保持**：完美保留Markdown格式，包括代码块、表格和链接
- **批量处理**：支持批量翻译多个文件，提高工作效率
- **智能分块**：自动将长文档分块处理，确保翻译质量
- **术语管理**：支持自定义术语词典，确保专业术语一致性
- **性能监控**：内置性能监控和资源使用统计

### 🔧 技术特点
- **多模型支持**：兼容Ollama、OpenAI等多种大模型
- **异步处理**：高效的异步处理架构，提升性能
- **多级缓存**：L1/L2/L3缓存机制，避免重复翻译
- **统一配置**：基于TOML的统一配置系统，支持多层级覆盖
- **可配置性**：丰富的配置选项，满足不同需求

## 🚀 安装方式

### 从源码安装（推荐）
```bash
git clone https://github.com/nphenix/UnityLangPX.git
cd UnityLangPX
pip install -e .
```

## 📖 快速开始

### 环境准备
```bash
# 安装Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 下载翻译模型
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8
```

### 基本使用
```bash
# 翻译单个文件
python -m src.cli.main translate README.md -o README_zh.md

# 翻译目录
python -m src.cli.main translate docs/ -o docs_zh/ -r

# 启动MCP服务器
python scripts/run_mcp_server.py

# 启动HTTP API服务器
python -m src.cli.main serve
```

### Obsidian插件
1. 将插件文件复制到Obsidian插件目录
2. 在Obsidian中启用插件
3. 配置翻译模型和API密钥
4. 右键点击文档选择"翻译文档"

## 📋 完整文档

- [📖 用户使用指南](docs/user_guide.md) - 详细的使用教程和配置说明
- [🚀 快速开始指南](docs/quick_start.md) - 5分钟快速上手
- [🔧 API参考文档](docs/api_reference.md) - 完整的API接口文档
- [⚙️ 配置指南](docs/configuration_guide.md) - 配置文件详解

## 🔧 系统要求

### 基础要求
- **Python**: 3.11 或更高版本
- **操作系统**: Windows 10/11, Ubuntu 20.04+, macOS 12+
- **内存**: 4GB RAM（推荐8GB）
- **存储**: 10GB可用空间

### 依赖服务
- **Ollama**: 本地部署的大模型服务
- **翻译模型**: SimonPu/Hunyuan-MT-Chimera-7B:Q8

## 🐛 已知问题

1. 某些复杂的Markdown表格可能需要手动调整格式
2. 超长文档（>10,000字）可能需要调整分块参数
3. 部分单元测试存在mock对象问题，不影响实际功能使用

## 🙏 致谢

感谢所有为UnityLangPX项目做出贡献的开发者和用户！

## 📄 许可证

本项目采用Apache 2.0许可证，详见[LICENSE](LICENSE)文件。

## 🔗 相关链接

- 📦 **项目仓库**: https://github.com/nphenix/UnityLangPX
- 📚 **文档网站**: https://unitylangpx.readthedocs.io
- 💬 **问题反馈**: https://github.com/nphenix/UnityLangPX/issues
- 🤝 **贡献指南**: https://github.com/nphenix/UnityLangPX/blob/main/CONTRIBUTING.md

---

**🎉 UnityLangPX v1.0.0 正式发布！这是一个稳定、功能完整的多平台翻译解决方案，欢迎使用和贡献！**