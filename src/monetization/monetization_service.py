"""
수익화 검증 통합 서비스

쿠팡 파트너스 API를 통한 제품 검색, 매칭, 링크 생성을 통합 관리하는 서비스입니다.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import time

from config.config import Config
from .coupang_api_client import CoupangApiClient, CoupangApiError
from .product_matcher import ProductMatcher, ProductMatch
from .link_generator import LinkGenerator, AffiliateLink
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


@dataclass
class MonetizationResult:
    """수익화 검증 결과"""
    product_name: str
    is_monetizable: bool
    best_match: Optional[ProductMatch]
    all_matches: List[ProductMatch]
    affiliate_link: Optional[AffiliateLink]
    search_keywords_used: List[str]
    cache_hit: bool
    processing_time: float
    error_message: Optional[str] = None


class MonetizationService:
    """수익화 검증 통합 서비스"""
    
    def __init__(self, access_key: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Args:
            access_key: 쿠팡 Access Key (None이면 환경변수 사용)
            secret_key: 쿠팡 Secret Key (None이면 환경변수 사용)
        """
        # API 키 설정
        self.access_key = access_key or Config.COUPANG_ACCESS_KEY
        self.secret_key = secret_key or Config.COUPANG_SECRET_KEY
        
        # API 키가 없으면 비활성화 모드
        self.is_enabled = bool(self.access_key and self.secret_key)
        
        if self.is_enabled:
            # 모듈 초기화
            self.api_client = CoupangApiClient(self.access_key, self.secret_key)
            self.product_matcher = ProductMatcher()
            self.link_generator = LinkGenerator(self.api_client)
            self.cache_manager = CacheManager()
            
            logger.info("수익화 서비스 초기화 완료 - API 활성화")
        else:
            logger.warning("쿠팡 API 키가 설정되지 않음 - 수익화 서비스 비활성화")
            
    def verify_product_monetization(self, product_name: str, 
                                  sub_id: Optional[str] = None,
                                  min_similarity: float = 0.6) -> MonetizationResult:
        """
        제품 수익화 가능성 검증
        
        Args:
            product_name: AI가 추출한 제품명
            sub_id: 서브 ID (추적용)
            min_similarity: 최소 유사도 임계값
            
        Returns:
            수익화 검증 결과
        """
        start_time = time.time()
        
        logger.info(f"수익화 검증 시작: '{product_name}'")
        
        if not self.is_enabled:
            return MonetizationResult(
                product_name=product_name,
                is_monetizable=False,
                best_match=None,
                all_matches=[],
                affiliate_link=None,
                search_keywords_used=[],
                cache_hit=False,
                processing_time=time.time() - start_time,
                error_message="쿠팡 API가 설정되지 않음"
            )
            
        try:
            # 검색 키워드 최적화
            search_keywords = self.product_matcher.optimize_search_keyword(product_name)
            
            best_match = None
            all_matches = []
            cache_hit = False
            affiliate_link = None
            
            # 키워드별 검색 수행
            for keyword in search_keywords:
                try:
                    # 캐시 확인
                    cached_result = self.cache_manager.get_search_cache(keyword, Config.COUPANG_SEARCH_LIMIT)
                    
                    if cached_result:
                        logger.debug(f"캐시 히트: {keyword}")
                        search_result = cached_result
                        cache_hit = True
                    else:
                        # API 호출
                        logger.debug(f"API 호출: {keyword}")
                        search_result = self.api_client.search_products(keyword, Config.COUPANG_SEARCH_LIMIT, sub_id)
                        
                        # 캐시 저장
                        self.cache_manager.set_search_cache(keyword, Config.COUPANG_SEARCH_LIMIT, search_result)
                        
                    # 검색 결과 처리
                    if search_result.get('rCode') == '0':
                        products = search_result.get('data', {}).get('productData', [])
                        
                        if products:
                            # 제품 매칭 평가
                            matches = self.product_matcher.evaluate_search_results(
                                product_name, products, min_similarity
                            )
                            
                            all_matches.extend(matches)
                            
                            # 최고 매칭 업데이트
                            if matches and (not best_match or matches[0].match_confidence > best_match.match_confidence):
                                best_match = matches[0]
                                
                            # 충분히 좋은 매칭을 찾으면 중단
                            if best_match and best_match.match_confidence >= 0.8:
                                break
                                
                except CoupangApiError as e:
                    logger.warning(f"키워드 '{keyword}' 검색 실패: {str(e)}")
                    continue
                    
            # 제휴 링크 생성
            if best_match:
                try:
                    affiliate_link = self.link_generator.generate_affiliate_link(
                        best_match.click_url, sub_id
                    )
                except Exception as e:
                    logger.warning(f"제휴 링크 생성 실패: {str(e)}")
                    
            # 결과 생성
            is_monetizable = best_match is not None and affiliate_link is not None
            
            result = MonetizationResult(
                product_name=product_name,
                is_monetizable=is_monetizable,
                best_match=best_match,
                all_matches=sorted(all_matches, key=lambda x: x.match_confidence, reverse=True),
                affiliate_link=affiliate_link,
                search_keywords_used=search_keywords,
                cache_hit=cache_hit,
                processing_time=time.time() - start_time
            )
            
            logger.info(f"수익화 검증 완료: {product_name} - 수익화 가능: {is_monetizable}")
            return result
            
        except Exception as e:
            logger.error(f"수익화 검증 중 오류: {str(e)}")
            return MonetizationResult(
                product_name=product_name,
                is_monetizable=False,
                best_match=None,
                all_matches=[],
                affiliate_link=None,
                search_keywords_used=[],
                cache_hit=False,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
            
    def batch_verify_monetization(self, product_names: List[str], 
                                sub_id: Optional[str] = None) -> List[MonetizationResult]:
        """
        여러 제품의 수익화 가능성 일괄 검증
        
        Args:
            product_names: 제품명 리스트
            sub_id: 서브 ID
            
        Returns:
            수익화 검증 결과 리스트
        """
        logger.info(f"일괄 수익화 검증 시작: {len(product_names)}개 제품")
        
        results = []
        
        for product_name in product_names:
            try:
                result = self.verify_product_monetization(product_name, sub_id)
                results.append(result)
                
                # API 제한 준수를 위한 대기
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"제품 '{product_name}' 검증 실패: {str(e)}")
                results.append(MonetizationResult(
                    product_name=product_name,
                    is_monetizable=False,
                    best_match=None,
                    all_matches=[],
                    affiliate_link=None,
                    search_keywords_used=[],
                    cache_hit=False,
                    processing_time=0.0,
                    error_message=str(e)
                ))
                
        monetizable_count = sum(1 for r in results if r.is_monetizable)
        logger.info(f"일괄 수익화 검증 완료: {monetizable_count}/{len(product_names)}개 수익화 가능")
        
        return results
        
    def get_monetization_statistics(self) -> Dict[str, Any]:
        """
        수익화 서비스 통계 정보 반환
        
        Returns:
            통계 딕셔너리
        """
        if not self.is_enabled:
            return {
                "service_status": "disabled",
                "reason": "API 키 미설정"
            }
            
        try:
            # API 상태 확인
            api_status = self.api_client.check_api_limit_status()
            
            # 캐시 통계
            cache_stats = self.cache_manager.get_cache_statistics()
            
            return {
                "service_status": "enabled",
                "api_status": api_status,
                "cache_statistics": cache_stats,
                "configuration": {
                    "search_limit": Config.COUPANG_SEARCH_LIMIT,
                    "cache_ttl": Config.COUPANG_CACHE_TTL,
                    "api_timeout": Config.COUPANG_API_TIMEOUT
                }
            }
            
        except Exception as e:
            logger.error(f"통계 정보 수집 실패: {str(e)}")
            return {
                "service_status": "error",
                "error": str(e)
            }
            
    def cleanup_cache(self) -> Dict[str, int]:
        """
        캐시 정리 수행
        
        Returns:
            정리 결과 통계
        """
        if not self.is_enabled:
            return {"status": "disabled"}
            
        return self.cache_manager.cache_maintenance()
        
    def test_api_connection(self) -> Dict[str, Any]:
        """
        API 연결 테스트
        
        Returns:
            테스트 결과
        """
        if not self.is_enabled:
            return {
                "success": False,
                "error": "API 키가 설정되지 않음"
            }
            
        try:
            # 간단한 검색으로 연결 테스트
            result = self.api_client.search_products("테스트", limit=1)
            
            return {
                "success": True,
                "response_code": result.get("rCode"),
                "message": "API 연결 성공"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }