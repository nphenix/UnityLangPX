# UnityLangPX 项目结构优化建议

## 当前状态分析

经过清理，项目结构已经得到显著改善，但仍有一些可以优化的地方。

## 已完成的清理工作

### ✅ 移动到 deprecated 目录的文件
- **测试文件**: 26个 test_*.py 文件
- **调试文件**: debug_*.py, simple_*.py, analyze_*.py, fix_*.py
- **启动脚本**: 重复的 start_*.py 文件
- **配置文件**: 过时的 dify_mcp_simple.json, dify_mcp_sse_config.json
- **文档**: 11个 dify_*.md 过程文档
- **指南文件**: manual_test_guide.md, dify_mcp_fix_plan.md

### ✅ 保留的核心文件
- **启动脚本**: `scripts/run_mcp_server.py` (主要启动脚本)
- **批处理**: `scripts/run_mcp_server.bat`, `scripts/run_mcp_server.sh`
- **环境设置**: `scripts/setup_env.bat`
- **配置文件**: `config/dify_mcp_config.json`, `config/dify_mcp_docker_fix.json`, `config/dify_mcp_dynamic_config.json`

## 项目结构优化建议

### 1. 目录结构重组

```
UnityLangPX/
├── README.md                    # 主要项目说明
├── pyproject.toml               # 项目配置
├── .gitignore                   # Git忽略文件
├── start_mcp_server.bat         # 主启动入口 (Windows)
├── start_mcp_server.sh          # 主启动入口 (Unix)
│
├── src/                         # 源代码
│   ├── cli/                     # 命令行接口
│   ├── core/                    # 核心功能
│   ├── mcp/                     # MCP协议实现
│   └── obsidian/                # Obsidian插件
│
├── scripts/                     # 工具脚本
│   ├── run_mcp_server.py        # 主启动脚本
│   ├── run_mcp_server.bat       # Windows批处理
│   ├── run_mcp_server.sh        # Unix shell脚本
│   └── setup_env.bat            # 环境设置
│
├── config/                      # 配置文件
│   ├── default.toml             # 默认配置
│   ├── desktop_config.json      # 桌面版配置
│   ├── dify_mcp_config.json    # Dify MCP配置
│   ├── dify_mcp_docker_fix.json # Docker修复配置
│   ├── dify_mcp_dynamic_config.json # 动态配置
│   └── templates.json          # 模板配置
│
├── docs/                        # 文档
│   ├── api_reference.md         # API参考
│   ├── configuration_guide.md   # 配置指南
│   ├── documentation_index.md   # 文档索引
│   ├── mcp_server_deployment.md # MCP部署指南
│   ├── obsidian_plugin_usage.md # Obsidian插件使用
│   ├── quick_start.md           # 快速开始
│   ├── user_guide.md            # 用户指南
│   └── ...                     # 其他核心文档
│
├── requirements/                # 依赖管理
│   ├── base.txt                # 基础依赖
│   ├── cli.txt                 # CLI依赖
│   ├── dev.txt                 # 开发依赖
│   ├── mcp.txt                 # MCP依赖
│   └── obsidian.txt            # Obsidian依赖
│
├── data/                        # 数据文件
│   └── font/                   # 字体文件
│
├── logs/                        # 日志目录
├── input/                       # 输入目录
├── static/                      # 静态文件
├── tools/                       # 工具目录
├── deprecated/                  # 已弃用文件 ⭐
└── -p/                         # 私有配置目录
```

### 2. 启动入口统一

**建议**: 将根目录的启动脚本作为主要入口点

#### Windows (`start_mcp_server.bat`)
```batch
@echo off
echo Starting UnityLangPX MCP Server...
python scripts/run_mcp_server.py %*
pause
```

#### Unix (`start_mcp_server.sh`)
```bash
#!/bin/bash
echo "Starting UnityLangPX MCP Server..."
python3 scripts/run_mcp_server.py "$@"
```

### 3. 配置文件整合

**当前配置文件分析**:
- `dify_mcp_config.json` - 基础配置，使用标准MCP协议
- `dify_mcp_docker_fix.json` - Docker特定配置，包含HTTP服务器
- `dify_mcp_dynamic_config.json` - SSE配置，用于Dify集成

**建议**: 创建一个统一的配置文件，通过参数控制不同模式

### 4. 文档结构优化

**保留的核心文档**:
- ✅ `api_reference.md` - API参考
- ✅ `configuration_guide.md` - 配置指南
- ✅ `documentation_index.md` - 文档索引
- ✅ `mcp_server_deployment.md` - MCP部署指南
- ✅ `obsidian_plugin_usage.md` - Obsidian插件使用
- ✅ `quick_start.md` - 快速开始
- ✅ `user_guide.md` - 用户指南

**可以进一步整理的文档**:
- `terminology_guide.md` - 术语指南
- `template_feature_guide.md` - 模板功能指南
- `release_*.md` - 发布相关文档

### 5. 脚本目录清理

**当前 scripts 目录**:
```
scripts/
├── run_mcp_server.py        ✅ 主要启动脚本
├── run_mcp_server.bat       ✅ Windows批处理
├── run_mcp_server.sh        ✅ Unix shell脚本
└── setup_env.bat           ✅ 环境设置
```

**状态**: 已经很清洁，建议保持现状。

### 6. 根目录清理

**当前根目录问题文件**:
- `start_mcp_server.bat` - 与 scripts/run_mcp_server.bat 重复

**建议**: 
1. 保留根目录的 `start_mcp_server.bat` 作为主入口
2. 删除 scripts 目录下的重复批处理文件
3. 创建对应的 Unix 脚本

### 7. .gitignore 优化

确保以下内容在 .gitignore 中:
```
# 日志文件
*.log
logs/

# 临时文件
temp/
tmp/

# IDE文件
.vscode/
.idea/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# 配置文件 (如果包含敏感信息)
config/local_*.json
```

## 实施优先级

### 🔴 高优先级 (立即执行)
1. **统一启动入口**: 整理根目录和 scripts 目录的启动脚本
2. **配置文件整合**: 减少配置文件数量，提高可维护性
3. **文档索引更新**: 更新 documentation_index.md 反映新结构

### 🟡 中优先级 (近期执行)
1. **目录结构微调**: 根据实际使用情况调整
2. **依赖管理优化**: 检查 requirements 文件的完整性
3. **示例配置添加**: 为不同使用场景提供示例配置

### 🟢 低优先级 (长期规划)
1. **自动化脚本**: 添加项目维护脚本
2. **测试框架**: 建立完整的测试体系
3. **CI/CD配置**: 添加持续集成配置

## 维护建议

### 1. 定期清理
- 每月检查 deprecated 目录
- 清理过时的日志文件
- 更新文档索引

### 2. 版本控制
- 重要更改前创建分支
- 保持 .gitignore 更新
- 定期合并 deprecated 中的有用代码

### 3. 文档维护
- 新功能必须包含文档
- 定期检查文档准确性
- 保持文档与代码同步

## 总结

通过这次清理，项目结构已经显著改善：
- ✅ 移除了 40+ 个过时文件
- ✅ 保留了核心功能文件
- ✅ 建立了 deprecated 目录管理过时代码
- ✅ 统一了启动脚本

建议按照优先级逐步实施剩余的优化措施，确保项目的长期可维护性。