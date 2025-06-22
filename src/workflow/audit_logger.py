"""
워크플로우 감사 로거

모든 필터링 결정, 상태 전환, 워크플로우 실행을 추적하고 로깅합니다.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import sqlite3
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """로그 레벨"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    """로그 카테고리"""
    WORKFLOW = "workflow"
    FILTER = "filter"
    PRIORITY = "priority"
    STATE = "state"
    PERFORMANCE = "performance"
    ERROR = "error"


@dataclass
class AuditLogEntry:
    """감사 로그 엔트리"""
    timestamp: datetime
    category: LogCategory
    level: LogLevel
    candidate_id: str
    message: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "level": self.level.value,
            "candidate_id": self.candidate_id,
            "message": self.message,
            "metadata": self.metadata
        }


class AuditLogger:
    """워크플로우 감사 로거"""
    
    def __init__(self, db_path: Optional[str] = None, max_entries: int = 10000):
        """
        Args:
            db_path: SQLite 데이터베이스 경로 (None이면 메모리)
            max_entries: 최대 로그 엔트리 수 (오래된 것부터 삭제)
        """
        self.db_path = db_path or ":memory:"
        self.max_entries = max_entries
        self.in_memory_logs: List[AuditLogEntry] = []
        
        # 데이터베이스 초기화
        self._init_database()
        
    def _init_database(self):
        """데이터베이스 테이블 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON audit_logs(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_candidate_id 
                    ON audit_logs(candidate_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_category 
                    ON audit_logs(category)
                """)
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to initialize audit database: {e}")
            
    def log(
        self,
        category: LogCategory,
        level: LogLevel,
        candidate_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        감사 로그 기록
        
        Args:
            category: 로그 카테고리
            level: 로그 레벨
            candidate_id: 후보 ID
            message: 로그 메시지
            metadata: 추가 메타데이터
        """
        if metadata is None:
            metadata = {}
            
        entry = AuditLogEntry(
            timestamp=datetime.now(),
            category=category,
            level=level,
            candidate_id=candidate_id,
            message=message,
            metadata=metadata
        )
        
        # 메모리에 저장
        self.in_memory_logs.append(entry)
        
        # 메모리 제한 확인
        if len(self.in_memory_logs) > self.max_entries:
            self.in_memory_logs = self.in_memory_logs[-self.max_entries:]
            
        # 데이터베이스에 저장
        self._save_to_database(entry)
        
        # 표준 로그에도 기록
        python_logger = logging.getLogger(f"audit.{category.value}")
        log_method = getattr(python_logger, level.value, python_logger.info)
        log_method(f"[{candidate_id}] {message}")
        
    def _save_to_database(self, entry: AuditLogEntry):
        """데이터베이스에 로그 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO audit_logs 
                    (timestamp, category, level, candidate_id, message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    entry.timestamp.isoformat(),
                    entry.category.value,
                    entry.level.value,
                    entry.candidate_id,
                    entry.message,
                    json.dumps(entry.metadata, ensure_ascii=False)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save audit log to database: {e}")
            
    def log_workflow_execution(self, workflow_result):
        """워크플로우 실행 결과 로깅"""
        from .workflow_manager import WorkflowResult
        
        if isinstance(workflow_result, WorkflowResult):
            if workflow_result.success:
                self.log(
                    LogCategory.WORKFLOW,
                    LogLevel.INFO,
                    workflow_result.candidate_id,
                    f"Workflow completed successfully in {workflow_result.processing_time_ms}ms",
                    {
                        "processing_time_ms": workflow_result.processing_time_ms,
                        "final_status": workflow_result.state_transition.to_status.value if workflow_result.state_transition else None,
                        "priority_score": workflow_result.priority_score.total_score if workflow_result.priority_score else None,
                        "filter_actions_count": len(workflow_result.filter_actions)
                    }
                )
            else:
                self.log_workflow_error(workflow_result.candidate_id, workflow_result.error_message)
                
    def log_workflow_error(self, candidate_id: str, error_message: str):
        """워크플로우 오류 로깅"""
        self.log(
            LogCategory.ERROR,
            LogLevel.ERROR,
            candidate_id,
            f"Workflow execution failed: {error_message}",
            {"error_type": "workflow_execution"}
        )
        
    def log_filter_decision(
        self,
        candidate_id: str,
        rule_name: str,
        decision: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """필터링 결정 로깅"""
        log_metadata = {"rule_name": rule_name, "decision": decision}
        if metadata:
            log_metadata.update(metadata)
            
        self.log(
            LogCategory.FILTER,
            LogLevel.INFO,
            candidate_id,
            f"Filter rule '{rule_name}' applied: {decision} - {reason}",
            log_metadata
        )
        
    def log_priority_calculation(
        self,
        candidate_id: str,
        priority_score: float,
        priority_level: str,
        factors: Dict[str, float]
    ):
        """우선순위 계산 로깅"""
        self.log(
            LogCategory.PRIORITY,
            LogLevel.INFO,
            candidate_id,
            f"Priority calculated: {priority_score:.1f} ({priority_level})",
            {
                "priority_score": priority_score,
                "priority_level": priority_level,
                "factors": factors
            }
        )
        
    def log_state_transition(
        self,
        candidate_id: str,
        from_status: str,
        to_status: str,
        reason: str
    ):
        """상태 전환 로깅"""
        self.log(
            LogCategory.STATE,
            LogLevel.INFO,
            candidate_id,
            f"Status changed: {from_status} -> {to_status}",
            {
                "from_status": from_status,
                "to_status": to_status,
                "transition_reason": reason
            }
        )
        
    def log_performance_metric(
        self,
        candidate_id: str,
        metric_name: str,
        value: Union[int, float],
        unit: str = ""
    ):
        """성능 지표 로깅"""
        self.log(
            LogCategory.PERFORMANCE,
            LogLevel.DEBUG,
            candidate_id,
            f"Performance metric: {metric_name} = {value}{unit}",
            {
                "metric_name": metric_name,
                "value": value,
                "unit": unit
            }
        )
        
    def get_logs(
        self,
        candidate_id: Optional[str] = None,
        category: Optional[LogCategory] = None,
        level: Optional[LogLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AuditLogEntry]:
        """
        조건에 맞는 로그 조회
        
        Args:
            candidate_id: 후보 ID 필터
            category: 카테고리 필터
            level: 로그 레벨 필터
            start_time: 시작 시간
            end_time: 종료 시간
            limit: 최대 결과 수
            
        Returns:
            AuditLogEntry 목록
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT timestamp, category, level, candidate_id, message, metadata FROM audit_logs WHERE 1=1"
                params = []
                
                if candidate_id:
                    query += " AND candidate_id = ?"
                    params.append(candidate_id)
                    
                if category:
                    query += " AND category = ?"
                    params.append(category.value)
                    
                if level:
                    query += " AND level = ?"
                    params.append(level.value)
                    
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())
                    
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())
                    
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                logs = []
                for row in rows:
                    timestamp, category_str, level_str, cid, message, metadata_str = row
                    
                    logs.append(AuditLogEntry(
                        timestamp=datetime.fromisoformat(timestamp),
                        category=LogCategory(category_str),
                        level=LogLevel(level_str),
                        candidate_id=cid,
                        message=message,
                        metadata=json.loads(metadata_str)
                    ))
                    
                return logs
                
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {e}")
            return []
            
    def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        로그 통계 생성
        
        Args:
            start_time: 통계 시작 시간
            end_time: 통계 종료 시간
            
        Returns:
            통계 딕셔너리
        """
        logs = self.get_logs(start_time=start_time, end_time=end_time, limit=10000)
        
        if not logs:
            return {}
            
        # 카테고리별 분포
        category_counts = {}
        level_counts = {}
        candidate_counts = {}
        hourly_counts = {}
        
        for log in logs:
            # 카테고리
            category = log.category.value
            category_counts[category] = category_counts.get(category, 0) + 1
            
            # 레벨
            level = log.level.value
            level_counts[level] = level_counts.get(level, 0) + 1
            
            # 후보별
            candidate_counts[log.candidate_id] = candidate_counts.get(log.candidate_id, 0) + 1
            
            # 시간별
            hour = log.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            
        # 가장 활발한 후보
        most_active_candidate = max(candidate_counts.items(), key=lambda x: x[1]) if candidate_counts else None
        
        # 오류율 계산
        error_count = level_counts.get("error", 0) + level_counts.get("critical", 0)
        error_rate = error_count / len(logs) if logs else 0
        
        return {
            "total_logs": len(logs),
            "category_distribution": category_counts,
            "level_distribution": level_counts,
            "error_rate": error_rate,
            "unique_candidates": len(candidate_counts),
            "most_active_candidate": most_active_candidate,
            "hourly_activity": hourly_counts,
            "time_range": {
                "start": logs[-1].timestamp.isoformat() if logs else None,
                "end": logs[0].timestamp.isoformat() if logs else None
            }
        }
        
    def export_logs(
        self,
        filepath: str,
        format: str = "json",
        **filter_kwargs
    ):
        """
        로그를 파일로 내보내기
        
        Args:
            filepath: 출력 파일 경로
            format: 출력 형식 (json, csv)
            **filter_kwargs: get_logs()에 전달할 필터 인수
        """
        logs = self.get_logs(**filter_kwargs)
        
        if format.lower() == "json":
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_logs": len(logs),
                "logs": [log.to_dict() for log in logs]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
        elif format.lower() == "csv":
            import csv
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "category", "level", "candidate_id", "message", "metadata"
                ])
                
                for log in logs:
                    writer.writerow([
                        log.timestamp.isoformat(),
                        log.category.value,
                        log.level.value,
                        log.candidate_id,
                        log.message,
                        json.dumps(log.metadata, ensure_ascii=False)
                    ])
        else:
            raise ValueError(f"Unsupported export format: {format}")
            
        logger.info(f"Exported {len(logs)} audit logs to {filepath}")
        
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """오래된 로그 정리"""
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM audit_logs WHERE timestamp < ?",
                    (cutoff_time.isoformat(),)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
            logger.info(f"Cleaned up {deleted_count} old audit logs")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            
    def close(self):
        """리소스 정리"""
        # 메모리 로그 클리어
        self.in_memory_logs.clear()
        logger.info("Audit logger closed")