"""
강화된 에러 처리 시스템

지수 백오프 재시도, 회로 차단기 패턴, 실패 복구 메커니즘을 포함한
견고한 에러 처리 시스템
"""

import asyncio
import logging
import time
import random
from typing import Optional, Callable, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics


class CircuitBreakerState(Enum):
    """회로 차단기 상태"""
    CLOSED = "closed"      # 정상 동작
    OPEN = "open"          # 차단 상태 (요청 차단)
    HALF_OPEN = "half_open"  # 반개방 상태 (테스트 중)


@dataclass
class ErrorMetrics:
    """에러 메트릭스"""
    total_requests: int = 0
    failed_requests: int = 0
    success_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    error_types: Dict[str, int] = field(default_factory=dict)
    response_times: List[float] = field(default_factory=list)


class CircuitBreaker:
    """회로 차단기 구현"""
    
    def __init__(self, 
                 failure_threshold: int = 5,          # 실패 임계치
                 recovery_timeout: int = 60,          # 복구 대기 시간 (초)
                 expected_exception: tuple = (Exception,),  # 감지할 예외 타입
                 success_threshold: int = 3,          # 반개방에서 복구 성공 임계치
                 timeout: float = 30.0):              # 요청 타임아웃
        
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self.state = CircuitBreakerState.CLOSED
        self.metrics = ErrorMetrics()
        self.last_failure_time = None
        
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, func: Callable) -> Callable:
        """데코레이터로 사용"""
        async def wrapper(*args, **kwargs):
            return await self._call(func, *args, **kwargs)
        return wrapper
    
    async def _call(self, func: Callable, *args, **kwargs) -> Any:
        """함수 호출 및 회로 차단기 로직 적용"""
        
        # 1. 상태 확인 및 업데이트
        self._update_state()
        
        # 2. OPEN 상태에서는 즉시 예외 발생
        if self.state == CircuitBreakerState.OPEN:
            raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        # 3. 함수 실행
        start_time = time.time()
        
        try:
            # 타임아웃 적용
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout)
            
            # 성공 기록
            execution_time = time.time() - start_time
            self._record_success(execution_time)
            
            return result
            
        except asyncio.TimeoutError:
            self._record_failure("TimeoutError")
            raise CircuitBreakerTimeoutError(f"Function call timed out after {self.timeout}s")
            
        except self.expected_exception as e:
            self._record_failure(type(e).__name__)
            raise
    
    def _update_state(self):
        """회로 차단기 상태 업데이트"""
        current_time = datetime.now()
        
        if self.state == CircuitBreakerState.OPEN:
            # OPEN 상태에서 복구 시간이 지났는지 확인
            if (self.last_failure_time and 
                current_time - self.last_failure_time > timedelta(seconds=self.recovery_timeout)):
                self.state = CircuitBreakerState.HALF_OPEN
                self.metrics.consecutive_successes = 0
                self.logger.info("Circuit breaker: OPEN -> HALF_OPEN")
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # HALF_OPEN 상태에서 충분한 성공이 있었는지 확인
            if self.metrics.consecutive_successes >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.metrics.consecutive_failures = 0
                self.logger.info("Circuit breaker: HALF_OPEN -> CLOSED")
    
    def _record_success(self, execution_time: float):
        """성공 기록"""
        self.metrics.total_requests += 1
        self.metrics.success_requests += 1
        self.metrics.consecutive_successes += 1
        self.metrics.consecutive_failures = 0
        self.metrics.last_success_time = datetime.now()
        self.metrics.response_times.append(execution_time)
        
        # 응답 시간 기록 제한 (최근 100개만)
        if len(self.metrics.response_times) > 100:
            self.metrics.response_times = self.metrics.response_times[-100:]
    
    def _record_failure(self, error_type: str):
        """실패 기록"""
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1
        self.metrics.consecutive_failures += 1
        self.metrics.consecutive_successes = 0
        self.metrics.last_failure_time = datetime.now()
        self.last_failure_time = datetime.now()
        
        # 에러 타입별 카운트
        if error_type not in self.metrics.error_types:
            self.metrics.error_types[error_type] = 0
        self.metrics.error_types[error_type] += 1
        
        # 임계치 도달 시 OPEN 상태로 전환
        if (self.state == CircuitBreakerState.CLOSED and 
            self.metrics.consecutive_failures >= self.failure_threshold):
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(f"Circuit breaker: CLOSED -> OPEN (failures: {self.metrics.consecutive_failures})")
        
        elif (self.state == CircuitBreakerState.HALF_OPEN and 
              self.metrics.consecutive_failures >= 1):
            self.state = CircuitBreakerState.OPEN
            self.logger.warning("Circuit breaker: HALF_OPEN -> OPEN (failure during test)")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        total = self.metrics.total_requests
        if total == 0:
            return {
                'state': self.state.value,
                'total_requests': 0,
                'success_rate': 0.0,
                'failure_rate': 0.0,
                'avg_response_time': 0.0
            }
        
        avg_response_time = 0.0
        if self.metrics.response_times:
            avg_response_time = statistics.mean(self.metrics.response_times)
        
        return {
            'state': self.state.value,
            'total_requests': total,
            'success_requests': self.metrics.success_requests,
            'failed_requests': self.metrics.failed_requests,
            'success_rate': (self.metrics.success_requests / total) * 100,
            'failure_rate': (self.metrics.failed_requests / total) * 100,
            'consecutive_failures': self.metrics.consecutive_failures,
            'consecutive_successes': self.metrics.consecutive_successes,
            'avg_response_time': avg_response_time,
            'error_types': self.metrics.error_types.copy(),
            'last_failure_time': self.metrics.last_failure_time,
            'last_success_time': self.metrics.last_success_time
        }
    
    def reset(self):
        """회로 차단기 리셋"""
        self.state = CircuitBreakerState.CLOSED
        self.metrics = ErrorMetrics()
        self.last_failure_time = None
        self.logger.info("Circuit breaker reset")


class ExponentialBackoff:
    """지수 백오프 재시도 구현"""
    
    def __init__(self,
                 max_retries: int = 5,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_factor: float = 2.0,
                 jitter: bool = True):
        
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        
        self.logger = logging.getLogger(__name__)
    
    def calculate_delay(self, attempt: int) -> float:
        """재시도 대기 시간 계산"""
        # 지수적 증가
        delay = self.base_delay * (self.backoff_factor ** attempt)
        
        # 최대 대기 시간 제한
        delay = min(delay, self.max_delay)
        
        # 지터 추가 (무작위성으로 동시 요청 방지)
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% 지터
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0.1)  # 최소 0.1초
    
    async def retry(self, func: Callable, *args, **kwargs) -> Any:
        """재시도 로직 실행"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"Function succeeded after {attempt} retries")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"All {self.max_retries + 1} attempts failed")
        
        # 모든 재시도 실패
        raise RetryExhaustedException(
            f"Function failed after {self.max_retries + 1} attempts"
        ) from last_exception


class RobustErrorHandler:
    """종합 에러 처리 시스템"""
    
    def __init__(self,
                 max_retries: int = 3,
                 circuit_breaker_config: Optional[Dict] = None,
                 backoff_config: Optional[Dict] = None):
        
        # 기본 설정
        cb_config = circuit_breaker_config or {}
        backoff_config = backoff_config or {}
        
        self.circuit_breaker = CircuitBreaker(**cb_config)
        self.exponential_backoff = ExponentialBackoff(
            max_retries=max_retries, 
            **backoff_config
        )
        
        self.logger = logging.getLogger(__name__)
    
    async def execute_with_resilience(self, func: Callable, *args, **kwargs) -> Any:
        """탄력적 실행 (회로 차단기 + 재시도)"""
        
        async def protected_func():
            return await self.circuit_breaker._call(func, *args, **kwargs)
        
        try:
            return await self.exponential_backoff.retry(protected_func)
        
        except CircuitBreakerOpenError:
            self.logger.error("Circuit breaker is OPEN - operation blocked")
            raise
        
        except RetryExhaustedException:
            self.logger.error("All retry attempts exhausted")
            raise
        
        except Exception as e:
            self.logger.error(f"Unexpected error in resilient execution: {str(e)}")
            raise
    
    def get_health_status(self) -> Dict[str, Any]:
        """시스템 건강성 상태"""
        cb_stats = self.circuit_breaker.get_stats()
        
        # 건강성 점수 계산 (0-100)
        health_score = 100
        
        if cb_stats['state'] == 'open':
            health_score = 0
        elif cb_stats['state'] == 'half_open':
            health_score = 50
        else:
            # 성공률 기반 점수
            if cb_stats['total_requests'] > 0:
                health_score = cb_stats['success_rate']
        
        return {
            'health_score': health_score,
            'circuit_breaker': cb_stats,
            'status': 'healthy' if health_score > 80 else 'degraded' if health_score > 50 else 'unhealthy'
        }


# 커스텀 예외들
class CircuitBreakerOpenError(Exception):
    """회로 차단기가 열려있을 때 발생하는 예외"""
    pass


class CircuitBreakerTimeoutError(Exception):
    """회로 차단기 타임아웃 예외"""
    pass


class RetryExhaustedException(Exception):
    """모든 재시도가 실패했을 때 발생하는 예외"""
    pass


# 편의 함수들
def create_resilient_handler(
    max_retries: int = 3,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> RobustErrorHandler:
    """견고한 에러 처리기 생성"""
    
    circuit_breaker_config = {
        'failure_threshold': failure_threshold,
        'recovery_timeout': recovery_timeout,
        'timeout': 30.0
    }
    
    backoff_config = {
        'base_delay': base_delay,
        'max_delay': max_delay,
        'backoff_factor': 2.0,
        'jitter': True
    }
    
    return RobustErrorHandler(
        max_retries=max_retries,
        circuit_breaker_config=circuit_breaker_config,
        backoff_config=backoff_config
    )


# 데코레이터 버전
def resilient(max_retries: int = 3, **kwargs):
    """탄력적 실행 데코레이터"""
    handler = create_resilient_handler(max_retries=max_retries, **kwargs)
    
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            return await handler.execute_with_resilience(func, *args, **kwargs)
        return wrapper
    return decorator