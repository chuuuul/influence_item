"""
PPL 패턴 스코어링 시스템 테스트
"""

import unittest
from unittest.mock import patch, mock_open
import json

from src.filtering.pattern_scorer import PatternScorer, PPLScore
from src.filtering.ppl_pattern_matcher import PatternMatch
from src.filtering.pattern_definitions import PPLPattern


class TestPatternScorer(unittest.TestCase):
    """패턴 스코어링 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.test_config = {
            "scoring_weights": {
                "explicit_patterns": {
                    "direct_disclosure": 0.6,
                    "hashtag_disclosure": 0.55,
                    "description_patterns": 0.5
                },
                "implicit_patterns": {
                    "promotional_language": 0.25,
                    "commercial_context": 0.3,
                    "purchase_guidance": 0.35,
                    "timing_patterns": 0.4
                }
            },
            "thresholds": {
                "high_ppl_probability": 0.8,
                "medium_ppl_probability": 0.5,
                "low_ppl_probability": 0.2
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(self.test_config))):
            self.scorer = PatternScorer()
    
    def _create_test_match(self, pattern_text: str, weight: float, confidence: float, 
                          category: str = "explicit") -> PatternMatch:
        """테스트용 패턴 매칭 생성"""
        pattern = PPLPattern(pattern_text, weight, category, f"{pattern_text} 테스트")
        return PatternMatch(
            pattern=pattern,
            matched_text=pattern_text,
            start_position=0,
            end_position=len(pattern_text),
            confidence=confidence,
            match_type="exact"
        )
    
    def test_explicit_score_calculation(self):
        """명시적 패턴 점수 계산 테스트"""
        # 고신뢰도 명시적 패턴
        explicit_matches = [
            self._create_test_match("협찬", 0.95, 0.9, "explicit"),
            self._create_test_match("#광고", 0.95, 0.85, "explicit")
        ]
        
        score = self.scorer.calculate_ppl_score(explicit_matches, [])
        
        self.assertGreater(score.explicit_score, 0.7, "명시적 패턴 점수가 낮음")
        self.assertGreater(score.combined_score, 0.6, "종합 점수가 낮음")
        self.assertEqual(score.implicit_score, 0.0, "암시적 패턴이 없는데 점수가 있음")
    
    def test_implicit_score_calculation(self):
        """암시적 패턴 점수 계산 테스트"""
        # 다양한 암시적 패턴
        implicit_matches = [
            self._create_test_match("특가", 0.7, 0.8, "implicit"),
            self._create_test_match("구매링크", 0.85, 0.9, "implicit"),
            self._create_test_match("아래 링크", 0.85, 0.85, "implicit")
        ]
        
        score = self.scorer.calculate_ppl_score([], implicit_matches)
        
        self.assertGreater(score.implicit_score, 0.0, "암시적 패턴 점수가 0")
        self.assertGreater(score.combined_score, 0.0, "종합 점수가 0")
        self.assertEqual(score.explicit_score, 0.0, "명시적 패턴이 없는데 점수가 있음")
    
    def test_combined_score_weighting(self):
        """종합 점수 가중치 테스트"""
        explicit_matches = [self._create_test_match("협찬", 0.95, 0.9, "explicit")]
        implicit_matches = [self._create_test_match("특가", 0.7, 0.8, "implicit")]
        
        # 명시적 패턴만
        explicit_only = self.scorer.calculate_ppl_score(explicit_matches, [])
        
        # 암시적 패턴만
        implicit_only = self.scorer.calculate_ppl_score([], implicit_matches)
        
        # 둘 다 포함
        combined = self.scorer.calculate_ppl_score(explicit_matches, implicit_matches)
        
        # 명시적 패턴이 있으면 더 높은 점수
        self.assertGreater(explicit_only.combined_score, implicit_only.combined_score)
        self.assertGreater(combined.combined_score, implicit_only.combined_score)
    
    def test_confidence_calculation(self):
        """신뢰도 계산 테스트"""
        # 고신뢰도 패턴들
        high_conf_matches = [
            self._create_test_match("협찬", 0.95, 0.95, "explicit"),
            self._create_test_match("#광고", 0.95, 0.9, "explicit")
        ]
        
        # 저신뢰도 패턴들
        low_conf_matches = [
            self._create_test_match("특가", 0.7, 0.6, "implicit")
        ]
        
        high_score = self.scorer.calculate_ppl_score(high_conf_matches, [])
        low_score = self.scorer.calculate_ppl_score([], low_conf_matches)
        
        self.assertGreater(high_score.confidence, low_score.confidence)
        self.assertGreater(high_score.confidence, 0.8, "고신뢰도 패턴의 신뢰도가 낮음")
    
    def test_evidence_count(self):
        """증거 개수 테스트"""
        explicit_matches = [
            self._create_test_match("협찬", 0.95, 0.9, "explicit"),
            self._create_test_match("#광고", 0.95, 0.85, "explicit")
        ]
        
        implicit_matches = [
            self._create_test_match("특가", 0.7, 0.8, "implicit")
        ]
        
        score = self.scorer.calculate_ppl_score(explicit_matches, implicit_matches)
        
        expected_count = len(explicit_matches) + len(implicit_matches)
        self.assertEqual(score.evidence_count, expected_count)
    
    def test_dominant_category_detection(self):
        """주요 카테고리 탐지 테스트"""
        # 명시적 패턴이 많은 경우
        explicit_heavy = [
            self._create_test_match("협찬", 0.95, 0.9, "explicit"),
            self._create_test_match("#광고", 0.95, 0.85, "explicit"),
            self._create_test_match("제공받은", 0.9, 0.8, "explicit")
        ]
        
        implicit_light = [self._create_test_match("특가", 0.7, 0.8, "implicit")]
        
        score = self.scorer.calculate_ppl_score(explicit_heavy, implicit_light)
        self.assertEqual(score.dominant_category, "explicit")
    
    def test_reasoning_generation(self):
        """판단 근거 생성 테스트"""
        explicit_matches = [self._create_test_match("협찬", 0.95, 0.9, "explicit")]
        implicit_matches = [self._create_test_match("특가", 0.7, 0.8, "implicit")]
        
        score = self.scorer.calculate_ppl_score(explicit_matches, implicit_matches)
        
        self.assertIsInstance(score.reasoning, list)
        self.assertGreater(len(score.reasoning), 0, "판단 근거가 생성되지 않음")
        
        reasoning_text = " ".join(score.reasoning)
        self.assertIn("명시적", reasoning_text, "명시적 패턴 언급 없음")
        self.assertIn("암시적", reasoning_text, "암시적 패턴 언급 없음")
    
    def test_ppl_level_classification(self):
        """PPL 수준 분류 테스트"""
        # 고확률 PPL
        high_ppl_matches = [
            self._create_test_match("협찬", 0.95, 0.95, "explicit"),
            self._create_test_match("#광고", 0.95, 0.9, "explicit"),
            self._create_test_match("제공받은", 0.9, 0.85, "explicit")
        ]
        
        high_score = self.scorer.calculate_ppl_score(high_ppl_matches, [])
        high_level = self.scorer.classify_ppl_level(high_score)
        
        self.assertIn("high", high_level.lower(), "고확률 PPL 분류 실패")
        
        # 저확률 PPL
        low_ppl_matches = [self._create_test_match("제품", 0.3, 0.4, "implicit")]
        
        low_score = self.scorer.calculate_ppl_score([], low_ppl_matches)
        low_level = self.scorer.classify_ppl_level(low_score)
        
        self.assertIn("low", low_level.lower(), "저확률 PPL 분류 실패")
    
    def test_score_summary(self):
        """점수 요약 테스트"""
        matches = [self._create_test_match("협찬", 0.95, 0.9, "explicit")]
        score = self.scorer.calculate_ppl_score(matches, [])
        summary = self.scorer.get_score_summary(score)
        
        required_fields = ["level", "combined_score", "confidence", "evidence_count", 
                          "dominant_category", "breakdown"]
        
        for field in required_fields:
            self.assertIn(field, summary, f"요약에 '{field}' 필드 누락")
        
        self.assertIn("explicit", summary["breakdown"])
        self.assertIn("implicit", summary["breakdown"])
    
    def test_edge_cases(self):
        """엣지 케이스 테스트"""
        # 빈 매칭 리스트
        empty_score = self.scorer.calculate_ppl_score([], [])
        
        self.assertEqual(empty_score.explicit_score, 0.0)
        self.assertEqual(empty_score.implicit_score, 0.0)
        self.assertEqual(empty_score.combined_score, 0.0)
        self.assertEqual(empty_score.evidence_count, 0)
        
        # 매우 낮은 신뢰도 패턴
        low_conf_match = self._create_test_match("테스트", 0.1, 0.1, "implicit")
        low_score = self.scorer.calculate_ppl_score([], [low_conf_match])
        
        self.assertLess(low_score.combined_score, 0.3, "낮은 신뢰도 패턴의 점수가 높음")
    
    def test_multiple_categories(self):
        """다중 카테고리 테스트"""
        diverse_matches = [
            self._create_test_match("협찬", 0.95, 0.9, "explicit"),
            self._create_test_match("특가", 0.7, 0.8, "promotional"),
            self._create_test_match("신제품", 0.75, 0.7, "commercial"),
            self._create_test_match("구매링크", 0.85, 0.85, "guidance")
        ]
        
        score = self.scorer.calculate_ppl_score([diverse_matches[0]], diverse_matches[1:])
        
        # 다양한 카테고리의 증거가 있으면 신뢰도 증가
        self.assertGreater(score.confidence, 0.7, "다양한 증거의 신뢰도 보너스 없음")


class TestPPLScoreDataClass(unittest.TestCase):
    """PPLScore 데이터 클래스 테스트"""
    
    def test_ppl_score_creation(self):
        """PPLScore 생성 테스트"""
        score = PPLScore(
            explicit_score=0.8,
            implicit_score=0.4,
            combined_score=0.7,
            confidence=0.85,
            evidence_count=3,
            dominant_category="explicit",
            reasoning=["테스트 근거"]
        )
        
        self.assertEqual(score.explicit_score, 0.8)
        self.assertEqual(score.implicit_score, 0.4)
        self.assertEqual(score.combined_score, 0.7)
        self.assertEqual(score.confidence, 0.85)
        self.assertEqual(score.evidence_count, 3)
        self.assertEqual(score.dominant_category, "explicit")
        self.assertEqual(len(score.reasoning), 1)


if __name__ == '__main__':
    unittest.main()