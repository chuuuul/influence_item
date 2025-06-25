"""
데이터베이스 관리 유틸리티
T08_S01_M02: Workflow State Management - Database Operations

후보 데이터의 CRUD 작업 및 상태 관리를 위한 데이터베이스 연동
"""

import sqlite3
import json
import logging
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from functools import lru_cache
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 관리자 (성능 최적화)"""
    
    def __init__(self, db_path: str = "influence_item.db"):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._connection_pool = {}
        self._pool_lock = threading.Lock()
        self._cache_timeout = 300  # 5분 캐시
        self._init_database()
        
    def _init_database(self):
        """데이터베이스 테이블 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 후보 데이터 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS candidates (
                        id TEXT PRIMARY KEY,
                        source_info TEXT NOT NULL,
                        candidate_info TEXT NOT NULL,
                        monetization_info TEXT NOT NULL,
                        status_info TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 상태 변경 이력 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS status_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_id TEXT NOT NULL,
                        from_status TEXT NOT NULL,
                        to_status TEXT NOT NULL,
                        reason TEXT,
                        operator_id TEXT DEFAULT 'system',
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT,
                        FOREIGN KEY (candidate_id) REFERENCES candidates (id)
                    )
                """)
                
                # 감사 로그 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        category TEXT NOT NULL,
                        level TEXT NOT NULL,
                        candidate_id TEXT NOT NULL,
                        message TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # T03_S02_M02: 외부 검색 이력 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_id TEXT NOT NULL,
                        search_engine TEXT NOT NULL,
                        query TEXT NOT NULL,
                        search_type TEXT NOT NULL,
                        search_url TEXT NOT NULL,
                        session_key TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT,
                        FOREIGN KEY (candidate_id) REFERENCES candidates (id)
                    )
                """)
                
                # 검색 피드백 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_id TEXT NOT NULL,
                        search_id INTEGER,
                        feedback_type TEXT NOT NULL,
                        comments TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        session_key TEXT,
                        FOREIGN KEY (candidate_id) REFERENCES candidates (id),
                        FOREIGN KEY (search_id) REFERENCES search_history (id)
                    )
                """)
                
                # 인덱스 생성
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_candidates_status 
                    ON candidates(json_extract(status_info, '$.current_status'))
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status_history_candidate 
                    ON status_history(candidate_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status_history_timestamp 
                    ON status_history(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp 
                    ON audit_logs(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_logs_candidate_id 
                    ON audit_logs(candidate_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_history_candidate 
                    ON search_history(candidate_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_history_timestamp 
                    ON search_history(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_feedback_candidate 
                    ON search_feedback(candidate_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_logs_category 
                    ON audit_logs(category)
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _get_connection(self) -> sqlite3.Connection:
        """성능 최적화된 데이터베이스 연결 획득"""
        thread_id = threading.get_ident()
        
        with self._pool_lock:
            if thread_id not in self._connection_pool:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                # 고급 성능 최적화 설정
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=20000")  # 캐시 크기 증가
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA mmap_size=268435456")  # 256MB 메모리 맵
                conn.execute("PRAGMA page_size=4096")  # 페이지 크기 최적화
                conn.execute("PRAGMA wal_autocheckpoint=1000")  # WAL 체크포인트 최적화
                conn.execute("PRAGMA optimize")  # 쿼리 플래너 최적화
                
                # 연결 풀에 추가
                self._connection_pool[thread_id] = conn
                
            return self._connection_pool[thread_id]
    
    @lru_cache(maxsize=100)
    def _get_cached_status_counts(self, cache_key: str) -> Dict[str, int]:
        """상태별 개수 캐시"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT json_extract(status_info, '$.current_status') as status, COUNT(*) as count
                FROM candidates
                GROUP BY status
            """)
            
            status_counts = {}
            for row in cursor.fetchall():
                status, count = row
                status_counts[status or "unknown"] = count
                
            return status_counts
        except Exception as e:
            logger.error(f"Failed to get cached status counts: {e}")
            return {}
    
    @lru_cache(maxsize=50)
    def _get_cached_candidate_list(self, status: str, limit: int, offset: int, cache_key: str) -> List[Dict[str, Any]]:
        """후보 목록 캐시"""
        try:
            conn = self._get_connection()
            
            if status and status != "all":
                query = """
                    SELECT id, source_info, candidate_info, monetization_info, status_info, created_at, updated_at
                    FROM candidates 
                    WHERE json_extract(status_info, '$.current_status') = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (status, limit, offset)
            else:
                query = """
                    SELECT id, source_info, candidate_info, monetization_info, status_info, created_at, updated_at
                    FROM candidates 
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (limit, offset)
                
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            candidates = []
            for row in rows:
                cid, source_info, candidate_info, monetization_info, status_info, created_at, updated_at = row
                
                candidates.append({
                    "id": cid,
                    "source_info": json.loads(source_info),
                    "candidate_info": json.loads(candidate_info),
                    "monetization_info": json.loads(monetization_info),
                    "status_info": json.loads(status_info),
                    "created_at": created_at,
                    "updated_at": updated_at
                })
                
            return candidates
        except Exception as e:
            logger.error(f"Failed to get cached candidate list: {e}")
            return []
            
    def save_candidate(self, candidate_data: Dict[str, Any]) -> bool:
        """
        후보 데이터 저장/업데이트
        
        Args:
            candidate_data: 완전한 후보 데이터 (JSON 스키마 형식)
            
        Returns:
            성공 여부
        """
        try:
            candidate_id = self._extract_candidate_id(candidate_data)
            if not candidate_id:
                raise ValueError("Candidate ID not found in data")
                
            conn = self._get_connection()
            # 기존 데이터 확인
            cursor = conn.execute("SELECT id FROM candidates WHERE id = ?", (candidate_id,))
            exists = cursor.fetchone() is not None
            
            now = datetime.now().isoformat()
            
            if exists:
                # 업데이트
                conn.execute("""
                    UPDATE candidates 
                    SET source_info = ?, candidate_info = ?, monetization_info = ?, 
                        status_info = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    json.dumps(candidate_data.get("source_info", {}), ensure_ascii=False),
                    json.dumps(candidate_data.get("candidate_info", {}), ensure_ascii=False),
                    json.dumps(candidate_data.get("monetization_info", {}), ensure_ascii=False),
                    json.dumps(candidate_data.get("status_info", {}), ensure_ascii=False),
                    now,
                    candidate_id
                ))
                logger.info(f"Updated candidate: {candidate_id}")
            else:
                # 신규 삽입
                conn.execute("""
                    INSERT INTO candidates (id, source_info, candidate_info, monetization_info, status_info, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    candidate_id,
                    json.dumps(candidate_data.get("source_info", {}), ensure_ascii=False),
                    json.dumps(candidate_data.get("candidate_info", {}), ensure_ascii=False),
                    json.dumps(candidate_data.get("monetization_info", {}), ensure_ascii=False),
                    json.dumps(candidate_data.get("status_info", {}), ensure_ascii=False),
                    now,
                    now
                ))
                logger.info(f"Created candidate: {candidate_id}")
                
            conn.commit()
            # 캐시 무효화
            self._get_cached_status_counts.cache_clear()
            self._get_cached_candidate_list.cache_clear()
            return True
                
        except Exception as e:
            logger.error(f"Failed to save candidate: {e}")
            return False
            
    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """
        후보 데이터 조회
        
        Args:
            candidate_id: 후보 ID
            
        Returns:
            후보 데이터 또는 None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT source_info, candidate_info, monetization_info, status_info, created_at, updated_at
                    FROM candidates WHERE id = ?
                """, (candidate_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                    
                source_info, candidate_info, monetization_info, status_info, created_at, updated_at = row
                
                return {
                    "source_info": json.loads(source_info),
                    "candidate_info": json.loads(candidate_info),
                    "monetization_info": json.loads(monetization_info),
                    "status_info": json.loads(status_info),
                    "created_at": created_at,
                    "updated_at": updated_at
                }
                
        except Exception as e:
            logger.error(f"Failed to get candidate {candidate_id}: {e}")
            return None
            
    def get_candidates_by_status(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        상태별 후보 목록 조회 (캐시 사용)
        
        Args:
            status: 조회할 상태 (None이면 전체)
            limit: 최대 결과 수
            offset: 시작 오프셋
            
        Returns:
            후보 데이터 목록
        """
        try:
            # 캐시 키 생성 (5분마다 갱신)
            cache_key = f"{int(time.time() // self._cache_timeout)}"
            status_key = status or "all"
            
            return self._get_cached_candidate_list(status_key, limit, offset, cache_key)
                
        except Exception as e:
            logger.error(f"Failed to get candidates by status: {e}")
            return []
            
    def update_candidate_status(
        self,
        candidate_id: str,
        new_status: str,
        reason: str = "",
        operator_id: str = "system"
    ) -> bool:
        """
        후보 상태 업데이트 및 이력 기록
        
        Args:
            candidate_id: 후보 ID
            new_status: 새로운 상태
            reason: 변경 사유
            operator_id: 운영자 ID
            
        Returns:
            성공 여부
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 현재 상태 조회
                cursor = conn.execute("""
                    SELECT status_info FROM candidates WHERE id = ?
                """, (candidate_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Candidate not found: {candidate_id}")
                    return False
                    
                current_status_info = json.loads(row[0])
                old_status = current_status_info.get("current_status", "unknown")
                
                # 상태 정보 업데이트
                current_status_info["current_status"] = new_status
                current_status_info["updated_at"] = datetime.now().isoformat()
                current_status_info["updated_by"] = operator_id
                current_status_info["last_reason"] = reason
                
                # 후보 데이터 업데이트
                conn.execute("""
                    UPDATE candidates 
                    SET status_info = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    json.dumps(current_status_info, ensure_ascii=False),
                    datetime.now().isoformat(),
                    candidate_id
                ))
                
                # 상태 변경 이력 기록
                conn.execute("""
                    INSERT INTO status_history (candidate_id, from_status, to_status, reason, operator_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    candidate_id,
                    old_status,
                    new_status,
                    reason,
                    operator_id,
                    json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "manual_change": True
                    }, ensure_ascii=False)
                ))
                
                conn.commit()
                logger.info(f"Status updated: {candidate_id} {old_status} -> {new_status}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update candidate status: {e}")
            return False
            
    def get_status_history(
        self,
        candidate_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        상태 변경 이력 조회
        
        Args:
            candidate_id: 후보 ID
            limit: 최대 결과 수
            
        Returns:
            상태 이력 목록
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT from_status, to_status, reason, operator_id, timestamp, metadata
                    FROM status_history 
                    WHERE candidate_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (candidate_id, limit))
                
                rows = cursor.fetchall()
                
                history = []
                for row in rows:
                    from_status, to_status, reason, operator_id, timestamp, metadata = row
                    
                    history.append({
                        "from_status": from_status,
                        "to_status": to_status,
                        "reason": reason,
                        "operator_id": operator_id,
                        "timestamp": timestamp,
                        "metadata": json.loads(metadata) if metadata else {}
                    })
                    
                return history
                
        except Exception as e:
            logger.error(f"Failed to get status history: {e}")
            return []
            
    def get_status_statistics(self) -> Dict[str, Any]:
        """상태별 통계 정보 조회 (캐시 사용)"""
        try:
            # 캐시 키 생성 (5분마다 갱신)
            cache_key = f"{int(time.time() // self._cache_timeout)}"
            status_counts = self._get_cached_status_counts(cache_key)
            
            conn = self._get_connection()
            
            # 최근 활동
            cursor = conn.execute("""
                SELECT COUNT(*) FROM status_history 
                WHERE timestamp >= datetime('now', '-24 hours')
            """)
            recent_changes = cursor.fetchone()[0]
            
            # 총 후보 수
            cursor = conn.execute("SELECT COUNT(*) FROM candidates")
            total_candidates = cursor.fetchone()[0]
            
            return {
                "total_candidates": total_candidates,
                "status_distribution": status_counts,
                "recent_changes_24h": recent_changes,
                "last_updated": datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"Failed to get status statistics: {e}")
            return {}
            
    def _extract_candidate_id(self, candidate_data: Dict[str, Any]) -> Optional[str]:
        """후보 데이터에서 ID 추출"""
        # 여러 가능한 ID 필드 확인
        for field in ["id", "candidate_id"]:
            if field in candidate_data:
                return candidate_data[field]
                
        # source_info에서 URL 기반 ID 생성
        source_info = candidate_data.get("source_info", {})
        video_url = source_info.get("video_url", "")
        if video_url:
            # URL에서 고유 식별자 추출
            if "youtube.com/watch?v=" in video_url:
                video_id = video_url.split("v=")[1].split("&")[0]
                clip_start = candidate_data.get("candidate_info", {}).get("clip_start_time", 0)
                return f"{video_id}_{clip_start}"
                
        return None
        
    def delete_candidate(self, candidate_id: str) -> bool:
        """후보 데이터 삭제"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 관련 이력도 함께 삭제
                conn.execute("DELETE FROM status_history WHERE candidate_id = ?", (candidate_id,))
                conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
                conn.commit()
                
                logger.info(f"Deleted candidate: {candidate_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete candidate: {e}")
            return False
            
    def save_search_event(
        self, 
        candidate_id: str, 
        search_event: Dict[str, Any]
    ) -> bool:
        """
        T03_S02_M02: 검색 이벤트 저장
        
        Args:
            candidate_id: 후보 ID
            search_event: 검색 이벤트 정보
            
        Returns:
            저장 성공 여부
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                metadata = {
                    'image_data': search_event.get('image_data'),
                    'uploaded_image': str(search_event.get('uploaded_image', '')),
                    'user_agent': 'dashboard',
                    'session_info': search_event.get('session_info', {})
                }
                
                conn.execute("""
                    INSERT INTO search_history 
                    (candidate_id, search_engine, query, search_type, search_url, session_key, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    candidate_id,
                    search_event.get('engine', ''),
                    search_event.get('query', ''),
                    search_event.get('type', 'text'),
                    search_event.get('url', ''),
                    search_event.get('session_key', ''),
                    json.dumps(metadata)
                ))
                
                conn.commit()
                logger.info(f"Saved search event for candidate {candidate_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save search event: {e}")
            return False
    
    def get_search_history(
        self, 
        candidate_id: str = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        검색 이력 조회
        
        Args:
            candidate_id: 특정 후보의 이력만 조회 (None이면 전체)
            limit: 최대 조회 개수
            
        Returns:
            검색 이력 목록
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if candidate_id:
                    cursor = conn.execute("""
                        SELECT id, candidate_id, search_engine, query, search_type, 
                               search_url, session_key, timestamp, metadata
                        FROM search_history 
                        WHERE candidate_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (candidate_id, limit))
                else:
                    cursor = conn.execute("""
                        SELECT id, candidate_id, search_engine, query, search_type, 
                               search_url, session_key, timestamp, metadata
                        FROM search_history 
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (limit,))
                
                rows = cursor.fetchall()
                
                history = []
                for row in rows:
                    (search_id, cand_id, engine, query, search_type, 
                     url, session_key, timestamp, metadata) = row
                    
                    history.append({
                        "id": search_id,
                        "candidate_id": cand_id,
                        "search_engine": engine,
                        "query": query,
                        "search_type": search_type,
                        "search_url": url,
                        "session_key": session_key,
                        "timestamp": timestamp,
                        "metadata": json.loads(metadata) if metadata else {}
                    })
                    
                return history
                
        except Exception as e:
            logger.error(f"Failed to get search history: {e}")
            return []
    
    def save_search_feedback(
        self, 
        candidate_id: str, 
        feedback_type: str,
        search_id: int = None,
        comments: str = None,
        session_key: str = None
    ) -> bool:
        """
        검색 피드백 저장
        
        Args:
            candidate_id: 후보 ID
            feedback_type: 피드백 유형 (positive, neutral, negative)
            search_id: 관련 검색 ID (선택적)
            comments: 추가 코멘트 (선택적)
            session_key: 세션 키 (선택적)
            
        Returns:
            저장 성공 여부
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO search_feedback 
                    (candidate_id, search_id, feedback_type, comments, session_key)
                    VALUES (?, ?, ?, ?, ?)
                """, (candidate_id, search_id, feedback_type, comments, session_key))
                
                conn.commit()
                logger.info(f"Saved search feedback for candidate {candidate_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save search feedback: {e}")
            return False
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """
        검색 관련 통계 조회
        
        Returns:
            검색 통계 정보
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 검색 엔진별 사용 통계
                cursor = conn.execute("""
                    SELECT search_engine, COUNT(*) as count
                    FROM search_history
                    GROUP BY search_engine
                """)
                engine_stats = dict(cursor.fetchall())
                
                # 검색 타입별 통계
                cursor = conn.execute("""
                    SELECT search_type, COUNT(*) as count
                    FROM search_history
                    GROUP BY search_type
                """)
                type_stats = dict(cursor.fetchall())
                
                # 최근 24시간 검색 수
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM search_history 
                    WHERE timestamp >= datetime('now', '-24 hours')
                """)
                recent_searches = cursor.fetchone()[0]
                
                # 피드백 통계
                cursor = conn.execute("""
                    SELECT feedback_type, COUNT(*) as count
                    FROM search_feedback
                    GROUP BY feedback_type
                """)
                feedback_stats = dict(cursor.fetchall())
                
                # 총 검색 수
                cursor = conn.execute("SELECT COUNT(*) FROM search_history")
                total_searches = cursor.fetchone()[0]
                
                # 고유 후보 검색 수
                cursor = conn.execute("SELECT COUNT(DISTINCT candidate_id) FROM search_history")
                unique_candidates = cursor.fetchone()[0]
                
                return {
                    "total_searches": total_searches,
                    "unique_candidates_searched": unique_candidates,
                    "recent_searches_24h": recent_searches,
                    "engine_distribution": engine_stats,
                    "type_distribution": type_stats,
                    "feedback_distribution": feedback_stats,
                    "last_updated": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get search statistics: {e}")
            return {}
    
    def get_popular_search_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        인기 검색 쿼리 조회
        
        Args:
            limit: 최대 조회 개수
            
        Returns:
            인기 검색 쿼리 목록
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT query, COUNT(*) as search_count, 
                           MAX(timestamp) as last_searched
                    FROM search_history
                    WHERE query != '' AND query IS NOT NULL
                    GROUP BY LOWER(query)
                    ORDER BY search_count DESC, last_searched DESC
                    LIMIT ?
                """, (limit,))
                
                popular_queries = []
                for row in cursor.fetchall():
                    query, count, last_searched = row
                    popular_queries.append({
                        "query": query,
                        "search_count": count,
                        "last_searched": last_searched
                    })
                    
                return popular_queries
                
        except Exception as e:
            logger.error(f"Failed to get popular search queries: {e}")
            return []
    
    def save_candidates_batch(self, candidates_data: List[Dict[str, Any]]) -> int:
        """
        후보 데이터 배치 저장 (성능 최적화)
        
        Args:
            candidates_data: 후보 데이터 목록
            
        Returns:
            성공적으로 저장된 개수
        """
        if not candidates_data:
            return 0
            
        saved_count = 0
        try:
            conn = self._get_connection()
            conn.execute("BEGIN IMMEDIATE")  # 즉시 배타적 트랜잭션 시작
            
            for candidate_data in candidates_data:
                try:
                    candidate_id = self._extract_candidate_id(candidate_data)
                    if not candidate_id:
                        logger.warning("Candidate ID not found, skipping")
                        continue
                    
                    now = datetime.now().isoformat()
                    
                    # UPSERT 쿼리 사용 (SQLite 3.24+)
                    conn.execute("""
                        INSERT INTO candidates (id, source_info, candidate_info, monetization_info, status_info, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            source_info = excluded.source_info,
                            candidate_info = excluded.candidate_info,
                            monetization_info = excluded.monetization_info,
                            status_info = excluded.status_info,
                            updated_at = excluded.updated_at
                    """, (
                        candidate_id,
                        json.dumps(candidate_data.get("source_info", {}), ensure_ascii=False),
                        json.dumps(candidate_data.get("candidate_info", {}), ensure_ascii=False),
                        json.dumps(candidate_data.get("monetization_info", {}), ensure_ascii=False),
                        json.dumps(candidate_data.get("status_info", {}), ensure_ascii=False),
                        now,
                        now
                    ))
                    saved_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to save individual candidate: {e}")
                    continue
                    
            conn.execute("COMMIT")
            
            # 캐시 무효화
            self._get_cached_status_counts.cache_clear()
            self._get_cached_candidate_list.cache_clear()
            
            logger.info(f"Batch saved {saved_count}/{len(candidates_data)} candidates")
            return saved_count
            
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except:
                pass
            logger.error(f"Failed to batch save candidates: {e}")
            return 0
    
    def update_status_batch(self, status_updates: List[Dict[str, Any]]) -> int:
        """
        상태 배치 업데이트
        
        Args:
            status_updates: [{"candidate_id": str, "new_status": str, "reason": str}, ...]
            
        Returns:
            성공적으로 업데이트된 개수
        """
        if not status_updates:
            return 0
            
        updated_count = 0
        try:
            conn = self._get_connection()
            conn.execute("BEGIN IMMEDIATE")
            
            for update in status_updates:
                try:
                    candidate_id = update.get("candidate_id")
                    new_status = update.get("new_status")
                    reason = update.get("reason", "")
                    operator_id = update.get("operator_id", "system")
                    
                    if not candidate_id or not new_status:
                        continue
                    
                    # 현재 상태 조회
                    cursor = conn.execute("""
                        SELECT status_info FROM candidates WHERE id = ?
                    """, (candidate_id,))
                    
                    row = cursor.fetchone()
                    if not row:
                        continue
                        
                    current_status_info = json.loads(row[0])
                    old_status = current_status_info.get("current_status", "unknown")
                    
                    # 상태 정보 업데이트
                    current_status_info["current_status"] = new_status
                    current_status_info["updated_at"] = datetime.now().isoformat()
                    current_status_info["updated_by"] = operator_id
                    current_status_info["last_reason"] = reason
                    
                    # 후보 데이터 업데이트
                    conn.execute("""
                        UPDATE candidates 
                        SET status_info = ?, updated_at = ?
                        WHERE id = ?
                    """, (
                        json.dumps(current_status_info, ensure_ascii=False),
                        datetime.now().isoformat(),
                        candidate_id
                    ))
                    
                    # 상태 변경 이력 기록
                    conn.execute("""
                        INSERT INTO status_history (candidate_id, from_status, to_status, reason, operator_id, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        candidate_id,
                        old_status,
                        new_status,
                        reason,
                        operator_id,
                        json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "batch_update": True
                        }, ensure_ascii=False)
                    ))
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to update individual status: {e}")
                    continue
                    
            conn.execute("COMMIT")
            
            # 캐시 무효화
            self._get_cached_status_counts.cache_clear()
            self._get_cached_candidate_list.cache_clear()
            
            logger.info(f"Batch updated {updated_count}/{len(status_updates)} statuses")
            return updated_count
            
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except:
                pass
            logger.error(f"Failed to batch update statuses: {e}")
            return 0
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """
        오래된 데이터 정리 (성능 유지)
        
        Args:
            days_to_keep: 보관할 일수
            
        Returns:
            정리된 레코드 수
        """
        cleaned = {"audit_logs": 0, "status_history": 0, "search_history": 0}
        
        try:
            conn = self._get_connection()
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            # 오래된 감사 로그 정리
            cursor = conn.execute("""
                DELETE FROM audit_logs 
                WHERE created_at < ?
            """, (cutoff_str,))
            cleaned["audit_logs"] = cursor.rowcount
            
            # 오래된 상태 이력 정리 (최근 5개는 보존)
            cursor = conn.execute("""
                DELETE FROM status_history 
                WHERE timestamp < ? AND id NOT IN (
                    SELECT id FROM status_history 
                    WHERE candidate_id = status_history.candidate_id 
                    ORDER BY timestamp DESC 
                    LIMIT 5
                )
            """, (cutoff_str,))
            cleaned["status_history"] = cursor.rowcount
            
            # 오래된 검색 이력 정리
            cursor = conn.execute("""
                DELETE FROM search_history 
                WHERE timestamp < ?
            """, (cutoff_str,))
            cleaned["search_history"] = cursor.rowcount
            
            conn.commit()
            
            # 데이터베이스 최적화
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            
            logger.info(f"Cleaned old data: {cleaned}")
            return cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return cleaned
    
    def get_database_stats(self) -> Dict[str, Any]:
        """데이터베이스 통계 및 성능 지표"""
        try:
            conn = self._get_connection()
            stats = {}
            
            # 테이블별 레코드 수
            tables = ['candidates', 'status_history', 'audit_logs', 'search_history', 'search_feedback']
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            
            # 데이터베이스 파일 크기
            db_path = Path(self.db_path)
            if db_path.exists():
                stats["db_size_mb"] = db_path.stat().st_size / (1024 * 1024)
            
            # WAL 파일 크기
            wal_path = Path(f"{self.db_path}-wal")
            if wal_path.exists():
                stats["wal_size_mb"] = wal_path.stat().st_size / (1024 * 1024)
            
            # 인덱스 사용 통계
            cursor = conn.execute("""
                SELECT name, tbl_name FROM sqlite_master 
                WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
            """)
            stats["index_count"] = len(cursor.fetchall())
            
            # 캐시 히트율 추정
            stats["cache_info"] = {
                "status_counts_cache": self._get_cached_status_counts.cache_info()._asdict(),
                "candidate_list_cache": self._get_cached_candidate_list.cache_info()._asdict()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    def close(self):
        """데이터베이스 연결 정리"""
        with self._pool_lock:
            for conn in self._connection_pool.values():
                try:
                    conn.close()
                except:
                    pass
            self._connection_pool.clear()
        logger.info("Database manager closed")


# 전역 데이터베이스 매니저 인스턴스
_db_manager = None

def get_database_manager() -> DatabaseManager:
    """싱글톤 데이터베이스 매니저 반환"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager