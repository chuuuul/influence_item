"""
매력도 스코어링 시스템 통합 테스트

ScoreCalculator의 전체 워크플로우를 테스트합니다.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from src.scoring.score_calculator import ScoreCalculator, ScoringInput
from src.scoring.influencer_analyzer import ChannelMetrics
from src.gemini_analyzer.models import ScoreDetails


class TestScoreCalculator(unittest.TestCase):
    """매력도 점수 계산기 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.calculator = ScoreCalculator()
        
        # 테스트용 채널 메트릭스
        self.test_channel_metrics = ChannelMetrics(
            subscriber_count=100000,
            video_view_count=50000,
            video_count=200,
            channel_age_months=24,
            engagement_rate=0.05,
            verified_status=True
        )
        
        # 테스트용 입력 데이터
        self.test_scoring_input = ScoringInput(
            transcript_text="정말 좋아요! 이 제품 완전 추천합니다. 써보니까 진짜 효과가 있어요.",
            usage_patterns=["써보니까", "사용해보면", "이렇게 쓰면"],
            demonstration_level=2,
            channel_metrics=self.test_channel_metrics,
            tone_indicators={"positive": True},
            reputation_score=0.8
        )
    
    def test_calculate_attractiveness_score_basic(self):
        """기본 매력도 점수 계산 테스트"""
        result = self.calculator.calculate_attractiveness_score(self.test_scoring_input)
        
        # 결과 타입 검증
        self.assertIsInstance(result, ScoreDetails)
        
        # 점수 범위 검증
        self.assertGreaterEqual(result.total, 0)
        self.assertLessEqual(result.total, 100)
        self.assertGreaterEqual(result.sentiment_score, 0.0)
        self.assertLessEqual(result.sentiment_score, 1.0)
        self.assertGreaterEqual(result.endorsement_score, 0.0)
        self.assertLessEqual(result.endorsement_score, 1.0)
        self.assertGreaterEqual(result.influencer_score, 0.0)
        self.assertLessEqual(result.influencer_score, 1.0)
    
    def test_prd_formula_accuracy(self):
        """PRD 공식 정확성 테스트"""
        result = self.calculator.calculate_attractiveness_score(self.test_scoring_input)
        
        # PRD 공식으로 계산한 예상값
        expected_total = int(round(
            (0.50 * result.sentiment_score +
             0.35 * result.endorsement_score +
             0.15 * result.influencer_score) * 100
        ))
        
        # 1점 오차 허용
        self.assertLessEqual(abs(result.total - expected_total), 1)
    
    def test_high_quality_input(self):
        """고품질 입력 데이터 테스트"""
        high_quality_input = ScoringInput(
            transcript_text="진짜 완전 대박이에요! 이거 써보시면 진짜 놀라실 거예요. 저는 매일 쓰고 있어요.",
            usage_patterns=["써보시면", "매일 쓰고", "사용해보니", "발라보면"],
            demonstration_level=3,
            channel_metrics=ChannelMetrics(
                subscriber_count=1000000,
                video_view_count=500000,
                video_count=500,
                channel_age_months=36,
                engagement_rate=0.08,
                verified_status=True
            ),
            reputation_score=0.9
        )
        
        result = self.calculator.calculate_attractiveness_score(high_quality_input)
        
        # 높은 점수 예상
        self.assertGreater(result.total, 70)
        self.assertGreater(result.sentiment_score, 0.6)
    
    def test_low_quality_input(self):
        """저품질 입력 데이터 테스트"""
        low_quality_input = ScoringInput(
            transcript_text="뭔가 그냥 그런 것 같아요.",
            usage_patterns=["그런 것 같아요"],
            demonstration_level=0,
            channel_metrics=ChannelMetrics(
                subscriber_count=100,
                video_view_count=50,
                video_count=5,
                channel_age_months=1,
                engagement_rate=0.01,
                verified_status=False
            ),
            reputation_score=0.3
        )
        
        result = self.calculator.calculate_attractiveness_score(low_quality_input)
        
        # 낮은 점수 예상
        self.assertLess(result.total, 50)
    
    def test_classify_by_thresholds(self):
        """임계값 기반 분류 테스트"""
        # 높은 점수 분류
        high_classification = self.calculator.classify_by_thresholds(85)
        self.assertEqual(high_classification["priority"], "high")
        self.assertEqual(high_classification["status"], "approved")
        
        # 중간 점수 분류
        medium_classification = self.calculator.classify_by_thresholds(65)
        self.assertEqual(medium_classification["priority"], "medium")
        self.assertEqual(medium_classification["status"], "needs_review")
        
        # 낮은 점수 분류
        low_classification = self.calculator.classify_by_thresholds(45)
        self.assertEqual(low_classification["priority"], "low")
        
        # 매우 낮은 점수 분류
        reject_classification = self.calculator.classify_by_thresholds(25)
        self.assertEqual(reject_classification["priority"], "reject")
        self.assertEqual(reject_classification["status"], "rejected")
    
    def test_get_production_recommendation(self):
        """제작 권장사항 생성 테스트"""
        score_details = ScoreDetails(
            total=75,
            sentiment_score=0.8,
            endorsement_score=0.7,
            influencer_score=0.6
        )
        
        recommendation = self.calculator.get_production_recommendation(score_details)
        
        # 구조 검증
        self.assertIn("classification", recommendation)
        self.assertIn("score_breakdown", recommendation)
        self.assertIn("analysis", recommendation)
        self.assertIn("recommendation", recommendation)
        
        # 분석 내용 검증
        self.assertIn("strengths", recommendation["analysis"])
        self.assertIn("weaknesses", recommendation["analysis"])
        self.assertIn("improvement_suggestions", recommendation["analysis"])
    
    def test_get_score_breakdown(self):
        """점수 세부 내역 테스트"""
        breakdown = self.calculator.get_score_breakdown(self.test_scoring_input)
        
        # 구조 검증
        self.assertIn("final_score", breakdown)
        self.assertIn("sentiment_analysis", breakdown)
        self.assertIn("endorsement_analysis", breakdown)
        self.assertIn("influencer_analysis", breakdown)
        
        # 최종 점수 구조 검증
        final_score = breakdown["final_score"]
        self.assertIn("total", final_score)
        self.assertIn("weights", final_score)
        
        # 가중치 검증
        weights = final_score["weights"]
        self.assertEqual(weights["sentiment_weight"], 0.50)
        self.assertEqual(weights["endorsement_weight"], 0.35)
        self.assertEqual(weights["influencer_weight"], 0.15)
    
    def test_calculate_score_confidence(self):
        """점수 신뢰도 계산 테스트"""
        confidence = self.calculator.calculate_score_confidence(self.test_scoring_input)
        
        # 신뢰도 범위 검증
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
    
    def test_batch_calculate_scores(self):
        """배치 점수 계산 테스트"""
        scoring_inputs = [
            self.test_scoring_input,
            ScoringInput(
                transcript_text="그냥 평범한 제품이에요.",
                usage_patterns=["사용했어요"],
                demonstration_level=1,
                channel_metrics=self.test_channel_metrics
            )
        ]
        
        results = self.calculator.batch_calculate_scores(scoring_inputs)
        
        # 결과 개수 검증
        self.assertEqual(len(results), 2)
        
        # 각 결과 구조 검증
        for result in results:
            self.assertIn("index", result)
            self.assertIn("success", result)
            if result["success"]:
                self.assertIn("score_details", result)
                self.assertIn("classification", result)
    
    def test_edge_cases(self):
        """엣지 케이스 테스트"""
        # 빈 텍스트
        empty_input = ScoringInput(
            transcript_text="",
            usage_patterns=[],
            demonstration_level=0,
            channel_metrics=ChannelMetrics(
                subscriber_count=0,
                video_view_count=0,
                video_count=0,
                channel_age_months=0
            )
        )
        
        result = self.calculator.calculate_attractiveness_score(empty_input)
        self.assertIsInstance(result, ScoreDetails)
        self.assertGreaterEqual(result.total, 0)
        self.assertLessEqual(result.total, 100)
        
        # 매우 긴 텍스트
        long_text = "정말 좋아요! " * 100
        long_input = ScoringInput(
            transcript_text=long_text,
            usage_patterns=["좋아요"] * 50,
            demonstration_level=3,
            channel_metrics=self.test_channel_metrics
        )
        
        result = self.calculator.calculate_attractiveness_score(long_input)
        self.assertIsInstance(result, ScoreDetails)
    
    def test_score_interpretation(self):
        """점수 해석 테스트"""
        # 다양한 점수대의 해석 테스트
        test_scores = [95, 85, 75, 65, 55, 45, 35, 25]
        
        for score in test_scores:
            interpretation = self.calculator.get_score_interpretation(score)
            
            self.assertIn("grade", interpretation)
            self.assertIn("interpretation", interpretation)
            self.assertIn("recommended_action", interpretation)
            
            # 점수에 따른 등급 검증
            if score >= 90:
                self.assertEqual(interpretation["grade"], "S")
            elif score >= 80:
                self.assertEqual(interpretation["grade"], "A")
            elif score >= 70:
                self.assertEqual(interpretation["grade"], "B")


class TestScoringAccuracy(unittest.TestCase):
    """스코어링 정확도 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.calculator = ScoreCalculator()
    
    def test_known_high_score_case(self):
        """알려진 고점수 케이스 테스트"""
        # 실제 고품질 콘텐츠를 모방한 테스트 케이스
        high_score_input = ScoringInput(
            transcript_text="진짜 완전 대박이에요! 이거 써보시면 놀라실 거예요. 저는 매일매일 쓰고 있는데 효과가 정말 확실해요. 강력 추천합니다!",
            usage_patterns=[
                "써보시면", "매일매일 쓰고", "사용해보니", "발라보면", 
                "이렇게 써보세요", "직접 써봤는데"
            ],
            demonstration_level=3,
            channel_metrics=ChannelMetrics(
                subscriber_count=2000000,
                video_view_count=1000000,
                video_count=800,
                channel_age_months=48,
                engagement_rate=0.10,
                verified_status=True
            ),
            reputation_score=0.95
        )
        
        result = self.calculator.calculate_attractiveness_score(high_score_input)
        
        # 높은 점수 예상 (80점 이상)
        self.assertGreaterEqual(result.total, 80, 
                               f"고품질 콘텐츠의 점수가 {result.total}로 예상보다 낮습니다.")
        
        # 각 구성요소도 높아야 함
        self.assertGreater(result.sentiment_score, 0.7)
        self.assertGreater(result.endorsement_score, 0.6)
        self.assertGreater(result.influencer_score, 0.8)
    
    def test_known_low_score_case(self):
        """알려진 저점수 케이스 테스트"""
        low_score_input = ScoringInput(
            transcript_text="음.. 그냥 그런 것 같아요. 별로 특별할 건 없네요.",
            usage_patterns=["그런 것 같아요"],
            demonstration_level=0,
            channel_metrics=ChannelMetrics(
                subscriber_count=500,
                video_view_count=100,
                video_count=10,
                channel_age_months=2,
                engagement_rate=0.02,
                verified_status=False
            ),
            reputation_score=0.2
        )
        
        result = self.calculator.calculate_attractiveness_score(low_score_input)
        
        # 낮은 점수 예상 (40점 이하)
        self.assertLessEqual(result.total, 40,
                            f"저품질 콘텐츠의 점수가 {result.total}로 예상보다 높습니다.")
    
    def test_consistency_across_similar_inputs(self):
        """유사한 입력에 대한 일관성 테스트"""
        base_channel = ChannelMetrics(
            subscriber_count=100000,
            video_view_count=50000,
            video_count=200,
            channel_age_months=24,
            engagement_rate=0.05,
            verified_status=True
        )
        
        # 유사한 텍스트로 여러 번 테스트
        similar_texts = [
            "정말 좋아요! 이 제품 완전 추천합니다.",
            "진짜 좋네요! 이거 완전 추천해요.",
            "정말로 좋아요! 이 상품 강력 추천합니다."
        ]
        
        scores = []
        for text in similar_texts:
            scoring_input = ScoringInput(
                transcript_text=text,
                usage_patterns=["좋아요", "추천"],
                demonstration_level=2,
                channel_metrics=base_channel
            )
            result = self.calculator.calculate_attractiveness_score(scoring_input)
            scores.append(result.total)
        
        # 점수들이 비슷한 범위에 있어야 함 (최대 10점 차이)
        score_range = max(scores) - min(scores)
        self.assertLessEqual(score_range, 10,
                            f"유사한 입력의 점수 차이가 {score_range}로 너무 큽니다.")


if __name__ == '__main__':
    unittest.main()