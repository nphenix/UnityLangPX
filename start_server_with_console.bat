@echo off
chcp 65001 >nul
echo ========================================
echo Start FastMCP Server with Console
echo ========================================

cd /d "%~dp0src\mcp\fastmcp-main"

echo Installing dependencies (if needed)...
if not exist "node_modules" npm install --legacy-peer-deps

echo Building TypeScript code...
npm run build

echo Starting server with console...
echo You will see all server output in this window.
echo Press Ctrl+C to stop the server.
echo ========================================
node dist/unitylang-server.js

pause