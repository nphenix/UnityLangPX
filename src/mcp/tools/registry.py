"""
UnityLangPX MCP工具注册表模块

管理工具的注册、查找和调用。
"""

import asyncio
from typing import Dict, List, Optional, Any

from .base import BaseTool, ToolResult
from ...core.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, BaseTool] = {}
        self._tool_lock = asyncio.Lock()
        
        logger.info("工具注册表初始化完成")
    
    async def register_tool(self, tool: BaseTool) -> bool:
        """
        注册工具
        
        Args:
            tool: 工具实例
            
        Returns:
            是否注册成功
        """
        async with self._tool_lock:
            if tool.name in self._tools:
                logger.warning(f"工具已存在，将被覆盖: {tool.name}")
            
            self._tools[tool.name] = tool
            logger.info(f"注册工具: {tool.name}")
            return True
    
    async def unregister_tool(self, name: str) -> bool:
        """
        注销工具
        
        Args:
            name: 工具名称
            
        Returns:
            是否注销成功
        """
        async with self._tool_lock:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"注销工具: {name}")
                return True
            else:
                logger.warning(f"工具不存在: {name}")
                return False
    
    async def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例或None
        """
        async with self._tool_lock:
            return self._tools.get(name)
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有工具
        
        Returns:
            工具定义列表
        """
        async with self._tool_lock:
            return [tool.get_tool_definition() for tool in self._tools.values()]
    
    async def call_tool(self, name: str, params: Dict[str, Any]) -> ToolResult:
        """
        调用工具
        
        Args:
            name: 工具名称
            params: 工具参数
            
        Returns:
            工具执行结果
        """
        tool = await self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"未找到工具: {name}"
            )
        
        try:
            return await tool.safe_execute(params)
        except Exception as e:
            logger.error(f"调用工具失败: {name}, 错误: {str(e)}")
            return ToolResult(
                success=False,
                error=f"工具调用失败: {str(e)}"
            )
    
    async def get_tool_names(self) -> List[str]:
        """
        获取所有工具名称
        
        Returns:
            工具名称列表
        """
        async with self._tool_lock:
            return list(self._tools.keys())
    
    async def has_tool(self, name: str) -> bool:
        """
        检查工具是否存在
        
        Args:
            name: 工具名称
            
        Returns:
            是否存在
        """
        async with self._tool_lock:
            return name in self._tools
    
    async def get_tool_count(self) -> int:
        """
        获取工具数量
        
        Returns:
            工具数量
        """
        async with self._tool_lock:
            return len(self._tools)
    
    async def clear_tools(self) -> int:
        """
        清空所有工具
        
        Returns:
            清空的工具数量
        """
        async with self._tool_lock:
            count = len(self._tools)
            self._tools.clear()
            logger.info(f"清空所有工具，共 {count} 个")
            return count
    
    async def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """
        按类别获取工具
        
        Args:
            category: 工具类别
            
        Returns:
            工具列表
        """
        async with self._tool_lock:
            # 通过工具名称中的类别前缀来分类
            return [
                tool for tool in self._tools.values()
                if tool.name.startswith(category + "_")
            ]
    
    async def validate_tools(self) -> Dict[str, Any]:
        """
        验证所有工具
        
        Returns:
            验证结果
        """
        results = {
            "valid": [],
            "invalid": [],
            "total": 0
        }
        
        async with self._tool_lock:
            results["total"] = len(self._tools)
            
            for name, tool in self._tools.items():
                try:
                    # 验证工具定义
                    definition = tool.get_tool_definition()
                    
                    # 检查必需字段
                    if not all(key in definition for key in ["name", "description", "inputSchema"]):
                        results["invalid"].append({
                            "name": name,
                            "error": "缺少必需字段"
                        })
                        continue
                    
                    # 检查输入模式
                    input_schema = definition["inputSchema"]
                    if not isinstance(input_schema, dict) or "type" not in input_schema:
                        results["invalid"].append({
                            "name": name,
                            "error": "无效的输入模式"
                        })
                        continue
                    
                    results["valid"].append(name)
                    
                except Exception as e:
                    results["invalid"].append({
                        "name": name,
                        "error": str(e)
                    })
        
        logger.info(f"工具验证完成，有效: {len(results['valid'])}, 无效: {len(results['invalid'])}")
        return results
    
    def __len__(self) -> int:
        """返回工具数量"""
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools
    
    def __iter__(self):
        """迭代工具"""
        return iter(self._tools.values())


# 全局工具注册表实例
_global_registry: Optional[ToolRegistry] = None


async def get_global_tool_registry() -> ToolRegistry:
    """
    获取全局工具注册表
    
    Returns:
        全局工具注册表实例
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


async def register_global_tool(tool: BaseTool) -> bool:
    """
    注册全局工具
    
    Args:
        tool: 工具实例
        
    Returns:
        是否注册成功
    """
    registry = await get_global_tool_registry()
    return await registry.register_tool(tool)


async def unregister_global_tool(name: str) -> bool:
    """
    注销全局工具
    
    Args:
        name: 工具名称
        
    Returns:
        是否注销成功
    """
    registry = await get_global_tool_registry()
    return await registry.unregister_tool(name)


async def call_global_tool(name: str, params: Dict[str, Any]) -> ToolResult:
    """
    调用全局工具
    
    Args:
        name: 工具名称
        params: 工具参数
        
    Returns:
        工具执行结果
    """
    registry = await get_global_tool_registry()
    return await registry.call_tool(name, params)


# 便捷函数
def create_tool_registry() -> ToolRegistry:
    """
    创建工具注册表
    
    Returns:
        工具注册表实例
    """
    return ToolRegistry()