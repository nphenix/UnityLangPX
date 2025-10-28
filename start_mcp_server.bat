@echo off
:: FastMCP Server 启动脚本 - Windows版本
:: 基于工作正常的start_fastmcp_server.sh脚本移植

:: 设置代码页为UTF-8以支持中文显示
chcp 65001 >nul

:: 设置控制台窗口标题
title FastMCP Server

:: 设置控制台窗口大小和颜色
mode con: cols=80 lines=25
color 0a

:: 打印启动信息
echo.
echo ========================================
echo 启动FastMCP服务器
echo ========================================
echo.

:: 进入FastMCP目录（使用脚本所在目录）
cd /d "%~dp0src\mcp\fastmcp-main"

:: 检查Node.js是否安装
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Node.js，请先安装Node.js
    pause
    exit /b 1
)

:: 检查依赖是否安装
if not exist "node_modules" (
    echo 正在安装Node.js依赖...
    npm install
    if %errorlevel% neq 0 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

:: 检查编译输出是否存在
if exist "dist\unitylang-server.js" (
    :: 直接使用编译后的文件启动（您手工启动的有效命令）
    echo ========================================
    echo Starting FastMCP Server with pre-built file...
    echo Server URL: http://localhost:4010/mcp
    echo Press Ctrl+C to stop server
    echo ========================================
    node dist/unitylang-server.js
    goto end
) else (
    :: 如果没有编译文件，则进行编译
    echo 编译文件不存在，正在编译TypeScript代码...
    npm run build
    if %errorlevel% neq 0 (
        echo ERROR: TypeScript build failed
        echo 尝试使用开发模式启动...
        goto dev_start
    )
    
    :: 再次检查编译输出
    if exist "dist\unitylang-server.js" (
        echo ========================================
        echo Starting FastMCP Server with newly built file...
        echo Server URL: http://localhost:4010/mcp
        echo Press Ctrl+C to stop server
        echo ========================================
        node dist/unitylang-server.js
        goto end
    ) else (
        echo ERROR: Build completed but output file not found
        goto dev_start
    )
)

:dev_start
echo ========================================
echo Starting FastMCP Server in development mode...
echo Server URL: http://localhost:4010/mcp
echo Press Ctrl+C to stop server
echo ========================================
npx ts-node src/unitylang-server.ts
if %errorlevel% neq 0 (
    echo ERROR: Failed to start server
    pause
    exit /b 1
)

:: 如果服务器意外退出，显示错误信息
if %errorlevel% neq 0 (
    echo.
    echo 服务器意外停止
    echo.
    pause
)

exit /b %errorlevel%