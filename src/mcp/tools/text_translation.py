"""
UnityLangPX MCP文本翻译工具模块

实现MCP协议的文本翻译工具。
"""

from typing import Dict, Any

from .base import BaseTool, ToolParameter, ToolResult, create_tool_parameter
from ...core.logger import get_logger

logger = get_logger(__name__)


class TextTranslationTool(BaseTool):
    """文本翻译工具"""
    
    def __init__(self, protocol_adapter):
        """
        初始化文本翻译工具
        
        Args:
            protocol_adapter: 协议适配器
        """
        super().__init__(
            name="translate_text",
            description="翻译单个文本片段，支持多种语言对"
        )
        self.protocol_adapter = protocol_adapter
    
    def _setup_parameters(self):
        """设置工具参数"""
        # 文本参数
        self.add_parameter(create_tool_parameter(
            name="text",
            param_type="string",
            description="需要翻译的文本内容",
            required=True,
            min_length=1,
            max_length=10000
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
        执行文本翻译
        
        Args:
            params: 工具参数
            
        Returns:
            翻译结果
        """
        try:
            # 提取参数
            text = params["text"]
            source_lang = params.get("source_language", "en")
            target_lang = params.get("target_language", "zh")
            context = params.get("context", "")
            
            logger.info(f"开始文本翻译: {source_lang} -> {target_lang}, 长度: {len(text)}")
            
            # 调用协议适配器进行翻译
            result = await self.protocol_adapter.translate_text(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                context=context if context else None,
                use_terminology=False
            )
            
            if result["success"]:
                logger.info(f"文本翻译完成，耗时: {result['duration']:.2f}秒")
                return ToolResult(
                    success=True,
                    data={
                        "original_text": result["original_text"],
                        "translated_text": result["translated_text"],
                        "source_language": result["source_language"],
                        "target_language": result["target_language"],
                        "duration": result["duration"],
                        "chars_translated": result["chars_translated"],
                        "context_used": bool(context),
                        "metadata": result.get("metadata", {})
                    }
                )
            else:
                logger.error(f"文本翻译失败: {result['error']}")
                return ToolResult(
                    success=False,
                    error=result["error"],
                    data={
                        "original_text": text,
                        "source_language": source_lang,
                        "target_language": target_lang
                    }
                )
                
        except Exception as e:
            logger.error(f"文本翻译异常: {str(e)}")
            return ToolResult(
                success=False,
                error=f"文本翻译失败: {str(e)}"
            )