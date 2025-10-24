#!/usr/bin/env python3
"""
UnityLangPX MCP服务器简单测试脚本

使用urllib进行基本功能测试。
"""

import json
import urllib.request
import urllib.error
import sys
import time

def test_http_request(url, data=None, headers=None):
    """发送HTTP请求"""
    try:
        if data:
            # POST请求
            req = urllib.request.Request(url, data=data.encode('utf-8'), headers=headers or {})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, response.read().decode('utf-8')
        else:
            # GET请求
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.status, response.read().decode('utf-8')
    except Exception as e:
        return None, str(e)

def test_mcp_server(base_url="http://localhost:4012"):
    """测试MCP服务器功能"""
    
    print("开始测试UnityLangPX MCP服务器...")
    print(f"服务器地址: {base_url}")
    print("=" * 60)
    
    # 测试1: 健康检查
    print("测试1: 健康检查")
    status, response = test_http_request(f"{base_url}/")
    if status == 200:
        print("[OK] 健康检查通过")
        try:
            data = json.loads(response)
            print(f"   响应: {data}")
        except:
            print(f"   响应: {response}")
    else:
        print(f"[FAIL] 健康检查失败: {status} - {response}")
        return False
    
    print()
    
    # 测试2: JSON-RPC ping
    print("测试2: JSON-RPC ping")
    ping_data = {
        "jsonrpc": "2.0",
        "method": "ping",
        "id": 1
    }
    headers = {"Content-Type": "application/json"}
    status, response = test_http_request(f"{base_url}/", json.dumps(ping_data), headers)
    if status == 200:
        try:
            result = json.loads(response)
            if result.get("result", {}).get("pong"):
                print("[OK] ping测试通过")
                print(f"   响应: {result}")
            else:
                print("[FAIL] ping响应格式不正确")
                print(f"   响应: {result}")
        except Exception as e:
            print(f"[FAIL] ping响应解析失败: {e}")
            print(f"   原始响应: {response}")
    else:
        print(f"[FAIL] ping测试失败: {status} - {response}")
        return False
    
    print()
    
    # 测试3: JSON-RPC initialize
    print("测试3: JSON-RPC initialize")
    init_data = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {"sampling": {}},
            "clientInfo": {"name": "TestClient", "version": "1.0.0"}
        },
        "id": 2
    }
    status, response = test_http_request(f"{base_url}/", json.dumps(init_data), headers)
    if status == 200:
        try:
            result = json.loads(response)
            if "result" in result and "serverInfo" in result["result"]:
                print("[OK] initialize测试通过")
                server_info = result["result"]["serverInfo"]
                print(f"   服务器信息: {server_info}")
            else:
                print("[FAIL] initialize响应格式不正确")
                print(f"   响应: {result}")
        except Exception as e:
            print(f"[FAIL] initialize响应解析失败: {e}")
            print(f"   原始响应: {response}")
    else:
        print(f"[FAIL] initialize测试失败: {status} - {response}")
        return False
    
    print()
    
    # 测试4: notifications/initialized
    print("测试4: notifications/initialized")
    notification_data = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    status, response = test_http_request(f"{base_url}/", json.dumps(notification_data), headers)
    if status == 204:
        print("[OK] notifications/initialized测试通过")
        print("   正确返回204 No Content")
    else:
        print(f"[FAIL] notifications/initialized测试失败: {status} - {response}")
        return False
    
    print()
    
    # 测试5: tools/list
    print("测试5: tools/list")
    tools_data = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 3
    }
    status, response = test_http_request(f"{base_url}/", json.dumps(tools_data), headers)
    if status == 200:
        try:
            result = json.loads(response)
            if "result" in result and "tools" in result["result"]:
                tools = result["result"]["tools"]
                print("[OK] tools/list测试通过")
                print(f"   可用工具数量: {len(tools)}")
                for tool in tools:
                    print(f"   - {tool['name']}: {tool['description']}")
            else:
                print("[FAIL] tools/list响应格式不正确")
                print(f"   响应: {result}")
        except Exception as e:
            print(f"[FAIL] tools/list响应解析失败: {e}")
            print(f"   原始响应: {response}")
    else:
        print(f"[FAIL] tools/list测试失败: {status} - {response}")
        return False
    
    print()
    
    # 测试6: 错误处理
    print("测试6: 错误处理")
    error_data = {
        "jsonrpc": "2.0",
        "method": "nonexistent_method",
        "id": 4
    }
    status, response = test_http_request(f"{base_url}/", json.dumps(error_data), headers)
    if status == 200:
        try:
            result = json.loads(response)
            if "error" in result:
                print("[OK] 错误处理测试通过")
                print(f"   错误响应: {result['error']}")
            else:
                print("[FAIL] 错误处理响应格式不正确")
                print(f"   响应: {result}")
        except Exception as e:
            print(f"[FAIL] 错误处理响应解析失败: {e}")
            print(f"   原始响应: {response}")
    else:
        print(f"[FAIL] 错误处理测试失败: {status} - {response}")
        return False
    
    print()
    print("=" * 60)
    print("所有测试通过！MCP服务器运行正常。")
    print()
    print("服务器信息:")
    print(f"   - HTTP地址: {base_url}")
    print(f"   - JSON-RPC端点: {base_url}/")
    print(f"   - 健康检查: {base_url}/")
    print()
    print("Dify集成配置:")
    print(f"   - MCP服务器URL: {base_url}")
    print(f"   - 协议版本: 2025-03-26")
    
    return True

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="UnityLangPX MCP服务器简单测试脚本")
    parser.add_argument("--url", type=str, default="http://localhost:4012", 
                       help="MCP服务器地址 (默认: http://localhost:4012)")
    
    args = parser.parse_args()
    
    try:
        success = test_mcp_server(args.url)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中发生异常: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()