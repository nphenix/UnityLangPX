"""
UnityLangPX MCP状态查询工具模块

实现MCP协议的状态查询工具。
"""

from typing import Dict, Any

from .base import BaseTool, ToolParameter, ToolResult, create_tool_parameter
from ...core.logger import get_logger

logger = get_logger(__name__)


class StatusQueryTool(BaseTool):
    """状态查询工具"""
    
    def __init__(self, protocol_adapter):
        """
        初始化状态查询工具
        
        Args:
            protocol_adapter: 协议适配器
        """
        super().__init__(
            name="get_translation_status",
            description="查询翻译服务器状态和统计信息"
        )
        self.protocol_adapter = protocol_adapter
    
    def _setup_parameters(self):
        """设置工具参数"""
        # 查询类型参数
        self.add_parameter(create_tool_parameter(
            name="query_type",
            param_type="string",
            description="查询类型",
            required=False,
            default="health",
            enum=["health", "statistics", "full"]
        ))
        
        # 详细程度参数
        self.add_parameter(create_tool_parameter(
            name="verbose",
            param_type="boolean",
            description="是否返回详细信息",
            required=False,
            default=False
        ))
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        执行状态查询
        
        Args:
            params: 工具参数
            
        Returns:
            查询结果
        """
        try:
            # 提取参数
            query_type = params.get("query_type", "health")
            verbose = params.get("verbose", False)
            
            logger.debug(f"查询状态: {query_type}, 详细: {verbose}")
            
            # 根据查询类型获取不同信息
            if query_type == "health":
                result = await self._get_health_status(verbose)
            elif query_type == "statistics":
                result = await self._get_statistics(verbose)
            elif query_type == "full":
                result = await self._get_full_status(verbose)
            else:
                return ToolResult(
                    success=False,
                    error=f"不支持的查询类型: {query_type}"
                )
            
            return ToolResult(
                success=True,
                data=result
            )
            
        except Exception as e:
            logger.error(f"状态查询异常: {str(e)}")
            return ToolResult(
                success=False,
                error=f"状态查询失败: {str(e)}"
            )
    
    async def _get_health_status(self, verbose: bool = False) -> Dict[str, Any]:
        """
        获取健康状态
        
        Args:
            verbose: 是否返回详细信息
            
        Returns:
            健康状态信息
        """
        try:
            # 获取基础健康状态
            health_status = await self.protocol_adapter.get_health_status()
            
            if not verbose:
                # 简化状态信息
                return {
                    "status": health_status["status"],
                    "timestamp": health_status["timestamp"]
                }
            
            # 返回详细状态信息
            return health_status
            
        except Exception as e:
            logger.error(f"获取健康状态失败: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    async def _get_statistics(self, verbose: bool = False) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            verbose: 是否返回详细信息
            
        Returns:
            统计信息
        """
        try:
            # 这里可以添加更多统计信息的收集
            # 目前返回基础统计信息
            stats = {
                "server_info": {
                    "name": "UnityLangPX MCP Server",
                    "version": "1.0.0",
                    "uptime": self._get_uptime()
                },
                "translation_stats": {
                    "total_requests": 0,  # 这里可以从消息处理器获取
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "success_rate": 0.0
                },
                "resource_stats": {
                    "memory_usage": self._get_memory_usage(),
                    "cpu_usage": self._get_cpu_usage()
                },
                "timestamp": self._get_timestamp()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    async def _get_full_status(self, verbose: bool = False) -> Dict[str, Any]:
        """
        获取完整状态信息
        
        Args:
            verbose: 是否返回详细信息
            
        Returns:
            完整状态信息
        """
        try:
            # 获取健康状态
            health_status = await self._get_health_status(True)
            
            # 获取统计信息
            stats = await self._get_statistics(True)
            
            # 合并状态信息
            full_status = {
                "health": health_status,
                "statistics": stats,
                "timestamp": self._get_timestamp()
            }
            
            return full_status
            
        except Exception as e:
            logger.error(f"获取完整状态失败: {str(e)}")
            return {
                "error": str(e),
                "timestamp": self._get_timestamp()
            }
    
    def _get_timestamp(self) -> str:
        """
        获取当前时间戳
        
        Returns:
            ISO格式时间戳
        """
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def _get_uptime(self) -> str:
        """
        获取服务器运行时间
        
        Returns:
            运行时间字符串
        """
        try:
            # 这里可以记录服务器启动时间并计算运行时间
            # 目前返回模拟值
            return "0h 0m 0s"
        except Exception:
            return "unknown"
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """
        获取内存使用情况
        
        Returns:
            内存使用信息
        """
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss": memory_info.rss,  # 物理内存
                "vms": memory_info.vms,  # 虚拟内存
                "percent": process.memory_percent(),  # 内存使用百分比
                "available": psutil.virtual_memory().available  # 可用内存
            }
        except Exception:
            return {"error": "无法获取内存信息"}
    
    def _get_cpu_usage(self) -> Dict[str, Any]:
        """
        获取CPU使用情况
        
        Returns:
            CPU使用信息
        """
        try:
            import psutil
            return {
                "percent": psutil.cpu_percent(interval=1),  # CPU使用百分比
                "count": psutil.cpu_count(),  # CPU核心数
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None  # CPU频率
            }
        except Exception:
            return {"error": "无法获取CPU信息"}