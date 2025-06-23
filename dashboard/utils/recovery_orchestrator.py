"""
T04_S03_M03: 장애 감지 및 자동 복구 시스템 - 복구 오케스트레이터
단계별 복구 시도를 관리하고 조율하는 중앙 관리 시스템
"""

import time
import asyncio
import threading
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# 기존 모듈 임포트
from dashboard.utils.failure_detector import FailureEvent, FailureType, FailureSeverity, get_failure_detector
from dashboard.utils.auto_recovery import AutoRecovery, RecoveryAttempt, RecoveryResult, get_auto_recovery
from dashboard.utils.error_handler import get_error_handler

logger = logging.getLogger(__name__)


class RecoveryStage(Enum):
    """복구 단계"""
    IMMEDIATE = "immediate"     # 즉시 복구
    DELAYED_1MIN = "delayed_1min"   # 1분 후 복구
    DELAYED_5MIN = "delayed_5min"   # 5분 후 복구
    ESCALATED = "escalated"     # 운영자 에스컬레이션


class RecoveryStatus(Enum):
    """복구 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


@dataclass
class RecoverySession:
    """복구 세션 정보"""
    session_id: str
    failure_event: FailureEvent
    current_stage: RecoveryStage
    status: RecoveryStatus
    total_attempts: int
    start_time: datetime
    end_time: Optional[datetime]
    recovery_attempts: List[RecoveryAttempt]
    escalation_reason: Optional[str] = None
    next_attempt_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['failure_event'] = self.failure_event.to_dict()
        data['current_stage'] = self.current_stage.value
        data['status'] = self.status.value
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        if self.next_attempt_time:
            data['next_attempt_time'] = self.next_attempt_time.isoformat()
        data['recovery_attempts'] = [
            {
                'action': attempt.action.value,
                'result': attempt.result.value,
                'message': attempt.message,
                'timestamp': attempt.timestamp.isoformat(),
                'execution_time_seconds': attempt.execution_time_seconds
            }
            for attempt in self.recovery_attempts
        ]
        return data


class RecoveryOrchestrator:
    """복구 오케스트레이터 - 단계별 복구 시도 관리"""
    
    def __init__(self, orchestrator_db: str = "recovery_orchestrator.db"):
        """
        Args:
            orchestrator_db: 오케스트레이터 데이터베이스 파일
        """
        self.orchestrator_db = Path(orchestrator_db)
        self.orchestrator_db.parent.mkdir(exist_ok=True)
        
        # 복구 단계 설정
        self.recovery_stages = [
            {
                'stage': RecoveryStage.IMMEDIATE,
                'delay_seconds': 0,          # 즉시 실행
                'max_attempts': 2,           # 최대 2회 시도
                'timeout_seconds': 120       # 2분 타임아웃
            },
            {
                'stage': RecoveryStage.DELAYED_1MIN,
                'delay_seconds': 60,         # 1분 후 실행
                'max_attempts': 3,           # 최대 3회 시도
                'timeout_seconds': 180       # 3분 타임아웃
            },
            {
                'stage': RecoveryStage.DELAYED_5MIN,
                'delay_seconds': 300,        # 5분 후 실행
                'max_attempts': 2,           # 최대 2회 시도
                'timeout_seconds': 300       # 5분 타임아웃
            }
        ]
        
        # 활성 복구 세션들
        self.active_sessions: Dict[str, RecoverySession] = {}
        
        # 의존성 주입
        self.failure_detector = get_failure_detector()
        self.auto_recovery = get_auto_recovery()
        self.error_handler = get_error_handler()
        
        # 오케스트레이터 상태
        self.is_running = False
        self.orchestrator_thread = None
        
        # 통계 및 모니터링
        self.session_stats = {
            'total_sessions': 0,
            'successful_sessions': 0,
            'failed_sessions': 0,
            'escalated_sessions': 0
        }
        
        # 데이터베이스 초기화
        self._init_database()
        
        self._lock = threading.Lock()
    
    def _init_database(self):
        """오케스트레이터 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.orchestrator_db)
            cursor = conn.cursor()
            
            # 복구 세션 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recovery_sessions (
                    session_id TEXT PRIMARY KEY,
                    component TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    failure_severity TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_attempts INTEGER DEFAULT 0,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    escalation_reason TEXT,
                    failure_event_data TEXT,
                    recovery_attempts_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 단계별 통계 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stage_statistics (
                    stage TEXT PRIMARY KEY,
                    total_executions INTEGER DEFAULT 0,
                    successful_executions INTEGER DEFAULT 0,
                    failed_executions INTEGER DEFAULT 0,
                    avg_execution_time_seconds REAL DEFAULT 0,
                    last_execution TEXT
                )
            ''')
            
            # 에스컬레이션 로그 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS escalation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    component TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    escalation_reason TEXT NOT NULL,
                    escalation_time TEXT NOT NULL,
                    notification_sent BOOLEAN DEFAULT 0,
                    resolved BOOLEAN DEFAULT 0,
                    resolution_time TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Recovery orchestrator database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator database: {e}")
            raise
    
    def start_orchestrator(self):
        """오케스트레이터 시작"""
        if self.is_running:
            logger.info("Recovery orchestrator is already running")
            return
        
        self.is_running = True
        self.orchestrator_thread = threading.Thread(target=self._orchestrator_loop, daemon=True)
        self.orchestrator_thread.start()
        
        logger.info("Recovery orchestrator started")
    
    def stop_orchestrator(self):
        """오케스트레이터 중지"""
        self.is_running = False
        if self.orchestrator_thread and self.orchestrator_thread.is_alive():
            self.orchestrator_thread.join(timeout=10)
        
        logger.info("Recovery orchestrator stopped")
    
    def _orchestrator_loop(self):
        """오케스트레이터 메인 루프"""
        while self.is_running:
            try:
                current_time = datetime.now()
                
                # 활성 세션 처리
                sessions_to_process = []
                with self._lock:
                    for session_id, session in list(self.active_sessions.items()):
                        if (session.status == RecoveryStatus.PENDING and
                            session.next_attempt_time and
                            current_time >= session.next_attempt_time):
                            sessions_to_process.append(session_id)
                
                # 각 세션 처리
                for session_id in sessions_to_process:
                    try:
                        asyncio.run(self._process_recovery_session(session_id))
                    except Exception as e:
                        logger.error(f"Failed to process session {session_id}: {e}")
                
                # 장애 큐에서 새 이벤트 확인
                try:
                    asyncio.run(self._check_new_failures())
                except Exception as e:
                    logger.error(f"Failed to check new failures: {e}")
                
                time.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                logger.error(f"Error in orchestrator loop: {e}")
                time.sleep(30)  # 에러 시 30초 대기
    
    async def _check_new_failures(self):
        """새로운 장애 이벤트 확인"""
        try:
            # 장애 감지기에서 새 이벤트 가져오기
            while True:
                try:
                    failure_event = await asyncio.wait_for(
                        self.failure_detector.failure_queue.get(),
                        timeout=1.0
                    )
                    await self.handle_failure(failure_event)
                    
                except asyncio.TimeoutError:
                    break  # 큐가 비어있음
                    
        except Exception as e:
            logger.error(f"Failed to check new failures: {e}")
    
    async def handle_failure(self, failure: FailureEvent) -> str:
        """
        장애 처리 시작
        
        Args:
            failure: 장애 이벤트
            
        Returns:
            생성된 복구 세션 ID
        """
        try:
            # 중복 처리 방지 - 동일 컴포넌트의 활성 세션 확인
            existing_session = self._find_active_session(failure.component, failure.failure_type)
            if existing_session:
                logger.info(f"Active session exists for {failure.component}: {existing_session.session_id}")
                return existing_session.session_id
            
            # 새 복구 세션 생성
            session_id = f"recovery_{failure.component}_{int(datetime.now().timestamp())}"
            
            recovery_session = RecoverySession(
                session_id=session_id,
                failure_event=failure,
                current_stage=RecoveryStage.IMMEDIATE,
                status=RecoveryStatus.PENDING,
                total_attempts=0,
                start_time=datetime.now(),
                end_time=None,
                recovery_attempts=[],
                next_attempt_time=datetime.now()  # 즉시 실행
            )
            
            # 세션 등록
            with self._lock:
                self.active_sessions[session_id] = recovery_session
                self.session_stats['total_sessions'] += 1
            
            # 데이터베이스에 저장
            self._save_session(recovery_session)
            
            logger.info(f"Recovery session created: {session_id} for {failure.component}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to handle failure: {e}")
            self.error_handler.handle_error(e, 
                context={'failure_event': failure.to_dict()},
                user_message="장애 처리 중 오류가 발생했습니다."
            )
            raise
    
    def _find_active_session(self, component: str, failure_type: FailureType) -> Optional[RecoverySession]:
        """활성 세션 찾기"""
        with self._lock:
            for session in self.active_sessions.values():
                if (session.failure_event.component == component and
                    session.failure_event.failure_type == failure_type and
                    session.status in [RecoveryStatus.PENDING, RecoveryStatus.IN_PROGRESS]):
                    return session
        return None
    
    async def _process_recovery_session(self, session_id: str):
        """복구 세션 처리"""
        try:
            with self._lock:
                session = self.active_sessions.get(session_id)
                if not session:
                    return
                
                # 상태 변경
                session.status = RecoveryStatus.IN_PROGRESS
            
            logger.info(f"Processing recovery session: {session_id} (stage: {session.current_stage.value})")
            
            # 현재 단계 설정 가져오기
            stage_config = self._get_stage_config(session.current_stage)
            if not stage_config:
                await self._escalate_session(session, "Invalid stage configuration")
                return
            
            # 단계별 복구 시도
            recovery_attempts = await asyncio.wait_for(
                self.auto_recovery.attempt_recovery(session.failure_event),
                timeout=stage_config['timeout_seconds']
            )
            
            # 복구 시도 결과 처리
            session.recovery_attempts.extend(recovery_attempts)
            session.total_attempts += len(recovery_attempts)
            
            # 성공 여부 확인
            successful_attempts = [a for a in recovery_attempts if a.result == RecoveryResult.SUCCESS]
            
            if successful_attempts:
                # 복구 성공
                await self._complete_session(session, "Recovery successful")
                
            else:
                # 복구 실패 - 다음 단계로 진행 또는 에스컬레이션
                next_stage = self._get_next_stage(session.current_stage)
                
                if next_stage:
                    await self._advance_to_next_stage(session, next_stage)
                else:
                    await self._escalate_session(session, "All recovery stages exhausted")
            
            # 세션 업데이트 저장
            self._save_session(session)
            
        except asyncio.TimeoutError:
            await self._escalate_session(session, f"Recovery timeout in stage {session.current_stage.value}")
            
        except Exception as e:
            logger.error(f"Failed to process recovery session {session_id}: {e}")
            await self._escalate_session(session, f"Processing error: {str(e)}")
    
    def _get_stage_config(self, stage: RecoveryStage) -> Optional[Dict[str, Any]]:
        """단계 설정 조회"""
        for config in self.recovery_stages:
            if config['stage'] == stage:
                return config
        return None
    
    def _get_next_stage(self, current_stage: RecoveryStage) -> Optional[RecoveryStage]:
        """다음 단계 조회"""
        stage_order = [RecoveryStage.IMMEDIATE, RecoveryStage.DELAYED_1MIN, RecoveryStage.DELAYED_5MIN]
        
        try:
            current_index = stage_order.index(current_stage)
            if current_index < len(stage_order) - 1:
                return stage_order[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    async def _advance_to_next_stage(self, session: RecoverySession, next_stage: RecoveryStage):
        """다음 단계로 진행"""
        try:
            stage_config = self._get_stage_config(next_stage)
            if not stage_config:
                await self._escalate_session(session, f"Invalid next stage: {next_stage.value}")
                return
            
            # 세션 업데이트
            session.current_stage = next_stage
            session.status = RecoveryStatus.PENDING
            session.next_attempt_time = datetime.now() + timedelta(seconds=stage_config['delay_seconds'])
            
            logger.info(f"Session {session.session_id} advanced to stage {next_stage.value} "
                       f"(next attempt: {session.next_attempt_time})")
            
        except Exception as e:
            logger.error(f"Failed to advance session to next stage: {e}")
            await self._escalate_session(session, f"Stage advancement error: {str(e)}")
    
    async def _complete_session(self, session: RecoverySession, message: str):
        """세션 완료 처리"""
        try:
            session.status = RecoveryStatus.COMPLETED
            session.end_time = datetime.now()
            
            # 통계 업데이트
            with self._lock:
                self.session_stats['successful_sessions'] += 1
                if session.session_id in self.active_sessions:
                    del self.active_sessions[session.session_id]
            
            logger.info(f"Recovery session completed: {session.session_id} - {message}")
            
            # 장애 이벤트 해결 마킹
            session.failure_event.resolved = True
            session.failure_event.resolution_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to complete session: {e}")
    
    async def _escalate_session(self, session: RecoverySession, reason: str):
        """세션 에스컬레이션 (운영자 알림)"""
        try:
            session.status = RecoveryStatus.ESCALATED
            session.escalation_reason = reason
            session.end_time = datetime.now()
            
            # 통계 업데이트
            with self._lock:
                self.session_stats['escalated_sessions'] += 1
                if session.session_id in self.active_sessions:
                    del self.active_sessions[session.session_id]
            
            # 에스컬레이션 로그 저장
            self._save_escalation(session, reason)
            
            # 운영자 알림 발송
            await self._send_escalation_alert(session, reason)
            
            logger.warning(f"Recovery session escalated: {session.session_id} - {reason}")
            
        except Exception as e:
            logger.error(f"Failed to escalate session: {e}")
    
    def _save_session(self, session: RecoverySession):
        """세션 데이터베이스 저장"""
        try:
            conn = sqlite3.connect(self.orchestrator_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO recovery_sessions 
                (session_id, component, failure_type, failure_severity, current_stage, status, 
                 total_attempts, start_time, end_time, escalation_reason, failure_event_data, recovery_attempts_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session.session_id,
                session.failure_event.component,
                session.failure_event.failure_type.value,
                session.failure_event.severity.value,
                session.current_stage.value,
                session.status.value,
                session.total_attempts,
                session.start_time.isoformat(),
                session.end_time.isoformat() if session.end_time else None,
                session.escalation_reason,
                json.dumps(session.failure_event.to_dict(), ensure_ascii=False),
                json.dumps([{
                    'action': attempt.action.value,
                    'result': attempt.result.value,
                    'message': attempt.message,
                    'timestamp': attempt.timestamp.isoformat(),
                    'execution_time_seconds': attempt.execution_time_seconds
                } for attempt in session.recovery_attempts], ensure_ascii=False)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def _save_escalation(self, session: RecoverySession, reason: str):
        """에스컬레이션 저장"""
        try:
            conn = sqlite3.connect(self.orchestrator_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO escalation_log 
                (session_id, component, failure_type, escalation_reason, escalation_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session.session_id,
                session.failure_event.component,
                session.failure_event.failure_type.value,
                reason,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save escalation: {e}")
    
    async def _send_escalation_alert(self, session: RecoverySession, reason: str):
        """에스컬레이션 알림 발송"""
        try:
            # 향후 AlertManager와 연동
            failure = session.failure_event
            
            alert_message = f"""
🚨 자동 복구 실패 - 운영자 개입 필요

• 컴포넌트: {failure.component}
• 장애 유형: {failure.failure_type.value}
• 심각도: {failure.severity.value}
• 복구 시도: {session.total_attempts}회
• 에스컬레이션 사유: {reason}
• 발생 시간: {failure.timestamp}

세션 ID: {session.session_id}

즉시 대응이 필요합니다!
"""
            
            # 로그로 기록 (향후 Slack/이메일 연동)
            logger.critical(f"ESCALATION ALERT: {alert_message}")
            
            # 에러 핸들러를 통한 알림
            self.error_handler.handle_error(
                Exception(f"Recovery escalation: {reason}"),
                context={
                    'session_id': session.session_id,
                    'component': failure.component,
                    'failure_type': failure.failure_type.value,
                    'recovery_attempts': session.total_attempts
                },
                user_message="자동 복구에 실패했습니다. 운영자 개입이 필요합니다."
            )
            
        except Exception as e:
            logger.error(f"Failed to send escalation alert: {e}")
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """활성 세션 목록 조회"""
        with self._lock:
            return [session.to_dict() for session in self.active_sessions.values()]
    
    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 상세 정보 조회"""
        with self._lock:
            session = self.active_sessions.get(session_id)
            if session:
                return session.to_dict()
        
        # 데이터베이스에서 조회
        try:
            conn = sqlite3.connect(self.orchestrator_db)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM recovery_sessions WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'session_id': row[0],
                    'component': row[1],
                    'failure_type': row[2],
                    'failure_severity': row[3],
                    'current_stage': row[4],
                    'status': row[5],
                    'total_attempts': row[6],
                    'start_time': row[7],
                    'end_time': row[8],
                    'escalation_reason': row[9],
                    'failure_event_data': json.loads(row[10]) if row[10] else None,
                    'recovery_attempts_data': json.loads(row[11]) if row[11] else []
                }
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to get session details: {e}")
        
        return None
    
    def get_orchestrator_statistics(self, days: int = 7) -> Dict[str, Any]:
        """오케스트레이터 통계 조회"""
        try:
            conn = sqlite3.connect(self.orchestrator_db)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 기간별 세션 통계
            cursor.execute('''
                SELECT 
                    status,
                    COUNT(*) as count,
                    AVG(total_attempts) as avg_attempts
                FROM recovery_sessions 
                WHERE start_time >= ?
                GROUP BY status
            ''', (cutoff_date,))
            
            session_breakdown = []
            for row in cursor.fetchall():
                session_breakdown.append({
                    'status': row[0],
                    'count': row[1],
                    'avg_attempts': round(row[2], 2) if row[2] else 0
                })
            
            # 에스컬레이션 통계
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_escalations,
                    COUNT(CASE WHEN resolved = 1 THEN 1 END) as resolved_escalations
                FROM escalation_log
                WHERE escalation_time >= ?
            ''', (cutoff_date,))
            
            escalation_stats = cursor.fetchone()
            
            # 컴포넌트별 통계
            cursor.execute('''
                SELECT 
                    component,
                    COUNT(*) as session_count,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as success_count
                FROM recovery_sessions
                WHERE start_time >= ?
                GROUP BY component
                ORDER BY session_count DESC
            ''', (cutoff_date,))
            
            component_stats = []
            for row in cursor.fetchall():
                success_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
                component_stats.append({
                    'component': row[0],
                    'session_count': row[1],
                    'success_count': row[2],
                    'success_rate': round(success_rate, 2)
                })
            
            conn.close()
            
            return {
                'period_days': days,
                'current_stats': self.session_stats.copy(),
                'active_sessions_count': len(self.active_sessions),
                'session_breakdown': session_breakdown,
                'escalations': {
                    'total': escalation_stats[0] if escalation_stats else 0,
                    'resolved': escalation_stats[1] if escalation_stats else 0
                },
                'component_stats': component_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get orchestrator statistics: {e}")
            return {'error': str(e)}
    
    def cancel_session(self, session_id: str, reason: str = "Manually cancelled") -> bool:
        """세션 취소"""
        try:
            with self._lock:
                session = self.active_sessions.get(session_id)
                if session:
                    session.status = RecoveryStatus.CANCELLED
                    session.escalation_reason = reason
                    session.end_time = datetime.now()
                    
                    del self.active_sessions[session_id]
                    self._save_session(session)
                    
                    logger.info(f"Recovery session cancelled: {session_id} - {reason}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel session: {e}")
            return False


# 전역 복구 오케스트레이터 인스턴스
_recovery_orchestrator = None


def get_recovery_orchestrator() -> RecoveryOrchestrator:
    """싱글톤 복구 오케스트레이터 반환"""
    global _recovery_orchestrator
    if _recovery_orchestrator is None:
        _recovery_orchestrator = RecoveryOrchestrator()
    return _recovery_orchestrator