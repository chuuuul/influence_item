"""
이미지 유사도 분석 유틸리티
Google Vision API 대안으로 간단한 이미지 분석 제공
"""

import requests
import hashlib
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import base64
from io import BytesIO
import streamlit as st

class ImageSimilarityAnalyzer:
    """
    이미지 유사도 분석 클래스
    실제 Vision API 대신 휴리스틱 방법 사용
    """
    
    def __init__(self):
        self.cache = {}
        self.analysis_cache = {}
        
    def extract_image_features(self, image_url: str) -> Dict[str, Any]:
        """
        이미지에서 특징 추출
        실제로는 URL 패턴과 메타데이터를 분석
        """
        try:
            # URL 파싱
            parsed_url = urlparse(image_url)
            
            # 기본 특징 추출
            features = {
                'url_hash': hashlib.md5(image_url.encode()).hexdigest()[:8],
                'domain': parsed_url.netloc,
                'file_type': self._guess_file_type(image_url),
                'estimated_category': self._guess_category_from_url(image_url),
                'url_keywords': self._extract_url_keywords(image_url)
            }
            
            # 캐시에 저장
            self.cache[image_url] = features
            
            return features
            
        except Exception as e:
            return {
                'url_hash': 'unknown',
                'domain': 'unknown',
                'file_type': 'unknown',
                'estimated_category': 'general',
                'url_keywords': [],
                'error': str(e)
            }
    
    def _guess_file_type(self, url: str) -> str:
        """
        URL에서 파일 타입 추측
        """
        url_lower = url.lower()
        if '.jpg' in url_lower or '.jpeg' in url_lower:
            return 'jpeg'
        elif '.png' in url_lower:
            return 'png'
        elif '.gif' in url_lower:
            return 'gif'
        elif '.webp' in url_lower:
            return 'webp'
        else:
            return 'unknown'
    
    def _guess_category_from_url(self, url: str) -> str:
        """
        URL에서 카테고리 추측
        """
        url_lower = url.lower()
        
        # 쇼핑몰별 패턴
        if 'coupang' in url_lower:
            return 'coupang_product'
        elif 'naver' in url_lower and 'shopping' in url_lower:
            return 'naver_shopping'
        elif '11st' in url_lower:
            return 'elevenst_product'
        elif 'amazon' in url_lower:
            return 'amazon_product'
        
        # 카테고리 키워드
        beauty_keywords = ['beauty', 'cosmetic', 'makeup', 'skincare']
        fashion_keywords = ['fashion', 'clothing', 'shoes', 'bag']
        tech_keywords = ['tech', 'electronics', 'phone', 'computer']
        
        for keyword in beauty_keywords:
            if keyword in url_lower:
                return 'beauty'
        
        for keyword in fashion_keywords:
            if keyword in url_lower:
                return 'fashion'
        
        for keyword in tech_keywords:
            if keyword in url_lower:
                return 'tech'
        
        return 'general'
    
    def _extract_url_keywords(self, url: str) -> List[str]:
        """
        URL에서 키워드 추출
        """
        import re
        
        # URL에서 단어 추출
        words = re.findall(r'[a-zA-Z가-힣]{3,}', url)
        
        # 일반적인 URL 키워드 제외
        excluded_words = {
            'http', 'https', 'www', 'com', 'net', 'org', 'co', 'kr',
            'image', 'img', 'pic', 'photo', 'jpg', 'jpeg', 'png', 'gif',
            'thumb', 'thumbnail', 'small', 'large', 'medium'
        }
        
        keywords = [word.lower() for word in words if word.lower() not in excluded_words]
        
        return keywords[:10]  # 최대 10개
    
    def calculate_similarity_score(self, source_features: Dict, target_features: Dict) -> float:
        """
        두 이미지 특징 간 유사도 점수 계산
        """
        try:
            score = 0.0
            
            # 1. 도메인 유사도 (20%)
            if source_features['domain'] == target_features['domain']:
                score += 0.2
            elif self._are_similar_domains(source_features['domain'], target_features['domain']):
                score += 0.1
            
            # 2. 카테고리 유사도 (30%)
            if source_features['estimated_category'] == target_features['estimated_category']:
                score += 0.3
            elif self._are_similar_categories(source_features['estimated_category'], target_features['estimated_category']):
                score += 0.15
            
            # 3. 키워드 유사도 (30%)
            source_keywords = set(source_features.get('url_keywords', []))
            target_keywords = set(target_features.get('url_keywords', []))
            
            if source_keywords and target_keywords:
                common_keywords = source_keywords.intersection(target_keywords)
                keyword_similarity = len(common_keywords) / max(len(source_keywords), len(target_keywords))
                score += keyword_similarity * 0.3
            
            # 4. 파일 타입 유사도 (10%)
            if source_features['file_type'] == target_features['file_type']:
                score += 0.1
            
            # 5. 랜덤 팩터 (10%) - 실제 이미지 분석 대신
            url_hash_similarity = self._hash_similarity(
                source_features['url_hash'], 
                target_features['url_hash']
            )
            score += url_hash_similarity * 0.1
            
            return min(score, 0.99)  # 최대 0.99
            
        except Exception as e:
            # 기본 점수 반환
            return 0.5
    
    def _are_similar_domains(self, domain1: str, domain2: str) -> bool:
        """
        도메인 유사도 판단
        """
        shopping_domains = {'coupang.com', 'naver.com', '11st.co.kr', 'amazon.com', 'gmarket.co.kr'}
        
        return (domain1 in shopping_domains and domain2 in shopping_domains)
    
    def _are_similar_categories(self, cat1: str, cat2: str) -> bool:
        """
        카테고리 유사도 판단
        """
        similar_groups = [
            {'beauty', 'cosmetic', 'skincare'},
            {'fashion', 'clothing', 'accessories'},
            {'tech', 'electronics', 'digital'},
            {'home', 'kitchen', 'furniture'}
        ]
        
        for group in similar_groups:
            if cat1 in group and cat2 in group:
                return True
        
        return False
    
    def _hash_similarity(self, hash1: str, hash2: str) -> float:
        """
        해시 문자열 유사도 계산
        """
        if not hash1 or not hash2:
            return 0.0
        
        # 문자별 비교
        matches = sum(1 for a, b in zip(hash1, hash2) if a == b)
        return matches / max(len(hash1), len(hash2))
    
    def analyze_product_images(self, product_image_url: str, search_results: List[Dict]) -> List[Dict]:
        """
        제품 이미지와 검색 결과 이미지들의 유사도 분석
        """
        if not product_image_url or not search_results:
            return search_results
        
        try:
            # 원본 제품 이미지 특징 추출
            source_features = self.extract_image_features(product_image_url)
            
            # 각 검색 결과의 이미지와 비교
            for result in search_results:
                target_image_url = result.get('image_url', '')
                
                if target_image_url:
                    target_features = self.extract_image_features(target_image_url)
                    similarity = self.calculate_similarity_score(source_features, target_features)
                    result['image_similarity'] = similarity
                    result['image_analysis'] = {
                        'source_category': source_features['estimated_category'],
                        'target_category': target_features['estimated_category'],
                        'common_keywords': list(
                            set(source_features.get('url_keywords', [])).intersection(
                                set(target_features.get('url_keywords', []))
                            )
                        )
                    }
                else:
                    result['image_similarity'] = 0.3  # 기본값
                    result['image_analysis'] = {'error': 'No image URL provided'}
            
            # 유사도 순으로 정렬
            search_results.sort(key=lambda x: x.get('image_similarity', 0), reverse=True)
            
            return search_results
            
        except Exception as e:
            st.error(f"이미지 유사도 분석 중 오류: {str(e)}")
            # 오류 시 기본 유사도 점수 할당
            for result in search_results:
                if 'image_similarity' not in result:
                    result['image_similarity'] = 0.5
            
            return search_results
    
    def get_visual_search_suggestions(self, image_url: str) -> List[str]:
        """
        이미지 기반 검색 키워드 제안
        """
        try:
            features = self.extract_image_features(image_url)
            
            suggestions = []
            
            # 카테고리 기반 제안
            category = features['estimated_category']
            category_keywords = {
                'beauty': ['화장품', '뷰티', '스킨케어', '메이크업'],
                'fashion': ['패션', '의류', '스타일', '악세서리'],
                'tech': ['전자제품', '디지털', '기기', '가전'],
                'general': ['제품', '아이템', '상품']
            }
            
            suggestions.extend(category_keywords.get(category, category_keywords['general']))
            
            # URL 키워드 기반 제안
            url_keywords = features.get('url_keywords', [])
            suggestions.extend(url_keywords[:5])
            
            # 중복 제거
            unique_suggestions = list(set(suggestions))
            
            return unique_suggestions[:8]
            
        except Exception as e:
            return ['제품', '아이템', '상품']
    
    def create_similarity_report(self, product_image_url: str, analyzed_results: List[Dict]) -> Dict[str, Any]:
        """
        이미지 유사도 분석 리포트 생성
        """
        try:
            if not analyzed_results:
                return {'error': '분석할 결과가 없습니다.'}
            
            # 통계 계산
            similarities = [r.get('image_similarity', 0) for r in analyzed_results]
            avg_similarity = sum(similarities) / len(similarities)
            max_similarity = max(similarities)
            min_similarity = min(similarities)
            
            # 높은 유사도 결과 (0.7 이상)
            high_similarity_results = [r for r in analyzed_results if r.get('image_similarity', 0) >= 0.7]
            
            # 카테고리별 분포
            categories = {}
            for result in analyzed_results:
                category = result.get('image_analysis', {}).get('target_category', 'unknown')
                categories[category] = categories.get(category, 0) + 1
            
            report = {
                'total_analyzed': len(analyzed_results),
                'average_similarity': round(avg_similarity, 3),
                'highest_similarity': round(max_similarity, 3),
                'lowest_similarity': round(min_similarity, 3),
                'high_similarity_count': len(high_similarity_results),
                'category_distribution': categories,
                'recommendations': []
            }
            
            # 추천사항 생성
            if avg_similarity < 0.4:
                report['recommendations'].append("전반적인 유사도가 낮습니다. 더 구체적인 키워드로 검색해보세요.")
            elif avg_similarity > 0.7:
                report['recommendations'].append("높은 유사도의 결과들을 찾았습니다!")
            
            if len(high_similarity_results) > 0:
                report['recommendations'].append(f"{len(high_similarity_results)}개의 높은 유사도 결과를 발견했습니다.")
            
            return report
            
        except Exception as e:
            return {'error': f'리포트 생성 중 오류: {str(e)}'}
    
    def get_cached_analysis(self, image_url: str) -> Optional[Dict]:
        """
        캐시된 분석 결과 반환
        """
        return self.analysis_cache.get(image_url)
    
    def cache_analysis(self, image_url: str, analysis_result: Dict):
        """
        분석 결과를 캐시에 저장
        """
        self.analysis_cache[image_url] = {
            'result': analysis_result,
            'timestamp': time.time()
        }
        
        # 캐시 크기 제한 (최대 100개)
        if len(self.analysis_cache) > 100:
            # 가장 오래된 항목 제거
            oldest_key = min(self.analysis_cache.keys(), 
                           key=lambda k: self.analysis_cache[k]['timestamp'])
            del self.analysis_cache[oldest_key]