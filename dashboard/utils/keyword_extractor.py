"""
키워드 추출 및 확장 유틸리티
제품명으로부터 검색에 최적화된 키워드 생성
"""

import re
import json
from typing import List, Dict, Set
from pathlib import Path

class KeywordExtractor:
    """
    제품명 키워드 추출 및 확장 클래스
    """
    
    def __init__(self):
        self.synonyms = self._load_synonyms()
        self.brand_patterns = self._load_brand_patterns()
        self.category_keywords = self._load_category_keywords()
        
    def _load_synonyms(self) -> Dict[str, List[str]]:
        """
        동의어 사전 로드
        """
        return {
            # 화장품 관련
            '크림': ['크림', '로션', '에멀전', '겔', '밤'],
            '립스틱': ['립스틱', '립컬러', '립틴트', '입술연지', '루즈'],
            '파운데이션': ['파운데이션', '파데', 'BB크림', 'CC크림', '베이스'],
            '아이섀도': ['아이섀도', '아이섀도우', '섀도', '아이컬러'],
            '마스카라': ['마스카라', '마스카', '속눈썹 메이크업'],
            
            # 패션 관련
            '가방': ['가방', '백', '핸드백', '숄더백', '토트백', '클러치'],
            '신발': ['신발', '구두', '운동화', '스니커즈', '부츠', '샌들'],
            '옷': ['옷', '의류', '패션', '복장', '어패럴'],
            '액세서리': ['액세서리', '악세사리', '소품', '장신구'],
            
            # 전자제품
            '스마트폰': ['스마트폰', '휴대폰', '핸드폰', '모바일', '폰'],
            '노트북': ['노트북', '랩톱', '컴퓨터'],
            '이어폰': ['이어폰', '헤드폰', '이어버드', '무선이어폰'],
            
            # 생활용품
            '향수': ['향수', '퍼퓸', '프래그런스', '오드토왈렛'],
            '시계': ['시계', '워치', '손목시계'],
            '선글라스': ['선글라스', '썬글라스', '안경']
        }
    
    def _load_brand_patterns(self) -> List[str]:
        """
        브랜드명 패턴 로드
        """
        return [
            r'^[A-Za-z]{2,}\s+',           # 영문 브랜드 (2글자 이상)
            r'^[가-힣]{2,}\s+',            # 한글 브랜드 (2글자 이상)
            r'^\w+\s*[x×]\s*\w+\s+',      # 콜라보 브랜드 (A x B)
            r'^[A-Z]{2,}\s+',              # 대문자 브랜드
            r'^\d+\w*\s+',                 # 숫자로 시작하는 모델명
        ]
    
    def _load_category_keywords(self) -> Dict[str, List[str]]:
        """
        카테고리별 연관 키워드 로드
        """
        return {
            '뷰티': [
                '화장품', '코스메틱', '스킨케어', '메이크업', '뷰티',
                '기초화장품', '색조화장품', '향수', '케어'
            ],
            '패션': [
                '패션', '의류', '옷', '스타일', '룩', '아이템',
                '트렌드', '코디', '스타일링'
            ],
            '가전': [
                '가전', '전자제품', '디지털', '스마트', '기기',
                '가전제품', 'IT', '테크'
            ],
            '생활': [
                '생활용품', '라이프스타일', '홈', '인테리어',
                '데일리', '일상', '필수템'
            ],
            '건강': [
                '건강', '헬스', '웰니스', '케어', '관리',
                '영양', '운동', '피트니스'
            ]
        }
    
    def extract_base_keywords(self, product_name: str) -> List[str]:
        """
        기본 키워드 추출
        """
        if not product_name:
            return []
        
        keywords = []
        
        # 1. 원본 제품명
        keywords.append(product_name.strip())
        
        # 2. 소문자 변환
        lower_name = product_name.lower().strip()
        if lower_name != product_name.strip():
            keywords.append(lower_name)
        
        # 3. 특수문자 제거
        clean_name = re.sub(r'[^\w\s가-힣]', ' ', product_name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        if clean_name and clean_name not in keywords:
            keywords.append(clean_name)
        
        # 4. 브랜드명 제거 버전들
        for pattern in self.brand_patterns:
            no_brand = re.sub(pattern, '', product_name, flags=re.IGNORECASE).strip()
            if no_brand and len(no_brand) > 2 and no_brand not in keywords:
                keywords.append(no_brand)
        
        return keywords
    
    def extract_word_combinations(self, product_name: str) -> List[str]:
        """
        단어 조합 키워드 생성
        """
        # 단어 분리
        words = re.findall(r'\w+', product_name)
        words = [word for word in words if len(word) >= 2]  # 2글자 이상만
        
        combinations = []
        
        if len(words) >= 2:
            # 연속된 2개 단어 조합
            for i in range(len(words) - 1):
                combo = f"{words[i]} {words[i+1]}"
                combinations.append(combo)
            
            # 첫 번째와 마지막 단어
            if len(words) > 2:
                combinations.append(f"{words[0]} {words[-1]}")
            
            # 핵심 단어만 (명사 추정)
            # 한글 명사 패턴 (받침 있는 단어들)
            korean_nouns = [word for word in words if re.match(r'[가-힣]{2,}', word)]
            if len(korean_nouns) >= 2:
                combinations.append(' '.join(korean_nouns[:2]))
        
        return combinations
    
    def expand_with_synonyms(self, keywords: List[str]) -> List[str]:
        """
        동의어로 키워드 확장
        """
        expanded = list(keywords)  # 원본 키워드 포함
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for base_word, synonyms in self.synonyms.items():
                if base_word in keyword_lower:
                    # 동의어로 치환
                    for synonym in synonyms:
                        if synonym != base_word:
                            expanded_keyword = keyword_lower.replace(base_word, synonym)
                            if expanded_keyword not in expanded:
                                expanded.append(expanded_keyword)
        
        return expanded
    
    def add_category_keywords(self, product_name: str) -> List[str]:
        """
        카테고리 기반 연관 키워드 추가
        """
        category_keywords = []
        product_lower = product_name.lower()
        
        for category, keywords in self.category_keywords.items():
            # 카테고리 키워드가 제품명에 포함되어 있는지 확인
            for keyword in keywords:
                if any(word in product_lower for word in keyword.split()):
                    category_keywords.extend(keywords[:3])  # 상위 3개만
                    break
        
        return list(set(category_keywords))
    
    def generate_search_variations(self, product_name: str) -> List[str]:
        """
        검색 최적화 변형 생성
        """
        variations = []
        
        # 1. 추천/리뷰 키워드 추가
        base_keywords = [product_name]
        for base in base_keywords:
            variations.extend([
                f"{base} 추천",
                f"{base} 리뷰",
                f"{base} 후기",
                f"{base} 인기",
                f"{base} 베스트"
            ])
        
        # 2. 가격/할인 키워드
        variations.extend([
            f"{product_name} 가격",
            f"{product_name} 할인",
            f"{product_name} 세일"
        ])
        
        # 3. 비교 키워드
        variations.extend([
            f"{product_name} 비교",
            f"{product_name} 대안",
            f"{product_name} 유사"
        ])
        
        return variations
    
    def extract_all_keywords(self, product_name: str, max_keywords: int = 15) -> Dict[str, List[str]]:
        """
        모든 키워드 추출 통합 메소드
        """
        if not product_name or len(product_name.strip()) < 2:
            return {'keywords': [], 'error': '제품명이 너무 짧습니다.'}
        
        try:
            # 1. 기본 키워드 추출
            base_keywords = self.extract_base_keywords(product_name)
            
            # 2. 단어 조합 생성
            combinations = self.extract_word_combinations(product_name)
            
            # 3. 동의어 확장
            expanded = self.expand_with_synonyms(base_keywords + combinations)
            
            # 4. 카테고리 키워드 추가
            category_keywords = self.add_category_keywords(product_name)
            
            # 5. 검색 변형 생성
            search_variations = self.generate_search_variations(product_name)
            
            # 6. 모든 키워드 합치기
            all_keywords = (
                base_keywords +
                combinations + 
                expanded + 
                category_keywords + 
                search_variations
            )
            
            # 7. 중복 제거 및 정리
            unique_keywords = []
            seen = set()
            
            for keyword in all_keywords:
                keyword_clean = keyword.strip().lower()
                if (keyword_clean not in seen and 
                    len(keyword.strip()) >= 2 and 
                    len(keyword.strip()) <= 50):
                    unique_keywords.append(keyword.strip())
                    seen.add(keyword_clean)
                
                if len(unique_keywords) >= max_keywords:
                    break
            
            # 8. 우선순위별 정렬
            # 짧고 핵심적인 키워드를 앞에 배치
            def keyword_priority(keyword):
                score = 0
                # 길이 점수 (짧을수록 높음)
                score += max(0, 20 - len(keyword))
                # 원본 포함 여부
                if product_name.lower() in keyword.lower():
                    score += 30
                # 한글 포함 여부 (한국 상품이므로)
                if re.search(r'[가-힣]', keyword):
                    score += 10
                return score
            
            unique_keywords.sort(key=keyword_priority, reverse=True)
            
            return {
                'keywords': unique_keywords,
                'base_keywords': base_keywords,
                'combinations': combinations,
                'category_keywords': category_keywords,
                'total_generated': len(all_keywords),
                'final_count': len(unique_keywords)
            }
            
        except Exception as e:
            return {'keywords': [product_name], 'error': f'키워드 추출 중 오류: {str(e)}'}
    
    def suggest_alternative_searches(self, product_name: str, failed_keywords: List[str] = None) -> List[str]:
        """
        기존 검색 실패 시 대안 검색어 제안
        """
        suggestions = []
        
        # 실패한 키워드 제외
        failed_set = set(failed_keywords or [])
        
        # 더 일반적인 키워드 생성
        result = self.extract_all_keywords(product_name, max_keywords=20)
        all_keywords = result.get('keywords', [])
        
        for keyword in all_keywords:
            if keyword.lower() not in failed_set:
                suggestions.append(keyword)
                
        # 카테고리 기반 일반 검색어 추가
        category_suggestions = []
        for category, keywords in self.category_keywords.items():
            if any(word in product_name.lower() for word in keywords):
                category_suggestions.extend(keywords[:2])
        
        suggestions.extend(category_suggestions)
        
        # 중복 제거 및 길이순 정렬 (짧은 것부터)
        unique_suggestions = list(set(suggestions))
        unique_suggestions.sort(key=len)
        
        return unique_suggestions[:10]