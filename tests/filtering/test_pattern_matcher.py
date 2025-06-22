"""
PPL 패턴 매칭 엔진 테스트
"""

import unittest
from unittest.mock import patch, mock_open
import json

from src.filtering.ppl_pattern_matcher import PPLPatternMatcher, PatternMatch
from src.filtering.pattern_definitions import PPLPattern


class TestPPLPatternMatcher(unittest.TestCase):
    """PPL 패턴 매칭 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 테스트용 설정
        self.test_config = {
            "thresholds": {
                "pattern_match_minimum": 0.7,
                "high_ppl_probability": 0.8,
                "medium_ppl_probability": 0.5,
                "low_ppl_probability": 0.2
            },
            "fuzzy_matching": {
                "enabled": True,
                "edit_distance_threshold": 2,
                "similarity_threshold": 0.8
            }
        }
        
        # Mock 설정 파일 로드
        with patch('builtins.open', mock_open(read_data=json.dumps(self.test_config))):
            self.matcher = PPLPatternMatcher()
    
    def test_explicit_pattern_detection(self):
        """명시적 PPL 패턴 탐지 테스트"""
        test_cases = [
            {
                'text': '이 영상은 브랜드로부터 협찬을 받아 제작되었습니다.',
                'expected_patterns': ['협찬'],
                'min_matches': 1
            },
            {
                'text': '제품을 제공받아 솔직하게 리뷰해봤어요 #광고',
                'expected_patterns': ['제공받', '#광고'],
                'min_matches': 2
            },
            {
                'text': 'This video is sponsored by the brand',
                'expected_patterns': ['sponsored'],
                'min_matches': 1
            },
            {
                'text': '개인적으로 구매해서 사용한 제품입니다.',
                'expected_patterns': [],
                'min_matches': 0
            }
        ]
        
        for i, case in enumerate(test_cases):
            with self.subTest(f"명시적 패턴 테스트 {i+1}"):
                matches = self.matcher.analyze_explicit_patterns(case['text'])
                
                # 최소 매칭 수 확인
                self.assertGreaterEqual(len(matches), case['min_matches'])
                
                # 예상 패턴 포함 확인
                if case['expected_patterns']:
                    matched_patterns = [match.pattern.pattern for match in matches]
                    for expected in case['expected_patterns']:
                        self.assertTrue(
                            any(expected in pattern for pattern in matched_patterns),
                            f"예상 패턴 '{expected}'를 찾을 수 없음"
                        )
    
    def test_implicit_pattern_detection(self):
        """암시적 PPL 패턴 탐지 테스트"""
        test_cases = [
            {
                'text': '특가 이벤트 진행 중! 구매링크는 아래에 있어요',
                'expected_categories': ['promotional_language', 'purchase_guidance'],
                'min_matches': 2
            },
            {
                'text': '신제품 런칭 기념 캠페인에 참여했어요',
                'expected_categories': ['commercial_context'],
                'min_matches': 1
            },
            {
                'text': '관심있으신 분들은 설명란 참고해주세요',
                'expected_categories': ['purchase_guidance'],
                'min_matches': 1
            }
        ]
        
        for i, case in enumerate(test_cases):
            with self.subTest(f"암시적 패턴 테스트 {i+1}"):
                matches = self.matcher.analyze_implicit_patterns(case['text'])
                
                self.assertGreaterEqual(len(matches), case['min_matches'])
                
                if case['expected_categories']:
                    matched_categories = [match.pattern.category for match in matches]
                    for expected_cat in case['expected_categories']:
                        self.assertIn(expected_cat, matched_categories)
    
    def test_fuzzy_matching(self):
        """퍼지 매칭 테스트"""
        test_cases = [
            {
                'text': '이 영상은 광고입니다',  # '광고' 정확 매칭
                'should_match': True,
                'description': '광고 정확 매칭'
            },
            {
                'text': '협찬 제품을 받았습니다',  # '협찬' 정확 매칭
                'should_match': True,
                'description': '협찬 정확 매칭'
            },
            {
                'text': '완전히 다른 내용입니다',
                'should_match': False,
                'description': '무관한 텍스트'
            }
        ]
        
        for case in test_cases:
            with self.subTest(case['description']):
                explicit_matches = self.matcher.analyze_explicit_patterns(case['text'])
                implicit_matches = self.matcher.analyze_implicit_patterns(case['text'])
                total_matches = explicit_matches + implicit_matches
                
                if case['should_match']:
                    self.assertGreater(len(total_matches), 0, "매칭 실패")
                else:
                    # 매칭되더라도 낮은 신뢰도여야 함
                    for match in total_matches:
                        self.assertLess(match.confidence, 0.8, "잘못된 높은 신뢰도 매칭")
    
    def test_pattern_overlap_filtering(self):
        """중복 패턴 필터링 테스트"""
        # 중복 패턴이 있는 텍스트
        text = "협찬 광고 영상입니다 #광고 #협찬"
        
        explicit_matches = self.matcher.analyze_explicit_patterns(text)
        filtered_matches = self.matcher.filter_overlapping_matches(explicit_matches)
        
        # 필터링된 매칭이 원본보다 적거나 같아야 함
        self.assertLessEqual(len(filtered_matches), len(explicit_matches))
        
        # 필터링된 매칭들은 겹치지 않아야 함
        for i, match1 in enumerate(filtered_matches):
            for j, match2 in enumerate(filtered_matches):
                if i != j:
                    self.assertFalse(
                        self.matcher._is_overlapping(match1, match2),
                        "필터링 후에도 겹치는 매칭 존재"
                    )
    
    def test_confidence_calculation(self):
        """신뢰도 계산 테스트"""
        high_confidence_text = "이 영상은 협찬을 받아 제작되었습니다 #광고"
        low_confidence_text = "이 제품이 좋은 것 같아요"
        
        high_matches = self.matcher.analyze_explicit_patterns(high_confidence_text)
        low_matches = self.matcher.analyze_explicit_patterns(low_confidence_text)
        
        if high_matches:
            avg_high_confidence = sum(m.confidence for m in high_matches) / len(high_matches)
            self.assertGreater(avg_high_confidence, 0.7, "명시적 패턴의 신뢰도가 낮음")
        
        if low_matches:
            avg_low_confidence = sum(m.confidence for m in low_matches) / len(low_matches)
            self.assertLess(avg_low_confidence, 0.5, "무관한 텍스트의 신뢰도가 높음")
    
    def test_statistics_generation(self):
        """통계 생성 테스트"""
        text = "협찬받은 제품 특가 이벤트 #광고 구매링크 아래"
        
        explicit_matches = self.matcher.analyze_explicit_patterns(text)
        implicit_matches = self.matcher.analyze_implicit_patterns(text)
        all_matches = explicit_matches + implicit_matches
        
        stats = self.matcher.get_pattern_statistics(all_matches)
        
        self.assertIn('total_matches', stats)
        self.assertIn('by_category', stats)
        self.assertIn('by_match_type', stats)
        self.assertIn('confidence_distribution', stats)
        
        self.assertEqual(stats['total_matches'], len(all_matches))
        
        # 신뢰도 분포 확인
        confidence_total = (stats['confidence_distribution']['high'] + 
                          stats['confidence_distribution']['medium'] + 
                          stats['confidence_distribution']['low'])
        self.assertEqual(confidence_total, len(all_matches))
    
    def test_performance(self):
        """성능 테스트"""
        import time
        
        # 긴 텍스트 생성
        long_text = "개인적으로 구매한 제품 리뷰입니다. " * 100
        long_text += "협찬받은 제품입니다 #광고 특가 이벤트 구매링크"
        
        start_time = time.time()
        
        explicit_matches = self.matcher.analyze_explicit_patterns(long_text)
        implicit_matches = self.matcher.analyze_implicit_patterns(long_text)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 5초 이내 처리 확인
        self.assertLess(processing_time, 5.0, f"처리 시간이 너무 김: {processing_time:.2f}초")
        
        # 결과가 있어야 함
        total_matches = len(explicit_matches) + len(implicit_matches)
        self.assertGreater(total_matches, 0, "긴 텍스트에서 패턴을 찾지 못함")


class TestPatternMatchDataClass(unittest.TestCase):
    """PatternMatch 데이터 클래스 테스트"""
    
    def test_pattern_match_creation(self):
        """PatternMatch 생성 테스트"""
        pattern = PPLPattern("테스트", 0.8, "test", "테스트 패턴")
        
        match = PatternMatch(
            pattern=pattern,
            matched_text="테스트",
            start_position=0,
            end_position=2,
            confidence=0.9,
            match_type="exact"
        )
        
        self.assertEqual(match.pattern.pattern, "테스트")
        self.assertEqual(match.matched_text, "테스트")
        self.assertEqual(match.confidence, 0.9)
        self.assertEqual(match.match_type, "exact")


if __name__ == '__main__':
    unittest.main()