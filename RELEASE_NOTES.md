# UnityLangPX v1.0.0 发布说明

我们很高兴地宣布 UnityLangPX v1.0.0 正式发布！这是一个基于大模型技术的多平台翻译解决方案，专为Markdown文档翻译而设计。

## 🎉 主要特性

### 🌐 多平台支持
- **命令行工具**：强大的CLI工具，支持批量翻译和自动化处理
- **Obsidian插件**：无缝集成到Obsidian笔记软件
- **MCP服务器**：标准化接口，支持多平台集成

### ⚡ 核心功能
- **高质量翻译**：基于先进的大模型技术，提供准确流畅的翻译
- **格式保持**：完美保留Markdown格式，包括代码块、表格和链接
- **批量处理**：支持批量翻译多个文件，提高工作效率
- **智能分块**：自动将长文档分块处理，确保翻译质量
- **术语管理**：支持自定义术语词典，确保专业术语一致性

### 🔧 技术特点
- **多模型支持**：兼容Ollama、OpenAI等多种大模型
- **异步处理**：高效的异步处理架构，提升性能
- **缓存机制**：智能缓存，避免重复翻译
- **可配置性**：丰富的配置选项，满足不同需求

## 🚀 安装方式

### 使用pip安装
```bash
pip install unitylangpx
```

### 从源码安装
```bash
git clone https://gitee.com/unitylangpx/unitylangpx.git
cd unitylangpx
pip install -e .
```

## 📖 快速开始

### 命令行工具
```bash
# 翻译单个文件
unitylangpx translate input.md -o output.md --to zh

# 批量翻译
unitylangpx batch-translate docs/ -o translated/ --to zh

# 启动HTTP服务器
unitylangpx serve --port 8080
```

### Obsidian插件
1. 下载插件文件到Obsidian插件目录
2. 在Obsidian中启用插件
3. 配置翻译模型和API密钥
4. 右键点击文档选择"翻译文档"

### MCP服务器
```bash
# 启动MCP服务器
python -m src.mcp.server

# 在支持MCP的应用中使用
```

## 📋 文档

- [用户使用指南](docs/user_guide.md)
- [快速开始指南](docs/quick_start.md)
- [API参考文档](docs/api_reference.md)

## 🔧 系统要求

- Python 3.11+
- 依赖的大模型服务（如Ollama、OpenAI API等）

## 🐛 已知问题

1. 某些复杂的Markdown表格可能需要手动调整格式
2. 超长文档（>10,000字）可能需要调整分块参数

## 🙏 致谢

感谢所有为UnityLangPX项目做出贡献的开发者和用户！

## 📄 许可证

本项目采用MIT许可证，详见[LICENSE](LICENSE)文件。

## 🔗 相关链接

- 项目主页：https://gitee.com/unitylangpx/unitylangpx
- 文档网站：https://unitylangpx.readthedocs.io
- 问题反馈：https://gitee.com/unitylangpx/unitylangpx/issues

---

**注意**：v1.0.0版本已移除桌面应用功能，专注于命令行工具、Obsidian插件和MCP服务器。如果您需要桌面应用功能，请使用之前的版本或考虑使用命令行工具替代。