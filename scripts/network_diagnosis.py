#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP服务器网络诊断工具
用于诊断Dify连接问题和502错误
"""

import socket
import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_port_binding(host, port):
    """检查端口绑定状态"""
    print(f"检查端口绑定: {host}:{port}")
    try:
        # 检查端口是否被占用
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ 端口 {port} 可访问")
            return True
        else:
            print(f"✗ 端口 {port} 不可访问，错误代码: {result}")
            return False
    except Exception as e:
        print(f"✗ 端口检查失败: {str(e)}")
        return False

def check_local_network():
    """检查本地网络配置"""
    print("\n=== 本地网络配置检查 ===")
    
    # 获取本机IP地址
    try:
        # 连接到外部地址获取实际IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"本机IP地址: {local_ip}")
        
        # 获取主机名
        hostname = socket.gethostname()
        print(f"主机名: {hostname}")
        
        # 获取所有网络接口
        host_ip = socket.gethostbyname(hostname)
        print(f"主机名解析IP: {host_ip}")
        
        return local_ip
    except Exception as e:
        print(f"获取网络信息失败: {str(e)}")
        return "127.0.0.1"

def check_docker_connectivity():
    """检查Docker网络连接"""
    print("\n=== Docker网络连接检查 ===")
    
    docker_hosts = [
        "host.docker.internal",
        "localhost",
        "127.0.0.1"
    ]
    
    for host in docker_hosts:
        print(f"检查Docker主机: {host}")
        try:
            # 尝试解析主机名
            ip = socket.gethostbyname(host)
            print(f"  {host} -> {ip}")
            
            # 检查端口连接
            if check_port_binding(host, 4010):
                print(f"  ✓ {host}:4010 可访问")
            else:
                print(f"  ✗ {host}:4010 不可访问")
                
        except Exception as e:
            print(f"  ✗ {host} 解析失败: {str(e)}")

def check_http_endpoints():
    """检查HTTP端点"""
    print("\n=== HTTP端点检查 ===")
    
    endpoints = [
        "http://localhost:4010/",
        "http://localhost:4010/health",
        "http://localhost:4010/sse",
        "http://127.0.0.1:4010/",
        "http://127.0.0.1:4010/health",
        "http://127.0.0.1:4010/sse"
    ]
    
    for endpoint in endpoints:
        print(f"检查端点: {endpoint}")
        try:
            response = requests.get(endpoint, timeout=5)
            print(f"  ✓ 状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✓ 响应内容: {response.text[:100]}...")
        except requests.exceptions.ConnectionError:
            print(f"  ✗ 连接被拒绝")
        except requests.exceptions.Timeout:
            print(f"  ✗ 连接超时")
        except Exception as e:
            print(f"  ✗ 检查失败: {str(e)}")

def check_firewall_issues():
    """检查防火墙问题"""
    print("\n=== 防火墙检查 ===")
    
    # 检查Windows防火墙状态（仅Windows）
    if sys.platform == 'win32':
        try:
            import subprocess
            result = subprocess.run(
                ['netsh', 'advfirewall', 'show', 'allprofiles'],
                capture_output=True, text=True, timeout=10, encoding='utf-8'
            )
            if result.returncode == 0:
                print("Windows防火墙状态:")
                print(result.stdout)
            else:
                print("无法获取防火墙状态")
        except Exception as e:
            print(f"防火墙检查失败: {str(e)}")
            # 尝试使用默认编码
            try:
                result = subprocess.run(
                    ['netsh', 'advfirewall', 'show', 'allprofiles'],
                    capture_output=True, timeout=10
                )
                if result.returncode == 0:
                    print("Windows防火墙状态:")
                    try:
                        output = result.stdout.decode('gbk', errors='ignore')
                        print(output)
                    except:
                        output = result.stdout.decode('utf-8', errors='ignore')
                        print(output)
            except Exception as e2:
                print(f"备用防火墙检查也失败: {str(e2)}")
    else:
        print("非Windows系统，跳过防火墙检查")

def diagnose_502_error():
    """诊断502错误"""
    print("\n=== 502错误诊断 ===")
    
    print("502 Bad Gateway错误的可能原因:")
    print("1. MCP服务器未正确启动")
    print("2. 端口4010被其他程序占用")
    print("3. 防火墙阻止了端口访问")
    print("4. Docker网络配置问题")
    print("5. 服务器绑定到错误的IP地址")
    print("6. 服务器内部处理错误")
    
    print("\n建议的解决方案:")
    print("1. 确保MCP服务器正在运行")
    print("2. 检查端口4010是否被占用")
    print("3. 临时关闭防火墙测试")
    print("4. 检查Docker网络配置")
    print("5. 确保服务器绑定到0.0.0.0而不是127.0.0.1")
    print("6. 查看MCP服务器日志获取详细错误信息")

def main():
    """主函数"""
    print("MCP服务器网络诊断工具")
    print("=" * 50)
    
    # 检查本地网络
    local_ip = check_local_network()
    
    # 检查端口绑定
    print("\n=== 端口绑定检查 ===")
    hosts_to_check = ["localhost", "127.0.0.1", "0.0.0.0", local_ip]
    for host in hosts_to_check:
        check_port_binding(host, 4010)
    
    # 检查Docker连接
    check_docker_connectivity()
    
    # 检查HTTP端点
    check_http_endpoints()
    
    # 检查防火墙
    check_firewall_issues()
    
    # 诊断502错误
    diagnose_502_error()
    
    print("\n=== 诊断完成 ===")
    print("如果问题仍然存在，请:")
    print("1. 查看MCP服务器日志")
    print("2. 检查Dify容器日志")
    print("3. 确认网络配置正确")
    print("4. 尝试重启MCP服务器和Dify容器")

if __name__ == "__main__":
    main()