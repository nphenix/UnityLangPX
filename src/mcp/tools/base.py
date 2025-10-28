"""
UnityLangPX MCP工具基类模块

定义MCP工具的基础接口和通用功能。
"""

import asyncio
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ...core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseTool(ABC):
    """MCP工具基类"""
    
    def __init__(self, name: str, description: str):
        """
        初始化工具
        
        Args:
            name: 工具名称
            description: 工具描述
        """
        self.name = name
        self.description = description
        self._parameters: Dict[str, ToolParameter] = {}
        self._setup_parameters()
        
        logger.debug(f"初始化工具: {self.name}")
    
    @abstractmethod
    def _setup_parameters(self):
        """设置工具参数"""
        pass
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        执行工具逻辑
        
        Args:
            params: 工具参数
            
        Returns:
            工具执行结果
        """
        pass
    
    def add_parameter(self, param: ToolParameter):
        """
        添加工具参数
        
        Args:
            param: 参数定义
        """
        self._parameters[param.name] = param
        logger.debug(f"添加参数: {self.name}.{param.name}")
    
    def get_parameter(self, name: str) -> Optional[ToolParameter]:
        """
        获取参数定义
        
        Args:
            name: 参数名
            
        Returns:
            参数定义
        """
        return self._parameters.get(name)
    
    def get_parameters(self) -> Dict[str, ToolParameter]:
        """
        获取所有参数定义
        
        Returns:
            参数定义字典
        """
        return self._parameters.copy()
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数
        
        Args:
            params: 参数字典
            
        Returns:
            是否有效
        """
        try:
            # 检查必需参数
            for param_name, param_def in self._parameters.items():
                if param_def.required and param_name not in params:
                    logger.warning(f"缺少必需参数: {param_name}")
                    return False
                
                # 如果参数存在但值为None，且是必需的，则验证失败
                if param_def.required and params.get(param_name) is None:
                    logger.warning(f"必需参数不能为None: {param_name}")
                    return False
            
            # 验证每个参数的值
            for param_name, value in params.items():
                if param_name in self._parameters:
                    if not self._validate_parameter_value(
                        param_name, value, self._parameters[param_name]
                    ):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"参数验证异常: {str(e)}")
            return False
    
    def _validate_parameter_value(self, name: str, value: Any, 
                                 param_def: ToolParameter) -> bool:
        """
        验证单个参数值
        
        Args:
            name: 参数名
            value: 参数值
            param_def: 参数定义
            
        Returns:
            是否有效
        """
        try:
            # 类型检查
            if param_def.type == "string" and not isinstance(value, str):
                logger.warning(f"参数类型错误: {name} 应为字符串")
                return False
            elif param_def.type == "number" and not isinstance(value, (int, float)):
                logger.warning(f"参数类型错误: {name} 应为数字")
                return False
            elif param_def.type == "boolean" and not isinstance(value, bool):
                logger.warning(f"参数类型错误: {name} 应为布尔值")
                return False
            elif param_def.type == "array" and not isinstance(value, list):
                logger.warning(f"参数类型错误: {name} 应为数组")
                return False
            elif param_def.type == "object" and not isinstance(value, dict):
                logger.warning(f"参数类型错误: {name} 应为对象")
                return False
            
            # 字符串长度检查
            if param_def.type == "string":
                if param_def.min_length is not None and len(value) < param_def.min_length:
                    logger.warning(f"参数长度过短: {name} 最小长度 {param_def.min_length}")
                    return False
                if param_def.max_length is not None and len(value) > param_def.max_length:
                    logger.warning(f"参数长度过长: {name} 最大长度 {param_def.max_length}")
                    return False
                
                # 正则表达式检查
                if param_def.pattern and not re.match(param_def.pattern, value):
                    logger.warning(f"参数格式错误: {name} 不匹配模式 {param_def.pattern}")
                    return False
            
            # 数值范围检查
            if param_def.type in ["number", "integer"]:
                if param_def.minimum is not None and value < param_def.minimum:
                    logger.warning(f"参数值过小: {name} 最小值 {param_def.minimum}")
                    return False
                if param_def.maximum is not None and value > param_def.maximum:
                    logger.warning(f"参数值过大: {name} 最大值 {param_def.maximum}")
                    return False
            
            # 枚举值检查
            if param_def.enum and value not in param_def.enum:
                logger.warning(f"参数值无效: {name} 应为 {param_def.enum} 之一")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证参数值异常: {name}, 错误: {str(e)}")
            return False
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        获取输入模式定义
        
        Returns:
            JSON Schema格式的输入定义
        """
        properties = {}
        required = []
        
        for param_name, param_def in self._parameters.items():
            # 确保参数定义不为空
            if not param_def or param_def.type is None:
                logger.warning(f"跳过无效参数: {param_name}")
                continue
                
            prop_def = {
                "type": param_def.type or "string",
                "description": param_def.description or ""
            }
            
            # 添加默认值
            if param_def.default is not None:
                prop_def["default"] = param_def.default
            
            # 添加枚举值
            if param_def.enum and len(param_def.enum) > 0:
                prop_def["enum"] = param_def.enum
            
            # 添加字符串约束
            if param_def.type == "string":
                if param_def.min_length is not None:
                    prop_def["minLength"] = param_def.min_length
                if param_def.max_length is not None:
                    prop_def["maxLength"] = param_def.max_length
                if param_def.pattern:
                    prop_def["pattern"] = param_def.pattern
            
            # 添加数值约束
            if param_def.type in ["number", "integer"]:
                if param_def.minimum is not None:
                    prop_def["minimum"] = param_def.minimum
                if param_def.maximum is not None:
                    prop_def["maximum"] = param_def.maximum
            
            properties[param_name] = prop_def
            
            # 记录必需参数
            if param_def.required:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """
        获取工具定义
        
        Returns:
            工具定义字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.get_input_schema()
        }
    
    async def safe_execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        安全执行工具，包含异常处理
        
        Args:
            params: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            # 验证参数
            if not self.validate_params(params):
                return ToolResult(
                    success=False,
                    error="参数验证失败"
                )
            
            # 执行工具
            logger.debug(f"执行工具: {self.name}")
            start_time = asyncio.get_event_loop().time()
            
            result = await self.execute(params)
            
            # 记录执行时间
            execution_time = asyncio.get_event_loop().time() - start_time
            result.metadata["execution_time"] = execution_time
            
            logger.debug(f"工具执行完成: {self.name}, 耗时: {execution_time:.3f}秒")
            return result
            
        except Exception as e:
            logger.error(f"工具执行异常: {self.name}, 错误: {str(e)}")
            return ToolResult(
                success=False,
                error=f"工具执行失败: {str(e)}"
            )
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"{self.__class__.__name__}(name={self.name}, description={self.description})"


# 便捷函数
def create_tool_parameter(name: str, param_type: str, description: str,
                         required: bool = True, default: Any = None,
                         **kwargs) -> ToolParameter:
    """
    创建工具参数
    
    Args:
        name: 参数名
        param_type: 参数类型
        description: 参数描述
        required: 是否必需
        default: 默认值
        **kwargs: 其他参数属性
        
    Returns:
        工具参数定义
    """
    return ToolParameter(
        name=name,
        type=param_type,
        description=description,
        required=required,
        default=default,
        **kwargs
    )