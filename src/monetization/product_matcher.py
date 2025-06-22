"""
제품 매칭 및 검색 최적화 모듈

AI가 추출한 제품명을 쿠팡 API 검색에 최적화된 키워드로 변환하고,
검색 결과와의 매칭 신뢰도를 계산합니다.
"""

import re
import difflib
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProductMatch:
    """제품 매칭 결과"""
    product_data: Dict[str, Any]
    similarity_score: float
    match_confidence: float
    match_reasons: List[str]
    click_url: str
    image_url: str
    price: int
    original_price: int
    commission_rate: float


class ProductMatcher:
    """제품 매칭 및 검색 최적화 클래스"""
    
    def __init__(self):
        """제품 매칭 초기화"""
        self.brand_patterns = {
            # 한국 브랜드
            '아디다스': ['adidas', '아디다스'],
            '나이키': ['nike', '나이키'],
            '에뛰드': ['etude', 'etude house', '에뛰드'],
            '이니스프리': ['innisfree', '이니스프리'],
            '라네즈': ['laneige', '라네즈'],
            '설화수': ['sulwhasoo', '설화수'],
            '헤라': ['hera', '헤라'],
            # 해외 브랜드
            '샤넬': ['chanel', '샤넬'],
            '디올': ['dior', '디올'],
            '에르메스': ['hermes', '에르메스'],
            '구찌': ['gucci', '구찌'],
            '루이비통': ['louis vuitton', 'lv', '루이비통']
        }
        
        self.category_keywords = {
            '화장품': ['립스틱', '파운데이션', '아이섀도', '마스카라', '블러셔', '컨실러'],
            '스킨케어': ['토너', '세럼', '크림', '클렌징', '선크림', '마스크팩'],
            '패션': ['가방', '지갑', '신발', '옷', '악세서리', '시계'],
            '전자제품': ['폰', '이어폰', '스피커', '카메라', '노트북'],
            '생활용품': ['향수', '샴푸', '바디워시', '치약']
        }
        
        logger.info("제품 매칭 시스템 초기화 완료")
        
    def optimize_search_keyword(self, product_name: str) -> List[str]:
        """
        AI 추출 제품명을 쿠팡 검색 최적화 키워드로 변환
        
        Args:
            product_name: AI가 추출한 제품명
            
        Returns:
            최적화된 검색 키워드 리스트 (우선순위 순)
        """
        logger.info(f"검색 키워드 최적화 시작: '{product_name}'")
        
        keywords = []
        
        # 1. 원본 제품명 (괄호 제거)
        clean_name = re.sub(r'\([^)]*\)', '', product_name).strip()
        keywords.append(clean_name)
        
        # 2. 브랜드명 추출 및 변형
        brand_variants = self._extract_brand_variants(product_name)
        for variant in brand_variants:
            if variant not in keywords:
                keywords.append(variant)
                
        # 3. 핵심 키워드 조합
        core_keywords = self._extract_core_keywords(clean_name)
        if len(core_keywords) >= 2:
            keywords.append(' '.join(core_keywords[:2]))
            
        # 4. 단일 핵심 키워드
        for keyword in core_keywords:
            if len(keyword) > 2 and keyword not in keywords:
                keywords.append(keyword)
                
        # 5. 카테고리 기반 키워드
        category_keywords = self._generate_category_keywords(product_name)
        keywords.extend(category_keywords)
        
        # 중복 제거 및 우선순위 정렬
        final_keywords = []
        seen = set()
        
        for keyword in keywords:
            if keyword and keyword not in seen and len(keyword.strip()) > 1:
                final_keywords.append(keyword.strip())
                seen.add(keyword)
                
        logger.info(f"최적화된 키워드 생성: {final_keywords}")
        return final_keywords[:5]  # 최대 5개
        
    def _extract_brand_variants(self, product_name: str) -> List[str]:
        """브랜드명 추출 및 변형"""
        variants = []
        product_lower = product_name.lower()
        
        for korean_brand, english_variants in self.brand_patterns.items():
            if korean_brand in product_name:
                variants.extend(english_variants)
                variants.append(korean_brand)
            
            for eng_brand in english_variants:
                if eng_brand in product_lower:
                    variants.append(korean_brand)
                    variants.extend(english_variants)
                    break
                    
        return list(set(variants))
        
    def _extract_core_keywords(self, product_name: str) -> List[str]:
        """핵심 키워드 추출"""
        # 불용어 제거
        stop_words = {'의', '이', '가', '을', '를', '에', '에서', '으로', '로', '와', '과', '도'}
        
        # 단어 분리 (공백, 특수문자 기준)
        words = re.findall(r'\w+', product_name)
        
        # 불용어 제거 및 길이 필터링
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        return keywords
        
    def _generate_category_keywords(self, product_name: str) -> List[str]:
        """카테고리 기반 키워드 생성"""
        keywords = []
        product_lower = product_name.lower()
        
        for category, category_keywords in self.category_keywords.items():
            for keyword in category_keywords:
                if keyword in product_lower or keyword in product_name:
                    keywords.append(keyword)
                    
        return keywords
        
    def calculate_product_similarity(self, ai_product_name: str, coupang_product: Dict[str, Any]) -> float:
        """
        AI 추출 제품명과 쿠팡 제품 정보 간 유사도 계산
        
        Args:
            ai_product_name: AI가 추출한 제품명
            coupang_product: 쿠팡 API 제품 데이터
            
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        """
        try:
            coupang_name = coupang_product.get('productName', '')
            
            if not coupang_name:
                return 0.0
                
            # 1. 문자열 유사도 (SequenceMatcher)
            sequence_similarity = difflib.SequenceMatcher(None, ai_product_name.lower(), coupang_name.lower()).ratio()
            
            # 2. 공통 단어 비율
            ai_words = set(re.findall(r'\w+', ai_product_name.lower()))
            coupang_words = set(re.findall(r'\w+', coupang_name.lower()))
            
            if len(ai_words) == 0:
                word_similarity = 0.0
            else:
                common_words = ai_words.intersection(coupang_words)
                word_similarity = len(common_words) / len(ai_words)
            
            # 3. 브랜드명 매칭 보너스
            brand_bonus = 0.0
            for korean_brand, english_variants in self.brand_patterns.items():
                if korean_brand in ai_product_name and korean_brand in coupang_name:
                    brand_bonus = 0.2
                    break
                for eng_brand in english_variants:
                    if (eng_brand in ai_product_name.lower() and eng_brand in coupang_name.lower()):
                        brand_bonus = 0.2
                        break
                        
            # 가중 평균 계산
            final_similarity = (
                0.4 * sequence_similarity +
                0.4 * word_similarity +
                0.2 * brand_bonus
            )
            
            return min(1.0, final_similarity)
            
        except Exception as e:
            logger.error(f"유사도 계산 중 오류: {str(e)}")
            return 0.0
            
    def evaluate_search_results(self, ai_product_name: str, search_results: List[Dict[str, Any]], 
                              min_similarity: float = 0.6) -> List[ProductMatch]:
        """
        검색 결과 평가 및 매칭
        
        Args:
            ai_product_name: AI가 추출한 제품명
            search_results: 쿠팡 API 검색 결과
            min_similarity: 최소 유사도 임계값
            
        Returns:
            매칭된 제품 리스트 (신뢰도 순)
        """
        logger.info(f"검색 결과 평가 시작: {len(search_results)}개 제품")
        
        matches = []
        
        for product in search_results:
            try:
                # 유사도 계산
                similarity = self.calculate_product_similarity(ai_product_name, product)
                
                if similarity >= min_similarity:
                    # 매칭 신뢰도 계산
                    confidence = self._calculate_match_confidence(ai_product_name, product, similarity)
                    
                    # 매칭 이유 생성
                    reasons = self._generate_match_reasons(ai_product_name, product, similarity)
                    
                    match = ProductMatch(
                        product_data=product,
                        similarity_score=similarity,
                        match_confidence=confidence,
                        match_reasons=reasons,
                        click_url=product.get('productUrl', ''),
                        image_url=product.get('productImage', ''),
                        price=product.get('productPrice', 0),
                        original_price=product.get('originalPrice', 0),
                        commission_rate=product.get('commissionRate', 0.0)
                    )
                    
                    matches.append(match)
                    
            except Exception as e:
                logger.warning(f"제품 매칭 평가 중 오류: {str(e)}")
                continue
                
        # 신뢰도 순으로 정렬
        matches.sort(key=lambda x: x.match_confidence, reverse=True)
        
        logger.info(f"매칭 완료: {len(matches)}개 제품 매칭됨")
        return matches
        
    def _calculate_match_confidence(self, ai_name: str, product: Dict[str, Any], similarity: float) -> float:
        """매칭 신뢰도 계산"""
        confidence = similarity
        
        # 가격 정보가 있으면 보너스
        if product.get('productPrice', 0) > 0:
            confidence += 0.1
            
        # 이미지가 있으면 보너스
        if product.get('productImage'):
            confidence += 0.05
            
        # 높은 평점이면 보너스
        rating = product.get('rating', 0)
        if rating >= 4.0:
            confidence += 0.05
            
        return min(1.0, confidence)
        
    def _generate_match_reasons(self, ai_name: str, product: Dict[str, Any], similarity: float) -> List[str]:
        """매칭 이유 생성"""
        reasons = []
        
        if similarity >= 0.8:
            reasons.append("제품명 높은 유사도")
        elif similarity >= 0.6:
            reasons.append("제품명 유사도 양호")
            
        # 브랜드 매칭 확인
        product_name = product.get('productName', '').lower()
        for korean_brand, english_variants in self.brand_patterns.items():
            if korean_brand in ai_name and korean_brand in product_name:
                reasons.append(f"브랜드명 매칭: {korean_brand}")
                break
                
        # 가격 정보
        price = product.get('productPrice', 0)
        if price > 0:
            reasons.append(f"가격 정보 확인됨: {price:,}원")
            
        # 평점 정보
        rating = product.get('rating', 0)
        if rating >= 4.0:
            reasons.append(f"높은 평점: {rating}/5.0")
            
        return reasons