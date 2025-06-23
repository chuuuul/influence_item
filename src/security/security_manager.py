"""
통합 보안 관리 시스템

API 키 관리, 레이트 리미팅, Circuit Breaker, 로깅을 통합 관리합니다.
"""

import time
import logging
import hashlib
from typing import Dict, Optional, Any, Callable
from contextlib import contextmanager
from functools import wraps

from .key_manager import get_key_manager, KeyManager
from .rate_limiter import get_rate_limiter, RateLimiter
from .circuit_breaker import get_circuit_manager, CircuitBreakerManager, CircuitOpenError
from .api_logger import get_api_logger, APILogger, APICallLog

logger = logging.getLogger(__name__)


class SecurityManager:
    """통합 보안 관리자"""
    
    def __init__(self):
        self.key_manager: KeyManager = get_key_manager()
        self.rate_limiter: RateLimiter = get_rate_limiter()
        self.circuit_manager: CircuitBreakerManager = get_circuit_manager()
        self.api_logger: APILogger = get_api_logger()
        
        logger.info("통합 보안 관리자 초기화 완료")
    
    def secure_api_call(
        self,
        api_name: str,
        endpoint: str,
        method: str = "GET",
        api_key_name: Optional[str] = None,
        use_rate_limiting: bool = True,
        use_circuit_breaker: bool = True,
        log_calls: bool = True
    ):
        """
        보안이 적용된 API 호출 데코레이터
        
        Args:
            api_name: API 이름
            endpoint: API 엔드포인트
            method: HTTP 메서드
            api_key_name: API 키 이름 (암호화 저장소에서 조회)
            use_rate_limiting: 레이트 리미팅 사용 여부
            use_circuit_breaker: Circuit Breaker 사용 여부
            log_calls: API 호출 로깅 여부
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self._execute_secure_call(
                    func, api_name, endpoint, method, api_key_name,
                    use_rate_limiting, use_circuit_breaker, log_calls,
                    *args, **kwargs
                )
            return wrapper
        return decorator
    
    def _execute_secure_call(
        self,
        func: Callable,
        api_name: str,
        endpoint: str,
        method: str,
        api_key_name: Optional[str],
        use_rate_limiting: bool,
        use_circuit_breaker: bool,
        log_calls: bool,
        *args,
        **kwargs
    ) -> Any:
        """보안이 적용된 API 호출 실행"""
        start_time = time.time()
        success = False
        error_message = None
        status_code = None
        response_size = 0
        request_size = 0
        
        try:
            # 1. API 키 주입
            if api_key_name:
                api_key = self.key_manager.get_api_key_safe(api_key_name)
                if api_key:
                    kwargs["api_key"] = api_key
                else:
                    logger.warning(f"API 키 '{api_key_name}'을 찾을 수 없습니다")
            
            # 2. 레이트 리미팅 확인
            if use_rate_limiting:
                if not self.rate_limiter.can_make_call(api_name):
                    # 대기 시간 계산
                    wait_time = self.rate_limiter.wait_for_rate_limit(api_name)
                    raise RateLimitExceededError(f"Rate limit exceeded for {api_name}, wait {wait_time:.1f}s")
            
            # 3. Circuit Breaker를 통한 호출
            if use_circuit_breaker:
                circuit = self.circuit_manager.get_circuit(api_name)
                if circuit:
                    result = circuit.call(func, *args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 성공 처리
            success = True
            response_time = time.time() - start_time
            
            # 응답 크기 추정
            if hasattr(result, '__len__'):
                try:
                    response_size = len(str(result))
                except:
                    response_size = 0
            
            # 4. 레이트 리미팅 기록
            if use_rate_limiting:
                self.rate_limiter.record_call(api_name, success, response_time)
            
            return result
            
        except Exception as e:
            error_message = str(e)
            response_time = time.time() - start_time
            
            # 에러 타입별 처리
            if isinstance(e, CircuitOpenError):
                logger.warning(f"Circuit Breaker가 열린 상태: {api_name}")
            elif "rate limit" in error_message.lower():
                logger.warning(f"Rate limit 도달: {api_name}")
            else:
                logger.error(f"API 호출 실패: {api_name} - {error_message}")
            
            # 레이트 리미팅 기록 (실패도 기록)
            if use_rate_limiting:
                self.rate_limiter.record_call(api_name, success, response_time)
            
            raise
            
        finally:
            # 5. API 호출 로깅
            if log_calls:
                api_key_hash = None
                if api_key_name and api_key_name in kwargs:
                    api_key_hash = hashlib.md5(kwargs[api_key_name].encode()).hexdigest()[:8]
                
                log_entry = APICallLog(
                    timestamp=start_time,
                    api_name=api_name,
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    response_time=time.time() - start_time,
                    request_size=request_size,
                    response_size=response_size,
                    success=success,
                    error_message=error_message,
                    api_key_hash=api_key_hash
                )
                
                self.api_logger.log_api_call(log_entry)
    
    @contextmanager
    def api_context(self, api_name: str):
        """API 호출 컨텍스트 매니저"""
        start_time = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start_time
            logger.debug(f"API '{api_name}' 호출 완료: {elapsed:.2f}초")
    
    def get_api_key(self, key_name: str, fallback_env: Optional[str] = None) -> str:
        """안전한 API 키 조회"""
        return self.key_manager.get_api_key_safe(key_name, fallback_env)
    
    def rotate_api_key(self, key_name: str, new_key: str) -> bool:
        """API 키 로테이션"""
        return self.key_manager.rotate_key(key_name, new_key)
    
    def get_security_stats(self) -> Dict[str, Any]:
        """보안 시스템 통계 조회"""
        stats = {
            "rate_limiting": {},
            "circuit_breakers": self.circuit_manager.get_all_stats(),
            "api_calls": self.api_logger.get_api_stats(),
            "stored_keys": list(self.key_manager.list_keys().keys())
        }
        
        # API별 레이트 리미팅 통계
        for api_name in ["gemini", "coupang", "google_sheets", "whisper"]:
            stats["rate_limiting"][api_name] = self.rate_limiter.get_call_stats(api_name)
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """보안 시스템 헬스체크"""
        health = {
            "status": "healthy",
            "components": {},
            "timestamp": time.time()
        }
        
        try:
            # 키 매니저 체크
            key_count = len(self.key_manager.list_keys())
            health["components"]["key_manager"] = {
                "status": "healthy",
                "stored_keys": key_count
            }
        except Exception as e:
            health["components"]["key_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health["status"] = "degraded"
        
        try:
            # Circuit Breaker 체크
            circuits = self.circuit_manager.get_all_stats()
            open_circuits = [name for name, stats in circuits.items() if stats["state"] == "open"]
            
            health["components"]["circuit_breakers"] = {
                "status": "healthy" if not open_circuits else "degraded",
                "total_circuits": len(circuits),
                "open_circuits": open_circuits
            }
            
            if open_circuits:
                health["status"] = "degraded"
                
        except Exception as e:
            health["components"]["circuit_breakers"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health["status"] = "degraded"
        
        return health
    
    def reset_security_systems(self) -> None:
        """보안 시스템 리셋"""
        try:
            self.circuit_manager.reset_all()
            self.key_manager.clear_cache()
            logger.info("보안 시스템 리셋 완료")
        except Exception as e:
            logger.error(f"보안 시스템 리셋 실패: {str(e)}")


class RateLimitExceededError(Exception):
    """레이트 리미트 초과 예외"""
    pass


# 전역 보안 관리자 인스턴스
_security_manager = None

def get_security_manager() -> SecurityManager:
    """보안 관리자 싱글톤 인스턴스 반환"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# 편의 함수들
def secure_api_call(api_name: str, endpoint: str, **kwargs):
    """보안 API 호출 데코레이터 (편의 함수)"""
    return get_security_manager().secure_api_call(api_name, endpoint, **kwargs)


def get_api_key(key_name: str, fallback_env: Optional[str] = None) -> str:
    """API 키 조회 (편의 함수)"""
    return get_security_manager().get_api_key(key_name, fallback_env)