"""
PPL (Product Placement) 패턴 정의 모듈

연예인 YouTube 콘텐츠에서 유료광고를 탐지하기 위한 
명시적/암시적 PPL 인디케이터 패턴을 정의합니다.
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class PPLPattern:
    """PPL 패턴 정보를 담는 데이터 클래스"""
    pattern: str
    weight: float
    category: str
    description: str


class PPLPatternDefinitions:
    """PPL 패턴 정의 클래스"""
    
    def __init__(self):
        self._explicit_patterns = self._load_explicit_patterns()
        self._implicit_patterns = self._load_implicit_patterns()
    
    def _load_explicit_patterns(self) -> Dict[str, List[PPLPattern]]:
        """명시적 PPL 패턴 로드"""
        return {
            'direct_disclosure': [
                PPLPattern('협찬', 0.95, 'direct_disclosure', '직접적인 협찬 공지'),
                PPLPattern('광고', 0.95, 'direct_disclosure', '직접적인 광고 표시'),
                PPLPattern('제공받은', 0.90, 'direct_disclosure', '제품 제공 공지'),
                PPLPattern('제공받았습니다', 0.90, 'direct_disclosure', '제품 제공 공지 정중형'),
                PPLPattern('sponsored', 0.95, 'direct_disclosure', '영문 스폰서 표시'),
                PPLPattern('AD', 0.95, 'direct_disclosure', '광고 약어'),
                PPLPattern('advertisement', 0.90, 'direct_disclosure', '영문 광고 표시'),
                PPLPattern('paid promotion', 0.85, 'direct_disclosure', '유료 프로모션'),
                PPLPattern('유료광고', 0.95, 'direct_disclosure', '유료광고 직접 표시'),
            ],
            'hashtag_disclosure': [
                PPLPattern('#광고', 0.95, 'hashtag_disclosure', '해시태그 광고 공지'),
                PPLPattern('#협찬', 0.95, 'hashtag_disclosure', '해시태그 협찬 공지'),
                PPLPattern('#제공', 0.85, 'hashtag_disclosure', '해시태그 제품 제공'),
                PPLPattern('#AD', 0.95, 'hashtag_disclosure', '해시태그 광고 약어'),
                PPLPattern('#sponsored', 0.95, 'hashtag_disclosure', '해시태그 스폰서'),
                PPLPattern('#PR', 0.80, 'hashtag_disclosure', '해시태그 PR'),
            ],
            'description_patterns': [
                PPLPattern('업체로부터 제품을 제공받아', 0.90, 'description_patterns', '제품 제공 설명'),
                PPLPattern('협찬을 받고 작성한', 0.90, 'description_patterns', '협찬 설명'),
                PPLPattern('광고가 포함된', 0.85, 'description_patterns', '광고 포함 고지'),
                PPLPattern('브랜드로부터 제공받은', 0.85, 'description_patterns', '브랜드 제공'),
                PPLPattern('마케팅 목적으로 제작된', 0.80, 'description_patterns', '마케팅 목적 고지'),
            ]
        }
    
    def _load_implicit_patterns(self) -> Dict[str, List[PPLPattern]]:
        """암시적 PPL 패턴 로드"""
        return {
            'promotional_language': [
                PPLPattern('특가', 0.70, 'promotional_language', '특별가격 언급'),
                PPLPattern('할인', 0.65, 'promotional_language', '할인 언급'),
                PPLPattern('이벤트', 0.60, 'promotional_language', '이벤트 언급'),
                PPLPattern('프로모션', 0.70, 'promotional_language', '프로모션 언급'),
                PPLPattern('쿠폰', 0.75, 'promotional_language', '쿠폰 언급'),
                PPLPattern('링크 아래', 0.80, 'purchase_guidance', '구매 링크 안내'),
                PPLPattern('구매링크', 0.85, 'purchase_guidance', '직접적 구매 링크'),
                PPLPattern('상품정보', 0.60, 'promotional_language', '상품 정보 안내'),
                PPLPattern('한정판매', 0.65, 'promotional_language', '한정 판매'),
                PPLPattern('출시기념', 0.70, 'promotional_language', '출시 기념'),
            ],
            'commercial_context': [
                PPLPattern('브랜드 소개', 0.75, 'commercial_context', '브랜드 소개'),
                PPLPattern('신제품', 0.80, 'commercial_context', '신제품 출시'),
                PPLPattern('런칭', 0.75, 'commercial_context', '제품 런칭'),
                PPLPattern('캠페인', 0.70, 'commercial_context', '마케팅 캠페인'),
                PPLPattern('컬래버레이션', 0.75, 'commercial_context', '브랜드 컬래버'),
                PPLPattern('콜라보', 0.75, 'commercial_context', '브랜드 콜라보'),
                PPLPattern('앰버서더', 0.85, 'commercial_context', '브랜드 앰버서더'),
                PPLPattern('모델', 0.60, 'commercial_context', '브랜드 모델'),
            ],
            'purchase_guidance': [
                PPLPattern('구매하실 분들', 0.80, 'purchase_guidance', '구매 유도'),
                PPLPattern('관심있으신', 0.65, 'purchase_guidance', '관심 유도'),
                PPLPattern('궁금하신', 0.60, 'purchase_guidance', '문의 유도'),
                PPLPattern('아래', 0.85, 'purchase_guidance', '링크 안내'),
                PPLPattern('설명란', 0.70, 'purchase_guidance', '설명란 안내'),
                PPLPattern('더보기', 0.70, 'purchase_guidance', '더보기 안내'),
                PPLPattern('댓글', 0.65, 'purchase_guidance', '댓글 정보 안내'),
                PPLPattern('DM', 0.60, 'purchase_guidance', 'DM 문의 유도'),
                PPLPattern('참고', 0.60, 'purchase_guidance', '참고 안내'),
            ],
            'timing_patterns': [
                PPLPattern('오늘만', 0.75, 'timing_patterns', '한정 시간'),
                PPLPattern('지금 바로', 0.70, 'timing_patterns', '즉시 행동 유도'),
                PPLPattern('마감임박', 0.80, 'timing_patterns', '마감 압박'),
                PPLPattern('선착순', 0.75, 'timing_patterns', '선착순 압박'),
                PPLPattern('수량 한정', 0.70, 'timing_patterns', '수량 제한'),
            ]
        }
    
    @property
    def explicit_patterns(self) -> Dict[str, List[PPLPattern]]:
        """명시적 PPL 패턴 반환"""
        return self._explicit_patterns
    
    @property
    def implicit_patterns(self) -> Dict[str, List[PPLPattern]]:
        """암시적 PPL 패턴 반환"""
        return self._implicit_patterns
    
    def get_all_patterns(self) -> Dict[str, List[PPLPattern]]:
        """모든 PPL 패턴 반환"""
        all_patterns = {}
        all_patterns.update(self._explicit_patterns)
        all_patterns.update(self._implicit_patterns)
        return all_patterns
    
    def get_pattern_by_category(self, category: str) -> List[PPLPattern]:
        """카테고리별 패턴 반환"""
        all_patterns = self.get_all_patterns()
        return all_patterns.get(category, [])
    
    def get_high_weight_patterns(self, threshold: float = 0.8) -> List[PPLPattern]:
        """고가중치 패턴 반환"""
        high_weight_patterns = []
        for patterns in self.get_all_patterns().values():
            for pattern in patterns:
                if pattern.weight >= threshold:
                    high_weight_patterns.append(pattern)
        return high_weight_patterns


# 패턴 정의 싱글톤 인스턴스
ppl_patterns = PPLPatternDefinitions()