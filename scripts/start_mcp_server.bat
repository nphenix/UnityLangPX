@echo off
REM 启动UnityLangPX MCP服务器用于Dify集成测试

echo ========================================
echo UnityLangPX MCP服务器启动脚本
echo ========================================

REM 检查是否已经安装了必要的依赖
echo 检查依赖...
python -c "import pydantic; import toml; import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo 安装MCP服务器依赖...
    pip install -r requirements/mcp.txt
)

REM 启动MCP服务器
echo 启动MCP服务器...
echo 服务器地址: http://localhost:4010
echo SSE端点: http://localhost:4010/sse
echo.

python scripts/run_mcp_server.py --config config/dify_mcp_config.json --log-level INFO

pause