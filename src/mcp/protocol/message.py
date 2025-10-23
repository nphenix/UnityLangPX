"""
UnityLangPX MCP消息定义模块

定义MCP协议的消息格式和数据结构。
"""

import json
import time
from typing import Optional, Union, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

from ...core.exceptions import UnityLangPXError


class MCPMessageType(Enum):
    """MCP消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    NOTIFICATION = "notification"


class MCPErrorCode(Enum):
    """MCP错误代码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000
    TRANSLATION_ERROR = -32001
    FILE_ERROR = -32002
    AUTHENTICATION_ERROR = -32003
    RATE_LIMIT_ERROR = -32004


@dataclass
class MCPMessage:
    """MCP消息基类"""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 移除None值的字段
        return {k: v for k, v in data.items() if v is not None}
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPMessage':
        """从字典创建消息"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MCPMessage':
        """从JSON字符串创建消息"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise MCPError(
                MCPErrorCode.PARSE_ERROR,
                f"JSON解析错误: {str(e)}"
            )


@dataclass
class MCPRequest(MCPMessage):
    """MCP请求消息"""
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        if not self.method:
            raise ValueError("请求消息必须指定method")
    
    def validate(self) -> bool:
        """验证请求消息"""
        if not self.method:
            return False
        if self.id is None:
            return False
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPRequest':
        """从字典创建请求消息"""
        if 'method' not in data:
            raise MCPError(
                MCPErrorCode.INVALID_REQUEST,
                "请求消息缺少method字段"
            )
        return cls(**data)


@dataclass
class MCPResponse(MCPMessage):
    """MCP响应消息"""
    result: Any = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            raise ValueError("响应消息必须指定id")
    
    def validate(self) -> bool:
        """验证响应消息"""
        if self.id is None:
            return False
        if self.result is None and not hasattr(self, 'error'):
            return False
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPResponse':
        """从字典创建响应消息"""
        if 'id' not in data:
            raise MCPError(
                MCPErrorCode.INVALID_REQUEST,
                "响应消息缺少id字段"
            )
        if 'result' not in data:
            raise MCPError(
                MCPErrorCode.INVALID_REQUEST,
                "响应消息缺少result字段"
            )
        return cls(**data)


@dataclass
class MCPError(MCPMessage):
    """MCP错误消息"""
    error: Dict[str, Any] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.error is None:
            self.error = {
                "code": MCPErrorCode.INTERNAL_ERROR.value,
                "message": "内部错误"
            }
        elif isinstance(self.error, MCPErrorCode):
            self.error = {
                "code": self.error.value,
                "message": self.error.name
            }
        elif isinstance(self.error, Exception):
            self.error = {
                "code": MCPErrorCode.INTERNAL_ERROR.value,
                "message": str(self.error)
            }
    
    def validate(self) -> bool:
        """验证错误消息"""
        if self.error is None:
            return False
        if 'code' not in self.error:
            return False
        if 'message' not in self.error:
            return False
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPError':
        """从字典创建错误消息"""
        if 'error' not in data:
            raise MCPError(
                MCPErrorCode.INVALID_REQUEST,
                "错误消息缺少error字段"
            )
        return cls(**data)
    
    @classmethod
    def create_error(cls, code: Union[MCPErrorCode, int], message: str, 
                    data: Optional[Dict[str, Any]] = None, 
                    request_id: Optional[Union[str, int]] = None) -> 'MCPError':
        """创建错误消息"""
        if isinstance(code, MCPErrorCode):
            code = code.value
        
        error_data = {
            "code": code,
            "message": message
        }
        
        if data:
            error_data["data"] = data
        
        return cls(id=request_id, error=error_data)


@dataclass
class MCPNotification(MCPMessage):
    """MCP通知消息"""
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        # 通知消息没有id字段
        self.id = None
        if not self.method:
            raise ValueError("通知消息必须指定method")
    
    def validate(self) -> bool:
        """验证通知消息"""
        if not self.method:
            return False
        if self.id is not None:
            return False
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPNotification':
        """从字典创建通知消息"""
        if 'method' not in data:
            raise MCPError(
                MCPErrorCode.INVALID_REQUEST,
                "通知消息缺少method字段"
            )
        return cls(**data)


class MCPMessageFactory:
    """MCP消息工厂"""
    
    @staticmethod
    def create_message(data: Union[str, Dict[str, Any]]) -> MCPMessage:
        """
        创建MCP消息
        
        Args:
            data: 消息数据，可以是JSON字符串或字典
            
        Returns:
            MCP消息实例
            
        Raises:
            MCPError: 消息格式错误
        """
        try:
            if isinstance(data, str):
                data = json.loads(data)
            
            # 检查必要字段
            if 'jsonrpc' not in data:
                raise MCPError(
                    MCPErrorCode.INVALID_REQUEST,
                    "消息缺少jsonrpc字段"
                )
            
            # 根据消息类型创建对应的消息对象
            if 'method' in data:
                if 'id' in data:
                    # 有id字段的是请求消息
                    return MCPRequest.from_dict(data)
                else:
                    # 没有id字段的是通知消息
                    return MCPNotification.from_dict(data)
            elif 'result' in data:
                # 有result字段的是响应消息
                return MCPResponse.from_dict(data)
            elif 'error' in data:
                # 有error字段的是错误消息
                return MCPError.from_dict(data)
            else:
                raise MCPError(
                    MCPErrorCode.INVALID_REQUEST,
                    "无法识别的消息类型"
                )
                
        except json.JSONDecodeError as e:
            raise MCPError(
                MCPErrorCode.PARSE_ERROR,
                f"JSON解析错误: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, MCPError):
                raise
            raise MCPError(
                MCPErrorCode.INTERNAL_ERROR,
                f"创建消息失败: {str(e)}"
            )
    
    @staticmethod
    def create_response(result: Any, request_id: Union[str, int]) -> MCPResponse:
        """
        创建响应消息
        
        Args:
            result: 响应结果
            request_id: 请求ID
            
        Returns:
            响应消息
        """
        return MCPResponse(id=request_id, result=result)
    
    @staticmethod
    def create_error_response(error: Union[MCPErrorCode, int, Exception], 
                            request_id: Optional[Union[str, int]] = None,
                            data: Optional[Dict[str, Any]] = None) -> MCPError:
        """
        创建错误响应消息
        
        Args:
            error: 错误信息
            request_id: 请求ID
            data: 额外错误数据
            
        Returns:
            错误消息
        """
        if isinstance(error, Exception):
            return MCPError.create_error(
                MCPErrorCode.INTERNAL_ERROR,
                str(error),
                data,
                request_id
            )
        else:
            return MCPError.create_error(
                error,
                str(error),
                data,
                request_id
            )


# 便捷函数
def parse_message(data: Union[str, Dict[str, Any]]) -> MCPMessage:
    """
    解析MCP消息
    
    Args:
        data: 消息数据
        
    Returns:
        MCP消息实例
    """
    return MCPMessageFactory.create_message(data)


def create_success_response(result: Any, request_id: Union[str, int]) -> str:
    """
    创建成功响应JSON
    
    Args:
        result: 响应结果
        request_id: 请求ID
        
    Returns:
        响应JSON字符串
    """
    response = MCPMessageFactory.create_response(result, request_id)
    return response.to_json()


def create_error_response(error: Union[MCPErrorCode, int, Exception], 
                         request_id: Optional[Union[str, int]] = None,
                         data: Optional[Dict[str, Any]] = None) -> str:
    """
    创建错误响应JSON
    
    Args:
        error: 错误信息
        request_id: 请求ID
        data: 额外错误数据
        
    Returns:
        错误响应JSON字符串
    """
    error_response = MCPMessageFactory.create_error_response(error, request_id, data)
    return error_response.to_json()