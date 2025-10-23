@echo off
REM UnityLangPX MCP服务器启动脚本 (Windows批处理)

REM 设置Python路径
set PYTHONPATH=%~dp0..

REM 启动MCP服务器
python scripts/run_mcp_server.py %*

pause