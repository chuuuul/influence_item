"""
쿠팡 API 검색 결과 캐싱 관리 모듈

API 호출 최적화를 위한 캐싱 시스템을 제공합니다.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

from config.config import Config

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """캐시 엔트리 데이터 클래스"""
    key: str
    data: Any
    timestamp: float
    ttl: int
    access_count: int = 0
    last_access: float = 0.0
    
    def is_expired(self) -> bool:
        """캐시 만료 여부 확인"""
        return time.time() - self.timestamp > self.ttl
        
    def update_access(self) -> None:
        """접근 정보 업데이트"""
        self.access_count += 1
        self.last_access = time.time()


class CacheManager:
    """캐시 관리 클래스"""
    
    def __init__(self, cache_dir: Optional[Path] = None, default_ttl: int = None):
        """
        Args:
            cache_dir: 캐시 디렉토리 경로
            default_ttl: 기본 TTL (초)
        """
        self.cache_dir = cache_dir or Config.TEMP_DIR / "coupang_cache"
        self.default_ttl = default_ttl or Config.COUPANG_CACHE_TTL
        self.memory_cache: Dict[str, CacheEntry] = {}
        
        # 캐시 디렉토리 생성
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 캐시 파일 경로
        self.cache_file = self.cache_dir / "search_cache.json"
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        
        # 캐시 로드
        self._load_cache_from_disk()
        
        logger.info(f"캐시 관리자 초기화 완료 - 디렉토리: {self.cache_dir}")
        
    def get_search_cache(self, keyword: str, limit: int = 50) -> Optional[Dict[str, Any]]:
        """
        검색 결과 캐시 조회
        
        Args:
            keyword: 검색 키워드
            limit: 검색 결과 수
            
        Returns:
            캐시된 검색 결과 또는 None
        """
        cache_key = self._generate_search_key(keyword, limit)
        
        # 메모리 캐시 확인
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            
            if not entry.is_expired():
                entry.update_access()
                logger.debug(f"메모리 캐시 히트: {keyword}")
                return entry.data
            else:
                # 만료된 캐시 제거
                del self.memory_cache[cache_key]
                logger.debug(f"만료된 캐시 제거: {keyword}")
                
        return None
        
    def set_search_cache(self, keyword: str, limit: int, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        검색 결과 캐시 저장
        
        Args:
            keyword: 검색 키워드
            limit: 검색 결과 수
            data: 캐시할 데이터
            ttl: 캐시 유효 시간 (초)
        """
        cache_key = self._generate_search_key(keyword, limit)
        ttl = ttl or self.default_ttl
        
        entry = CacheEntry(
            key=cache_key,
            data=data,
            timestamp=time.time(),
            ttl=ttl
        )
        
        # 메모리 캐시에 저장
        self.memory_cache[cache_key] = entry
        
        # 디스크에 비동기 저장
        self._save_cache_to_disk()
        
        logger.debug(f"캐시 저장 완료: {keyword} (TTL: {ttl}초)")
        
    def get_product_cache(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        제품 상세 정보 캐시 조회
        
        Args:
            product_id: 제품 ID
            
        Returns:
            캐시된 제품 정보 또는 None
        """
        cache_key = f"product_{product_id}"
        
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            
            if not entry.is_expired():
                entry.update_access()
                logger.debug(f"제품 캐시 히트: {product_id}")
                return entry.data
            else:
                del self.memory_cache[cache_key]
                
        return None
        
    def set_product_cache(self, product_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        제품 상세 정보 캐시 저장
        
        Args:
            product_id: 제품 ID
            data: 캐시할 데이터
            ttl: 캐시 유효 시간 (초)
        """
        cache_key = f"product_{product_id}"
        ttl = ttl or self.default_ttl * 2  # 제품 정보는 더 오래 캐시
        
        entry = CacheEntry(
            key=cache_key,
            data=data,
            timestamp=time.time(),
            ttl=ttl
        )
        
        self.memory_cache[cache_key] = entry
        self._save_cache_to_disk()
        
        logger.debug(f"제품 캐시 저장 완료: {product_id}")
        
    def invalidate_cache(self, pattern: Optional[str] = None) -> int:
        """
        캐시 무효화
        
        Args:
            pattern: 무효화할 키 패턴 (None이면 전체)
            
        Returns:
            무효화된 캐시 수
        """
        if pattern is None:
            # 전체 캐시 초기화
            count = len(self.memory_cache)
            self.memory_cache.clear()
            logger.info(f"전체 캐시 초기화: {count}개 항목")
            return count
        else:
            # 패턴 매칭 무효화
            keys_to_remove = [key for key in self.memory_cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self.memory_cache[key]
            logger.info(f"패턴 캐시 무효화: {len(keys_to_remove)}개 항목 (패턴: {pattern})")
            return len(keys_to_remove)
            
    def cleanup_expired_cache(self) -> int:
        """
        만료된 캐시 정리
        
        Returns:
            정리된 캐시 수
        """
        expired_keys = []
        
        for key, entry in self.memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)
                
        for key in expired_keys:
            del self.memory_cache[key]
            
        if expired_keys:
            self._save_cache_to_disk()
            
        logger.info(f"만료된 캐시 정리 완료: {len(expired_keys)}개 항목")
        return len(expired_keys)
        
    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        캐시 통계 정보 반환
        
        Returns:
            캐시 통계 딕셔너리
        """
        total_entries = len(self.memory_cache)
        expired_entries = sum(1 for entry in self.memory_cache.values() if entry.is_expired())
        search_entries = sum(1 for key in self.memory_cache.keys() if key.startswith("search_"))
        product_entries = sum(1 for key in self.memory_cache.keys() if key.startswith("product_"))
        
        # 접근 빈도 통계
        access_counts = [entry.access_count for entry in self.memory_cache.values()]
        avg_access = sum(access_counts) / len(access_counts) if access_counts else 0
        
        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
            "search_entries": search_entries,
            "product_entries": product_entries,
            "average_access_count": round(avg_access, 2),
            "cache_hit_potential": round((total_entries - expired_entries) / max(total_entries, 1) * 100, 2)
        }
        
    def _generate_search_key(self, keyword: str, limit: int) -> str:
        """검색 캐시 키 생성"""
        key_string = f"search_{keyword}_{limit}"
        return hashlib.md5(key_string.encode()).hexdigest()
        
    def _load_cache_from_disk(self) -> None:
        """디스크에서 캐시 로드"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                for key, entry_dict in cache_data.items():
                    entry = CacheEntry(**entry_dict)
                    if not entry.is_expired():
                        self.memory_cache[key] = entry
                        
                logger.info(f"디스크 캐시 로드 완료: {len(self.memory_cache)}개 항목")
                
        except Exception as e:
            logger.warning(f"캐시 로드 실패: {str(e)}")
            self.memory_cache = {}
            
    def _save_cache_to_disk(self) -> None:
        """디스크에 캐시 저장"""
        try:
            # 만료되지 않은 캐시만 저장
            cache_to_save = {}
            for key, entry in self.memory_cache.items():
                if not entry.is_expired():
                    cache_to_save[key] = asdict(entry)
                    
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
                
            # 메타데이터 저장
            metadata = {
                "last_saved": time.time(),
                "total_entries": len(cache_to_save),
                "cache_dir": str(self.cache_dir)
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"캐시 저장 실패: {str(e)}")
            
    def cache_maintenance(self) -> Dict[str, int]:
        """
        캐시 유지보수 실행
        
        Returns:
            유지보수 결과 통계
        """
        logger.info("캐시 유지보수 시작")
        
        initial_count = len(self.memory_cache)
        
        # 만료된 캐시 정리
        expired_cleaned = self.cleanup_expired_cache()
        
        # 디스크 저장
        self._save_cache_to_disk()
        
        final_count = len(self.memory_cache)
        
        result = {
            "initial_entries": initial_count,
            "expired_cleaned": expired_cleaned,
            "final_entries": final_count,
            "space_saved": expired_cleaned
        }
        
        logger.info(f"캐시 유지보수 완료: {result}")
        return result