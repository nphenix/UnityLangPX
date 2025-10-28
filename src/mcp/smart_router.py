"""
智能路由系统
根据客户端类型自动选择合适的适配器
"""

import json
import logging
from typing import Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger(__name__)


class SmartRouter:
    """智能路由器，根据客户端类型自动选择适配器"""
    
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.adapters = {}
        self.client_detector = ClientDetector()
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化适配器"""
        try:
            from .dify_adapter import DifySSEAdapter
            from .standard_adapter import StandardMCPAdapter
            
            self.adapters = {
                'dify': DifySSEAdapter(self.mcp_server),
                'standard': StandardMCPAdapter(self.mcp_server)
            }
            
            logger.info(f"智能路由器初始化完成，支持适配器: {list(self.adapters.keys())}")
        except ImportError as e:
            logger.warning(f"适配器导入失败，将使用基础功能: {e}")
            # 如果适配器不可用，创建基础适配器
            self.adapters = {
                'standard': StandardMCPAdapter(self.mcp_server)
            }
    
    async def route_request(self, handler, request_type='http', **kwargs):
        """路由请求到合适的适配器"""
        try:
            logger.info("=" * 50)
            logger.info(f"[SMART_ROUTER] 开始路由请求")
            logger.info(f"[SMART_ROUTER] 请求类型: {request_type}")
            
            # 特殊处理健康检查请求
            path = getattr(handler, 'path', '')
            logger.info(f"[SMART_ROUTER] 请求路径: {path}")
            
            if path == '/' or path == '/health':
                logger.info(f"[SMART_ROUTER] 处理健康检查请求: {path}")
                # 使用标准适配器处理健康检查
                if 'standard' in self.adapters:
                    return self.adapters['standard'].handle_request(handler)
                else:
                    return self._send_error_response(handler, 404, "Not Found")
            
            # 检测客户端类型
            client_type = self.client_detector.detect_client_type(handler)
            logger.info(f"[SMART_ROUTER] 检测到客户端类型: {client_type}")
            
            # 获取对应的适配器
            adapter = self.adapters.get(client_type, self.adapters.get('standard'))
            logger.info(f"[SMART_ROUTER] 选择的适配器: {type(adapter).__name__ if adapter else 'None'}")
            
            if not adapter:
                logger.error("[SMART_ROUTER] 没有可用的适配器")
                return self._send_error_response(handler, 500, "没有可用的适配器")
            
            # 路由请求
            logger.info(f"[SMART_ROUTER] 路由到适配器处理...")
            try:
                if request_type == 'sse':
                    logger.info("[SMART_ROUTER] 路由到SSE处理器")
                    result = adapter.handle_sse_connection(handler)
                elif request_type == 'message':
                    logger.info("[SMART_ROUTER] 路由到message处理器")
                    # 传递已读取的数据
                    post_data = kwargs.get('post_data', '')
                    result = await adapter.handle_message_request(handler, post_data=post_data)
                else:
                    logger.info("[SMART_ROUTER] 路由到HTTP处理器")
                    # 传递已读取的数据
                    post_data = kwargs.get('post_data', '')
                    result = await adapter.handle_request(handler, post_data=post_data)
                
                logger.info(f"[SMART_ROUTER] 适配器处理完成")
                logger.info("=" * 50)
                return result
            except Exception as adapter_error:
                logger.error(f"[SMART_ROUTER] 适配器处理失败: {str(adapter_error)}")
                import traceback
                logger.error(f"[SMART_ROUTER] 适配器错误详情: {traceback.format_exc()}")
                
                # 如果是Dify适配器失败，尝试回退到标准适配器
                if client_type == 'dify' and 'standard' in self.adapters:
                    logger.info("[SMART_ROUTER] Dify适配器失败，回退到标准适配器")
                    return await self.adapters['standard'].handle_request(handler)
                else:
                    return self._send_error_response(handler, 500, f"适配器处理失败: {str(adapter_error)}")
                
        except Exception as e:
            logger.error(f"[SMART_ROUTER] 路由请求失败: {str(e)}")
            import traceback
            logger.error(f"[SMART_ROUTER] 错误详情: {traceback.format_exc()}")
            # 回退到标准适配器
            if 'standard' in self.adapters:
                logger.info("[SMART_ROUTER] 回退到标准适配器")
                return await self.adapters['standard'].handle_request(handler)
            else:
                return self._send_error_response(handler, 500, f"路由失败: {str(e)}")
    
    def _send_error_response(self, handler, code, message):
        """发送错误响应"""
        try:
            handler.send_response(code)
            handler.send_header('Content-Type', 'application/json')
            handler.send_header('Access-Control-Allow-Origin', '*')
            handler.end_headers()
            error_response = {"error": message}
            handler.wfile.write(json.dumps(error_response).encode('utf-8'))
        except Exception as e:
            logger.error(f"发送错误响应失败: {str(e)}")
    
    def get_adapter_stats(self):
        """获取适配器统计信息"""
        stats = {}
        for name, adapter in self.adapters.items():
            if hasattr(adapter, 'get_stats'):
                stats[name] = adapter.get_stats()
        return stats


class ClientDetector:
    """客户端类型检测器"""
    
    def __init__(self):
        self.detection_cache = {}
        self.cache_ttl = 300  # 缓存5分钟
    
    def detect_client_type(self, handler) -> str:
        """检测客户端类型"""
        try:
            # 尝试从缓存获取
            cache_key = self._get_cache_key(handler)
            if cache_key in self.detection_cache:
                cached_result, timestamp = self.detection_cache[cache_key]
                import time
                if time.time() - timestamp < self.cache_ttl:
                    logger.debug(f"从缓存获取客户端类型: {cached_result}")
                    return cached_result
            
            # 检查User-Agent
            user_agent = handler.headers.get('User-Agent', '').lower()
            
            # 检查请求路径
            path = getattr(handler, 'path', '')
            
            # 检查特定请求头
            headers = dict(handler.headers)
            
            # Dify客户端特征 - 增强检测逻辑
            dify_indicators = []
            
            # 检查User-Agent中是否包含dify
            if 'dify' in user_agent:
                dify_indicators.append(True)
                logger.debug("检测到Dify User-Agent")
            
            # 检查SSE路径
            if path.startswith('/sse') or path.startswith('/events'):
                dify_indicators.append(True)
                logger.debug("检测到SSE路径")
            
            # 检查特定请求头
            if 'x-dify' in headers:
                dify_indicators.append(True)
                logger.debug("检测到X-Dify头")
            
            # 检查是否有Bearer token（强Dify特征）
            auth_header = headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                dify_indicators.append(True)
                logger.debug("检测到Bearer token，增加Dify特征得分")
            
            # 检查是否有测试token（用于测试）
            if 'test-token' in auth_header:
                dify_indicators.append(True)
                logger.debug("检测到测试token，增加Dify特征得分")
            
            # 检查Content-Type
            if 'content-type' in headers and 'application/json' in headers['content-type']:
                dify_indicators.append(True)
                logger.debug("检测到JSON Content-Type")
            
            # 额外的Dify特征检测
            origin = headers.get('Origin', '').lower()
            referer = headers.get('Referer', '').lower()
            
            # 检查Origin或Referer中是否包含dify相关内容
            if 'dify' in origin or 'dify' in referer:
                dify_indicators.append(True)
                logger.debug("检测到Dify Origin或Referer")
            
            # 检查特定的Dify请求模式
            if path.startswith('/messages') and 'session_id' in getattr(handler, 'query', ''):
                dify_indicators.append(True)
                logger.debug("检测到Dify messages请求模式")
            
            # 如果有任何一个Dify特征，就认为是Dify客户端 - 降低阈值以提高检测准确性
            dify_score = sum(dify_indicators)
            
            # 特殊处理：如果是POST请求到/messages端点，且有Bearer token，强制认为是Dify客户端
            # 检查请求方法：通过检查是否有Content-Length和Content-Type来判断是否为POST请求
            content_length = headers.get('Content-Length', '0')
            content_type = headers.get('Content-Type', '')
            is_post_request = content_length != '0' and 'application/json' in content_type
            
            logger.debug(f"客户端检测详情: path={path}, auth_header={auth_header[:20]}..., content_length={content_length}, content_type={content_type}, is_post_request={is_post_request}")
            logger.debug(f"Dify特征得分: {dify_score}, 特征: {dify_indicators}")
            
            # 修复：只要路径是/messages且有Bearer token，就强制识别为Dify客户端
            if path.startswith('/messages') and auth_header.startswith('Bearer '):
                client_type = 'dify'
                logger.debug("检测到Dify messages请求模式，强制识别为Dify客户端")
            else:
                # 降低Dify检测阈值，提高检测准确性
                client_type = 'dify' if dify_score >= 1 else 'standard'
            
            # 缓存结果
            import time
            self.detection_cache[cache_key] = (client_type, time.time())
            
            logger.debug(f"客户端检测结果: {client_type}, 特征得分: {dify_score}, 特征: {dify_indicators}")
            return client_type
            
        except Exception as e:
            logger.warning(f"客户端类型检测失败，使用默认标准客户端: {str(e)}")
            return 'standard'
    
    def _get_cache_key(self, handler) -> str:
        """生成缓存键"""
        try:
            user_agent = handler.headers.get('User-Agent', '')
            origin = handler.headers.get('Origin', '')
            path = getattr(handler, 'path', '')
            return f"{user_agent}:{origin}:{path}"
        except:
            return "unknown"
    
    def clear_cache(self):
        """清除缓存"""
        self.detection_cache.clear()
        logger.info("客户端检测缓存已清除")