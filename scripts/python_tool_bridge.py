#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python工具桥接脚本
用于FastMCP服务器调用Python MCP工具
"""

import sys
import json
import os
import traceback
from pathlib import Path

# 设置环境变量确保UTF-8编码输出
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 确保stdout使用UTF-8编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp.tools.registry import create_tool_registry
from src.mcp.protocol.adapter import create_protocol_adapter
from src.core.config import Config
from src.core.logger import get_logger

logger = get_logger(__name__)


def list_tools(args=None):
    """获取可用工具列表"""
    try:
        # 创建工具注册表和协议适配器
        config = Config()
        tool_registry = create_tool_registry()
        protocol_adapter = create_protocol_adapter(config, tool_registry)
        
        # 注册所有工具
        run_async(register_all_tools(tool_registry, protocol_adapter))
        
        # 获取所有工具
        tools = []
        tool_names = run_async(tool_registry.get_tool_names())
        
        for tool_name in tool_names:
            tool = run_async(tool_registry.get_tool(tool_name))
            if tool:
                # 获取输入schema并转换为MCP格式
                input_schema = getattr(tool, 'get_input_schema', lambda: {})()
                
                # 确保所有必需的属性都存在
                # 创建符合StandardSchemaV1格式的parameters对象
                # 注意：不包含validate函数，因为它不能被JSON序列化
                parameters = {
                    "~standard": {
                        "version": 1,
                        "vendor": "zod",
                        "shape": {}
                    }
                }
                
                if input_schema and isinstance(input_schema, dict):
                    # 转换JSON Schema为StandardSchemaV1格式
                    properties = input_schema.get("properties", {})
                    required = input_schema.get("required", [])
                    
                    if properties:
                        # 创建zod兼容的schema结构
                        zod_shape = {}
                        for prop_name, prop_def in properties.items():
                            prop_type = prop_def.get("type", "string")
                            
                            # 构建constraints对象，只包含非None值
                            constraints = {}
                            if prop_type == "string":
                                if prop_def.get("minLength") is not None:
                                    constraints["minLength"] = prop_def.get("minLength")
                                if prop_def.get("maxLength") is not None:
                                    constraints["maxLength"] = prop_def.get("maxLength")
                                if prop_def.get("pattern") is not None:
                                    constraints["pattern"] = prop_def.get("pattern")
                                if prop_def.get("enum") is not None:
                                    constraints["enum"] = prop_def.get("enum")
                                    
                                zod_shape[prop_name] = {
                                    "typeName": "string",
                                    "isOptional": prop_name not in required,
                                    "defaultValue": prop_def.get("default"),
                                    "constraints": constraints if constraints else None
                                }
                            elif prop_type == "number":
                                if prop_def.get("minimum") is not None:
                                    constraints["min"] = prop_def.get("minimum")
                                if prop_def.get("maximum") is not None:
                                    constraints["max"] = prop_def.get("maximum")
                                    
                                zod_shape[prop_name] = {
                                    "typeName": "number",
                                    "isOptional": prop_name not in required,
                                    "defaultValue": prop_def.get("default"),
                                    "constraints": constraints if constraints else None
                                }
                            elif prop_type == "boolean":
                                zod_shape[prop_name] = {
                                    "typeName": "boolean",
                                    "isOptional": prop_name not in required,
                                    "defaultValue": prop_def.get("default")
                                }
                            elif prop_type == "array":
                                zod_shape[prop_name] = {
                                    "typeName": "array",
                                    "isOptional": prop_name not in required,
                                    "element": {"typeName": "string"},
                                    "defaultValue": prop_def.get("default")
                                }
                            else:
                                # 默认为string类型，不添加任何约束
                                zod_shape[prop_name] = {
                                    "typeName": "string",
                                    "isOptional": prop_name not in required,
                                    "defaultValue": prop_def.get("default")
                                }
                        
                        parameters["~standard"]["shape"] = zod_shape
                
                tool_info = {
                    "name": getattr(tool, 'name', tool_name),
                    "description": getattr(tool, 'description', ''),
                    "parameters": parameters  # 使用StandardSchemaV1格式，移除vendor属性
                }
                tools.append(tool_info)
        
        return {
            "success": True,
            "data": tools
        }
    except Exception as e:
        logger.error(f"获取工具列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


async def execute_tool(tool_name, args):
    """执行指定的工具"""
    try:
        # 创建工具注册表和协议适配器
        config = Config()
        tool_registry = create_tool_registry()
        protocol_adapter = create_protocol_adapter(config, tool_registry)
        
        # 注册所有工具
        await register_all_tools(tool_registry, protocol_adapter)
        
        # 获取工具
        tool = await tool_registry.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"工具不存在: {tool_name}"
            }
        
        # 执行工具
        logger.info(f"执行工具: {tool_name}, 参数: {args}")
        result = await tool.safe_execute(args)
        
        if result.success:
            logger.info(f"工具 {tool_name} 执行成功")
            return {
                "success": True,
                "data": result.data
            }
        else:
            logger.error(f"工具 {tool_name} 执行失败: {result.error}")
            return {
                "success": False,
                "error": result.error
            }
            
    except Exception as e:
        logger.error(f"执行工具失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


async def register_all_tools(tool_registry, protocol_adapter):
    """注册所有工具"""
    from src.mcp.tools import (
        TextTranslationTool,
        FileTranslationTool,
        BatchTranslationTool,
        StatusQueryTool
    )
    
    # 注册文本翻译工具
    text_tool = TextTranslationTool(protocol_adapter)
    await tool_registry.register_tool(text_tool)
    
    # 注册文件翻译工具
    file_tool = FileTranslationTool(protocol_adapter)
    await tool_registry.register_tool(file_tool)
    
    # 注册批量翻译工具
    batch_tool = BatchTranslationTool(protocol_adapter)
    await tool_registry.register_tool(batch_tool)
    
    # 注册状态查询工具
    status_tool = StatusQueryTool(protocol_adapter)
    await tool_registry.register_tool(status_tool)
    
    logger.info(f"已注册 {await tool_registry.get_tool_count()} 个工具")


def run_async(coro):
    """辅助函数，用于等待协程"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    except AttributeError:
        # 如果没有事件循环，创建一个新的
        return asyncio.run(coro)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "用法: python python_tool_bridge.py <command> [args_json]"
        }))
        sys.exit(1)
    
    command = sys.argv[1]
    args_json = sys.argv[2] if len(sys.argv) > 2 else "{}"
    
    try:
        args = json.loads(args_json)
    except json.JSONDecodeError:
        print(json.dumps({
            "success": False,
            "error": f"无效的JSON参数: {args_json}"
        }))
        sys.exit(1)
    
    if command == "list-tools":
        result = list_tools()
    else:
        result = run_async(execute_tool(command, args))
    
    # 确保JSON输出使用UTF-8编码
    output = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
    try:
        print(output)
    except UnicodeEncodeError:
        # 如果直接打印失败，使用错误替换
        print(output.encode('utf-8', errors='replace').decode('utf-8'))
    sys.exit(0)


if __name__ == "__main__":
    main()