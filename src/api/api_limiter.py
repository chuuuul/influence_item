"""
API Call Limitation Middleware
API 호출 제한 미들웨어

예산 임계값에 따른 API 호출 제한 및 회로 차단기 패턴 구현
"""

import asyncio
import time
import logging
from typing import Dict, Set, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from threading import Lock
from collections import defaultdict, deque

from src.api.budget_controller import get_budget_controller, BudgetThreshold, BudgetExceededException

# 로깅 설정
logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """회로 차단기 상태"""
    CLOSED = "closed"       # 정상 동작
    OPEN = "open"           # 차단됨
    HALF_OPEN = "half_open" # 부분 테스트


@dataclass
class CircuitBreakerConfig:
    """회로 차단기 설정"""
    failure_threshold: int = 5      # 실패 임계값
    recovery_timeout: int = 60      # 복구 시도 시간 (초)
    success_threshold: int = 3      # 복구를 위한 성공 임계값
    timeout: float = 30.0           # API 호출 타임아웃


@dataclass
class RateLimitConfig:
    """Rate Limiting 설정"""
    calls_per_minute: int = 60
    calls_per_hour: int = 1000
    calls_per_day: int = 10000


class APILimiter:
    """API 호출 제한 관리자"""
    
    def __init__(self):
        self.limited_apis: Set[str] = set()
        self.total_block = False
        self.bypass_emergency = False
        self._lock = Lock()
        
        # 회로 차단기 상태 관리
        self.circuit_states: Dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, float] = defaultdict(float)
        
        # Rate limiting
        self.rate_limits: Dict[str, RateLimitConfig] = {}
        self.call_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 기본 설정
        self._setup_default_limits()
        
        logger.info("API Limiter 초기화 완료")
    
    def _setup_default_limits(self):
        """기본 API 제한 설정"""
        # Gemini API 제한 (PRD 기준)
        self.rate_limits['gemini'] = RateLimitConfig(
            calls_per_minute=60,
            calls_per_hour=1000,
            calls_per_day=1500  # PRD 기준
        )
        
        # Coupang API 제한
        self.rate_limits['coupang'] = RateLimitConfig(
            calls_per_minute=10,
            calls_per_hour=9,   # 시간당 10건 제한
            calls_per_day=100
        )
        
        # Whisper는 오픈소스이므로 관대한 제한
        self.rate_limits['whisper'] = RateLimitConfig(
            calls_per_minute=30,
            calls_per_hour=500,
            calls_per_day=2000
        )
    
    def limit_api_calls(self, api_name: Optional[str] = None):
        """API 호출 제한 설정"""
        with self._lock:
            if api_name:
                self.limited_apis.add(api_name.lower())
                logger.warning(f"API 제한 설정: {api_name}")
            else:
                self.total_block = True
                logger.critical("모든 API 호출 차단 설정")
    
    def remove_api_limit(self, api_name: Optional[str] = None):
        """API 호출 제한 해제"""
        with self._lock:
            if api_name:
                self.limited_apis.discard(api_name.lower())
                logger.info(f"API 제한 해제: {api_name}")
            else:
                self.total_block = False
                self.limited_apis.clear()
                logger.info("모든 API 제한 해제")
    
    def set_emergency_bypass(self, enabled: bool):
        """긴급 우회 모드 설정"""
        with self._lock:
            self.bypass_emergency = enabled
            logger.warning(f"긴급 우회 모드: {'활성화' if enabled else '비활성화'}")
    
    def api_call_allowed(self, api_name: str, essential: bool = False) -> bool:
        """API 호출 허용 여부 확인"""
        api_name = api_name.lower()
        
        # 긴급 우회 모드
        if self.bypass_emergency:
            return True
        
        # 예산 기반 제한 확인
        budget_controller = get_budget_controller()
        if not budget_controller.can_make_api_call(api_name, essential):
            return False
        
        # 전체 차단
        if self.total_block and not essential:
            return False
        
        # 개별 API 제한
        if api_name in self.limited_apis and not essential:
            return False
        
        # 회로 차단기 확인
        if not self._circuit_breaker_allows(api_name):
            return False
        
        # Rate limiting 확인
        if not self._rate_limit_allows(api_name):
            return False
        
        return True
    
    def _circuit_breaker_allows(self, api_name: str) -> bool:
        """회로 차단기 상태 확인"""
        state = self.circuit_states[api_name]
        current_time = time.time()
        
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            # 복구 시간이 지났는지 확인
            if current_time - self.last_failure_time[api_name] > CircuitBreakerConfig().recovery_timeout:
                self.circuit_states[api_name] = CircuitState.HALF_OPEN
                self.success_counts[api_name] = 0
                logger.info(f"회로 차단기 부분 복구 시도: {api_name}")
                return True
            return False
        elif state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def _rate_limit_allows(self, api_name: str) -> bool:
        """Rate limiting 확인"""
        if api_name not in self.rate_limits:
            return True
        
        config = self.rate_limits[api_name]
        current_time = time.time()
        call_times = self.call_history[api_name]
        
        # 오래된 호출 기록 정리
        while call_times and current_time - call_times[0] > 86400:  # 24시간
            call_times.popleft()
        
        # 분당 제한 확인
        minute_calls = sum(1 for t in call_times if current_time - t < 60)
        if minute_calls >= config.calls_per_minute:
            logger.warning(f"Rate limit 초과 (분당): {api_name} - {minute_calls}/{config.calls_per_minute}")
            return False
        
        # 시간당 제한 확인
        hour_calls = sum(1 for t in call_times if current_time - t < 3600)
        if hour_calls >= config.calls_per_hour:
            logger.warning(f"Rate limit 초과 (시간당): {api_name} - {hour_calls}/{config.calls_per_hour}")
            return False
        
        # 일당 제한 확인
        day_calls = len(call_times)
        if day_calls >= config.calls_per_day:
            logger.warning(f"Rate limit 초과 (일당): {api_name} - {day_calls}/{config.calls_per_day}")
            return False
        
        return True
    
    def record_api_call(self, api_name: str, success: bool, response_time: float = 0):
        """API 호출 기록 및 회로 차단기 상태 업데이트"""
        api_name = api_name.lower()
        current_time = time.time()
        
        # 호출 시간 기록
        self.call_history[api_name].append(current_time)
        
        # 회로 차단기 상태 업데이트
        if success:
            self._handle_success(api_name)
        else:
            self._handle_failure(api_name, current_time)
    
    def _handle_success(self, api_name: str):
        """성공 처리"""
        state = self.circuit_states[api_name]
        
        if state == CircuitState.HALF_OPEN:
            self.success_counts[api_name] += 1
            if self.success_counts[api_name] >= CircuitBreakerConfig().success_threshold:
                self.circuit_states[api_name] = CircuitState.CLOSED
                self.failure_counts[api_name] = 0
                logger.info(f"회로 차단기 복구 완료: {api_name}")
        elif state == CircuitState.CLOSED:
            # 성공 시 실패 카운트 감소
            if self.failure_counts[api_name] > 0:
                self.failure_counts[api_name] = max(0, self.failure_counts[api_name] - 1)
    
    def _handle_failure(self, api_name: str, current_time: float):
        """실패 처리"""
        self.failure_counts[api_name] += 1
        self.last_failure_time[api_name] = current_time
        
        config = CircuitBreakerConfig()
        
        if (self.circuit_states[api_name] == CircuitState.CLOSED and 
            self.failure_counts[api_name] >= config.failure_threshold):
            
            self.circuit_states[api_name] = CircuitState.OPEN
            logger.error(f"회로 차단기 열림: {api_name} - 실패 {self.failure_counts[api_name]}회")
        
        elif self.circuit_states[api_name] == CircuitState.HALF_OPEN:
            # Half-open 상태에서 실패하면 다시 열림
            self.circuit_states[api_name] = CircuitState.OPEN
            logger.error(f"회로 차단기 재차단: {api_name}")
    
    def get_api_status(self, api_name: str) -> Dict[str, Any]:
        """API 상태 정보 반환"""
        api_name = api_name.lower()
        
        # Rate limit 정보
        rate_info = {}
        if api_name in self.rate_limits:
            config = self.rate_limits[api_name]
            call_times = self.call_history[api_name]
            current_time = time.time()
            
            rate_info = {
                'calls_last_minute': sum(1 for t in call_times if current_time - t < 60),
                'calls_last_hour': sum(1 for t in call_times if current_time - t < 3600),
                'calls_today': len(call_times),
                'limits': {
                    'per_minute': config.calls_per_minute,
                    'per_hour': config.calls_per_hour,
                    'per_day': config.calls_per_day
                }
            }
        
        return {
            'api_name': api_name,
            'is_limited': api_name in self.limited_apis,
            'total_block': self.total_block,
            'emergency_bypass': self.bypass_emergency,
            'circuit_state': self.circuit_states[api_name].value,
            'failure_count': self.failure_counts[api_name],
            'success_count': self.success_counts[api_name],
            'rate_limit_info': rate_info,
            'call_allowed': self.api_call_allowed(api_name)
        }
    
    def get_all_api_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 API 상태 정보 반환"""
        apis = set()
        apis.update(self.limited_apis)
        apis.update(self.circuit_states.keys())
        apis.update(self.rate_limits.keys())
        apis.update(['gemini', 'coupang', 'whisper'])  # 기본 API들
        
        return {api: self.get_api_status(api) for api in apis}


# 전역 API 제한기 인스턴스
_global_api_limiter = None

def get_api_limiter() -> APILimiter:
    """전역 API 제한기 인스턴스를 반환"""
    global _global_api_limiter
    if _global_api_limiter is None:
        _global_api_limiter = APILimiter()
    return _global_api_limiter


def api_rate_limited(api_name: str, essential: bool = False):
    """API Rate Limiting 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            limiter = get_api_limiter()
            
            # 호출 허용 여부 확인
            if not limiter.api_call_allowed(api_name, essential):
                # 예산 제한인지 확인
                budget_controller = get_budget_controller()
                if not budget_controller.can_make_api_call(api_name, essential):
                    usage_rate = budget_controller.current_spend / budget_controller.monthly_budget
                    threshold = 1.0 if budget_controller.emergency_mode else 0.95
                    
                    raise BudgetExceededException(
                        f"API 호출이 예산 제한으로 차단됨: {api_name}",
                        usage_rate,
                        threshold
                    )
                
                # 기타 제한 사유
                status = limiter.get_api_status(api_name)
                raise Exception(
                    f"API 호출이 제한되었습니다: {api_name}. "
                    f"상태: {status['circuit_state']}, "
                    f"제한됨: {status['is_limited']}"
                )
            
            # API 호출 실행
            start_time = time.time()
            success = False
            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                logger.error(f"API 호출 실패: {api_name} - {e}")
                raise
            finally:
                # 호출 결과 기록
                response_time = time.time() - start_time
                limiter.record_api_call(api_name, success, response_time)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            limiter = get_api_limiter()
            
            # 호출 허용 여부 확인
            if not limiter.api_call_allowed(api_name, essential):
                # 예산 제한인지 확인
                budget_controller = get_budget_controller()
                if not budget_controller.can_make_api_call(api_name, essential):
                    usage_rate = budget_controller.current_spend / budget_controller.monthly_budget
                    threshold = 1.0 if budget_controller.emergency_mode else 0.95
                    
                    raise BudgetExceededException(
                        f"API 호출이 예산 제한으로 차단됨: {api_name}",
                        usage_rate,
                        threshold
                    )
                
                # 기타 제한 사유
                status = limiter.get_api_status(api_name)
                raise Exception(
                    f"API 호출이 제한되었습니다: {api_name}. "
                    f"상태: {status['circuit_state']}, "
                    f"제한됨: {status['is_limited']}"
                )
            
            # API 호출 실행
            start_time = time.time()
            success = False
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                logger.error(f"API 호출 실패: {api_name} - {e}")
                raise
            finally:
                # 호출 결과 기록
                response_time = time.time() - start_time
                limiter.record_api_call(api_name, success, response_time)
        
        # 비동기 함수인지 확인
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator