"""
YouTube Data API v3 클라이언트

채널 정보, 영상 메타데이터 추출 및 API 할당량 관리를 포함한 완전한 YouTube API 클라이언트
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from collections import OrderedDict
import asyncio

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.exceptions import GoogleAuthError
except ImportError:
    raise ImportError("Google API Client가 설치되지 않았습니다. 'pip install google-api-python-client google-auth' 실행")

from .quota_manager import QuotaManager
from ..security.key_manager import get_key_manager


class LRUCache:
    """
    LRU (Least Recently Used) 캐시 구현
    메모리 제한이 있는 안전한 캐시 시스템
    """
    
    def __init__(self, max_size: int = 500):
        """
        LRU 캐시 초기화
        
        Args:
            max_size: 최대 캐시 크기
        """
        self.max_size = max_size
        self.cache = OrderedDict()
        self.timestamps = {}
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 값 조회
        
        Args:
            key: 조회할 키
            
        Returns:
            캐시된 값 또는 None
        """
        if key in self.cache:
            # 최근 사용으로 이동
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        
        self.misses += 1
        return None
    
    def put(self, key: str, value: Any):
        """
        캐시에 값 저장
        
        Args:
            key: 저장할 키
            value: 저장할 값
        """
        if key in self.cache:
            # 기존 값 업데이트
            self.cache.move_to_end(key)
        else:
            # 새 값 추가
            if len(self.cache) >= self.max_size:
                # 가장 오래된 항목 제거
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                if oldest_key in self.timestamps:
                    del self.timestamps[oldest_key]
        
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def is_valid(self, key: str, ttl: timedelta) -> bool:
        """
        캐시 항목이 유효한지 확인
        
        Args:
            key: 확인할 키
            ttl: Time To Live
            
        Returns:
            유효성 여부
        """
        if key not in self.cache:
            return False
        
        if key not in self.timestamps:
            return False
        
        cache_time = self.timestamps[key]
        if datetime.now() - cache_time > ttl:
            # 만료된 항목 제거
            del self.cache[key]
            del self.timestamps[key]
            return False
        
        return True
    
    def clear(self):
        """캐시 클리어"""
        self.cache.clear()
        self.timestamps.clear()
        self.hits = 0
        self.misses = 0
    
    def size(self) -> int:
        """현재 캐시 크기 반환"""
        return len(self.cache)
    
    def hit_rate(self) -> float:
        """캐시 히트율 반환"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


@dataclass
class ChannelInfo:
    """채널 정보 데이터 클래스"""
    channel_id: str
    channel_name: str
    subscriber_count: int
    video_count: int
    view_count: int
    description: str
    published_at: str
    thumbnail_url: str
    country: Optional[str] = None
    keywords: Optional[List[str]] = None
    verified: bool = False


@dataclass
class VideoInfo:
    """영상 정보 데이터 클래스"""
    video_id: str
    title: str
    description: str
    published_at: str
    duration: str
    view_count: int
    like_count: int
    comment_count: int
    thumbnail_url: str
    channel_id: str
    channel_title: str
    category_id: str
    tags: Optional[List[str]] = None
    language: Optional[str] = None


class YouTubeAPIError(Exception):
    """YouTube API 관련 에러"""
    pass


class YouTubeAPIClient:
    """
    YouTube Data API v3 클라이언트
    
    기능:
    - 채널 정보 추출 (구독자 수, 설명 등)
    - 영상 메타데이터 추출 (제목, 설명, 업로드 일자, 조회수, 좋아요)
    - API 할당량 관리 (일일 10,000 요청 제한)
    - 에러 처리 및 재시도 로직
    - 캐싱 메커니즘으로 중복 요청 방지
    - Mock 모드 지원 (API 키 없이도 동작)
    """
    
    def __init__(self, api_key: Optional[str] = None, quota_manager: Optional[QuotaManager] = None,
                 encrypted_key_name: str = "youtube_api_key", mock_mode: bool = False):
        """
        YouTube API 클라이언트 초기화
        
        Args:
            api_key: Google Cloud Console에서 발급받은 YouTube Data API v3 키 (선택사항)
            quota_manager: 할당량 관리자 (없으면 자동 생성)
            encrypted_key_name: 암호화된 키 저장소에서 사용할 키 이름
        """
        self.key_manager = get_key_manager()
        self.encrypted_key_name = encrypted_key_name
        self.mock_mode = mock_mode
        
        # Mock 모드에서는 API 키 없이 동작
        if mock_mode:
            self.api_key = "MOCK_API_KEY"
            self.youtube = None
            self.logger = self._setup_logger()
            self.logger.info("Mock 모드로 YouTube API 클라이언트 초기화")
        else:
            self.logger = self._setup_logger()
            # API 키 초기화 (암호화된 저장소 우선)
            self.api_key = self._get_secure_api_key(api_key)
            if not self.api_key:
                raise ValueError("YouTube API 키가 필요합니다. 암호화된 저장소에 저장하거나 직접 제공하세요.")
        
            self.quota_manager = quota_manager or QuotaManager()
            
            # YouTube API 서비스 초기화 (암호화된 키 사용)
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
                self.logger.info("YouTube API 클라이언트 초기화 완료 (암호화된 키 사용)")
            except GoogleAuthError as e:
                raise YouTubeAPIError(f"YouTube API 인증 실패: {str(e)}")
            except Exception as e:
                raise YouTubeAPIError(f"YouTube API 클라이언트 초기화 실패: {str(e)}")
        
        # 공통 초기화
        if not hasattr(self, 'quota_manager'):
            self.quota_manager = quota_manager or QuotaManager()
        
        # LRU 캐시 설정
        self.max_cache_size = 1000  # 최대 캐시 항목 수
        self._channel_cache = LRUCache(max_size=self.max_cache_size // 2)  # 절반은 채널용
        self._video_cache = LRUCache(max_size=self.max_cache_size // 2)   # 절반은 비디오용
        self._cache_ttl = timedelta(hours=1)  # 1시간 캐시 유지
        
        # 재시도 설정
        self.max_retries = 3
        self.retry_delay = 1  # 초
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _sanitize_for_logging(self, text: str, max_length: int = 100) -> str:
        """
        강화된 로깅 보안 - 민감한 정보 완전 필터링 및 텍스트 정리
        
        Args:
            text: 원본 텍스트
            max_length: 최대 길이
            
        Returns:
            안전한 로깅용 텍스트
        """
        if not text:
            return ""
        
        # 민감한 패턴들 강화된 마스킹
        import re
        
        # 1. API 키 패턴 마스킹 (다양한 형태)
        text = re.sub(r'AIza[0-9A-Za-z_-]{35}', 'AIza***MASKED***', text)
        text = re.sub(r'GOOG[0-9A-Za-z_-]{20,}', 'GOOG***MASKED***', text)
        text = re.sub(r'ya29\.[0-9A-Za-z_-]{50,}', 'ya29.***MASKED***', text)  # OAuth 토큰
        
        # 2. 이메일 주소 완전 마스킹
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***', text)
        
        # 3. URL 파라미터의 모든 키 값들 마스킹
        text = re.sub(r'key=[^&\s]+', 'key=***MASKED***', text)
        text = re.sub(r'token=[^&\s]+', 'token=***MASKED***', text)
        text = re.sub(r'apikey=[^&\s]+', 'apikey=***MASKED***', text)
        text = re.sub(r'api_key=[^&\s]+', 'api_key=***MASKED***', text)
        text = re.sub(r'access_token=[^&\s]+', 'access_token=***MASKED***', text)
        text = re.sub(r'refresh_token=[^&\s]+', 'refresh_token=***MASKED***', text)
        
        # 4. 신용카드 번호 마스킹
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '****-****-****-****', text)
        
        # 5. 전화번호 마스킹
        text = re.sub(r'\b\d{3}[-\.\s]?\d{3,4}[-\.\s]?\d{4}\b', '***-***-****', text)
        
        # 6. IP 주소 마스킹
        text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***.***.***.***', text)
        
        # 7. JSON 내 키 값 마스킹
        text = re.sub(r'"(api_?key|token|secret|password|passwd)"\s*:\s*"[^"]*"', r'"\1": "***MASKED***"', text, flags=re.IGNORECASE)
        
        # 8. XML/HTML 속성 내 키 값 마스킹
        text = re.sub(r'(api_?key|token|secret|password)=["\'][^"\']*["\']', r'\1="***MASKED***"', text, flags=re.IGNORECASE)
        
        # 9. Base64 인코딩된 데이터 의심 패턴 마스킹
        text = re.sub(r'\b[A-Za-z0-9+/]{50,}={0,2}\b', '***BASE64_MASKED***', text)
        
        # 10. 해시값 의심 패턴 마스킹
        text = re.sub(r'\b[a-fA-F0-9]{32}\b', '***HASH32_MASKED***', text)  # MD5
        text = re.sub(r'\b[a-fA-F0-9]{40}\b', '***HASH40_MASKED***', text)  # SHA1
        text = re.sub(r'\b[a-fA-F0-9]{64}\b', '***HASH64_MASKED***', text)  # SHA256
        
        # 11. 개인 식별 정보 마스킹
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****', text)  # SSN
        text = re.sub(r'\b\d{6}-\d{7}\b', '******-*******', text)  # 주민등록번호
        
        # 12. 길이 제한 및 특수문자 정리
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        # 13. 로깅 안전성 검증
        if self._contains_suspicious_patterns(text):
            text = "***POTENTIALLY_SENSITIVE_DATA_BLOCKED***"
        
        return text
    
    def _contains_suspicious_patterns(self, text: str) -> bool:
        """
        의심스러운 패턴 감지
        
        Args:
            text: 검사할 텍스트
            
        Returns:
            의심스러운 패턴 포함 여부
        """
        import re
        
        suspicious_patterns = [
            r'BEGIN [A-Z]+ PRIVATE KEY',  # 개인키
            r'-----BEGIN [A-Z]+ KEY-----',  # 암호화 키
            r'sk_[a-z]+_[a-zA-Z0-9]+',  # Stripe 등의 비밀키
            r'xox[baprs]-[a-zA-Z0-9-]+',  # Slack 토큰
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub 토큰
            r'glpat-[a-zA-Z0-9_-]{20}',  # GitLab 토큰
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',  # UUID
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _log_api_request(self, endpoint: str, params: Dict[str, Any] = None):
        """
        API 요청을 안전하게 로깅
        
        Args:
            endpoint: API 엔드포인트
            params: 요청 파라미터
        """
        safe_endpoint = self._sanitize_for_logging(endpoint)
        
        if params:
            # 민감한 파라미터 필터링
            safe_params = {}
            for key, value in params.items():
                if key.lower() in ['key', 'api_key', 'token', 'secret']:
                    safe_params[key] = "***MASKED***"
                else:
                    safe_params[key] = self._sanitize_for_logging(str(value), 50)
            self.logger.debug(f"API 요청: {safe_endpoint}, 파라미터: {safe_params}")
        else:
            self.logger.debug(f"API 요청: {safe_endpoint}")
    
    def _log_error_safely(self, error_message: str, context: str = ""):
        """
        에러를 안전하게 로깅 (민감한 정보 제거)
        
        Args:
            error_message: 에러 메시지
            context: 추가 컨텍스트
        """
        safe_error = self._sanitize_for_logging(error_message, 200)
        safe_context = self._sanitize_for_logging(context, 100) if context else ""
        
        if safe_context:
            self.logger.error(f"[{safe_context}] {safe_error}")
        else:
            self.logger.error(safe_error)
    
    def _get_secure_api_key(self, provided_key: Optional[str] = None) -> str:
        """
        보안 API 키 조회 (Mock 모드 고려)
        
        Args:
            provided_key: 직접 제공된 키 (선택사항)
            
        Returns:
            API 키 문자열
        """
        # Mock 모드에서는 키 검증 생략
        if self.mock_mode:
            return "MOCK_API_KEY"
        
        # 1. 직접 제공된 키가 있으면 사용 (그리고 암호화 저장)
        if provided_key:
            self.logger.info("직접 제공된 API 키 사용 및 암호화 저장")
            # 기존에 저장된 키와 다르면 업데이트
            stored_key = self.key_manager.decrypt_key(self.encrypted_key_name)
            if stored_key != provided_key:
                success = self.key_manager.encrypt_key(self.encrypted_key_name, provided_key)
                if success:
                    self.logger.info(f"API 키가 암호화되어 저장되었습니다: {self.encrypted_key_name}")
                else:
                    self.logger.warning("API 키 암호화 저장 실패")
            return provided_key
        
        # 2. 암호화된 저장소에서 키 조회
        stored_key = self.key_manager.get_api_key_safe(
            self.encrypted_key_name, 
            fallback_env_var="YOUTUBE_API_KEY"
        )
        
        if stored_key:
            self.logger.debug("암호화된 저장소에서 API 키 로드")
            return stored_key
        
        return ""
    
    def store_api_key(self, new_api_key: str) -> bool:
        """
        새로운 API 키를 암호화하여 저장
        
        Args:
            new_api_key: 새로운 API 키
            
        Returns:
            저장 성공 여부
        """
        success = self.key_manager.encrypt_key(self.encrypted_key_name, new_api_key)
        if success:
            self.api_key = new_api_key
            # YouTube API 서비스 재초기화
            try:
                self.youtube = build('youtube', 'v3', developerKey=new_api_key)
                self.logger.info("API 키 업데이트 및 서비스 재초기화 완료")
            except Exception as e:
                self.logger.error(f"서비스 재초기화 실패: {str(e)}")
                return False
        return success
    
    def rotate_api_key(self, new_api_key: str) -> bool:
        """
        API 키 로테이션 (기존 키 백업)
        
        Args:
            new_api_key: 새로운 API 키
            
        Returns:
            로테이션 성공 여부
        """
        success = self.key_manager.rotate_key(self.encrypted_key_name, new_api_key)
        if success:
            self.api_key = new_api_key
            # YouTube API 서비스 재초기화
            try:
                self.youtube = build('youtube', 'v3', developerKey=new_api_key)
                self.logger.info("API 키 로테이션 및 서비스 재초기화 완료")
            except Exception as e:
                self.logger.error(f"서비스 재초기화 실패: {str(e)}")
                return False
        return success
    
    def _is_cache_valid(self, cache_key: str, cache_type: str = "video") -> bool:
        """캐시가 유효한지 확인"""
        cache = self._video_cache if cache_type == "video" else self._channel_cache
        return cache.is_valid(cache_key, self._cache_ttl)
    
    def _update_cache(self, cache_key: str, data: Any, cache_type: str = "video"):
        """캐시 업데이트"""
        cache = self._video_cache if cache_type == "video" else self._channel_cache
        cache.put(cache_key, data)
    
    def extract_video_id(self, youtube_url: str) -> Optional[str]:
        """
        YouTube URL에서 비디오 ID 추출
        
        Args:
            youtube_url: YouTube URL
            
        Returns:
            비디오 ID 또는 None
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        return None
    
    def extract_channel_id_from_url(self, youtube_url: str) -> Optional[str]:
        """
        YouTube URL에서 채널 ID 또는 사용자명 추출
        
        Args:
            youtube_url: YouTube URL
            
        Returns:
            채널 ID 또는 사용자명
        """
        patterns = [
            r'youtube\.com\/channel\/([a-zA-Z0-9_-]+)',
            r'youtube\.com\/c\/([a-zA-Z0-9_-]+)',
            r'youtube\.com\/user\/([a-zA-Z0-9_-]+)',
            r'youtube\.com\/@([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        return None
    
    async def _retry_request(self, func, *args, **kwargs):
        """
        재시도 로직을 포함한 API 요청 (Mock 모드 지원)
        
        Args:
            func: 실행할 함수
            *args, **kwargs: 함수 인자
            
        Returns:
            API 응답
            
        Raises:
            YouTubeAPIError: 모든 재시도 실패 시
        """
        # Mock 모드에서는 Mock 데이터 반환
        if self.mock_mode:
            return await self._get_mock_response(func.__name__, *args, **kwargs)
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 할당량 확인
                if not self.quota_manager.can_make_request():
                    raise YouTubeAPIError("일일 API 할당량 초과")
                
                # API 요청 실행
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 할당량 사용량 업데이트
                self.quota_manager.record_request()
                
                return result
                
            except HttpError as e:
                last_error = e
                error_code = e.resp.status
                
                # 할당량 초과 에러
                if error_code == 403 and 'quotaExceeded' in str(e):
                    self.quota_manager.mark_quota_exceeded()
                    raise YouTubeAPIError("API 할당량 초과")
                
                # 재시도 가능한 에러
                if error_code in [500, 502, 503, 504] and attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"API 요청 실패 (재시도 {attempt + 1}/{self.max_retries}): {str(e)}")
                    await asyncio.sleep(wait_time)
                    continue
                
                # 재시도 불가능한 에러
                self._log_error_safely(str(e), "YouTube API 에러")
                raise YouTubeAPIError(f"YouTube API 에러 발생")
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"요청 실패 (재시도 {attempt + 1}/{self.max_retries}): {str(e)}")
                    await asyncio.sleep(wait_time)
                    continue
                
                self._log_error_safely(str(e), "API 요청 실패")
                raise YouTubeAPIError(f"API 요청 실패")
        
        if last_error:
            self._log_error_safely(str(last_error), "모든 재시도 실패")
        raise YouTubeAPIError(f"모든 재시도 실패")
    
    async def _get_mock_response(self, func_name: str, *args, **kwargs):
        """
        Mock 모드용 응답 생성
        
        Args:
            func_name: 호출된 함수명
            *args, **kwargs: 함수 인자
            
        Returns:
            Mock 응답 데이터
        """
        import random
        import time
        
        # 함수명에 따른 Mock 데이터 생성
        if "videos" in func_name.lower():
            return {
                'items': [{
                    'id': 'mock_video_id',
                    'snippet': {
                        'title': 'Mock 영상 제목 - 뷰티 리뷰',
                        'description': 'Mock 영상 설명입니다. 이것은 테스트용 데이터입니다.',
                        'publishedAt': '2025-06-01T10:00:00Z',
                        'channelId': 'mock_channel_id',
                        'channelTitle': 'Mock 뷰티 채널',
                        'categoryId': '26',  # Howto & Style
                        'tags': ['뷰티', '메이크업', '리뷰'],
                        'defaultLanguage': 'ko',
                        'thumbnails': {
                            'high': {
                                'url': 'https://example.com/mock_thumbnail.jpg'
                            }
                        }
                    },
                    'statistics': {
                        'viewCount': str(random.randint(10000, 1000000)),
                        'likeCount': str(random.randint(100, 10000)),
                        'commentCount': str(random.randint(10, 1000))
                    },
                    'contentDetails': {
                        'duration': 'PT10M30S'
                    }
                }]
            }
        
        elif "channels" in func_name.lower():
            return {
                'items': [{
                    'id': 'mock_channel_id',
                    'snippet': {
                        'title': 'Mock 뷰티 채널',
                        'description': 'Mock 채널 설명입니다. 뷰티와 패션 콘텐츠를 다룹니다.',
                        'publishedAt': '2020-01-01T00:00:00Z',
                        'country': 'KR',
                        'customUrl': '@mockbeauty',
                        'thumbnails': {
                            'high': {
                                'url': 'https://example.com/mock_channel_thumb.jpg'
                            }
                        }
                    },
                    'statistics': {
                        'subscriberCount': str(random.randint(10000, 500000)),
                        'videoCount': str(random.randint(50, 500)),
                        'viewCount': str(random.randint(1000000, 10000000))
                    },
                    'brandingSettings': {
                        'channel': {
                            'keywords': '뷰티,메이크업,패션,스킨케어'
                        }
                    }
                }]
            }
        
        elif "search" in func_name.lower():
            # 채널 타입 검색
            if kwargs.get('type') == 'channel':
                return {
                    'items': [{
                        'id': {
                            'kind': 'youtube#channel',
                            'channelId': 'mock_search_channel_id'
                        },
                        'snippet': {
                            'channelId': 'mock_search_channel_id',
                            'title': 'Mock 검색 채널',
                            'description': 'Mock 검색 결과 채널',
                            'publishedAt': '2021-01-01T00:00:00Z',
                            'thumbnails': {
                                'high': {
                                    'url': 'https://example.com/mock_search_thumb.jpg'
                                }
                            }
                        }
                    }]
                }
            else:
                # 비디오 검색
                return {
                    'items': [{
                        'id': {
                            'kind': 'youtube#video',
                            'videoId': 'mock_search_video_id'
                        },
                        'snippet': {
                            'title': 'Mock 검색 영상',
                            'description': 'Mock 검색 결과 영상',
                            'publishedAt': '2025-06-01T10:00:00Z',
                            'channelId': 'mock_channel_id',
                            'channelTitle': 'Mock 채널',
                            'thumbnails': {
                                'high': {
                                    'url': 'https://example.com/mock_video_thumb.jpg'
                                }
                            }
                        }
                    }]
                }
        
        # 기본 응답
        return {'items': []}
    
    async def get_video_info(self, video_url_or_id: str, use_cache: bool = True) -> VideoInfo:
        """
        YouTube 영상 정보 추출
        
        Args:
            video_url_or_id: YouTube URL 또는 비디오 ID
            use_cache: 캐시 사용 여부
            
        Returns:
            VideoInfo 객체
            
        Raises:
            YouTubeAPIError: API 요청 실패 시
        """
        # 비디오 ID 추출
        if video_url_or_id.startswith('http'):
            video_id = self.extract_video_id(video_url_or_id)
            if not video_id:
                raise YouTubeAPIError(f"유효하지 않은 YouTube URL: {video_url_or_id}")
        else:
            video_id = video_url_or_id
        
        # 캐시 확인
        if use_cache and self._is_cache_valid(video_id, "video"):
            cached_video = self._video_cache.get(video_id)
            if cached_video:
                self.logger.debug(f"비디오 정보 캐시 사용: {video_id}")
                return cached_video
        
        self._log_api_request("videos.list", {"id": video_id})
        self.logger.info(f"YouTube 영상 정보 요청: {self._sanitize_for_logging(video_id)}")
        
        # API 요청
        def _get_video_details():
            return self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            ).execute()
        
        response = await self._retry_request(_get_video_details)
        
        if not response.get('items'):
            raise YouTubeAPIError(f"비디오를 찾을 수 없습니다: {video_id}")
        
        item = response['items'][0]
        snippet = item['snippet']
        statistics = item['statistics']
        content_details = item['contentDetails']
        
        # VideoInfo 객체 생성
        video_info = VideoInfo(
            video_id=video_id,
            title=snippet.get('title', ''),
            description=snippet.get('description', ''),
            published_at=snippet.get('publishedAt', ''),
            duration=content_details.get('duration', ''),
            view_count=int(statistics.get('viewCount', 0)),
            like_count=int(statistics.get('likeCount', 0)),
            comment_count=int(statistics.get('commentCount', 0)),
            thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            channel_id=snippet.get('channelId', ''),
            channel_title=snippet.get('channelTitle', ''),
            category_id=snippet.get('categoryId', ''),
            tags=snippet.get('tags', []),
            language=snippet.get('defaultLanguage')
        )
        
        # 캐시 업데이트
        if use_cache:
            self._update_cache(video_id, video_info, "video")
        
        # 민감한 정보 필터링하여 로깅
        safe_title = video_info.title[:50] + "..." if len(video_info.title) > 50 else video_info.title
        self.logger.info(f"영상 정보 추출 완료: {safe_title}")
        return video_info
    
    async def get_channel_info(self, channel_id_or_url: str, use_cache: bool = True) -> ChannelInfo:
        """
        YouTube 채널 정보 추출
        
        Args:
            channel_id_or_url: 채널 ID 또는 YouTube URL
            use_cache: 캐시 사용 여부
            
        Returns:
            ChannelInfo 객체
            
        Raises:
            YouTubeAPIError: API 요청 실패 시
        """
        # 채널 ID 추출
        if channel_id_or_url.startswith('http'):
            channel_identifier = self.extract_channel_id_from_url(channel_id_or_url)
            if not channel_identifier:
                raise YouTubeAPIError(f"유효하지 않은 YouTube URL: {channel_id_or_url}")
        else:
            channel_identifier = channel_id_or_url
        
        # 캐시 확인
        if use_cache and self._is_cache_valid(channel_identifier, "channel"):
            cached_channel = self._channel_cache.get(channel_identifier)
            if cached_channel:
                self.logger.debug(f"채널 정보 캐시 사용: {channel_identifier}")
                return cached_channel
        
        self._log_api_request("channels.list", {"id": channel_identifier})
        self.logger.info(f"YouTube 채널 정보 요청: {self._sanitize_for_logging(channel_identifier)}")
        
        # API 요청 (채널 ID로 검색)
        def _get_channel_by_id():
            return self.youtube.channels().list(
                part='snippet,statistics,brandingSettings',
                id=channel_identifier
            ).execute()
        
        # API 요청 (사용자명으로 검색 - forUsername은 deprecated)
        def _get_channel_by_custom_url():
            return self.youtube.search().list(
                part='snippet',
                q=channel_identifier,
                type='channel',
                maxResults=1
            ).execute()
        
        response = await self._retry_request(_get_channel_by_id)
        
        # 채널 ID로 찾을 수 없으면 검색으로 시도
        if not response.get('items'):
            self.logger.debug(f"채널 ID로 찾지 못함, 검색 시도: {self._sanitize_for_logging(channel_identifier)}")
            self._log_api_request("search.list", {"q": channel_identifier, "type": "channel"})
            search_response = await self._retry_request(_get_channel_by_custom_url)
            
            if not search_response.get('items'):
                raise YouTubeAPIError(f"채널을 찾을 수 없습니다: {channel_identifier}")
            
            # 검색 결과에서 채널 ID 추출
            found_channel_id = search_response['items'][0]['snippet']['channelId']
            
            # 실제 채널 정보 요청
            def _get_found_channel():
                return self.youtube.channels().list(
                    part='snippet,statistics,brandingSettings',
                    id=found_channel_id
                ).execute()
            
            response = await self._retry_request(_get_found_channel)
        
        if not response.get('items'):
            raise YouTubeAPIError(f"채널 정보를 가져올 수 없습니다: {channel_identifier}")
        
        item = response['items'][0]
        snippet = item['snippet']
        statistics = item['statistics']
        branding = item.get('brandingSettings', {}).get('channel', {})
        
        # 키워드 파싱
        keywords = None
        if branding.get('keywords'):
            keywords = [kw.strip().strip('"') for kw in branding['keywords'].split(',')]
        
        # ChannelInfo 객체 생성
        channel_info = ChannelInfo(
            channel_id=item['id'],
            channel_name=snippet.get('title', ''),
            subscriber_count=int(statistics.get('subscriberCount', 0)),
            video_count=int(statistics.get('videoCount', 0)),
            view_count=int(statistics.get('viewCount', 0)),
            description=snippet.get('description', ''),
            published_at=snippet.get('publishedAt', ''),
            thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            country=snippet.get('country'),
            keywords=keywords,
            verified=snippet.get('customUrl', '').startswith('c/') or snippet.get('customUrl', '').startswith('@')
        )
        
        # 캐시 업데이트
        if use_cache:
            self._update_cache(channel_identifier, channel_info, "channel")
        
        # 민감한 정보 필터링하여 로깅
        safe_name = channel_info.channel_name[:30] + "..." if len(channel_info.channel_name) > 30 else channel_info.channel_name
        self.logger.info(f"채널 정보 추출 완료: {safe_name} (구독자: {channel_info.subscriber_count:,}명)")
        return channel_info
    
    async def get_channel_info_from_video(self, video_url_or_id: str, use_cache: bool = True) -> ChannelInfo:
        """
        YouTube 영상 URL로부터 채널 정보 추출
        
        Args:
            video_url_or_id: YouTube URL 또는 비디오 ID  
            use_cache: 캐시 사용 여부
            
        Returns:
            ChannelInfo 객체
            
        Raises:
            YouTubeAPIError: API 요청 실패 시
        """
        # 먼저 비디오 정보를 가져와서 채널 ID 추출
        video_info = await self.get_video_info(video_url_or_id, use_cache)
        
        # 채널 정보 가져오기
        return await self.get_channel_info(video_info.channel_id, use_cache)
    
    def get_quota_status(self) -> Dict[str, Any]:
        """
        현재 API 할당량 상태 반환
        
        Returns:
            할당량 상태 정보
        """
        return self.quota_manager.get_status()
    
    def clear_cache(self):
        """모든 캐시 데이터 삭제"""
        self._channel_cache.clear()
        self._video_cache.clear()
        self.logger.info("캐시 데이터 삭제 완료")
    
    async def batch_get_video_info(self, video_ids: List[str], use_cache: bool = True) -> List[VideoInfo]:
        """
        여러 비디오 정보를 배치로 처리하여 할당량 효율성 개선
        
        Args:
            video_ids: 비디오 ID 리스트 (최대 50개)
            use_cache: 캐시 사용 여부
            
        Returns:
            VideoInfo 객체 리스트
            
        Raises:
            YouTubeAPIError: API 요청 실패 시
        """
        if not video_ids:
            return []
        
        # YouTube API는 한 번에 최대 50개까지 처리 가능
        batch_size = 50
        all_videos = []
        
        # 캐시에서 먼저 조회
        uncached_ids = []
        cached_videos = {}
        
        if use_cache:
            for video_id in video_ids:
                if self._is_cache_valid(video_id, "video"):
                    cached_video = self._video_cache.get(video_id)
                    if cached_video:
                        cached_videos[video_id] = cached_video
                    else:
                        uncached_ids.append(video_id)
                else:
                    uncached_ids.append(video_id)
        else:
            uncached_ids = video_ids.copy()
        
        self.logger.info(f"배치 비디오 정보 요청: 총 {len(video_ids)}개, 캐시 히트 {len(cached_videos)}개, API 요청 {len(uncached_ids)}개")
        
        # 배치 단위로 API 요청
        for i in range(0, len(uncached_ids), batch_size):
            batch_ids = uncached_ids[i:i + batch_size]
            
            self._log_api_request("videos.list", {"id": ",".join(batch_ids), "batch_size": len(batch_ids)})
            
            # API 요청
            def _get_batch_videos():
                return self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch_ids)
                ).execute()
            
            response = await self._retry_request(_get_batch_videos)
            
            if response.get('items'):
                for item in response['items']:
                    video_id = item['id']
                    snippet = item['snippet']
                    statistics = item['statistics']
                    content_details = item['contentDetails']
                    
                    # VideoInfo 객체 생성
                    video_info = VideoInfo(
                        video_id=video_id,
                        title=snippet.get('title', ''),
                        description=snippet.get('description', ''),
                        published_at=snippet.get('publishedAt', ''),
                        duration=content_details.get('duration', ''),
                        view_count=int(statistics.get('viewCount', 0)),
                        like_count=int(statistics.get('likeCount', 0)),
                        comment_count=int(statistics.get('commentCount', 0)),
                        thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        channel_id=snippet.get('channelId', ''),
                        channel_title=snippet.get('channelTitle', ''),
                        category_id=snippet.get('categoryId', ''),
                        tags=snippet.get('tags', []),
                        language=snippet.get('defaultLanguage')
                    )
                    
                    # 캐시 업데이트
                    if use_cache:
                        self._update_cache(video_id, video_info, "video")
                    
                    cached_videos[video_id] = video_info
        
        # 요청된 순서대로 결과 정렬
        for video_id in video_ids:
            if video_id in cached_videos:
                all_videos.append(cached_videos[video_id])
        
        batch_efficiency = ((len(cached_videos) / len(video_ids)) * 100) if video_ids else 0
        self.logger.info(f"배치 처리 완료: {len(all_videos)}개 비디오, 효율성 {batch_efficiency:.1f}%")
        
        return all_videos
    
    async def batch_get_channel_info(self, channel_ids: List[str], use_cache: bool = True) -> List[ChannelInfo]:
        """
        여러 채널 정보를 배치로 처리하여 할당량 효율성 개선
        
        Args:
            channel_ids: 채널 ID 리스트 (최대 50개)
            use_cache: 캐시 사용 여부
            
        Returns:
            ChannelInfo 객체 리스트
            
        Raises:
            YouTubeAPIError: API 요청 실패 시
        """
        if not channel_ids:
            return []
        
        # YouTube API는 한 번에 최대 50개까지 처리 가능
        batch_size = 50
        all_channels = []
        
        # 캐시에서 먼저 조회
        uncached_ids = []
        cached_channels = {}
        
        if use_cache:
            for channel_id in channel_ids:
                if self._is_cache_valid(channel_id, "channel"):
                    cached_channel = self._channel_cache.get(channel_id)
                    if cached_channel:
                        cached_channels[channel_id] = cached_channel
                    else:
                        uncached_ids.append(channel_id)
                else:
                    uncached_ids.append(channel_id)
        else:
            uncached_ids = channel_ids.copy()
        
        self.logger.info(f"배치 채널 정보 요청: 총 {len(channel_ids)}개, 캐시 히트 {len(cached_channels)}개, API 요청 {len(uncached_ids)}개")
        
        # 배치 단위로 API 요청
        for i in range(0, len(uncached_ids), batch_size):
            batch_ids = uncached_ids[i:i + batch_size]
            
            self._log_api_request("channels.list", {"id": ",".join(batch_ids), "batch_size": len(batch_ids)})
            
            # API 요청
            def _get_batch_channels():
                return self.youtube.channels().list(
                    part='snippet,statistics,brandingSettings',
                    id=','.join(batch_ids)
                ).execute()
            
            response = await self._retry_request(_get_batch_channels)
            
            if response.get('items'):
                for item in response['items']:
                    channel_id = item['id']
                    snippet = item['snippet']
                    statistics = item['statistics']
                    branding = item.get('brandingSettings', {}).get('channel', {})
                    
                    # 키워드 파싱
                    keywords = None
                    if branding.get('keywords'):
                        keywords = [kw.strip().strip('"') for kw in branding['keywords'].split(',')]
                    
                    # ChannelInfo 객체 생성
                    channel_info = ChannelInfo(
                        channel_id=channel_id,
                        channel_name=snippet.get('title', ''),
                        subscriber_count=int(statistics.get('subscriberCount', 0)),
                        video_count=int(statistics.get('videoCount', 0)),
                        view_count=int(statistics.get('viewCount', 0)),
                        description=snippet.get('description', ''),
                        published_at=snippet.get('publishedAt', ''),
                        thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        country=snippet.get('country'),
                        keywords=keywords,
                        verified=snippet.get('customUrl', '').startswith('c/') or snippet.get('customUrl', '').startswith('@')
                    )
                    
                    # 캐시 업데이트
                    if use_cache:
                        self._update_cache(channel_id, channel_info, "channel")
                    
                    cached_channels[channel_id] = channel_info
        
        # 요청된 순서대로 결과 정렬
        for channel_id in channel_ids:
            if channel_id in cached_channels:
                all_channels.append(cached_channels[channel_id])
        
        batch_efficiency = ((len(cached_channels) / len(channel_ids)) * 100) if channel_ids else 0
        self.logger.info(f"배치 처리 완료: {len(all_channels)}개 채널, 효율성 {batch_efficiency:.1f}%")
        
        return all_channels
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 반환
        
        Returns:
            캐시 통계 정보
        """
        return {
            'channel_cache_size': self._channel_cache.size(),
            'video_cache_size': self._video_cache.size(),
            'max_cache_size': self.max_cache_size,
            'cache_ttl_hours': self._cache_ttl.total_seconds() / 3600,
            'total_cached_items': self._channel_cache.size() + self._video_cache.size(),
            'channel_cache_hits': self._channel_cache.hits,
            'channel_cache_misses': self._channel_cache.misses,
            'video_cache_hits': self._video_cache.hits,
            'video_cache_misses': self._video_cache.misses,
            'memory_efficient': True
        }


# 편의 함수들
async def extract_youtube_video_info(video_url: str, api_key: Optional[str] = None) -> VideoInfo:
    """
    YouTube 영상 정보 추출을 위한 편의 함수
    
    Args:
        video_url: YouTube 영상 URL
        api_key: YouTube Data API v3 키 (선택사항, 암호화된 저장소에서 자동 로드)
        
    Returns:
        VideoInfo 객체
    """
    client = YouTubeAPIClient(api_key)
    return await client.get_video_info(video_url)


async def extract_youtube_channel_info(channel_url_or_id: str, api_key: Optional[str] = None) -> ChannelInfo:
    """
    YouTube 채널 정보 추출을 위한 편의 함수
    
    Args:
        channel_url_or_id: YouTube 채널 URL 또는 ID
        api_key: YouTube Data API v3 키 (선택사항, 암호화된 저장소에서 자동 로드)
        
    Returns:
        ChannelInfo 객체
    """
    client = YouTubeAPIClient(api_key)
    return await client.get_channel_info(channel_url_or_id)