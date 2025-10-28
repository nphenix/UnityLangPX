"""
UnityLangPX 智能分块算法

实现语义感知的文本分块算法，特别处理Obsidian语法和控制代码，
确保不会破坏文档结构和功能。
"""

import re
import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .logger import get_logger

logger = get_logger(__name__)


class ContentType(Enum):
    """内容类型"""
    TEXT = "text"
    CODE_BLOCK = "code_block"
    INLINE_CODE = "inline_code"
    WIKILINK = "wikilink"
    TAG = "tag"
    FRONTMATTER = "frontmatter"
    CALLOUT = "callout"
    TABLE = "table"
    MATH = "math"
    HTML = "html"


@dataclass
class TextChunk:
    """文本块"""
    content: str
    content_type: ContentType
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any]
    should_translate: bool = True
    context: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ChunkConfig:
    """分块配置"""
    max_tokens: int = 4000
    min_tokens: int = 200
    overlap_tokens: int = 200
    respect_code_blocks: bool = True
    respect_obsidian_syntax: bool = True
    preserve_structure: bool = True
    language: str = "en"


class SmartChunker:
    """智能分块器"""
    
    def __init__(self, config: ChunkConfig):
        self.config = config
        
        # Obsidian语法模式
        self.obsidian_patterns = {
            'wikilink': re.compile(r'\[\[([^\]]+)\]\]'),
            'tag': re.compile(r'#([^\s#]+)'),
            'callout': re.compile(r'^>\s*\[!([^\]]+)\]\]', re.MULTILINE),
            'frontmatter': re.compile(r'^---\s*\n.*?\n---\s*\n', re.MULTILINE | re.DOTALL),
            'code_block': re.compile(r'```(\w*)\n(.*?)\n```', re.MULTILINE | re.DOTALL),
            'inline_code': re.compile(r'`([^`]+)`'),
            'math_block': re.compile(r'\$\$(.*?)\$\$', re.MULTILINE | re.DOTALL),
            'table': re.compile(r'^\|(.+)\|$', re.MULTILINE),
            'html_tag': re.compile(r'<[^>]+>.*?</[^>]+>', re.MULTILINE | re.DOTALL),
        }
        
        # 句子边界模式（支持多种语言）
        self.sentence_patterns = {
            'en': re.compile(r'(?<=[.!?])\s+'),
            'zh': re.compile(r'(?<=[。！？])\s*'),
            'ja': re.compile(r'(?<=[。！？])\s*'),
            'ko': re.compile(r'(?<=[.!?])\s+'),
            'default': re.compile(r'(?<=[.!?。！？])\s+')
        }
        
        # 段落边界模式
        self.paragraph_pattern = re.compile(r'\n\s*\n')
        
        logger.debug("智能分块器初始化完成")
    
    def chunk_text(self, text: str) -> List[TextChunk]:
        """
        智能分块文本
        
        Args:
            text: 待分块的文本
            
        Returns:
            文本块列表
        """
        logger.debug(f"开始智能分块，文本长度: {len(text)}")
        
        # 1. 解析文本结构
        segments = self._parse_text_structure(text)
        
        # 2. 合并相邻的可翻译内容
        merged_segments = self._merge_translatable_segments(segments)
        
        # 3. 按语义边界分块
        chunks = self._create_semantic_chunks(merged_segments)
        
        # 4. 优化分块大小
        optimized_chunks = self._optimize_chunk_sizes(chunks)
        
        logger.debug(f"分块完成，共 {len(optimized_chunks)} 个块")
        return optimized_chunks
    
    def _parse_text_structure(self, text: str) -> List[TextChunk]:
        """解析文本结构，识别不同类型的内容"""
        segments = []
        pos = 0
        
        while pos < len(text):
            # 查找下一个特殊内容
            next_special = self._find_next_special_content(text, pos)
            
            if next_special is None:
                # 剩余都是普通文本
                if pos < len(text):
                    segments.append(TextChunk(
                        content=text[pos:],
                        content_type=ContentType.TEXT,
                        start_pos=pos,
                        end_pos=len(text),
                        metadata={'source': 'tail_text'},
                        should_translate=True
                    ))
                break
            
            special_start, special_end, special_type, special_content = next_special
            
            # 添加特殊内容前的普通文本
            if special_start > pos:
                normal_text = text[pos:special_start]
                if normal_text.strip():
                    segments.append(TextChunk(
                        content=normal_text,
                        content_type=ContentType.TEXT,
                        start_pos=pos,
                        end_pos=special_start,
                        metadata={'source': 'normal_text'},
                        should_translate=True
                    ))
            
            # 添加特殊内容
            should_translate = self._should_translate_content(special_type, special_content)
            segments.append(TextChunk(
                content=special_content,
                content_type=special_type,
                start_pos=special_start,
                end_pos=special_end,
                metadata={
                    'source': 'special_content',
                    'pattern_type': special_type.name
                },
                should_translate=should_translate
            ))
            
            pos = special_end
        
        return segments
    
    def _find_next_special_content(self, text: str, start_pos: int) -> Optional[Tuple[int, int, ContentType, str]]:
        """查找下一个特殊内容"""
        next_match = None
        
        # 检查所有模式
        for content_type, pattern in self.obsidian_patterns.items():
            match = pattern.search(text, start_pos)
            if match:
                match_start, match_end = match.span()
                # 对于代码块，使用整个匹配
                if content_type == 'code_block':
                    match_content = match.group(0)
                else:
                    match_content = match.group(0)
                
                if next_match is None or match_start < next_match[0]:
                    next_match = (match_start, match_end, ContentType[content_type.upper()], match_content)
        
        return next_match
    
    def _should_translate_content(self, content_type: ContentType, content: str) -> bool:
        """判断内容是否应该翻译"""
        # 不翻译的内容类型
        non_translatable_types = {
            ContentType.CODE_BLOCK,
            ContentType.INLINE_CODE,
            ContentType.FRONTMATTER,
            ContentType.MATH,
            ContentType.HTML
        }
        
        if content_type in non_translatable_types:
            return False
        
        # 特殊处理某些类型
        if content_type == ContentType.WIKILINK:
            # 只翻译wikilink的显示文本，不翻译链接本身
            # 例如：[[中文翻译|English Translation]] -> 只翻译"中文翻译"
            if '|' in content:
                display_text = content.split('|')[0].strip('[]')
                return display_text and not display_text.startswith('#')
            return False
        
        if content_type == ContentType.TAG:
            # 标签不翻译
            return False
        
        if content_type == ContentType.CALLOUT:
            # Callout的类型不翻译，但内容可能翻译
            # 这里标记为需要进一步处理
            return True
        
        if content_type == ContentType.TABLE:
            # 表格内容可能翻译，但需要特殊处理
            return True
        
        return True
    
    def _merge_translatable_segments(self, segments: List[TextChunk]) -> List[TextChunk]:
        """合并相邻的可翻译内容"""
        if not self.config.preserve_structure:
            return segments
        
        merged = []
        current_merge = None
        
        for segment in segments:
            if not segment.should_translate:
                # 不可翻译的内容直接添加
                if current_merge:
                    merged.append(current_merge)
                    current_merge = None
                merged.append(segment)
            else:
                # 可翻译的内容尝试合并
                if current_merge is None:
                    current_merge = segment
                else:
                    # 检查是否可以合并
                    if self._can_merge_segments(current_merge, segment):
                        current_merge = self._merge_two_segments(current_merge, segment)
                    else:
                        merged.append(current_merge)
                        current_merge = segment
        
        # 添加最后一个合并块
        if current_merge:
            merged.append(current_merge)
        
        return merged
    
    def _can_merge_segments(self, seg1: TextChunk, seg2: TextChunk) -> bool:
        """判断两个段是否可以合并"""
        # 检查类型兼容性
        if seg1.content_type != ContentType.TEXT or seg2.content_type != ContentType.TEXT:
            return False
        
        # 检查合并后的令牌数
        combined_content = seg1.content + seg2.content
        estimated_tokens = self._estimate_tokens(combined_content)
        
        return estimated_tokens <= self.config.max_tokens
    
    def _merge_two_segments(self, seg1: TextChunk, seg2: TextChunk) -> TextChunk:
        """合并两个段"""
        return TextChunk(
            content=seg1.content + seg2.content,
            content_type=ContentType.TEXT,
            start_pos=seg1.start_pos,
            end_pos=seg2.end_pos,
            metadata={
                'source': 'merged_text',
                'original_count': 2
            },
            should_translate=True
        )
    
    def _create_semantic_chunks(self, segments: List[TextChunk]) -> List[TextChunk]:
        """按语义边界创建块"""
        chunks = []
        
        for segment in segments:
            if not segment.should_translate:
                # 不可翻译的内容直接作为块
                chunks.append(segment)
                continue
            
            # 对可翻译内容进行语义分块
            if segment.content_type == ContentType.TEXT:
                text_chunks = self._chunk_text_semantically(segment.content)
                for i, text_chunk in enumerate(text_chunks):
                    chunks.append(TextChunk(
                        content=text_chunk,
                        content_type=ContentType.TEXT,
                        start_pos=segment.start_pos,
                        end_pos=segment.start_pos + len(text_chunk),
                        metadata={
                            **segment.metadata,
                            'chunk_index': i,
                            'source': 'semantic_chunk'
                        },
                        should_translate=True
                    ))
            else:
                # 其他类型的可翻译内容直接作为块
                chunks.append(segment)
        
        return chunks
    
    def _chunk_text_semantically(self, text: str) -> List[str]:
        """语义分块文本"""
        if not text.strip():
            return []
        
        # 估算令牌数
        estimated_tokens = self._estimate_tokens(text)
        
        if estimated_tokens <= self.config.max_tokens:
            return [text]
        
        chunks = []
        
        # 1. 首先尝试按段落分割
        paragraphs = self.paragraph_pattern.split(text)
        
        current_chunk = ""
        current_tokens = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            paragraph_tokens = self._estimate_tokens(paragraph)
            
            # 检查添加这个段落后是否会超限
            if current_tokens + paragraph_tokens <= self.config.max_tokens:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                current_tokens += paragraph_tokens
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 如果单个段落就超限，需要进一步分割
                if paragraph_tokens > self.config.max_tokens:
                    sub_chunks = self._chunk_long_paragraph(paragraph)
                    chunks.extend(sub_chunks[:-1])  # 除了最后一个
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                    current_tokens = self._estimate_tokens(current_chunk)
                else:
                    current_chunk = paragraph
                    current_tokens = paragraph_tokens
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _chunk_long_paragraph(self, paragraph: str) -> List[str]:
        """分块过长的段落"""
        chunks = []
        
        # 2. 尝试按句子分割
        sentence_pattern = self.sentence_patterns.get(
            self.config.language, 
            self.sentence_patterns['default']
        )
        
        sentences = sentence_pattern.split(paragraph)
        
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_tokens = self._estimate_tokens(sentence)
            
            # 检查是否可以添加到当前块
            if current_tokens + sentence_tokens <= self.config.max_tokens:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_tokens += sentence_tokens
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 如果单个句子就超限，强制分割
                if sentence_tokens > self.config.max_tokens:
                    forced_chunks = self._force_chunk_text(sentence)
                    chunks.extend(forced_chunks[:-1])
                    current_chunk = forced_chunks[-1] if forced_chunks else ""
                    current_tokens = self._estimate_tokens(current_chunk)
                else:
                    current_chunk = sentence
                    current_tokens = sentence_tokens
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _force_chunk_text(self, text: str) -> List[str]:
        """强制分块文本（按字符数）"""
        chunks = []
        max_chars = int(self.config.max_tokens * 1.5)  # 粗略估算
        
        for i in range(0, len(text), max_chars):
            chunk = text[i:i + max_chars]
            chunks.append(chunk)
        
        return chunks
    
    def _optimize_chunk_sizes(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """优化块大小，添加重叠"""
        if not self.config.overlap_tokens or len(chunks) <= 1:
            return chunks
        
        optimized = []
        
        for i, chunk in enumerate(chunks):
            if not chunk.should_translate:
                optimized.append(chunk)
                continue
            
            # 为可翻译的块添加重叠
            if i > 0:
                # 查找前一个可翻译的块
                prev_translatable = None
                for j in range(i - 1, -1, -1):
                    if chunks[j].should_translate:
                        prev_translatable = chunks[j]
                        break
                
                if prev_translatable:
                    # 添加前一个块的尾部作为上下文
                    prev_content = prev_translatable.content
                    overlap_size = min(
                        self.config.overlap_tokens,
                        len(prev_content) // 4  # 最多取前一个块的1/4
                    )
                    
                    if overlap_size > 0:
                        # 按词或字符边界截取
                        overlap_text = self._extract_overlap(prev_content, overlap_size)
                        chunk.content = overlap_text + chunk.content
                        chunk.metadata['has_overlap'] = True
                        chunk.metadata['overlap_size'] = overlap_size
                        chunk.metadata['overlap_source'] = prev_translatable.start_pos
            
            optimized.append(chunk)
        
        return optimized
    
    def _extract_overlap(self, text: str, size: int) -> str:
        """提取重叠文本，尽量保持语义完整"""
        if size >= len(text):
            return text
        
        # 尝试在词边界截取
        words = text.split()
        overlap_words = []
        current_length = 0
        
        for word in reversed(words):
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length <= size:
                overlap_words.insert(0, word)
                current_length += word_length
            else:
                break
        
        overlap_text = ' '.join(overlap_words)
        
        # 如果重叠文本太短，直接截取
        if len(overlap_text) < size // 2:
            overlap_text = text[-size:]
        
        return overlap_text
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的令牌数"""
        if not text:
            return 0
        
        # 根据语言使用不同的估算方法
        if self.config.language in ["zh", "ja", "ko"]:
            # 中文、日文、韩文等亚洲语言
            return len(text) * 2  # 粗略估算
        else:
            # 英文等拉丁语言
            # 平均1.3个字符 = 1个令牌
            return int(len(text) / 1.3)
    
    def get_chunk_statistics(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """获取分块统计信息"""
        if not chunks:
            return {
                'total_chunks': 0,
                'translatable_chunks': 0,
                'non_translatable_chunks': 0,
                'total_tokens': 0,
                'avg_tokens_per_chunk': 0,
                'content_types': {}
            }
        
        total_chunks = len(chunks)
        translatable_chunks = sum(1 for c in chunks if c.should_translate)
        non_translatable_chunks = total_chunks - translatable_chunks
        
        total_tokens = sum(self._estimate_tokens(c.content) for c in chunks)
        avg_tokens = total_tokens / total_chunks if total_chunks > 0 else 0
        
        # 统计内容类型
        content_types = {}
        for chunk in chunks:
            type_name = chunk.content_type.value
            content_types[type_name] = content_types.get(type_name, 0) + 1
        
        return {
            'total_chunks': total_chunks,
            'translatable_chunks': translatable_chunks,
            'non_translatable_chunks': non_translatable_chunks,
            'total_tokens': total_tokens,
            'avg_tokens_per_chunk': avg_tokens,
            'content_types': content_types,
            'max_chunk_tokens': max(self._estimate_tokens(c.content) for c in chunks),
            'min_chunk_tokens': min(self._estimate_tokens(c.content) for c in chunks)
        }


# 便捷函数
def create_smart_chunker(
    max_tokens: int = 4000,
    language: str = "en",
    respect_obsidian_syntax: bool = True
) -> SmartChunker:
    """创建智能分块器实例"""
    config = ChunkConfig(
        max_tokens=max_tokens,
        language=language,
        respect_obsidian_syntax=respect_obsidian_syntax
    )
    return SmartChunker(config)