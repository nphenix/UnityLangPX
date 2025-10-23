"""
UnityLangPX 混合决策引擎单元测试

测试混合决策引擎的各项功能，包括策略决策、复杂度分析、
传统匹配质量分析和混合处理等。
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.core.hybrid_decision_engine import (
    HybridDecisionEngine,
    DecisionResult,
    ProcessingStrategy
)
from src.core.terminology_enhancement import TerminologyEnhancementService
from src.core.terminology import TerminologyEntry


class TestHybridDecisionEngine(unittest.TestCase):
    """混合决策引擎测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟配置
        self.mock_config = Mock()
        self.mock_config.complexity_threshold = 0.7
        self.mock_config.traditional_threshold = 0.8
        self.mock_config.enhancement_threshold = 0.5
        self.mock_config.fallback_enabled = True
        
        # 创建模拟增强服务
        self.mock_enhancement_service = Mock(spec=TerminologyEnhancementService)
        
        # 创建混合决策引擎
        self.decision_engine = HybridDecisionEngine(
            self.mock_config,
            self.mock_enhancement_service
        )
    
    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.decision_engine.config)
        self.assertIsNotNone(self.decision_enhancement_service)
        self.assertIsNotNone(self.decision_engine.traditional_store)
        self.assertIsNotNone(self.decision_engine.terminology_matcher)
        self.assertEqual(self.decision_engine.complexity_threshold, 0.7)
        self.assertEqual(self.decision_engine.traditional_threshold, 0.8)
        self.assertEqual(self.decision_engine.enhancement_threshold, 0.5)
    
    def test_decide_processing_strategy_traditional_only(self):
        """测试决策处理策略 - 仅传统"""
        # 准备测试数据
        text = "This is simple text with algorithm."
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        # 设置模拟匹配
        mock_term = Mock(spec=TerminologyEntry)
        mock_term.source_term = "algorithm"
        mock_term.confidence = 0.9
        
        with patch.object(self.decision_engine, '_find_traditional_matches') as mock_find:
            with patch.object(self.decision_engine, '_analyze_traditional_quality') as mock_analyze:
                with patch.object(self.decision_engine, '_detect_enhancement_needs') as mock_detect:
                    with patch.object(self.decision_engine, '_make_decision') as mock_decide:
                        # 设置模拟返回值
                        mock_find.return_value = [(mock_term, "algorithm")]
                        mock_analyze.return_value = 0.9
                        mock_detect.return_value = False
                        mock_decide.return_value = (
                            ProcessingStrategy.TRADITIONAL_ONLY,
                            0.9,
                            "传统匹配质量高，无需增强"
                        )
                        
                        # 执行测试
                        result = self.decision_engine.decide_processing_strategy(
                            text, source_lang, target_lang, context
                        )
                        
                        # 验证结果
                        self.assertIsInstance(result, DecisionResult)
                        self.assertEqual(result.strategy, ProcessingStrategy.TRADITIONAL_ONLY)
                        self.assertEqual(result.confidence, 0.9)
                        self.assertEqual(result.reasoning, "传统匹配质量高，无需增强")
                        self.assertGreater(result.complexity_score, 0)
                        self.assertEqual(len(result.traditional_matches), 1)
                        self.assertFalse(result.enhancement_suggested)
    
    def test_decide_processing_strategy_enhancement_only(self):
        """测试决策处理策略 - 仅增强"""
        # 准备测试数据
        text = "The <code>algorithm</code> processes data."
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
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
                            text, source_lang, target_lang, context
                        )
                        
                        # 验证结果
                        self.assertIsInstance(result, DecisionResult)
                        self.assertEqual(result.strategy, ProcessingStrategy.ENHANCEMENT_ONLY)
                        self.assertEqual(result.confidence, 0.8)
                        self.assertEqual(result.reasoning, "文本复杂度高，使用增强功能")
                        self.assertGreater(result.complexity_score, 0)
                        self.assertEqual(len(result.traditional_matches), 0)
                        self.assertTrue(result.enhancement_suggested)
    
    def test_decide_processing_strategy_hybrid(self):
        """测试决策处理策略 - 混合"""
        # 准备测试数据
        text = "The algorithm processes data efficiently."
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        with patch.object(self.decision_engine, '_find_traditional_matches') as mock_find:
            with patch.object(self.decision_engine, '_analyze_traditional_quality') as mock_analyze:
                with patch.object(self.decision_engine, '_detect_enhancement_needs') as mock_detect:
                    with patch.object(self.decision_engine, '_make_decision') as mock_decide:
                        # 设置模拟返回值
                        mock_term = Mock(spec=TerminologyEntry)
                        mock_term.source_term = "algorithm"
                        mock_find.return_value = [(mock_term, "algorithm")]
                        mock_analyze.return_value = 0.6
                        mock_detect.return_value = True
                        mock_decide.return_value = (
                            ProcessingStrategy.HYBRID,
                            0.7,
                            "需要增强但传统匹配尚可，使用混合策略"
                        )
                        
                        # 执行测试
                        result = self.decision_engine.decide_processing_strategy(
                            text, source_lang, target_lang, context
                        )
                        
                        # 验证结果
                        self.assertIsInstance(result, DecisionResult)
                        self.assertEqual(result.strategy, ProcessingStrategy.HYBRID)
                        self.assertEqual(result.confidence, 0.7)
                        self.assertEqual(result.reasoning, "需要增强但传统匹配尚可，使用混合策略")
                        self.assertGreater(result.complexity_score, 0)
                        self.assertEqual(len(result.traditional_matches), 1)
                        self.assertTrue(result.enhancement_suggested)
    
    def test_decide_processing_strategy_fallback(self):
        """测试决策处理策略 - 降级"""
        # 准备测试数据
        text = "This is simple text."
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        with patch.object(self.decision_engine, '_find_traditional_matches') as mock_find:
            with patch.object(self.decision_engine, '_analyze_traditional_quality') as mock_analyze:
                with patch.object(self.decision_engine, '_detect_enhancement_needs') as mock_detect:
                    with patch.object(self.decision_engine, '_make_decision') as mock_decide:
                        # 设置模拟异常
                        mock_find.side_effect = Exception("测试异常")
                        
                        # 执行测试
                        result = self.decision_engine.decide_processing_strategy(
                            text, source_lang, target_lang, context
                        )
                        
                        # 验证结果
                        self.assertIsInstance(result, DecisionResult)
                        self.assertEqual(result.strategy, ProcessingStrategy.FALLBACK)
                        self.assertEqual(result.confidence, 0.0)
                        self.assertIn("决策失败", result.reasoning)
                        self.assertEqual(result.complexity_score, 0.0)
                        self.assertEqual(len(result.traditional_matches), 0)
                        self.assertFalse(result.enhancement_suggested)
    
    def test_process_with_strategy_traditional_only(self):
        """测试根据策略处理 - 仅传统"""
        # 准备测试数据
        text = "This is simple text with algorithm."
        strategy = ProcessingStrategy.TRADITIONAL_ONLY
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        with patch.object(self.decision_engine, '_process_traditional_only') as mock_process:
            # 设置模拟返回值
            mock_process.return_value = ("这是带有算法的简单文本。", [])
            
            # 执行测试
            result_text, processing_info = self.decision_engine.process_with_strategy(
                text, strategy, source_lang, target_lang, context
            )
            
            # 验证结果
            self.assertEqual(result_text, "这是带有算法的简单文本。")
            self.assertIsInstance(processing_info, dict)
            self.assertEqual(processing_info['strategy'], 'traditional_only')
            self.assertFalse(processing_info['enhancement_used'])
            self.assertEqual(processing_info['traditional_matches'], 0)
            
            # 验证方法被调用
            mock_process.assert_called_once_with(text, source_lang, target_lang)
    
    def test_process_with_strategy_enhancement_only(self):
        """测试根据策略处理 - 仅增强"""
        # 准备测试数据
        text = "The <code>algorithm</code> processes data."
        strategy = ProcessingStrategy.ENHANCEMENT_ONLY
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        with patch.object(self.decision_engine, '_process_enhancement_only') as mock_process:
            # 设置模拟返回值
            mock_process.return_value = "算法处理数据。"
            
            # 执行测试
            result_text, processing_info = self.decision_engine.process_with_strategy(
                text, strategy, source_lang, target_lang, context
            )
            
            # 验证结果
            self.assertEqual(result_text, "算法处理数据。")
            self.assertIsInstance(processing_info, dict)
            self.assertEqual(processing_info['strategy'], 'enhancement_only')
            self.assertTrue(processing_info['enhancement_used'])
            
            # 验证方法被调用
            mock_process.assert_called_once_with(text, source_lang, target_lang, context)
    
    def test_process_with_strategy_hybrid(self):
        """测试根据策略处理 - 混合"""
        # 准备测试数据
        text = "The algorithm processes data."
        strategy = ProcessingStrategy.HYBRID
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        with patch.object(self.decision_engine, '_process_hybrid') as mock_process:
            with patch.object(self.decision_engine, '_find_traditional_matches') as mock_find:
                # 设置模拟返回值
                mock_process.return_value = "算法处理数据。"
                mock_term = Mock(spec=TerminologyEntry)
                mock_find.return_value = [(mock_term, "algorithm")]
                
                # 执行测试
                result_text, processing_info = self.decision_engine.process_with_strategy(
                    text, strategy, source_lang, target_lang, context
                )
                
                # 验证结果
                self.assertEqual(result_text, "算法处理数据。")
                self.assertIsInstance(processing_info, dict)
                self.assertEqual(processing_info['strategy'], 'hybrid')
                self.assertTrue(processing_info['enhancement_used'])
                self.assertEqual(processing_info['traditional_matches'], 1)
                
                # 验证方法被调用
                mock_process.assert_called_once_with(text, source_lang, target_lang, context)
    
    def test_process_with_strategy_fallback(self):
        """测试根据策略处理 - 降级"""
        # 准备测试数据
        text = "This is simple text."
        strategy = ProcessingStrategy.FALLBACK
        source_lang = "en"
        target_lang = "zh"
        context = ""
        
        with patch.object(self.decision_engine, '_process_fallback') as mock_process:
            # 设置模拟返回值
            mock_process.return_value = "这是简单文本。"
            
            # 执行测试
            result_text, processing_info = self.decision_engine.process_with_strategy(
                text, strategy, source_lang, target_lang, context
            )
            
            # 验证结果
            self.assertEqual(result_text, "这是简单文本。")
            self.assertIsInstance(processing_info, dict)
            self.assertEqual(processing_info['strategy'], 'fallback')
            
            # 验证方法被调用
            mock_process.assert_called_once_with(text, source_lang, target_lang)
    
    def test_analyze_text_complexity(self):
        """测试分析文本复杂度"""
        # 测试简单文本
        simple_text = "This is simple."
        complexity = self.decision_engine.analyze_text_complexity(simple_text)
        self.assertGreaterEqual(complexity, 0)
        self.assertLessEqual(complexity, 1)
        
        # 测试复杂文本
        complex_text = "The <code>algorithm</code> processes data; it's very complex."
        complexity = self.decision_engine.analyze_text_complexity(complex_text)
        self.assertGreater(complexity, 0.1)  # 应该比简单文本复杂
        
        # 测试长文本
        long_text = "This is a very long text. " * 50
        complexity = self.decision_engine.analyze_text_complexity(long_text)
        self.assertGreater(complexity, 0.2)  # 长文本应该更复杂
    
    def test_find_traditional_matches(self):
        """测试查找传统匹配"""
        text = "This is simple text with algorithm."
        source_lang = "en"
        target_lang = "zh"
        
        with patch.object(self.decision_engine.traditional_store, 'find_terms') as mock_find:
            with patch.object(self.decision_engine.terminology_matcher, 'find_exact_matches') as mock_match:
                # 设置模拟返回值
                mock_term = Mock(spec=TerminologyEntry)
                mock_find.return_value = [mock_term]
                mock_match.return_value = [(mock_term, "algorithm")]
                
                # 执行测试
                matches = self.decision_engine._find_traditional_matches(text, source_lang, target_lang)
                
                # 验证结果
                self.assertIsInstance(matches, list)
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0][1], "algorithm")
                
                # 验证方法被调用
                mock_find.assert_called_once_with(source_lang=source_lang, target_lang=target_lang)
                mock_match.assert_called_once()
    
    def test_analyze_traditional_quality(self):
        """测试分析传统匹配质量"""
        # 测试无匹配
        quality = self.decision_engine._analyze_traditional_quality("text", [])
        self.assertEqual(quality, 0.0)
        
        # 测试有匹配
        mock_term = Mock(spec=TerminologyEntry)
        mock_term.confidence = 0.9
        mock_term.source_term = "algorithm"
        matches = [(mock_term, "algorithm")]
        
        quality = self.decision_engine._analyze_traditional_quality("This is algorithm.", matches)
        self.assertGreater(quality, 0)
        self.assertLessEqual(quality, 1.0)
    
    def test_detect_enhancement_needs(self):
        """测试检测增强需求"""
        # 测试简单文本
        simple_text = "This is simple."
        context = ""
        needs = self.decision_engine._detect_enhancement_needs(simple_text, context)
        self.assertIsInstance(needs, bool)
        
        # 测试复杂文本
        complex_text = "The <code>algorithm</code> processes data."
        needs = self.decision_engine._detect_enhancement_needs(complex_text, context)
        self.assertTrue(needs)  # 复杂文本应该需要增强
        
        # 测试包含模糊候选的文本
        fuzzy_text = "The algorithim processes data."
        needs = self.decision_engine._detect_enhancement_needs(fuzzy_text, context)
        self.assertTrue(needs)  # 模糊文本应该需要增强
    
    def test_make_decision(self):
        """测试制定决策"""
        # 测试高质量传统匹配
        decision = self.decision_engine._make_decision(
            complexity_score=0.3,
            traditional_quality=0.9,
            enhancement_needed=False,
            traditional_matches=[],
            text="simple text",
            context=""
        )
        self.assertEqual(decision[0], ProcessingStrategy.TRADITIONAL_ONLY)
        self.assertGreater(decision[1], 0.8)  # 高置信度
        
        # 测试高复杂度
        decision = self.decision_engine._make_decision(
            complexity_score=0.9,
            traditional_quality=0.3,
            enhancement_needed=True,
            traditional_matches=[],
            text="complex text",
            context=""
        )
        self.assertEqual(decision[0], ProcessingStrategy.ENHANCEMENT_ONLY)
        
        # 测试中等情况
        decision = self.decision_engine._make_decision(
            complexity_score=0.6,
            traditional_quality=0.6,
            enhancement_needed=True,
            traditional_matches=[],
            text="medium text",
            context=""
        )
        self.assertIn(decision[0], [ProcessingStrategy.HYBRID, ProcessingStrategy.ENHANCEMENT_ONLY])
    
    def test_has_complex_elements(self):
        """测试检测复杂元素"""
        # 测试HTML标签
        html_text = "The <title>AI</title> is important."
        has_complex = self.decision_engine._has_complex_elements(html_text)
        self.assertTrue(has_complex)
        
        # 测试代码片段
        code_text = "Use `algorithm` to process data."
        has_complex = self.decision_engine._has_complex_elements(code_text)
        self.assertTrue(has_complex)
        
        # 测试无复杂元素
        simple_text = "This is simple text."
        has_complex = self.decision_engine._has_complex_elements(simple_text)
        self.assertFalse(has_complex)
    
    def test_has_fuzzy_candidate_terms(self):
        """测试检测模糊匹配候选"""
        # 测试包含拼写错误的文本
        fuzzy_text = "The algorithim processes data."
        has_fuzzy = self.decision_engine._has_fuzzy_candidate_terms(fuzzy_text)
        self.assertTrue(has_fuzzy)
        
        # 测试正常文本
        normal_text = "The algorithm processes data."
        has_fuzzy = self.decision_engine._has_fuzzy_candidate_terms(normal_text)
        self.assertFalse(has_fuzzy)
    
    def test_has_potential_polysems(self):
        """测试检测潜在多义词"""
        # 测试包含多义词的文本
        polysem_text = "The light in the room is bright."
        has_polysem = self.decision_engine._has_potential_polysems(polysem_text)
        self.assertTrue(has_polysem)
        
        # 测试不包含多义词的文本
        non_polysem_text = "The algorithm processes data."
        has_polysem = self.decision_engine._has_potential_polysems(non_polysem_text)
        self.assertFalse(has_polysem)
    
    def test_is_context_dependent(self):
        """测试检测是否依赖上下文"""
        # 测试依赖上下文的文本
        context_text = "It is important."
        context = "The algorithm is important."
        is_dependent = self.decision_engine._is_context_dependent(context_text, context)
        self.assertTrue(is_dependent)
        
        # 测试不依赖上下文的文本
        independent_text = "Algorithm processes data."
        is_dependent = self.decision_engine._is_context_dependent(independent_text, context)
        self.assertFalse(is_dependent)
        
        # 测试无上下文
        is_dependent = self.decision_engine._is_context_dependent(independent_text, "")
        self.assertFalse(is_dependent)
    
    def test_get_decision_statistics(self):
        """测试获取决策统计"""
        # 初始统计
        stats = self.decision_engine.get_decision_statistics()
        self.assertIn('total_decisions', stats)
        self.assertIn('traditional_decisions', stats)
        self.assertIn('enhancement_decisions', stats)
        self.assertIn('hybrid_decisions', stats)
        self.assertIn('fallback_decisions', stats)
        self.assertEqual(stats['total_decisions'], 0)
        
        # 执行一些决策
        self.decision_engine._update_decision_stats(ProcessingStrategy.TRADITIONAL_ONLY)
        self.decision_engine._update_decision_stats(ProcessingStrategy.ENHANCEMENT_ONLY)
        
        # 检查更新后的统计
        stats = self.decision_engine.get_decision_statistics()
        self.assertEqual(stats['total_decisions'], 2)
        self.assertEqual(stats['traditional_decisions'], 1)
        self.assertEqual(stats['enhancement_decisions'], 1)
    
    def test_reset_statistics(self):
        """测试重置统计信息"""
        # 添加一些统计
        self.decision_engine._update_decision_stats(ProcessingStrategy.TRADITIONAL_ONLY)
        
        # 重置统计
        self.decision_engine.reset_statistics()
        
        # 检查统计是否重置
        stats = self.decision_engine.get_decision_statistics()
        self.assertEqual(stats['total_decisions'], 0)
        self.assertEqual(stats['traditional_decisions'], 0)
    
    def test_update_decision_stats(self):
        """测试更新决策统计"""
        # 测试各种策略
        self.decision_engine._update_decision_stats(ProcessingStrategy.TRADITIONAL_ONLY)
        self.decision_engine._update_decision_stats(ProcessingStrategy.ENHANCEMENT_ONLY)
        self.decision_engine._update_decision_stats(ProcessingStrategy.HYBRID)
        self.decision_engine._update_decision_stats(ProcessingStrategy.FALLBACK)
        
        # 检查统计
        stats = self.decision_engine.get_decision_statistics()
        self.assertEqual(stats['total_decisions'], 4)
        self.assertEqual(stats['traditional_decisions'], 1)
        self.assertEqual(stats['enhancement_decisions'], 1)
        self.assertEqual(stats['hybrid_decisions'], 1)
        self.assertEqual(stats['fallback_decisions'], 1)


class TestDecisionResult(unittest.TestCase):
    """决策结果测试"""
    
    def test_init(self):
        """测试初始化"""
        result = DecisionResult(
            strategy=ProcessingStrategy.TRADITIONAL_ONLY,
            confidence=0.9,
            reasoning="传统匹配质量高",
            complexity_score=0.3,
            traditional_matches=[],
            enhancement_suggested=False,
            metadata={}
        )
        
        self.assertEqual(result.strategy, ProcessingStrategy.TRADITIONAL_ONLY)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.reasoning, "传统匹配质量高")
        self.assertEqual(result.complexity_score, 0.3)
        self.assertEqual(len(result.traditional_matches), 0)
        self.assertFalse(result.enhancement_suggested)
        self.assertIsInstance(result.metadata, dict)


if __name__ == '__main__':
    unittest.main()