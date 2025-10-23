"""
UnityLangPX 增强型术语库功能验证测试

基于testjson.js和testmd.md的测试数据，验证增强型术语库的各项功能，
包括上下文感知翻译、模糊匹配增强、多义词消歧和复杂场景处理等。
"""

import unittest
import json
import time
import re
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.terminology_enhancement import (
    TerminologyEnhancementService, 
    EnhancementResult, 
    FuzzyMatchResult
)
from src.core.hybrid_decision_engine import (
    HybridDecisionEngine,
    DecisionResult,
    ProcessingStrategy
)
from src.core.models.enhanced_factory import EnhancedModelClientFactory
from src.core.terminology import TraditionalTerminologyStore, TerminologyEntry
from src.core.models.base import ModelClient


class TestEnhancedTerminologyValidation(unittest.TestCase):
    """增强型术语库功能验证测试"""
    
    @classmethod
    def setUpClass(cls):
        """类级别的测试前准备"""
        # 加载测试数据
        test_data_dir = Path(__file__).parent
        
        # 加载术语库数据
        with open(test_data_dir / "testjson.js", "r", encoding="utf-8") as f:
            content = f.read()
            # 尝试解析JSON，处理可能的JavaScript变量声明
            try:
                # 查找JSON对象的开始和结束
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_content = content[start_idx:end_idx]
                    cls.terminology_data = json.loads(json_content)
                else:
                    # 如果找不到JSON对象，创建一个简单的测试数据
                    cls.terminology_data = {
                        "terms": [
                            {
                                "source_term": "algorithm",
                                "target_translations": {"zh-CN": "算法"},
                                "domain": "计算机科学"
                            },
                            {
                                "source_term": "myocardial infarction",
                                "target_translations": {"zh-CN": "心肌梗死"},
                                "domain": "医学"
                            },
                            {
                                "source_term": "quantitative easing",
                                "target_translations": {"zh-CN": "量化宽松"},
                                "domain": "金融"
                            }
                        ]
                    }
            except json.JSONDecodeError:
                # 如果解析失败，创建一个简单的测试数据
                cls.terminology_data = {
                    "terms": [
                        {
                            "source_term": "algorithm",
                            "target_translations": {"zh-CN": "算法"},
                            "domain": "计算机科学"
                        },
                        {
                            "source_term": "myocardial infarction",
                            "target_translations": {"zh-CN": "心肌梗死"},
                            "domain": "医学"
                        },
                        {
                            "source_term": "quantitative easing",
                            "target_translations": {"zh-CN": "量化宽松"},
                            "domain": "金融"
                        }
                    ]
                }
        
        # 加载测试文本
        with open(test_data_dir / "testmd.md", "r", encoding="utf-8") as f:
            cls.test_texts = f.read()
        
        # 提取术语列表
        cls.terms = [term["source_term"] for term in cls.terminology_data["terms"]]
    
    def setUp(self):
        """每个测试方法前的准备"""
        # 创建模拟模型客户端
        self.mock_model_client = Mock(spec=ModelClient)
        self.mock_model_client.generate = Mock()
        self.mock_model_client.translate_text = Mock()
        
        # 创建模拟配置
        self.mock_config = Mock()
        self.mock_config.context_window_size = 200
        self.mock_config.max_cache_size = 1000
        self.mock_config.fuzzy_threshold = 0.7
        self.mock_config.complexity_threshold = 0.7
        self.mock_config.traditional_threshold = 0.8
        self.mock_config.enhancement_threshold = 0.5
        self.mock_config.fallback_enabled = True
        
        # 创建术语增强服务
        self.enhancement_service = TerminologyEnhancementService(
            self.mock_model_client, 
            self.mock_config
        )
        
        # 创建混合决策引擎
        self.decision_engine = HybridDecisionEngine(
            self.mock_config,
            self.enhancement_service
        )
        
        # 创建增强型工厂
        self.enhanced_factory = EnhancedModelClientFactory()
    
    def test_context_aware_translation_accuracy(self):
        """测试上下文感知翻译准确性"""
        # 测试用例1：algorithm在技术上下文中的翻译
        term = "algorithm"
        context = "The optimization of this **algorithm** significantly improves data processing efficiency."
        expected_translation = "算法"
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = expected_translation
        
        # 执行测试
        result = self.enhancement_service.enhance_term_translation(
            term, context, "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, term)
        self.assertEqual(result.enhanced_translation, expected_translation)
        self.assertEqual(result.enhancement_type, "context_aware")
        self.assertGreater(result.confidence, 0.7)
        
        # 验证模型客户端被正确调用
        self.mock_model_client.generate.assert_called_once()
        call_args = self.mock_model_client.generate.call_args
        self.assertIn(term, call_args[1]["prompt"])
        self.assertIn(context, call_args[1]["prompt"])
    
    def test_medical_terminology_translation(self):
        """测试医学术语翻译"""
        # 测试用例：myocardial infarction
        term = "myocardial infarction"
        context = "Patients with a history of **myocardial infarction** require long-term monitoring."
        expected_translation = "心肌梗死"
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = expected_translation
        
        # 执行测试
        result = self.enhancement_service.enhance_term_translation(
            term, context, "en", "zh"
        )
        
        # 验证结果
        self.assertEqual(result.enhanced_translation, expected_translation)
        self.assertGreater(result.confidence, 0.8)  # 医学术语应该有高置信度
    
    def test_financial_terminology_translation(self):
        """测试金融术语翻译"""
        # 测试用例：quantitative easing
        term = "quantitative easing"
        context = "The central bank implemented **quantitative easing** to stimulate economic growth."
        expected_translation = "量化宽松"
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = expected_translation
        
        # 执行测试
        result = self.enhancement_service.enhance_term_translation(
            term, context, "en", "zh"
        )
        
        # 验证结果
        self.assertEqual(result.enhanced_translation, expected_translation)
        self.assertGreater(result.confidence, 0.8)
    
    def test_fuzzy_matching_with_spelling_errors(self):
        """测试模糊匹配处理拼写错误"""
        # 测试用例：algorithim -> algorithm
        text = "The new **algorithim** (正确：algorithm) shows promise in handling large datasets."
        potential_terms = ["algorithm", "algorithms", "method"]
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = "algorithm:0.9"
        
        # 执行测试
        results = self.enhancement_service.enhance_fuzzy_matching(
            text, potential_terms, "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        # 查找algorithm匹配
        algorithm_matches = [r for r in results if r.term == "algorithm"]
        self.assertGreater(len(algorithm_matches), 0)
        self.assertGreater(algorithm_matches[0].confidence, 0.8)
    
    def test_abbreviation_expansion(self):
        """测试缩写扩展"""
        # 测试用例：QE -> Quantitative Easing
        text = "The IMF discussed the impact of **QE** (Quantitative Easing) on global markets."
        potential_terms = ["quantitative easing", "quality assurance", "quick estimate"]
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = "quantitative easing:0.95"
        
        # 执行测试
        results = self.enhancement_service.enhance_fuzzy_matching(
            text, potential_terms, "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        # 查找quantitative easing匹配
        qe_matches = [r for r in results if r.term == "quantitative easing"]
        self.assertGreater(len(qe_matches), 0)
        self.assertGreater(qe_matches[0].confidence, 0.9)
    
    def test_morphological_variations(self):
        """测试词形变化"""
        # 测试用例：algorithmic -> algorithm
        text = "The **algorithmic** trading model relies on complex mathematical formulas."
        potential_terms = ["algorithm", "algorithms", "method"]
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = "algorithm:0.85"
        
        # 执行测试
        results = self.enhancement_service.enhance_fuzzy_matching(
            text, potential_terms, "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        # 查找algorithm匹配
        algorithm_matches = [r for r in results if r.term == "algorithm"]
        self.assertGreater(len(algorithm_matches), 0)
        self.assertGreater(algorithm_matches[0].confidence, 0.7)
    
    def test_polysemy_disambiguation(self):
        """测试多义词消歧"""
        # 测试用例1：light在物理上下文中
        term = "light"
        context1 = "The **light** in this room is too bright."
        expected_translation1 = "灯光"
        
        # 设置模拟响应
        self.mock_model_client.generate.return_value = expected_translation1
        
        # 执行测试
        result1 = self.enhancement_service.disambiguate_term(
            term, context1, "en", "zh"
        )
        
        # 验证结果
        self.assertEqual(result1.enhanced_translation, expected_translation1)
        self.assertEqual(result1.enhancement_type, "disambiguation")
        
        # 测试用例2：light在重量上下文中
        context2 = "The package is **light** and easy to carry."
        expected_translation2 = "轻的"
        
        # 重置模拟
        self.mock_model_client.reset_mock()
        self.mock_model_client.generate.return_value = expected_translation2
        
        # 执行测试
        result2 = self.enhancement_service.disambiguate_term(
            term, context2, "en", "zh"
        )
        
        # 验证结果
        self.assertEqual(result2.enhanced_translation, expected_translation2)
        self.assertNotEqual(result1.enhanced_translation, result2.enhanced_translation)
    
    def test_complex_scenario_processing(self):
        """测试复杂场景处理"""
        # 测试用例：HTML标签
        text = "The title <title>Artificial Intelligence</title> discusses <strong>machine learning</strong> applications."
        expected_translation = "标题 <title>人工智能</title> 讨论<strong>机器学习</strong>的应用。"
        
        # 设置模拟响应
        self.mock_model_client.translate_text.return_value = expected_translation
        
        # 执行测试
        result = self.enhancement_service.handle_complex_scenario(
            text, "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.enhancement_type, "complex_scenario")
        self.assertIn("<title>", result.enhanced_translation)
        self.assertIn("</title>", result.enhanced_translation)
        self.assertIn("<strong>", result.enhanced_translation)
        self.assertIn("</strong>", result.enhanced_translation)
        self.assertIn("人工智能", result.enhanced_translation)
        self.assertIn("机器学习", result.enhanced_translation)
    
    def test_code_preservation(self):
        """测试代码保留"""
        # 测试用例：代码片段
        text = 'Check the value in `config.json` where path = "C:\\Program Files\\App". If x > y, update the **algorithm** parameters.'
        
        # 设置模拟响应
        self.mock_model_client.translate_text.return_value = '检查`config.json`中的值，其中path = "C:\\Program Files\\App"。如果x > y，更新算法参数。'
        
        # 执行测试
        result = self.enhancement_service.handle_complex_scenario(
            text, "en", "zh"
        )
        
        # 验证结果
        self.assertIn("`config.json`", result.enhanced_translation)
        self.assertIn('path = "C:\\Program Files\\App"', result.enhanced_translation)
        self.assertIn("x > y", result.enhanced_translation)
        self.assertIn("算法", result.enhanced_translation)
    
    def test_mixed_language_processing(self):
        """测试中英混合处理"""
        # 测试用例：中英混合文本
        text = "这个API的**response**时间对**throughput**有直接影响。"
        expected_translation = "这个API的响应时间对吞吐量有直接影响。"
        
        # 设置模拟响应
        self.mock_model_client.translate_text.return_value = expected_translation
        
        # 执行测试
        result = self.enhancement_service.handle_complex_scenario(
            text, "en", "zh"
        )
        
        # 验证结果
        self.assertIn("响应", result.enhanced_translation)
        self.assertIn("吞吐量", result.enhanced_translation)
    
    def test_decision_engine_simple_text(self):
        """测试决策引擎简单文本处理"""
        # 简单文本应该使用传统策略
        text = "This is simple text."
        
        # 模拟传统匹配
        with patch.object(self.decision_engine, '_find_traditional_matches') as mock_find:
            with patch.object(self.decision_engine, '_analyze_traditional_quality') as mock_analyze:
                with patch.object(self.decision_engine, '_detect_enhancement_needs') as mock_detect:
                    with patch.object(self.decision_engine, '_make_decision') as mock_decide:
                        # 设置模拟返回值
                        mock_find.return_value = []
                        mock_analyze.return_value = 0.3
                        mock_detect.return_value = False
                        mock_decide.return_value = (
                            ProcessingStrategy.TRADITIONAL_ONLY,
                            0.6,
                            "默认使用传统策略"
                        )
                        
                        # 执行测试
                        result = self.decision_engine.decide_processing_strategy(
                            text, "en", "zh"
                        )
                        
                        # 验证结果
                        self.assertEqual(result.strategy, ProcessingStrategy.TRADITIONAL_ONLY)
                        self.assertGreater(result.complexity_score, 0)
                        self.assertFalse(result.enhancement_suggested)
    
    def test_decision_engine_complex_text(self):
        """测试决策引擎复杂文本处理"""
        # 复杂文本应该使用增强策略
        text = "The <code>algorithm</code> processes data; it's very complex with multiple **technical terms**."
        
        # 模拟传统匹配
        with patch.object(self.decision_engine, '_find_traditional_matches') as mock_find:
            with patch.object(self.decision_engine, '_analyze_traditional_quality') as mock_analyze:
                with patch.object(self.decision_engine, '_detect_enhancement_needs') as mock_detect:
                    with patch.object(self.decision_engine, '_make_decision') as mock_decide:
                        # 设置模拟返回值
                        mock_find.return_value = []
                        mock_analyze.return_value = 0.2
                        mock_detect.return_value = True
                        mock_decide.return_value = (
                            ProcessingStrategy.ENHANCEMENT_ONLY,
                            0.8,
                            "文本复杂度高，使用增强功能"
                        )
                        
                        # 执行测试
                        result = self.decision_engine.decide_processing_strategy(
                            text, "en", "zh"
                        )
                        
                        # 验证结果
                        self.assertEqual(result.strategy, ProcessingStrategy.ENHANCEMENT_ONLY)
                        self.assertGreater(result.complexity_score, 0)
                        self.assertTrue(result.enhancement_suggested)
    
    def test_cross_domain_terminology(self):
        """测试跨领域术语处理"""
        # 测试用例：同时包含技术和金融术语
        text = "**Blockchain technology** enhances transparency in **financial derivatives** trading."
        
        # 设置模拟响应
        self.mock_model_client.translate_text.return_value = "区块链技术增强了金融衍生品交易的透明度。"
        
        # 执行测试
        result = self.enhancement_service.handle_complex_scenario(
            text, "en", "zh"
        )
        
        # 验证结果
        self.assertIn("区块链技术", result.enhanced_translation)
        self.assertIn("金融衍生品", result.enhanced_translation)
    
    def test_performance_metrics(self):
        """测试性能指标"""
        # 测试处理时间
        start_time = time.time()
        
        term = "algorithm"
        context = "The algorithm processes data efficiently."
        self.mock_model_client.generate.return_value = "算法"
        
        result = self.enhancement_service.enhance_term_translation(
            term, context, "en", "zh"
        )
        
        end_time = time.time()
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertGreater(result.processing_time, 0)
        self.assertLess(result.processing_time, end_time - start_time + 0.1)  # 允许一些误差
        
        # 验证元数据
        self.assertIn('context_length', result.metadata)
        self.assertIn('prompt_length', result.metadata)
        self.assertIn('response_length', result.metadata)
    
    def test_error_handling(self):
        """测试错误处理"""
        # 设置模拟异常
        self.mock_model_client.generate.side_effect = Exception("模型错误")
        
        # 执行测试
        result = self.enhancement_service.enhance_term_translation(
            "algorithm", "context", "en", "zh"
        )
        
        # 验证结果
        self.assertIsInstance(result, EnhancementResult)
        self.assertEqual(result.original_term, "algorithm")
        self.assertEqual(result.enhanced_translation, "algorithm")  # 降级到原文
        self.assertIn('error', result.metadata)
        self.assertEqual(result.confidence, 0.0)
    
    def test_cache_effectiveness(self):
        """测试缓存效果"""
        term = "algorithm"
        context = "The algorithm processes data."
        self.mock_model_client.generate.return_value = "算法"
        
        # 第一次调用
        start_time = time.time()
        result1 = self.enhancement_service.enhance_term_translation(
            term, context, "en", "zh"
        )
        first_call_time = time.time() - start_time
        
        # 第二次调用（应该使用缓存）
        start_time = time.time()
        result2 = self.enhancement_service.enhance_term_translation(
            term, context, "en", "zh"
        )
        second_call_time = time.time() - start_time
        
        # 验证结果
        self.assertEqual(result1.original_term, result2.original_term)
        self.assertEqual(result1.enhanced_translation, result2.enhanced_translation)
        
        # 第二次调用应该更快（使用缓存）
        self.assertLessEqual(second_call_time, first_call_time)
        
        # 模型客户端只被调用一次
        self.assertEqual(self.mock_model_client.generate.call_count, 1)
    
    def test_terminology_consistency(self):
        """测试术语一致性"""
        # 同一术语在不同上下文中应保持一致翻译
        term = "algorithm"
        contexts = [
            "The algorithm processes data efficiently.",
            "We need to implement a new algorithm for this task.",
            "This algorithm uses advanced machine learning techniques."
        ]
        
        expected_translation = "算法"
        self.mock_model_client.generate.return_value = expected_translation
        
        results = []
        for context in contexts:
            result = self.enhancement_service.enhance_term_translation(
                term, context, "en", "zh"
            )
            results.append(result)
        
        # 验证所有翻译结果一致
        translations = [result.enhanced_translation for result in results]
        self.assertTrue(all(t == expected_translation for t in translations))
    
    def test_batch_processing(self):
        """测试批处理"""
        # 准备多个测试项
        test_items = [
            ("algorithm", "The algorithm processes data."),
            ("blockchain", "Blockchain technology is innovative."),
            ("artificial intelligence", "Artificial intelligence is advancing rapidly.")
        ]
        
        expected_translations = ["算法", "区块链", "人工智能"]
        
        # 执行批处理
        results = []
        for i, (term, context) in enumerate(test_items):
            self.mock_model_client.reset_mock()
            self.mock_model_client.generate.return_value = expected_translations[i]
            result = self.enhancement_service.enhance_term_translation(
                term, context, "en", "zh"
            )
            results.append(result)
        
        # 验证结果
        self.assertEqual(len(results), len(test_items))
        for i, result in enumerate(results):
            self.assertEqual(result.enhanced_translation, expected_translations[i])
            self.assertEqual(result.original_term, test_items[i][0])
            self.assertGreater(result.confidence, 0.7)


class TestEnhancedFactoryValidation(unittest.TestCase):
    """增强型工厂验证测试"""
    
    def setUp(self):
        """测试前准备"""
        self.factory = EnhancedModelClientFactory()
    
    def test_strategy_selection(self):
        """测试策略选择"""
        from src.core.models.enhanced_factory import ClientStrategy, ClientType
        
        # 创建完整的模拟配置
        mock_config = Mock()
        mock_config.provider = "ollama"
        mock_config.model = "test-model"
        mock_config.host = "localhost"
        mock_config.port = 11434
        mock_config.timeout = 30
        mock_config.temperature = 0.1
        mock_config.max_tokens = 1000
        
        # 测试质量优先策略
        with patch('src.core.models.enhanced_factory.EnhancedModelClientFactory._create_client_by_type') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            client = self.factory.create_client_with_strategy(
                "ollama", 
                mock_config, 
                ClientStrategy.QUALITY,
                ClientType.ENHANCEMENT
            )
            
            self.assertIsNotNone(client)
            mock_create.assert_called_once()
        
        # 测试性能优先策略
        with patch('src.core.models.enhanced_factory.EnhancedModelClientFactory._create_client_by_type') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            client = self.factory.create_client_with_strategy(
                "ollama", 
                mock_config, 
                ClientStrategy.PERFORMANCE,
                ClientType.TRANSLATION
            )
            
            self.assertIsNotNone(client)
            mock_create.assert_called_once()
    
    def test_optimal_client_selection(self):
        """测试最优客户端选择"""
        # 创建完整的模拟配置
        mock_config = Mock()
        mock_config.provider = "ollama"
        mock_config.model = "test-model"
        mock_config.host = "localhost"
        mock_config.port = 11434
        mock_config.timeout = 30
        mock_config.temperature = 0.1
        mock_config.max_tokens = 1000
        
        # 测试高复杂度任务应选择质量优先策略
        with patch('src.core.models.enhanced_factory.EnhancedModelClientFactory.create_client_with_strategy') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            client = self.factory.get_optimal_client(
                "enhancement", 0.9, "en", "zh"
            )
            
            self.assertIsNotNone(client)
            mock_create.assert_called_once()
        
        # 测试低复杂度任务可选择性能优先策略
        with patch('src.core.models.enhanced_factory.EnhancedModelClientFactory.create_client_with_strategy') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            client = self.factory.get_optimal_client(
                "translation", 0.2, "en", "zh"
            )
            
            self.assertIsNotNone(client)
            mock_create.assert_called_once()
    
    def test_terminology_enhancement_client(self):
        """测试术语增强专用客户端"""
        # 创建完整的模拟配置
        mock_config = Mock()
        mock_config.model = Mock()
        mock_config.model.provider = "ollama"
        mock_config.model.model = "test-model"
        mock_config.model.host = "localhost"
        mock_config.model.port = 11434
        mock_config.model.timeout = 30
        mock_config.model.temperature = 0.1
        mock_config.model.max_tokens = 1000
        
        # 创建术语增强专用客户端
        with patch('src.core.models.enhanced_factory.EnhancedModelClientFactory.create_client_with_strategy') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            client = self.factory.create_terminology_enhancement_client(mock_config)
            
            self.assertIsNotNone(client)
            mock_create.assert_called_once()
    
    def test_cache_statistics(self):
        """测试缓存统计"""
        # 获取初始缓存统计
        stats = self.factory.get_cache_statistics()
        
        self.assertIn('cache_enabled', stats)
        self.assertIn('cache_size', stats)
        self.assertIn('max_cache_size', stats)
        
        # 清空缓存
        self.factory.clear_cache()
        
        # 验证缓存已清空
        stats = self.factory.get_cache_statistics()
        self.assertEqual(stats['cache_size'], 0)


if __name__ == '__main__':
    unittest.main()