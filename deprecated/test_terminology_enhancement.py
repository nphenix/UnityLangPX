"""
UnityLangPX 术语增强功能单元测试

测试术语增强服务的各项功能，包括上下文感知翻译、模糊匹配增强、
多义词消歧和复杂场景处理等。
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.core.terminology_enhancement import (
    TerminologyEnhancementService, 
    EnhancementResult, 
    FuzzyMatchResult
)
from src.core.terminology import TraditionalTerminologyStore, TerminologyEntry
from src.core.models.base import ModelClient


class TestTerminologyEnhancementService(unittest.TestCase):
    """术语增强服务测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟模型客户端
        self.mock_model_client = Mock(spec=ModelClient)
        
        # 创建模拟配置
        self.mock_config = Mock()
        self.mock_config.context_window_size = 200
        self.mock_config.max_cache_size = 1000
        self.mock_config.fuzzy_threshold = 0.7
        
        # 创建术语增强服务
        self.enhancement_service = TerminologyEnhancementService(
            self.mock_model_client, 
            self.mock_config
        )
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = "算法"
    
    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.enhancement_service.model_client)
        self.assertIsNotNone(self.enhancement_service.config)
        self.assertIsNotNone(self.enhancement_service.traditional_store)
        self.assertEqual(self.enhancement_service.context_window_size, 200)
        self.assertEqual(self.enhancement_service.fuzzy_threshold, 0.7)
    
    def test_enhance_term_translation(self):
        """测试上下文感知术语翻译"""
        # 准备测试数据
        term = "algorithm"
        context = "The algorithm efficiently processes large datasets."
        source_lang = "en"
        target_lang = "zh"
        
        # 执行测试
        result = self.enhancement_service.enhance_term_translation(
            term, context, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, term)
        self.assertEqual(result.enhancement_translation, "算法")
        self.assertEqual(result.enhancement_type, "context_aware")
        self.assertGreater(result.confidence, 0)
        self.assertGreater(result.processing_time, 0)
        
        # 验证模型客户端被调用
        self.mock_model_client.generate.assert_called_once()
    
    def test_enhance_term_translation_with_cache(self):
        """测试上下文感知术语翻译缓存"""
        # 准备测试数据
        term = "algorithm"
        context = "The algorithm efficiently processes large datasets."
        source_lang = "en"
        target_lang = "zh"
        
        # 第一次调用
        result1 = self.enhancement_service.enhance_term_translation(
            term, context, source_lang, target_lang
        )
        
        # 第二次调用（应该使用缓存）
        result2 = self.enhancement_service.enhance_term_translation(
            term, context, source_lang, target_lang
        )
        
        # 验证结果
        self.assertEqual(result1.original_term, result2.original_term)
        self.assertEqual(result1.enhanced_translation, result2.enhanced_translation)
        
        # 验证模型客户端只被调用一次
        self.assertEqual(self.mock_model_client.generate.call_count, 1)
    
    def test_enhance_fuzzy_matching(self):
        """测试模糊匹配增强"""
        # 准备测试数据
        text = "The new algorithim shows promise."
        potential_terms = ["algorithm", "algorithms", "method"]
        source_lang = "en"
        target_lang = "zh"
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = "algorithm:0.9"
        
        # 执行测试
        results = self.enhancement_service.enhance_fuzzy_matching(
            text, potential_terms, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        for result in results:
            self.assertIsInstance(result, FuzzyMatchResult)
            self.assertIn(result.term, potential_terms)
            self.assertGreaterEqual(result.confidence, 0)
            self.assertLessEqual(result.confidence, 1)
            self.assertIsInstance(result.match_type, str)
    
    def test_enhance_fuzzy_matching_exact_match(self):
        """测试模糊匹配精确匹配"""
        # 准备测试数据
        text = "The algorithm processes data."
        potential_terms = ["algorithm", "method"]
        source_lang = "en"
        target_lang = "zh"
        
        # 执行测试
        results = self.enhancement_service.enhance_fuzzy_matching(
            text, potential_terms, source_lang, target_lang
        )
        
        # 验证结果
        self.assertGreater(len(results), 0)
        
        # 查找精确匹配
        exact_matches = [r for r in results if r.match_type == "exact"]
        self.assertGreater(len(exact_matches), 0)
        self.assertEqual(exact_matches[0].term, "algorithm")
        self.assertEqual(exact_matches[0].confidence, 1.0)
    
    def test_disambiguate_term(self):
        """测试术语消歧"""
        # 准备测试数据
        term = "light"
        context = "The light in the room is too bright."
        source_lang = "en"
        target_lang = "zh"
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = "灯光"
        
        # 执行测试
        result = self.enhancement_service.disambiguate_term(
            term, context, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, term)
        self.assertEqual(result.enhanced_translation, "灯光")
        self.assertEqual(result.enhancement_type, "disambiguation")
        self.assertGreater(result.confidence, 0)
        
        # 验证模型客户端被调用
        self.mock_model_client.generate.assert_called()
    
    def test_disambiguate_non_polysemous_term(self):
        """测试非多义词消歧"""
        # 准备测试数据
        term = "algorithm"
        context = "The algorithm processes data."
        source_lang = "en"
        target_lang = "zh"
        
        # 执行测试
        result = self.enhancement_service.disambiguate_term(
            term, context, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, term)
        self.assertEqual(result.enhancement_type, "disambiguation")
        self.assertFalse(result.metadata.get('polysemous', True))
    
    def test_handle_complex_scenario(self):
        """测试复杂场景处理"""
        # 准备测试数据
        text = "The title <title>Artificial Intelligence</title> discusses AI."
        source_lang = "en"
        target_lang = "zh"
        
        # 设置模拟响应
        self.mock_model_client.translate_text.return_value = "标题 <title>人工智能</title> 讨论AI。"
        
        # 执行测试
        result = self.enhancement_service.handle_complex_scenario(
            text, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, text)
        self.assertEqual(result.enhancement_type, "complex_scenario")
        self.assertIn("<title>", result.enhanced_translation)
        self.assertIn("</title>", result.enhanced_translation)
    
    def test_handle_complex_scenario_no_complex_elements(self):
        """测试无复杂元素的复杂场景处理"""
        # 准备测试数据
        text = "This is a simple text."
        source_lang = "en"
        target_lang = "zh"
        
        # 执行测试
        result = self.enhancement_service.handle_complex_scenario(
            text, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, text)
        self.assertEqual(result.enhanced_translation, text)
        self.assertEqual(result.enhancement_type, "complex_scenario")
        self.assertFalse(result.metadata.get('complex_elements', False))
    
    def test_should_use_enhancement(self):
        """测试是否应该使用增强功能"""
        # 测试复杂场景
        complex_text = "The <code>algorithm</code> processes data."
        traditional_matches = []
        self.assertTrue(
            self.enhancement_service.should_use_enhancement(
                complex_text, traditional_matches
            )
        )
        
        # 测试简单场景
        simple_text = "This is simple."
        self.assertFalse(
            self.enhancement_service.should_use_enhancement(
                simple_text, traditional_matches
            )
        )
        
        # 测试高匹配率场景
        high_matches = [("term", "translation")]
        self.assertFalse(
            self.enhancement_service.should_use_enhancement(
                simple_text, high_matches
            )
        )
    
    def test_build_context_prompt(self):
        """测试构建上下文提示词"""
        term = "algorithm"
        context = "The algorithm processes data."
        source_lang = "en"
        target_lang = "zh"
        
        # 执行测试
        prompt = self.enhancement_service._build_context_prompt(
            term, context, source_lang, target_lang
        )
        
        # 验证结果
        self.assertIn(term, prompt)
        self.assertIn(context, prompt)
        self.assertIn(source_lang, prompt)
        self.assertIn(target_lang, prompt)
    
    def test_extract_translation_from_response(self):
        """测试从响应中提取翻译结果"""
        # 测试正常响应
        response = "算法"
        result = self.enhancement_service._extract_translation_from_response(response)
        self.assertEqual(result, "算法")
        
        # 测试多行响应
        response = "一些解释\n翻译：算法\n更多解释"
        result = self.enhancement_service._extract_translation_from_response(response)
        self.assertEqual(result, "翻译：算法")
    
    def test_calculate_confidence(self):
        """测试计算置信度"""
        response = "算法"
        term = "algorithm"
        context = "The algorithm processes data."
        
        # 执行测试
        confidence = self.enhancement_service._calculate_confidence(response, term, context)
        
        # 验证结果
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)
    
    def test_calculate_edit_distance(self):
        """测试计算编辑距离"""
        # 测试相同字符串
        distance = self.enhancement_service._calculate_edit_distance("algorithm", "algorithm")
        self.assertEqual(distance, 0)
        
        # 测试不同字符串
        distance = self.enhancement_service._calculate_edit_distance("algorithm", "algorith")
        self.assertEqual(distance, 1)
        
        # 测试空字符串
        distance = self.enhancement_service._calculate_edit_distance("", "algorithm")
        self.assertEqual(distance, len("algorithm"))
    
    def test_find_edit_distance_matches(self):
        """测试查找编辑距离匹配"""
        text = "The algorithim processes data."
        potential_terms = ["algorithm", "method"]
        
        # 执行测试
        matches = self.enhancement_service._find_edit_distance_matches(text, potential_terms)
        
        # 验证结果
        self.assertIsInstance(matches, list)
        if matches:
            for match, score in matches:
                self.assertIsInstance(match, str)
                self.assertIsInstance(score, float)
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 1)
    
    def test_find_abbreviation_matches(self):
        """测试查找缩写匹配"""
        text = "The AI processes data."
        potential_terms = ["Artificial Intelligence", "Machine Learning"]
        
        # 执行测试
        matches = self.enhancement_service._find_abbreviation_matches(text, potential_terms)
        
        # 验证结果
        self.assertIsInstance(matches, list)
        if matches:
            for match, score in matches:
                self.assertIsInstance(match, str)
                self.assertIsInstance(score, float)
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 1)
    
    def test_find_morphological_matches(self):
        """测试查找词形变化匹配"""
        text = "The running algorithm processes data."
        potential_terms = ["run", "algorithm"]
        source_lang = "en"
        
        # 执行测试
        matches = self.enhancement_service._find_morphological_matches(
            text, potential_terms, source_lang
        )
        
        # 验证结果
        self.assertIsInstance(matches, list)
        if matches:
            for match, score in matches:
                self.assertIsInstance(match, str)
                self.assertIsInstance(score, float)
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 1)
    
    def test_detect_complex_elements(self):
        """测试检测复杂元素"""
        # 测试HTML标签
        text = "The <title>AI</title> is important."
        elements = self.enhancement_service._detect_complex_elements(text)
        self.assertGreater(len(elements), 0)
        self.assertEqual(elements[0]['type'], 'html')
        
        # 测试代码片段
        text = "Use `algorithm` to process data."
        elements = self.enhancement_service._detect_complex_elements(text)
        self.assertGreater(len(elements), 0)
        self.assertEqual(elements[0]['type'], 'code')
        
        # 测试无复杂元素
        text = "This is simple text."
        elements = self.enhancement_service._detect_complex_elements(text)
        self.assertEqual(len(elements), 0)
    
    def test_isolate_elements(self):
        """测试隔离元素"""
        text = "The <title>AI</title> is important."
        complex_elements = [
            {'type': 'html', 'content': '<title>AI</title>', 'start': 4, 'end': 18}
        ]
        
        # 执行测试
        isolated = self.enhancement_service._isolate_elements(text, complex_elements)
        
        # 验证结果
        self.assertEqual(len(isolated), 3)
        self.assertEqual(isolated[0]['type'], 'text')
        self.assertEqual(isolated[0]['content'], "The ")
        self.assertEqual(isolated[1]['type'], 'html')
        self.assertEqual(isolated[2]['type'], 'text')
        self.assertEqual(isolated[2]['content'], " is important.")
    
    def test_merge_processed_elements(self):
        """测试合并处理后的元素"""
        elements = [
            {'type': 'text', 'content': "The "},
            {'type': 'html', 'content': '<title>AI</title>'},
            {'type': 'text', 'content': " is important."}
        ]
        
        # 执行测试
        result = self.enhancement_service._merge_processed_elements(elements)
        
        # 验证结果
        self.assertEqual(result, "The <title>AI</title> is important.")
    
    def test_analyze_text_complexity(self):
        """测试分析文本复杂度"""
        # 测试简单文本
        simple_text = "This is simple."
        complexity = self.enhancement_service._analyze_text_complexity(simple_text)
        self.assertGreaterEqual(complexity, 0)
        self.assertLessEqual(complexity, 1)
        
        # 测试复杂文本
        complex_text = "The <code>algorithm</code> processes data; it's very complex."
        complexity = self.enhancement_service._analyze_text_complexity(complex_text)
        self.assertGreater(complexity, 0.1)  # 应该比简单文本复杂
    
    @patch('src.core.terminology_enhancement.TerminologyEnhancementService._build_context_prompt')
    def test_enhance_term_translation_error_handling(self, mock_build_prompt):
        """测试上下文感知术语翻译错误处理"""
        # 设置模拟异常
        self.mock_model_client.generate.side_effect = Exception("模型错误")
        mock_build_prompt.return_value = "模拟提示词"
        
        # 执行测试
        result = self.enhancement_service.enhance_term_translation(
            "algorithm", "context", "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, "algorithm")
        self.assertEqual(result.enhanced_translation, "algorithm")  # 降级到原文
        self.assertEqual(result.enhancement_type, "context_aware")
        self.assertIn('error', result.metadata)


class TestFuzzyMatchResult(unittest.TestCase):
    """模糊匹配结果测试"""
    
    def test_init(self):
        """测试初始化"""
        result = FuzzyMatchResult(
            term="algorithm",
            confidence=0.9,
            match_type="exact"
        )
        
        self.assertEqual(result.term, "algorithm")
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.match_type, "exact")
    
    def test_equality(self):
        """测试相等性"""
        result1 = FuzzyMatchResult("algorithm", 0.9, "exact")
        result2 = FuzzyMatchResult("algorithm", 0.9, "exact")
        result3 = FuzzyMatchResult("method", 0.9, "exact")
        
        # 由于没有实现__eq__，这里测试属性相等
        self.assertEqual(result1.term, result2.term)
        self.assertEqual(result1.confidence, result2.confidence)
        self.assertEqual(result1.match_type, result2.match_type)
        
        self.assertNotEqual(result1.term, result3.term)


class TestEnhancementResult(unittest.TestCase):
    """增强结果测试"""
    
    def test_init(self):
        """测试初始化"""
        result = EnhancementResult(
            original_term="algorithm",
            enhanced_translation="算法",
            confidence=0.9,
            enhancement_type="context_aware",
            processing_time=0.1,
            metadata={}
        )
        
        self.assertEqual(result.original_term, "algorithm")
        self.assertEqual(result.enhanced_translation, "算法")
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.enhancement_type, "context_aware")
        self.assertEqual(result.processing_time, 0.1)
        self.assertIsInstance(result.metadata, dict)


if __name__ == '__main__':
    unittest.main()