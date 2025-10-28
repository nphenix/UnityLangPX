#!/usr/bin/env python3
"""
UnityLangPX MCP服务器性能测试脚本

用于测试智能路由系统的性能，包括客户端检测、适配器选择和请求处理性能。
"""

import asyncio
import json
import time
import statistics
import threading
import concurrent.futures
from typing import List, Dict, Any
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock
from src.mcp.smart_router import SmartRouter, ClientDetector
from src.mcp.dify_adapter import DifySSEAdapter
from src.mcp.standard_adapter import StandardMCPAdapter
from src.mcp.config import MCPConfig


class PerformanceTestSuite:
    """性能测试套件"""
    
    def __init__(self):
        self.config = MCPConfig()
        self.mcp_server = self._create_mock_server()
        self.results = {}
    
    def _create_mock_server(self):
        """创建模拟MCP服务器"""
        server = Mock()
        server.config = self.config
        server.translator = Mock()
        server.translator.translate_text.return_value = Mock(
            success=True,
            translated_text="翻译结果"
        )
        return server
    
    def run_all_tests(self):
        """运行所有性能测试"""
        print("开始UnityLangPX MCP服务器性能测试")
        print("=" * 60)
        
        # 客户端检测性能测试
        self.test_client_detection_performance()
        
        # 智能路由性能测试
        self.test_smart_routing_performance()
        
        # 适配器性能测试
        self.test_adapter_performance()
        
        # 并发性能测试
        self.test_concurrent_performance()
        
        # 内存使用测试
        self.test_memory_usage()
        
        # 生成性能报告
        self.generate_performance_report()
    
    def test_client_detection_performance(self):
        """测试客户端检测性能"""
        print("\n客户端检测性能测试")
        print("-" * 40)
        
        detector = ClientDetector()
        
        # 创建测试用例
        test_cases = [
            {
                "name": "Dify客户端",
                "headers": {
                    "User-Agent": "Dify/1.0.0",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer token123"
                },
                "path": "/sse",
                "expected": "dify"
            },
            {
                "name": "标准MCP客户端",
                "headers": {
                    "User-Agent": "MCP-Client/1.0.0",
                    "Content-Type": "application/json"
                },
                "path": "/health",
                "expected": "standard"
            },
            {
                "name": "未知客户端",
                "headers": {
                    "User-Agent": "Unknown-Client/1.0.0",
                    "Content-Type": "application/json"
                },
                "path": "/unknown",
                "expected": "standard"
            }
        ]
        
        detection_times = []
        
        for test_case in test_cases:
            print(f"  测试 {test_case['name']}...")
            
            # 创建模拟处理器
            handler = Mock()
            handler.headers = test_case['headers']
            handler.path = test_case['path']
            
            # 测量检测时间
            times = []
            for _ in range(100):  # 每个测试用例运行100次
                start_time = time.perf_counter()
                result = detector.detect_client_type(handler)
                end_time = time.perf_counter()
                
                times.append(end_time - start_time)
                
                # 验证结果
                assert result == test_case['expected'], f"检测结果不匹配: 期望 {test_case['expected']}, 实际 {result}"
            
            # 计算统计信息
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = statistics.stdev(times)
            
            detection_times.extend(times)
            
            print(f"    平均时间: {avg_time*1000:.3f}ms")
            print(f"    最小时间: {min_time*1000:.3f}ms")
            print(f"    最大时间: {max_time*1000:.3f}ms")
            print(f"    标准差: {std_dev*1000:.3f}ms")
        
        # 缓存性能测试
        print("\n  缓存性能测试...")
        handler = Mock()
        handler.headers = {"User-Agent": "Dify/1.0.0"}
        handler.path = "/sse"
        
        # 第一次检测（无缓存）
        start_time = time.perf_counter()
        detector.detect_client_type(handler)
        first_time = time.perf_counter() - start_time
        
        # 第二次检测（有缓存）
        start_time = time.perf_counter()
        detector.detect_client_type(handler)
        cached_time = time.perf_counter() - start_time
        
        cache_speedup = (first_time - cached_time) / first_time * 100
        print(f"    首次检测: {first_time*1000:.3f}ms")
        print(f"    缓存检测: {cached_time*1000:.3f}ms")
        print(f"    缓存加速: {cache_speedup:.1f}%")
        
        self.results['client_detection'] = {
            'avg_time': statistics.mean(detection_times),
            'min_time': min(detection_times),
            'max_time': max(detection_times),
            'std_dev': statistics.stdev(detection_times),
            'cache_speedup': cache_speedup
        }
    
    def test_smart_routing_performance(self):
        """测试智能路由性能"""
        print("\n智能路由性能测试")
        print("-" * 40)
        
        router = SmartRouter(self.mcp_server)
        
        # 创建测试用例
        test_cases = [
            {
                "name": "Dify SSE请求",
                "headers": {"User-Agent": "Dify/1.0.0"},
                "path": "/sse",
                "request_type": "sse"
            },
            {
                "name": "Dify消息请求",
                "headers": {"User-Agent": "Dify/1.0.0"},
                "path": "/messages",
                "request_type": "message"
            },
            {
                "name": "标准HTTP请求",
                "headers": {"User-Agent": "MCP-Client/1.0.0"},
                "path": "/health",
                "request_type": "http"
            }
        ]
        
        routing_times = []
        
        for test_case in test_cases:
            print(f"  测试 {test_case['name']}...")
            
            # 创建模拟处理器
            handler = Mock()
            handler.headers = test_case['headers']
            handler.path = test_case['path']
            
            # 测量路由时间
            times = []
            for _ in range(100):
                start_time = time.perf_counter()
                router.route_request(handler, test_case['request_type'])
                end_time = time.perf_counter()
                
                times.append(end_time - start_time)
            
            # 计算统计信息
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = statistics.stdev(times)
            
            routing_times.extend(times)
            
            print(f"    平均时间: {avg_time*1000:.3f}ms")
            print(f"    最小时间: {min_time*1000:.3f}ms")
            print(f"    最大时间: {max_time*1000:.3f}ms")
            print(f"    标准差: {std_dev*1000:.3f}ms")
        
        self.results['smart_routing'] = {
            'avg_time': statistics.mean(routing_times),
            'min_time': min(routing_times),
            'max_time': max(routing_times),
            'std_dev': statistics.stdev(routing_times)
        }
    
    def test_adapter_performance(self):
        """测试适配器性能"""
        print("\n适配器性能测试")
        print("-" * 40)
        
        # 测试Dify适配器
        print("  测试Dify适配器...")
        dify_adapter = DifySSEAdapter(self.mcp_server)
        
        handler = Mock()
        handler.headers = {
            "Host": "localhost:4010",
            "User-Agent": "Dify/1.0.0",
            "Content-Length": "100"
        }
        handler.path = "/messages"
        handler.rfile.read.return_value = b'{"jsonrpc": "2.0", "id": 1, "method": "ping"}'
        
        # 模拟响应方法
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = Mock()
        
        # 测量处理时间
        dify_times = []
        for _ in range(50):
            start_time = time.perf_counter()
            dify_adapter.handle_message_request(handler)
            end_time = time.perf_counter()
            
            dify_times.append(end_time - start_time)
        
        # 测试标准适配器
        print("  测试标准适配器...")
        standard_adapter = StandardMCPAdapter(self.mcp_server)
        
        # 测量处理时间
        standard_times = []
        for _ in range(50):
            start_time = time.perf_counter()
            standard_adapter.handle_message_request(handler)
            end_time = time.perf_counter()
            
            standard_times.append(end_time - start_time)
        
        # 计算统计信息
        dify_avg = statistics.mean(dify_times)
        standard_avg = statistics.mean(standard_times)
        
        print(f"    Dify适配器平均时间: {dify_avg*1000:.3f}ms")
        print(f"    标准适配器平均时间: {standard_avg*1000:.3f}ms")
        
        self.results['adapter_performance'] = {
            'dify_avg': dify_avg,
            'standard_avg': standard_avg,
            'dify_times': dify_times,
            'standard_times': standard_times
        }
    
    def test_concurrent_performance(self):
        """测试并发性能"""
        print("\n并发性能测试")
        print("-" * 40)
        
        router = SmartRouter(self.mcp_server)
        
        def simulate_request(request_id):
            """模拟请求处理"""
            handler = Mock()
            handler.headers = {"User-Agent": f"Test-Client/{request_id}"}
            handler.path = "/health"
            
            start_time = time.perf_counter()
            router.route_request(handler, 'http')
            end_time = time.perf_counter()
            
            return end_time - start_time
        
        # 测试不同并发级别
        concurrency_levels = [1, 5, 10, 20, 50]
        
        for level in concurrency_levels:
            print(f"  测试并发级别: {level}")
            
            times = []
            start_time = time.perf_counter()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
                futures = [executor.submit(simulate_request, i) for i in range(100)]
                for future in concurrent.futures.as_completed(futures):
                    times.append(future.result())
            
            end_time = time.perf_counter()
            total_time = end_time - start_time
            
            avg_time = statistics.mean(times)
            throughput = 100 / total_time  # 请求/秒
            
            print(f"    总时间: {total_time:.3f}s")
            print(f"    平均响应时间: {avg_time*1000:.3f}ms")
            print(f"    吞吐量: {throughput:.1f} 请求/秒")
        
        self.results['concurrent_performance'] = {
            'concurrency_levels': concurrency_levels,
            'throughput': throughput
        }
    
    def test_memory_usage(self):
        """测试内存使用"""
        print("\n内存使用测试")
        print("-" * 40)
        
        import psutil
        import gc
        
        # 获取初始内存使用
        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 创建多个路由器实例
        routers = []
        for i in range(100):
            server = self._create_mock_server()
            router = SmartRouter(server)
            routers.append(router)
            
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                print(f"    创建 {i} 个路由器后内存增加: {memory_increase:.1f}MB")
        
        # 清理
        del routers
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_recovered = final_memory - initial_memory
        
        print(f"    清理后内存增加: {memory_recovered:.1f}MB")
        
        self.results['memory_usage'] = {
            'initial_memory': initial_memory,
            'final_memory': final_memory,
            'memory_increase': memory_recovered
        }
    
    def generate_performance_report(self):
        """生成性能报告"""
        print("\n性能测试报告")
        print("=" * 60)
        
        # 客户端检测性能
        if 'client_detection' in self.results:
            cd = self.results['client_detection']
            print("\n客户端检测性能:")
            print(f"  平均检测时间: {cd['avg_time']*1000:.3f}ms")
            print(f"  最小检测时间: {cd['min_time']*1000:.3f}ms")
            print(f"  最大检测时间: {cd['max_time']*1000:.3f}ms")
            print(f"  标准差: {cd['std_dev']*1000:.3f}ms")
            print(f"  缓存加速: {cd['cache_speedup']:.1f}%")
        
        # 智能路由性能
        if 'smart_routing' in self.results:
            sr = self.results['smart_routing']
            print("\n智能路由性能:")
            print(f"  平均路由时间: {sr['avg_time']*1000:.3f}ms")
            print(f"  最小路由时间: {sr['min_time']*1000:.3f}ms")
            print(f"  最大路由时间: {sr['max_time']*1000:.3f}ms")
            print(f"  标准差: {sr['std_dev']*1000:.3f}ms")
        
        # 适配器性能
        if 'adapter_performance' in self.results:
            ap = self.results['adapter_performance']
            print("\n适配器性能:")
            print(f"  Dify适配器平均时间: {ap['dify_avg']*1000:.3f}ms")
            print(f"  标准适配器平均时间: {ap['standard_avg']*1000:.3f}ms")
            
            # 性能比较
            if ap['dify_avg'] < ap['standard_avg']:
                speedup = (ap['standard_avg'] - ap['dify_avg']) / ap['standard_avg'] * 100
                print(f"  Dify适配器比标准适配器快 {speedup:.1f}%")
            else:
                slowdown = (ap['dify_avg'] - ap['standard_avg']) / ap['standard_avg'] * 100
                print(f"  Dify适配器比标准适配器慢 {slowdown:.1f}%")
        
        # 并发性能
        if 'concurrent_performance' in self.results:
            cp = self.results['concurrent_performance']
            print("\n并发性能:")
            print(f"  最大吞吐量: {cp['throughput']:.1f} 请求/秒")
        
        # 内存使用
        if 'memory_usage' in self.results:
            mu = self.results['memory_usage']
            print("\n内存使用:")
            print(f"  初始内存: {mu['initial_memory']:.1f}MB")
            print(f"  最终内存: {mu['final_memory']:.1f}MB")
            print(f"  内存增加: {mu['memory_increase']:.1f}MB")
        
        # 性能建议
        print("\n性能建议:")
        
        if 'client_detection' in self.results:
            cd = self.results['client_detection']
            if cd['avg_time'] > 0.001:  # 1ms
                print("  - 客户端检测时间较长，考虑优化检测算法")
            
            if cd['cache_speedup'] < 50:
                print("  - 缓存效果不明显，考虑调整缓存策略")
        
        if 'smart_routing' in self.results:
            sr = self.results['smart_routing']
            if sr['avg_time'] > 0.005:  # 5ms
                print("  - 智能路由时间较长，考虑优化路由逻辑")
        
        if 'adapter_performance' in self.results:
            ap = self.results['adapter_performance']
            if ap['dify_avg'] > 0.01:  # 10ms
                print("  - Dify适配器处理时间较长，考虑优化适配器逻辑")
            
            if ap['standard_avg'] > 0.01:  # 10ms
                print("  - 标准适配器处理时间较长，考虑优化适配器逻辑")
        
        if 'memory_usage' in self.results:
            mu = self.results['memory_usage']
            if mu['memory_increase'] > 50:  # 50MB
                print("  - 内存使用较高，考虑优化内存管理")
        
        print("\n性能测试完成！")


def main():
    """主函数"""
    print("UnityLangPX MCP服务器性能测试工具")
    print("用于测试智能路由系统的性能表现")
    print()
    
    # 创建测试套件
    test_suite = PerformanceTestSuite()
    
    try:
        # 运行所有测试
        test_suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n感谢使用UnityLangPX性能测试工具！")


if __name__ == "__main__":
    main()