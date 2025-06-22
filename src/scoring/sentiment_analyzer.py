"""
감성 강도 분석 모듈

텍스트의 감성 강도를 분석하여 0.0-1.0 범위의 점수를 계산합니다.
긍정/부정 키워드, 감탄사, 강조 표현을 종합적으로 분석합니다.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SentimentPattern:
    """감성 패턴 정의"""
    positive_keywords: List[str]
    negative_keywords: List[str]
    exclamation_patterns: List[str]
    emphasis_patterns: List[str]
    emotional_expressions: List[str]


class SentimentAnalyzer:
    """감성 강도 분석기"""
    
    def __init__(self):
        """감성 분석기 초기화"""
        self.sentiment_patterns = self._load_sentiment_patterns()
        logger.info("감성 강도 분석기 초기화 완료")
    
    def _load_sentiment_patterns(self) -> SentimentPattern:
        """감성 패턴 로드"""
        return SentimentPattern(
            positive_keywords=[
                # 강한 긍정 표현
                "진짜", "정말", "완전", "너무", "엄청", "최고", "짱",
                "대박", "개", "쩐다", "좋아", "사랑", "애정", "찐",
                "레전드", "미쳤다", "존좋", "갓", "핵",
                
                # 만족 표현
                "만족", "추천", "강추", "믿고", "신뢰", "확실", "보장",
                "효과", "놀라", "감동", "후회없", "베스트", "원탑",
                
                # 품질/성능 표현
                "품질", "퀄리티", "고급", "프리미엄", "명품", "브랜드",
                "완벽", "훌륭", "멋진", "예쁜", "이쁜", "예뻐",
                
                # 사용 만족도
                "편해", "좋네", "만족스러", "괜찮", "훌륭", "완벽",
                "최적", "적절", "딱", "마음에", "취향저격"
            ],
            
            negative_keywords=[
                # 부정 표현
                "별로", "그냥", "안좋", "실망", "후회", "아쉬", "별로",
                "글쎄", "음", "뭔가", "애매", "그저그래", "평범",
                
                # 문제점 표현
                "문제", "단점", "아쉬움", "불편", "귀찮", "짜증",
                "스트레스", "힘들", "어려", "복잡", "번거"
            ],
            
            exclamation_patterns=[
                r'!{1,}',  # 느낌표
                r'\?{1,}',  # 물음표
                r'~{2,}',   # 물결표 연속
                r'ㅋ{2,}',  # ㅋㅋㅋ
                r'ㅎ{2,}',  # ㅎㅎㅎ
                r'ㅠ{2,}',  # ㅠㅠㅠ
                r'ㅜ{2,}',  # ㅜㅜㅜ
            ],
            
            emphasis_patterns=[
                # 강조 표현
                r'정말\s*정말',
                r'진짜\s*진짜',
                r'너무\s*너무',
                r'완전\s*완전',
                r'엄청\s*엄청',
                
                # 반복 강조
                r'(\w+)\s*\1',  # 단어 반복
                r'[가-힣]{1,3}[ㄱ-ㅎㅏ-ㅣ]{2,}',  # 의성어/의태어
            ],
            
            emotional_expressions=[
                # 감정 표현
                "와", "우와", "헉", "와우", "오", "어머", "세상에",
                "대박", "미쳤다", "장난아니", "실화", "진심",
                
                # 놀라움 표현
                "놀라", "깜짝", "충격", "당황", "멘붕", "소름",
                
                # 기쁨 표현
                "기뻐", "행복", "신나", "좋아", "즐거", "쾌감",
                "환상", "꿈같", "기분좋", "만족"
            ]
        )
    
    def analyze_sentiment_intensity(self, text: str, tone_indicators: Optional[Dict] = None) -> float:
        """
        감성 강도 분석
        
        Args:
            text: 분석할 텍스트
            tone_indicators: 추가적인 톤 지표
            
        Returns:
            감성 강도 점수 (0.0-1.0)
        """
        try:
            if not text or not text.strip():
                return 0.0
            
            text = text.strip().lower()
            
            # 개별 분석 수행
            positive_score = self._calculate_positive_score(text)
            negative_score = self._calculate_negative_score(text)
            exclamation_score = self._calculate_exclamation_score(text)
            emphasis_score = self._calculate_emphasis_score(text)
            emotional_score = self._calculate_emotional_score(text)
            
            # 가중 평균 계산
            sentiment_score = (
                positive_score * 0.35 +
                exclamation_score * 0.25 +
                emphasis_score * 0.20 +
                emotional_score * 0.20 -
                negative_score * 0.15  # 부정 요소는 차감
            )
            
            # 0.0-1.0 범위로 정규화
            sentiment_score = max(0.0, min(1.0, sentiment_score))
            
            logger.debug(f"감성 강도 분석 완료 - 점수: {sentiment_score:.3f}")
            return sentiment_score
            
        except Exception as e:
            logger.error(f"감성 강도 분석 실패: {str(e)}")
            return 0.5  # 기본값 반환
    
    def _calculate_positive_score(self, text: str) -> float:
        """긍정 키워드 점수 계산"""
        positive_count = 0
        total_words = len(text.split())
        
        for keyword in self.sentiment_patterns.positive_keywords:
            count = text.count(keyword)
            if count > 0:
                # 키워드 빈도와 강도를 고려
                positive_count += count * self._get_keyword_weight(keyword)
        
        # 전체 단어 수 대비 정규화
        if total_words == 0:
            return 0.0
        
        score = positive_count / total_words
        return min(1.0, score * 2)  # 최대 1.0으로 제한
    
    def _calculate_negative_score(self, text: str) -> float:
        """부정 키워드 점수 계산"""
        negative_count = 0
        total_words = len(text.split())
        
        for keyword in self.sentiment_patterns.negative_keywords:
            count = text.count(keyword)
            if count > 0:
                negative_count += count
        
        if total_words == 0:
            return 0.0
        
        score = negative_count / total_words
        return min(1.0, score * 3)  # 부정 요소는 더 강하게 반영
    
    def _calculate_exclamation_score(self, text: str) -> float:
        """감탄사 점수 계산"""
        exclamation_count = 0
        
        for pattern in self.sentiment_patterns.exclamation_patterns:
            matches = re.findall(pattern, text)
            exclamation_count += len(matches)
        
        # 텍스트 길이 대비 정규화
        text_length = len(text)
        if text_length == 0:
            return 0.0
        
        score = exclamation_count / (text_length / 50)  # 50자당 1개 기준
        return min(1.0, score)
    
    def _calculate_emphasis_score(self, text: str) -> float:
        """강조 표현 점수 계산"""
        emphasis_count = 0
        
        for pattern in self.sentiment_patterns.emphasis_patterns:
            matches = re.findall(pattern, text)
            emphasis_count += len(matches)
        
        # 문장 수 대비 정규화
        sentence_count = len(re.split(r'[.!?]', text))
        if sentence_count == 0:
            return 0.0
        
        score = emphasis_count / sentence_count
        return min(1.0, score)
    
    def _calculate_emotional_score(self, text: str) -> float:
        """감정 표현 점수 계산"""
        emotional_count = 0
        
        for expression in self.sentiment_patterns.emotional_expressions:
            count = text.count(expression)
            emotional_count += count
        
        total_words = len(text.split())
        if total_words == 0:
            return 0.0
        
        score = emotional_count / total_words
        return min(1.0, score * 5)  # 감정 표현은 강하게 반영
    
    def _get_keyword_weight(self, keyword: str) -> float:
        """키워드별 가중치 반환"""
        high_weight_keywords = [
            "최고", "완전", "대박", "미쳤다", "레전드", "찐",
            "사랑", "애정", "강추", "믿고", "확실"
        ]
        
        if keyword in high_weight_keywords:
            return 2.0
        return 1.0
    
    def get_sentiment_breakdown(self, text: str) -> Dict[str, float]:
        """감성 분석 세부 내역 반환"""
        if not text or not text.strip():
            return {
                "positive_score": 0.0,
                "negative_score": 0.0,
                "exclamation_score": 0.0,
                "emphasis_score": 0.0,
                "emotional_score": 0.0,
                "total_sentiment": 0.0
            }
        
        text = text.strip().lower()
        
        positive_score = self._calculate_positive_score(text)
        negative_score = self._calculate_negative_score(text)
        exclamation_score = self._calculate_exclamation_score(text)
        emphasis_score = self._calculate_emphasis_score(text)
        emotional_score = self._calculate_emotional_score(text)
        
        total_sentiment = self.analyze_sentiment_intensity(text)
        
        return {
            "positive_score": positive_score,
            "negative_score": negative_score,
            "exclamation_score": exclamation_score,
            "emphasis_score": emphasis_score,
            "emotional_score": emotional_score,
            "total_sentiment": total_sentiment
        }