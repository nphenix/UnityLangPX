"""
UnityLangPX MCP文件翻译工具模块

实现MCP协议的文件翻译工具。
"""

from pathlib import Path
from typing import Dict, Any

from .base import BaseTool, ToolParameter, ToolResult, create_tool_parameter
from ...core.logger import get_logger

logger = get_logger(__name__)


class FileTranslationTool(BaseTool):
    """文件翻译工具"""
    
    def __init__(self, protocol_adapter):
        """
        初始化文件翻译工具
        
        Args:
            protocol_adapter: 协议适配器
        """
        super().__init__(
            name="translate_file",
            description="翻译单个文件，支持Markdown和纯文本文件"
        )
        self.protocol_adapter = protocol_adapter
    
    def _setup_parameters(self):
        """设置工具参数"""
        # 文件路径参数
        self.add_parameter(create_tool_parameter(
            name="file_path",
            param_type="string",
            description="需要翻译的文件路径",
            required=True,
            min_length=1,
            max_length=500
        ))
        
        # 输出路径参数
        self.add_parameter(create_tool_parameter(
            name="output_path",
            param_type="string",
            description="输出文件路径，如果不指定则自动生成",
            required=False,
            default="",
            max_length=500
        ))
        
        # 源语言参数
        self.add_parameter(create_tool_parameter(
            name="source_language",
            param_type="string",
            description="源语言代码，如'en'、'zh'等",
            required=False,
            default="en",
            enum=["en", "zh", "ja", "ko", "fr", "de", "es", "ru", "ar"]
        ))
        
        # 目标语言参数
        self.add_parameter(create_tool_parameter(
            name="target_language",
            param_type="string",
            description="目标语言代码，如'en'、'zh'等",
            required=False,
            default="zh",
            enum=["en", "zh", "ja", "ko", "fr", "de", "es", "ru", "ar"]
        ))
        
        # 上下文参数
        self.add_parameter(create_tool_parameter(
            name="context",
            param_type="string",
            description="翻译上下文信息，有助于提高翻译质量",
            required=False,
            default="",
            max_length=1000
        ))
        
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        执行文件翻译
        
        Args:
            params: 工具参数
            
        Returns:
            翻译结果
        """
        try:
            # 提取参数
            file_path = params["file_path"]
            output_path = params.get("output_path", "")
            source_lang = params.get("source_language", "en")
            target_lang = params.get("target_language", "zh")
            context = params.get("context", "")
            
            # 验证文件路径
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"文件不存在: {file_path}"
                )
            
            # 检查文件类型
            if not self._is_supported_file(path):
                return ToolResult(
                    success=False,
                    error=f"不支持的文件类型: {path.suffix}，支持的类型: .md, .txt"
                )
            
            # 检查文件大小
            file_size = path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB
                return ToolResult(
                    success=False,
                    error=f"文件过大: {file_size / 1024 / 1024:.2f}MB，最大支持10MB"
                )
            
            logger.info(f"开始文件翻译: {file_path} ({file_size} 字节)")
            
            # 调用协议适配器进行翻译
            result = await self.protocol_adapter.translate_file(
                file_path=file_path,
                source_lang=source_lang,
                target_lang=target_lang,
                output_path=output_path if output_path else None,
                context=context if context else None,
                use_terminology=False
            )
            
            if result["success"]:
                logger.info(f"文件翻译完成，耗时: {result['duration']:.2f}秒")
                return ToolResult(
                    success=True,
                    data={
                        "source_file": result["source_file"],
                        "target_file": result["target_file"],
                        "source_language": result["source_language"],
                        "target_language": result["target_language"],
                        "duration": result["duration"],
                        "chars_translated": result["chars_translated"],
                        "elements_processed": result["elements_processed"],
                        "file_size": file_size,
                        "context_used": bool(context),
                        "metadata": result.get("metadata", {})
                    }
                )
            else:
                logger.error(f"文件翻译失败: {result['error']}")
                return ToolResult(
                    success=False,
                    error=result["error"],
                    data={
                        "source_file": file_path,
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "file_size": file_size
                    }
                )
                
        except Exception as e:
            logger.error(f"文件翻译异常: {str(e)}")
            return ToolResult(
                success=False,
                error=f"文件翻译失败: {str(e)}"
            )
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """
        检查是否为支持的文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持
        """
        supported_extensions = {".md", ".txt", ".markdown"}
        return file_path.suffix.lower() in supported_extensions