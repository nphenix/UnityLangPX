#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 SSE 端点，查看实际输出
"""
import requests
import time
import json
import sys
import os

# 设置控制台编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')

def debug_sse_endpoint(host="localhost", port=4010):
    """调试 SSE 端点"""
    print(f"调试 SSE 端点: http://{host}:{port}/sse")
    
    try:
        # 连接到 SSE 端点
        response = requests.get(f'http://{host}:{port}/sse', stream=True, timeout=10)
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("\n[OK] 成功连接到 SSE 端点")
            print("\n开始读取事件流...")
            
            # 读取事件
            event_count = 0
            endpoint_found = False
            current_event = None
            all_events = []
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    event_count += 1
                    all_events.append(line)
                    print(f"事件 #{event_count}: {line}")
                    
                    # 检查事件类型
                    if line.startswith('event:'):
                        current_event = line[6:].strip()  # 移除 'event: ' 前缀
                        print(f"  -> 事件类型: {current_event}")
                        
                        if current_event == 'endpoint':
                            print("  -> [关键] 发现端点事件类型")
                    elif line.startswith('data:'):
                        data = line[5:].strip()  # 移除 'data: ' 前缀
                        print(f"  -> 事件数据: {data}")
                        
                        # 如果是端点事件，验证数据
                        if current_event == 'endpoint':
                            endpoint_found = True
                            print(f"  -> [关键] 端点事件数据: {data}")
                            
                            # 尝试解析数据
                            try:
                                if data.startswith('{'):
                                    parsed_data = json.loads(data)
                                    print(f"  -> [解析] JSON数据: {parsed_data}")
                                else:
                                    print(f"  -> [解析] 纯文本数据: '{data}'")
                            except:
                                print(f"  -> [解析] 无法解析数据")
                
                # 限制读取的事件数量
                if event_count >= 20:
                    print("\n[限制] 已读取20个事件，停止读取")
                    break
                
                # 检查是否超时
                time.sleep(0.1)
            
            print(f"\n[总结] 共读取 {event_count} 个事件")
            print(f"[总结] 端点事件: {'找到' if endpoint_found else '未找到'}")
            
            if endpoint_found:
                print("\n[成功] SSE 端点包含端点事件")
                return True
            else:
                print("\n[失败] SSE 端点不包含端点事件")
                print("\n[分析] 所有事件:")
                for i, event in enumerate(all_events):
                    print(f"  {i+1}. {event}")
                return False
        else:
            print(f"[错误] 无法连接到 SSE 端点，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[错误] 连接失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_different_paths(host="localhost", port=4010):
    """测试不同的 SSE 路径"""
    paths = ['/sse', '/events', '/mcp/sse', '/mcp/events']
    
    for path in paths:
        print(f"\n{'='*60}")
        print(f"测试路径: http://{host}:{port}{path}")
        print('='*60)
        
        try:
            response = requests.get(f'http://{host}:{port}{path}', stream=True, timeout=5)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("路径有效")
                # 读取前几个事件
                event_count = 0
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        event_count += 1
                        print(f"事件 {event_count}: {line}")
                        
                        if event_count >= 5:
                            break
                    time.sleep(0.1)
            else:
                print("路径无效")
                
        except Exception as e:
            print(f"错误: {str(e)}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="调试 SSE 端点")
    parser.add_argument("--host", default="localhost", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=4010, help="服务器端口")
    parser.add_argument("--test-paths", action="store_true", help="测试不同的 SSE 路径")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("UnityLangPX MCP 服务器 SSE 端点调试")
    print("=" * 60)
    
    if args.test_paths:
        test_different_paths(args.host, args.port)
    else:
        debug_sse_endpoint(args.host, args.port)

if __name__ == "__main__":
    sys.exit(main())