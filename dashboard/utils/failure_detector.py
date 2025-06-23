"""
T04_S03_M03: 장애 감지 및 자동 복구 시스템 - 장애 감지 센서
시스템 장애를 신속하게 감지하는 종합적인 센서 시스템
"""

import time
import asyncio
import threading
import requests
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# 기존 모듈 임포트
from dashboard.utils.error_handler import ErrorHandler, get_error_handler
from dashboard.utils.system_monitor import SystemMonitor, get_system_monitor, HealthStatus
from dashboard.utils.database_manager import DatabaseManager
from config.config import Config

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """장애 유형"""
    API_TIMEOUT = "api_timeout"
    API_ERROR = "api_error"
    DATABASE_CONNECTION = "database_connection"
    SERVER_UNRESPONSIVE = "server_unresponsive"
    WORKFLOW_FAILED = "workflow_failed"
    HIGH_ERROR_RATE = "high_error_rate"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    N8N_WORKFLOW_ERROR = "n8n_workflow_error"
    GPU_SERVER_ERROR = "gpu_server_error"
    EXTERNAL_API_ERROR = "external_api_error"


class FailureSeverity(Enum):
    """장애 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FailureEvent:
    """장애 이벤트"""
    failure_type: FailureType
    component: str
    severity: FailureSeverity
    message: str
    timestamp: datetime
    context: Dict[str, Any]
    recovery_attempts: int = 0
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['failure_type'] = self.failure_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.resolution_time:
            data['resolution_time'] = self.resolution_time.isoformat()
        return data


class FailureDetector:
    """장애 감지 시스템"""
    
    def __init__(self, monitoring_db: str = "failure_monitoring.db"):
        """
        Args:
            monitoring_db: 장애 모니터링 데이터베이스 파일
        """
        self.monitoring_db = Path(monitoring_db)
        self.monitoring_db.parent.mkdir(exist_ok=True)
        
        # 모니터링 설정
        self.monitors = {}
        self.failure_queue = asyncio.Queue()
        self.is_monitoring = False
        self.monitor_thread = None
        
        # 임계값 설정
        self.thresholds = {
            'api_timeout_seconds': 30,
            'api_error_rate_percent': 25,
            'database_timeout_seconds': 10,
            'cpu_critical_percent': 90,
            'memory_critical_percent': 90,
            'disk_critical_percent': 95,
            'gpu_memory_critical_percent': 95,
            'consecutive_failures_limit': 3
        }
        
        # 상태 추적
        self.component_states = {}
        self.error_counts = {}
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 시스템 모니터 및 에러 핸들러 연동
        self.system_monitor = get_system_monitor()
        self.error_handler = get_error_handler()
        
        self._lock = threading.Lock()
    
    def _init_database(self):
        """장애 모니터링 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.monitoring_db)
            cursor = conn.cursor()
            
            # 장애 이벤트 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failure_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    failure_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    context TEXT,
                    recovery_attempts INTEGER DEFAULT 0,
                    resolved BOOLEAN DEFAULT 0,
                    resolution_time TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 컴포넌트 상태 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS component_states (
                    component TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_check TEXT NOT NULL,
                    consecutive_failures INTEGER DEFAULT 0,
                    last_failure_time TEXT,
                    total_failures INTEGER DEFAULT 0,
                    uptime_start TEXT
                )
            ''')
            
            # 장애 통계 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failure_statistics (
                    date TEXT PRIMARY KEY,
                    total_failures INTEGER DEFAULT 0,
                    critical_failures INTEGER DEFAULT 0,
                    high_failures INTEGER DEFAULT 0,
                    medium_failures INTEGER DEFAULT 0,
                    low_failures INTEGER DEFAULT 0,
                    resolved_failures INTEGER DEFAULT 0,
                    avg_resolution_time_minutes REAL DEFAULT 0
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Failure monitoring database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize monitoring database: {e}")
            raise
    
    def register_monitor(self, name: str, check_func: Callable, interval: int, enabled: bool = True):
        """
        모니터 등록
        
        Args:
            name: 모니터 이름
            check_func: 헬스체크 함수
            interval: 체크 간격 (초)
            enabled: 활성화 여부
        """
        self.monitors[name] = {
            'check_func': check_func,
            'interval': interval,
            'enabled': enabled,
            'last_check': None,
            'consecutive_failures': 0,
            'last_result': None
        }
        
        logger.info(f"Monitor registered: {name} (interval: {interval}s)")
    
    def start_monitoring(self):
        """모니터링 시작"""
        if self.is_monitoring:
            logger.info("Failure monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        # 기본 모니터들 등록
        self._register_default_monitors()
        
        logger.info("Failure detection monitoring started")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        logger.info("Failure detection monitoring stopped")
    
    def _register_default_monitors(self):
        """기본 모니터들 등록"""
        # API 헬스체크 (로컬 서버)
        self.register_monitor(
            "local_api",
            lambda: self.check_api_health("http://localhost:8501/health"),
            interval=30  # 30초
        )
        
        # 데이터베이스 헬스체크
        self.register_monitor(
            "database",
            self.check_database_health,
            interval=60  # 1분
        )
        
        # 시스템 리소스 체크
        self.register_monitor(
            "system_resources",
            self.check_system_resources,
            interval=120  # 2분
        )
        
        # GPU 서버 헬스체크 (구성되어 있는 경우)
        try:
            config = Config()
            if hasattr(config, 'GPU_SERVER_URL') and config.GPU_SERVER_URL:
                self.register_monitor(
                    "gpu_server",
                    lambda: self.check_api_health(f"{config.GPU_SERVER_URL}/health"),
                    interval=60
                )
        except Exception:
            pass
        
        # n8n 워크플로우 상태 체크
        self.register_monitor(
            "n8n_workflows",
            self.check_n8n_workflows,
            interval=300  # 5분
        )
    
    def _monitoring_loop(self):
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                current_time = time.time()
                
                for monitor_name, monitor_config in list(self.monitors.items()):
                    if not monitor_config['enabled']:
                        continue
                    
                    # 간격 체크
                    last_check = monitor_config['last_check']
                    if last_check and (current_time - last_check) < monitor_config['interval']:
                        continue
                    
                    # 헬스체크 실행
                    try:
                        monitor_config['last_check'] = current_time
                        result = monitor_config['check_func']()
                        
                        # 결과 처리
                        self._process_monitor_result(monitor_name, result, monitor_config)
                        
                    except Exception as e:
                        logger.error(f"Monitor '{monitor_name}' failed: {e}")
                        self._handle_monitor_failure(monitor_name, str(e), monitor_config)
                
                time.sleep(10)  # 10초마다 모니터 상태 체크
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # 에러 발생 시 30초 대기
    
    def _process_monitor_result(self, monitor_name: str, result: Any, monitor_config: Dict):
        """모니터 결과 처리"""
        try:
            is_healthy = self._evaluate_monitor_result(result)
            
            if is_healthy:
                # 성공 - 연속 실패 카운트 리셋
                if monitor_config['consecutive_failures'] > 0:
                    logger.info(f"Monitor '{monitor_name}' recovered")
                    monitor_config['consecutive_failures'] = 0
                    self._update_component_state(monitor_name, "healthy")
                
                monitor_config['last_result'] = result
                
            else:
                # 실패 - 연속 실패 카운트 증가
                monitor_config['consecutive_failures'] += 1
                consecutive_failures = monitor_config['consecutive_failures']
                
                logger.warning(f"Monitor '{monitor_name}' failed ({consecutive_failures} consecutive)")
                
                # 임계값 초과 시 장애 이벤트 생성
                if consecutive_failures >= self.thresholds['consecutive_failures_limit']:
                    self._create_failure_event(
                        failure_type=self._get_failure_type_for_monitor(monitor_name),
                        component=monitor_name,
                        severity=self._get_failure_severity(consecutive_failures),
                        message=f"Monitor failed {consecutive_failures} times consecutively",
                        context={'result': result, 'consecutive_failures': consecutive_failures}
                    )
                    
                    self._update_component_state(monitor_name, "failed")
                
        except Exception as e:
            logger.error(f"Failed to process monitor result for '{monitor_name}': {e}")
    
    def _evaluate_monitor_result(self, result: Any) -> bool:
        """모니터 결과 평가"""
        if isinstance(result, bool):
            return result
        elif isinstance(result, dict):
            return result.get('healthy', False)
        elif hasattr(result, 'status'):
            return result.status in [HealthStatus.HEALTHY, HealthStatus.WARNING]
        else:
            return False
    
    def _get_failure_type_for_monitor(self, monitor_name: str) -> FailureType:
        """모니터에 따른 장애 유형 결정"""
        mapping = {
            'local_api': FailureType.API_ERROR,
            'gpu_server': FailureType.GPU_SERVER_ERROR,
            'database': FailureType.DATABASE_CONNECTION,
            'system_resources': FailureType.RESOURCE_EXHAUSTED,
            'n8n_workflows': FailureType.N8N_WORKFLOW_ERROR
        }
        return mapping.get(monitor_name, FailureType.SERVER_UNRESPONSIVE)
    
    def _get_failure_severity(self, consecutive_failures: int) -> FailureSeverity:
        """연속 실패 횟수에 따른 심각도 결정"""
        if consecutive_failures >= 10:
            return FailureSeverity.CRITICAL
        elif consecutive_failures >= 6:
            return FailureSeverity.HIGH
        elif consecutive_failures >= 3:
            return FailureSeverity.MEDIUM
        else:
            return FailureSeverity.LOW
    
    def _handle_monitor_failure(self, monitor_name: str, error_message: str, monitor_config: Dict):
        """모니터 실패 처리"""
        monitor_config['consecutive_failures'] += 1
        consecutive_failures = monitor_config['consecutive_failures']
        
        if consecutive_failures >= self.thresholds['consecutive_failures_limit']:
            self._create_failure_event(
                failure_type=FailureType.SERVER_UNRESPONSIVE,
                component=monitor_name,
                severity=self._get_failure_severity(consecutive_failures),
                message=f"Monitor execution failed: {error_message}",
                context={'error': error_message, 'consecutive_failures': consecutive_failures}
            )
    
    def _create_failure_event(
        self, 
        failure_type: FailureType,
        component: str,
        severity: FailureSeverity,
        message: str,
        context: Dict[str, Any] = None
    ):
        """장애 이벤트 생성 및 저장"""
        try:
            failure_event = FailureEvent(
                failure_type=failure_type,
                component=component,
                severity=severity,
                message=message,
                timestamp=datetime.now(),
                context=context or {}
            )
            
            # 데이터베이스에 저장
            self._save_failure_event(failure_event)
            
            # 큐에 추가 (복구 시스템에서 처리)
            try:
                asyncio.create_task(self.failure_queue.put(failure_event))
            except RuntimeError:
                # 이벤트 루프가 없는 경우 - 스레드에서 실행 중
                pass
            
            logger.error(f"Failure detected - {component}: {message}")
            
        except Exception as e:
            logger.error(f"Failed to create failure event: {e}")
    
    def _save_failure_event(self, failure_event: FailureEvent):
        """장애 이벤트 데이터베이스 저장"""
        try:
            conn = sqlite3.connect(self.monitoring_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO failure_events 
                (failure_type, component, severity, message, timestamp, context)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                failure_event.failure_type.value,
                failure_event.component,
                failure_event.severity.value,
                failure_event.message,
                failure_event.timestamp.isoformat(),
                json.dumps(failure_event.context, ensure_ascii=False)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save failure event: {e}")
    
    def _update_component_state(self, component: str, status: str):
        """컴포넌트 상태 업데이트"""
        try:
            conn = sqlite3.connect(self.monitoring_db)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT OR REPLACE INTO component_states 
                (component, status, last_check, consecutive_failures, last_failure_time, total_failures, uptime_start)
                VALUES (?, ?, ?, 
                    COALESCE((SELECT consecutive_failures FROM component_states WHERE component = ?), 0),
                    CASE WHEN ? = 'failed' THEN ? ELSE (SELECT last_failure_time FROM component_states WHERE component = ?) END,
                    COALESCE((SELECT total_failures FROM component_states WHERE component = ?), 0) + 
                    CASE WHEN ? = 'failed' THEN 1 ELSE 0 END,
                    COALESCE((SELECT uptime_start FROM component_states WHERE component = ?), ?)
                )
            ''', (component, status, now, component, status, now, component, component, status, component, now))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update component state: {e}")
    
    # 헬스체크 메서드들
    async def check_api_health(self, endpoint: str, timeout: int = 10) -> Dict[str, Any]:
        """API 헬스체크"""
        try:
            start_time = time.time()
            response = requests.get(endpoint, timeout=timeout)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'status_code': response.status_code,
                    'response_time_ms': response_time,
                    'endpoint': endpoint
                }
            else:
                return {
                    'healthy': False,
                    'status_code': response.status_code,
                    'response_time_ms': response_time,
                    'endpoint': endpoint,
                    'error': f"HTTP {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {
                'healthy': False,
                'endpoint': endpoint,
                'error': 'Request timeout',
                'timeout_seconds': timeout
            }
        except Exception as e:
            return {
                'healthy': False,
                'endpoint': endpoint,
                'error': str(e)
            }
    
    def check_database_health(self) -> Dict[str, Any]:
        """데이터베이스 헬스체크"""
        try:
            start_time = time.time()
            
            conn = sqlite3.connect("influence_item.db", timeout=self.thresholds['database_timeout_seconds'])
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # 간단한 쿼리로 응답성 확인
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            
            conn.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'healthy': True,
                'table_count': table_count,
                'response_time_ms': response_time,
                'query_result': result[0] if result else None
            }
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                return {
                    'healthy': False,
                    'error': 'Database locked',
                    'error_type': 'lock_error'
                }
            else:
                return {
                    'healthy': False,
                    'error': str(e),
                    'error_type': 'operational_error'
                }
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'error_type': 'general_error'
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """시스템 리소스 헬스체크"""
        try:
            health_status = self.system_monitor.get_health_status()
            
            critical_components = []
            warning_components = []
            
            for component, health_check in health_status.items():
                if health_check.status == HealthStatus.CRITICAL:
                    critical_components.append(component)
                elif health_check.status == HealthStatus.WARNING:
                    warning_components.append(component)
            
            is_healthy = len(critical_components) == 0
            
            return {
                'healthy': is_healthy,
                'critical_components': critical_components,
                'warning_components': warning_components,
                'total_components_checked': len(health_status),
                'details': {comp: health.message for comp, health in health_status.items()}
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'error_type': 'system_check_error'
            }
    
    def check_n8n_workflows(self) -> Dict[str, Any]:
        """n8n 워크플로우 상태 체크"""
        try:
            # n8n API 엔드포인트 확인 (설정에 따라)
            n8n_url = "http://localhost:5678"  # 기본 n8n 포트
            
            try:
                # n8n 헬스체크
                response = requests.get(f"{n8n_url}/healthz", timeout=10)
                if response.status_code != 200:
                    return {
                        'healthy': False,
                        'error': f"n8n healthcheck failed: HTTP {response.status_code}",
                        'n8n_url': n8n_url
                    }
                
                # 활성 워크플로우 확인 (API 키가 있는 경우)
                # workflows_response = requests.get(f"{n8n_url}/api/v1/workflows", ...)
                
                return {
                    'healthy': True,
                    'n8n_status': 'running',
                    'n8n_url': n8n_url
                }
                
            except requests.exceptions.ConnectionError:
                return {
                    'healthy': False,
                    'error': 'n8n server not reachable',
                    'n8n_url': n8n_url
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'error_type': 'n8n_check_error'
            }
    
    def get_failure_statistics(self, days: int = 7) -> Dict[str, Any]:
        """장애 통계 조회"""
        try:
            conn = sqlite3.connect(self.monitoring_db)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 기간별 장애 건수
            cursor.execute('''
                SELECT 
                    failure_type,
                    severity,
                    COUNT(*) as count,
                    AVG(recovery_attempts) as avg_recovery_attempts
                FROM failure_events 
                WHERE timestamp >= ?
                GROUP BY failure_type, severity
                ORDER BY count DESC
            ''', (cutoff_date,))
            
            failure_breakdown = []
            for row in cursor.fetchall():
                failure_breakdown.append({
                    'failure_type': row[0],
                    'severity': row[1],
                    'count': row[2],
                    'avg_recovery_attempts': round(row[3], 2) if row[3] else 0
                })
            
            # 총 통계
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_failures,
                    COUNT(CASE WHEN resolved = 1 THEN 1 END) as resolved_failures,
                    AVG(CASE WHEN resolved = 1 AND resolution_time IS NOT NULL 
                        THEN (julianday(resolution_time) - julianday(timestamp)) * 24 * 60 END) as avg_resolution_minutes
                FROM failure_events
                WHERE timestamp >= ?
            ''', (cutoff_date,))
            
            total_stats = cursor.fetchone()
            
            # 컴포넌트별 상태
            cursor.execute('SELECT * FROM component_states')
            component_states = []
            for row in cursor.fetchall():
                component_states.append({
                    'component': row[0],
                    'status': row[1],
                    'last_check': row[2],
                    'consecutive_failures': row[3],
                    'total_failures': row[5]
                })
            
            conn.close()
            
            return {
                'period_days': days,
                'total_failures': total_stats[0] if total_stats else 0,
                'resolved_failures': total_stats[1] if total_stats else 0,
                'avg_resolution_minutes': round(total_stats[2], 2) if total_stats and total_stats[2] else 0,
                'failure_breakdown': failure_breakdown,
                'component_states': component_states,
                'active_monitors': len([m for m in self.monitors.values() if m['enabled']])
            }
            
        except Exception as e:
            logger.error(f"Failed to get failure statistics: {e}")
            return {'error': str(e)}


# 전역 장애 감지기 인스턴스
_failure_detector = None


def get_failure_detector() -> FailureDetector:
    """싱글톤 장애 감지기 반환"""
    global _failure_detector
    if _failure_detector is None:
        _failure_detector = FailureDetector()
    return _failure_detector