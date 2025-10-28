#!/bin/bash

echo "========================================"
echo "启动FastMCP服务器"
echo "========================================"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 进入FastMCP目录
cd "$SCRIPT_DIR/src/mcp/fastmcp-main"

# 检查Node.js是否安装
if ! command -v node &> /dev/null; then
    echo "错误: 未找到Node.js，请先安装Node.js"
    exit 1
fi

# 检查依赖是否安装
if [ ! -d "node_modules" ]; then
    echo "正在安装Node.js依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "错误: 依赖安装失败"
        exit 1
    fi
fi

# Build TypeScript code
echo "Building TypeScript code..."
npm run build
if [ $? -ne 0 ]; then
    echo "ERROR: TypeScript build failed"
    exit 1
fi

# Check if build output exists
if [ ! -f "dist/unitylang-server.js" ]; then
    echo "ERROR: Build output not found. Trying alternative start method..."
    echo "Starting with ts-node directly..."
    npx ts-node src/unitylang-server.ts
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to start server with ts-node"
        exit 1
    fi
else
    # Start server
    echo "========================================"
    echo "Starting FastMCP Server..."
    echo "Server URL: http://localhost:4010/mcp"
    echo "Press Ctrl+C to stop server"
    echo "========================================"
    npm start
fi