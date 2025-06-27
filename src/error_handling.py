"""
고급 에러 핸들링 및 재시도 로직 모듈
PRD v1.0 - 안정적인 24/7 자동화를 위한 복원력 있는 시스템
"""

import os
import time
import logging
import asyncio
import traceback
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """에러 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """에러 카테고리"""
    API_LIMIT = "api_limit"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    DATA_VALIDATION = "data_validation"
    PROCESSING = "processing"
    STORAGE = "storage"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM = "system"


class RetryStrategy(Enum):
    """재시도 전략"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"
    NO_RETRY = "no_retry"


class SystemError(Exception):
    """시스템 에러 기본 클래스"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.retry_strategy = retry_strategy
        self.metadata = metadata or {}
        self.timestamp = datetime.now()


class APIRateLimitError(SystemError):
    """API 호출 제한 에러"""
    
    def __init__(self, service: str, reset_time: Optional[datetime] = None):
        super().__init__(
            f"{service} API 호출 제한에 도달했습니다.",
            ErrorCategory.API_LIMIT,
            ErrorSeverity.MEDIUM,
            RetryStrategy.EXPONENTIAL_BACKOFF,
            {"service": service, "reset_time": reset_time}
        )


class NetworkError(SystemError):
    """네트워크 관련 에러"""
    
    def __init__(self, operation: str, url: str = None):
        super().__init__(
            f"네트워크 오류: {operation}",
            ErrorCategory.NETWORK,
            ErrorSeverity.MEDIUM,
            RetryStrategy.EXPONENTIAL_BACKOFF,
            {"operation": operation, "url": url}
        )


class DataValidationError(SystemError):
    """데이터 검증 에러"""
    
    def __init__(self, field: str, value: Any, expected: str):
        super().__init__(
            f"데이터 검증 실패: {field} = {value} (예상: {expected})",
            ErrorCategory.DATA_VALIDATION,
            ErrorSeverity.LOW,
            RetryStrategy.NO_RETRY,
            {"field": field, "value": value, "expected": expected}
        )


class ProcessingError(SystemError):
    """처리 관련 에러"""
    
    def __init__(self, stage: str, details: str):
        super().__init__(
            f"처리 오류 [{stage}]: {details}",
            ErrorCategory.PROCESSING,
            ErrorSeverity.MEDIUM,
            RetryStrategy.LINEAR_BACKOFF,
            {"stage": stage, "details": details}
        )


class ErrorHandler:
    """통합 에러 핸들러"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        Args:
            max_retries: 최대 재시도 횟수
            base_delay: 기본 대기 시간 (초)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.error_log = []
        self.circuit_breakers = {}
        
        # 에러 통계
        self.error_stats = {
            "total_errors": 0,
            "critical_errors": 0,
            "retry_success": 0,
            "retry_failed": 0,
            "by_category": {category.value: 0 for category in ErrorCategory},
            "by_severity": {severity.value: 0 for severity in ErrorSeverity}
        }
    
    def log_error(self, error: Union[Exception, SystemError], context: Dict[str, Any] = None):
        """에러 로깅"""
        context = context or {}
        
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "type": type(error).__name__,
            "message": str(error),
            "context": context,
            "traceback": traceback.format_exc()
        }
        
        # SystemError인 경우 추가 정보
        if isinstance(error, SystemError):
            error_info.update({
                "category": error.category.value,
                "severity": error.severity.value,
                "retry_strategy": error.retry_strategy.value,
                "metadata": error.metadata
            })
            
            # 통계 업데이트
            self.error_stats["by_category"][error.category.value] += 1
            self.error_stats["by_severity"][error.severity.value] += 1
            
            if error.severity == ErrorSeverity.CRITICAL:
                self.error_stats["critical_errors"] += 1
        
        self.error_stats["total_errors"] += 1
        self.error_log.append(error_info)
        
        # 로그 레벨 결정
        if isinstance(error, SystemError):
            if error.severity == ErrorSeverity.CRITICAL:
                logger.critical(f"Critical Error: {error.message}", extra=error_info)
            elif error.severity == ErrorSeverity.HIGH:
                logger.error(f"High Severity Error: {error.message}", extra=error_info)
            elif error.severity == ErrorSeverity.MEDIUM:
                logger.warning(f"Medium Severity Error: {error.message}", extra=error_info)
            else:
                logger.info(f"Low Severity Error: {error.message}", extra=error_info)
        else:
            logger.error(f"Unhandled Error: {str(error)}", extra=error_info)
    
    def calculate_delay(self, attempt: int, strategy: RetryStrategy) -> float:
        """재시도 지연 시간 계산"""
        if strategy == RetryStrategy.NO_RETRY:
            return 0
        elif strategy == RetryStrategy.IMMEDIATE:
            return 0
        elif strategy == RetryStrategy.FIXED_DELAY:
            return self.base_delay
        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            return self.base_delay * attempt
        elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return self.base_delay * (2 ** (attempt - 1))
        else:
            return self.base_delay
    
    def should_retry(self, error: Union[Exception, SystemError], attempt: int) -> bool:
        """재시도 여부 결정"""
        if attempt >= self.max_retries:
            return False
        
        if isinstance(error, SystemError):
            return error.retry_strategy != RetryStrategy.NO_RETRY
        
        # 기본적으로 네트워크 에러나 일시적 에러는 재시도
        error_str = str(error).lower()
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'temporary', 'rate limit']):
            return True
        
        return False
    
    def retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: int = None,
        context: Dict[str, Any] = None,
        **kwargs
    ):
        """백오프와 함께 재시도 실행"""
        max_retries = max_retries or self.max_retries
        context = context or {}
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 1:
                    self.error_stats["retry_success"] += 1
                    logger.info(f"재시도 성공: {attempt}번째 시도에서 성공")
                
                return result
                
            except Exception as e:
                last_error = e
                self.log_error(e, {**context, "attempt": attempt})
                
                if not self.should_retry(e, attempt):
                    break
                
                if attempt < max_retries:
                    strategy = RetryStrategy.EXPONENTIAL_BACKOFF
                    if isinstance(e, SystemError):
                        strategy = e.retry_strategy
                    
                    delay = self.calculate_delay(attempt, strategy)
                    logger.info(f"재시도 대기: {delay}초 후 {attempt + 1}번째 시도")
                    time.sleep(delay)
        
        # 모든 재시도 실패
        self.error_stats["retry_failed"] += 1
        logger.error(f"재시도 실패: {max_retries}번 시도 후 포기")
        raise last_error
    
    async def async_retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: int = None,
        context: Dict[str, Any] = None,
        **kwargs
    ):
        """비동기 버전의 백오프와 함께 재시도 실행"""
        max_retries = max_retries or self.max_retries
        context = context or {}
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 1:
                    self.error_stats["retry_success"] += 1
                    logger.info(f"비동기 재시도 성공: {attempt}번째 시도에서 성공")
                
                return result
                
            except Exception as e:
                last_error = e
                self.log_error(e, {**context, "attempt": attempt, "async": True})
                
                if not self.should_retry(e, attempt):
                    break
                
                if attempt < max_retries:
                    strategy = RetryStrategy.EXPONENTIAL_BACKOFF
                    if isinstance(e, SystemError):
                        strategy = e.retry_strategy
                    
                    delay = self.calculate_delay(attempt, strategy)
                    logger.info(f"비동기 재시도 대기: {delay}초 후 {attempt + 1}번째 시도")
                    await asyncio.sleep(delay)
        
        # 모든 재시도 실패
        self.error_stats["retry_failed"] += 1
        logger.error(f"비동기 재시도 실패: {max_retries}번 시도 후 포기")
        raise last_error
    
    def circuit_breaker(self, service_name: str, failure_threshold: int = 5, timeout: int = 300):
        """서킷 브레이커 패턴 구현"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                breaker = self.circuit_breakers.get(service_name, {
                    "failures": 0,
                    "last_failure": None,
                    "state": "closed"  # closed, open, half-open
                })
                
                # 서킷이 열린 상태면 timeout 확인
                if breaker["state"] == "open":
                    if breaker["last_failure"]:
                        time_since_failure = (datetime.now() - breaker["last_failure"]).seconds
                        if time_since_failure < timeout:
                            raise SystemError(
                                f"서킷 브레이커 작동: {service_name} 서비스 일시 차단",
                                ErrorCategory.EXTERNAL_SERVICE,
                                ErrorSeverity.HIGH,
                                RetryStrategy.NO_RETRY
                            )
                        else:
                            breaker["state"] = "half-open"
                
                try:
                    result = func(*args, **kwargs)
                    
                    # 성공시 서킷 리셋
                    if breaker["failures"] > 0:
                        logger.info(f"서킷 브레이커 리셋: {service_name}")
                        breaker["failures"] = 0
                        breaker["state"] = "closed"
                    
                    self.circuit_breakers[service_name] = breaker
                    return result
                    
                except Exception as e:
                    breaker["failures"] += 1
                    breaker["last_failure"] = datetime.now()
                    
                    if breaker["failures"] >= failure_threshold:
                        breaker["state"] = "open"
                        logger.error(f"서킷 브레이커 활성화: {service_name} ({breaker['failures']}회 실패)")
                    
                    self.circuit_breakers[service_name] = breaker
                    raise e
            
            return wrapper
        return decorator
    
    def get_error_stats(self) -> Dict[str, Any]:
        """에러 통계 반환"""
        return {
            **self.error_stats,
            "recent_errors": self.error_log[-10:] if self.error_log else [],
            "circuit_breakers": self.circuit_breakers,
            "error_rate": self.error_stats["total_errors"] / max(1, self.error_stats["total_errors"] + self.error_stats["retry_success"])
        }
    
    def export_error_log(self, file_path: str):
        """에러 로그 파일 내보내기"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "error_log": self.error_log,
                    "statistics": self.error_stats,
                    "circuit_breakers": self.circuit_breakers,
                    "export_time": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"에러 로그 내보내기 완료: {file_path}")
            
        except Exception as e:
            logger.error(f"에러 로그 내보내기 실패: {e}")


def retry_decorator(
    max_retries: int = 3,
    delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    error_handler: ErrorHandler = None
):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler(max_retries, delay)
            
            return handler.retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                context={"function": func.__name__},
                **kwargs
            )
        
        return wrapper
    return decorator


def async_retry_decorator(
    max_retries: int = 3,
    delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    error_handler: ErrorHandler = None
):
    """비동기 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler(max_retries, delay)
            
            return await handler.async_retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                context={"function": func.__name__},
                **kwargs
            )
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    default_return=None,
    log_errors: bool = True,
    error_handler: ErrorHandler = None,
    **kwargs
) -> Any:
    """안전한 함수 실행 (예외 발생시 기본값 반환)"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            handler = error_handler or ErrorHandler()
            handler.log_error(e, {"function": func.__name__, "safe_execute": True})
        
        return default_return


# 전역 에러 핸들러 인스턴스
global_error_handler = ErrorHandler()


if __name__ == "__main__":
    # 테스트 코드
    import requests
    
    logging.basicConfig(level=logging.INFO)
    
    handler = ErrorHandler()
    
    # 재시도 테스트
    @retry_decorator(max_retries=3, delay=0.5)
    def test_api_call():
        """테스트 API 호출"""
        response = requests.get("https://httpstat.us/500", timeout=5)
        if response.status_code != 200:
            raise NetworkError("API 호출", "https://httpstat.us/500")
        return response.json()
    
    # 서킷 브레이커 테스트
    @handler.circuit_breaker("test_service", failure_threshold=2)
    def test_service_call():
        """테스트 서비스 호출"""
        raise ProcessingError("test", "의도적 실패")
    
    print("에러 핸들링 시스템 테스트...")
    
    # 재시도 테스트
    try:
        test_api_call()
    except Exception as e:
        print(f"재시도 후 최종 실패: {e}")
    
    # 서킷 브레이커 테스트
    for i in range(5):
        try:
            test_service_call()
        except Exception as e:
            print(f"서킷 브레이커 테스트 {i+1}: {e}")
    
    # 통계 출력
    stats = handler.get_error_stats()
    print(f"\n에러 통계: {stats}")