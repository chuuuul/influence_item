"""
스마트 제품 검색 시스템
쿠팡 API 실패 시 대안 검색 솔루션 제공
"""

import streamlit as st
import requests
import re
import time
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import json

class SmartSearch:
    """
    반자동 보조 검색 시스템
    쿠팡 상품 매칭 실패 시 다중 플랫폼 대안 검색 제공
    """
    
    def __init__(self):
        self.search_history = []
        self.cached_results = {}
        
    def extract_keywords(self, product_name: str) -> List[str]:
        """
        제품명에서 핵심 키워드 추출 및 확장
        """
        if not product_name:
            return []
            
        # 기본 키워드 추출
        keywords = []
        
        # 1. 원본 제품명
        keywords.append(product_name)
        
        # 2. 브랜드명 제거 버전
        # 일반적인 브랜드 패턴 제거
        brand_patterns = [
            r'^[A-Za-z]+\s+',  # 영문 브랜드명
            r'^\S+\s+',        # 첫 번째 단어 (브랜드로 가정)
        ]
        
        for pattern in brand_patterns:
            no_brand = re.sub(pattern, '', product_name).strip()
            if no_brand and no_brand != product_name:
                keywords.append(no_brand)
        
        # 3. 특수문자 및 괄호 제거
        clean_name = re.sub(r'[^\w\s가-힣]', ' ', product_name).strip()
        if clean_name and clean_name not in keywords:
            keywords.append(clean_name)
        
        # 4. 주요 단어만 추출 (2글자 이상)
        words = clean_name.split()
        main_words = [word for word in words if len(word) >= 2]
        if len(main_words) >= 2:
            keywords.append(' '.join(main_words[:2]))  # 앞의 2단어
        
        # 5. 카테고리 키워드 추가
        category_mappings = {
            '크림': ['크림', '화장품', '스킨케어'],
            '비비크림': ['비비크림', 'BB크림', '베이스 메이크업'],
            '립스틱': ['립스틱', '립컬러', '입술화장품'],
            '가방': ['가방', '핸드백', '숄더백'],
            '신발': ['신발', '운동화', '구두'],
            '의류': ['옷', '의류', '패션'],
        }
        
        for category, related_terms in category_mappings.items():
            if category in product_name.lower():
                keywords.extend(related_terms)
        
        # 중복 제거 및 정리
        unique_keywords = []
        for keyword in keywords:
            if keyword and keyword.strip() and keyword not in unique_keywords:
                unique_keywords.append(keyword.strip())
        
        return unique_keywords[:10]  # 최대 10개 키워드
    
    def search_naver(self, keyword: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        네이버 쇼핑 검색
        """
        try:
            # 네이버 쇼핑 검색 URL 생성
            encoded_keyword = quote_plus(keyword)
            search_url = f"https://search.shopping.naver.com/search/all?query={encoded_keyword}"
            
            # 실제 API가 없으므로 모의 결과 반환
            mock_results = [
                {
                    'title': f'{keyword} - 네이버 쇼핑 상품 1',
                    'price': '29,900원',
                    'url': search_url,
                    'image_url': 'https://via.placeholder.com/150',
                    'platform': 'naver',
                    'rating': 4.5,
                    'review_count': 123
                },
                {
                    'title': f'{keyword} - 네이버 쇼핑 상품 2',
                    'price': '35,000원',
                    'url': search_url,
                    'image_url': 'https://via.placeholder.com/150',
                    'platform': 'naver',
                    'rating': 4.2,
                    'review_count': 89
                }
            ]
            
            return mock_results[:max_results]
            
        except Exception as e:
            st.error(f"네이버 검색 중 오류: {str(e)}")
            return []
    
    def search_11st(self, keyword: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        11번가 검색
        """
        try:
            encoded_keyword = quote_plus(keyword)
            search_url = f"https://search.11st.co.kr/MW/search?searchKeyword={encoded_keyword}"
            
            mock_results = [
                {
                    'title': f'{keyword} - 11번가 상품 1',
                    'price': '27,500원',
                    'url': search_url,
                    'image_url': 'https://via.placeholder.com/150',
                    'platform': '11st',
                    'rating': 4.3,
                    'review_count': 67
                },
                {
                    'title': f'{keyword} - 11번가 상품 2',
                    'price': '31,900원',
                    'url': search_url,
                    'image_url': 'https://via.placeholder.com/150',
                    'platform': '11st',
                    'rating': 4.1,
                    'review_count': 45
                }
            ]
            
            return mock_results[:max_results]
            
        except Exception as e:
            st.error(f"11번가 검색 중 오류: {str(e)}")
            return []
    
    def search_amazon(self, keyword: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        아마존 검색 (한국 상품 우선)
        """
        try:
            encoded_keyword = quote_plus(keyword)
            search_url = f"https://www.amazon.com/s?k={encoded_keyword}"
            
            mock_results = [
                {
                    'title': f'{keyword} - Amazon Product 1',
                    'price': '$25.99',
                    'url': search_url,
                    'image_url': 'https://via.placeholder.com/150',
                    'platform': 'amazon',
                    'rating': 4.4,
                    'review_count': 234
                }
            ]
            
            return mock_results[:max_results]
            
        except Exception as e:
            st.error(f"아마존 검색 중 오류: {str(e)}")
            return []
    
    def analyze_image_similarity(self, product_image_url: str, search_results: List[Dict]) -> List[Dict]:
        """
        이미지 기반 유사도 분석 (Google Vision API 대안)
        """
        try:
            # 실제 이미지 분석 대신 모의 유사도 점수 추가
            for result in search_results:
                # 간단한 휴리스틱으로 유사도 점수 계산
                similarity_score = 0.8 + (hash(result['title']) % 20) / 100  # 0.8~0.99
                result['image_similarity'] = min(similarity_score, 0.99)
                
            # 유사도 순으로 정렬
            search_results.sort(key=lambda x: x.get('image_similarity', 0), reverse=True)
            
            return search_results
            
        except Exception as e:
            st.error(f"이미지 유사도 분석 중 오류: {str(e)}")
            return search_results
    
    def calculate_recommendation_score(self, result: Dict[str, Any]) -> float:
        """
        가격, 평점, 리뷰 수를 종합한 추천 점수 계산
        """
        try:
            # 평점 점수 (40%)
            rating_score = result.get('rating', 0) / 5.0
            
            # 리뷰 수 점수 (30%) - 로그 스케일
            review_count = result.get('review_count', 1)
            review_score = min(1.0, (review_count / 1000) ** 0.5)
            
            # 이미지 유사도 점수 (30%)
            similarity_score = result.get('image_similarity', 0.5)
            
            # 종합 점수 계산
            total_score = (rating_score * 0.4) + (review_score * 0.3) + (similarity_score * 0.3)
            
            return min(total_score, 1.0)
            
        except Exception as e:
            return 0.5
    
    def search_multi_platform(self, product_name: str, product_image_url: str = None) -> Dict[str, Any]:
        """
        다중 플랫폼 통합 검색 실행
        """
        if not product_name:
            return {'success': False, 'message': '제품명이 필요합니다.'}
        
        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 1. 키워드 추출
            status_text.text("키워드 추출 중...")
            progress_bar.progress(10)
            keywords = self.extract_keywords(product_name)
            
            if not keywords:
                return {'success': False, 'message': '키워드 추출에 실패했습니다.'}
            
            # 2. 플랫폼별 검색
            all_results = []
            platforms = [
                ('naver', self.search_naver),
                ('11st', self.search_11st),
                ('amazon', self.search_amazon)
            ]
            
            for i, (platform_name, search_func) in enumerate(platforms):
                status_text.text(f"{platform_name} 검색 중...")
                progress_bar.progress(20 + (i * 20))
                
                for keyword in keywords[:3]:  # 상위 3개 키워드만 사용
                    results = search_func(keyword, max_results=3)
                    for result in results:
                        result['keyword_used'] = keyword
                        result['search_rank'] = len(all_results) + 1
                    all_results.extend(results)
                    
                    time.sleep(0.1)  # 요청 간격
            
            # 3. 이미지 유사도 분석
            if product_image_url:
                status_text.text("이미지 유사도 분석 중...")
                progress_bar.progress(80)
                all_results = self.analyze_image_similarity(product_image_url, all_results)
            
            # 4. 추천 점수 계산
            status_text.text("결과 분석 중...")
            progress_bar.progress(90)
            
            for result in all_results:
                result['recommendation_score'] = self.calculate_recommendation_score(result)
            
            # 5. 결과 정렬 (추천 점수 순)
            all_results.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            # 6. 중복 제거 (제목 유사도 기반)
            unique_results = []
            seen_titles = set()
            
            for result in all_results:
                title_key = re.sub(r'[^\w가-힣]', '', result['title']).lower()
                if title_key not in seen_titles:
                    unique_results.append(result)
                    seen_titles.add(title_key)
                    
                if len(unique_results) >= 10:  # 최대 10개 결과
                    break
            
            progress_bar.progress(100)
            status_text.text("검색 완료!")
            
            # 검색 기록 저장
            search_record = {
                'timestamp': time.time(),
                'product_name': product_name,
                'keywords_used': keywords,
                'total_results': len(unique_results),
                'platforms_searched': [p[0] for p in platforms]
            }
            self.search_history.append(search_record)
            
            return {
                'success': True,
                'results': unique_results,
                'keywords_used': keywords,
                'search_info': search_record
            }
            
        except Exception as e:
            progress_bar.progress(100)
            status_text.text(f"검색 중 오류 발생: {str(e)}")
            return {'success': False, 'message': f'검색 중 오류: {str(e)}'}
        
        finally:
            # UI 요소 정리
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
    
    def manual_search(self, custom_keyword: str) -> List[Dict[str, Any]]:
        """
        사용자 정의 키워드로 수동 검색
        """
        if not custom_keyword:
            return []
        
        st.info(f"수동 검색 키워드: '{custom_keyword}'")
        
        # 모든 플랫폼에서 사용자 키워드로 검색
        results = []
        results.extend(self.search_naver(custom_keyword, 3))
        results.extend(self.search_11st(custom_keyword, 3))
        results.extend(self.search_amazon(custom_keyword, 2))
        
        # 추천 점수 계산
        for result in results:
            result['recommendation_score'] = self.calculate_recommendation_score(result)
            result['keyword_used'] = custom_keyword
            result['search_type'] = 'manual'
        
        # 점수순 정렬
        results.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        return results
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """
        검색 통계 정보 반환
        """
        if not self.search_history:
            return {'total_searches': 0}
        
        total_searches = len(self.search_history)
        total_results = sum(record['total_results'] for record in self.search_history)
        avg_results = total_results / total_searches if total_searches > 0 else 0
        
        # 가장 많이 사용된 플랫폼
        platform_counts = {}
        for record in self.search_history:
            for platform in record.get('platforms_searched', []):
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        most_used_platform = max(platform_counts.items(), key=lambda x: x[1])[0] if platform_counts else None
        
        return {
            'total_searches': total_searches,
            'total_results_found': total_results,
            'average_results_per_search': round(avg_results, 1),
            'most_used_platform': most_used_platform,
            'platform_usage': platform_counts
        }