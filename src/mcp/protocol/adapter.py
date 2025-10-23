"""
UnityLangPX MCP协议适配器模块

将MCP协议转换为内部调用，处理协议版本兼容性。
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from ...core.logger import get_logger
from ...core.config import Config
from ...core.translator import Translator
from ..tools import ToolRegistry

logger = get_logger(__name__)


class ProtocolAdapter:
    """MCP协议适配器"""
    
    def __init__(self, config: Config, tool_registry: ToolRegistry):
        """
        初始化协议适配器
        
        Args:
            config: 配置对象
            tool_registry: 工具注册表
        """
        self.config = config
        self.tool_registry = tool_registry
        self._translator_pool = asyncio.Queue(maxsize=5)
        self._initialize_translator_pool()
        
        logger.info("MCP协议适配器初始化完成")
    
    def _initialize_translator_pool(self):
        """初始化翻译器连接池"""
        for _ in range(5):
            translator = Translator(self.config)
            self._translator_pool.put_nowait(translator)
        
        logger.debug("翻译器连接池初始化完成，池大小: 5")
    
    async def _get_translator(self) -> Translator:
        """
        获取翻译器实例
        
        Returns:
            翻译器实例
        """
        return await self._translator_pool.get()
    
    async def _return_translator(self, translator: Translator):
        """
        归还翻译器实例
        
        Args:
            translator: 翻译器实例
        """
        await self._translator_pool.put(translator)
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有可用工具
        
        Returns:
            工具列表
        """
        try:
            tools = await self.tool_registry.list_tools()
            logger.debug(f"获取工具列表，共 {len(tools)} 个工具")
            return tools
        except Exception as e:
            logger.error(f"获取工具列表失败: {str(e)}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            # 获取工具
            tool = await self.tool_registry.get_tool(tool_name)
            if not tool:
                raise ValueError(f"未找到工具: {tool_name}")
            
            # 验证参数
            if not tool.validate_params(arguments):
                raise ValueError(f"工具参数验证失败: {tool_name}")
            
            # 执行工具
            logger.debug(f"执行工具: {tool_name}")
            result = await tool.execute(arguments)
            
            logger.debug(f"工具执行完成: {tool_name}")
            return result
            
        except Exception as e:
            logger.error(f"工具调用失败: {tool_name}, 错误: {str(e)}")
            raise
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        获取健康状态
        
        Returns:
            健康状态信息
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        try:
            # 检查翻译器状态
            translator = await self._get_translator()
            ollama_status = translator.check_service()
            
            health_status["checks"]["translator"] = {
                "status": "healthy" if ollama_status.get("connected") else "unhealthy",
                "details": ollama_status
            }
            
            await self._return_translator(translator)
            
            # 检查工具注册表状态
            tools = await self.tool_registry.list_tools()
            tools_count = len(tools)
            health_status["checks"]["tools"] = {
                "status": "healthy",
                "details": {
                    "available_tools": tools_count
                }
            }
            
            # 检查连接池状态
            pool_size = self._translator_pool.qsize()
            health_status["checks"]["connection_pool"] = {
                "status": "healthy",
                "details": {
                    "available_connections": pool_size,
                    "max_connections": 5
                }
            }
            
            # 如果有任何检查失败，整体状态为不健康
            for check in health_status["checks"].values():
                if check["status"] != "healthy":
                    health_status["status"] = "unhealthy"
                    break
            
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def translate_text(self, text: str, source_lang: str = "en",
                           target_lang: str = "zh", context: Optional[str] = None,
                           use_terminology: bool = False) -> Dict[str, Any]:
        """
        翻译文本
        
        Args:
            text: 待翻译文本
            source_lang: 源语言
            target_lang: 目标语言
            context: 上下文信息
            use_terminology: 是否使用术语库
            
        Returns:
            翻译结果
        """
        translator = None
        try:
            # 获取翻译器
            translator = await self._get_translator()
            
            # 执行翻译
            logger.debug(f"开始翻译文本，长度: {len(text)}")
            result = translator.translate_text(
                text=text,
                context=context,
                source_lang=source_lang,
                target_lang=target_lang,
                apply_terminology=False
            )
            
            if result.success:
                logger.debug(f"文本翻译完成，耗时: {result.duration:.2f}秒")
                return {
                    "success": True,
                    "original_text": result.source_text,
                    "translated_text": result.translated_text,
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "duration": result.duration,
                    "chars_translated": result.chars_translated,
                    "metadata": result.metadata
                }
            else:
                logger.error(f"文本翻译失败: {result.error}")
                return {
                    "success": False,
                    "error": result.error,
                    "original_text": text,
                    "source_language": source_lang,
                    "target_language": target_lang
                }
                
        except Exception as e:
            logger.error(f"文本翻译异常: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "original_text": text,
                "source_language": source_lang,
                "target_language": target_lang
            }
        finally:
            if translator:
                await self._return_translator(translator)
    
    async def translate_file(self, file_path: str, source_lang: str = "en",
                           target_lang: str = "zh", output_path: Optional[str] = None,
                           context: Optional[str] = None, use_terminology: bool = False) -> Dict[str, Any]:
        """
        翻译文件
        
        Args:
            file_path: 文件路径
            source_lang: 源语言
            target_lang: 目标语言
            output_path: 输出路径
            context: 上下文信息
            use_terminology: 是否使用术语库
            
        Returns:
            翻译结果
        """
        from pathlib import Path
        
        translator = None
        try:
            # 验证文件路径
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 获取翻译器
            translator = await self._get_translator()
            
            # 确定输出路径
            output_file = None
            if output_path:
                output_file = Path(output_path)
            else:
                # 自动生成输出路径
                output_file = path.with_suffix(f".translated{path.suffix}")
            
            # 执行翻译
            logger.debug(f"开始翻译文件: {file_path}")
            result = translator.translate_file(
                input_file=path,
                output_file=output_file,
                context=context,
                source_lang=source_lang,
                target_lang=target_lang,
                apply_terminology=False
            )
            
            if result.success:
                logger.debug(f"文件翻译完成，耗时: {result.duration:.2f}秒")
                return {
                    "success": True,
                    "source_file": str(result.source_file),
                    "target_file": str(result.target_file),
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "duration": result.duration,
                    "chars_translated": result.chars_translated,
                    "elements_processed": result.elements_processed,
                    "metadata": result.metadata
                }
            else:
                logger.error(f"文件翻译失败: {result.error}")
                return {
                    "success": False,
                    "error": result.error,
                    "source_file": file_path,
                    "source_language": source_lang,
                    "target_language": target_lang
                }
                
        except Exception as e:
            logger.error(f"文件翻译异常: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "source_file": file_path,
                "source_language": source_lang,
                "target_language": target_lang
            }
        finally:
            if translator:
                await self._return_translator(translator)
    
    async def translate_directory(self, input_dir: str, output_dir: str,
                                source_lang: str = "en", target_lang: str = "zh",
                                file_pattern: str = "*.md", recursive: bool = False,
                                parallel_workers: int = 4, context: Optional[str] = None,
                                use_terminology: bool = False) -> Dict[str, Any]:
        """
        批量翻译目录
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            source_lang: 源语言
            target_lang: 目标语言
            file_pattern: 文件模式
            recursive: 是否递归处理
            parallel_workers: 并行工作线程数
            context: 上下文信息
            use_terminology: 是否使用术语库
            
        Returns:
            批量翻译结果
        """
        from pathlib import Path
        import glob
        
        try:
            # 验证目录
            input_path = Path(input_dir)
            output_path = Path(output_dir)
            
            if not input_path.exists():
                raise FileNotFoundError(f"输入目录不存在: {input_dir}")
            
            # 创建输出目录
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 查找文件
            pattern = f"**/{file_pattern}" if recursive else file_pattern
            files = list(input_path.glob(pattern))
            
            if not files:
                return {
                    "success": True,
                    "message": "没有找到匹配的文件",
                    "input_directory": input_dir,
                    "output_directory": output_dir,
                    "files_found": 0,
                    "files_processed": 0,
                    "files_failed": 0
                }
            
            logger.info(f"开始批量翻译，共 {len(files)} 个文件")
            
            # 创建翻译任务
            tasks = []
            for file_path in files:
                # 计算相对路径
                relative_path = file_path.relative_to(input_path)
                output_file = output_path / relative_path
                
                # 确保输出目录存在
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 创建翻译任务
                task = self.translate_file(
                    file_path=str(file_path),
                    source_lang=source_lang,
                    target_lang=target_lang,
                    output_path=str(output_file),
                    context=context,
                    use_terminology=False
                )
                tasks.append(task)
            
            # 限制并发数
            semaphore = asyncio.Semaphore(parallel_workers)
            
            async def limited_translate(task):
                async with semaphore:
                    return await task
            
            # 执行翻译任务
            results = await asyncio.gather(*[limited_translate(task) for task in tasks])
            
            # 统计结果
            files_processed = sum(1 for r in results if r["success"])
            files_failed = len(results) - files_processed
            
            logger.info(f"批量翻译完成，成功: {files_processed}, 失败: {files_failed}")
            
            return {
                "success": files_failed == 0,
                "input_directory": input_dir,
                "output_directory": output_dir,
                "files_found": len(files),
                "files_processed": files_processed,
                "files_failed": files_failed,
                "source_language": source_lang,
                "target_language": target_lang,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"批量翻译异常: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "input_directory": input_dir,
                "output_directory": output_dir,
                "source_language": source_lang,
                "target_language": target_lang
            }
    
    async def close(self):
        """关闭适配器"""
        try:
            # 关闭所有翻译器
            while not self._translator_pool.empty():
                translator = await self._translator_pool.get()
                translator.close()
            
            logger.info("MCP协议适配器已关闭")
        except Exception as e:
            logger.error(f"关闭协议适配器失败: {str(e)}")


# 便捷函数
def create_protocol_adapter(config: Config, tool_registry: ToolRegistry) -> ProtocolAdapter:
    """
    创建协议适配器
    
    Args:
        config: 配置对象
        tool_registry: 工具注册表
        
    Returns:
        协议适配器实例
    """
    return ProtocolAdapter(config, tool_registry)