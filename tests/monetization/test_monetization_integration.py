"""
수익화 모듈 통합 테스트

쿠팡 파트너스 API 연동 및 전체 수익화 워크플로우를 검증합니다.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path

from src.monetization.monetization_service import MonetizationService, MonetizationResult
from src.monetization.coupang_api_client import CoupangApiClient, CoupangApiError
from src.monetization.product_matcher import ProductMatcher, ProductMatch
from src.monetization.link_generator import LinkGenerator, AffiliateLink
from src.monetization.cache_manager import CacheManager


class TestMonetizationIntegration:
    """수익화 모듈 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.test_access_key = "test_access_key"
        self.test_secret_key = "test_secret_key"
        
        # Mock API 응답 데이터
        self.mock_search_response = {
            "rCode": "0",
            "rMessage": "성공",
            "data": {
                "productData": [
                    {
                        "productId": "123456789",
                        "productName": "에뛰드 립스틱 벨벳 매트 02호",
                        "productPrice": 15000,
                        "originalPrice": 20000,
                        "productUrl": "https://www.coupang.com/vp/products/123456789",
                        "productImage": "https://example.com/image.jpg",
                        "commissionRate": 3.5,
                        "rating": 4.5
                    }
                ]
            }
        }
        
        self.mock_deep_link = "https://link.coupang.com/a/abc123"
        
    def test_monetization_service_initialization_with_api_keys(self):
        """API 키가 있을 때 서비스 초기화 테스트"""
        service = MonetizationService(self.test_access_key, self.test_secret_key)
        
        assert service.is_enabled is True
        assert service.access_key == self.test_access_key
        assert service.secret_key == self.test_secret_key
        assert isinstance(service.api_client, CoupangApiClient)
        assert isinstance(service.product_matcher, ProductMatcher)
        assert isinstance(service.link_generator, LinkGenerator)
        assert isinstance(service.cache_manager, CacheManager)
        
    def test_monetization_service_initialization_without_api_keys(self):
        """API 키가 없을 때 서비스 초기화 테스트"""
        service = MonetizationService("", "")
        
        assert service.is_enabled is False
        
    @patch('src.monetization.coupang_api_client.requests')
    def test_successful_product_monetization(self, mock_requests):
        """성공적인 제품 수익화 검증 테스트"""
        # Mock API 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = self.mock_search_response
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response
        
        # Mock 딥링크 응답 설정
        mock_deep_link_response = Mock()
        mock_deep_link_response.json.return_value = {
            "rCode": "0",
            "data": {"shortenUrl": self.mock_deep_link}
        }
        mock_deep_link_response.status_code = 200
        mock_deep_link_response.raise_for_status.return_value = None
        
        # requests.get을 순차적으로 다른 응답을 반환하도록 설정
        mock_requests.get.side_effect = [mock_response, mock_deep_link_response]
        
        service = MonetizationService(self.test_access_key, self.test_secret_key)
        
        # 링크 유효성 검증 Mock
        with patch('src.monetization.link_generator.requests.head') as mock_head:
            mock_head.return_value.status_code = 200
            
            result = service.verify_product_monetization("에뛰드 립스틱")
            
        assert isinstance(result, MonetizationResult)
        assert result.is_monetizable is True
        assert result.best_match is not None
        assert len(result.all_matches) > 0
        assert result.affiliate_link is not None
        assert len(result.search_keywords_used) > 0
        assert result.error_message is None
        
    def test_failed_product_monetization_no_results(self):
        """검색 결과가 없을 때 수익화 실패 테스트"""
        with patch.object(CoupangApiClient, 'search_products') as mock_search:
            mock_search.return_value = {
                "rCode": "0",
                "data": {"productData": []}
            }
            
            service = MonetizationService(self.test_access_key, self.test_secret_key)
            result = service.verify_product_monetization("존재하지않는제품")
            
        assert result.is_monetizable is False
        assert result.best_match is None
        assert len(result.all_matches) == 0
        assert result.affiliate_link is None
        
    def test_api_error_handling(self):
        """API 오류 처리 테스트"""
        with patch.object(CoupangApiClient, 'search_products') as mock_search:
            mock_search.side_effect = CoupangApiError("API 호출 제한 초과")
            
            service = MonetizationService(self.test_access_key, self.test_secret_key)
            result = service.verify_product_monetization("테스트 제품")
            
        assert result.is_monetizable is False
        assert result.error_message is not None
        
    def test_batch_monetization_verification(self):
        """일괄 수익화 검증 테스트"""
        product_names = ["에뛰드 립스틱", "라네즈 크림", "아디다스 운동화"]
        
        with patch.object(MonetizationService, 'verify_product_monetization') as mock_verify:
            # 각 제품별로 다른 결과 반환
            mock_results = [
                MonetizationResult(
                    product_name=name,
                    is_monetizable=i % 2 == 0,  # 번갈아가며 True/False
                    best_match=None,
                    all_matches=[],
                    affiliate_link=None,
                    search_keywords_used=[],
                    cache_hit=False,
                    processing_time=0.5
                ) for i, name in enumerate(product_names)
            ]
            
            mock_verify.side_effect = mock_results
            
            service = MonetizationService(self.test_access_key, self.test_secret_key)
            results = service.batch_verify_monetization(product_names)
            
        assert len(results) == len(product_names)
        assert sum(1 for r in results if r.is_monetizable) == 2  # 짝수 인덱스만 True
        
    def test_cache_functionality(self):
        """캐시 기능 테스트"""
        with patch.object(CoupangApiClient, 'search_products') as mock_search:
            mock_search.return_value = self.mock_search_response
            
            service = MonetizationService(self.test_access_key, self.test_secret_key)
            
            # 첫 번째 호출 - API 호출
            result1 = service.verify_product_monetization("에뛰드 립스틱")
            
            # 두 번째 호출 - 캐시 사용
            result2 = service.verify_product_monetization("에뛰드 립스틱")
            
            # API는 한 번만 호출되어야 함
            assert mock_search.call_count >= 1
            assert result2.cache_hit is True or mock_search.call_count == 1
            
    def test_service_statistics(self):
        """서비스 통계 테스트"""
        with patch.object(CoupangApiClient, 'check_api_limit_status') as mock_status:
            mock_status.return_value = {"status": "available"}
            
            service = MonetizationService(self.test_access_key, self.test_secret_key)
            stats = service.get_monetization_statistics()
            
        assert stats["service_status"] == "enabled"
        assert "api_status" in stats
        assert "cache_statistics" in stats
        assert "configuration" in stats
        
    def test_api_connection_test(self):
        """API 연결 테스트"""
        with patch.object(CoupangApiClient, 'search_products') as mock_search:
            mock_search.return_value = {"rCode": "0"}
            
            service = MonetizationService(self.test_access_key, self.test_secret_key)
            result = service.test_api_connection()
            
        assert result["success"] is True
        assert "response_code" in result
        
    def test_disabled_service_behavior(self):
        """비활성화된 서비스 동작 테스트"""
        service = MonetizationService("", "")
        
        # 수익화 검증
        result = service.verify_product_monetization("테스트 제품")
        assert result.is_monetizable is False
        assert result.error_message == "쿠팡 API가 설정되지 않음"
        
        # 통계 조회
        stats = service.get_monetization_statistics()
        assert stats["service_status"] == "disabled"
        
        # API 연결 테스트
        test_result = service.test_api_connection()
        assert test_result["success"] is False


class TestProductMatcherUnit:
    """제품 매칭 단위 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.matcher = ProductMatcher()
        
    def test_search_keyword_optimization(self):
        """검색 키워드 최적화 테스트"""
        product_name = "에뛰드 립스틱 벨벳 매트 (02호 로즈브라운)"
        keywords = self.matcher.optimize_search_keyword(product_name)
        
        assert len(keywords) > 0
        assert any("에뛰드" in keyword for keyword in keywords)
        assert any("립스틱" in keyword for keyword in keywords)
        
    def test_product_similarity_calculation(self):
        """제품 유사도 계산 테스트"""
        ai_name = "에뛰드 립스틱"
        coupang_product = {
            "productName": "에뛰드 매트 립스틱 벨벳 02호",
            "productPrice": 15000
        }
        
        similarity = self.matcher.calculate_product_similarity(ai_name, coupang_product)
        
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5  # 유사한 제품이므로 높은 점수 예상
        
    def test_brand_variant_extraction(self):
        """브랜드 변형 추출 테스트"""
        product_name = "etude 립스틱"
        variants = self.matcher._extract_brand_variants(product_name)
        
        assert "에뛰드" in variants or "etude" in variants


class TestCacheManagerUnit:
    """캐시 관리자 단위 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.cache_manager = CacheManager()
        
    def test_search_cache_operations(self):
        """검색 캐시 동작 테스트"""
        keyword = "테스트키워드"
        limit = 50
        test_data = {"test": "data"}
        
        # 캐시 저장
        self.cache_manager.set_search_cache(keyword, limit, test_data)
        
        # 캐시 조회
        cached_data = self.cache_manager.get_search_cache(keyword, limit)
        
        assert cached_data == test_data
        
    def test_cache_expiration(self):
        """캐시 만료 테스트"""
        keyword = "만료테스트"
        test_data = {"test": "data"}
        
        # 즉시 만료되는 캐시 설정
        self.cache_manager.set_search_cache(keyword, 50, test_data, ttl=0)
        
        # 약간의 시간 후 조회
        import time
        time.sleep(0.1)
        
        cached_data = self.cache_manager.get_search_cache(keyword, 50)
        assert cached_data is None  # 만료되어 None 반환
        
    def test_cache_statistics(self):
        """캐시 통계 테스트"""
        # 테스트 데이터 추가
        self.cache_manager.set_search_cache("test1", 50, {"data": 1})
        self.cache_manager.set_search_cache("test2", 50, {"data": 2})
        
        stats = self.cache_manager.get_cache_statistics()
        
        assert "total_entries" in stats
        assert "active_entries" in stats
        assert stats["total_entries"] >= 2