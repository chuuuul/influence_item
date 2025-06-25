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
                PPLPattern('협찬', 0.98, 'direct_disclosure', '직접적인 협찬 공지'),
                PPLPattern('광고', 0.98, 'direct_disclosure', '직접적인 광고 표시'),
                PPLPattern('제공받은', 0.95, 'direct_disclosure', '제품 제공 공지'),
                PPLPattern('제공받았습니다', 0.95, 'direct_disclosure', '제품 제공 공지 정중형'),
                PPLPattern('sponsored', 0.98, 'direct_disclosure', '영문 스폰서 표시'),
                PPLPattern('AD', 0.98, 'direct_disclosure', '광고 약어'),
                PPLPattern('advertisement', 0.95, 'direct_disclosure', '영문 광고 표시'),
                PPLPattern('paid promotion', 0.90, 'direct_disclosure', '유료 프로모션'),
                PPLPattern('유료광고', 0.98, 'direct_disclosure', '유료광고 직접 표시'),
                # 새로운 명시적 패턴 추가 - 한국어 특화 및 강화
                PPLPattern('상업적 목적', 0.95, 'direct_disclosure', '상업적 목적 명시'),
                PPLPattern('제품 홍보', 0.92, 'direct_disclosure', '제품 홍보 목적'),
                PPLPattern('브랜드 협찬', 0.96, 'direct_disclosure', '브랜드 협찬 명시'),
                PPLPattern('마케팅 콘텐츠', 0.93, 'direct_disclosure', '마케팅 콘텐츠 표시'),
                PPLPattern('후원 콘텐츠', 0.94, 'direct_disclosure', '후원 콘텐츠 표시'),
                PPLPattern('협찬받은', 0.97, 'direct_disclosure', '협찬받은 제품 명시'),
                PPLPattern('제공받고', 0.95, 'direct_disclosure', '제공받고 제작'),
                PPLPattern('무료제공', 0.94, 'direct_disclosure', '무료제공 명시'),
                PPLPattern('체험단', 0.90, 'direct_disclosure', '체험단 활동'),
                PPLPattern('서포터즈', 0.88, 'direct_disclosure', '서포터즈 활동'),
            ],
            'hashtag_disclosure': [
                PPLPattern('#광고', 0.98, 'hashtag_disclosure', '해시태그 광고 공지'),
                PPLPattern('#협찬', 0.98, 'hashtag_disclosure', '해시태그 협찬 공지'),
                PPLPattern('#제공', 0.90, 'hashtag_disclosure', '해시태그 제품 제공'),
                PPLPattern('#AD', 0.98, 'hashtag_disclosure', '해시태그 광고 약어'),
                PPLPattern('#sponsored', 0.98, 'hashtag_disclosure', '해시태그 스폰서'),
                PPLPattern('#PR', 0.85, 'hashtag_disclosure', '해시태그 PR'),
                # 새로운 해시태그 패턴 추가
                PPLPattern('#유료광고', 0.99, 'hashtag_disclosure', '해시태그 유료광고'),
                PPLPattern('#상업적협찬', 0.95, 'hashtag_disclosure', '해시태그 상업적 협찬'),
                PPLPattern('#브랜드제공', 0.92, 'hashtag_disclosure', '해시태그 브랜드 제공'),
            ],
            'description_patterns': [
                PPLPattern('업체로부터 제품을 제공받아', 0.95, 'description_patterns', '제품 제공 설명'),
                PPLPattern('협찬을 받고 작성한', 0.95, 'description_patterns', '협찬 설명'),
                PPLPattern('광고가 포함된', 0.90, 'description_patterns', '광고 포함 고지'),
                PPLPattern('브랜드로부터 제공받은', 0.90, 'description_patterns', '브랜드 제공'),
                PPLPattern('마케팅 목적으로 제작된', 0.85, 'description_patterns', '마케팅 목적 고지'),
                # 새로운 설명 패턴 추가
                PPLPattern('제공받고 제작한', 0.92, 'description_patterns', '제공받고 제작'),
                PPLPattern('스폰서십으로 제작된', 0.94, 'description_patterns', '스폰서십 명시'),
                PPLPattern('상업적 파트너십', 0.88, 'description_patterns', '상업적 파트너십'),
                PPLPattern('브랜드와 협업하여', 0.85, 'description_patterns', '브랜드 협업'),
                PPLPattern('유료로 제작된', 0.96, 'description_patterns', '유료 제작 명시'),
            ]
        }
    
    def _load_implicit_patterns(self) -> Dict[str, List[PPLPattern]]:
        """암시적 PPL 패턴 로드"""
        return {
            'promotional_language': [
                PPLPattern('특가', 0.80, 'promotional_language', '특별가격 언급'),
                PPLPattern('할인', 0.75, 'promotional_language', '할인 언급'),
                PPLPattern('이벤트', 0.70, 'promotional_language', '이벤트 언급'),
                PPLPattern('프로모션', 0.80, 'promotional_language', '프로모션 언급'),
                PPLPattern('쿠폰', 0.85, 'promotional_language', '쿠폰 언급'),
                PPLPattern('상품정보', 0.70, 'promotional_language', '상품 정보 안내'),
                PPLPattern('한정판매', 0.75, 'promotional_language', '한정 판매'),
                PPLPattern('출시기념', 0.80, 'promotional_language', '출시 기념'),
                # 새로운 프로모션 언어 패턴 추가 - 가중치 강화
                PPLPattern('세일', 0.77, 'promotional_language', '세일 언급'),
                PPLPattern('특별혜택', 0.83, 'promotional_language', '특별 혜택'),
                PPLPattern('런칭기념', 0.78, 'promotional_language', '런칭 기념'),
                PPLPattern('런칭 혜택', 0.81, 'promotional_language', '런칭 혜택'),
                PPLPattern('신상 출시', 0.73, 'promotional_language', '신상품 출시'),
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
                PPLPattern('링크 아래', 0.90, 'purchase_guidance', '구매 링크 안내'),
                PPLPattern('구매링크', 0.95, 'purchase_guidance', '직접적 구매 링크'),
                PPLPattern('구매하실 분들', 0.87, 'purchase_guidance', '구매 유도'),
                PPLPattern('관심있으신', 0.73, 'purchase_guidance', '관심 유도'),
                PPLPattern('궁금하신', 0.68, 'purchase_guidance', '문의 유도'),
                PPLPattern('아래', 0.92, 'purchase_guidance', '링크 안내'),
                PPLPattern('설명란', 0.78, 'purchase_guidance', '설명란 안내'),
                PPLPattern('더보기', 0.78, 'purchase_guidance', '더보기 안내'),
                PPLPattern('댓글', 0.73, 'purchase_guidance', '댓글 정보 안내'),
                PPLPattern('DM', 0.68, 'purchase_guidance', 'DM 문의 유도'),
                PPLPattern('참고', 0.68, 'purchase_guidance', '참고 안내'),
                # 새로운 구매 유도 패턴 추가 - 가중치 강화
                PPLPattern('구매 문의', 0.90, 'purchase_guidance', '구매 문의 유도'),
                PPLPattern('주문 링크', 0.92, 'purchase_guidance', '주문 링크 안내'),
                PPLPattern('구입 가능', 0.80, 'purchase_guidance', '구입 가능성 안내'),
                PPLPattern('온라인샵', 0.85, 'purchase_guidance', '온라인 쇼핑'),
                PPLPattern('쇼핑몰', 0.83, 'purchase_guidance', '쇼핑몰 안내'),
            ],
            'timing_patterns': [
                PPLPattern('오늘만', 0.88, 'timing_patterns', '한정 시간'),
                PPLPattern('지금 바로', 0.85, 'timing_patterns', '즉시 행동 유도'),
                PPLPattern('마감임박', 0.93, 'timing_patterns', '마감 압박'),
                PPLPattern('선착순', 0.88, 'timing_patterns', '선착순 압박'),
                PPLPattern('수량 한정', 0.85, 'timing_patterns', '수량 제한'),
                # 추가 타이밍 압박 패턴 - 가중치 강화
                PPLPattern('한정시간', 0.88, 'timing_patterns', '한정 시간'),
                PPLPattern('기간한정', 0.85, 'timing_patterns', '기간 한정'),
                PPLPattern('지금만', 0.87, 'timing_patterns', '지금만'),
                PPLPattern('당일 마감', 0.91, 'timing_patterns', '당일 마감'),
                PPLPattern('이벤트 마감', 0.80, 'timing_patterns', '이벤트 마감'),
                PPLPattern('24시간 한정', 0.90, 'timing_patterns', '24시간 한정'),
                PPLPattern('한정수량', 0.87, 'timing_patterns', '한정수량'),
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