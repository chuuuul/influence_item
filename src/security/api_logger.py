"""
API 호출 로깅 및 모니터링 시스템

모든 API 호출을 로깅하고 모니터링 데이터를 수집합니다.
"""

import time
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import threading
from queue import Queue
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class APICallLog:
    """API 호출 로그"""
    timestamp: float
    api_name: str
    endpoint: str
    method: str
    status_code: Optional[int]
    response_time: float
    request_size: int
    response_size: int
    success: bool
    error_message: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    api_key_hash: Optional[str] = None


class APILogger:
    """API 호출 로거"""
    
    def __init__(self, db_path: Optional[Path] = None, buffer_size: int = 100):
        """
        Args:
            db_path: SQLite 데이터베이스 경로
            buffer_size: 버퍼 크기
        """
        self.db_path = db_path or Path("logs/api_calls.db")
        self.buffer_size = buffer_size
        self.log_buffer: Queue = Queue()
        self.is_running = True
        
        # 저장 디렉토리 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 백그라운드 로깅 스레드 시작
        self.logging_thread = threading.Thread(target=self._logging_worker, daemon=True)
        self.logging_thread.start()
        
        logger.info("API 로거 초기화 완료")
    
    def _init_database(self) -> None:
        """데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_calls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        api_name TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        method TEXT NOT NULL,
                        status_code INTEGER,
                        response_time REAL NOT NULL,
                        request_size INTEGER NOT NULL,
                        response_size INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        user_agent TEXT,
                        ip_address TEXT,
                        api_key_hash TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 인덱스 생성
                conn.execute("CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON api_calls(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_api_calls_api_name ON api_calls(api_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_api_calls_success ON api_calls(success)")
                
                conn.commit()
                
            logger.info("API 로그 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {str(e)}")
    
    def log_api_call(self, call_log: APICallLog) -> None:
        """API 호출 로그 추가"""
        try:
            self.log_buffer.put_nowait(call_log)
        except Exception as e:
            logger.error(f"API 로그 버퍼 추가 실패: {str(e)}")
    
    def _logging_worker(self) -> None:
        """백그라운드 로깅 워커"""
        batch = []
        
        while self.is_running:
            try:
                # 배치 수집
                while len(batch) < self.buffer_size:
                    try:
                        log_entry = self.log_buffer.get(timeout=1.0)
                        batch.append(log_entry)
                    except:
                        break
                
                # 배치 저장
                if batch:
                    self._save_batch(batch)
                    batch.clear()
                    
            except Exception as e:
                logger.error(f"로깅 워커 오류: {str(e)}")
    
    def _save_batch(self, batch: List[APICallLog]) -> None:
        """배치 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for log_entry in batch:
                    cursor.execute("""
                        INSERT INTO api_calls (
                            timestamp, api_name, endpoint, method, status_code,
                            response_time, request_size, response_size, success,
                            error_message, user_agent, ip_address, api_key_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        log_entry.timestamp,
                        log_entry.api_name,
                        log_entry.endpoint,
                        log_entry.method,
                        log_entry.status_code,
                        log_entry.response_time,
                        log_entry.request_size,
                        log_entry.response_size,
                        log_entry.success,
                        log_entry.error_message,
                        log_entry.user_agent,
                        log_entry.ip_address,
                        log_entry.api_key_hash
                    ))
                
                conn.commit()
                
            logger.debug(f"API 로그 배치 저장 완료: {len(batch)}건")
            
        except Exception as e:
            logger.error(f"API 로그 배치 저장 실패: {str(e)}")
    
    def get_api_stats(self, api_name: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        """API 통계 조회"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                base_query = """
                    SELECT 
                        api_name,
                        COUNT(*) as total_calls,
                        COUNT(CASE WHEN success = 1 THEN 1 END) as success_calls,
                        COUNT(CASE WHEN success = 0 THEN 1 END) as error_calls,
                        AVG(response_time) as avg_response_time,
                        MIN(response_time) as min_response_time,
                        MAX(response_time) as max_response_time,
                        SUM(request_size) as total_request_size,
                        SUM(response_size) as total_response_size
                    FROM api_calls 
                    WHERE timestamp >= ?
                """
                
                if api_name:
                    base_query += " AND api_name = ?"
                    params = [cutoff_time, api_name]
                else:
                    params = [cutoff_time]
                
                base_query += " GROUP BY api_name"
                
                cursor.execute(base_query, params)
                results = cursor.fetchall()
                
                stats = {}
                for row in results:
                    api_stats = dict(row)
                    api_stats["success_rate"] = api_stats["success_calls"] / max(1, api_stats["total_calls"])
                    api_stats["error_rate"] = api_stats["error_calls"] / max(1, api_stats["total_calls"])
                    stats[row["api_name"]] = api_stats
                
                return stats
                
        except Exception as e:
            logger.error(f"API 통계 조회 실패: {str(e)}")
            return {}
    
    def get_error_summary(self, api_name: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """에러 요약 조회"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        api_name,
                        error_message,
                        COUNT(*) as error_count,
                        MAX(timestamp) as last_occurrence
                    FROM api_calls 
                    WHERE timestamp >= ? AND success = 0 AND error_message IS NOT NULL
                """
                
                params = [cutoff_time]
                if api_name:
                    query += " AND api_name = ?"
                    params.append(api_name)
                
                query += " GROUP BY api_name, error_message ORDER BY error_count DESC"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"에러 요약 조회 실패: {str(e)}")
            return []
    
    def get_response_time_percentiles(self, api_name: str, hours: int = 24) -> Dict[str, float]:
        """응답 시간 백분위수 조회"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT response_time 
                    FROM api_calls 
                    WHERE timestamp >= ? AND api_name = ? AND success = 1
                    ORDER BY response_time
                """, [cutoff_time, api_name])
                
                response_times = [row[0] for row in cursor.fetchall()]
                
                if not response_times:
                    return {}
                
                def percentile(data, p):
                    if not data:
                        return 0
                    k = (len(data) - 1) * p / 100
                    f = int(k)
                    c = k - f
                    if f + 1 < len(data):
                        return data[f] * (1 - c) + data[f + 1] * c
                    else:
                        return data[f]
                
                return {
                    "p50": percentile(response_times, 50),
                    "p75": percentile(response_times, 75),
                    "p90": percentile(response_times, 90),
                    "p95": percentile(response_times, 95),
                    "p99": percentile(response_times, 99)
                }
                
        except Exception as e:
            logger.error(f"응답 시간 백분위수 조회 실패: {str(e)}")
            return {}
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """오래된 로그 정리"""
        try:
            cutoff_time = time.time() - (days * 86400)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM api_calls WHERE timestamp < ?", [cutoff_time])
                deleted_count = cursor.rowcount
                conn.commit()
                
            logger.info(f"오래된 API 로그 정리 완료: {deleted_count}건 삭제")
            return deleted_count
            
        except Exception as e:
            logger.error(f"로그 정리 실패: {str(e)}")
            return 0
    
    def export_logs(self, api_name: Optional[str] = None, hours: int = 24, format: str = "json") -> str:
        """로그 내보내기"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM api_calls WHERE timestamp >= ?"
                params = [cutoff_time]
                
                if api_name:
                    query += " AND api_name = ?"
                    params.append(api_name)
                
                query += " ORDER BY timestamp DESC"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                if format == "json":
                    return json.dumps([dict(row) for row in results], indent=2)
                elif format == "csv":
                    import csv
                    import io
                    
                    output = io.StringIO()
                    if results:
                        writer = csv.DictWriter(output, fieldnames=results[0].keys())
                        writer.writeheader()
                        writer.writerows([dict(row) for row in results])
                    
                    return output.getvalue()
                
        except Exception as e:
            logger.error(f"로그 내보내기 실패: {str(e)}")
            return ""
    
    def stop(self) -> None:
        """로거 중지"""
        self.is_running = False
        if self.logging_thread.is_alive():
            self.logging_thread.join(timeout=5.0)
        logger.info("API 로거 중지 완료")


# 전역 API 로거 인스턴스
_api_logger = None

def get_api_logger() -> APILogger:
    """API 로거 싱글톤 인스턴스 반환"""
    global _api_logger
    if _api_logger is None:
        _api_logger = APILogger()
    return _api_logger