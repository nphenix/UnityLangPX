#!/usr/bin/env python3
"""
简单的SSE端点测试脚本
"""

import requests
import json
import time

def test_sse_endpoint(url):
    """测试SSE端点"""
    print(f"测试SSE端点: {url}")
    
    try:
        # 测试GET请求
        response = requests.get(url, timeout=10, stream=True)
        print(f"响应状态: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            # 读取SSE流
            events = []
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    print(f"SSE数据: {decoded_line}")
                    events.append(decoded_line)
                    
                    # 如果收到关闭事件，停止读取
                    if 'event: close' in decoded_line:
                        break
                    
                    # 限制读取的事件数量
                    if len(events) >= 10:
                        break
            
            # 分析事件
            print("\n分析SSE事件...")
            endpoint_found = False
            for event in events:
                if 'event: endpoint' in event:
                    endpoint_found = True
                    print("✓ 找到端点事件")
                    break
            
            if endpoint_found:
                print("✓ SSE端点测试成功 - 找到端点URL事件")
                return True
            else:
                print("✗ SSE端点测试失败 - 未找到端点URL事件")
                return False
        else:
            print(f"✗ SSE端点测试失败 - HTTP状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ SSE端点测试失败: {str(e)}")
        return False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="简单SSE端点测试")
    parser.add_argument("--host", default="localhost", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=4012, help="服务器端口")
    
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    sse_url = f"{base_url}/sse"
    
    print("=" * 60)
    print("UnityLangPX MCP 服务器 SSE 端点简单测试")
    print("=" * 60)
    
    # 测试SSE端点
    sse_ok = test_sse_endpoint(sse_url)
    
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"SSE端点: {'✓ 通过' if sse_ok else '✗ 失败'}")
    
    if sse_ok:
        print("\n🎉 SSE端点测试通过！MCP服务器应该可以正常与Dify集成。")
        return 0
    else:
        print("\n⚠️  SSE端点测试失败，请检查服务器配置。")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())