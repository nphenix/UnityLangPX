"""
UnityLangPX Markdown处理器模块

这个模块实现了Markdown文档的解析和重构功能，能够识别和处理各种Markdown元素，
保持原始格式的同时提取可翻译内容。
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from .exceptions import MarkdownProcessingError
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class MarkdownElement:
    """Markdown元素数据类"""
    type: str  # 元素类型：text, code_block, header, list_item, link, image, wikilink, tag, yaml
    content: str  # 原始内容
    translatable: bool  # 是否可翻译
    metadata: Optional[Dict[str, Any]] = None  # 元数据
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MarkdownProcessor:
    """Markdown处理器"""
    
    def __init__(self):
        """初始化Markdown处理器"""
        # 编译正则表达式以提高性能
        self._code_block_pattern = re.compile(r'^```(\w*)\s*$(.*?)^```$', re.MULTILINE | re.DOTALL)
        self._inline_code_pattern = re.compile(r'`([^`]+)`')
        self._header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self._list_pattern = re.compile(r'^(\s*[-*+]\s+|\s*\d+\.\s+)(.+)$', re.MULTILINE)
        self._link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        self._image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        self._wikilink_pattern = re.compile(r'\[\[([^\]]+)\]\]')
        self._tag_pattern = re.compile(r'^\s*#\w+')
        self._bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
        self._italic_pattern = re.compile(r'\*([^*]+)\*')
        # 添加Obsidian Callouts模式
        self._callout_pattern = re.compile(r'^>\s*\[!([^\]]+)\](?:\s+(.*))?$', re.MULTILINE)
        self._callout_content_pattern = re.compile(r'^>\s*(.*)$', re.MULTILINE)
        
        logger.debug("Markdown处理器初始化完成")
    
    def extract_translatable_elements(self, text: str) -> List[MarkdownElement]:
        """
        提取可翻译的Markdown元素
        
        Args:
            text: Markdown文本
            
        Returns:
            Markdown元素列表
        """
        try:
            logger.debug(f"开始提取Markdown元素，文本长度: {len(text)}")
            
            elements = []
            
            # 首先提取YAML前置元数据
            text_without_yaml, yaml_element = self._extract_yaml_frontmatter(text)
            if yaml_element:
                elements.append(yaml_element)
            
            # 然后处理代码块（需要先提取，避免干扰其他解析）
            text_without_code_blocks, code_blocks = self._extract_code_blocks(text_without_yaml)
            
            # 提取Obsidian Callouts（需要在处理行内元素之前提取）
            text_without_callouts, callouts = self._extract_callouts(text_without_code_blocks)
            
            # 处理行内元素
            lines = text_without_callouts.split('\n')
            current_block = []
            in_code_block = False
            
            for line_num, line in enumerate(lines):
                # 检查是否是代码块行（已经被提取，这里只是占位）
                if line.strip() == '__CODE_BLOCK_PLACEHOLDER__':
                    # 保存当前块
                    if current_block:
                        block_element = MarkdownElement(
                            type='text',
                            content='\n'.join(current_block),
                            translatable=True,
                            metadata={'line_start': line_num - len(current_block)}
                        )
                        elements.append(block_element)
                        current_block = []
                    
                    # 添加代码块元素
                    if code_blocks:
                        code_element = code_blocks.pop(0)
                        elements.append(code_element)
                    continue
                
                # 检查是否是Callout占位符
                if line.strip() == '__CALLOUT_PLACEHOLDER__':
                    # 保存当前块
                    if current_block:
                        block_element = MarkdownElement(
                            type='text',
                            content='\n'.join(current_block),
                            translatable=True,
                            metadata={'line_start': line_num - len(current_block)}
                        )
                        elements.append(block_element)
                        current_block = []
                    
                    # 添加Callout元素
                    if callouts:
                        callout_element = callouts.pop(0)
                        elements.append(callout_element)
                    continue
                
                # 处理行内元素
                processed_line = self._process_inline_elements(line)
                
                if processed_line.translatable:
                    current_block.append(processed_line.content)
                else:
                    # 保存当前块
                    if current_block:
                        block_element = MarkdownElement(
                            type='text',
                            content='\n'.join(current_block),
                            translatable=True,
                            metadata={'line_start': line_num - len(current_block)}
                        )
                        elements.append(block_element)
                        current_block = []
                    
                    # 添加非可翻译元素
                    elements.append(processed_line)
            
            # 处理最后一个块
            if current_block:
                block_element = MarkdownElement(
                    type='text',
                    content='\n'.join(current_block),
                    translatable=True,
                    metadata={'line_start': len(lines) - len(current_block)}
                )
                elements.append(block_element)
            
            logger.debug(f"提取完成，共 {len(elements)} 个元素")
            return elements
            
        except Exception as e:
            logger.error(f"提取Markdown元素失败: {str(e)}")
            raise MarkdownProcessingError(f"提取Markdown元素失败: {str(e)}")
    
    def _extract_code_blocks(self, text: str) -> Tuple[str, List[MarkdownElement]]:
        """
        提取代码块
        
        Args:
            text: Markdown文本
            
        Returns:
            (去除代码块的文本, 代码块元素列表)
        """
        code_blocks = []
        
        def replace_code_block(match):
            lang = match.group(1).strip()
            code = match.group(2)
            
            # 创建代码块元素
            code_element = MarkdownElement(
                type='code_block',
                content=match.group(0),  # 保留原始格式
                translatable=False,
                metadata={
                    'language': lang,
                    'code': code
                }
            )
            code_blocks.append(code_element)
            
            return '__CODE_BLOCK_PLACEHOLDER__'
        
        # 替换所有代码块
        text_without_code_blocks = self._code_block_pattern.sub(replace_code_block, text)
        
        return text_without_code_blocks, code_blocks
    
    def _extract_callouts(self, text: str) -> Tuple[str, List[MarkdownElement]]:
        """
        提取Obsidian Callouts
        
        Args:
            text: Markdown文本
            
        Returns:
            (去除Callouts的文本, Callout元素列表)
        """
        callouts = []
        lines = text.split('\n')
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是Callout开始
            callout_match = self._callout_pattern.match(line)
            if callout_match:
                callout_type = callout_match.group(1)
                callout_title = callout_match.group(2) or ""
                
                # 收集Callout内容
                callout_lines = [line]
                i += 1
                
                # 收集后续以>开头的内容行
                while i < len(lines) and lines[i].strip().startswith('>'):
                    callout_lines.append(lines[i])
                    i += 1
                
                # 创建Callout元素
                callout_content = '\n'.join(callout_lines)
                callout_element = MarkdownElement(
                    type='callout',
                    content=callout_content,
                    translatable=True,  # Callout内容可翻译，但类型名称不翻译
                    metadata={
                        'type': callout_type,
                        'title': callout_title,
                        'lines': callout_lines
                    }
                )
                callouts.append(callout_element)
                
                # 添加占位符
                result_lines.append('__CALLOUT_PLACEHOLDER__')
            else:
                # 不是Callout，保留原行
                result_lines.append(line)
                i += 1
        
        text_without_callouts = '\n'.join(result_lines)
        return text_without_callouts, callouts
    
    def _extract_yaml_frontmatter(self, text: str) -> Tuple[str, Optional[MarkdownElement]]:
        """
        提取YAML前置元数据
        
        Args:
            text: Markdown文本
            
        Returns:
            (去除YAML的文本, YAML元素)
        """
        # 检查是否以YAML前置元数据开始
        if not text.startswith('---\n'):
            return text, None
        
        # 查找YAML前置元数据的结束位置
        end_pos = text.find('\n---\n', 4)  # 从第4个字符开始查找，跳过开头的---
        if end_pos == -1:
            # 没有找到结束标记，可能不是有效的YAML前置元数据
            return text, None
        
        # 提取YAML前置元数据
        yaml_content = text[:end_pos + 5]  # 包含结束的---\n
        remaining_text = text[end_pos + 5:]
        
        # 创建YAML元素
        yaml_element = MarkdownElement(
            type='yaml',
            content=yaml_content,
            translatable=False,  # YAML前置元数据不翻译
            metadata={'type': 'frontmatter'}
        )
        
        return remaining_text, yaml_element
    
    def _process_inline_elements(self, line: str) -> MarkdownElement:
        """
        处理行内元素
        
        Args:
            line: 文本行
            
        Returns:
            Markdown元素
        """
        # 检查标题
        header_match = self._header_pattern.match(line)
        if header_match:
            level, content = header_match.groups()
            return MarkdownElement(
                type='header',
                content=line,
                translatable=True,
                metadata={
                    'level': len(level),
                    'text': content
                }
            )
        
        # 检查列表项
        list_match = self._list_pattern.match(line)
        if list_match:
            marker, content = list_match.groups()
            return MarkdownElement(
                type='list_item',
                content=line,
                translatable=True,
                metadata={
                    'marker': marker,
                    'text': content
                }
            )
        
        # 检查标签
        if self._tag_pattern.match(line):
            return MarkdownElement(
                type='tag',
                content=line,
                translatable=False,
                metadata={'tag': line.strip()}
            )
        
        # 检查图片
        if self._image_pattern.search(line):
            return self._process_image_line(line)
        
        # 检查链接
        if self._link_pattern.search(line):
            return self._process_link_line(line)
        
        # 检查wikilink
        if self._wikilink_pattern.search(line):
            return self._process_wikilink_line(line)
        
        # 普通文本
        return MarkdownElement(
            type='text',
            content=line,
            translatable=True
        )
    
    def _process_link_line(self, line: str) -> MarkdownElement:
        """处理包含链接的行"""
        # 提取所有链接
        links = []
        
        def extract_link(match):
            text, url = match.groups()
            links.append({'text': text, 'url': url})
            return match.group(0)  # 暂时保持原样
        
        processed_line = self._link_pattern.sub(extract_link, line)
        
        return MarkdownElement(
            type='link',
            content=processed_line,
            translatable=True,
            metadata={'links': links}
        )
    
    def _process_image_line(self, line: str) -> MarkdownElement:
        """处理包含图片的行"""
        # 提取所有图片
        images = []
        
        def extract_image(match):
            alt, url = match.groups()
            images.append({'alt': alt, 'url': url})
            return match.group(0)  # 暂时保持原样
        
        processed_line = self._image_pattern.sub(extract_image, line)
        
        return MarkdownElement(
            type='image',
            content=processed_line,
            translatable=True,  # alt文本可翻译
            metadata={'images': images}
        )
    
    def _process_wikilink_line(self, line: str) -> MarkdownElement:
        """处理包含wikilink的行"""
        # 提取所有wikilink
        wikilinks = []
        
        def extract_wikilink(match):
            link_text = match.group(1)
            wikilinks.append({'text': link_text, 'original': match.group(0)})
            return match.group(0)  # 暂时保持原样
        
        processed_line = self._wikilink_pattern.sub(extract_wikilink, line)
        
        # 检查是否只包含wikilink或主要是wikilink
        non_wikilink_text = self._wikilink_pattern.sub('', line).strip()
        
        # 如果行中除了wikilink还有其他文本，则标记为可翻译
        # 这样可以翻译周围的文本，同时保护wikilink结构
        is_translatable = len(non_wikilink_text) > 0
        
        return MarkdownElement(
            type='wikilink',
            content=processed_line,
            translatable=is_translatable,
            metadata={'wikilinks': wikilinks, 'non_wikilink_text': non_wikilink_text}
        )
    
    def reconstruct_markdown(self, elements: List[MarkdownElement]) -> str:
        """
        重构Markdown文档
        
        Args:
            elements: Markdown元素列表
            
        Returns:
            重构的Markdown文本
        """
        try:
            logger.debug(f"开始重构Markdown文档，元素数量: {len(elements)}")
            
            lines = []
            for element in elements:
                # 确保内容是ASCII兼容的，替换特殊Unicode字符
                content = element.content
                # 替换可能导致编码问题的特殊字符
                content = content.replace('\u280b', '[ ]')  # Braille pattern
                content = content.replace('\u2834', '[ ]')  # Braille pattern
                content = content.replace('\u2826', '[ ]')  # Braille pattern
                content = content.replace('\u2713', '[✓]')  # Check mark
                content = content.replace('\u2717', '[✗]')  # Cross mark
                # 处理所有Braille字符范围 (U+2800 to U+28FF)
                import re
                content = re.sub(r'[\u2800-\u28FF]', '[ ]', content)
                lines.append(content)
            
            result = '\n'.join(lines)
            logger.debug(f"重构完成，文档长度: {len(result)}")
            
            return result
            
        except Exception as e:
            logger.error(f"重构Markdown文档失败: {str(e)}")
            raise MarkdownProcessingError(f"重构Markdown文档失败: {str(e)}")
    
    def translate_element_content(self, element: MarkdownElement, 
                                translated_text: str) -> MarkdownElement:
        """
        翻译元素内容
        
        Args:
            element: 原始元素
            translated_text: 翻译后的文本
            
        Returns:
            更新后的元素
        """
        if not element.translatable:
            return element
        
        # 根据元素类型进行特殊处理
        if element.type == 'header':
            return self._translate_header_element(element, translated_text)
        elif element.type == 'list_item':
            return self._translate_list_item_element(element, translated_text)
        elif element.type == 'link':
            return self._translate_link_element(element, translated_text)
        elif element.type == 'image':
            return self._translate_image_element(element, translated_text)
        elif element.type == 'wikilink':
            return self._translate_wikilink_element(element, translated_text)
        elif element.type == 'yaml':
            # YAML前置元数据不翻译，直接返回原始内容
            return element
        elif element.type == 'text':
            return self._translate_text_element(element, translated_text)
        else:
            # 默认处理
            new_element = MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
            return new_element
    
    def _translate_header_element(self, element: MarkdownElement, 
                                translated_text: str) -> MarkdownElement:
        """翻译标题元素"""
        level = element.metadata.get('level', 1)
        prefix = '#' * level
        return MarkdownElement(
            type=element.type,
            content=f"{prefix} {translated_text}",
            translatable=element.translatable,
            metadata=element.metadata.copy()
        )
    
    def _translate_list_item_element(self, element: MarkdownElement, 
                                   translated_text: str) -> MarkdownElement:
        """翻译列表项元素"""
        marker = element.metadata.get('marker', '- ')
        return MarkdownElement(
            type=element.type,
            content=f"{marker}{translated_text}",
            translatable=element.translatable,
            metadata=element.metadata.copy()
        )
    
    def _translate_link_element(self, element: MarkdownElement,
                              translated_text: str) -> MarkdownElement:
        """翻译链接元素"""
        # 解析原始内容中的链接
        links = element.metadata.get('links', [])
        original_content = element.content
        
        # 如果没有链接信息，直接返回翻译后的内容
        if not links:
            return MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
        
        # 尝试保持链接结构，只翻译链接文本
        try:
            import re
            result_content = original_content
            
            # 对每个链接进行翻译
            for link_info in links:
                original_text = link_info['text']
                url = link_info['url']
                
                # 在翻译结果中查找对应的翻译文本
                # 这里使用简单的替换策略，更复杂的场景可能需要更智能的匹配
                if original_text in translated_text:
                    # 找到翻译后的文本
                    # 注意：这是一个简化的实现，可能不适用于所有情况
                    translated_link_text = self._extract_translated_part(
                        translated_text, original_text, result_content
                    )
                    
                    # 替换原始链接中的文本
                    old_link = f"[{original_text}]({url})"
                    new_link = f"[{translated_link_text}]({url})"
                    result_content = result_content.replace(old_link, new_link, 1)
            
            return MarkdownElement(
                type=element.type,
                content=result_content,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
        except Exception as e:
            logger.warning(f"翻译链接元素失败，使用原始翻译结果: {str(e)}")
            return MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
    
    def _translate_image_element(self, element: MarkdownElement,
                               translated_text: str) -> MarkdownElement:
        """翻译图片元素"""
        # 解析原始内容中的图片
        images = element.metadata.get('images', [])
        original_content = element.content
        
        # 如果没有图片信息，直接返回翻译后的内容
        if not images:
            return MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
        
        # 尝试保持图片结构，只翻译alt文本
        try:
            import re
            result_content = original_content
            
            # 对每个图片进行翻译
            for img_info in images:
                original_alt = img_info['alt']
                url = img_info['url']
                
                # 在翻译结果中查找对应的翻译文本
                if original_alt in translated_text:
                    # 找到翻译后的alt文本
                    translated_alt = self._extract_translated_part(
                        translated_text, original_alt, result_content
                    )
                    
                    # 替换原始图片中的alt文本
                    old_img = f"![{original_alt}]({url})"
                    new_img = f"![{translated_alt}]({url})"
                    result_content = result_content.replace(old_img, new_img, 1)
            
            return MarkdownElement(
                type=element.type,
                content=result_content,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
        except Exception as e:
            logger.warning(f"翻译图片元素失败，使用原始翻译结果: {str(e)}")
            return MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
    
    def _extract_translated_part(self, translated_text: str, original_text: str,
                                context: str) -> str:
        """从翻译文本中提取对应部分的翻译"""
        # 这是一个简化的实现，尝试找到最相关的翻译部分
        # 在实际应用中，可能需要更复杂的匹配算法
        
        # 如果翻译文本中直接包含原始文本的翻译，直接返回
        if original_text in translated_text:
            # 简单情况：原始文本在翻译文本中完整出现
            start = translated_text.find(original_text)
            if start != -1:
                # 尝试提取周围的可能翻译部分
                # 这里使用启发式方法，提取相同长度的文本
                end = start + len(original_text)
                return translated_text[start:end]
        
        # 如果找不到直接匹配，尝试使用整个翻译文本
        # 这不是最优解，但可以确保不会失败
        return translated_text
    
    def _translate_wikilink_element(self, element: MarkdownElement,
                                   translated_text: str) -> MarkdownElement:
        """翻译wikilink元素"""
        # 获取原始内容和wikilink信息
        original_content = element.content
        wikilinks = element.metadata.get('wikilinks', [])
        non_wikilink_text = element.metadata.get('non_wikilink_text', '')
        
        # 如果没有wikilink信息，直接返回翻译后的内容
        if not wikilinks:
            return MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
        
        # 尝试保持wikilink结构，只翻译周围的文本
        try:
            result_content = original_content
            
            # 如果有非wikilink文本需要翻译
            if non_wikilink_text:
                # 在翻译结果中查找非wikilink文本的翻译
                # 这是一个简化的实现
                for wikilink_info in wikilinks:
                    original_wikilink = wikilink_info['original']
                    original_text = wikilink_info['text']
                    
                    # 在翻译文本中查找对应的翻译
                    if original_text in translated_text:
                        # 找到翻译后的文本
                        translated_part = self._extract_translated_part(
                            translated_text, original_text, result_content
                        )
                        
                        # 替换原始wikilink中的文本，但保持链接结构
                        # 注意：这里选择不翻译wikilink本身，只翻译周围文本
                        # 如果需要翻译wikilink显示文本，可以取消下面的注释
                        # new_wikilink = f"[[{translated_part}]]"
                        # result_content = result_content.replace(original_wikilink, new_wikilink, 1)
            
            return MarkdownElement(
                type=element.type,
                content=result_content,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
        except Exception as e:
            logger.warning(f"翻译wikilink元素失败，使用原始翻译结果: {str(e)}")
            return MarkdownElement(
                type=element.type,
                content=translated_text,
                translatable=element.translatable,
                metadata=element.metadata.copy()
            )
    
    def _translate_callout_element(self, element: MarkdownElement,
                                  translated_text: str) -> MarkdownElement:
        """翻译Callout元素"""
        callout_type = element.metadata.get('type', '')
        callout_title = element.metadata.get('title', '')
        original_lines = element.metadata.get('lines', [])
        
        # 如果没有标题，只有类型，直接替换内容
        if not callout_title:
            # 直接使用翻译后的内容
            translated_lines = translated_text.split('\n')
            # 确保每行都以>开头
            result_lines = []
            for line in translated_lines:
                if line.strip() and not line.strip().startswith('>'):
                    result_lines.append(f"> {line}")
                else:
                    result_lines.append(line)
            
            result_content = '\n'.join(result_lines)
        else:
            # 有标题的情况，需要保留类型，翻译标题和内容
            # 第一行是标题行
            first_line = original_lines[0]
            # 提取前缀和后缀
            prefix = first_line[:first_line.find('[')]
            suffix = first_line[first_line.find(']') + 1:] if ']' in first_line else ''
            
            # 翻译标题部分
            translated_title = self._extract_translated_part(translated_text, callout_title, first_line)
            
            # 重构标题行
            new_first_line = f"{prefix}[!{callout_type}]{suffix} {translated_title}" if suffix else f"{prefix}[!{callout_type}] {translated_title}"
            
            # 处理内容行
            translated_content_lines = translated_text.split('\n')
            result_lines = [new_first_line]
            
            # 添加翻译后的内容行，保持>前缀
            for i, line in enumerate(translated_content_lines[1:], 1):
                if i < len(original_lines) - 1:  # 确保不超过原始行数
                    original_line = original_lines[i]
                    original_prefix = original_line[:original_line.find(' ') + 1] if ' ' in original_line else original_line
                    if line.strip() and not line.strip().startswith('>'):
                        result_lines.append(f"{original_prefix}{line}")
                    else:
                        result_lines.append(line)
            
            result_content = '\n'.join(result_lines)
        
        return MarkdownElement(
            type=element.type,
            content=result_content,
            translatable=element.translatable,
            metadata=element.metadata.copy()
        )
    
    def _translate_text_element(self, element: MarkdownElement,
                              translated_text: str) -> MarkdownElement:
        """翻译文本元素"""
        return MarkdownElement(
            type=element.type,
            content=translated_text,
            translatable=element.translatable,
            metadata=element.metadata.copy()
        )
    
    def extract_translatable_text(self, elements: List[MarkdownElement]) -> str:
        """
        从元素列表中提取可翻译的文本
        
        Args:
            elements: Markdown元素列表
            
        Returns:
            可翻译文本
        """
        texts = []
        for element in elements:
            if element.translatable:
                if element.type == 'header':
                    texts.append(element.metadata.get('text', ''))
                elif element.type == 'list_item':
                    texts.append(element.metadata.get('text', ''))
                elif element.type == 'text':
                    texts.append(element.content)
                # 其他类型暂时不处理
        
        return '\n\n'.join(texts)
    
    def get_statistics(self, elements: List[MarkdownElement]) -> Dict[str, int]:
        """
        获取元素统计信息
        
        Args:
            elements: Markdown元素列表
            
        Returns:
            统计信息字典
        """
        stats = {
            'total_elements': len(elements),
            'translatable_elements': 0,
            'non_translatable_elements': 0,
            'code_blocks': 0,
            'headers': 0,
            'list_items': 0,
            'links': 0,
            'images': 0,
            'wikilinks': 0,
            'tags': 0,
            'text_blocks': 0,
            'yaml_blocks': 0
        }
        
        for element in elements:
            if element.translatable:
                stats['translatable_elements'] += 1
            else:
                stats['non_translatable_elements'] += 1
            
            stats[f"{element.type}s"] = stats.get(f"{element.type}s", 0) + 1
        
        return stats