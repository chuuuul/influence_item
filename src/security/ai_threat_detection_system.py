"""
AI 기반 위협 탐지 시스템

머신러닝과 딥러닝을 활용하여 실시간으로 보안 위협을 탐지하고 차단합니다.
- 실시간 침입 탐지
- 이상 행동 패턴 분석
- 자동 위협 분류 및 대응
- 적응형 보안 학습
"""

import asyncio
import numpy as np
import pandas as pd
import logging
import json
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import ipaddress
import re
import aiohttp
import psutil
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle
import threading
from collections import defaultdict, deque
import geoip2.database
import geoip2.errors

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """위협 수준"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class ThreatType(Enum):
    """위협 유형"""
    BRUTE_FORCE = "BRUTE_FORCE"
    DDoS = "DDoS"
    SQL_INJECTION = "SQL_INJECTION"
    XSS = "XSS"
    MALWARE = "MALWARE"
    PHISHING = "PHISHING"
    INSIDER_THREAT = "INSIDER_THREAT"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    ANOMALOUS_BEHAVIOR = "ANOMALOUS_BEHAVIOR"
    API_ABUSE = "API_ABUSE"
    RECONNAISSANCE = "RECONNAISSANCE"


class ActionType(Enum):
    """대응 액션"""
    MONITOR = "MONITOR"
    ALERT = "ALERT"
    BLOCK_IP = "BLOCK_IP"
    RATE_LIMIT = "RATE_LIMIT"
    QUARANTINE = "QUARANTINE"
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"


@dataclass
class ThreatEvent:
    """위협 이벤트"""
    event_id: str
    timestamp: datetime
    threat_type: ThreatType
    threat_level: ThreatLevel
    source_ip: str
    target: str
    description: str
    evidence: Dict[str, Any]
    confidence_score: float
    risk_score: float
    geo_location: Optional[Dict[str, str]]
    user_agent: Optional[str]
    payload: Optional[str]
    affected_systems: List[str]
    recommended_actions: List[ActionType]
    status: str = "ACTIVE"
    resolved_at: Optional[datetime] = None


@dataclass
class SecurityMetrics:
    """보안 메트릭"""
    total_threats_detected: int
    threats_blocked: int
    false_positives: int
    response_time_avg: float
    threat_accuracy: float
    system_uptime: float
    last_update: datetime


class AIThreatDetectionSystem:
    """AI 기반 위협 탐지 시스템"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or Path("config/threat_detection_config.json")
        self.db_path = Path("security/threat_detection.db")
        self.models_path = Path("security/models")
        
        # 설정 로드
        self.config = self._load_config()
        
        # AI 모델들
        self.anomaly_detector = None
        self.threat_classifier = None
        self.scaler = StandardScaler()
        self.models_loaded = False
        
        # 실시간 데이터 수집
        self.request_patterns = defaultdict(lambda: deque(maxlen=1000))
        self.ip_reputation = {}
        self.threat_indicators = set()
        
        # 지리적 위치 데이터베이스
        self.geoip_reader = None
        
        # 위협 이벤트 저장
        self.active_threats: Dict[str, ThreatEvent] = {}
        self.threat_history = deque(maxlen=10000)
        
        # 메트릭
        self.metrics = SecurityMetrics(
            total_threats_detected=0,
            threats_blocked=0,
            false_positives=0,
            response_time_avg=0.0,
            threat_accuracy=0.0,
            system_uptime=0.0,
            last_update=datetime.now()
        )
        
        # 비동기 처리
        self.running = False
        self.detection_task = None
        self.learning_task = None
        
        # 초기화
        self._init_database()
        self._init_models()
        self._load_threat_intelligence()
        
        logger.info("AI 위협 탐지 시스템 초기화 완료")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "detection": {
                "anomaly_threshold": 0.7,
                "threat_threshold": 0.8,
                "learning_rate": 0.01,
                "update_interval": 300,  # 5분
                "max_false_positive_rate": 0.05
            },
            "monitoring": {
                "api_requests": True,
                "file_system": True,
                "network_traffic": True,
                "user_behavior": True,
                "system_logs": True
            },
            "response": {
                "auto_block_critical": True,
                "auto_quarantine_malware": True,
                "alert_slack": True,
                "alert_email": True,
                "emergency_contact": "admin@example.com"
            },
            "intelligence": {
                "update_threat_feeds": True,
                "threat_feed_urls": [
                    "https://rules.emergingthreats.net/fwrules/emerging-Block-IPs.txt",
                    "https://www.spamhaus.org/drop/drop.txt"
                ],
                "geoip_database": "security/GeoLite2-City.mmdb"
            },
            "machine_learning": {
                "retrain_interval": 86400,  # 24시간
                "feature_importance_threshold": 0.1,
                "model_accuracy_threshold": 0.85,
                "ensemble_voting": True
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
        
        # 위협 이벤트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threat_events (
                event_id TEXT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                threat_type TEXT NOT NULL,
                threat_level TEXT NOT NULL,
                source_ip TEXT,
                target TEXT,
                description TEXT,
                evidence TEXT,
                confidence_score REAL,
                risk_score REAL,
                geo_location TEXT,
                user_agent TEXT,
                payload TEXT,
                affected_systems TEXT,
                recommended_actions TEXT,
                status TEXT DEFAULT 'ACTIVE',
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 보안 메트릭 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                total_threats_detected INTEGER,
                threats_blocked INTEGER,
                false_positives INTEGER,
                response_time_avg REAL,
                threat_accuracy REAL,
                system_uptime REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # IP 평판 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_reputation (
                ip_address TEXT PRIMARY KEY,
                reputation_score REAL,
                threat_types TEXT,
                first_seen DATETIME,
                last_seen DATETIME,
                threat_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # 학습 데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                features TEXT NOT NULL,
                label INTEGER NOT NULL,
                is_validated BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("위협 탐지 데이터베이스 초기화 완료")
    
    def _init_models(self):
        """AI 모델 초기화"""
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        # 이상 탐지 모델 (Isolation Forest)
        anomaly_model_path = self.models_path / "anomaly_detector.pkl"
        if anomaly_model_path.exists():
            try:
                with open(anomaly_model_path, 'rb') as f:
                    self.anomaly_detector = pickle.load(f)
                logger.info("이상 탐지 모델 로드 완료")
            except Exception as e:
                logger.error(f"이상 탐지 모델 로드 실패: {e}")
        
        if self.anomaly_detector is None:
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
        
        # 위협 분류 모델 (Random Forest)
        classifier_model_path = self.models_path / "threat_classifier.pkl"
        if classifier_model_path.exists():
            try:
                with open(classifier_model_path, 'rb') as f:
                    self.threat_classifier = pickle.load(f)
                logger.info("위협 분류 모델 로드 완료")
            except Exception as e:
                logger.error(f"위협 분류 모델 로드 실패: {e}")
        
        if self.threat_classifier is None:
            self.threat_classifier = RandomForestClassifier(
                n_estimators=200,
                random_state=42,
                max_depth=10
            )
        
        # 스케일러 로드
        scaler_path = self.models_path / "scaler.pkl"
        if scaler_path.exists():
            try:
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("스케일러 로드 완료")
            except Exception as e:
                logger.error(f"스케일러 로드 실패: {e}")
        
        self.models_loaded = True
    
    def _load_threat_intelligence(self):
        """위협 인텔리전스 로드"""
        try:
            # GeoIP 데이터베이스 로드
            geoip_path = self.config["intelligence"].get("geoip_database")
            if geoip_path and Path(geoip_path).exists():
                self.geoip_reader = geoip2.database.Reader(geoip_path)
                logger.info("GeoIP 데이터베이스 로드 완료")
            
            # 위협 피드 업데이트
            if self.config["intelligence"].get("update_threat_feeds", False):
                asyncio.create_task(self._update_threat_feeds())
            
        except Exception as e:
            logger.error(f"위협 인텔리전스 로드 실패: {e}")
    
    async def start_detection(self):
        """위협 탐지 시작"""
        if self.running:
            logger.warning("위협 탐지가 이미 실행 중입니다")
            return
        
        self.running = True
        logger.info("AI 위협 탐지 시스템 시작")
        
        # 탐지 태스크 시작
        self.detection_task = asyncio.create_task(self._detection_loop())
        
        # 학습 태스크 시작
        self.learning_task = asyncio.create_task(self._learning_loop())
        
        # 인텔리전스 업데이트 태스크
        asyncio.create_task(self._intelligence_update_loop())
    
    async def stop_detection(self):
        """위협 탐지 중지"""
        self.running = False
        
        if self.detection_task:
            self.detection_task.cancel()
        
        if self.learning_task:
            self.learning_task.cancel()
        
        if self.geoip_reader:
            self.geoip_reader.close()
        
        logger.info("AI 위협 탐지 시스템 중지")
    
    async def _detection_loop(self):
        """메인 탐지 루프"""
        while self.running:
            try:
                # 실시간 데이터 분석
                await self._analyze_real_time_data()
                
                # 이상 패턴 탐지
                await self._detect_anomalies()
                
                # 위협 분류 및 평가
                await self._classify_threats()
                
                # 자동 대응 실행
                await self._execute_automated_response()
                
                # 메트릭 업데이트
                await self._update_metrics()
                
                await asyncio.sleep(10)  # 10초마다 실행
                
            except Exception as e:
                logger.error(f"탐지 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def _analyze_real_time_data(self):
        """실시간 데이터 분석"""
        current_time = datetime.now()
        
        # API 요청 패턴 분석
        if self.config["monitoring"]["api_requests"]:
            await self._analyze_api_patterns()
        
        # 시스템 리소스 분석
        await self._analyze_system_resources()
        
        # 네트워크 트래픽 분석
        if self.config["monitoring"]["network_traffic"]:
            await self._analyze_network_traffic()
    
    async def _analyze_api_patterns(self):
        """API 요청 패턴 분석"""
        suspicious_patterns = []
        
        for ip, requests in self.request_patterns.items():
            if len(requests) < 10:  # 최소 요청 수
                continue
            
            recent_requests = [r for r in requests 
                             if datetime.now() - r['timestamp'] < timedelta(minutes=5)]
            
            if len(recent_requests) > 100:  # 5분간 100회 이상 요청
                suspicious_patterns.append({
                    'type': 'HIGH_FREQUENCY_REQUESTS',
                    'ip': ip,
                    'count': len(recent_requests),
                    'threat_type': ThreatType.DDoS
                })
            
            # SQL 인젝션 패턴 탐지
            sql_patterns = [
                r"(?i)(union.*select|select.*from|insert.*into|delete.*from)",
                r"(?i)(or\s+1=1|and\s+1=1|'.*or.*'=')",
                r"(?i)(exec\s*\(|execute\s*\(|sp_executesql)"
            ]
            
            for request in recent_requests:
                payload = request.get('payload', '')
                for pattern in sql_patterns:
                    if re.search(pattern, payload):
                        suspicious_patterns.append({
                            'type': 'SQL_INJECTION_ATTEMPT',
                            'ip': ip,
                            'payload': payload,
                            'threat_type': ThreatType.SQL_INJECTION
                        })
                        break
        
        # 의심스러운 패턴 처리
        for pattern in suspicious_patterns:
            await self._handle_suspicious_pattern(pattern)
    
    async def _analyze_system_resources(self):
        """시스템 리소스 분석"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                await self._create_threat_event(
                    threat_type=ThreatType.DDoS,
                    threat_level=ThreatLevel.HIGH,
                    description=f"비정상적 CPU 사용률: {cpu_percent}%",
                    source_ip="system",
                    confidence_score=0.8
                )
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                await self._create_threat_event(
                    threat_type=ThreatType.DDoS,
                    threat_level=ThreatLevel.HIGH,
                    description=f"비정상적 메모리 사용률: {memory.percent}%",
                    source_ip="system",
                    confidence_score=0.8
                )
            
            # 디스크 I/O
            disk_io = psutil.disk_io_counters()
            if disk_io and disk_io.read_bytes > 1000000000:  # 1GB 이상
                await self._create_threat_event(
                    threat_type=ThreatType.DATA_EXFILTRATION,
                    threat_level=ThreatLevel.MEDIUM,
                    description=f"대량 디스크 읽기 감지: {disk_io.read_bytes} bytes",
                    source_ip="system",
                    confidence_score=0.6
                )
            
        except Exception as e:
            logger.error(f"시스템 리소스 분석 실패: {e}")
    
    async def _analyze_network_traffic(self):
        """네트워크 트래픽 분석"""
        try:
            # 네트워크 연결 분석
            connections = psutil.net_connections()
            
            # 외부 연결 통계
            external_connections = defaultdict(int)
            for conn in connections:
                if conn.raddr and conn.status == 'ESTABLISHED':
                    external_ip = conn.raddr.ip
                    if not self._is_internal_ip(external_ip):
                        external_connections[external_ip] += 1
            
            # 의심스러운 연결 탐지
            for ip, count in external_connections.items():
                if count > 20:  # 동일 IP로 20개 이상 연결
                    await self._create_threat_event(
                        threat_type=ThreatType.RECONNAISSANCE,
                        threat_level=ThreatLevel.MEDIUM,
                        description=f"의심스러운 대량 연결: {ip} ({count}개)",
                        source_ip=ip,
                        confidence_score=0.7
                    )
            
        except Exception as e:
            logger.error(f"네트워크 트래픽 분석 실패: {e}")
    
    def _is_internal_ip(self, ip: str) -> bool:
        """내부 IP 확인"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private or ip_obj.is_loopback
        except ValueError:
            return False
    
    async def _detect_anomalies(self):
        """이상 패턴 탐지"""
        if not self.models_loaded:
            return
        
        try:
            # 현재 시스템 상태 특성 추출
            features = await self._extract_system_features()
            
            if len(features) == 0:
                return
            
            # 특성 정규화
            features_scaled = self.scaler.transform([features])
            
            # 이상 탐지
            anomaly_score = self.anomaly_detector.decision_function(features_scaled)[0]
            is_anomaly = self.anomaly_detector.predict(features_scaled)[0] == -1
            
            if is_anomaly:
                confidence = min(abs(anomaly_score), 1.0)
                
                await self._create_threat_event(
                    threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                    threat_level=self._calculate_threat_level(confidence),
                    description=f"시스템 이상 패턴 탐지 (점수: {anomaly_score:.3f})",
                    source_ip="system",
                    confidence_score=confidence,
                    evidence={"anomaly_score": anomaly_score, "features": features}
                )
            
        except Exception as e:
            logger.error(f"이상 탐지 실패: {e}")
    
    async def _extract_system_features(self) -> List[float]:
        """시스템 특성 추출"""
        features = []
        
        try:
            # CPU 특성
            cpu_percent = psutil.cpu_percent()
            cpu_count = psutil.cpu_count()
            features.extend([cpu_percent, cpu_count])
            
            # 메모리 특성
            memory = psutil.virtual_memory()
            features.extend([memory.percent, memory.available / 1024**3])  # GB
            
            # 디스크 특성
            disk = psutil.disk_usage('/')
            features.extend([disk.percent, disk.free / 1024**3])  # GB
            
            # 네트워크 특성
            net_io = psutil.net_io_counters()
            features.extend([
                net_io.bytes_sent / 1024**2,  # MB
                net_io.bytes_recv / 1024**2,  # MB
                net_io.packets_sent,
                net_io.packets_recv
            ])
            
            # 프로세스 특성
            process_count = len(psutil.pids())
            features.append(process_count)
            
            # 시간 특성
            hour = datetime.now().hour
            day_of_week = datetime.now().weekday()
            features.extend([hour, day_of_week])
            
        except Exception as e:
            logger.error(f"특성 추출 실패: {e}")
            return []
        
        return features
    
    def _calculate_threat_level(self, confidence: float) -> ThreatLevel:
        """위협 수준 계산"""
        if confidence >= 0.9:
            return ThreatLevel.CRITICAL
        elif confidence >= 0.8:
            return ThreatLevel.HIGH
        elif confidence >= 0.6:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW
    
    async def _classify_threats(self):
        """위협 분류"""
        # 활성 위협 이벤트들을 분류
        for threat_id, threat in self.active_threats.items():
            if threat.threat_type == ThreatType.ANOMALOUS_BEHAVIOR:
                # 이상 패턴을 구체적인 위협으로 분류
                classified_type = await self._classify_anomaly(threat)
                if classified_type != threat.threat_type:
                    threat.threat_type = classified_type
                    threat.description = f"분류된 위협: {classified_type.value}"
    
    async def _classify_anomaly(self, threat: ThreatEvent) -> ThreatType:
        """이상 패턴 분류"""
        evidence = threat.evidence
        
        # 시스템 리소스 기반 분류
        if 'features' in evidence:
            features = evidence['features']
            
            # CPU/메모리 과사용 -> DDoS
            if len(features) >= 4 and (features[0] > 90 or features[2] > 90):
                return ThreatType.DDoS
            
            # 대량 네트워크 트래픽 -> 데이터 유출
            if len(features) >= 8 and features[4] > 1000:  # 1GB 이상
                return ThreatType.DATA_EXFILTRATION
        
        return threat.threat_type
    
    async def _execute_automated_response(self):
        """자동 대응 실행"""
        for threat_id, threat in list(self.active_threats.items()):
            if threat.status != "ACTIVE":
                continue
            
            # 위협 수준별 자동 대응
            if threat.threat_level == ThreatLevel.CRITICAL:
                await self._handle_critical_threat(threat)
            elif threat.threat_level == ThreatLevel.HIGH:
                await self._handle_high_threat(threat)
            elif threat.threat_level == ThreatLevel.MEDIUM:
                await self._handle_medium_threat(threat)
    
    async def _handle_critical_threat(self, threat: ThreatEvent):
        """중요 위협 처리"""
        logger.critical(f"중요 위협 탐지: {threat.description}")
        
        # IP 자동 차단
        if threat.source_ip and threat.source_ip != "system":
            await self._block_ip(threat.source_ip)
        
        # 긴급 알림 발송
        await self._send_emergency_alert(threat)
        
        # 필요시 시스템 격리
        if threat.threat_type in [ThreatType.MALWARE, ThreatType.DATA_EXFILTRATION]:
            await self._quarantine_system(threat.affected_systems)
        
        # 위협 상태 업데이트
        threat.status = "RESPONDING"
        await self._update_threat_event(threat)
    
    async def _handle_high_threat(self, threat: ThreatEvent):
        """높은 위협 처리"""
        logger.warning(f"높은 위협 탐지: {threat.description}")
        
        # 속도 제한 적용
        if threat.source_ip and threat.source_ip != "system":
            await self._apply_rate_limit(threat.source_ip)
        
        # 알림 발송
        await self._send_threat_alert(threat)
        
        threat.status = "MONITORING"
        await self._update_threat_event(threat)
    
    async def _handle_medium_threat(self, threat: ThreatEvent):
        """중간 위협 처리"""
        logger.info(f"중간 위협 탐지: {threat.description}")
        
        # 모니터링 강화
        await self._enhance_monitoring(threat.source_ip)
        
        # 경고 알림
        await self._send_warning_alert(threat)
        
        threat.status = "MONITORING"
        await self._update_threat_event(threat)
    
    async def _handle_suspicious_pattern(self, pattern: Dict[str, Any]):
        """의심스러운 패턴 처리"""
        threat_type = pattern.get('threat_type', ThreatType.ANOMALOUS_BEHAVIOR)
        ip = pattern.get('ip', 'unknown')
        
        await self._create_threat_event(
            threat_type=threat_type,
            threat_level=ThreatLevel.MEDIUM,
            description=f"의심스러운 패턴 탐지: {pattern['type']}",
            source_ip=ip,
            confidence_score=0.7,
            evidence=pattern
        )
    
    async def _create_threat_event(self, 
                                 threat_type: ThreatType,
                                 threat_level: ThreatLevel,
                                 description: str,
                                 source_ip: str,
                                 confidence_score: float,
                                 evidence: Optional[Dict] = None,
                                 target: str = "system",
                                 payload: Optional[str] = None) -> ThreatEvent:
        """위협 이벤트 생성"""
        
        event_id = hashlib.md5(
            f"{threat_type.value}_{source_ip}_{datetime.now().isoformat()}".encode()
        ).hexdigest()
        
        # 지리적 위치 정보
        geo_location = await self._get_geo_location(source_ip)
        
        # 위험 점수 계산
        risk_score = self._calculate_risk_score(threat_type, threat_level, confidence_score)
        
        # 권장 액션 결정
        recommended_actions = self._determine_actions(threat_type, threat_level)
        
        threat_event = ThreatEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            threat_type=threat_type,
            threat_level=threat_level,
            source_ip=source_ip,
            target=target,
            description=description,
            evidence=evidence or {},
            confidence_score=confidence_score,
            risk_score=risk_score,
            geo_location=geo_location,
            user_agent=None,
            payload=payload,
            affected_systems=[target],
            recommended_actions=recommended_actions
        )
        
        # 활성 위협에 추가
        self.active_threats[event_id] = threat_event
        self.threat_history.append(threat_event)
        
        # 데이터베이스에 저장
        await self._save_threat_event(threat_event)
        
        # 메트릭 업데이트
        self.metrics.total_threats_detected += 1
        
        logger.info(f"위협 이벤트 생성: {threat_type.value} - {description}")
        
        return threat_event
    
    async def _get_geo_location(self, ip: str) -> Optional[Dict[str, str]]:
        """IP 지리적 위치 조회"""
        if not self.geoip_reader or ip == "system" or self._is_internal_ip(ip):
            return None
        
        try:
            response = self.geoip_reader.city(ip)
            return {
                "country": response.country.name,
                "city": response.city.name,
                "latitude": str(response.location.latitude),
                "longitude": str(response.location.longitude)
            }
        except geoip2.errors.AddressNotFoundError:
            return None
        except Exception as e:
            logger.error(f"지리적 위치 조회 실패: {e}")
            return None
    
    def _calculate_risk_score(self, threat_type: ThreatType, 
                            threat_level: ThreatLevel, 
                            confidence_score: float) -> float:
        """위험 점수 계산"""
        # 위협 유형별 기본 점수
        type_scores = {
            ThreatType.MALWARE: 0.9,
            ThreatType.DATA_EXFILTRATION: 0.8,
            ThreatType.SQL_INJECTION: 0.7,
            ThreatType.DDoS: 0.6,
            ThreatType.BRUTE_FORCE: 0.5,
            ThreatType.XSS: 0.4,
            ThreatType.RECONNAISSANCE: 0.3,
            ThreatType.ANOMALOUS_BEHAVIOR: 0.4
        }
        
        # 위협 수준별 가중치
        level_weights = {
            ThreatLevel.CRITICAL: 1.0,
            ThreatLevel.HIGH: 0.8,
            ThreatLevel.MEDIUM: 0.6,
            ThreatLevel.LOW: 0.4
        }
        
        base_score = type_scores.get(threat_type, 0.5)
        level_weight = level_weights.get(threat_level, 0.5)
        
        risk_score = base_score * level_weight * confidence_score
        return min(risk_score, 1.0)
    
    def _determine_actions(self, threat_type: ThreatType, 
                         threat_level: ThreatLevel) -> List[ActionType]:
        """권장 액션 결정"""
        actions = [ActionType.MONITOR, ActionType.ALERT]
        
        if threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
            if threat_type in [ThreatType.DDoS, ThreatType.BRUTE_FORCE]:
                actions.append(ActionType.BLOCK_IP)
            elif threat_type == ThreatType.MALWARE:
                actions.append(ActionType.QUARANTINE)
            elif threat_type == ThreatType.DATA_EXFILTRATION:
                actions.extend([ActionType.QUARANTINE, ActionType.BLOCK_IP])
        
        if threat_level == ThreatLevel.CRITICAL:
            actions.append(ActionType.EMERGENCY_SHUTDOWN)
        
        return actions
    
    async def _save_threat_event(self, threat: ThreatEvent):
        """위협 이벤트 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO threat_events (
                event_id, timestamp, threat_type, threat_level, source_ip,
                target, description, evidence, confidence_score, risk_score,
                geo_location, user_agent, payload, affected_systems,
                recommended_actions, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            threat.event_id, threat.timestamp, threat.threat_type.value,
            threat.threat_level.value, threat.source_ip, threat.target,
            threat.description, json.dumps(threat.evidence),
            threat.confidence_score, threat.risk_score,
            json.dumps(threat.geo_location) if threat.geo_location else None,
            threat.user_agent, threat.payload,
            json.dumps(threat.affected_systems),
            json.dumps([a.value for a in threat.recommended_actions]),
            threat.status
        ))
        
        conn.commit()
        conn.close()
    
    async def _update_threat_event(self, threat: ThreatEvent):
        """위협 이벤트 업데이트"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE threat_events 
            SET status = ?, resolved_at = ?
            WHERE event_id = ?
        ''', (threat.status, threat.resolved_at, threat.event_id))
        
        conn.commit()
        conn.close()
    
    async def _block_ip(self, ip: str):
        """IP 주소 차단"""
        logger.warning(f"IP 주소 차단: {ip}")
        
        # 방화벽 규칙 추가 (iptables 예시)
        try:
            import subprocess
            subprocess.run([
                "sudo", "iptables", "-A", "INPUT", 
                "-s", ip, "-j", "DROP"
            ], check=True)
            
            # IP 평판 업데이트
            await self._update_ip_reputation(ip, -1.0, ["BLOCKED"])
            
        except Exception as e:
            logger.error(f"IP 차단 실패: {e}")
    
    async def _apply_rate_limit(self, ip: str):
        """속도 제한 적용"""
        logger.info(f"속도 제한 적용: {ip}")
        # 속도 제한 로직 구현
        # 예: nginx rate limiting, API gateway throttling 등
    
    async def _quarantine_system(self, systems: List[str]):
        """시스템 격리"""
        logger.critical(f"시스템 격리: {systems}")
        # 시스템 격리 로직 구현
        # 예: 네트워크 분리, 서비스 중지 등
    
    async def _enhance_monitoring(self, ip: str):
        """모니터링 강화"""
        logger.info(f"모니터링 강화: {ip}")
        # 해당 IP에 대한 세밀한 모니터링 설정
    
    async def _send_emergency_alert(self, threat: ThreatEvent):
        """긴급 알림 발송"""
        message = f"🚨 CRITICAL THREAT DETECTED 🚨\n"
        message += f"Type: {threat.threat_type.value}\n"
        message += f"Source: {threat.source_ip}\n"
        message += f"Description: {threat.description}\n"
        message += f"Risk Score: {threat.risk_score:.2f}\n"
        
        await self._send_alert(message, "EMERGENCY")
    
    async def _send_threat_alert(self, threat: ThreatEvent):
        """위협 알림 발송"""
        message = f"⚠️ THREAT DETECTED\n"
        message += f"Type: {threat.threat_type.value}\n"
        message += f"Level: {threat.threat_level.value}\n"
        message += f"Source: {threat.source_ip}\n"
        message += f"Description: {threat.description}\n"
        
        await self._send_alert(message, "HIGH")
    
    async def _send_warning_alert(self, threat: ThreatEvent):
        """경고 알림 발송"""
        message = f"ℹ️ SECURITY WARNING\n"
        message += f"Type: {threat.threat_type.value}\n"
        message += f"Source: {threat.source_ip}\n"
        message += f"Description: {threat.description}\n"
        
        await self._send_alert(message, "MEDIUM")
    
    async def _send_alert(self, message: str, level: str):
        """알림 발송"""
        logger.info(f"보안 알림 발송 ({level}): {message}")
        
        # Slack 알림
        if self.config["response"].get("alert_slack", False):
            # Slack 웹훅 구현
            pass
        
        # 이메일 알림
        if self.config["response"].get("alert_email", False):
            # 이메일 발송 구현
            pass
    
    async def _update_ip_reputation(self, ip: str, score: float, threat_types: List[str]):
        """IP 평판 업데이트"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ip_reputation (
                ip_address, reputation_score, threat_types, 
                first_seen, last_seen, threat_count, is_blocked
            ) VALUES (
                ?, ?, ?, 
                COALESCE((SELECT first_seen FROM ip_reputation WHERE ip_address = ?), ?),
                ?, 
                COALESCE((SELECT threat_count FROM ip_reputation WHERE ip_address = ?), 0) + 1,
                ?
            )
        ''', (ip, score, json.dumps(threat_types), ip, datetime.now(), 
              datetime.now(), ip, score < 0))
        
        conn.commit()
        conn.close()
    
    async def _learning_loop(self):
        """머신러닝 모델 학습 루프"""
        retrain_interval = self.config["machine_learning"]["retrain_interval"]
        
        while self.running:
            try:
                await self._retrain_models()
                await asyncio.sleep(retrain_interval)
                
            except Exception as e:
                logger.error(f"학습 루프 오류: {e}")
                await asyncio.sleep(3600)  # 1시간 대기
    
    async def _retrain_models(self):
        """모델 재학습"""
        logger.info("AI 모델 재학습 시작")
        
        # 학습 데이터 수집
        training_data = await self._collect_training_data()
        
        if len(training_data) < 100:  # 최소 학습 데이터
            logger.warning("학습 데이터 부족")
            return
        
        # 특성과 라벨 분리
        X = [json.loads(row[0]) for row in training_data]
        y = [row[1] for row in training_data]
        
        # 데이터 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # 스케일러 재학습
        self.scaler.fit(X_train)
        X_train_scaled = self.scaler.transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 이상 탐지 모델 재학습
        self.anomaly_detector.fit(X_train_scaled)
        
        # 위협 분류 모델 재학습
        if len(set(y_train)) > 1:  # 다중 클래스가 있는 경우만
            self.threat_classifier.fit(X_train_scaled, y_train)
            
            # 성능 평가
            y_pred = self.threat_classifier.predict(X_test_scaled)
            accuracy = (y_pred == y_test).mean()
            
            if accuracy >= self.config["machine_learning"]["model_accuracy_threshold"]:
                logger.info(f"모델 재학습 완료 - 정확도: {accuracy:.3f}")
                
                # 모델 저장
                await self._save_models()
            else:
                logger.warning(f"모델 성능 부족 - 정확도: {accuracy:.3f}")
    
    async def _collect_training_data(self) -> List[Tuple]:
        """학습 데이터 수집"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT features, label FROM training_data 
            WHERE is_validated = TRUE
            ORDER BY created_at DESC
            LIMIT 10000
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        return data
    
    async def _save_models(self):
        """모델 저장"""
        try:
            # 이상 탐지 모델 저장
            with open(self.models_path / "anomaly_detector.pkl", 'wb') as f:
                pickle.dump(self.anomaly_detector, f)
            
            # 위협 분류 모델 저장
            with open(self.models_path / "threat_classifier.pkl", 'wb') as f:
                pickle.dump(self.threat_classifier, f)
            
            # 스케일러 저장
            with open(self.models_path / "scaler.pkl", 'wb') as f:
                pickle.dump(self.scaler, f)
            
            logger.info("AI 모델 저장 완료")
            
        except Exception as e:
            logger.error(f"모델 저장 실패: {e}")
    
    async def _intelligence_update_loop(self):
        """위협 인텔리전스 업데이트 루프"""
        while self.running:
            try:
                await self._update_threat_feeds()
                await asyncio.sleep(3600)  # 1시간마다
                
            except Exception as e:
                logger.error(f"위협 인텔리전스 업데이트 오류: {e}")
                await asyncio.sleep(1800)  # 30분 대기
    
    async def _update_threat_feeds(self):
        """위협 피드 업데이트"""
        feed_urls = self.config["intelligence"]["threat_feed_urls"]
        
        for url in feed_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            await self._process_threat_feed(content, url)
                        
            except Exception as e:
                logger.error(f"위협 피드 업데이트 실패 ({url}): {e}")
    
    async def _process_threat_feed(self, content: str, source: str):
        """위협 피드 처리"""
        lines = content.strip().split('\n')
        threat_ips = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # IP 주소 추출
                ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', line)
                if ip_match:
                    threat_ips.append(ip_match.group(1))
        
        # 위협 지표에 추가
        self.threat_indicators.update(threat_ips)
        
        logger.info(f"위협 피드 업데이트: {len(threat_ips)}개 IP ({source})")
    
    async def _update_metrics(self):
        """메트릭 업데이트"""
        self.metrics.last_update = datetime.now()
        
        # 일일 메트릭 저장
        today = datetime.now().date()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO security_metrics (
                date, total_threats_detected, threats_blocked, 
                false_positives, response_time_avg, threat_accuracy, system_uptime
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            today, self.metrics.total_threats_detected,
            self.metrics.threats_blocked, self.metrics.false_positives,
            self.metrics.response_time_avg, self.metrics.threat_accuracy,
            self.metrics.system_uptime
        ))
        
        conn.commit()
        conn.close()
    
    async def get_security_status(self) -> Dict[str, Any]:
        """보안 상태 조회"""
        active_threat_count = len(self.active_threats)
        critical_threats = [t for t in self.active_threats.values() 
                          if t.threat_level == ThreatLevel.CRITICAL]
        
        return {
            "status": "SECURE" if active_threat_count == 0 else "THREATS_DETECTED",
            "active_threats": active_threat_count,
            "critical_threats": len(critical_threats),
            "threat_indicators": len(self.threat_indicators),
            "ip_reputation_db_size": len(self.ip_reputation),
            "models_loaded": self.models_loaded,
            "metrics": asdict(self.metrics),
            "recent_threats": [
                {
                    "type": t.threat_type.value,
                    "level": t.threat_level.value,
                    "source": t.source_ip,
                    "timestamp": t.timestamp.isoformat()
                }
                for t in list(self.threat_history)[-10:]
            ]
        }
    
    async def analyze_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """요청 분석"""
        ip = request_data.get('ip', 'unknown')
        url = request_data.get('url', '')
        payload = request_data.get('payload', '')
        user_agent = request_data.get('user_agent', '')
        
        # 요청 패턴에 추가
        self.request_patterns[ip].append({
            'timestamp': datetime.now(),
            'url': url,
            'payload': payload,
            'user_agent': user_agent
        })
        
        analysis_result = {
            'ip': ip,
            'threat_detected': False,
            'threat_type': None,
            'threat_level': None,
            'confidence': 0.0,
            'should_block': False,
            'recommendations': []
        }
        
        # IP 평판 확인
        if ip in self.threat_indicators:
            analysis_result.update({
                'threat_detected': True,
                'threat_type': 'MALICIOUS_IP',
                'threat_level': 'HIGH',
                'confidence': 0.9,
                'should_block': True,
                'recommendations': ['BLOCK_IP', 'ALERT']
            })
            
            await self._create_threat_event(
                threat_type=ThreatType.RECONNAISSANCE,
                threat_level=ThreatLevel.HIGH,
                description=f"악성 IP 접근: {ip}",
                source_ip=ip,
                confidence_score=0.9
            )
        
        # 페이로드 분석
        threat_patterns = {
            'sql_injection': [
                r"(?i)(union.*select|select.*from|insert.*into)",
                r"(?i)(or\s+1=1|and\s+1=1|'.*or.*'=')"
            ],
            'xss': [
                r"(?i)(<script|javascript:|onload=|onerror=)",
                r"(?i)(alert\(|document\.cookie|window\.location)"
            ],
            'path_traversal': [
                r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)",
                r"(/etc/passwd|/windows/system32)"
            ]
        }
        
        for threat_name, patterns in threat_patterns.items():
            for pattern in patterns:
                if re.search(pattern, payload + url):
                    threat_type_map = {
                        'sql_injection': ThreatType.SQL_INJECTION,
                        'xss': ThreatType.XSS,
                        'path_traversal': ThreatType.UNAUTHORIZED_ACCESS
                    }
                    
                    analysis_result.update({
                        'threat_detected': True,
                        'threat_type': threat_name.upper(),
                        'threat_level': 'HIGH',
                        'confidence': 0.8,
                        'should_block': True,
                        'recommendations': ['BLOCK_IP', 'ALERT', 'LOG_INCIDENT']
                    })
                    
                    await self._create_threat_event(
                        threat_type=threat_type_map[threat_name],
                        threat_level=ThreatLevel.HIGH,
                        description=f"{threat_name.replace('_', ' ').title()} 시도 탐지",
                        source_ip=ip,
                        confidence_score=0.8,
                        payload=payload
                    )
                    break
        
        return analysis_result


# 전역 인스턴스
_threat_detection_system = None

def get_threat_detection_system() -> AIThreatDetectionSystem:
    """AI 위협 탐지 시스템 싱글톤 반환"""
    global _threat_detection_system
    if _threat_detection_system is None:
        _threat_detection_system = AIThreatDetectionSystem()
    return _threat_detection_system


async def main():
    """메인 함수 - 테스트용"""
    system = AIThreatDetectionSystem()
    
    try:
        await system.start_detection()
        
        while system.running:
            status = await system.get_security_status()
            print(f"보안 상태: {status['status']}")
            print(f"활성 위협: {status['active_threats']}")
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        await system.stop_detection()


if __name__ == "__main__":
    asyncio.run(main())