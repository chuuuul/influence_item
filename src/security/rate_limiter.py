"""
API 호출 레이트 리미팅 시스템

API 호출 빈도를 제한하고 모니터링합니다.
"""

import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from threading import Lock
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RateLimit:
    """레이트 리미트 설정"""
    calls_per_minute: int
    calls_per_hour: int
    calls_per_day: int


@dataclass
class CallRecord:
    """API 호출 기록"""
    timestamp: float
    api_name: str
    success: bool
    response_time: Optional[float] = None


class RateLimiter:
    """API 레이트 리미터"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Args:
            storage_path: 호출 기록 저장 경로
        """
        self.storage_path = storage_path or Path("logs/api_calls.json")
        self.call_history: Dict[str, List[CallRecord]] = {}
        self.limits: Dict[str, RateLimit] = {}
        self.lock = Lock()
        
        # 기본 레이트 리미트 설정
        self._setup_default_limits()
        
        # 저장 디렉토리 생성
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 기존 기록 로드
        self._load_call_history()
        
        logger.info("API 레이트 리미터 초기화 완료")
    
    def _setup_default_limits(self) -> None:
        """기본 레이트 리미트 설정"""
        self.limits = {
            "gemini": RateLimit(
                calls_per_minute=60,
                calls_per_hour=1500,
                calls_per_day=1500
            ),
            "coupang": RateLimit(
                calls_per_minute=2,
                calls_per_hour=10,
                calls_per_day=100
            ),
            "google_sheets": RateLimit(
                calls_per_minute=60,
                calls_per_hour=1000,
                calls_per_day=3000
            ),
            "whisper": RateLimit(
                calls_per_minute=10,
                calls_per_hour=200,
                calls_per_day=500
            )
        }
    
    def set_rate_limit(self, api_name: str, limit: RateLimit) -> None:
        """API별 레이트 리미트 설정"""
        with self.lock:
            self.limits[api_name] = limit
            logger.info(f"API '{api_name}' 레이트 리미트 설정: {limit}")
    
    def can_make_call(self, api_name: str) -> bool:
        """API 호출 가능 여부 확인"""
        with self.lock:
            if api_name not in self.limits:
                logger.warning(f"API '{api_name}'에 대한 레이트 리미트 설정이 없습니다")
                return True
            
            limit = self.limits[api_name]
            history = self.call_history.get(api_name, [])
            
            current_time = time.time()
            
            # 시간대별 호출 수 계산
            minute_calls = self._count_calls_in_period(history, current_time, 60)
            hour_calls = self._count_calls_in_period(history, current_time, 3600)
            day_calls = self._count_calls_in_period(history, current_time, 86400)
            
            # 리미트 확인
            if minute_calls >= limit.calls_per_minute:
                logger.warning(f"API '{api_name}' 분당 호출 제한 도달: {minute_calls}/{limit.calls_per_minute}")
                return False
            
            if hour_calls >= limit.calls_per_hour:
                logger.warning(f"API '{api_name}' 시간당 호출 제한 도달: {hour_calls}/{limit.calls_per_hour}")
                return False
            
            if day_calls >= limit.calls_per_day:
                logger.warning(f"API '{api_name}' 일당 호출 제한 도달: {day_calls}/{limit.calls_per_day}")
                return False
            
            return True
    
    def record_call(self, api_name: str, success: bool, response_time: Optional[float] = None) -> None:
        """API 호출 기록"""
        with self.lock:
            if api_name not in self.call_history:
                self.call_history[api_name] = []
            
            record = CallRecord(
                timestamp=time.time(),
                api_name=api_name,
                success=success,
                response_time=response_time
            )
            
            self.call_history[api_name].append(record)
            
            # 오래된 기록 정리 (7일 이상)
            self._cleanup_old_records(api_name)
            
            logger.debug(f"API '{api_name}' 호출 기록: success={success}, response_time={response_time}")
    
    def _count_calls_in_period(self, history: List[CallRecord], current_time: float, period_seconds: int) -> int:
        """특정 기간 내 호출 수 계산"""
        cutoff_time = current_time - period_seconds
        return sum(1 for record in history if record.timestamp >= cutoff_time)
    
    def _cleanup_old_records(self, api_name: str, max_age_days: int = 7) -> None:
        """오래된 호출 기록 정리"""
        cutoff_time = time.time() - (max_age_days * 86400)
        self.call_history[api_name] = [
            record for record in self.call_history[api_name]
            if record.timestamp >= cutoff_time
        ]
    
    def get_call_stats(self, api_name: str) -> Dict[str, int]:
        """API 호출 통계 조회"""
        with self.lock:
            history = self.call_history.get(api_name, [])
            current_time = time.time()
            
            stats = {
                "minute_calls": self._count_calls_in_period(history, current_time, 60),
                "hour_calls": self._count_calls_in_period(history, current_time, 3600),
                "day_calls": self._count_calls_in_period(history, current_time, 86400),
                "total_calls": len(history),
                "success_calls": sum(1 for record in history if record.success),
                "error_calls": sum(1 for record in history if not record.success)
            }
            
            if api_name in self.limits:
                limit = self.limits[api_name]
                stats.update({
                    "minute_limit": limit.calls_per_minute,
                    "hour_limit": limit.calls_per_hour,
                    "day_limit": limit.calls_per_day,
                    "minute_remaining": max(0, limit.calls_per_minute - stats["minute_calls"]),
                    "hour_remaining": max(0, limit.calls_per_hour - stats["hour_calls"]),
                    "day_remaining": max(0, limit.calls_per_day - stats["day_calls"])
                })
            
            return stats
    
    def get_next_available_time(self, api_name: str) -> Optional[float]:
        """다음 호출 가능 시간 계산"""
        if self.can_make_call(api_name):
            return None
        
        with self.lock:
            if api_name not in self.limits:
                return None
            
            limit = self.limits[api_name]
            history = self.call_history.get(api_name, [])
            current_time = time.time()
            
            # 가장 제한적인 시간 찾기
            next_times = []
            
            # 분당 제한
            minute_calls = [r for r in history if r.timestamp >= current_time - 60]
            if len(minute_calls) >= limit.calls_per_minute:
                oldest_in_minute = min(minute_calls, key=lambda x: x.timestamp)
                next_times.append(oldest_in_minute.timestamp + 60)
            
            # 시간당 제한
            hour_calls = [r for r in history if r.timestamp >= current_time - 3600]
            if len(hour_calls) >= limit.calls_per_hour:
                oldest_in_hour = min(hour_calls, key=lambda x: x.timestamp)
                next_times.append(oldest_in_hour.timestamp + 3600)
            
            # 일당 제한
            day_calls = [r for r in history if r.timestamp >= current_time - 86400]
            if len(day_calls) >= limit.calls_per_day:
                oldest_in_day = min(day_calls, key=lambda x: x.timestamp)
                next_times.append(oldest_in_day.timestamp + 86400)
            
            return min(next_times) if next_times else None
    
    def _load_call_history(self) -> None:
        """호출 기록 로드"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # JSON에서 CallRecord 객체로 변환
            for api_name, records in data.items():
                self.call_history[api_name] = [
                    CallRecord(
                        timestamp=record["timestamp"],
                        api_name=record["api_name"],
                        success=record["success"],
                        response_time=record.get("response_time")
                    )
                    for record in records
                ]
            
            logger.info(f"API 호출 기록 로드 완료: {len(data)}개 API")
            
        except Exception as e:
            logger.warning(f"API 호출 기록 로드 실패: {str(e)}")
    
    def save_call_history(self) -> None:
        """호출 기록 저장"""
        try:
            # CallRecord 객체를 JSON 직렬화 가능한 형태로 변환
            data = {}
            for api_name, records in self.call_history.items():
                data[api_name] = [
                    {
                        "timestamp": record.timestamp,
                        "api_name": record.api_name,
                        "success": record.success,
                        "response_time": record.response_time
                    }
                    for record in records
                ]
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("API 호출 기록 저장 완료")
            
        except Exception as e:
            logger.error(f"API 호출 기록 저장 실패: {str(e)}")
    
    def wait_for_rate_limit(self, api_name: str) -> float:
        """레이트 리미트 대기"""
        next_available = self.get_next_available_time(api_name)
        if next_available is None:
            return 0.0
        
        wait_time = next_available - time.time()
        if wait_time > 0:
            logger.info(f"API '{api_name}' 레이트 리미트 대기: {wait_time:.1f}초")
            time.sleep(wait_time)
        
        return wait_time


# 전역 레이트 리미터 인스턴스
_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    """레이트 리미터 싱글톤 인스턴스 반환"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter