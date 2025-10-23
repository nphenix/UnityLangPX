"""
UnityLangPX OpenAI兼容API模型客户端实现

支持OpenAI API及兼容的API服务，实现统一的ModelClient接口。
"""

import time
from typing import Optional, Dict, Any, List

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

from .base import ModelClient
from ..exceptions import APIConnectionError, ModelNotFoundError, TranslationError
from ..logger import get_logger

logger = get_logger(__name__)


class OpenAIModelClient(ModelClient):
    """OpenAI兼容API模型客户端实现"""
    
    def __init__(self, config):
        """
        初始化OpenAI模型客户端
        
        Args:
            config: OpenAI配置对象
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI库未安装，请运行: pip install openai")
        
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout
        )
        self.model = config.model
        logger.debug(f"初始化OpenAI模型客户端: {config.base_url}")
    
    def check_connection(self) -> bool:
        """检查API服务连接是否正常"""
        try:
            # 尝试获取模型列表验证连接
            self.client.models.list()
            logger.debug("OpenAI兼容API连接成功")
            return True
        except Exception as e:
            logger.error(f"OpenAI兼容API连接失败: {str(e)}")
            raise APIConnectionError(f"无法连接到OpenAI兼容API: {str(e)}")
    
    def check_model(self) -> bool:
        """检查指定模型是否可用"""
        try:
            models = self.client.models.list()
            model_names = [model.id for model in models.data]
            
            if self.model not in model_names:
                available_models = ", ".join(model_names[:10])  # 只显示前10个
                if len(model_names) > 10:
                    available_models += f" (共{len(model_names)}个)"
                
                logger.warning(f"模型 {self.model} 不可用，可用模型: {available_models}")
                raise ModelNotFoundError(
                    f"模型 {self.model} 不可用，可用模型: {available_models}"
                )
            
            logger.debug(f"模型 {self.model} 可用")
            return True
        except Exception as e:
            logger.error(f"检查OpenAI模型失败: {str(e)}")
            if isinstance(e, (APIConnectionError, ModelNotFoundError)):
                raise
            raise APIConnectionError(f"检查模型失败: {str(e)}")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有可用模型"""
        try:
            models = self.client.models.list()
            result = [{"id": model.id, "created": model.created} for model in models.data]
            logger.debug(f"获取到 {len(result)} 个OpenAI兼容模型")
            return result
        except Exception as e:
            logger.error(f"获取OpenAI模型列表失败: {str(e)}")
            raise APIConnectionError(f"获取模型列表失败: {str(e)}")
    
    def translate_text(self, text: str, context: Optional[str] = None,
                      source_lang: str = "en", target_lang: str = "zh",
                      temperature: float = 0.1) -> str:
        """翻译文本"""
        system_prompt = self._build_translation_system_prompt(source_lang, target_lang)
        user_prompt = self._build_translation_prompt(text, context, source_lang, target_lang)
        
        try:
            logger.debug(f"使用OpenAI兼容API翻译文本，长度: {len(text)}")
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=self.config.max_tokens or 4000
            )
            
            duration = time.time() - start_time
            result = response.choices[0].message.content
            
            if not result:
                raise TranslationError("翻译结果为空")
            
            logger.debug(f"OpenAI翻译完成，耗时: {duration:.2f}秒，结果长度: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI翻译失败: {str(e)}")
            if isinstance(e, (APIConnectionError, ModelNotFoundError, TranslationError)):
                raise
            raise TranslationError(f"翻译失败: {str(e)}")
    
    def _build_translation_system_prompt(self, source_lang: str, target_lang: str) -> str:
        """构建翻译系统提示"""
        lang_map = {
            "en": "英文",
            "zh": "中文",
            "ja": "日文",
            "ko": "韩文",
            "fr": "法文",
            "de": "德文",
            "es": "西班牙文",
            "ru": "俄文"
        }
        
        source_name = lang_map.get(source_lang, source_lang)
        target_name = lang_map.get(target_lang, target_lang)
        
        return f"""你是一个专业的{source_name}到{target_name}翻译助手，专门负责翻译技术文档和Markdown文件。

请遵循以下规则：
1. 保持原文的Markdown格式不变
2. 只翻译需要翻译的内容，保留代码块、链接URL、图片路径等不变
3. 对于技术术语，保持一致性
4. 翻译要准确、自然、符合{target_name}表达习惯
5. 对于Obsidian特有的语法（如[[wikilinks]]、#tags），适当处理但不破坏其功能
6. 如果遇到不确定的术语，可以保留原文并添加注释"""
    
    def _build_translation_prompt(self, text: str, context: Optional[str],
                                source_lang: str, target_lang: str) -> str:
        """构建翻译用户提示"""
        lang_map = {
            "en": "英文",
            "zh": "中文",
            "ja": "日文",
            "ko": "韩文",
            "fr": "法文",
            "de": "德文",
            "es": "西班牙文",
            "ru": "俄文"
        }
        
        source_name = lang_map.get(source_lang, source_lang)
        target_name = lang_map.get(target_lang, target_lang)
        
        prompt = f"请将以下{source_name}内容翻译成{target_name}：\n\n{text}"
        
        if context:
            prompt = f"上下文信息：{context}\n\n{prompt}"
        
        return prompt
    
    def close(self):
        """关闭客户端连接"""
        # OpenAI客户端不需要显式关闭
        logger.debug("OpenAI模型客户端已关闭")