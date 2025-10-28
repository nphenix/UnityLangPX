#!/bin/bash
# FastMCP Server 启动脚本
# 本脚本用于在Linux/macOS系统上启动FastMCP服务器

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印启动信息
echo ""
echo "========================================"
echo "  FastMCP Server 启动脚本"
echo "========================================"
echo ""

# 检查Node.js环境
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ 错误：未找到Node.js，请先安装Node.js！${NC}"
    echo "下载地址：https://nodejs.org/"
    echo ""
    exit 1
fi

# 进入FastMCP目录
cd "$(dirname "$0")/src/mcp/fastmcp-main" || {
    echo -e "${RED}❌ 错误：无法进入FastMCP目录，请确保在项目根目录下运行此脚本！${NC}"
    echo "当前目录：$(pwd)"
    echo ""
    exit 1
}

# 检查项目根目录
if [ ! -f "package.json" ]; then
    echo -e "${RED}❌ 错误：未找到package.json，请确保在项目根目录下运行此脚本！${NC}"
    echo "当前目录：$(pwd)"
    echo ""
    exit 1
fi

# 检查依赖是否安装
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  正在安装Node.js依赖...${NC}"
    npm install
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 错误：依赖安装失败，请检查网络连接${NC}"
        echo ""
        exit 1
    fi
fi

# 编译TypeScript代码
echo "正在编译TypeScript代码..."
npm run build
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  TypeScript编译失败，尝试开发模式...${NC}"
    goto_dev=1
fi

# 检查编译输出
if [ ! -f "dist/unitylang-server.js" ]; then
    echo -e "${YELLOW}⚠️  编译输出未找到，尝试开发模式...${NC}"
    goto_dev=1
fi

# 正常启动服务器
if [ "$goto_dev" = "1" ]; then
    echo ""
    echo -e "${GREEN}✅ 开发模式启动FastMCP服务器...${NC}"
    echo "   服务器将运行在：http://localhost:4010/mcp"
    echo "   按 Ctrl+C 可以停止服务器"
    echo ""
    echo "========================================"
    echo ""
    npx ts-node src/unitylang-server.ts
else
    echo ""
    echo -e "${GREEN}✅ 编译完成，正在启动FastMCP服务器...${NC}"
    echo "   服务器将运行在：http://localhost:4010/mcp"
    echo "   按 Ctrl+C 可以停止服务器"
    echo ""
    echo "========================================"
    echo ""
    npm start
fi

# 检查退出状态
if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ 服务器意外停止${NC}"
    echo ""
    exit 1
fi