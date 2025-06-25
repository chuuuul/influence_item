"""
Graceful Degradation 핸들러

네트워크 오류, API 실패 등의 상황에서 시스템이 완전히 중단되지 않도록
부분적 기능 제공 및 우아한 성능 저하를 구현합니다.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass
from enum import Enum
import asyncio
import functools
from pathlib import Path

from config.config import Config


class DegradationLevel(Enum):
    """성능 저하 레벨"""
    NONE = "none"  # 정상 동작
    PARTIAL = "partial"  # 부분 기능 제한
    MINIMAL = "minimal"  # 최소 기능만 제공
    OFFLINE = "offline"  # 오프라인 모드


@dataclass
class DegradationState:
    """현재 성능 저하 상태"""
    level: DegradationLevel
    affected_services: List[str]
    reason: str
    timestamp: float
    recovery_attempts: int = 0
    estimated_recovery_time: Optional[float] = None


@dataclass
class ServiceStatus:
    """개별 서비스 상태"""
    service_name: str
    is_available: bool
    last_check: float
    error_count: int
    last_error: Optional[str] = None
    fallback_enabled: bool = False


class GracefulDegradationHandler:
    """우아한 성능 저하 핸들러"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        성능 저하 핸들러 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # 서비스 상태 관리
        self.service_statuses: Dict[str, ServiceStatus] = {}
        self.current_degradation = DegradationState(
            level=DegradationLevel.NONE,
            affected_services=[],
            reason="정상 동작",
            timestamp=time.time()
        )
        
        # 오류 임계값 설정
        self.error_thresholds = {
            'youtube_api': 3,    # YouTube API 연속 실패 횟수
            'gemini_api': 3,     # Gemini API 연속 실패 횟수
            'whisper': 2,        # Whisper 처리 실패 횟수
            'network': 5,        # 네트워크 오류 횟수
            'gpu': 2            # GPU 오류 횟수
        }
        
        # 재시도 설정
        self.retry_configs = {
            'default': {'max_retries': 3, 'base_delay': 1.0, 'exponential_base': 2},
            'api_critical': {'max_retries': 5, 'base_delay': 2.0, 'exponential_base': 2},
            'gpu_memory': {'max_retries': 2, 'base_delay': 5.0, 'exponential_base': 1.5}
        }
        
        # 폴백 데이터 캐시
        self.fallback_cache: Dict[str, Any] = {}
        self._load_fallback_cache()
        
        self.logger.info("Graceful Degradation 핸들러 초기화 완료")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        
        try:
            if hasattr(self.config, 'LOG_LEVEL') and isinstance(self.config.LOG_LEVEL, str):
                level_str = self.config.LOG_LEVEL.upper()
                logger.setLevel(getattr(logging, level_str, logging.INFO))
            else:
                logger.setLevel(logging.INFO)
        except (AttributeError, TypeError):
            logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _load_fallback_cache(self):
        """폴백 데이터 캐시 로드"""
        try:
            cache_file = Path("temp/fallback_cache.json")
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.fallback_cache = json.load(f)
                self.logger.info("폴백 캐시 로드 완료")
        except Exception as e:
            self.logger.warning(f"폴백 캐시 로드 실패: {e}")
            self.fallback_cache = {}
    
    def _save_fallback_cache(self):
        """폴백 데이터 캐시 저장"""
        try:
            cache_file = Path("temp/fallback_cache.json")
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.fallback_cache, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.warning(f"폴백 캐시 저장 실패: {e}")
    
    def register_service(self, service_name: str):
        """서비스 등록"""
        if service_name not in self.service_statuses:
            self.service_statuses[service_name] = ServiceStatus(
                service_name=service_name,
                is_available=True,
                last_check=time.time(),
                error_count=0
            )
            self.logger.debug(f"서비스 등록: {service_name}")
    
    def record_service_error(self, service_name: str, error: str):
        """서비스 오류 기록"""
        self.register_service(service_name)
        
        status = self.service_statuses[service_name]
        status.error_count += 1
        status.last_error = error
        status.last_check = time.time()
        
        # 임계값 확인
        threshold = self.error_thresholds.get(service_name, 3)
        if status.error_count >= threshold:
            status.is_available = False
            self._update_degradation_state()
            self.logger.warning(f"서비스 {service_name} 비활성화됨 - 오류 {status.error_count}회")
        
        self.logger.debug(f"서비스 오류 기록: {service_name} - {error}")
    
    def record_service_success(self, service_name: str):
        """서비스 성공 기록"""
        self.register_service(service_name)
        
        status = self.service_statuses[service_name]
        status.error_count = max(0, status.error_count - 1)  # 점진적 복구
        status.last_check = time.time()
        
        # 완전 복구 확인
        if status.error_count == 0 and not status.is_available:
            status.is_available = True
            self._update_degradation_state()
            self.logger.info(f"서비스 {service_name} 복구됨")
    
    def _update_degradation_state(self):
        """성능 저하 상태 업데이트"""
        unavailable_services = [
            name for name, status in self.service_statuses.items()
            if not status.is_available
        ]
        
        # 저하 레벨 결정
        if not unavailable_services:
            new_level = DegradationLevel.NONE
            reason = "모든 서비스 정상"
        elif len(unavailable_services) == 1 and unavailable_services[0] not in ['gemini_api', 'whisper']:
            new_level = DegradationLevel.PARTIAL
            reason = f"부분 서비스 장애: {', '.join(unavailable_services)}"
        elif any(service in unavailable_services for service in ['gemini_api', 'whisper']):
            new_level = DegradationLevel.MINIMAL
            reason = f"핵심 서비스 장애: {', '.join(unavailable_services)}"
        else:
            new_level = DegradationLevel.OFFLINE
            reason = f"다중 서비스 장애: {', '.join(unavailable_services)}"
        
        # 상태 변경된 경우
        if new_level != self.current_degradation.level:
            old_level = self.current_degradation.level
            
            self.current_degradation = DegradationState(
                level=new_level,
                affected_services=unavailable_services,
                reason=reason,
                timestamp=time.time()
            )
            
            self.logger.warning(f"성능 저하 레벨 변경: {old_level.value} -> {new_level.value}")
            self.logger.warning(f"사유: {reason}")
    
    def get_current_degradation(self) -> DegradationState:
        """현재 성능 저하 상태 반환"""
        return self.current_degradation
    
    def is_service_available(self, service_name: str) -> bool:
        """서비스 가용성 확인"""
        if service_name not in self.service_statuses:
            return True  # 등록되지 않은 서비스는 가용한 것으로 간주
        
        return self.service_statuses[service_name].is_available
    
    def with_graceful_degradation(self, 
                                  service_name: str,
                                  fallback_func: Optional[Callable] = None,
                                  retry_config: str = 'default'):
        """
        Graceful Degradation 데코레이터
        
        Args:
            service_name: 서비스 이름
            fallback_func: 폴백 함수
            retry_config: 재시도 설정 키
        """
        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._execute_with_degradation(
                    func, service_name, fallback_func, retry_config, args, kwargs
                )
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if asyncio.iscoroutinefunction(func):
                    return asyncio.run(async_wrapper(*args, **kwargs))
                else:
                    return self._execute_with_degradation_sync(
                        func, service_name, fallback_func, retry_config, args, kwargs
                    )
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
    
    async def _execute_with_degradation(self, 
                                       func: Callable,
                                       service_name: str,
                                       fallback_func: Optional[Callable],
                                       retry_config: str,
                                       args: tuple,
                                       kwargs: dict) -> Any:
        """비동기 함수 실행 (Graceful Degradation 적용)"""
        retry_cfg = self.retry_configs.get(retry_config, self.retry_configs['default'])
        
        last_exception = None
        
        for attempt in range(retry_cfg['max_retries'] + 1):
            try:
                # 서비스가 비활성화된 경우 즉시 폴백
                if not self.is_service_available(service_name):
                    raise Exception(f"서비스 {service_name}가 비활성화됨")
                
                # 함수 실행
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 성공 기록
                self.record_service_success(service_name)
                
                # 결과 캐싱 (폴백용)
                self._cache_successful_result(service_name, result, args, kwargs)
                
                return result
                
            except Exception as e:
                last_exception = e
                self.record_service_error(service_name, str(e))
                
                # 재시도 대기
                if attempt < retry_cfg['max_retries']:
                    delay = retry_cfg['base_delay'] * (retry_cfg['exponential_base'] ** attempt)
                    self.logger.warning(f"{service_name} 재시도 {attempt + 1}/{retry_cfg['max_retries']} - {delay:.1f}초 후")
                    await asyncio.sleep(delay)
        
        # 모든 재시도 실패 - 폴백 실행
        self.logger.error(f"{service_name} 모든 재시도 실패: {last_exception}")
        
        if fallback_func:
            try:
                self.logger.info(f"{service_name} 폴백 함수 실행")
                if asyncio.iscoroutinefunction(fallback_func):
                    return await fallback_func(*args, **kwargs)
                else:
                    return fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                self.logger.error(f"{service_name} 폴백 함수 실패: {fallback_error}")
        
        # 캐시된 결과 확인
        cached_result = self._get_cached_result(service_name, args, kwargs)
        if cached_result is not None:
            self.logger.info(f"{service_name} 캐시된 결과 반환")
            return cached_result
        
        # 최종적으로 원본 예외 발생
        raise last_exception
    
    def _execute_with_degradation_sync(self, 
                                      func: Callable,
                                      service_name: str,
                                      fallback_func: Optional[Callable],
                                      retry_config: str,
                                      args: tuple,
                                      kwargs: dict) -> Any:
        """동기 함수 실행 (Graceful Degradation 적용)"""
        retry_cfg = self.retry_configs.get(retry_config, self.retry_configs['default'])
        
        last_exception = None
        
        for attempt in range(retry_cfg['max_retries'] + 1):
            try:
                # 서비스가 비활성화된 경우 즉시 폴백
                if not self.is_service_available(service_name):
                    raise Exception(f"서비스 {service_name}가 비활성화됨")
                
                # 함수 실행
                result = func(*args, **kwargs)
                
                # 성공 기록
                self.record_service_success(service_name)
                
                # 결과 캐싱 (폴백용)
                self._cache_successful_result(service_name, result, args, kwargs)
                
                return result
                
            except Exception as e:
                last_exception = e
                self.record_service_error(service_name, str(e))
                
                # 재시도 대기
                if attempt < retry_cfg['max_retries']:
                    delay = retry_cfg['base_delay'] * (retry_cfg['exponential_base'] ** attempt)
                    self.logger.warning(f"{service_name} 재시도 {attempt + 1}/{retry_cfg['max_retries']} - {delay:.1f}초 후")
                    time.sleep(delay)
        
        # 모든 재시도 실패 - 폴백 실행
        self.logger.error(f"{service_name} 모든 재시도 실패: {last_exception}")
        
        if fallback_func:
            try:
                self.logger.info(f"{service_name} 폴백 함수 실행")
                return fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                self.logger.error(f"{service_name} 폴백 함수 실패: {fallback_error}")
        
        # 캐시된 결과 확인
        cached_result = self._get_cached_result(service_name, args, kwargs)
        if cached_result is not None:
            self.logger.info(f"{service_name} 캐시된 결과 반환")
            return cached_result
        
        # 최종적으로 원본 예외 발생
        raise last_exception
    
    def _cache_successful_result(self, service_name: str, result: Any, args: tuple, kwargs: dict):
        """성공한 결과 캐싱"""
        try:
            # 간단한 해시 기반 키 생성
            cache_key = f"{service_name}:{hash(str(args) + str(kwargs))}"
            
            # JSON 직렬화 가능한 결과만 캐싱
            if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
                self.fallback_cache[cache_key] = {
                    'result': result,
                    'timestamp': time.time(),
                    'service': service_name
                }
                
                # 캐시 크기 제한 (최근 100개만 유지)
                if len(self.fallback_cache) > 100:
                    oldest_key = min(self.fallback_cache.keys(), 
                                   key=lambda k: self.fallback_cache[k]['timestamp'])
                    del self.fallback_cache[oldest_key]
                
                self._save_fallback_cache()
                
        except Exception as e:
            self.logger.debug(f"결과 캐싱 실패: {e}")
    
    def _get_cached_result(self, service_name: str, args: tuple, kwargs: dict) -> Any:
        """캐시된 결과 조회"""
        try:
            cache_key = f"{service_name}:{hash(str(args) + str(kwargs))}"
            
            if cache_key in self.fallback_cache:
                cached_data = self.fallback_cache[cache_key]
                # 24시간 이내 캐시만 사용
                if time.time() - cached_data['timestamp'] < 86400:
                    return cached_data['result']
                else:
                    # 만료된 캐시 제거
                    del self.fallback_cache[cache_key]
                    
        except Exception as e:
            self.logger.debug(f"캐시 조회 실패: {e}")
        
        return None
    
    def get_fallback_youtube_metadata(self, video_url: str) -> Dict[str, Any]:
        """YouTube 메타데이터 폴백"""
        import re
        
        # URL에서 비디오 ID 추출
        url_pattern = r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
        video_id_match = re.search(url_pattern, video_url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        
        return {
            'video_title': f'영상 제목 ({video_id})',
            'channel_name': '알려지지 않은 채널',
            'channel_id': 'unknown',
            'upload_date': '2024-01-01',
            'view_count': 0,
            'like_count': 0,
            'subscriber_count': 0
        }
    
    def get_fallback_transcription_result(self) -> List[Dict[str, Any]]:
        """Whisper 폴백 결과"""
        return [
            {
                'start': 0.0,
                'end': 10.0,
                'text': '음성 인식 결과를 가져올 수 없습니다.',
                'segment_id': 0
            }
        ]
    
    def get_fallback_gemini_analysis(self) -> List[Dict[str, Any]]:
        """Gemini 분석 폴백 결과"""
        return [
            {
                'start_time': 0,
                'end_time': 30,
                'reason': 'API 응답 불가로 인한 기본 후보 구간',
                'confidence_score': 0.3,
                'product_mentions': ['제품명 불명'],
                'analysis_note': 'Gemini API 오류로 인한 폴백 결과'
            }
        ]
    
    def get_system_status_report(self) -> Dict[str, Any]:
        """시스템 상태 보고서 생성"""
        return {
            'degradation_state': {
                'level': self.current_degradation.level.value,
                'affected_services': self.current_degradation.affected_services,
                'reason': self.current_degradation.reason,
                'timestamp': self.current_degradation.timestamp
            },
            'service_statuses': {
                name: {
                    'available': status.is_available,
                    'error_count': status.error_count,
                    'last_check': status.last_check,
                    'last_error': status.last_error,
                    'fallback_enabled': status.fallback_enabled
                }
                for name, status in self.service_statuses.items()
            },
            'cache_stats': {
                'cached_items': len(self.fallback_cache),
                'cache_services': list(set(
                    item['service'] for item in self.fallback_cache.values()
                ))
            },
            'recommendations': self._get_recovery_recommendations()
        }
    
    def _get_recovery_recommendations(self) -> List[str]:
        """복구 권장사항 생성"""
        recommendations = []
        
        if self.current_degradation.level != DegradationLevel.NONE:
            recommendations.append("시스템 상태를 확인하고 오류 로그를 검토하세요.")
            
            if 'network' in self.current_degradation.affected_services:
                recommendations.append("네트워크 연결 상태를 확인하세요.")
            
            if 'youtube_api' in self.current_degradation.affected_services:
                recommendations.append("YouTube API 할당량을 확인하세요.")
            
            if 'gemini_api' in self.current_degradation.affected_services:
                recommendations.append("Gemini API 키와 할당량을 확인하세요.")
            
            if 'gpu' in self.current_degradation.affected_services:
                recommendations.append("GPU 메모리와 드라이버 상태를 확인하세요.")
        
        return recommendations


# 전역 인스턴스
_global_degradation_handler: Optional[GracefulDegradationHandler] = None


def get_degradation_handler(config: Optional[Config] = None) -> GracefulDegradationHandler:
    """전역 Graceful Degradation 핸들러 반환"""
    global _global_degradation_handler
    
    if _global_degradation_handler is None:
        _global_degradation_handler = GracefulDegradationHandler(config)
    
    return _global_degradation_handler


def with_graceful_degradation(service_name: str,
                             fallback_func: Optional[Callable] = None,
                             retry_config: str = 'default'):
    """
    Graceful Degradation 데코레이터 (편의 함수)
    
    Args:
        service_name: 서비스 이름
        fallback_func: 폴백 함수
        retry_config: 재시도 설정
    """
    handler = get_degradation_handler()
    return handler.with_graceful_degradation(service_name, fallback_func, retry_config)