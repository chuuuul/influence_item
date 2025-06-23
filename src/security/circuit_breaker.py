"""
Circuit Breaker 패턴 구현

API 장애 시 자동 차단 및 복구를 관리합니다.
"""

import time
import logging
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from threading import Lock
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit Breaker 상태"""
    CLOSED = "closed"      # 정상 상태
    OPEN = "open"         # 차단 상태
    HALF_OPEN = "half_open"  # 반개방 상태


@dataclass
class CircuitConfig:
    """Circuit Breaker 설정"""
    failure_threshold: int = 5      # 실패 임계치
    recovery_timeout: int = 60      # 복구 타임아웃 (초)
    expected_exception: tuple = (Exception,)  # 예상 예외 타입
    success_threshold: int = 3      # 반개방 상태에서 성공 임계치


@dataclass
class CircuitStats:
    """Circuit Breaker 통계"""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_calls: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """Circuit Breaker 구현"""
    
    def __init__(self, name: str, config: CircuitConfig, storage_path: Optional[Path] = None):
        """
        Args:
            name: Circuit Breaker 이름
            config: 설정
            storage_path: 상태 저장 경로
        """
        self.name = name
        self.config = config
        self.storage_path = storage_path or Path(f"logs/circuit_breaker_{name}.json")
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self.lock = Lock()
        
        # 저장 디렉토리 생성
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 기존 상태 로드
        self._load_state()
        
        logger.info(f"Circuit Breaker '{name}' 초기화 완료 - 상태: {self.state.value}")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Circuit Breaker를 통한 함수 호출
        
        Args:
            func: 호출할 함수
            *args, **kwargs: 함수 인자
            
        Returns:
            함수 실행 결과
            
        Raises:
            CircuitOpenError: Circuit이 열린 상태일 때
            기타: 함수 실행 중 발생한 예외
        """
        with self.lock:
            current_time = time.time()
            
            # 상태 확인 및 업데이트
            self._check_state(current_time)
            
            if self.state == CircuitState.OPEN:
                raise CircuitOpenError(f"Circuit '{self.name}' is open")
            
            self.stats.total_calls += 1
        
        # 함수 실행
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            
            # 성공 처리
            with self.lock:
                self._on_success(current_time, response_time)
            
            return result
            
        except self.config.expected_exception as e:
            # 예상된 예외 처리
            with self.lock:
                self._on_failure(current_time, str(e))
            raise
        except Exception as e:
            # 예상하지 못한 예외는 그대로 전파
            logger.warning(f"Circuit '{self.name}': 예상하지 못한 예외 - {str(e)}")
            raise
    
    def _check_state(self, current_time: float) -> None:
        """상태 확인 및 업데이트"""
        if self.state == CircuitState.OPEN:
            # 복구 타임아웃 확인
            if (self.stats.last_failure_time and 
                current_time - self.stats.last_failure_time >= self.config.recovery_timeout):
                self._transition_to_half_open()
        
        elif self.state == CircuitState.HALF_OPEN:
            # 반개방 상태에서 성공 임계치 확인
            if self.stats.success_count >= self.config.success_threshold:
                self._transition_to_closed()
    
    def _on_success(self, current_time: float, response_time: float) -> None:
        """성공 처리"""
        self.stats.success_count += 1
        self.stats.last_success_time = current_time
        
        if self.state == CircuitState.HALF_OPEN:
            if self.stats.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        
        # 상태 저장
        self._save_state()
        
        logger.debug(f"Circuit '{self.name}' 성공: response_time={response_time:.2f}s")
    
    def _on_failure(self, current_time: float, error_msg: str) -> None:
        """실패 처리"""
        self.stats.failure_count += 1
        self.stats.total_failures += 1
        self.stats.last_failure_time = current_time
        
        if self.state == CircuitState.CLOSED:
            if self.stats.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        
        # 상태 저장
        self._save_state()
        
        logger.warning(f"Circuit '{self.name}' 실패: {error_msg}")
    
    def _transition_to_open(self) -> None:
        """OPEN 상태로 전환"""
        self.state = CircuitState.OPEN
        self.stats.success_count = 0
        logger.warning(f"Circuit '{self.name}' OPEN 상태로 전환")
    
    def _transition_to_half_open(self) -> None:
        """HALF_OPEN 상태로 전환"""
        self.state = CircuitState.HALF_OPEN
        self.stats.failure_count = 0
        self.stats.success_count = 0
        logger.info(f"Circuit '{self.name}' HALF_OPEN 상태로 전환")
    
    def _transition_to_closed(self) -> None:
        """CLOSED 상태로 전환"""
        self.state = CircuitState.CLOSED
        self.stats.failure_count = 0
        self.stats.success_count = 0
        logger.info(f"Circuit '{self.name}' CLOSED 상태로 전환")
    
    def _load_state(self) -> None:
        """상태 로드"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # 상태 복원
            self.state = CircuitState(data.get("state", "closed"))
            
            # 통계 복원
            stats_data = data.get("stats", {})
            self.stats = CircuitStats(
                failure_count=stats_data.get("failure_count", 0),
                success_count=stats_data.get("success_count", 0),
                last_failure_time=stats_data.get("last_failure_time"),
                last_success_time=stats_data.get("last_success_time"),
                total_calls=stats_data.get("total_calls", 0),
                total_failures=stats_data.get("total_failures", 0)
            )
            
            logger.info(f"Circuit '{self.name}' 상태 로드 완료")
            
        except Exception as e:
            logger.warning(f"Circuit '{self.name}' 상태 로드 실패: {str(e)}")
    
    def _save_state(self) -> None:
        """상태 저장"""
        try:
            data = {
                "state": self.state.value,
                "stats": {
                    "failure_count": self.stats.failure_count,
                    "success_count": self.stats.success_count,
                    "last_failure_time": self.stats.last_failure_time,
                    "last_success_time": self.stats.last_success_time,
                    "total_calls": self.stats.total_calls,
                    "total_failures": self.stats.total_failures
                },
                "updated_at": time.time()
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Circuit '{self.name}' 상태 저장 실패: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.stats.failure_count,
                "success_count": self.stats.success_count,
                "total_calls": self.stats.total_calls,
                "total_failures": self.stats.total_failures,
                "failure_rate": self.stats.total_failures / max(1, self.stats.total_calls),
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold
                }
            }
    
    def reset(self) -> None:
        """Circuit Breaker 리셋"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self._save_state()
            logger.info(f"Circuit '{self.name}' 리셋 완료")
    
    def force_open(self) -> None:
        """강제로 OPEN 상태로 전환"""
        with self.lock:
            self._transition_to_open()
            self._save_state()
            logger.warning(f"Circuit '{self.name}' 강제 OPEN")
    
    def force_close(self) -> None:
        """강제로 CLOSED 상태로 전환"""
        with self.lock:
            self._transition_to_closed()
            self._save_state()
            logger.info(f"Circuit '{self.name}' 강제 CLOSE")


class CircuitOpenError(Exception):
    """Circuit이 열린 상태일 때 발생하는 예외"""
    pass


class CircuitBreakerManager:
    """Circuit Breaker 관리자"""
    
    def __init__(self):
        self.circuits: Dict[str, CircuitBreaker] = {}
        self.lock = Lock()
        self._setup_default_circuits()
        
        logger.info("Circuit Breaker Manager 초기화 완료")
    
    def _setup_default_circuits(self) -> None:
        """기본 Circuit Breaker 설정"""
        # Gemini API
        self.circuits["gemini"] = CircuitBreaker(
            name="gemini",
            config=CircuitConfig(
                failure_threshold=5,
                recovery_timeout=120,
                success_threshold=3
            )
        )
        
        # 쿠팡 API
        self.circuits["coupang"] = CircuitBreaker(
            name="coupang",
            config=CircuitConfig(
                failure_threshold=3,
                recovery_timeout=300,  # 5분
                success_threshold=2
            )
        )
        
        # Google Sheets API
        self.circuits["google_sheets"] = CircuitBreaker(
            name="google_sheets",
            config=CircuitConfig(
                failure_threshold=5,
                recovery_timeout=60,
                success_threshold=3
            )
        )
    
    def get_circuit(self, name: str) -> Optional[CircuitBreaker]:
        """Circuit Breaker 조회"""
        with self.lock:
            return self.circuits.get(name)
    
    def add_circuit(self, name: str, config: CircuitConfig) -> CircuitBreaker:
        """Circuit Breaker 추가"""
        with self.lock:
            circuit = CircuitBreaker(name, config)
            self.circuits[name] = circuit
            return circuit
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 Circuit Breaker 통계 조회"""
        with self.lock:
            return {name: circuit.get_stats() for name, circuit in self.circuits.items()}
    
    def reset_all(self) -> None:
        """모든 Circuit Breaker 리셋"""
        with self.lock:
            for circuit in self.circuits.values():
                circuit.reset()
            logger.info("모든 Circuit Breaker 리셋 완료")


# 전역 Circuit Breaker Manager 인스턴스
_circuit_manager = None

def get_circuit_manager() -> CircuitBreakerManager:
    """Circuit Breaker Manager 싱글톤 인스턴스 반환"""
    global _circuit_manager
    if _circuit_manager is None:
        _circuit_manager = CircuitBreakerManager()
    return _circuit_manager