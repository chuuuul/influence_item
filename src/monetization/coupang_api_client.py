"""
쿠팡 파트너스 API 클라이언트

쿠팡 파트너스 API를 통한 제품 검색, 인증, 링크 생성 기능을 제공합니다.
"""

import hmac
import hashlib
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import quote
import logging

from ..whisper_processor.retry_handler import RetryHandler

# API 사용량 추적을 위한 임포트
try:
    from src.api.usage_tracker import get_tracker
except ImportError:
    # 추적기가 없는 경우 더미 함수
    def get_tracker():
        return None

logger = logging.getLogger(__name__)


class CoupangApiError(Exception):
    """쿠팡 API 에러"""
    pass


class CoupangApiClient:
    """쿠팡 파트너스 API 클라이언트"""
    
    BASE_URL = "https://api-gateway.coupang.com"
    
    def __init__(self, access_key: str, secret_key: str):
        """
        Args:
            access_key: 쿠팡 파트너스 Access Key
            secret_key: 쿠팡 파트너스 Secret Key
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.retry_handler = RetryHandler()
        
        logger.info("쿠팡 API 클라이언트 초기화 완료")
        
    def _generate_hmac_signature(self, method: str, url_path: str, query_string: str = "") -> str:
        """
        HMAC 인증 서명 생성
        
        Args:
            method: HTTP 메서드 (GET, POST 등)
            url_path: API 경로
            query_string: 쿼리 스트링
            
        Returns:
            Base64 인코딩된 HMAC 서명
        """
        # 타임스탬프 생성
        timestamp = str(int(time.time() * 1000))
        
        # 서명 문자열 생성
        message_parts = [
            timestamp,
            method.upper(),
            url_path,
            self.access_key
        ]
        
        if query_string:
            message_parts.append(query_string)
            
        message = ''.join(message_parts)
        
        # HMAC-SHA256 서명 생성
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
        
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        API 요청 실행
        
        Args:
            method: HTTP 메서드
            endpoint: API 엔드포인트
            params: 쿼리 파라미터
            data: 요청 바디 데이터
            
        Returns:
            API 응답 데이터
            
        Raises:
            CoupangApiError: API 호출 실패 시
        """
        url = f"{self.BASE_URL}{endpoint}"
        tracker = get_tracker()
        start_time = time.time()
        
        # 쿼리 스트링 생성
        query_string = ""
        if params:
            query_parts = [f"{k}={quote(str(v))}" for k, v in sorted(params.items())]
            query_string = "&".join(query_parts)
            
        # HMAC 서명 생성
        signature = self._generate_hmac_signature(method, endpoint, query_string)
        
        # 헤더 설정
        headers = {
            "Authorization": f"CEA algorithm=HmacSHA256, access-key={self.access_key}, signed-date={int(time.time() * 1000)}, signature={signature}",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "influence-item-analyzer/1.0"
        }
        
        def _request() -> requests.Response:
            if method.upper() == "GET":
                return requests.get(url, params=params, headers=headers, timeout=30)
            elif method.upper() == "POST":
                return requests.post(url, params=params, json=data, headers=headers, timeout=30)
            else:
                raise CoupangApiError(f"지원하지 않는 HTTP 메서드: {method}")
        
        try:
            response = self.retry_handler.execute_with_retry(_request)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"쿠팡 API 호출 성공: {endpoint}")
            
            # 사용량 추적 - 성공
            if tracker:
                response_time = (time.time() - start_time) * 1000
                tracker.track_api_call(
                    api_name="coupang",
                    endpoint=endpoint,
                    method=method.upper(),
                    tokens_used=0,  # Coupang API는 토큰 기반이 아님
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    metadata={
                        "params": params,
                        "query_string": query_string,
                        "response_size": len(str(result)) if result else 0
                    }
                )
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"쿠팡 API 호출 실패: {endpoint} - {str(e)}")
            
            # 사용량 추적 - 실패
            if tracker:
                response_time = (time.time() - start_time) * 1000
                status_code = getattr(e.response, 'status_code', 500) if hasattr(e, 'response') else 500
                tracker.track_api_call(
                    api_name="coupang",
                    endpoint=endpoint,
                    method=method.upper(),
                    tokens_used=0,
                    status_code=status_code,
                    response_time_ms=response_time,
                    error_message=str(e),
                    metadata={
                        "params": params,
                        "error_type": type(e).__name__
                    }
                )
            
            raise CoupangApiError(f"API 호출 실패: {str(e)}")
        except Exception as e:
            logger.error(f"쿠팡 API 처리 중 오류: {str(e)}")
            
            # 사용량 추적 - 예외
            if tracker:
                response_time = (time.time() - start_time) * 1000
                tracker.track_api_call(
                    api_name="coupang",
                    endpoint=endpoint,
                    method=method.upper(),
                    tokens_used=0,
                    status_code=500,
                    response_time_ms=response_time,
                    error_message=str(e),
                    metadata={
                        "params": params,
                        "error_type": type(e).__name__
                    }
                )
            
            raise CoupangApiError(f"API 처리 오류: {str(e)}")
            
    def search_products(self, keyword: str, limit: int = 50, subId: Optional[str] = None) -> Dict[str, Any]:
        """
        제품 검색
        
        Args:
            keyword: 검색 키워드
            limit: 검색 결과 수 (최대 100)
            subId: 서브 ID (선택사항)
            
        Returns:
            검색 결과 데이터
        """
        logger.info(f"제품 검색 시작: keyword='{keyword}', limit={limit}")
        
        params = {
            "keyword": keyword,
            "limit": min(limit, 100)  # 최대 100개로 제한
        }
        
        if subId:
            params["subId"] = subId
            
        try:
            result = self._make_request("GET", "/v2/providers/affiliate_open_api/apis/openapi/products/search", params)
            
            # 응답 구조 검증
            if "rCode" not in result:
                raise CoupangApiError("API 응답 형식 오류: rCode 누락")
                
            if result["rCode"] == "0":
                products = result.get("data", {}).get("productData", [])
                logger.info(f"제품 검색 완료: {len(products)}개 제품 발견")
                return result
            else:
                error_msg = result.get("rMessage", "알 수 없는 오류")
                raise CoupangApiError(f"API 오류: {error_msg}")
                
        except CoupangApiError:
            raise
        except Exception as e:
            logger.error(f"제품 검색 중 오류: {str(e)}")
            raise CoupangApiError(f"제품 검색 실패: {str(e)}")
            
    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        제품 상세 정보 조회
        
        Args:
            product_id: 제품 ID
            
        Returns:
            제품 상세 정보
        """
        logger.info(f"제품 상세 정보 조회: product_id='{product_id}'")
        
        try:
            result = self._make_request("GET", f"/v2/providers/affiliate_open_api/apis/openapi/products/{product_id}")
            
            if result.get("rCode") == "0":
                logger.info(f"제품 상세 정보 조회 완료")
                return result
            else:
                error_msg = result.get("rMessage", "알 수 없는 오류")
                raise CoupangApiError(f"제품 상세 조회 실패: {error_msg}")
                
        except CoupangApiError:
            raise
        except Exception as e:
            logger.error(f"제품 상세 조회 중 오류: {str(e)}")
            raise CoupangApiError(f"제품 상세 조회 실패: {str(e)}")
            
    def generate_deep_link(self, click_url: str, subId: Optional[str] = None) -> str:
        """
        딥링크 생성
        
        Args:
            click_url: 원본 클릭 URL
            subId: 서브 ID (선택사항)
            
        Returns:
            생성된 딥링크
        """
        logger.info(f"딥링크 생성 시작")
        
        params = {
            "coupangUrls": click_url
        }
        
        if subId:
            params["subId"] = subId
            
        try:
            result = self._make_request("GET", "/v2/providers/affiliate_open_api/apis/openapi/deeplink", params)
            
            if result.get("rCode") == "0":
                deep_link = result.get("data", {}).get("shortenUrl", "")
                logger.info(f"딥링크 생성 완료")
                return deep_link
            else:
                error_msg = result.get("rMessage", "알 수 없는 오류")
                raise CoupangApiError(f"딥링크 생성 실패: {error_msg}")
                
        except CoupangApiError:
            raise
        except Exception as e:
            logger.error(f"딥링크 생성 중 오류: {str(e)}")
            raise CoupangApiError(f"딥링크 생성 실패: {str(e)}")
            
    def check_api_limit_status(self) -> Dict[str, Any]:
        """
        API 호출 제한 상태 확인
        
        Returns:
            API 제한 상태 정보
        """
        try:
            # 간단한 검색으로 상태 확인
            result = self.search_products("test", limit=1)
            return {
                "status": "available",
                "message": "API 사용 가능"
            }
        except CoupangApiError as e:
            if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                return {
                    "status": "limited",
                    "message": "API 호출 제한 도달"
                }
            else:
                return {
                    "status": "error", 
                    "message": str(e)
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"상태 확인 실패: {str(e)}"
            }