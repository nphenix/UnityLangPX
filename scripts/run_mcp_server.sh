#!/bin/bash
# UnityLangPX MCP服务器启动脚本 (Linux/macOS)

# 设置Python路径
export PYTHONPATH="$(dirname "$0")/.."

# 启动MCP服务器
python scripts/run_mcp_server.py "$@"