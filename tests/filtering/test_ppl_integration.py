"""
PPL 통합 분석 테스트

T01B_S03에서 구현된 PPL 컨텍스트 분석 및 통합 모듈의
통합 테스트를 수행합니다.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.filtering.ppl_analyzer import IntegratedPPLAnalyzer, PPLAnalysisInput
from src.filtering.ppl_context_analyzer import PPLContextAnalyzer, ContextAnalysisResult
from src.filtering.ppl_probability_calculator import PPLProbabilityCalculator
from src.filtering.ppl_classifier import PPLClassifier
from src.gemini_analyzer.state_manager import StateManager


class TestPPLIntegration:
    """PPL 통합 분석 테스트"""
    
    @pytest.fixture
    def mock_state_manager(self):
        """StateManager 모의 객체"""
        mock_manager = Mock(spec=StateManager)
        mock_manager.call_gemini_api = AsyncMock()
        return mock_manager
    
    @pytest.fixture
    def ppl_analyzer(self, mock_state_manager):
        """PPL 분석기 인스턴스"""
        return IntegratedPPLAnalyzer(mock_state_manager)
    
    @pytest.fixture
    def sample_analysis_input(self):
        """샘플 분석 입력 데이터"""
        return PPLAnalysisInput(
            video_title="요즘 제가 정말 애용하는 스킨케어 템!",
            video_description="안녕하세요! 오늘은 제가 요즘 정말 잘 쓰고 있는 스킨케어 제품들을 소개해드릴게요.",
            transcript_excerpt="이거 진짜 좋아서 여러분한테 꼭 알려드리고 싶었어요. 제가 요즘 정말 잘 쓰는 게 있는데, 이 크림이에요.",
            video_metadata={"channel": "뷰티유튜버", "duration": 600}
        )
    
    @pytest.mark.asyncio
    async def test_full_ppl_analysis_workflow(self, ppl_analyzer, sample_analysis_input, mock_state_manager):
        """전체 PPL 분석 워크플로우 테스트"""
        # Gemini API 응답 모의
        mock_gemini_response = """
        {
            "commercial_likelihood": 0.75,
            "reasoning": "강한 추천 언어와 개인적 애착 표현이 발견됨",
            "key_indicators": ["정말 좋아서", "꼭 알려드리고 싶었어요", "정말 잘 쓰는"],
            "confidence": 0.8
        }
        """
        mock_state_manager.call_gemini_api.return_value = mock_gemini_response
        
        # 분석 실행
        result = await ppl_analyzer.analyze_ppl(sample_analysis_input)
        
        # 결과 검증
        assert result is not None
        assert hasattr(result, 'is_ppl')
        assert hasattr(result, 'ppl_probability')
        assert hasattr(result, 'confidence_level')
        assert 0.0 <= result.ppl_probability <= 1.0
        assert result.analysis_duration > 0
        assert isinstance(result.analysis_timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_high_ppl_content_detection(self, ppl_analyzer, mock_state_manager):
        """높은 PPL 가능성 콘텐츠 감지 테스트"""
        # 명확한 PPL 콘텐츠 입력
        high_ppl_input = PPLAnalysisInput(
            video_title="협찬받은 화장품 리뷰! 할인 코드도 있어요",
            video_description="이 영상은 브랜드 제공으로 제작되었습니다.",
            transcript_excerpt="이번에 브랜드에서 협찬을 받아서 리뷰해드리게 되었어요. 정말 좋은 제품이니까 여러분도 구매해보세요. 할인 코드는 SAVE20 입니다."
        )
        
        # 높은 상업성 응답 모의
        mock_state_manager.call_gemini_api.return_value = """
        {
            "commercial_likelihood": 0.95,
            "reasoning": "명시적 협찬 언급, 할인 코드 제공, 직접적 구매 유도",
            "key_indicators": ["협찬", "브랜드 제공", "구매해보세요", "할인 코드"],
            "confidence": 0.9
        }
        """
        
        result = await ppl_analyzer.analyze_ppl(high_ppl_input)
        
        # 높은 PPL 확률 검증
        assert result.ppl_probability > 0.8
        assert result.is_ppl == True
        assert result.classification.category.value == "high_ppl_likely"
        assert result.classification.filtering_decision == True
    
    @pytest.mark.asyncio
    async def test_organic_content_detection(self, ppl_analyzer, mock_state_manager):
        """유기적 콘텐츠 감지 테스트"""
        # 유기적 콘텐츠 입력
        organic_input = PPLAnalysisInput(
            video_title="일상 브이로그 - 오늘 하루 기록",
            video_description="평범한 하루를 기록한 브이로그입니다.",
            transcript_excerpt="오늘은 집에서 휴식을 취했어요. 책도 읽고 음악도 들으면서 여유로운 시간을 보냈습니다."
        )
        
        # 낮은 상업성 응답 모의
        mock_state_manager.call_gemini_api.return_value = """
        {
            "commercial_likelihood": 0.1,
            "reasoning": "개인적 일상 공유, 상업적 의도 없음",
            "key_indicators": [],
            "confidence": 0.8
        }
        """
        
        result = await ppl_analyzer.analyze_ppl(organic_input)
        
        # 낮은 PPL 확률 검증
        assert result.ppl_probability < 0.3
        assert result.is_ppl == False
        assert result.classification.category.value in ["no_ppl_organic", "low_ppl_unlikely"]
        assert result.classification.filtering_decision == False
    
    @pytest.mark.asyncio
    async def test_context_analyzer_integration(self, mock_state_manager):
        """컨텍스트 분석기 통합 테스트"""
        context_analyzer = PPLContextAnalyzer(mock_state_manager)
        
        # 테스트 데이터
        mock_state_manager.call_gemini_api.return_value = """
        {
            "commercial_likelihood": 0.6,
            "reasoning": "중간 수준의 상업적 신호 감지",
            "key_indicators": ["추천", "좋은 제품"],
            "confidence": 0.7
        }
        """
        
        result = await context_analyzer.analyze_context(
            video_title="제품 리뷰",
            video_description="좋은 제품을 발견해서 공유합니다",
            transcript_excerpt="이 제품 정말 추천해요",
            pattern_analysis_result={"explicit_matches": [], "implicit_matches": []}
        )
        
        assert isinstance(result, ContextAnalysisResult)
        assert 0.0 <= result.commercial_likelihood <= 1.0
        assert result.reasoning is not None
        assert isinstance(result.key_indicators, list)
    
    def test_probability_calculator_integration(self):
        """확률 계산기 통합 테스트"""
        calculator = PPLProbabilityCalculator()
        
        # 테스트 패턴 분석 결과
        pattern_result = {
            "explicit_matches": [{"confidence": 0.8}],
            "implicit_matches": [{"confidence": 0.5}],
            "pattern_scores": {"explicit_score": 0.8, "implicit_score": 0.5}
        }
        
        # 테스트 컨텍스트 분석 결과
        context_result = ContextAnalysisResult(
            commercial_likelihood=0.7,
            reasoning="테스트 분석",
            key_indicators=["테스트"],
            confidence=0.8,
            raw_response={}
        )
        
        result = calculator.calculate_final_probability(pattern_result, context_result)
        
        assert result is not None
        assert 0.0 <= result.final_probability <= 1.0
        assert result.classification is not None
        assert result.confidence_level is not None
        assert isinstance(result.component_scores, dict)
    
    def test_classifier_integration(self):
        """분류기 통합 테스트"""
        classifier = PPLClassifier()
        
        # 다양한 확률로 분류 테스트
        test_cases = [
            (0.9, "high_ppl_likely"),
            (0.6, "medium_ppl_possible"),
            (0.3, "low_ppl_unlikely"),
            (0.1, "no_ppl_organic")
        ]
        
        for probability, expected_category in test_cases:
            result = classifier.classify(
                probability_score=probability,
                component_scores={"test": probability},
                context_indicators=["test"],
                confidence=0.8
            )
            
            assert result.category.value == expected_category
            assert result.probability_score == probability
            assert isinstance(result.labels, list)
            assert len(result.labels) > 0
    
    @pytest.mark.asyncio
    async def test_batch_analysis(self, ppl_analyzer, mock_state_manager):
        """배치 분석 테스트"""
        # 배치 입력 데이터
        batch_inputs = [
            PPLAnalysisInput(
                video_title=f"테스트 영상 {i}",
                video_description="테스트 설명",
                transcript_excerpt="테스트 스크립트"
            )
            for i in range(3)
        ]
        
        # Gemini API 응답 모의
        mock_state_manager.call_gemini_api.return_value = """
        {
            "commercial_likelihood": 0.5,
            "reasoning": "테스트 분석",
            "key_indicators": [],
            "confidence": 0.5
        }
        """
        
        results = await ppl_analyzer.batch_analyze(batch_inputs, max_concurrent=2)
        
        assert len(results) == len(batch_inputs)
        for result in results:
            assert result is not None
            assert hasattr(result, 'ppl_probability')
    
    @pytest.mark.asyncio
    async def test_error_handling(self, ppl_analyzer, mock_state_manager):
        """오류 처리 테스트"""
        # Gemini API 오류 시뮬레이션
        mock_state_manager.call_gemini_api.side_effect = Exception("API 오류")
        
        test_input = PPLAnalysisInput(
            video_title="테스트",
            video_description="테스트",
            transcript_excerpt="테스트"
        )
        
        result = await ppl_analyzer.analyze_ppl(test_input)
        
        # 오류 시에도 유효한 결과 반환 확인
        assert result is not None
        assert result.ppl_probability == 0.5  # 기본값
        assert result.confidence_level == "low"
        assert result.is_ppl == False  # 안전한 기본값
    
    def test_reasoning_generation(self, ppl_analyzer):
        """판단 근거 생성 테스트"""
        # 모의 분석 결과 생성
        pattern_result = {"explicit_matches": [], "implicit_matches": []}
        context_result = ContextAnalysisResult(
            commercial_likelihood=0.6,
            reasoning="테스트 근거",
            key_indicators=["테스트"],
            confidence=0.7,
            raw_response={}
        )
        
        from src.filtering.ppl_probability_calculator import PPLProbabilityResult
        probability_result = PPLProbabilityResult(
            final_probability=0.6,
            classification="medium_ppl_possible",
            confidence_level="medium",
            component_scores={"explicit_patterns": 0.5, "implicit_patterns": 0.4, "context_analysis": 0.6},
            reasoning_summary="테스트 요약"
        )
        
        from src.filtering.ppl_classifier import PPLClassificationResult, PPLCategory, ConfidenceLevel
        classification_result = PPLClassificationResult(
            category=PPLCategory.MEDIUM_PPL,
            confidence_level=ConfidenceLevel.MEDIUM,
            probability_score=0.6,
            risk_level="MEDIUM",
            recommended_action="MANUAL_REVIEW",
            filtering_decision=False,
            labels=["PPL_POSSIBLE"],
            metadata={}
        )
        
        reasoning_report = ppl_analyzer.reasoning_generator.generate_reasoning_report(
            pattern_analysis_result=pattern_result,
            context_analysis_result=context_result,
            probability_result=probability_result,
            classification_result=classification_result
        )
        
        assert reasoning_report is not None
        assert reasoning_report.analysis_summary is not None
        assert reasoning_report.detailed_reasoning is not None
        assert isinstance(reasoning_report.key_evidence, list)
        assert reasoning_report.confidence_explanation is not None
    
    def test_performance_requirements(self, ppl_analyzer):
        """성능 요구사항 검증"""
        # 분석 시간이 10초 이내인지 확인하는 테스트는 
        # 실제 API 호출이 필요하므로 모의 테스트로 대체
        assert hasattr(ppl_analyzer, 'analyze_ppl')
        assert hasattr(ppl_analyzer, 'batch_analyze')
        
        # 필요한 모든 컴포넌트가 초기화되었는지 확인
        assert ppl_analyzer.pattern_matcher is not None
        assert ppl_analyzer.context_analyzer is not None
        assert ppl_analyzer.probability_calculator is not None
        assert ppl_analyzer.classifier is not None
        assert ppl_analyzer.reasoning_generator is not None
    
    def test_accuracy_requirements_structure(self, ppl_analyzer):
        """정확도 요구사항 구조 검증"""
        # 80% 이상의 컨텍스트 분석 정확도는 실제 데이터로 검증 필요
        # 여기서는 구조적 요구사항만 확인
        
        # 가중치 검증
        weights = ppl_analyzer.probability_calculator.get_weight_info()
        assert abs(sum(weights.values()) - 1.0) < 0.01  # 가중치 총합이 1.0
        
        # 임계값 검증
        thresholds = ppl_analyzer.classifier.get_classification_summary
        assert callable(thresholds)  # 분류 기능 존재
        
        # 투명성 보장 검증
        assert hasattr(ppl_analyzer.reasoning_generator, 'generate_reasoning_report')
        assert hasattr(ppl_analyzer.reasoning_generator, 'export_report_as_text')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])