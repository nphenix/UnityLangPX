# UnityLangPX 快速开始指南

## 🚀 5分钟快速上手

### 前置要求
- Python 3.11+
- Ollama 已安装并运行

### 第一步：安装模型
```bash
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8
```

### 第二步：下载项目
```bash
git clone https://gitee.com/unitylangpx/unitylangpx.git
cd unitylangpx
```

### 第三步：安装依赖
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows
pip install -r requirements/cli.txt
```

### 第四步：验证安装
```bash
python -m src.cli.main status
```

### 第五步：开始翻译
```bash
# 创建测试文件
echo "# Hello World\n\nThis is a test document." > test.md

# 翻译文件
python -m src.cli.main translate test.md -o test_zh.md

# 查看结果
cat test_zh.md
```

## 📋 常用命令速查

### 基础操作
```bash
# 查看帮助
python -m src.cli.main --help

# 检查状态
python -m src.cli.main status

# 翻译文件
python -m src.cli.main translate input.md -o output.md

# 翻译目录
python -m src.cli.main translate docs/ -o docs_zh/ -r
```

### 服务器模式
```bash
# 启动HTTP API服务器
python -m src.cli.main serve

# 启动MCP服务器
python scripts/run_mcp_server.py
```

### 缓存管理
```bash
# 清空缓存
python -m src.cli.main clear-cache
```

## 🔧 配置示例

### 基础配置文件 (`config.toml`)
```toml
[translation]
source_language = "en"
target_language = "zh"

[model_ollama]
host = "http://localhost:11434"
model = "SimonPu/Hunyuan-MT-Chimera-7B:Q8"
```

## 📝 使用场景

### 场景1：翻译单个文档
```bash
python -m src.cli.main translate README.md -o README_zh.md
```

### 场景2：批量翻译项目文档
```bash
python -m src.cli.main translate docs/ -o docs_zh/ -r --overwrite
```

### 场景3：集成到工作流
```bash
# 在CI/CD中使用
python -m src.cli.main translate changelog.md -o changelog_zh.md -q
```

## 🛠️ 故障排除

### 常见问题及解决方案

1. **Ollama连接失败**
   ```bash
   # 检查Ollama是否运行
   ollama list
   
   # 重启Ollama服务
   # Linux: sudo systemctl restart ollama
   # Windows/macOS: 重新启动Ollama应用
   ```

2. **模型未找到**
   ```bash
   # 下载模型
   ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8
   ```

3. **Python环境问题**
   ```bash
   # 确保Python版本
   python --version  # 应该是3.11+
   
   # 重新创建虚拟环境
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements/cli.txt
   ```

## 📚 更多资源

- [完整用户指南](user_guide.md)
- [API文档](api_reference.md)
- [MCP服务器指南](mcp_server_deployment.md)
- [故障排除](troubleshooting.md)

## 🆘 获取帮助

如果遇到问题，请：
1. 查看[完整用户指南](user_guide.md)
2. 搜索[已知问题](https://gitee.com/unitylangpx/unitylangpx/issues)
3. 提交新的[Issue](https://gitee.com/unitylangpx/unitylangpx/issues/new)

---

**开始您的翻译之旅吧！** 🌍