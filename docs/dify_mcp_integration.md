# UnityLangPX MCP 与 Dify 集成指南

## 1. 概述

本指南将帮助您将 UnityLangPX MCP 服务集成到 Dify 平台中，实现强大的翻译功能。

## 2. 准备工作

### 2.1 确保 MCP 服务正常运行

首先确保 UnityLangPX MCP 服务已正确安装并可以运行：

```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 测试 MCP 服务
python -m src.mcp.server --help
```

### 2.2 确保 Ollama 服务运行

```bash
# 检查 Ollama 状态
ollama list

# 确保翻译模型已下载
ollama pull SimonPu/Hunyuan-MT-Chimera-7B:Q8
```

## 3. Dify 配置步骤

### 3.1 方法一：使用简化配置文件

1. 使用我们提供的简化配置文件：`config/dify_mcp_simple.json`

2. 在 Dify 中：
   - 进入 "设置" > "模型提供商"
   - 找到 "MCP" 或 "自定义工具" 部分
   - 点击 "添加" 或 "上传"
   - 选择 `config/dify_mcp_simple.json` 文件
   - 配置环境变量（如果需要）

### 3.2 方法二：手动配置

如果上传文件仍然失败，你可以尝试手动配置：

1. 在 Dify 中创建新的 MCP 配置
2. 使用以下参数：

```json
{
  "name": "UnityLangPX Translation",
  "command": "python",
  "args": ["-m", "src.mcp.server"],
  "env": {
    "PYTHONPATH": ".",
    "UNITYLANGPX_MCP_ENABLED": "true",
    "UNITYLANGPX_MCP_LOG_LEVEL": "INFO"
  }
}
```

### 3.3 方法三：使用完整配置

如果需要更多控制，可以使用 `config/dify_mcp_config.json` 文件，其中包含了详细的工具定义。

## 4. 环境变量配置

根据你的部署环境，可能需要设置以下环境变量：

```bash
# 基础配置
PYTHONPATH=.  # Python 路径
UNITYLANGPX_MCP_ENABLED=true  # 启用 MCP 服务
UNITYLANGPX_MCP_PORT=4010  # MCP 服务端口
UNITYLANGPX_MCP_LOG_LEVEL=INFO  # 日志级别

# Ollama 配置
OLLAMA_HOST=http://localhost:11434  # Ollama 服务地址
OLLAMA_MODEL=SimonPu/Hunyuan-MT-Chimera-7B:Q8  # 翻译模型

# 安全配置（可选）
UNITYLANGPX_MCP_API_KEY=your_api_key  # API 密钥
```

## 5. 故障排除

### 5.1 "Upload failed: invalid_param" 错误

这个错误通常由以下原因引起：

1. **JSON 格式错误**
   - 检查 JSON 文件是否有语法错误
   - 使用在线 JSON 验证工具验证格式

2. **缺少必要字段**
   - 确保 `name`、`command` 字段存在
   - 检查 `args` 数组格式是否正确

3. **路径问题**
   - 确保 Python 路径正确
   - 检查工作目录设置

### 5.2 连接问题

如果 MCP 服务无法连接：

1. 检查服务是否正在运行
2. 验证端口是否被占用
3. 检查防火墙设置

### 5.3 权限问题

确保 Dify 有权限：
1. 执行 Python 脚本
2. 访问项目目录
3. 读写日志和缓存文件

## 6. 测试集成

配置完成后，在 Dify 中测试：

1. 创建简单的对话
2. 尝试使用翻译功能
3. 检查日志输出

## 7. 高级配置

### 7.1 自定义工具

如果需要自定义工具，可以修改 `config/dify_mcp_config.json` 中的工具定义。

### 7.2 性能优化

1. 调整 `max_connections` 参数
2. 启用缓存
3. 优化模型参数

## 8. 生产环境部署

在生产环境中：

1. 使用 HTTPS
2. 启用 API 密钥认证
3. 配置 IP 白名单
4. 设置日志轮转

## 9. 常见问题

### Q: Dify 无法找到 MCP 服务？
A: 检查 PYTHONPATH 设置和 Python 命令路径。

### Q: 翻译质量不佳？
A: 尝试调整 temperature 参数或使用更大的模型。

### Q: 服务启动缓慢？
A: 考虑预热模型或使用 GPU 加速。

## 10. 支持

如果遇到问题：

1. 查看 Dify 和 MCP 服务的日志
2. 检查我们的 GitHub Issues
3. 提交详细的错误报告

---

**文档版本**：1.0  
**创建日期**：2025-10-23  
**最后更新**：2025-10-23  
**维护者**：UnityLangPX团队