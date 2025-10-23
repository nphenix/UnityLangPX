"""
UnityLangPX CLI命令处理器

这个模块实现了CLI命令的处理逻辑，包括文件翻译、目录翻译、
配置管理和服务状态检查等功能。
"""

import os
import sys
import time
import locale
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..core import (
    Config, Translator, TranslationResult,
    init_logger, get_logger, LoggerManager,
    UnityLangPXError, ConfigurationError
)
from ..core.batch_processor import FileBatchProcessor
from ..core.exceptions import APIConnectionError, ModelNotFoundError

# 设置默认编码为UTF-8
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        # 如果都失败了，至少设置控制台编码
        if sys.platform == 'win32':
            import subprocess
            try:
                subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
            except:
                pass

# 设置标准输出编码为UTF-8（Windows特有问题）
if sys.platform == 'win32':
    import codecs
    try:
        # 尝试设置控制台输出编码
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    except:
        # 如果失败，尝试其他方法
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except:
            pass

logger = get_logger(__name__)
console = Console()


class ProgressReporter:
    """进度报告器"""
    
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        )
        self.current_task = None
    
    def start(self, description: str, total: Optional[int] = None):
        """开始进度跟踪"""
        self.current_task = self.progress.add_task(description, total=total)
        self.progress.start()
    
    def update(self, advance: int = 1, description: Optional[str] = None):
        """更新进度"""
        if self.current_task:
            self.progress.update(self.current_task, advance=advance, description=description)
    
    def finish(self):
        """完成进度跟踪"""
        self.progress.stop()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish()


def print_banner():
    """打印程序横幅"""
    banner = """
[bold blue]UnityLangPX[/bold blue] - 基于大模型技术的翻译工具

版本: [green]0.1.0[/green]
作者: [cyan]UnityLangPX Team[/cyan]
"""
    console.print(Panel(banner, border_style="blue"))


def print_error(message: str):
    """打印错误信息"""
    console.print(f"[red]错误:[/red] {message}")


def print_success(message: str):
    """打印成功信息"""
    console.print(f"[green]成功:[/green] {message}")


def print_warning(message: str):
    """打印警告信息"""
    console.print(f"[yellow]警告:[/yellow] {message}")


def print_info(message: str):
    """打印信息"""
    console.print(f"[blue]信息:[/blue] {message}")


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.option('--quiet', '-q', is_flag=True, help='静默模式')
@click.pass_context
def cli(ctx, config, verbose, quiet):
    """UnityLangPX - 基于大模型技术的翻译工具"""
    # 确保上下文对象存在
    ctx.ensure_object(dict)
    
    # 设置日志级别
    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "ERROR"
    else:
        log_level = "INFO"
    
    # 初始化日志
    try:
        logger_manager = init_logger()
        ctx.obj['logger_manager'] = logger_manager
    except Exception as e:
        print_error(f"初始化日志失败: {str(e)}")
        sys.exit(1)
    
    # 加载配置
    try:
        app_config = Config(config_file=config)
        app_config.logging.level = log_level
        ctx.obj['config'] = app_config
    except Exception as e:
        print_error(f"加载配置失败: {str(e)}")
        sys.exit(1)
    
    # 如果不是静默模式，打印横幅
    if not quiet:
        print_banner()


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='输出文件或目录路径')
@click.option('--source-lang', '-s', default='en', help='源语言 (默认: en)')
@click.option('--target-lang', '-t', default='zh', help='目标语言 (默认: zh)')
@click.option('--recursive', '-r', is_flag=True, help='递归处理目录')
@click.option('--overwrite', is_flag=True, help='覆盖已存在的文件')
@click.pass_context
def translate(ctx, input_path, output, source_lang, target_lang, recursive, overwrite):
    """翻译文件或目录"""
    config = ctx.obj['config']
    
    try:
        # 创建翻译引擎
        with Translator(config) as translator:
            # 检查服务状态
            console.print("[blue]检查服务状态...[/blue]")
            status = translator.check_service()
            
            if not status["connected"]:
                print_error(f"无法连接到{status['provider']}服务，请确保服务正在运行")
                sys.exit(1)
            
            if not status["model_available"]:
                model_config = config.get_model_config()
                print_error(f"模型 {model_config.model} 不可用")
                if status["available_models"]:
                    print_info(f"可用模型: {', '.join(status['available_models'])}")
                sys.exit(1)
            
            print_success("服务状态正常")
            
            # 处理输入路径
            input_path = Path(input_path)
            
            if input_path.is_file():
                # 翻译单个文件
                _translate_single_file(
                    translator, input_path, output, 
                    source_lang, target_lang, overwrite
                )
            elif input_path.is_dir():
                # 翻译目录
                _translate_directory(
                    translator, input_path, output,
                    source_lang, target_lang, recursive, overwrite
                )
            else:
                print_error(f"无效的输入路径: {input_path}")
                sys.exit(1)
                
    except KeyboardInterrupt:
        print_warning("用户中断操作")
        sys.exit(1)
    except Exception as e:
        print_error(f"翻译失败: {str(e)}")
        sys.exit(1)


def _translate_single_file(translator: Translator, input_file: Path, 
                          output_path: Optional[str], source_lang: str,
                          target_lang: str, overwrite: bool):
    """翻译单个文件"""
    # 确定输出文件路径
    if output_path:
        output_file = Path(output_path)
        if output_file.is_dir():
            output_file = output_file / input_file.name
    else:
        output_file = translator._generate_output_path(input_file)
    
    # 检查输出文件是否存在
    if output_file.exists() and not overwrite:
        print_warning(f"输出文件已存在: {output_file}")
        if not click.confirm("是否覆盖?"):
            print_info("跳过文件翻译")
            return
    
    # 执行翻译
    console.print(f"[blue]翻译文件:[/blue] {input_file}")
    
    with ProgressReporter() as progress:
        progress.start("翻译中...", total=1)
        
        result = translator.translate_file(
            input_file, output_file,
            source_lang=source_lang,
            target_lang=target_lang
        )
        
        progress.update(1, "完成")
        progress.finish()
    
    # 显示结果
    if result.success:
        print_success(f"翻译完成: {output_file}")
        console.print(f"  翻译字符: {result.chars_translated}")
        console.print(f"  耗时: {result.duration:.2f}秒")
        if result.duration > 0:
            speed = result.chars_translated / result.duration
            console.print(f"  速度: {speed:.1f} 字符/秒")
    else:
        print_error(f"翻译失败: {result.error}")


def _translate_directory(translator: Translator, input_dir: Path,
                        output_path: Optional[str], source_lang: str,
                        target_lang: str, recursive: bool, overwrite: bool):
    """翻译目录"""
    # 确定输出目录
    if output_path:
        output_dir = Path(output_path)
    else:
        output_dir = Path(translator.config.cli.output_dir)
    
    # 创建批处理器
    batch_processor = FileBatchProcessor(None, translator)
    
    # 设置进度回调
    def progress_callback(processed: int, total: int, current_file: str):
        progress.update(processed, f"翻译: {Path(current_file).name}")
    
    batch_processor.set_progress_callback(progress_callback)
    
    # 执行批量翻译
    with ProgressReporter() as progress:
        progress.start(f"翻译目录: {input_dir.name}", total=1)
        
        # 处理目录
        stats = batch_processor.process_directory(
            input_dir=input_dir,
            output_dir=output_dir,
            pattern="*.md",
            recursive=recursive,
            overwrite=overwrite
        )
        
        progress.update(1, "完成")
        progress.finish()
    
    # 显示统计信息
    _print_batch_stats(stats)
    
    # 保存失败文件列表
    if stats.failed_files > 0:
        failed_files_path = output_dir / "translation_failed_files.md"
        batch_processor.save_failed_files_list(failed_files_path)
        print_warning(f"失败文件列表已保存到: {failed_files_path}")


def _find_markdown_files(directory: Path, recursive: bool) -> List[Path]:
    """查找Markdown文件"""
    files = []
    
    if recursive:
        pattern = "**/*.md"
    else:
        pattern = "*.md"
    
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            files.append(file_path)
    
    return sorted(files)


def _print_translation_stats(stats: Dict[str, Any]):
    """打印翻译统计信息"""
    table = Table(title="翻译统计")
    table.add_column("项目", style="cyan")
    table.add_column("数值", style="green")
    
    table.add_row("总文件数", str(stats['total']))
    table.add_row("成功", str(stats['success']))
    table.add_row("失败", str(stats['failed']))
    table.add_row("跳过", str(stats['skipped']))
    table.add_row("总字符数", str(stats['total_chars']))
    
    if stats['total_time'] > 0:
        table.add_row("总耗时", f"{stats['total_time']:.2f}秒")
        speed = stats['total_chars'] / stats['total_time']
        table.add_row("平均速度", f"{speed:.1f} 字符/秒")
    
    console.print(table)


def _print_batch_stats(stats):
    """打印批处理统计信息"""
    table = Table(title="翻译统计")
    table.add_column("项目", style="cyan")
    table.add_column("数值", style="green")
    
    table.add_row("总文件数", str(stats.total_files))
    table.add_row("成功", str(stats.processed_files))
    table.add_row("失败", str(stats.failed_files))
    table.add_row("跳过", str(stats.skipped_files))
    table.add_row("成功率", f"{stats.success_rate:.1f}%")
    table.add_row("总字符数", str(stats.total_chars))
    table.add_row("翻译字符", str(stats.translated_chars))
    
    if stats.duration > 0:
        table.add_row("总耗时", f"{stats.duration:.2f}秒")
        table.add_row("平均速度", f"{stats.average_speed:.1f} 字符/秒")
    
    console.print(table)
    
    # 显示失败文件列表
    if stats.failed_files_list:
        console.print("\n[red]翻译失败的文件:[/red]")
        for file_path in stats.failed_files_list[:10]:  # 只显示前10个
            console.print(f"  - {file_path}")
        
        if len(stats.failed_files_list) > 10:
            console.print(f"  ... 还有 {len(stats.failed_files_list) - 10} 个文件")


def _print_translation_status_summary(translator: Translator):
    """打印翻译状态摘要"""
    status_counts = {
        'pending': 0,
        'in_progress': 0,
        'completed': 0,
        'failed': 0,
        'partial': 0
    }
    
    for file_status in translator.file_statuses.values():
        status_counts[file_status.status] += 1
    
    table = Table(title="翻译状态摘要")
    table.add_column("状态", style="cyan")
    table.add_column("文件数", style="green")
    
    status_names = {
        'pending': '待处理',
        'in_progress': '进行中',
        'completed': '已完成',
        'failed': '失败',
        'partial': '部分完成'
    }
    
    for status, count in status_counts.items():
        if count > 0:
            table.add_row(status_names.get(status, status), str(count))
    
    console.print(table)


@cli.command()
@click.pass_context
def status(ctx):
    """检查服务状态"""
    config = ctx.obj['config']
    
    try:
        with Translator(config) as translator:
            console.print("[blue]检查服务状态...[/blue]")
            
            status = translator.check_service()
            
            # 创建状态表格
            table = Table(title="服务状态")
            table.add_column("项目", style="cyan")
            table.add_column("状态", style="green")
            table.add_column("详情", style="white")
            
            # 服务连接状态
            provider = status["provider"]
            connection_status = "正常" if status["connected"] else "异常"
            if provider == "ollama":
                connection_detail = config.model_ollama.host
            else:
                connection_detail = config.model_openai.base_url
            table.add_row(f"{provider}连接", connection_status, connection_detail)
            
            # 模型状态
            model_status = "可用" if status["model_available"] else "不可用"
            model_config = config.get_model_config()
            table.add_row("翻译模型", model_status, model_config.model)
            
            # 可用模型
            if status["available_models"]:
                models_text = ", ".join(status["available_models"][:5])
                if len(status["available_models"]) > 5:
                    models_text += f" (共{len(status['available_models'])}个)"
                table.add_row("可用模型", "", models_text)
            
            console.print(table)
            
            # 显示错误信息
            if status.get("error"):
                print_error(status["error"])
                
    except Exception as e:
        print_error(f"检查状态失败: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--show-cache', is_flag=True, help='显示缓存信息')
@click.pass_context
def config_cmd(ctx, show_cache):
    """配置管理"""
    config = ctx.obj['config']
    
    if show_cache:
        # 显示缓存信息
        cache_dir = Path(config.cache.cache_dir)
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*"))
            console.print(f"[blue]缓存目录:[/blue] {cache_dir}")
            console.print(f"[blue]缓存文件数:[/blue] {len(cache_files)}")
            
            # 计算缓存大小
            total_size = sum(f.stat().st_size for f in cache_files if f.is_file())
            console.print(f"[blue]缓存大小:[/blue] {total_size / 1024 / 1024:.2f} MB")
        else:
            console.print("[yellow]缓存目录不存在[/yellow]")
    else:
        # 显示当前配置
        console.print("[blue]当前配置:[/blue]")
        
        # 创建配置表格
        table = Table()
        table.add_column("配置项", style="cyan")
        table.add_column("值", style="white")
        
        # 模型配置
        provider = config.model.provider
        if provider == "ollama":
            table.add_row("模型提供商", provider)
            table.add_row("服务地址", config.model_ollama.host)
            table.add_row("翻译模型", config.model_ollama.model)
            table.add_row("请求超时", f"{config.model_ollama.timeout}秒")
        else:
            table.add_row("模型提供商", provider)
            table.add_row("API地址", config.model_openai.base_url)
            table.add_row("翻译模型", config.model_openai.model)
            table.add_row("请求超时", f"{config.model_openai.timeout}秒")
        
        # 翻译配置
        table.add_row("源语言", config.translation.source_language)
        table.add_row("目标语言", config.translation.target_language)
        table.add_row("生成温度", str(config.translation.temperature))
        table.add_row("分块大小", str(config.translation.chunk_size))
        
        # CLI配置
        table.add_row("输入目录", config.cli.input_dir)
        table.add_row("输出目录", config.cli.output_dir)
        table.add_row("并行线程", str(config.cli.parallel_workers))
        
        # 缓存配置
        cache_status = "启用" if config.cache.enable_cache else "禁用"
        table.add_row("缓存状态", cache_status)
        if config.cache.enable_cache:
            table.add_row("缓存目录", config.cache.cache_dir)
            table.add_row("最大缓存", f"{config.cache.max_cache_size_mb}MB")
        
        console.print(table)


@cli.command()
@click.pass_context
def clear_cache(ctx):
    """清空翻译缓存"""
    config = ctx.obj['config']
    
    if not config.cache.enable_cache:
        print_warning("缓存未启用")
        return
    
    if not click.confirm("确定要清空翻译缓存吗?"):
        print_info("操作已取消")
        return
    
    try:
        with Translator(config) as translator:
            translator.clear_cache()
            print_success("翻译缓存已清空")
    except Exception as e:
        print_error(f"清空缓存失败: {str(e)}")
        sys.exit(1)


@cli.command()
@click.argument('text')
@click.option('--source-lang', '-s', default='en', help='源语言 (默认: en)')
@click.option('--target-lang', '-t', default='zh', help='目标语言 (默认: zh)')
@click.pass_context
def demo(ctx, text, source_lang, target_lang):
    """演示翻译功能"""
    config = ctx.obj['config']
    
    try:
        with Translator(config) as translator:
            console.print(f"[blue]原文 ({source_lang}):[/blue] {text}")
            
            with ProgressReporter() as progress:
                progress.start("翻译中...", total=1)
                
                result = translator.translate_text(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                
                progress.update(1, "完成")
                progress.finish()
            
            if result.success:
                console.print(f"[green]译文 ({target_lang}):[/green] {result.translated_text}")
                console.print(f"  耗时: {result.duration:.2f}秒")
            else:
                print_error(f"翻译失败: {result.error}")
                
    except Exception as e:
        print_error(f"演示失败: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--port', '-p', type=int, help='指定端口 (默认自动分配)')
@click.option('--host', default='localhost', help='绑定地址 (默认: localhost)')
@click.option('--daemon', '-d', is_flag=True, help='后台运行')
@click.pass_context
def serve(ctx, port, host, daemon):
    """启动HTTP API服务器"""
    config = ctx.obj['config']
    
    try:
        from .http_server import create_server
        
        # 确定端口范围
        if port:
            port_range = (port, port)
        else:
            port_range = (8848, 8898)
        
        # 创建服务器
        server = create_server(config, port_range)
        
        # 启动服务器
        result = server.start()
        
        if result['success']:
            print_success(f"翻译API服务器已启动")
            console.print(f"[blue]服务地址:[/blue] http://{host}:{result['port']}")
            console.print(f"[blue]API文档:[/blue] http://{host}:{result['port']}/api/service/status")
            
            if not daemon:
                try:
                    print_info("按 Ctrl+C 停止服务器")
                    # 保持服务器运行
                    while server.is_running():
                        time.sleep(1)
                except KeyboardInterrupt:
                    print_warning("正在停止服务器...")
                    server.stop()
                    print_success("服务器已停止")
        else:
            print_error(f"启动服务器失败: {result['error']}")
            sys.exit(1)
            
    except ImportError as e:
        print_error(f"导入HTTP服务器模块失败: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print_error(f"启动服务器失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    cli()