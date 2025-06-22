"""
재시도 및 에러 핸들링 모듈

네트워크 오류나 일시적 실패에 대한 재시도 로직을 제공합니다.
"""

import logging
import time
import functools
from typing import Callable, Any, Optional, Type, Tuple
from config import Config


class RetryHandler:
    """재시도 핸들러 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        재시도 핸들러 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def retry_with_exponential_backoff(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        """
        지수 백오프를 사용한 재시도 데코레이터
        
        Args:
            max_retries: 최대 재시도 횟수
            base_delay: 기본 지연 시간 (초)
            max_delay: 최대 지연 시간 (초)
            exponential_base: 지수 증가율
            exceptions: 재시도할 예외 타입들
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        if attempt > 0:
                            self.logger.info(f"{func.__name__} 재시도 {attempt}/{max_retries}")
                        
                        result = func(*args, **kwargs)
                        
                        if attempt > 0:
                            self.logger.info(f"{func.__name__} 재시도 성공")
                        
                        return result
                        
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt < max_retries:
                            # 지연 시간 계산
                            delay = min(
                                base_delay * (exponential_base ** attempt),
                                max_delay
                            )
                            
                            self.logger.warning(
                                f"{func.__name__} 실패 (시도 {attempt + 1}/{max_retries + 1}): "
                                f"{str(e)}. {delay:.1f}초 후 재시도..."
                            )
                            
                            time.sleep(delay)
                        else:
                            self.logger.error(
                                f"{func.__name__} 최대 재시도 횟수 초과. 최종 오류: {str(e)}"
                            )
                
                # 모든 재시도 실패 시 마지막 예외 발생
                raise last_exception
            
            return wrapper
        return decorator
    
    def retry_on_network_error(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0
    ):
        """
        네트워크 오류에 대한 재시도 데코레이터
        
        Args:
            max_retries: 최대 재시도 횟수
            base_delay: 기본 지연 시간
        """
        import requests
        import urllib.error
        
        network_exceptions = (
            requests.exceptions.RequestException,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            urllib.error.URLError,
            OSError,  # 네트워크 관련 OS 오류
        )
        
        return self.retry_with_exponential_backoff(
            max_retries=max_retries,
            base_delay=base_delay,
            exceptions=network_exceptions
        )
    
    def retry_on_api_error(
        self,
        max_retries: int = 2,
        base_delay: float = 5.0
    ):
        """
        API 오류에 대한 재시도 데코레이터
        
        Args:
            max_retries: 최대 재시도 횟수
            base_delay: 기본 지연 시간
        """
        # API 관련 예외들
        api_exceptions = (
            ConnectionError,
            TimeoutError,
            # 여기에 Gemini API 관련 예외들을 추가할 예정
        )
        
        return self.retry_with_exponential_backoff(
            max_retries=max_retries,
            base_delay=base_delay,
            exceptions=api_exceptions
        )
    
    def safe_execute(
        self,
        func: Callable,
        *args,
        default_return: Any = None,
        log_error: bool = True,
        **kwargs
    ) -> Any:
        """
        안전한 함수 실행 (예외 발생 시 기본값 반환)
        
        Args:
            func: 실행할 함수
            *args: 함수 인자
            default_return: 예외 발생 시 반환할 기본값
            log_error: 오류 로깅 여부
            **kwargs: 함수 키워드 인자
            
        Returns:
            함수 실행 결과 또는 기본값
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if log_error:
                self.logger.error(f"{func.__name__} 실행 실패: {str(e)}")
            return default_return


# 전역 재시도 핸들러 인스턴스
retry_handler = RetryHandler()

# 편의를 위한 데코레이터 함수들
def retry_network_operation(max_retries: int = 3, base_delay: float = 2.0):
    """네트워크 작업 재시도 데코레이터"""
    return retry_handler.retry_on_network_error(max_retries, base_delay)

def retry_api_operation(max_retries: int = 2, base_delay: float = 5.0):
    """API 작업 재시도 데코레이터"""
    return retry_handler.retry_on_api_error(max_retries, base_delay)