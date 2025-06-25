"""
API 캐시 관리자

YouTube API와 Gemini API의 효율적 사용을 위한 
캐싱, 배치 처리, 할당량 관리 시스템입니다.
"""

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from contextlib import asynccontextmanager

from config.config import Config


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    data: Any
    timestamp: float
    expiry_time: float
    hit_count: int = 0
    size_bytes: int = 0
    api_cost: float = 0.0


@dataclass
class APIQuotaInfo:
    """API 할당량 정보"""
    service_name: str
    daily_limit: int
    current_usage: int
    reset_time: float
    cost_per_request: float
    burst_limit: int = 0
    burst_window: int = 60  # 초


@dataclass
class BatchRequest:
    """배치 요청"""
    id: str
    api_name: str
    method: str
    params: Dict[str, Any]
    callback: Optional[Callable] = None
    priority: int = 0
    created_at: float = 0.0


class APIRateLimiter:
    """API 속도 제한기"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Args:
            max_requests: 시간 윈도우 당 최대 요청 수
            time_window: 시간 윈도우 (초)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
    
    def is_allowed(self) -> bool:
        """요청 허용 여부 확인"""
        with self.lock:
            current_time = time.time()
            # 시간 윈도우 밖의 요청들 제거
            self.requests = [req_time for req_time in self.requests 
                           if current_time - req_time < self.time_window]
            
            return len(self.requests) < self.max_requests
    
    def add_request(self):
        """요청 기록"""
        with self.lock:
            self.requests.append(time.time())
    
    def get_wait_time(self) -> float:
        """다음 요청까지 대기 시간"""
        with self.lock:
            if len(self.requests) < self.max_requests:
                return 0.0
            
            oldest_request = min(self.requests) if self.requests else 0
            return max(0, self.time_window - (time.time() - oldest_request))


class APICacheManager:
    """API 캐시 관리자"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        API 캐시 관리자 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # 캐시 설정
        self.cache_dir = Path("temp/api_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 메모리 캐시
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_lock = threading.RLock()
        
        # 디스크 캐시 설정
        self.disk_cache_enabled = getattr(config, 'ENABLE_DISK_CACHE', True)
        self.max_memory_cache_size = getattr(config, 'MAX_MEMORY_CACHE_SIZE', 100 * 1024 * 1024)  # 100MB
        self.current_cache_size = 0
        
        # 캐시 만료 시간 설정 (초)
        self.default_cache_ttl = {
            'youtube_video_info': 24 * 3600,      # 24시간
            'youtube_channel_info': 12 * 3600,    # 12시간
            'gemini_analysis': 7 * 24 * 3600,     # 7일
            'whisper_transcription': 30 * 24 * 3600,  # 30일
            'monetization_check': 3 * 3600,       # 3시간
            'default': 3600                       # 1시간
        }
        
        # API 할당량 관리
        self.api_quotas: Dict[str, APIQuotaInfo] = {}
        self.rate_limiters: Dict[str, APIRateLimiter] = {}
        
        # 배치 처리
        self.batch_queues: Dict[str, List[BatchRequest]] = defaultdict(list)
        self.batch_processors: Dict[str, asyncio.Task] = {}
        self.batch_lock = asyncio.Lock()
        
        # 통계
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_requests_saved': 0,
            'total_api_cost_saved': 0.0,
            'batch_requests_processed': 0
        }
        
        self._initialize_api_quotas()
        self._initialize_rate_limiters()
        self._start_cleanup_task()
        
        self.logger.info("API 캐시 관리자 초기화 완료")
    
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
    
    def _initialize_api_quotas(self):
        """API 할당량 초기화"""
        quotas = [
            APIQuotaInfo(
                service_name='youtube_api',
                daily_limit=getattr(self.config, 'YOUTUBE_API_DAILY_QUOTA', 10000),
                current_usage=0,
                reset_time=self._get_next_reset_time(),
                cost_per_request=1.0,
                burst_limit=100,
                burst_window=60
            ),
            APIQuotaInfo(
                service_name='gemini_api',
                daily_limit=getattr(self.config, 'GEMINI_API_DAILY_QUOTA', 1000),
                current_usage=0,
                reset_time=self._get_next_reset_time(),
                cost_per_request=0.1,
                burst_limit=60,
                burst_window=60
            )
        ]
        
        for quota in quotas:
            self.api_quotas[quota.service_name] = quota
    
    def _initialize_rate_limiters(self):
        """속도 제한기 초기화"""
        self.rate_limiters['youtube_api'] = APIRateLimiter(100, 60)  # 분당 100회
        self.rate_limiters['gemini_api'] = APIRateLimiter(60, 60)    # 분당 60회
        self.rate_limiters['whisper'] = APIRateLimiter(10, 60)       # 분당 10회
    
    def _get_next_reset_time(self) -> float:
        """다음 할당량 리셋 시간 계산"""
        now = datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow.timestamp()
    
    def _start_cleanup_task(self):
        """정리 작업 시작"""
        import threading
        
        def cleanup_worker():
            while True:
                try:
                    self._cleanup_expired_cache()
                    time.sleep(300)  # 5분마다 실행
                except Exception as e:
                    self.logger.error(f"캐시 정리 작업 오류: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def generate_cache_key(self, api_name: str, method: str, params: Dict[str, Any]) -> str:
        """캐시 키 생성"""
        # 파라미터를 정렬하여 일관된 키 생성
        sorted_params = json.dumps(params, sort_keys=True, ensure_ascii=False)
        cache_string = f"{api_name}:{method}:{sorted_params}"
        
        # SHA256 해시로 키 생성
        return hashlib.sha256(cache_string.encode()).hexdigest()
    
    def get_from_cache(self, cache_key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        with self.cache_lock:
            # 메모리 캐시 확인
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                
                # 만료 확인
                if time.time() <= entry.expiry_time:
                    entry.hit_count += 1
                    self.stats['cache_hits'] += 1
                    self.logger.debug(f"캐시 히트: {cache_key[:16]}...")
                    return entry.data
                else:
                    # 만료된 엔트리 제거
                    del self.memory_cache[cache_key]
                    self.current_cache_size -= entry.size_bytes
            
            # 디스크 캐시 확인
            if self.disk_cache_enabled:
                disk_data = self._load_from_disk_cache(cache_key)
                if disk_data is not None:
                    self.stats['cache_hits'] += 1
                    self.logger.debug(f"디스크 캐시 히트: {cache_key[:16]}...")
                    return disk_data
            
            self.stats['cache_misses'] += 1
            return None
    
    def save_to_cache(
        self, 
        cache_key: str, 
        data: Any, 
        api_name: str,
        ttl: Optional[int] = None,
        api_cost: float = 0.0
    ):
        """캐시에 데이터 저장"""
        if ttl is None:
            ttl = self.default_cache_ttl.get(api_name, self.default_cache_ttl['default'])
        
        expiry_time = time.time() + ttl
        data_size = len(json.dumps(data, ensure_ascii=False).encode())
        
        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            expiry_time=expiry_time,
            size_bytes=data_size,
            api_cost=api_cost
        )
        
        with self.cache_lock:
            # 메모리 용량 확인 및 정리
            while (self.current_cache_size + data_size > self.max_memory_cache_size 
                   and self.memory_cache):
                self._evict_lru_entry()
            
            # 메모리 캐시에 저장
            if cache_key in self.memory_cache:
                self.current_cache_size -= self.memory_cache[cache_key].size_bytes
            
            self.memory_cache[cache_key] = entry
            self.current_cache_size += data_size
            
            # 디스크 캐시에도 저장
            if self.disk_cache_enabled:
                self._save_to_disk_cache(cache_key, entry)
            
            self.logger.debug(f"캐시 저장: {cache_key[:16]}... (크기: {data_size} bytes)")
    
    def _evict_lru_entry(self):
        """LRU 정책으로 캐시 엔트리 제거"""
        if not self.memory_cache:
            return
        
        # 마지막 액세스 시간이 가장 오래된 엔트리 찾기
        lru_key = min(
            self.memory_cache.keys(),
            key=lambda k: self.memory_cache[k].timestamp - self.memory_cache[k].hit_count * 3600
        )
        
        entry = self.memory_cache.pop(lru_key)
        self.current_cache_size -= entry.size_bytes
        self.logger.debug(f"LRU 캐시 제거: {lru_key[:16]}...")
    
    def _load_from_disk_cache(self, cache_key: str) -> Optional[Any]:
        """디스크 캐시에서 로드"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 만료 확인
            if time.time() > cache_data.get('expiry_time', 0):
                cache_file.unlink()  # 만료된 파일 삭제
                return None
            
            return cache_data.get('data')
            
        except Exception as e:
            self.logger.debug(f"디스크 캐시 로드 실패: {e}")
            return None
    
    def _save_to_disk_cache(self, cache_key: str, entry: CacheEntry):
        """디스크 캐시에 저장"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            cache_data = {
                'data': entry.data,
                'timestamp': entry.timestamp,
                'expiry_time': entry.expiry_time,
                'api_cost': entry.api_cost
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.warning(f"디스크 캐시 저장 실패: {e}")
    
    def _cleanup_expired_cache(self):
        """만료된 캐시 정리"""
        current_time = time.time()
        
        with self.cache_lock:
            # 메모리 캐시 정리
            expired_keys = [
                key for key, entry in self.memory_cache.items()
                if current_time > entry.expiry_time
            ]
            
            for key in expired_keys:
                entry = self.memory_cache.pop(key)
                self.current_cache_size -= entry.size_bytes
            
            if expired_keys:
                self.logger.info(f"만료된 메모리 캐시 {len(expired_keys)}개 정리")
        
        # 디스크 캐시 정리
        if self.disk_cache_enabled:
            try:
                expired_files = []
                for cache_file in self.cache_dir.glob("*.json"):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        if current_time > cache_data.get('expiry_time', 0):
                            cache_file.unlink()
                            expired_files.append(cache_file.name)
                    except:
                        continue
                
                if expired_files:
                    self.logger.info(f"만료된 디스크 캐시 {len(expired_files)}개 정리")
                    
            except Exception as e:
                self.logger.warning(f"디스크 캐시 정리 실패: {e}")
    
    def check_api_quota(self, api_name: str) -> bool:
        """API 할당량 확인"""
        if api_name not in self.api_quotas:
            return True  # 제한 없음
        
        quota = self.api_quotas[api_name]
        
        # 일일 할당량 리셋 확인
        if time.time() >= quota.reset_time:
            quota.current_usage = 0
            quota.reset_time = self._get_next_reset_time()
            self.logger.info(f"{api_name} 할당량 리셋")
        
        # 할당량 확인
        return quota.current_usage < quota.daily_limit
    
    def record_api_usage(self, api_name: str, cost: float = 1.0):
        """API 사용량 기록"""
        if api_name in self.api_quotas:
            self.api_quotas[api_name].current_usage += cost
        
        if api_name in self.rate_limiters:
            self.rate_limiters[api_name].add_request()
    
    def wait_for_rate_limit(self, api_name: str) -> float:
        """속도 제한 대기"""
        if api_name not in self.rate_limiters:
            return 0.0
        
        limiter = self.rate_limiters[api_name]
        wait_time = limiter.get_wait_time()
        
        if wait_time > 0:
            self.logger.info(f"{api_name} 속도 제한으로 {wait_time:.1f}초 대기")
        
        return wait_time
    
    async def cached_api_call(
        self,
        api_name: str,
        method: str,
        api_func: Callable,
        params: Dict[str, Any],
        force_refresh: bool = False,
        ttl: Optional[int] = None
    ) -> Any:
        """캐시된 API 호출"""
        # 캐시 키 생성
        cache_key = self.generate_cache_key(api_name, method, params)
        
        # 캐시에서 조회 (강제 새로고침이 아닌 경우)
        if not force_refresh:
            cached_data = self.get_from_cache(cache_key)
            if cached_data is not None:
                # API 비용 절약 기록
                if api_name in self.api_quotas:
                    cost_saved = self.api_quotas[api_name].cost_per_request
                    self.stats['total_api_cost_saved'] += cost_saved
                    self.stats['api_requests_saved'] += 1
                
                return cached_data
        
        # API 할당량 확인
        if not self.check_api_quota(api_name):
            raise Exception(f"{api_name} 일일 할당량 초과")
        
        # 속도 제한 확인
        wait_time = self.wait_for_rate_limit(api_name)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        try:
            # API 호출
            self.logger.debug(f"API 호출: {api_name}.{method}")
            
            if asyncio.iscoroutinefunction(api_func):
                result = await api_func(**params)
            else:
                result = api_func(**params)
            
            # 사용량 기록
            cost = self.api_quotas.get(api_name, APIQuotaInfo('', 0, 0, 0, 1.0)).cost_per_request
            self.record_api_usage(api_name, cost)
            
            # 캐시에 저장
            self.save_to_cache(cache_key, result, api_name, ttl, cost)
            
            return result
            
        except Exception as e:
            self.logger.error(f"API 호출 실패: {api_name}.{method} - {str(e)}")
            raise
    
    async def add_to_batch(
        self,
        api_name: str,
        method: str,
        params: Dict[str, Any],
        callback: Optional[Callable] = None,
        priority: int = 0
    ) -> str:
        """배치 요청 추가"""
        request_id = f"{api_name}_{method}_{int(time.time() * 1000)}_{len(self.batch_queues[api_name])}"
        
        request = BatchRequest(
            id=request_id,
            api_name=api_name,
            method=method,
            params=params,
            callback=callback,
            priority=priority,
            created_at=time.time()
        )
        
        async with self.batch_lock:
            self.batch_queues[api_name].append(request)
            
            # 배치 프로세서가 없으면 시작
            if api_name not in self.batch_processors:
                self.batch_processors[api_name] = asyncio.create_task(
                    self._process_batch_queue(api_name)
                )
        
        return request_id
    
    async def _process_batch_queue(self, api_name: str):
        """배치 큐 처리"""
        batch_size = 10  # 배치 크기
        batch_delay = 5   # 배치 대기 시간 (초)
        
        while True:
            try:
                async with self.batch_lock:
                    if not self.batch_queues[api_name]:
                        # 큐가 비어있으면 프로세서 종료
                        del self.batch_processors[api_name]
                        break
                    
                    # 우선순위 순으로 정렬
                    self.batch_queues[api_name].sort(
                        key=lambda x: (-x.priority, x.created_at)
                    )
                    
                    # 배치 추출
                    batch = self.batch_queues[api_name][:batch_size]
                    self.batch_queues[api_name] = self.batch_queues[api_name][batch_size:]
                
                if batch:
                    await self._execute_batch(api_name, batch)
                
                await asyncio.sleep(batch_delay)
                
            except Exception as e:
                self.logger.error(f"배치 처리 오류 ({api_name}): {e}")
                await asyncio.sleep(batch_delay)
    
    async def _execute_batch(self, api_name: str, batch: List[BatchRequest]):
        """배치 실행"""
        self.logger.info(f"{api_name} 배치 처리 시작: {len(batch)}개 요청")
        
        results = []
        for request in batch:
            try:
                # 실제 API 호출은 여기서 구현
                # 각 API별로 다른 처리 방식 적용
                result = await self._execute_single_request(request)
                results.append((request.id, result, None))
                
                # 콜백 실행
                if request.callback:
                    try:
                        if asyncio.iscoroutinefunction(request.callback):
                            await request.callback(result)
                        else:
                            request.callback(result)
                    except Exception as cb_error:
                        self.logger.warning(f"콜백 실행 실패: {cb_error}")
                
            except Exception as e:
                results.append((request.id, None, str(e)))
                self.logger.error(f"배치 요청 실패: {request.id} - {str(e)}")
        
        self.stats['batch_requests_processed'] += len(batch)
        self.logger.info(f"{api_name} 배치 처리 완료: {len(results)}개 결과")
    
    async def _execute_single_request(self, request: BatchRequest) -> Any:
        """단일 요청 실행"""
        # 여기서는 인터페이스만 제공
        # 실제 구현에서는 각 API별 처리 로직 구현
        await asyncio.sleep(0.1)  # 시뮬레이션
        return {"status": "success", "request_id": request.id}
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'hit_rate_percent': round(hit_rate, 2),
            'api_requests_saved': self.stats['api_requests_saved'],
            'total_cost_saved': round(self.stats['total_api_cost_saved'], 2),
            'batch_requests_processed': self.stats['batch_requests_processed'],
            'memory_cache_size_mb': round(self.current_cache_size / (1024 * 1024), 2),
            'memory_cache_entries': len(self.memory_cache),
            'api_quotas': {
                name: {
                    'current_usage': quota.current_usage,
                    'daily_limit': quota.daily_limit,
                    'usage_percent': round(quota.current_usage / quota.daily_limit * 100, 2)
                }
                for name, quota in self.api_quotas.items()
            }
        }
    
    def clear_cache(self, api_name: Optional[str] = None):
        """캐시 지우기"""
        with self.cache_lock:
            if api_name:
                # 특정 API 캐시만 지우기
                keys_to_remove = [
                    key for key in self.memory_cache.keys()
                    if key.startswith(f"{api_name}:")
                ]
                
                for key in keys_to_remove:
                    entry = self.memory_cache.pop(key)
                    self.current_cache_size -= entry.size_bytes
                
                self.logger.info(f"{api_name} 캐시 {len(keys_to_remove)}개 항목 삭제")
            else:
                # 전체 캐시 지우기
                self.memory_cache.clear()
                self.current_cache_size = 0
                self.logger.info("전체 캐시 삭제")
        
        # 디스크 캐시도 지우기
        if self.disk_cache_enabled:
            try:
                if api_name:
                    for cache_file in self.cache_dir.glob("*.json"):
                        if cache_file.stem.startswith(hashlib.sha256(f"{api_name}:".encode()).hexdigest()[:8]):
                            cache_file.unlink()
                else:
                    for cache_file in self.cache_dir.glob("*.json"):
                        cache_file.unlink()
            except Exception as e:
                self.logger.warning(f"디스크 캐시 삭제 실패: {e}")


# 전역 캐시 매니저 인스턴스
_global_cache_manager: Optional[APICacheManager] = None


def get_cache_manager(config: Optional[Config] = None) -> APICacheManager:
    """전역 캐시 매니저 반환"""
    global _global_cache_manager
    
    if _global_cache_manager is None:
        _global_cache_manager = APICacheManager(config)
    
    return _global_cache_manager


# 데코레이터
def cached_api_call(api_name: str, method: str, ttl: Optional[int] = None):
    """API 호출 캐싱 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            return await cache_manager.cached_api_call(
                api_name, method, func, kwargs, ttl=ttl
            )
        return wrapper
    return decorator