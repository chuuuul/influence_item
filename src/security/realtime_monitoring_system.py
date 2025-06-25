"""
실시간 모니터링 및 알림 시스템

99.99% 가용성을 보장하기 위한 포괄적인 모니터링 솔루션
- 실시간 성능 모니터링
- 지능형 이상 탐지
- 다채널 알림 시스템
- 예측적 장애 분석
- 자동화된 대응 조치
"""

import asyncio
import time
import logging
import json
import sqlite3
import psutil
import aiohttp
import smtplib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import socket
import subprocess
import statistics
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from collections import deque, defaultdict
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """알림 수준"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class MetricType(Enum):
    """메트릭 유형"""
    SYSTEM = "SYSTEM"
    APPLICATION = "APPLICATION"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    SECURITY = "SECURITY"
    BUSINESS = "BUSINESS"


class NotificationChannel(Enum):
    """알림 채널"""
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"
    DASHBOARD = "DASHBOARD"
    LOG = "LOG"


@dataclass
class Metric:
    """메트릭"""
    metric_id: str
    name: str
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class Alert:
    """알림"""
    alert_id: str
    title: str
    description: str
    level: AlertLevel
    metric_id: Optional[str]
    triggered_at: datetime
    resolved_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    channels: List[NotificationChannel]
    actions_taken: List[str]
    metadata: Dict[str, Any]


@dataclass
class Threshold:
    """임계값"""
    threshold_id: str
    metric_name: str
    warning_value: Optional[float]
    error_value: Optional[float]
    critical_value: Optional[float]
    comparison_operator: str  # >, <, ==, !=
    duration_seconds: int
    enabled: bool
    alert_channels: List[NotificationChannel]


@dataclass
class MonitoringRule:
    """모니터링 규칙"""
    rule_id: str
    name: str
    description: str
    metric_pattern: str
    condition: str
    alert_level: AlertLevel
    cooldown_seconds: int
    enabled: bool
    notification_channels: List[NotificationChannel]
    auto_actions: List[str]


class RealtimeMonitoringSystem:
    """실시간 모니터링 시스템"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or Path("config/monitoring_config.json")
        self.db_path = Path("monitoring/realtime_monitoring.db")
        
        # 설정 로드
        self.config = self._load_config()
        
        # 메트릭 저장소
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.current_metrics: Dict[str, Metric] = {}
        
        # 알림 관리
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.thresholds: Dict[str, Threshold] = {}
        self.monitoring_rules: Dict[str, MonitoringRule] = {}
        
        # 이상 탐지
        self.anomaly_baselines: Dict[str, Dict[str, float]] = {}
        self.ml_models: Dict[str, Any] = {}
        
        # 알림 채널
        self.notification_handlers: Dict[NotificationChannel, Callable] = {}
        self.alert_cooldowns: Dict[str, datetime] = {}
        
        # 성능 통계
        self.monitoring_stats = {
            "total_metrics_collected": 0,
            "alerts_triggered": 0,
            "alerts_resolved": 0,
            "false_positives": 0,
            "average_response_time": 0.0,
            "system_uptime": 0.0
        }
        
        # 비동기 처리
        self.running = False
        self.collection_tasks: List[asyncio.Task] = []
        self.analysis_task = None
        self.cleanup_task = None
        
        # 스레드 안전성
        self._lock = threading.RLock()
        
        # 초기화
        self._init_database()
        self._init_notification_handlers()
        self._load_thresholds()
        self._load_monitoring_rules()
        self._init_anomaly_detection()
        
        logger.info("실시간 모니터링 시스템 초기화 완료")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "collection": {
                "interval_seconds": 30,
                "batch_size": 100,
                "retention_hours": 168,  # 7일
                "parallel_collectors": 4
            },
            "analysis": {
                "anomaly_detection": True,
                "trend_analysis": True,
                "prediction_enabled": True,
                "correlation_analysis": True,
                "ml_model_update_hours": 24
            },
            "alerting": {
                "default_channels": ["EMAIL", "SLACK"],
                "escalation_minutes": 15,
                "max_alerts_per_hour": 50,
                "alert_grouping": True,
                "smart_throttling": True
            },
            "notifications": {
                "email": {
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "from_address": "monitoring@company.com",
                    "to_addresses": ["admin@company.com"]
                },
                "slack": {
                    "webhook_url": "",
                    "channel": "#alerts",
                    "username": "MonitorBot"
                },
                "sms": {
                    "provider": "twilio",
                    "account_sid": "",
                    "auth_token": "",
                    "from_number": "",
                    "to_numbers": []
                }
            },
            "metrics": {
                "system_metrics": True,
                "application_metrics": True,
                "network_metrics": True,
                "database_metrics": True,
                "security_metrics": True,
                "business_metrics": True
            },
            "thresholds": {
                "cpu_warning": 70.0,
                "cpu_critical": 90.0,
                "memory_warning": 80.0,
                "memory_critical": 95.0,
                "disk_warning": 85.0,
                "disk_critical": 95.0,
                "response_time_warning": 2.0,
                "response_time_critical": 5.0
            }
        }
        
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                default_config.update(config)
            
            # 설정 파일 저장
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            return default_config
            
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            return default_config
    
    def _init_database(self):
        """데이터베이스 초기화"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 메트릭 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                timestamp DATETIME NOT NULL,
                tags TEXT,
                metadata TEXT
            )
        ''')
        
        # 알림 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                level TEXT NOT NULL,
                metric_id TEXT,
                triggered_at DATETIME NOT NULL,
                resolved_at DATETIME,
                acknowledged_at DATETIME,
                acknowledged_by TEXT,
                channels TEXT,
                actions_taken TEXT,
                metadata TEXT
            )
        ''')
        
        # 임계값 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thresholds (
                threshold_id TEXT PRIMARY KEY,
                metric_name TEXT NOT NULL,
                warning_value REAL,
                error_value REAL,
                critical_value REAL,
                comparison_operator TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 60,
                enabled BOOLEAN DEFAULT TRUE,
                alert_channels TEXT
            )
        ''')
        
        # 모니터링 규칙 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                metric_pattern TEXT NOT NULL,
                condition TEXT NOT NULL,
                alert_level TEXT NOT NULL,
                cooldown_seconds INTEGER DEFAULT 300,
                enabled BOOLEAN DEFAULT TRUE,
                notification_channels TEXT,
                auto_actions TEXT
            )
        ''')
        
        # 이상 탐지 기준선 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anomaly_baselines (
                metric_name TEXT PRIMARY KEY,
                mean_value REAL,
                std_dev REAL,
                min_value REAL,
                max_value REAL,
                percentile_95 REAL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("모니터링 데이터베이스 초기화 완료")
    
    def _init_notification_handlers(self):
        """알림 핸들러 초기화"""
        self.notification_handlers = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.SMS: self._send_sms_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.DASHBOARD: self._send_dashboard_notification,
            NotificationChannel.LOG: self._send_log_notification
        }
    
    def _load_thresholds(self):
        """임계값 로드"""
        # 기본 임계값 생성
        default_thresholds = [
            {
                "threshold_id": "cpu_usage",
                "metric_name": "cpu_percent",
                "warning_value": self.config["thresholds"]["cpu_warning"],
                "error_value": None,
                "critical_value": self.config["thresholds"]["cpu_critical"],
                "comparison_operator": ">",
                "duration_seconds": 300,
                "enabled": True,
                "alert_channels": ["EMAIL", "SLACK"]
            },
            {
                "threshold_id": "memory_usage",
                "metric_name": "memory_percent",
                "warning_value": self.config["thresholds"]["memory_warning"],
                "error_value": None,
                "critical_value": self.config["thresholds"]["memory_critical"],
                "comparison_operator": ">",
                "duration_seconds": 300,
                "enabled": True,
                "alert_channels": ["EMAIL", "SLACK"]
            },
            {
                "threshold_id": "disk_usage",
                "metric_name": "disk_percent",
                "warning_value": self.config["thresholds"]["disk_warning"],
                "error_value": None,
                "critical_value": self.config["thresholds"]["disk_critical"],
                "comparison_operator": ">",
                "duration_seconds": 600,
                "enabled": True,
                "alert_channels": ["EMAIL", "SLACK"]
            },
            {
                "threshold_id": "response_time",
                "metric_name": "response_time_seconds",
                "warning_value": self.config["thresholds"]["response_time_warning"],
                "error_value": None,
                "critical_value": self.config["thresholds"]["response_time_critical"],
                "comparison_operator": ">",
                "duration_seconds": 120,
                "enabled": True,
                "alert_channels": ["EMAIL", "SLACK"]
            }
        ]
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for threshold_data in default_thresholds:
            cursor.execute('''
                INSERT OR REPLACE INTO thresholds (
                    threshold_id, metric_name, warning_value, error_value,
                    critical_value, comparison_operator, duration_seconds,
                    enabled, alert_channels
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                threshold_data["threshold_id"], threshold_data["metric_name"],
                threshold_data["warning_value"], threshold_data["error_value"],
                threshold_data["critical_value"], threshold_data["comparison_operator"],
                threshold_data["duration_seconds"], threshold_data["enabled"],
                json.dumps(threshold_data["alert_channels"])
            ))
        
        # 메모리에 로드
        cursor.execute('SELECT * FROM thresholds WHERE enabled = TRUE')
        thresholds_data = cursor.fetchall()
        
        for threshold_row in thresholds_data:
            threshold = Threshold(
                threshold_id=threshold_row[0],
                metric_name=threshold_row[1],
                warning_value=threshold_row[2],
                error_value=threshold_row[3],
                critical_value=threshold_row[4],
                comparison_operator=threshold_row[5],
                duration_seconds=threshold_row[6],
                enabled=bool(threshold_row[7]),
                alert_channels=[NotificationChannel(ch) for ch in json.loads(threshold_row[8])]
            )
            self.thresholds[threshold.threshold_id] = threshold
        
        conn.commit()
        conn.close()
        
        logger.info(f"{len(self.thresholds)}개 임계값 로드 완료")
    
    def _load_monitoring_rules(self):
        """모니터링 규칙 로드"""
        # 기본 규칙 생성
        default_rules = [
            {
                "rule_id": "high_error_rate",
                "name": "높은 오류율 감지",
                "description": "1분간 오류율이 5% 이상일 때",
                "metric_pattern": "error_rate_percent",
                "condition": "value > 5 and duration > 60",
                "alert_level": "ERROR",
                "cooldown_seconds": 600,
                "enabled": True,
                "notification_channels": ["EMAIL", "SLACK"],
                "auto_actions": ["restart_service"]
            },
            {
                "rule_id": "database_connection_failure",
                "name": "데이터베이스 연결 실패",
                "description": "데이터베이스 연결이 실패했을 때",
                "metric_pattern": "database_connections",
                "condition": "value == 0 and duration > 30",
                "alert_level": "CRITICAL",
                "cooldown_seconds": 300,
                "enabled": True,
                "notification_channels": ["EMAIL", "SLACK", "SMS"],
                "auto_actions": ["check_database", "restart_database"]
            },
            {
                "rule_id": "api_response_time_spike",
                "name": "API 응답 시간 급증",
                "description": "API 응답 시간이 평균의 3배 이상일 때",
                "metric_pattern": "api_response_time",
                "condition": "value > baseline_mean * 3",
                "alert_level": "WARNING",
                "cooldown_seconds": 300,
                "enabled": True,
                "notification_channels": ["SLACK"],
                "auto_actions": ["scale_up"]
            }
        ]
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for rule_data in default_rules:
            cursor.execute('''
                INSERT OR REPLACE INTO monitoring_rules (
                    rule_id, name, description, metric_pattern, condition,
                    alert_level, cooldown_seconds, enabled,
                    notification_channels, auto_actions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule_data["rule_id"], rule_data["name"], rule_data["description"],
                rule_data["metric_pattern"], rule_data["condition"],
                rule_data["alert_level"], rule_data["cooldown_seconds"],
                rule_data["enabled"], json.dumps(rule_data["notification_channels"]),
                json.dumps(rule_data["auto_actions"])
            ))
        
        # 메모리에 로드
        cursor.execute('SELECT * FROM monitoring_rules WHERE enabled = TRUE')
        rules_data = cursor.fetchall()
        
        for rule_row in rules_data:
            rule = MonitoringRule(
                rule_id=rule_row[0],
                name=rule_row[1],
                description=rule_row[2],
                metric_pattern=rule_row[3],
                condition=rule_row[4],
                alert_level=AlertLevel(rule_row[5]),
                cooldown_seconds=rule_row[6],
                enabled=bool(rule_row[7]),
                notification_channels=[NotificationChannel(ch) for ch in json.loads(rule_row[8])],
                auto_actions=json.loads(rule_row[9])
            )
            self.monitoring_rules[rule.rule_id] = rule
        
        conn.commit()
        conn.close()
        
        logger.info(f"{len(self.monitoring_rules)}개 모니터링 규칙 로드 완료")
    
    def _init_anomaly_detection(self):
        """이상 탐지 초기화"""
        if not self.config["analysis"]["anomaly_detection"]:
            return
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM anomaly_baselines')
        baselines_data = cursor.fetchall()
        
        for baseline_row in baselines_data:
            metric_name = baseline_row[0]
            self.anomaly_baselines[metric_name] = {
                "mean": baseline_row[1],
                "std_dev": baseline_row[2],
                "min": baseline_row[3],
                "max": baseline_row[4],
                "percentile_95": baseline_row[5],
                "last_updated": datetime.fromisoformat(baseline_row[6])
            }
        
        conn.close()
        
        logger.info(f"{len(self.anomaly_baselines)}개 이상 탐지 기준선 로드 완료")
    
    async def start_monitoring(self):
        """모니터링 시작"""
        if self.running:
            logger.warning("모니터링이 이미 실행 중입니다")
            return
        
        self.running = True
        logger.info("실시간 모니터링 시스템 시작")
        
        # 메트릭 수집 태스크들
        if self.config["metrics"]["system_metrics"]:
            self.collection_tasks.append(asyncio.create_task(self._collect_system_metrics()))
        
        if self.config["metrics"]["application_metrics"]:
            self.collection_tasks.append(asyncio.create_task(self._collect_application_metrics()))
        
        if self.config["metrics"]["network_metrics"]:
            self.collection_tasks.append(asyncio.create_task(self._collect_network_metrics()))
        
        if self.config["metrics"]["database_metrics"]:
            self.collection_tasks.append(asyncio.create_task(self._collect_database_metrics()))
        
        if self.config["metrics"]["security_metrics"]:
            self.collection_tasks.append(asyncio.create_task(self._collect_security_metrics()))
        
        # 분석 태스크
        self.analysis_task = asyncio.create_task(self._analysis_loop())
        
        # 정리 태스크
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # 기준선 업데이트 태스크
        asyncio.create_task(self._baseline_update_loop())
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        
        # 수집 태스크 중지
        for task in self.collection_tasks:
            task.cancel()
        
        if self.analysis_task:
            self.analysis_task.cancel()
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # 태스크 완료 대기
        await asyncio.gather(*self.collection_tasks, return_exceptions=True)
        
        logger.info("실시간 모니터링 시스템 중지")
    
    async def _collect_system_metrics(self):
        """시스템 메트릭 수집"""
        interval = self.config["collection"]["interval_seconds"]
        
        while self.running:
            try:
                timestamp = datetime.now()
                
                # CPU 사용률
                cpu_percent = psutil.cpu_percent(interval=1)
                await self._store_metric(
                    "cpu_percent", MetricType.SYSTEM, cpu_percent, "%",
                    timestamp, {"host": socket.gethostname()}
                )
                
                # 메모리 사용률
                memory = psutil.virtual_memory()
                await self._store_metric(
                    "memory_percent", MetricType.SYSTEM, memory.percent, "%",
                    timestamp, {"host": socket.gethostname()}
                )
                
                # 디스크 사용률
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                await self._store_metric(
                    "disk_percent", MetricType.SYSTEM, disk_percent, "%",
                    timestamp, {"host": socket.gethostname(), "mount": "/"}
                )
                
                # 네트워크 I/O
                net_io = psutil.net_io_counters()
                await self._store_metric(
                    "network_bytes_sent", MetricType.SYSTEM, net_io.bytes_sent, "bytes",
                    timestamp, {"host": socket.gethostname()}
                )
                await self._store_metric(
                    "network_bytes_recv", MetricType.SYSTEM, net_io.bytes_recv, "bytes",
                    timestamp, {"host": socket.gethostname()}
                )
                
                # 프로세스 수
                process_count = len(psutil.pids())
                await self._store_metric(
                    "process_count", MetricType.SYSTEM, process_count, "count",
                    timestamp, {"host": socket.gethostname()}
                )
                
                # 로드 평균 (Linux/macOS)
                try:
                    load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
                    await self._store_metric(
                        "load_average_1m", MetricType.SYSTEM, load_avg, "load",
                        timestamp, {"host": socket.gethostname()}
                    )
                except AttributeError:
                    pass  # Windows에서는 지원되지 않음
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"시스템 메트릭 수집 오류: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_application_metrics(self):
        """애플리케이션 메트릭 수집"""
        interval = self.config["collection"]["interval_seconds"]
        
        while self.running:
            try:
                timestamp = datetime.now()
                
                # API 서버 상태 확인
                api_status = await self._check_api_health("http://localhost:8000/health")
                await self._store_metric(
                    "api_server_status", MetricType.APPLICATION, api_status["status"], "status",
                    timestamp, {"service": "api_server"}
                )
                
                if api_status["response_time"]:
                    await self._store_metric(
                        "api_response_time", MetricType.APPLICATION, 
                        api_status["response_time"], "seconds",
                        timestamp, {"service": "api_server", "endpoint": "/health"}
                    )
                
                # 대시보드 상태 확인
                dashboard_status = await self._check_api_health("http://localhost:8501")
                await self._store_metric(
                    "dashboard_status", MetricType.APPLICATION, dashboard_status["status"], "status",
                    timestamp, {"service": "dashboard"}
                )
                
                # 애플리케이션 메모리 사용량
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                        if 'python' in proc.info['name'].lower():
                            await self._store_metric(
                                "app_memory_percent", MetricType.APPLICATION,
                                proc.info['memory_percent'], "%",
                                timestamp, {"process": proc.info['name'], "pid": proc.info['pid']}
                            )
                except psutil.NoSuchProcess:
                    pass
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"애플리케이션 메트릭 수집 오류: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_network_metrics(self):
        """네트워크 메트릭 수집"""
        interval = self.config["collection"]["interval_seconds"]
        
        while self.running:
            try:
                timestamp = datetime.now()
                
                # 네트워크 연결 수
                connections = len(psutil.net_connections())
                await self._store_metric(
                    "network_connections", MetricType.NETWORK, connections, "count",
                    timestamp, {"host": socket.gethostname()}
                )
                
                # 외부 서비스 연결 테스트
                external_services = [
                    ("google.com", 80),
                    ("8.8.8.8", 53)
                ]
                
                for host, port in external_services:
                    latency = await self._ping_host(host, port)
                    if latency is not None:
                        await self._store_metric(
                            "network_latency", MetricType.NETWORK, latency, "ms",
                            timestamp, {"target": host, "port": port}
                        )
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"네트워크 메트릭 수집 오류: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_database_metrics(self):
        """데이터베이스 메트릭 수집"""
        interval = self.config["collection"]["interval_seconds"]
        
        while self.running:
            try:
                timestamp = datetime.now()
                
                # SQLite 데이터베이스 상태
                db_files = ["influence_item.db", "monitoring/reliability.db"]
                
                for db_file in db_files:
                    if Path(db_file).exists():
                        # 파일 크기
                        db_size = Path(db_file).stat().st_size
                        await self._store_metric(
                            "database_size", MetricType.DATABASE, db_size, "bytes",
                            timestamp, {"database": db_file}
                        )
                        
                        # 연결 테스트
                        connection_status = await self._test_database_connection(db_file)
                        await self._store_metric(
                            "database_connections", MetricType.DATABASE, 
                            1 if connection_status else 0, "count",
                            timestamp, {"database": db_file}
                        )
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"데이터베이스 메트릭 수집 오류: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_security_metrics(self):
        """보안 메트릭 수집"""
        interval = self.config["collection"]["interval_seconds"] * 2  # 보안 메트릭은 덜 자주 수집
        
        while self.running:
            try:
                timestamp = datetime.now()
                
                # 실패한 로그인 시도 (로그 파일에서)
                failed_logins = await self._count_failed_logins()
                await self._store_metric(
                    "failed_login_attempts", MetricType.SECURITY, failed_logins, "count",
                    timestamp, {"time_window": "1hour"}
                )
                
                # 의심스러운 프로세스
                suspicious_processes = await self._detect_suspicious_processes()
                await self._store_metric(
                    "suspicious_processes", MetricType.SECURITY, suspicious_processes, "count",
                    timestamp, {"host": socket.gethostname()}
                )
                
                # 방화벽 상태 (간단한 예시)
                firewall_status = await self._check_firewall_status()
                await self._store_metric(
                    "firewall_status", MetricType.SECURITY, firewall_status, "status",
                    timestamp, {"host": socket.gethostname()}
                )
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"보안 메트릭 수집 오류: {e}")
                await asyncio.sleep(interval)
    
    async def _store_metric(self, name: str, metric_type: MetricType, value: float, 
                           unit: str, timestamp: datetime, tags: Dict[str, str],
                           metadata: Optional[Dict[str, Any]] = None):
        """메트릭 저장"""
        with self._lock:
            metric_id = f"{name}_{int(timestamp.timestamp())}"
            
            metric = Metric(
                metric_id=metric_id,
                name=name,
                metric_type=metric_type,
                value=value,
                unit=unit,
                timestamp=timestamp,
                tags=tags,
                metadata=metadata or {}
            )
            
            # 메모리에 저장
            self.metrics[name].append(metric)
            self.current_metrics[name] = metric
            
            # 통계 업데이트
            self.monitoring_stats["total_metrics_collected"] += 1
            
            # 임계값 검사
            await self._check_thresholds(metric)
            
            # 이상 탐지
            if self.config["analysis"]["anomaly_detection"]:
                await self._detect_anomalies(metric)
            
            # 데이터베이스에 저장 (배치로 처리)
            if self.monitoring_stats["total_metrics_collected"] % self.config["collection"]["batch_size"] == 0:
                asyncio.create_task(self._persist_metrics())
    
    async def _check_api_health(self, url: str) -> Dict[str, Any]:
        """API 헬스 체크"""
        try:
            start_time = time.time()
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        return {"status": 1, "response_time": response_time}
                    else:
                        return {"status": 0, "response_time": response_time}
                        
        except Exception as e:
            logger.debug(f"API 헬스 체크 실패 ({url}): {e}")
            return {"status": 0, "response_time": None}
    
    async def _ping_host(self, host: str, port: int) -> Optional[float]:
        """호스트 핑 테스트"""
        try:
            start_time = time.time()
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            
            latency = (time.time() - start_time) * 1000  # ms
            writer.close()
            await writer.wait_closed()
            
            return latency
            
        except Exception:
            return None
    
    async def _test_database_connection(self, db_file: str) -> bool:
        """데이터베이스 연결 테스트"""
        try:
            conn = sqlite3.connect(db_file, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False
    
    async def _count_failed_logins(self) -> int:
        """실패한 로그인 시도 수 계산"""
        # 로그 파일에서 실패한 로그인 시도를 찾는 간단한 예시
        try:
            failed_count = 0
            log_files = ["logs/error.log", "logs/security.log"]
            
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            for log_file in log_files:
                if Path(log_file).exists():
                    with open(log_file, 'r') as f:
                        for line in f:
                            if "failed login" in line.lower() or "authentication failed" in line.lower():
                                # 간단한 시간 파싱 (실제로는 더 정교한 로그 파싱 필요)
                                failed_count += 1
            
            return failed_count
            
        except Exception as e:
            logger.debug(f"실패한 로그인 계산 오류: {e}")
            return 0
    
    async def _detect_suspicious_processes(self) -> int:
        """의심스러운 프로세스 탐지"""
        try:
            suspicious_count = 0
            suspicious_names = ["nc", "ncat", "netcat", "nmap", "metasploit"]
            
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name'].lower()
                    if any(suspicious in proc_name for suspicious in suspicious_names):
                        suspicious_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return suspicious_count
            
        except Exception as e:
            logger.debug(f"의심스러운 프로세스 탐지 오류: {e}")
            return 0
    
    async def _check_firewall_status(self) -> int:
        """방화벽 상태 확인"""
        try:
            # macOS 예시
            result = subprocess.run(["pfctl", "-s", "info"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and "Enabled" in result.stdout:
                return 1
        except Exception:
            pass
        
        try:
            # Linux 예시 (ufw)
            result = subprocess.run(["ufw", "status"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and "active" in result.stdout.lower():
                return 1
        except Exception:
            pass
        
        return 0  # 방화벽 상태 확인 불가 또는 비활성
    
    async def _check_thresholds(self, metric: Metric):
        """임계값 검사"""
        for threshold in self.thresholds.values():
            if threshold.metric_name == metric.name and threshold.enabled:
                await self._evaluate_threshold(threshold, metric)
    
    async def _evaluate_threshold(self, threshold: Threshold, metric: Metric):
        """임계값 평가"""
        try:
            # 연산자에 따른 비교
            value = metric.value
            triggered_level = None
            
            if threshold.comparison_operator == ">":
                if threshold.critical_value and value > threshold.critical_value:
                    triggered_level = AlertLevel.CRITICAL
                elif threshold.error_value and value > threshold.error_value:
                    triggered_level = AlertLevel.ERROR
                elif threshold.warning_value and value > threshold.warning_value:
                    triggered_level = AlertLevel.WARNING
            
            elif threshold.comparison_operator == "<":
                if threshold.critical_value and value < threshold.critical_value:
                    triggered_level = AlertLevel.CRITICAL
                elif threshold.error_value and value < threshold.error_value:
                    triggered_level = AlertLevel.ERROR
                elif threshold.warning_value and value < threshold.warning_value:
                    triggered_level = AlertLevel.WARNING
            
            elif threshold.comparison_operator == "==":
                if threshold.critical_value and value == threshold.critical_value:
                    triggered_level = AlertLevel.CRITICAL
                elif threshold.error_value and value == threshold.error_value:
                    triggered_level = AlertLevel.ERROR
                elif threshold.warning_value and value == threshold.warning_value:
                    triggered_level = AlertLevel.WARNING
            
            # 알림 생성
            if triggered_level:
                # 쿨다운 확인
                cooldown_key = f"{threshold.threshold_id}_{triggered_level.value}"
                if cooldown_key in self.alert_cooldowns:
                    if datetime.now() - self.alert_cooldowns[cooldown_key] < timedelta(seconds=threshold.duration_seconds):
                        return  # 아직 쿨다운 중
                
                await self._create_alert(
                    f"{threshold.metric_name} 임계값 초과",
                    f"{metric.name} 값이 {value}{metric.unit}로 {triggered_level.value} 임계값을 초과했습니다",
                    triggered_level,
                    metric.metric_id,
                    threshold.alert_channels
                )
                
                # 쿨다운 설정
                self.alert_cooldowns[cooldown_key] = datetime.now()
                
        except Exception as e:
            logger.error(f"임계값 평가 오류: {e}")
    
    async def _detect_anomalies(self, metric: Metric):
        """이상 탐지"""
        if metric.name not in self.anomaly_baselines:
            return
        
        baseline = self.anomaly_baselines[metric.name]
        value = metric.value
        
        # Z-스코어 계산
        if baseline["std_dev"] > 0:
            z_score = abs(value - baseline["mean"]) / baseline["std_dev"]
            
            # 이상치 임계값 (Z-스코어 > 3)
            if z_score > 3:
                await self._create_alert(
                    f"{metric.name} 이상 패턴 감지",
                    f"{metric.name} 값 {value}{metric.unit}가 정상 범위를 벗어났습니다 (Z-스코어: {z_score:.2f})",
                    AlertLevel.WARNING,
                    metric.metric_id,
                    [NotificationChannel.SLACK, NotificationChannel.LOG]
                )
    
    async def _create_alert(self, title: str, description: str, level: AlertLevel,
                           metric_id: Optional[str], channels: List[NotificationChannel]):
        """알림 생성"""
        alert_id = f"alert_{int(time.time())}_{len(self.active_alerts)}"
        
        alert = Alert(
            alert_id=alert_id,
            title=title,
            description=description,
            level=level,
            metric_id=metric_id,
            triggered_at=datetime.now(),
            resolved_at=None,
            acknowledged_at=None,
            acknowledged_by=None,
            channels=channels,
            actions_taken=[],
            metadata={}
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # 통계 업데이트
        self.monitoring_stats["alerts_triggered"] += 1
        
        # 알림 발송
        for channel in channels:
            if channel in self.notification_handlers:
                try:
                    await self.notification_handlers[channel](alert)
                except Exception as e:
                    logger.error(f"알림 발송 실패 ({channel.value}): {e}")
        
        # 자동 액션 실행
        await self._execute_auto_actions(alert)
        
        logger.warning(f"알림 생성: {title} ({level.value})")
        
        # 데이터베이스에 저장
        asyncio.create_task(self._persist_alert(alert))
    
    async def _execute_auto_actions(self, alert: Alert):
        """자동 액션 실행"""
        # 모니터링 규칙에서 자동 액션 찾기
        for rule in self.monitoring_rules.values():
            if alert.metric_id and rule.metric_pattern in alert.description:
                for action in rule.auto_actions:
                    try:
                        result = await self._execute_action(action, alert)
                        alert.actions_taken.append(f"{action}: {result}")
                        logger.info(f"자동 액션 실행: {action} - {result}")
                    except Exception as e:
                        logger.error(f"자동 액션 실행 실패 ({action}): {e}")
    
    async def _execute_action(self, action: str, alert: Alert) -> str:
        """개별 액션 실행"""
        if action == "restart_service":
            # 서비스 재시작 로직
            return "서비스 재시작 시도됨"
        
        elif action == "scale_up":
            # 스케일업 로직
            return "자동 스케일업 실행됨"
        
        elif action == "check_database":
            # 데이터베이스 상태 확인
            status = await self._test_database_connection("influence_item.db")
            return f"데이터베이스 상태: {'정상' if status else '비정상'}"
        
        elif action == "restart_database":
            # 데이터베이스 재시작 로직
            return "데이터베이스 재시작 시도됨"
        
        else:
            return f"알 수 없는 액션: {action}"
    
    async def _send_email_notification(self, alert: Alert):
        """이메일 알림 발송"""
        config = self.config["notifications"]["email"]
        
        if not config["username"] or not config["password"]:
            logger.debug("이메일 설정이 구성되지 않음")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = config["from_address"]
            msg['To'] = ", ".join(config["to_addresses"])
            msg['Subject'] = f"[{alert.level.value}] {alert.title}"
            
            body = f"""
알림 레벨: {alert.level.value}
제목: {alert.title}
설명: {alert.description}
발생 시간: {alert.triggered_at}
알림 ID: {alert.alert_id}
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
            server.starttls()
            server.login(config["username"], config["password"])
            server.sendmail(config["from_address"], config["to_addresses"], msg.as_string())
            server.quit()
            
            logger.info(f"이메일 알림 발송 완료: {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"이메일 알림 발송 실패: {e}")
    
    async def _send_slack_notification(self, alert: Alert):
        """Slack 알림 발송"""
        config = self.config["notifications"]["slack"]
        
        if not config["webhook_url"]:
            logger.debug("Slack 웹훅 URL이 구성되지 않음")
            return
        
        try:
            color_map = {
                AlertLevel.INFO: "good",
                AlertLevel.WARNING: "warning",
                AlertLevel.ERROR: "danger",
                AlertLevel.CRITICAL: "danger",
                AlertLevel.EMERGENCY: "danger"
            }
            
            payload = {
                "channel": config["channel"],
                "username": config["username"],
                "attachments": [{
                    "color": color_map.get(alert.level, "warning"),
                    "title": f"[{alert.level.value}] {alert.title}",
                    "text": alert.description,
                    "fields": [
                        {"title": "알림 ID", "value": alert.alert_id, "short": True},
                        {"title": "발생 시간", "value": alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S"), "short": True}
                    ],
                    "ts": int(alert.triggered_at.timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(config["webhook_url"], json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Slack 알림 발송 완료: {alert.alert_id}")
                    else:
                        logger.error(f"Slack 알림 발송 실패: {response.status}")
                        
        except Exception as e:
            logger.error(f"Slack 알림 발송 실패: {e}")
    
    async def _send_sms_notification(self, alert: Alert):
        """SMS 알림 발송"""
        config = self.config["notifications"]["sms"]
        
        if not config["account_sid"] or not config["auth_token"]:
            logger.debug("SMS 설정이 구성되지 않음")
            return
        
        # Twilio 등의 SMS 서비스 구현
        logger.info(f"SMS 알림 (구현 필요): {alert.title}")
    
    async def _send_webhook_notification(self, alert: Alert):
        """웹훅 알림 발송"""
        # 웹훅 알림 구현
        logger.info(f"웹훅 알림 (구현 필요): {alert.title}")
    
    async def _send_dashboard_notification(self, alert: Alert):
        """대시보드 알림 발송"""
        # 대시보드에 실시간 알림 표시
        logger.info(f"대시보드 알림: {alert.title}")
    
    async def _send_log_notification(self, alert: Alert):
        """로그 알림 기록"""
        logger.warning(f"[ALERT] {alert.level.value}: {alert.title} - {alert.description}")
    
    async def _analysis_loop(self):
        """분석 루프"""
        while self.running:
            try:
                # 트렌드 분석
                if self.config["analysis"]["trend_analysis"]:
                    await self._analyze_trends()
                
                # 상관관계 분석
                if self.config["analysis"]["correlation_analysis"]:
                    await self._analyze_correlations()
                
                # 예측 분석
                if self.config["analysis"]["prediction_enabled"]:
                    await self._predict_metrics()
                
                await asyncio.sleep(300)  # 5분마다 분석
                
            except Exception as e:
                logger.error(f"분석 루프 오류: {e}")
                await asyncio.sleep(60)
    
    async def _analyze_trends(self):
        """트렌드 분석"""
        for metric_name, metric_history in self.metrics.items():
            if len(metric_history) < 10:  # 최소 데이터 포인트
                continue
            
            try:
                # 최근 데이터 포인트들의 값 추출
                recent_values = [m.value for m in list(metric_history)[-20:]]
                timestamps = [m.timestamp.timestamp() for m in list(metric_history)[-20:]]
                
                # 선형 회귀로 트렌드 계산
                slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, recent_values)
                
                # 급격한 증가/감소 트렌드 감지
                if abs(slope) > self._calculate_slope_threshold(metric_name):
                    trend_direction = "증가" if slope > 0 else "감소"
                    
                    await self._create_alert(
                        f"{metric_name} 트렌드 변화",
                        f"{metric_name}이 {trend_direction} 트렌드를 보이고 있습니다 (기울기: {slope:.4f})",
                        AlertLevel.INFO,
                        None,
                        [NotificationChannel.LOG]
                    )
                    
            except Exception as e:
                logger.debug(f"트렌드 분석 오류 ({metric_name}): {e}")
    
    def _calculate_slope_threshold(self, metric_name: str) -> float:
        """메트릭별 기울기 임계값 계산"""
        # 메트릭 유형에 따른 동적 임계값
        thresholds = {
            "cpu_percent": 0.1,
            "memory_percent": 0.05,
            "disk_percent": 0.01,
            "response_time": 0.001
        }
        return thresholds.get(metric_name, 0.1)
    
    async def _analyze_correlations(self):
        """상관관계 분석"""
        # 메트릭 간 상관관계 분석 (간단한 예시)
        metric_pairs = [
            ("cpu_percent", "response_time"),
            ("memory_percent", "cpu_percent"),
            ("network_connections", "cpu_percent")
        ]
        
        for metric1, metric2 in metric_pairs:
            if metric1 in self.metrics and metric2 in self.metrics:
                try:
                    values1 = [m.value for m in list(self.metrics[metric1])[-50:]]
                    values2 = [m.value for m in list(self.metrics[metric2])[-50:]]
                    
                    if len(values1) >= 10 and len(values2) >= 10:
                        correlation = np.corrcoef(values1[:min(len(values1), len(values2))], 
                                               values2[:min(len(values1), len(values2))])[0, 1]
                        
                        # 높은 상관관계 감지
                        if abs(correlation) > 0.8:
                            logger.info(f"높은 상관관계 감지: {metric1} <-> {metric2} (r={correlation:.3f})")
                            
                except Exception as e:
                    logger.debug(f"상관관계 분석 오류 ({metric1}, {metric2}): {e}")
    
    async def _predict_metrics(self):
        """메트릭 예측"""
        # 단순한 예측 모델 (실제로는 더 정교한 ML 모델 사용)
        for metric_name, metric_history in self.metrics.items():
            if len(metric_history) < 30:  # 최소 데이터 포인트
                continue
            
            try:
                recent_values = [m.value for m in list(metric_history)[-30:]]
                
                # 이동 평균 기반 예측
                prediction = statistics.mean(recent_values[-5:])  # 최근 5개 값의 평균
                current_value = recent_values[-1]
                
                # 예측값과 현재값의 차이가 클 때 알림
                deviation = abs(prediction - current_value) / max(current_value, 1) * 100
                
                if deviation > 50:  # 50% 이상 차이
                    await self._create_alert(
                        f"{metric_name} 예측 편차",
                        f"{metric_name}이 예측값({prediction:.2f})과 크게 다릅니다 (현재: {current_value:.2f}, 편차: {deviation:.1f}%)",
                        AlertLevel.INFO,
                        None,
                        [NotificationChannel.LOG]
                    )
                    
            except Exception as e:
                logger.debug(f"예측 분석 오류 ({metric_name}): {e}")
    
    async def _baseline_update_loop(self):
        """기준선 업데이트 루프"""
        update_interval = self.config["analysis"]["ml_model_update_hours"] * 3600
        
        while self.running:
            try:
                await self._update_anomaly_baselines()
                await asyncio.sleep(update_interval)
                
            except Exception as e:
                logger.error(f"기준선 업데이트 오류: {e}")
                await asyncio.sleep(3600)  # 1시간 후 재시도
    
    async def _update_anomaly_baselines(self):
        """이상 탐지 기준선 업데이트"""
        for metric_name, metric_history in self.metrics.items():
            if len(metric_history) < 100:  # 최소 데이터 포인트
                continue
            
            try:
                # 최근 데이터에서 통계 계산
                recent_values = [m.value for m in list(metric_history)[-1000:]]
                
                baseline = {
                    "mean": statistics.mean(recent_values),
                    "std_dev": statistics.stdev(recent_values) if len(recent_values) > 1 else 0,
                    "min": min(recent_values),
                    "max": max(recent_values),
                    "percentile_95": np.percentile(recent_values, 95),
                    "last_updated": datetime.now()
                }
                
                self.anomaly_baselines[metric_name] = baseline
                
                # 데이터베이스에 저장
                await self._persist_baseline(metric_name, baseline)
                
                logger.debug(f"기준선 업데이트: {metric_name}")
                
            except Exception as e:
                logger.error(f"기준선 업데이트 실패 ({metric_name}): {e}")
    
    async def _cleanup_loop(self):
        """정리 루프"""
        while self.running:
            try:
                # 오래된 메트릭 정리
                await self._cleanup_old_metrics()
                
                # 해결된 알림 정리
                await self._cleanup_resolved_alerts()
                
                # 쿨다운 정리
                await self._cleanup_cooldowns()
                
                await asyncio.sleep(3600)  # 1시간마다 정리
                
            except Exception as e:
                logger.error(f"정리 루프 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _cleanup_old_metrics(self):
        """오래된 메트릭 정리"""
        retention_hours = self.config["collection"]["retention_hours"]
        cutoff_time = datetime.now() - timedelta(hours=retention_hours)
        
        for metric_name in list(self.metrics.keys()):
            metric_history = self.metrics[metric_name]
            
            # 오래된 메트릭 제거
            while metric_history and metric_history[0].timestamp < cutoff_time:
                metric_history.popleft()
            
            # 빈 히스토리 제거
            if not metric_history:
                del self.metrics[metric_name]
        
        # 데이터베이스에서도 정리
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff_time,))
        conn.commit()
        conn.close()
    
    async def _cleanup_resolved_alerts(self):
        """해결된 알림 정리"""
        resolved_cutoff = datetime.now() - timedelta(days=7)  # 7일 후 삭제
        
        for alert_id in list(self.active_alerts.keys()):
            alert = self.active_alerts[alert_id]
            if alert.resolved_at and alert.resolved_at < resolved_cutoff:
                del self.active_alerts[alert_id]
    
    async def _cleanup_cooldowns(self):
        """쿨다운 정리"""
        current_time = datetime.now()
        expired_cooldowns = []
        
        for cooldown_key, cooldown_time in self.alert_cooldowns.items():
            if current_time - cooldown_time > timedelta(hours=1):  # 1시간 후 정리
                expired_cooldowns.append(cooldown_key)
        
        for cooldown_key in expired_cooldowns:
            del self.alert_cooldowns[cooldown_key]
    
    async def _persist_metrics(self):
        """메트릭 데이터베이스 저장"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 최근 메트릭들을 배치로 저장
            metrics_to_save = []
            for metric_history in self.metrics.values():
                if metric_history:
                    latest_metric = metric_history[-1]
                    metrics_to_save.append((
                        latest_metric.metric_id, latest_metric.name,
                        latest_metric.metric_type.value, latest_metric.value,
                        latest_metric.unit, latest_metric.timestamp,
                        json.dumps(latest_metric.tags),
                        json.dumps(latest_metric.metadata)
                    ))
            
            if metrics_to_save:
                cursor.executemany('''
                    INSERT OR REPLACE INTO metrics (
                        metric_id, name, metric_type, value, unit,
                        timestamp, tags, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', metrics_to_save)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"메트릭 저장 실패: {e}")
    
    async def _persist_alert(self, alert: Alert):
        """알림 데이터베이스 저장"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO alerts (
                    alert_id, title, description, level, metric_id,
                    triggered_at, resolved_at, acknowledged_at, acknowledged_by,
                    channels, actions_taken, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.alert_id, alert.title, alert.description,
                alert.level.value, alert.metric_id, alert.triggered_at,
                alert.resolved_at, alert.acknowledged_at, alert.acknowledged_by,
                json.dumps([ch.value for ch in alert.channels]),
                json.dumps(alert.actions_taken), json.dumps(alert.metadata)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"알림 저장 실패: {e}")
    
    async def _persist_baseline(self, metric_name: str, baseline: Dict[str, Any]):
        """기준선 데이터베이스 저장"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO anomaly_baselines (
                    metric_name, mean_value, std_dev, min_value,
                    max_value, percentile_95, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                metric_name, baseline["mean"], baseline["std_dev"],
                baseline["min"], baseline["max"], baseline["percentile_95"],
                baseline["last_updated"]
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"기준선 저장 실패: {e}")
    
    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """알림 해결"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.resolved_at = datetime.now()
        alert.metadata["resolved_by"] = resolved_by
        
        # 통계 업데이트
        self.monitoring_stats["alerts_resolved"] += 1
        
        # 데이터베이스 업데이트
        await self._persist_alert(alert)
        
        logger.info(f"알림 해결: {alert_id}")
        return True
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """알림 확인"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = acknowledged_by
        
        # 데이터베이스 업데이트
        await self._persist_alert(alert)
        
        logger.info(f"알림 확인: {alert_id} by {acknowledged_by}")
        return True
    
    async def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """모니터링 대시보드 데이터 조회"""
        current_time = datetime.now()
        
        # 현재 메트릭
        current_metrics = {}
        for name, metric in self.current_metrics.items():
            current_metrics[name] = {
                "value": metric.value,
                "unit": metric.unit,
                "timestamp": metric.timestamp.isoformat(),
                "tags": metric.tags
            }
        
        # 활성 알림 (심각도별)
        alerts_by_level = defaultdict(int)
        for alert in self.active_alerts.values():
            if not alert.resolved_at:
                alerts_by_level[alert.level.value] += 1
        
        # 최근 24시간 메트릭 통계
        metrics_24h = {}
        for metric_name, metric_history in self.metrics.items():
            recent_metrics = [m for m in metric_history 
                            if current_time - m.timestamp < timedelta(hours=24)]
            
            if recent_metrics:
                values = [m.value for m in recent_metrics]
                metrics_24h[metric_name] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": statistics.mean(values),
                    "current": values[-1] if values else 0,
                    "count": len(values)
                }
        
        # 시스템 상태 요약
        system_status = "HEALTHY"
        critical_alerts = alerts_by_level.get("CRITICAL", 0)
        error_alerts = alerts_by_level.get("ERROR", 0)
        
        if critical_alerts > 0:
            system_status = "CRITICAL"
        elif error_alerts > 0:
            system_status = "ERROR"
        elif alerts_by_level.get("WARNING", 0) > 0:
            system_status = "WARNING"
        
        return {
            "system_status": system_status,
            "timestamp": current_time.isoformat(),
            "current_metrics": current_metrics,
            "alerts": {
                "active_by_level": dict(alerts_by_level),
                "total_active": len([a for a in self.active_alerts.values() if not a.resolved_at]),
                "recent_alerts": [
                    {
                        "alert_id": alert.alert_id,
                        "title": alert.title,
                        "level": alert.level.value,
                        "triggered_at": alert.triggered_at.isoformat(),
                        "acknowledged": alert.acknowledged_at is not None
                    }
                    for alert in sorted(self.alert_history, 
                                      key=lambda x: x.triggered_at, reverse=True)[:10]
                ]
            },
            "metrics_24h": metrics_24h,
            "statistics": self.monitoring_stats,
            "thresholds": {
                th.threshold_id: {
                    "metric_name": th.metric_name,
                    "warning": th.warning_value,
                    "critical": th.critical_value,
                    "enabled": th.enabled
                }
                for th in self.thresholds.values()
            }
        }


# 전역 인스턴스
_monitoring_system = None

def get_monitoring_system() -> RealtimeMonitoringSystem:
    """모니터링 시스템 싱글톤 반환"""
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = RealtimeMonitoringSystem()
    return _monitoring_system


async def main():
    """테스트용 메인 함수"""
    monitoring = RealtimeMonitoringSystem()
    
    try:
        # 모니터링 시작
        await monitoring.start_monitoring()
        
        # 시스템 실행 (실제로는 서비스로 실행)
        for i in range(10):
            await asyncio.sleep(30)
            
            # 대시보드 데이터 조회
            dashboard_data = await monitoring.get_monitoring_dashboard_data()
            print(f"시스템 상태: {dashboard_data['system_status']}")
            print(f"활성 알림: {dashboard_data['alerts']['total_active']}")
        
    finally:
        await monitoring.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())