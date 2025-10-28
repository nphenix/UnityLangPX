@echo off
chcp 65001 >nul
echo ========================================
echo Quick Start FastMCP Server
echo ========================================

cd /d "%~dp0src\mcp\fastmcp-main"

echo Installing dependencies (if needed)...
if not exist "node_modules" npm install --legacy-peer-deps

echo Building TypeScript code...
npm run build

echo Starting server in new window...
start "FastMCP Server" cmd /k "cd /d \"%~dp0src\mcp\fastmcp-main\" && node dist/unitylang-server.js"

echo Server started in new window. You can close this window.
pause