"""
T03_S02_M02: 외부 검색 연동 기능 - 검색 쿼리 생성 알고리즘
제품 정보를 기반으로 Google/네이버 검색에 최적화된 쿼리를 생성하는 모듈
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus
import logging

logger = logging.getLogger(__name__)

class SearchQueryBuilder:
    """검색 쿼리 생성 및 최적화 클래스"""
    
    def __init__(self):
        # 검색 쿼리에서 제거할 불용어들
        self.stop_words = {
            '정말', '진짜', '완전', '매우', '너무', '아주', '엄청', '정말로',
            '이거', '이것', '그거', '그것', '저거', '저것', '요거', '요것',
            '좀', '좀더', '조금', '살짝', '약간', '대충', '그냥', '막',
            '사용', '써보니', '써봤는데', '사용해보니', '사용했는데',
            '추천', '추천해요', '추천합니다', '강추', '강력추천'
        }
        
        # 브랜드명 정규화 매핑
        self.brand_normalization = {
            '라네즈': 'LANEIGE',
            '설화수': '雪花秀',
            '헤라': 'HERA',
            '이니스프리': 'innisfree',
            '에뛰드': 'ETUDE',
            '미샤': 'MISSHA',
            '더페이스샵': 'THE FACE SHOP',
            'sk2': 'SK-II',
            'sk-2': 'SK-II'
        }
        
        # 카테고리별 핵심 키워드
        self.category_keywords = {
            '스킨케어': ['스킨케어', '기초화장품'],
            '메이크업': ['메이크업', '화장품'],
            '헤어': ['헤어', '모발', '헤어케어'],
            '바디': ['바디', '바디케어', '보디케어'],
            '향수': ['향수', '퍼퓸', '프래그런스'],
            '패션': ['패션', '의류', '옷'],
            '가방': ['가방', '백', 'bag'],
            '액세서리': ['액세서리', '장신구'],
            '신발': ['신발', '슈즈', 'shoes']
        }
    
    def extract_brand_and_product(self, product_name: str) -> Tuple[Optional[str], str]:
        """제품명에서 브랜드와 제품명을 분리"""
        if not product_name:
            return None, ""
        
        # 일반적인 브랜드-제품 패턴 검색
        patterns = [
            r'^([가-힣A-Za-z\-&\s]+?)\s*[-–]\s*(.+)$',  # 브랜드 - 제품명
            r'^([가-힣A-Za-z\-&\s]+?)\s+(.+)$',        # 브랜드 제품명 (공백으로 구분)
            r'^\[([^\]]+)\]\s*(.+)$',                   # [브랜드] 제품명
            r'^([A-Z][A-Za-z\-&\s]*?)\s+(.+)$'        # 영문 브랜드명 패턴
        ]
        
        for pattern in patterns:
            match = re.match(pattern, product_name.strip())
            if match:
                brand = match.group(1).strip()
                product = match.group(2).strip()
                
                # 브랜드 정규화
                brand = self.brand_normalization.get(brand.lower(), brand)
                
                return brand, product
        
        # 패턴 매치 실패 시 전체를 제품명으로 처리
        return None, product_name
    
    def clean_product_name(self, product_name: str) -> str:
        """제품명에서 불필요한 단어 제거 및 정제"""
        if not product_name:
            return ""
        
        # 괄호 안 내용 제거 (용량, 옵션 정보 등)
        cleaned = re.sub(r'\([^)]*\)', '', product_name)
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
        
        # 불용어 제거
        words = cleaned.split()
        filtered_words = [word for word in words if word not in self.stop_words]
        
        # 특수문자 정리 (검색에 유용한 것은 유지)
        cleaned = ' '.join(filtered_words)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def generate_search_queries(
        self, 
        candidate_info: Dict, 
        source_info: Dict = None,
        max_queries: int = 3
    ) -> Dict[str, List[str]]:
        """
        후보 정보를 기반으로 다양한 검색 쿼리 생성
        
        Args:
            candidate_info: 제품 후보 정보
            source_info: 영상 소스 정보 (선택적)
            max_queries: 생성할 최대 쿼리 수
            
        Returns:
            검색 엔진별 쿼리 리스트
        """
        product_name = candidate_info.get('product_name_ai', '')
        category_path = candidate_info.get('category_path', [])
        features = candidate_info.get('features', [])
        
        # 연예인/채널 정보
        celebrity_name = ""
        if source_info:
            celebrity_name = source_info.get('celebrity_name', '')
            if not celebrity_name:
                celebrity_name = source_info.get('channel_name', '')
        
        # 브랜드와 제품명 분리
        brand, clean_product = self.extract_brand_and_product(product_name)
        clean_product = self.clean_product_name(clean_product)
        
        # 카테고리 키워드 추출
        category_keywords = []
        for category in category_path:
            if category in self.category_keywords:
                category_keywords.extend(self.category_keywords[category])
        
        # 쿼리 생성 전략들
        queries = []
        
        # 1. 기본 제품명 검색
        if clean_product:
            queries.append(clean_product)
        
        # 2. 브랜드 + 제품명
        if brand and clean_product:
            queries.append(f"{brand} {clean_product}")
        
        # 3. 연예인 + 제품명 (연예인 정보가 있는 경우)
        if celebrity_name and clean_product:
            queries.append(f"{celebrity_name} {clean_product}")
            
        # 4. 카테고리 + 제품명
        if category_keywords and clean_product:
            primary_category = category_keywords[0]
            queries.append(f"{primary_category} {clean_product}")
        
        # 5. 제품 특징 포함 (주요 특징 1개)
        if features and clean_product:
            main_feature = features[0]
            if len(main_feature) < 10:  # 짧은 특징만 사용
                queries.append(f"{clean_product} {main_feature}")
        
        # 6. 브랜드 + 카테고리 (제품명이 너무 길거나 복잡한 경우)
        if brand and category_keywords:
            queries.append(f"{brand} {category_keywords[0]}")
        
        # 중복 제거 및 길이 제한
        unique_queries = []
        seen = set()
        
        for query in queries:
            query = query.strip()
            if query and query not in seen and len(query) >= 2:
                unique_queries.append(query)
                seen.add(query)
                
                if len(unique_queries) >= max_queries:
                    break
        
        # 검색 엔진별 쿼리 최적화
        google_queries = self._optimize_for_google(unique_queries)
        naver_queries = self._optimize_for_naver(unique_queries)
        
        return {
            'google': google_queries,
            'naver': naver_queries,
            'base': unique_queries
        }
    
    def _optimize_for_google(self, base_queries: List[str]) -> List[str]:
        """Google 검색에 최적화된 쿼리 생성"""
        optimized = []
        
        for query in base_queries:
            # Google은 영문 브랜드명에 강함
            # 따옴표로 정확한 매치 강화
            if any(char.isalpha() and ord(char) < 128 for char in query):
                # 영문이 포함된 경우 정확 검색 적용
                if ' ' in query:
                    optimized.append(f'"{query}"')
                else:
                    optimized.append(query)
            else:
                optimized.append(query)
        
        return optimized
    
    def _optimize_for_naver(self, base_queries: List[str]) -> List[str]:
        """네이버 검색에 최적화된 쿼리 생성"""
        optimized = []
        
        for query in base_queries:
            # 네이버는 한글 검색에 강함
            # 추가 한글 키워드 보강
            optimized_query = query
            
            # '추천', '후기' 키워드 추가로 관련도 향상
            if not any(keyword in query for keyword in ['추천', '후기', '리뷰']):
                optimized_query = f"{query} 추천"
            
            optimized.append(optimized_query)
        
        return optimized
    
    def build_search_urls(
        self, 
        candidate_info: Dict, 
        source_info: Dict = None
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        검색 URL들을 생성
        
        Returns:
            검색 엔진별 URL 리스트 (쿼리, URL, 타입 포함)
        """
        queries = self.generate_search_queries(candidate_info, source_info)
        
        search_urls = {
            'google': [],
            'naver': []
        }
        
        # Google 검색 URL 생성
        for i, query in enumerate(queries['google'][:3]):  # 최대 3개
            encoded_query = quote_plus(query)
            
            # 텍스트 검색
            text_url = f"https://www.google.com/search?q={encoded_query}&hl=ko&gl=KR"
            search_urls['google'].append({
                'query': query,
                'url': text_url,
                'type': 'text',
                'label': f"Google 검색 {i+1}"
            })
            
            # 이미지 검색
            image_url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&hl=ko&gl=KR"
            search_urls['google'].append({
                'query': query,
                'url': image_url,
                'type': 'image',
                'label': f"Google 이미지 {i+1}"
            })
        
        # 네이버 검색 URL 생성
        for i, query in enumerate(queries['naver'][:3]):  # 최대 3개
            encoded_query = quote_plus(query)
            
            # 통합 검색
            text_url = f"https://search.naver.com/search.naver?query={encoded_query}"
            search_urls['naver'].append({
                'query': query,
                'url': text_url,
                'type': 'text',
                'label': f"네이버 검색 {i+1}"
            })
            
            # 이미지 검색
            image_url = f"https://search.naver.com/search.naver?where=image&query={encoded_query}"
            search_urls['naver'].append({
                'query': query,
                'url': image_url,
                'type': 'image',
                'label': f"네이버 이미지 {i+1}"
            })
            
            # 쇼핑 검색 (상품인 경우 유용)
            shopping_url = f"https://search.shopping.naver.com/search/all?query={encoded_query}"
            search_urls['naver'].append({
                'query': query,
                'url': shopping_url,
                'type': 'shopping',
                'label': f"네이버 쇼핑 {i+1}"
            })
        
        return search_urls

    def get_image_search_urls(
        self, 
        candidate_info: Dict, 
        image_file_path: str = None
    ) -> Dict[str, str]:
        """
        이미지 기반 역검색 URL 생성
        
        Args:
            candidate_info: 제품 후보 정보
            image_file_path: 이미지 파일 경로 (선택적)
            
        Returns:
            이미지 검색 URL들
        """
        product_name = candidate_info.get('product_name_ai', '')
        
        # 기본 이미지 검색 URL (텍스트 기반)
        urls = {}
        
        if product_name:
            encoded_query = quote_plus(product_name)
            
            # Google Lens (이미지 업로드 방식은 별도 구현 필요)
            urls['google_lens'] = "https://lens.google.com/"
            
            # Google 이미지 검색
            urls['google_images'] = f"https://www.google.com/search?q={encoded_query}&tbm=isch&hl=ko&gl=KR"
            
            # 네이버 이미지 검색
            urls['naver_images'] = f"https://search.naver.com/search.naver?where=image&query={encoded_query}"
        
        return urls


def test_search_query_builder():
    """검색 쿼리 빌더 테스트"""
    builder = SearchQueryBuilder()
    
    # 테스트 데이터
    test_candidate = {
        "product_name_ai": "라네즈 - 수분크림 프리미엄",
        "category_path": ["스킨케어", "크림", "수분크림"],
        "features": ["높은 보습력", "빠른 흡수", "끈적임 없음"]
    }
    
    test_source = {
        "celebrity_name": "아이유",
        "channel_name": "아이유 공식채널"
    }
    
    # 쿼리 생성 테스트
    queries = builder.generate_search_queries(test_candidate, test_source)
    print("생성된 검색 쿼리:")
    for engine, query_list in queries.items():
        print(f"{engine}: {query_list}")
    
    # URL 생성 테스트
    urls = builder.build_search_urls(test_candidate, test_source)
    print("\n생성된 검색 URL:")
    for engine, url_list in urls.items():
        print(f"\n{engine}:")
        for url_info in url_list:
            print(f"  {url_info['label']}: {url_info['url']}")


if __name__ == "__main__":
    test_search_query_builder()