"""
데이터베이스 관리 유틸리티
T08_S01_M02: Workflow State Management - Database Operations

후보 데이터의 CRUD 작업 및 상태 관리를 위한 데이터베이스 연동
"""

import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 관리자"""
    
    def __init__(self, db_path: str = "influence_item.db"):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = db_path
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
                    CREATE INDEX IF NOT EXISTS idx_audit_logs_category 
                    ON audit_logs(category)
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
            
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
                
            with sqlite3.connect(self.db_path) as conn:
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
        상태별 후보 목록 조회
        
        Args:
            status: 조회할 상태 (None이면 전체)
            limit: 최대 결과 수
            offset: 시작 오프셋
            
        Returns:
            후보 데이터 목록
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if status:
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
        """상태별 통계 정보 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 상태별 개수
                cursor = conn.execute("""
                    SELECT json_extract(status_info, '$.current_status') as status, COUNT(*) as count
                    FROM candidates
                    GROUP BY status
                """)
                
                status_counts = {}
                for row in cursor.fetchall():
                    status, count = row
                    status_counts[status or "unknown"] = count
                    
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
            
    def close(self):
        """데이터베이스 연결 정리"""
        logger.info("Database manager closed")


# 전역 데이터베이스 매니저 인스턴스
_db_manager = None

def get_database_manager() -> DatabaseManager:
    """싱글톤 데이터베이스 매니저 반환"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager