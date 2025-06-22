"""
제휴 링크 생성 및 검증 모듈

쿠팡 파트너스 딥링크 생성, 유효성 검증, URL 단축 기능을 제공합니다.
"""

import re
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import logging

from .coupang_api_client import CoupangApiClient, CoupangApiError

logger = logging.getLogger(__name__)


@dataclass
class AffiliateLink:
    """제휴 링크 데이터 클래스"""
    original_url: str
    affiliate_url: str
    short_url: Optional[str]
    is_valid: bool
    commission_rate: float
    product_id: str
    sub_id: Optional[str]
    created_at: str


class LinkGenerator:
    """제휴 링크 생성 및 관리 클래스"""
    
    def __init__(self, api_client: CoupangApiClient):
        """
        Args:
            api_client: 쿠팡 API 클라이언트
        """
        self.api_client = api_client
        
        # 쿠팡 URL 패턴
        self.coupang_url_patterns = [
            r'https?://(?:www\.)?coupang\.com/vp/products/(\d+)',
            r'https?://(?:www\.)?coupang\.com/(?:np/)?product/(\d+)',
            r'https?://link\.coupang\.com/[a-zA-Z0-9]+'
        ]
        
        logger.info("제휴 링크 생성기 초기화 완료")
        
    def generate_affiliate_link(self, product_url: str, sub_id: Optional[str] = None) -> Optional[AffiliateLink]:
        """
        제품 URL을 제휴 링크로 변환
        
        Args:
            product_url: 원본 제품 URL
            sub_id: 서브 ID (선택사항)
            
        Returns:
            생성된 제휴 링크 정보
        """
        logger.info(f"제휴 링크 생성 시작: {product_url}")
        
        try:
            # URL 유효성 검증
            if not self._is_valid_coupang_url(product_url):
                logger.warning(f"유효하지 않은 쿠팡 URL: {product_url}")
                return None
                
            # 제품 ID 추출
            product_id = self._extract_product_id(product_url)
            if not product_id:
                logger.warning(f"제품 ID 추출 실패: {product_url}")
                return None
                
            # 딥링크 생성
            try:
                affiliate_url = self.api_client.generate_deep_link(product_url, sub_id)
                
                if not affiliate_url:
                    logger.error(f"딥링크 생성 실패: {product_url}")
                    return None
                    
            except CoupangApiError as e:
                logger.error(f"쿠팡 API 딥링크 생성 실패: {str(e)}")
                return None
                
            # 링크 유효성 검증
            is_valid = self._validate_affiliate_link(affiliate_url)
            
            # 제휴 링크 정보 생성
            affiliate_link = AffiliateLink(
                original_url=product_url,
                affiliate_url=affiliate_url,
                short_url=affiliate_url,  # 쿠팡 API가 이미 단축 URL 제공
                is_valid=is_valid,
                commission_rate=0.0,  # API 응답에서 추출 필요
                product_id=product_id,
                sub_id=sub_id,
                created_at=self._get_current_timestamp()
            )
            
            logger.info(f"제휴 링크 생성 완료: {affiliate_url}")
            return affiliate_link
            
        except Exception as e:
            logger.error(f"제휴 링크 생성 중 오류: {str(e)}")
            return None
            
    def generate_multiple_links(self, product_matches: List[Dict[str, Any]], 
                               sub_id: Optional[str] = None) -> List[AffiliateLink]:
        """
        여러 제품의 제휴 링크를 일괄 생성
        
        Args:
            product_matches: 제품 매칭 결과 리스트
            sub_id: 서브 ID
            
        Returns:
            생성된 제휴 링크 리스트
        """
        logger.info(f"일괄 제휴 링크 생성 시작: {len(product_matches)}개 제품")
        
        affiliate_links = []
        
        for match in product_matches:
            try:
                product_url = match.get('click_url') or match.get('productUrl', '')
                
                if not product_url:
                    logger.warning("제품 URL이 없습니다. 건너뜁니다.")
                    continue
                    
                affiliate_link = self.generate_affiliate_link(product_url, sub_id)
                
                if affiliate_link:
                    # 커미션 정보 추가
                    if hasattr(match, 'commission_rate'):
                        affiliate_link.commission_rate = match.commission_rate
                    elif 'commissionRate' in match:
                        affiliate_link.commission_rate = match['commissionRate']
                        
                    affiliate_links.append(affiliate_link)
                    
            except Exception as e:
                logger.warning(f"개별 제휴 링크 생성 실패: {str(e)}")
                continue
                
        logger.info(f"일괄 제휴 링크 생성 완료: {len(affiliate_links)}개 성공")
        return affiliate_links
        
    def _is_valid_coupang_url(self, url: str) -> bool:
        """쿠팡 URL 유효성 검증"""
        if not url:
            return False
            
        for pattern in self.coupang_url_patterns:
            if re.match(pattern, url):
                return True
                
        return False
        
    def _extract_product_id(self, url: str) -> Optional[str]:
        """URL에서 제품 ID 추출"""
        for pattern in self.coupang_url_patterns:
            match = re.match(pattern, url)
            if match and match.groups():
                return match.group(1)
                
        # 쿠팡 링크인 경우 URL에서 제품 ID를 찾을 수 없음
        # 이 경우 원본 URL을 그대로 사용
        return None
        
    def _validate_affiliate_link(self, affiliate_url: str) -> bool:
        """제휴 링크 유효성 검증"""
        try:
            # URL 형식 검증
            parsed = urlparse(affiliate_url)
            if not parsed.scheme or not parsed.netloc:
                return False
                
            # HTTP 상태 확인 (HEAD 요청)
            response = requests.head(affiliate_url, timeout=10, allow_redirects=True)
            
            # 2xx 또는 3xx 응답이면 유효
            return 200 <= response.status_code < 400
            
        except Exception as e:
            logger.warning(f"제휴 링크 유효성 검증 실패: {str(e)}")
            return False
            
    def _get_current_timestamp(self) -> str:
        """현재 타임스탬프 반환"""
        from datetime import datetime
        return datetime.now().isoformat()
        
    def verify_commission_tracking(self, affiliate_url: str) -> Dict[str, Any]:
        """
        제휴 링크의 커미션 추적 가능성 검증
        
        Args:
            affiliate_url: 제휴 링크 URL
            
        Returns:
            추적 정보 딕셔너리
        """
        try:
            parsed = urlparse(affiliate_url)
            query_params = parse_qs(parsed.query)
            
            tracking_info = {
                'has_tracking': False,
                'tracking_params': [],
                'domain': parsed.netloc,
                'is_coupang_link': 'coupang.com' in parsed.netloc.lower()
            }
            
            # 쿠팡 추적 파라미터 확인
            coupang_tracking_params = ['subid', 'af_id', 'tracking_id']
            
            for param in coupang_tracking_params:
                if param in query_params:
                    tracking_info['has_tracking'] = True
                    tracking_info['tracking_params'].append(param)
                    
            # 링크 도메인이 link.coupang.com인 경우 자동 추적
            if 'link.coupang.com' in parsed.netloc.lower():
                tracking_info['has_tracking'] = True
                tracking_info['tracking_params'].append('coupang_affiliate_domain')
                
            return tracking_info
            
        except Exception as e:
            logger.error(f"커미션 추적 검증 중 오류: {str(e)}")
            return {
                'has_tracking': False,
                'tracking_params': [],
                'domain': '',
                'is_coupang_link': False,
                'error': str(e)
            }
            
    def create_campaign_link(self, base_affiliate_url: str, campaign_id: str, 
                           source: str = "influence_item") -> str:
        """
        캠페인 추적이 가능한 제휴 링크 생성
        
        Args:
            base_affiliate_url: 기본 제휴 링크
            campaign_id: 캠페인 ID
            source: 트래픽 소스
            
        Returns:
            캠페인 추적 링크
        """
        try:
            parsed = urlparse(base_affiliate_url)
            query_params = parse_qs(parsed.query)
            
            # 캠페인 파라미터 추가
            query_params['utm_source'] = [source]
            query_params['utm_campaign'] = [campaign_id]
            query_params['utm_medium'] = ['affiliate']
            
            # 쿼리 스트링 재구성
            new_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items()])
            
            # URL 재구성
            campaign_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
            
            logger.info(f"캠페인 추적 링크 생성 완료: {campaign_id}")
            return campaign_url
            
        except Exception as e:
            logger.error(f"캠페인 링크 생성 중 오류: {str(e)}")
            return base_affiliate_url  # 실패시 원본 반환