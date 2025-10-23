"""
UnityLangPX MCP批量翻译工具模块

实现MCP协议的批量翻译工具。
"""

from pathlib import Path
from typing import Dict, Any

from .base import BaseTool, ToolParameter, ToolResult, create_tool_parameter
from ...core.logger import get_logger

logger = get_logger(__name__)


class BatchTranslationTool(BaseTool):
    """批量翻译工具"""
    
    def __init__(self, protocol_adapter):
        """
        初始化批量翻译工具
        
        Args:
            protocol_adapter: 协议适配器
        """
        super().__init__(
            name="translate_directory",
            description="批量翻译目录中的文件，支持递归处理"
        )
        self.protocol_adapter = protocol_adapter
    
    def _setup_parameters(self):
        """设置工具参数"""
        # 输入目录参数
        self.add_parameter(create_tool_parameter(
            name="input_directory",
            param_type="string",
            description="输入目录路径",
            required=True,
            min_length=1,
            max_length=500
        ))
        
        # 输出目录参数
        self.add_parameter(create_tool_parameter(
            name="output_directory",
            param_type="string",
            description="输出目录路径",
            required=True,
            min_length=1,
            max_length=500
        ))
        
        # 文件模式参数
        self.add_parameter(create_tool_parameter(
            name="file_pattern",
            param_type="string",
            description="文件匹配模式，如'*.md'、'*.txt'",
            required=False,
            default="*.md",
            enum=["*.md", "*.txt", "*.markdown", "*.*"]
        ))
        
        # 递归处理参数
        self.add_parameter(create_tool_parameter(
            name="recursive",
            param_type="boolean",
            description="是否递归处理子目录",
            required=False,
            default=False
        ))
        
        # 并行工作线程数参数
        self.add_parameter(create_tool_parameter(
            name="parallel_workers",
            param_type="number",
            description="并行工作线程数",
            required=False,
            default=4,
            minimum=1,
            maximum=10
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
        执行批量翻译
        
        Args:
            params: 工具参数
            
        Returns:
            翻译结果
        """
        try:
            # 提取参数
            input_dir = params["input_directory"]
            output_dir = params["output_directory"]
            file_pattern = params.get("file_pattern", "*.md")
            recursive = params.get("recursive", False)
            parallel_workers = int(params.get("parallel_workers", 4))
            source_lang = params.get("source_language", "en")
            target_lang = params.get("target_language", "zh")
            context = params.get("context", "")
            
            # 验证目录路径
            input_path = Path(input_dir)
            if not input_path.exists():
                return ToolResult(
                    success=False,
                    error=f"输入目录不存在: {input_dir}"
                )
            
            if not input_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"输入路径不是目录: {input_dir}"
                )
            
            # 创建输出目录
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 验证并行工作线程数
            if parallel_workers < 1 or parallel_workers > 10:
                return ToolResult(
                    success=False,
                    error=f"并行工作线程数必须在1-10之间: {parallel_workers}"
                )
            
            logger.info(f"开始批量翻译: {input_dir} -> {output_dir}")
            
            # 调用协议适配器进行批量翻译
            result = await self.protocol_adapter.translate_directory(
                input_dir=input_dir,
                output_dir=output_dir,
                source_lang=source_lang,
                target_lang=target_lang,
                file_pattern=file_pattern,
                recursive=recursive,
                parallel_workers=parallel_workers,
                context=context if context else None,
                use_terminology=False
            )
            
            if result["success"]:
                logger.info(f"批量翻译完成，成功: {result['files_processed']}, 失败: {result['files_failed']}")
                return ToolResult(
                    success=True,
                    data={
                        "input_directory": result["input_directory"],
                        "output_directory": result["output_directory"],
                        "files_found": result["files_found"],
                        "files_processed": result["files_processed"],
                        "files_failed": result["files_failed"],
                        "source_language": result["source_language"],
                        "target_language": result["target_language"],
                        "file_pattern": file_pattern,
                        "recursive": recursive,
                        "parallel_workers": parallel_workers,
                        "context_used": bool(context),
                        "success_rate": result["files_processed"] / result["files_found"] if result["files_found"] > 0 else 0,
                        "results": result.get("results", [])
                    }
                )
            else:
                logger.error(f"批量翻译失败: {result['error']}")
                return ToolResult(
                    success=False,
                    error=result["error"],
                    data={
                        "input_directory": input_dir,
                        "output_directory": output_dir,
                        "source_language": source_lang,
                        "target_language": target_lang
                    }
                )
                
        except Exception as e:
            logger.error(f"批量翻译异常: {str(e)}")
            return ToolResult(
                success=False,
                error=f"批量翻译失败: {str(e)}"
            )