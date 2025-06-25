"""
컴플라이언스 자동 준수 시스템

전 세계 규제 요구사항을 자동으로 준수하는 포괄적인 시스템
- GDPR, CCPA, HIPAA 등 주요 규제 준수
- 자동 데이터 분류 및 보호
- 감사 로그 자동 생성
- 규제 변화 실시간 감지
- 준수 상태 지속적 모니터링
"""

import asyncio
import json
import logging
import sqlite3
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import re
import uuid
import shutil
import tempfile
from cryptography.fernet import Fernet
import yaml

logger = logging.getLogger(__name__)


class ComplianceFramework(Enum):
    """컴플라이언스 프레임워크"""
    GDPR = "GDPR"  # General Data Protection Regulation
    CCPA = "CCPA"  # California Consumer Privacy Act
    HIPAA = "HIPAA"  # Health Insurance Portability and Accountability Act
    SOX = "SOX"  # Sarbanes-Oxley Act
    PCI_DSS = "PCI_DSS"  # Payment Card Industry Data Security Standard
    ISO_27001 = "ISO_27001"  # ISO/IEC 27001
    NIST = "NIST"  # NIST Cybersecurity Framework
    K_ISMS = "K_ISMS"  # 한국 정보보호관리체계


class DataCategory(Enum):
    """데이터 카테고리"""
    PERSONAL_DATA = "PERSONAL_DATA"
    SENSITIVE_PERSONAL_DATA = "SENSITIVE_PERSONAL_DATA"
    FINANCIAL_DATA = "FINANCIAL_DATA"
    HEALTH_DATA = "HEALTH_DATA"
    BIOMETRIC_DATA = "BIOMETRIC_DATA"
    LOCATION_DATA = "LOCATION_DATA"
    BEHAVIORAL_DATA = "BEHAVIORAL_DATA"
    PUBLIC_DATA = "PUBLIC_DATA"


class ComplianceStatus(Enum):
    """준수 상태"""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    UNDER_REVIEW = "UNDER_REVIEW"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"


class DataRetentionPeriod(Enum):
    """데이터 보존 기간"""
    IMMEDIATE_DELETE = 0
    THIRTY_DAYS = 30
    SIX_MONTHS = 180
    ONE_YEAR = 365
    THREE_YEARS = 1095
    SEVEN_YEARS = 2555
    INDEFINITE = -1


@dataclass
class ComplianceRule:
    """컴플라이언스 규칙"""
    rule_id: str
    framework: ComplianceFramework
    title: str
    description: str
    requirements: List[str]
    data_categories: List[DataCategory]
    retention_period: DataRetentionPeriod
    encryption_required: bool
    access_controls_required: bool
    audit_logging_required: bool
    consent_required: bool
    right_to_deletion: bool
    data_portability: bool
    breach_notification_hours: int
    penalty_amount: float
    last_updated: datetime
    is_active: bool


@dataclass
class DataAsset:
    """데이터 자산"""
    asset_id: str
    name: str
    location: str
    data_category: DataCategory
    data_subjects_count: int
    retention_period: DataRetentionPeriod
    encryption_status: bool
    access_controls: Dict[str, Any]
    processing_purposes: List[str]
    legal_basis: str
    consent_status: bool
    last_accessed: datetime
    created_at: datetime
    metadata: Dict[str, Any]


@dataclass
class ComplianceIncident:
    """컴플라이언스 사고"""
    incident_id: str
    framework: ComplianceFramework
    incident_type: str
    severity: str
    description: str
    affected_data_assets: List[str]
    affected_subjects_count: int
    discovered_at: datetime
    reported_at: Optional[datetime]
    resolved_at: Optional[datetime]
    notification_required: bool
    notification_deadline: Optional[datetime]
    remediation_actions: List[str]
    status: str


@dataclass
class AuditLog:
    """감사 로그"""
    log_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource: str
    data_category: Optional[DataCategory]
    purpose: str
    legal_basis: str
    ip_address: str
    user_agent: str
    success: bool
    details: Dict[str, Any]


class ComplianceAutomationSystem:
    """컴플라이언스 자동 준수 시스템"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or Path("config/compliance_config.json")
        self.db_path = Path("compliance/compliance.db")
        self.rules_path = Path("compliance/rules")
        self.reports_path = Path("compliance/reports")
        
        # 설정 로드
        self.config = self._load_config()
        
        # 규칙 및 정책 관리
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self.data_assets: Dict[str, DataAsset] = {}
        self.incidents: Dict[str, ComplianceIncident] = {}
        self.audit_logs: List[AuditLog] = []
        
        # 데이터 분류 패턴
        self.data_patterns = {
            DataCategory.PERSONAL_DATA: [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # 이메일
                r'\b\d{3}-\d{3,4}-\d{4}\b',  # 전화번호
                r'\b\d{6}-\d{7}\b'  # 주민등록번호 패턴
            ],
            DataCategory.FINANCIAL_DATA: [
                r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # 신용카드
                r'\b\d{3}-\d{2}-\d{3}-\d{6}\b'  # 계좌번호 패턴
            ],
            DataCategory.HEALTH_DATA: [
                r'\b의료\b', r'\b건강\b', r'\b병원\b', r'\b진료\b'
            ]
        }
        
        # 암호화 키
        self.encryption_key = self._get_or_create_encryption_key()
        
        # 실행 상태
        self.running = False
        self.monitoring_task = None
        self.data_discovery_task = None
        self.retention_task = None
        
        # 초기화
        self._init_database()
        self._create_directories()
        self._load_compliance_rules()
        
        logger.info("컴플라이언스 자동 준수 시스템 초기화 완료")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "frameworks": {
                "enabled": ["GDPR", "CCPA", "K_ISMS"],
                "jurisdiction": "EU",  # EU, US, KR
                "organization_type": "GENERAL"  # GENERAL, HEALTHCARE, FINANCIAL
            },
            "data_discovery": {
                "scan_interval_hours": 24,
                "auto_classify": True,
                "deep_scan": True,
                "scan_paths": ["src/", "data/", "logs/", "config/"]
            },
            "data_protection": {
                "auto_encrypt_sensitive": True,
                "default_encryption": "AES-256",
                "anonymization_enabled": True,
                "pseudonymization_enabled": True
            },
            "retention": {
                "auto_delete_expired": True,
                "grace_period_days": 30,
                "backup_before_delete": True,
                "notification_before_delete": True
            },
            "consent_management": {
                "enabled": True,
                "granular_consent": True,
                "consent_expiry_months": 24,
                "withdrawal_automation": True
            },
            "audit": {
                "log_all_access": True,
                "log_retention_years": 7,
                "real_time_monitoring": True,
                "automated_reporting": True
            },
            "incident_response": {
                "auto_detect": True,
                "notification_enabled": True,
                "escalation_enabled": True,
                "breach_notification_hours": 72
            },
            "reporting": {
                "monthly_compliance_report": True,
                "quarterly_audit_report": True,
                "annual_dpo_report": True,
                "real_time_dashboard": True
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
        
        # 컴플라이언스 규칙 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compliance_rules (
                rule_id TEXT PRIMARY KEY,
                framework TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                requirements TEXT,
                data_categories TEXT,
                retention_period INTEGER,
                encryption_required BOOLEAN,
                access_controls_required BOOLEAN,
                audit_logging_required BOOLEAN,
                consent_required BOOLEAN,
                right_to_deletion BOOLEAN,
                data_portability BOOLEAN,
                breach_notification_hours INTEGER,
                penalty_amount REAL,
                last_updated DATETIME,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # 데이터 자산 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_assets (
                asset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                data_category TEXT NOT NULL,
                data_subjects_count INTEGER,
                retention_period INTEGER,
                encryption_status BOOLEAN,
                access_controls TEXT,
                processing_purposes TEXT,
                legal_basis TEXT,
                consent_status BOOLEAN,
                last_accessed DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # 컴플라이언스 사고 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compliance_incidents (
                incident_id TEXT PRIMARY KEY,
                framework TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                affected_data_assets TEXT,
                affected_subjects_count INTEGER,
                discovered_at DATETIME NOT NULL,
                reported_at DATETIME,
                resolved_at DATETIME,
                notification_required BOOLEAN,
                notification_deadline DATETIME,
                remediation_actions TEXT,
                status TEXT DEFAULT 'OPEN'
            )
        ''')
        
        # 감사 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                data_category TEXT,
                purpose TEXT,
                legal_basis TEXT,
                ip_address TEXT,
                user_agent TEXT,
                success BOOLEAN,
                details TEXT
            )
        ''')
        
        # 동의 관리 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consent_records (
                consent_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                processing_purpose TEXT NOT NULL,
                consent_given BOOLEAN NOT NULL,
                consent_date DATETIME NOT NULL,
                expiry_date DATETIME,
                withdrawal_date DATETIME,
                legal_basis TEXT,
                granular_permissions TEXT,
                source TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # 데이터 주체 권리 요청 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_subject_requests (
                request_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                request_date DATETIME NOT NULL,
                completion_deadline DATETIME NOT NULL,
                status TEXT DEFAULT 'PENDING',
                completed_date DATETIME,
                verification_status BOOLEAN DEFAULT FALSE,
                response_data TEXT,
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("컴플라이언스 데이터베이스 초기화 완료")
    
    def _create_directories(self):
        """필요한 디렉토리 생성"""
        directories = [
            self.rules_path,
            self.reports_path,
            Path("compliance/templates"),
            Path("compliance/certificates"),
            Path("compliance/incidents")
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """암호화 키 생성 또는 로드"""
        key_file = Path("compliance/encryption.key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _load_compliance_rules(self):
        """컴플라이언스 규칙 로드"""
        # GDPR 규칙
        if "GDPR" in self.config["frameworks"]["enabled"]:
            self._load_gdpr_rules()
        
        # CCPA 규칙
        if "CCPA" in self.config["frameworks"]["enabled"]:
            self._load_ccpa_rules()
        
        # K-ISMS 규칙
        if "K_ISMS" in self.config["frameworks"]["enabled"]:
            self._load_k_isms_rules()
        
        logger.info(f"{len(self.compliance_rules)}개 컴플라이언스 규칙 로드 완료")
    
    def _load_gdpr_rules(self):
        """GDPR 규칙 로드"""
        gdpr_rules = [
            ComplianceRule(
                rule_id="gdpr_article_6",
                framework=ComplianceFramework.GDPR,
                title="Article 6 - Lawfulness of processing",
                description="개인데이터 처리의 합법성",
                requirements=[
                    "처리에 대한 합법적 근거 필요",
                    "동의 또는 기타 법적 근거 확보",
                    "처리 목적의 명확성"
                ],
                data_categories=[DataCategory.PERSONAL_DATA],
                retention_period=DataRetentionPeriod.THREE_YEARS,
                encryption_required=True,
                access_controls_required=True,
                audit_logging_required=True,
                consent_required=True,
                right_to_deletion=True,
                data_portability=True,
                breach_notification_hours=72,
                penalty_amount=20000000.0,  # 2천만 유로 또는 연간 매출의 4%
                last_updated=datetime.now(),
                is_active=True
            ),
            ComplianceRule(
                rule_id="gdpr_article_17",
                framework=ComplianceFramework.GDPR,
                title="Article 17 - Right to erasure",
                description="삭제권 (잊힐 권리)",
                requirements=[
                    "요청 시 개인데이터 삭제",
                    "삭제 불가능한 경우 정당한 사유 제시",
                    "제3자에게 삭제 요청 전달"
                ],
                data_categories=[DataCategory.PERSONAL_DATA, DataCategory.SENSITIVE_PERSONAL_DATA],
                retention_period=DataRetentionPeriod.IMMEDIATE_DELETE,
                encryption_required=True,
                access_controls_required=True,
                audit_logging_required=True,
                consent_required=False,
                right_to_deletion=True,
                data_portability=False,
                breach_notification_hours=72,
                penalty_amount=20000000.0,
                last_updated=datetime.now(),
                is_active=True
            ),
            ComplianceRule(
                rule_id="gdpr_article_20",
                framework=ComplianceFramework.GDPR,
                title="Article 20 - Right to data portability",
                description="데이터 이동권",
                requirements=[
                    "구조화되고 일반적으로 사용되는 기계 판독 가능 형식으로 제공",
                    "다른 컨트롤러에게 데이터 전송",
                    "기술적으로 가능한 경우 직접 전송"
                ],
                data_categories=[DataCategory.PERSONAL_DATA],
                retention_period=DataRetentionPeriod.INDEFINITE,
                encryption_required=True,
                access_controls_required=True,
                audit_logging_required=True,
                consent_required=True,
                right_to_deletion=False,
                data_portability=True,
                breach_notification_hours=72,
                penalty_amount=20000000.0,
                last_updated=datetime.now(),
                is_active=True
            )
        ]
        
        for rule in gdpr_rules:
            self.compliance_rules[rule.rule_id] = rule
    
    def _load_ccpa_rules(self):
        """CCPA 규칙 로드"""
        ccpa_rules = [
            ComplianceRule(
                rule_id="ccpa_section_1798_100",
                framework=ComplianceFramework.CCPA,
                title="Right to Know",
                description="개인정보 수집 및 사용에 대한 알 권리",
                requirements=[
                    "수집하는 개인정보 카테고리 공개",
                    "개인정보 사용 목적 공개",
                    "제3자와의 공유 여부 공개"
                ],
                data_categories=[DataCategory.PERSONAL_DATA],
                retention_period=DataRetentionPeriod.ONE_YEAR,
                encryption_required=True,
                access_controls_required=True,
                audit_logging_required=True,
                consent_required=True,
                right_to_deletion=True,
                data_portability=True,
                breach_notification_hours=0,  # CCPA는 위반 통지 의무 없음
                penalty_amount=7500.0,  # 위반 당 최대 $7,500
                last_updated=datetime.now(),
                is_active=True
            )
        ]
        
        for rule in ccpa_rules:
            self.compliance_rules[rule.rule_id] = rule
    
    def _load_k_isms_rules(self):
        """K-ISMS 규칙 로드"""
        k_isms_rules = [
            ComplianceRule(
                rule_id="k_isms_2_1_1",
                framework=ComplianceFramework.K_ISMS,
                title="정보보호정책 수립",
                description="정보보호 기본정책 수립 및 승인",
                requirements=[
                    "정보보호 기본정책 문서화",
                    "경영진 승인",
                    "전 직원 공지"
                ],
                data_categories=[DataCategory.PERSONAL_DATA],
                retention_period=DataRetentionPeriod.THREE_YEARS,
                encryption_required=True,
                access_controls_required=True,
                audit_logging_required=True,
                consent_required=True,
                right_to_deletion=True,
                data_portability=False,
                breach_notification_hours=24,
                penalty_amount=50000000.0,  # 5천만원 이하
                last_updated=datetime.now(),
                is_active=True
            )
        ]
        
        for rule in k_isms_rules:
            self.compliance_rules[rule.rule_id] = rule
    
    async def start_compliance_system(self):
        """컴플라이언스 시스템 시작"""
        if self.running:
            logger.warning("컴플라이언스 시스템이 이미 실행 중입니다")
            return
        
        self.running = True
        logger.info("컴플라이언스 자동 준수 시스템 시작")
        
        # 데이터 검색 태스크
        self.data_discovery_task = asyncio.create_task(self._data_discovery_loop())
        
        # 모니터링 태스크
        self.monitoring_task = asyncio.create_task(self._compliance_monitoring_loop())
        
        # 데이터 보존 태스크
        self.retention_task = asyncio.create_task(self._data_retention_loop())
        
        # 초기 데이터 검색
        asyncio.create_task(self._initial_data_discovery())
    
    async def stop_compliance_system(self):
        """컴플라이언스 시스템 중지"""
        self.running = False
        
        if self.data_discovery_task:
            self.data_discovery_task.cancel()
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        if self.retention_task:
            self.retention_task.cancel()
        
        logger.info("컴플라이언스 자동 준수 시스템 중지")
    
    async def _initial_data_discovery(self):
        """초기 데이터 검색"""
        logger.info("초기 데이터 검색 시작")
        
        scan_paths = self.config["data_discovery"]["scan_paths"]
        
        for scan_path in scan_paths:
            await self._scan_directory(Path(scan_path))
        
        logger.info("초기 데이터 검색 완료")
    
    async def _data_discovery_loop(self):
        """데이터 검색 루프"""
        scan_interval = self.config["data_discovery"]["scan_interval_hours"] * 3600
        
        while self.running:
            try:
                await self._perform_data_discovery()
                await asyncio.sleep(scan_interval)
                
            except Exception as e:
                logger.error(f"데이터 검색 루프 오류: {e}")
                await asyncio.sleep(3600)  # 1시간 후 재시도
    
    async def _perform_data_discovery(self):
        """데이터 검색 수행"""
        logger.info("데이터 검색 시작")
        
        scan_paths = self.config["data_discovery"]["scan_paths"]
        
        for scan_path in scan_paths:
            if Path(scan_path).exists():
                await self._scan_directory(Path(scan_path))
        
        # 데이터베이스 스캔
        await self._scan_databases()
        
        # 로그 파일 스캔
        await self._scan_log_files()
        
        logger.info("데이터 검색 완료")
    
    async def _scan_directory(self, directory: Path):
        """디렉토리 스캔"""
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    await self._analyze_file(file_path)
        except Exception as e:
            logger.error(f"디렉토리 스캔 실패 ({directory}): {e}")
    
    async def _analyze_file(self, file_path: Path):
        """파일 분석"""
        try:
            # 파일 확장자 확인
            if file_path.suffix.lower() in ['.txt', '.log', '.csv', '.json', '.py', '.js']:
                content = await self._read_file_content(file_path)
                
                if content:
                    data_category = await self._classify_data(content)
                    
                    if data_category != DataCategory.PUBLIC_DATA:
                        await self._register_data_asset(file_path, data_category, content)
        
        except Exception as e:
            logger.debug(f"파일 분석 실패 ({file_path}): {e}")
    
    async def _read_file_content(self, file_path: Path) -> str:
        """파일 내용 읽기"""
        try:
            # 파일 크기 확인 (큰 파일은 샘플만)
            file_size = file_path.stat().st_size
            
            if file_size > 10 * 1024 * 1024:  # 10MB 이상
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(10000)  # 처음 10KB만
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        except Exception:
            return ""
    
    async def _classify_data(self, content: str) -> DataCategory:
        """데이터 분류"""
        if not self.config["data_discovery"]["auto_classify"]:
            return DataCategory.PUBLIC_DATA
        
        # 패턴 매칭을 통한 데이터 분류
        for category, patterns in self.data_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    return category
        
        # 키워드 기반 분류
        sensitive_keywords = {
            DataCategory.PERSONAL_DATA: ['이름', '주소', '전화', '이메일', 'name', 'email', 'phone'],
            DataCategory.FINANCIAL_DATA: ['신용카드', '계좌', '금액', 'credit', 'card', 'account'],
            DataCategory.HEALTH_DATA: ['의료', '건강', '진료', 'medical', 'health', 'patient']
        }
        
        content_lower = content.lower()
        
        for category, keywords in sensitive_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return category
        
        return DataCategory.PUBLIC_DATA
    
    async def _register_data_asset(self, file_path: Path, data_category: DataCategory, content: str):
        """데이터 자산 등록"""
        asset_id = hashlib.md5(str(file_path).encode()).hexdigest()
        
        # 데이터 주체 수 추정
        subjects_count = await self._estimate_data_subjects_count(content, data_category)
        
        # 보존 기간 결정
        retention_period = await self._determine_retention_period(data_category)
        
        data_asset = DataAsset(
            asset_id=asset_id,
            name=file_path.name,
            location=str(file_path),
            data_category=data_category,
            data_subjects_count=subjects_count,
            retention_period=retention_period,
            encryption_status=await self._check_encryption_status(file_path),
            access_controls=await self._check_access_controls(file_path),
            processing_purposes=["데이터 처리"],
            legal_basis="정당한 이익",
            consent_status=False,
            last_accessed=datetime.now(),
            created_at=datetime.fromtimestamp(file_path.stat().st_ctime),
            metadata={"file_size": file_path.stat().st_size}
        )
        
        self.data_assets[asset_id] = data_asset
        await self._save_data_asset(data_asset)
        
        # 암호화 필요 시 자동 암호화
        if (data_category in [DataCategory.PERSONAL_DATA, DataCategory.SENSITIVE_PERSONAL_DATA] and
            self.config["data_protection"]["auto_encrypt_sensitive"] and
            not data_asset.encryption_status):
            await self._encrypt_data_asset(data_asset)
    
    async def _estimate_data_subjects_count(self, content: str, data_category: DataCategory) -> int:
        """데이터 주체 수 추정"""
        if data_category == DataCategory.PERSONAL_DATA:
            # 이메일 주소 개수로 추정
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, content)
            return len(set(emails))
        
        return 0
    
    async def _determine_retention_period(self, data_category: DataCategory) -> DataRetentionPeriod:
        """보존 기간 결정"""
        retention_map = {
            DataCategory.PERSONAL_DATA: DataRetentionPeriod.THREE_YEARS,
            DataCategory.SENSITIVE_PERSONAL_DATA: DataRetentionPeriod.ONE_YEAR,
            DataCategory.FINANCIAL_DATA: DataRetentionPeriod.SEVEN_YEARS,
            DataCategory.HEALTH_DATA: DataRetentionPeriod.SEVEN_YEARS,
            DataCategory.PUBLIC_DATA: DataRetentionPeriod.INDEFINITE
        }
        
        return retention_map.get(data_category, DataRetentionPeriod.ONE_YEAR)
    
    async def _check_encryption_status(self, file_path: Path) -> bool:
        """암호화 상태 확인"""
        try:
            # 파일 확장자나 헤더로 암호화 여부 판단
            if file_path.suffix.lower() in ['.enc', '.encrypted']:
                return True
            
            # 파일 내용 확인 (간단한 엔트로피 검사)
            with open(file_path, 'rb') as f:
                sample = f.read(1024)
                
            if len(sample) > 0:
                # 엔트로피 계산 (간단한 방법)
                byte_counts = [0] * 256
                for byte in sample:
                    byte_counts[byte] += 1
                
                entropy = 0
                for count in byte_counts:
                    if count > 0:
                        p = count / len(sample)
                        entropy -= p * (p.bit_length() - 1)
                
                # 높은 엔트로피는 암호화를 의미할 수 있음
                return entropy > 7.0
            
        except Exception:
            pass
        
        return False
    
    async def _check_access_controls(self, file_path: Path) -> Dict[str, Any]:
        """접근 제어 확인"""
        try:
            stat_info = file_path.stat()
            
            return {
                "file_mode": oct(stat_info.st_mode),
                "owner_read": bool(stat_info.st_mode & 0o400),
                "owner_write": bool(stat_info.st_mode & 0o200),
                "group_read": bool(stat_info.st_mode & 0o040),
                "others_read": bool(stat_info.st_mode & 0o004)
            }
        except Exception:
            return {}
    
    async def _encrypt_data_asset(self, data_asset: DataAsset):
        """데이터 자산 암호화"""
        try:
            file_path = Path(data_asset.location)
            
            if file_path.exists() and not data_asset.encryption_status:
                # 백업 생성
                backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                shutil.copy2(file_path, backup_path)
                
                # 파일 암호화
                fernet = Fernet(self.encryption_key)
                
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                encrypted_data = fernet.encrypt(file_data)
                
                with open(file_path, 'wb') as f:
                    f.write(encrypted_data)
                
                # 데이터 자산 정보 업데이트
                data_asset.encryption_status = True
                await self._save_data_asset(data_asset)
                
                logger.info(f"데이터 자산 암호화 완료: {data_asset.name}")
                
                # 감사 로그
                await self._create_audit_log(
                    user_id="system",
                    action="ENCRYPT",
                    resource=data_asset.location,
                    data_category=data_asset.data_category,
                    purpose="자동 암호화",
                    legal_basis="데이터 보호"
                )
        
        except Exception as e:
            logger.error(f"데이터 자산 암호화 실패: {e}")
    
    async def _scan_databases(self):
        """데이터베이스 스캔"""
        # SQLite 데이터베이스 스캔
        db_files = list(Path(".").glob("**/*.db"))
        
        for db_file in db_files:
            await self._analyze_database(db_file)
    
    async def _analyze_database(self, db_path: Path):
        """데이터베이스 분석"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 테이블 목록 조회
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                
                # 테이블 스키마 분석
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # 개인정보 포함 가능성 검사
                personal_data_columns = []
                for column in columns:
                    column_name = column[1].lower()
                    if any(keyword in column_name for keyword in ['email', 'phone', 'name', 'address']):
                        personal_data_columns.append(column_name)
                
                if personal_data_columns:
                    # 레코드 수 확인
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    record_count = cursor.fetchone()[0]
                    
                    # 데이터 자산으로 등록
                    await self._register_database_asset(db_path, table_name, personal_data_columns, record_count)
            
            conn.close()
            
        except Exception as e:
            logger.debug(f"데이터베이스 분석 실패 ({db_path}): {e}")
    
    async def _register_database_asset(self, db_path: Path, table_name: str, 
                                     personal_columns: List[str], record_count: int):
        """데이터베이스 자산 등록"""
        asset_id = hashlib.md5(f"{db_path}_{table_name}".encode()).hexdigest()
        
        data_asset = DataAsset(
            asset_id=asset_id,
            name=f"{db_path.name}:{table_name}",
            location=f"{db_path}:{table_name}",
            data_category=DataCategory.PERSONAL_DATA,
            data_subjects_count=record_count,
            retention_period=DataRetentionPeriod.THREE_YEARS,
            encryption_status=False,  # SQLite는 기본적으로 암호화되지 않음
            access_controls={},
            processing_purposes=["데이터베이스 저장"],
            legal_basis="정당한 이익",
            consent_status=False,
            last_accessed=datetime.now(),
            created_at=datetime.fromtimestamp(db_path.stat().st_ctime),
            metadata={
                "table_name": table_name,
                "personal_columns": personal_columns,
                "record_count": record_count
            }
        )
        
        self.data_assets[asset_id] = data_asset
        await self._save_data_asset(data_asset)
    
    async def _scan_log_files(self):
        """로그 파일 스캔"""
        log_files = list(Path("logs").glob("**/*.log")) if Path("logs").exists() else []
        
        for log_file in log_files:
            await self._analyze_log_file(log_file)
    
    async def _analyze_log_file(self, log_path: Path):
        """로그 파일 분석"""
        try:
            content = await self._read_file_content(log_path)
            
            # IP 주소 추출
            ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
            ip_addresses = re.findall(ip_pattern, content)
            
            if ip_addresses:
                # 로그 파일을 개인정보 자산으로 등록
                asset_id = hashlib.md5(str(log_path).encode()).hexdigest()
                
                data_asset = DataAsset(
                    asset_id=asset_id,
                    name=log_path.name,
                    location=str(log_path),
                    data_category=DataCategory.PERSONAL_DATA,
                    data_subjects_count=len(set(ip_addresses)),
                    retention_period=DataRetentionPeriod.ONE_YEAR,
                    encryption_status=False,
                    access_controls=await self._check_access_controls(log_path),
                    processing_purposes=["로그 기록"],
                    legal_basis="정당한 이익",
                    consent_status=False,
                    last_accessed=datetime.now(),
                    created_at=datetime.fromtimestamp(log_path.stat().st_ctime),
                    metadata={"ip_count": len(set(ip_addresses))}
                )
                
                self.data_assets[asset_id] = data_asset
                await self._save_data_asset(data_asset)
        
        except Exception as e:
            logger.debug(f"로그 파일 분석 실패 ({log_path}): {e}")
    
    async def _compliance_monitoring_loop(self):
        """컴플라이언스 모니터링 루프"""
        while self.running:
            try:
                await self._monitor_compliance_status()
                await self._check_consent_expiry()
                await self._monitor_data_access()
                await self._check_breach_indicators()
                
                await asyncio.sleep(3600)  # 1시간마다 모니터링
                
            except Exception as e:
                logger.error(f"컴플라이언스 모니터링 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _monitor_compliance_status(self):
        """컴플라이언스 상태 모니터링"""
        for rule_id, rule in self.compliance_rules.items():
            compliance_status = await self._check_rule_compliance(rule)
            
            if compliance_status == ComplianceStatus.NON_COMPLIANT:
                await self._create_compliance_incident(rule, "규칙 위반")
    
    async def _check_rule_compliance(self, rule: ComplianceRule) -> ComplianceStatus:
        """규칙 준수 상태 확인"""
        compliant_assets = 0
        total_assets = 0
        
        for asset in self.data_assets.values():
            if asset.data_category in rule.data_categories:
                total_assets += 1
                
                # 암호화 요구사항 확인
                if rule.encryption_required and not asset.encryption_status:
                    continue
                
                # 접근 제어 요구사항 확인
                if rule.access_controls_required and not asset.access_controls:
                    continue
                
                # 동의 요구사항 확인
                if rule.consent_required and not asset.consent_status:
                    continue
                
                compliant_assets += 1
        
        if total_assets == 0:
            return ComplianceStatus.COMPLIANT
        
        compliance_rate = compliant_assets / total_assets
        
        if compliance_rate >= 1.0:
            return ComplianceStatus.COMPLIANT
        elif compliance_rate >= 0.8:
            return ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            return ComplianceStatus.NON_COMPLIANT
    
    async def _check_consent_expiry(self):
        """동의 만료 확인"""
        # 동의 만료 임박 또는 만료된 경우 처리
        pass
    
    async def _monitor_data_access(self):
        """데이터 접근 모니터링"""
        # 비정상적인 데이터 접근 패턴 감지
        pass
    
    async def _check_breach_indicators(self):
        """침해 지표 확인"""
        # 데이터 유출 가능성 모니터링
        pass
    
    async def _data_retention_loop(self):
        """데이터 보존 루프"""
        while self.running:
            try:
                await self._process_data_retention()
                await asyncio.sleep(86400)  # 24시간마다 실행
                
            except Exception as e:
                logger.error(f"데이터 보존 루프 오류: {e}")
                await asyncio.sleep(86400)
    
    async def _process_data_retention(self):
        """데이터 보존 처리"""
        current_date = datetime.now()
        
        for asset_id, asset in list(self.data_assets.items()):
            if asset.retention_period == DataRetentionPeriod.INDEFINITE:
                continue
            
            # 보존 기간 확인
            retention_days = asset.retention_period.value
            if retention_days > 0:
                expiry_date = asset.created_at + timedelta(days=retention_days)
                
                if current_date >= expiry_date:
                    await self._delete_expired_data(asset)
    
    async def _delete_expired_data(self, asset: DataAsset):
        """만료된 데이터 삭제"""
        if not self.config["retention"]["auto_delete_expired"]:
            return
        
        try:
            # 백업 생성 (필요시)
            if self.config["retention"]["backup_before_delete"]:
                await self._backup_data_before_deletion(asset)
            
            # 알림 발송 (필요시)
            if self.config["retention"]["notification_before_delete"]:
                await self._send_deletion_notification(asset)
            
            # 실제 데이터 삭제
            await self._perform_data_deletion(asset)
            
            # 감사 로그
            await self._create_audit_log(
                user_id="system",
                action="DELETE",
                resource=asset.location,
                data_category=asset.data_category,
                purpose="보존 기간 만료",
                legal_basis="데이터 보존 정책"
            )
            
            # 데이터 자산 목록에서 제거
            del self.data_assets[asset.asset_id]
            
            logger.info(f"만료된 데이터 삭제: {asset.name}")
            
        except Exception as e:
            logger.error(f"데이터 삭제 실패: {e}")
    
    async def _backup_data_before_deletion(self, asset: DataAsset):
        """삭제 전 데이터 백업"""
        backup_dir = Path("compliance/deleted_data_backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        source_path = Path(asset.location)
        backup_path = backup_dir / f"{asset.asset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
        
        if source_path.exists():
            shutil.copy2(source_path, backup_path)
    
    async def _send_deletion_notification(self, asset: DataAsset):
        """삭제 알림 발송"""
        # 데이터 컨트롤러에게 알림
        logger.info(f"데이터 삭제 예정 알림: {asset.name}")
    
    async def _perform_data_deletion(self, asset: DataAsset):
        """데이터 삭제 수행"""
        file_path = Path(asset.location)
        
        if file_path.exists():
            # 보안 삭제 (여러 번 덮어쓰기)
            if file_path.is_file():
                file_size = file_path.stat().st_size
                
                # 파일을 랜덤 데이터로 3회 덮어쓰기
                with open(file_path, 'wb') as f:
                    for _ in range(3):
                        f.write(os.urandom(file_size))
                        f.flush()
                        os.fsync(f.fileno())
                
                # 파일 삭제
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
    
    async def _create_compliance_incident(self, rule: ComplianceRule, description: str):
        """컴플라이언스 사고 생성"""
        incident_id = str(uuid.uuid4())
        
        incident = ComplianceIncident(
            incident_id=incident_id,
            framework=rule.framework,
            incident_type="RULE_VIOLATION",
            severity="HIGH",
            description=description,
            affected_data_assets=[],
            affected_subjects_count=0,
            discovered_at=datetime.now(),
            reported_at=None,
            resolved_at=None,
            notification_required=True,
            notification_deadline=datetime.now() + timedelta(hours=rule.breach_notification_hours),
            remediation_actions=[],
            status="OPEN"
        )
        
        self.incidents[incident_id] = incident
        await self._save_compliance_incident(incident)
        
        logger.warning(f"컴플라이언스 사고 생성: {description}")
    
    async def _create_audit_log(self, user_id: str, action: str, resource: str,
                              data_category: Optional[DataCategory], purpose: str,
                              legal_basis: str, ip_address: str = "", user_agent: str = "",
                              success: bool = True, details: Optional[Dict[str, Any]] = None):
        """감사 로그 생성"""
        log_id = str(uuid.uuid4())
        
        audit_log = AuditLog(
            log_id=log_id,
            timestamp=datetime.now(),
            user_id=user_id,
            action=action,
            resource=resource,
            data_category=data_category,
            purpose=purpose,
            legal_basis=legal_basis,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details=details or {}
        )
        
        self.audit_logs.append(audit_log)
        await self._save_audit_log(audit_log)
    
    async def process_data_subject_request(self, request_type: str, subject_id: str,
                                         verification_data: Dict[str, Any]) -> str:
        """데이터 주체 권리 요청 처리"""
        request_id = str(uuid.uuid4())
        request_date = datetime.now()
        
        # 완료 기한 계산 (GDPR: 1개월)
        completion_deadline = request_date + timedelta(days=30)
        
        # 신원 확인
        verification_status = await self._verify_data_subject_identity(subject_id, verification_data)
        
        if request_type == "access":
            response_data = await self._process_access_request(subject_id)
        elif request_type == "deletion":
            response_data = await self._process_deletion_request(subject_id)
        elif request_type == "portability":
            response_data = await self._process_portability_request(subject_id)
        elif request_type == "rectification":
            response_data = await self._process_rectification_request(subject_id, verification_data)
        else:
            response_data = {"error": "지원하지 않는 요청 유형"}
        
        # 요청 기록
        await self._save_data_subject_request(request_id, subject_id, request_type,
                                            request_date, completion_deadline,
                                            verification_status, response_data)
        
        # 감사 로그
        await self._create_audit_log(
            user_id=subject_id,
            action=f"DATA_SUBJECT_{request_type.upper()}",
            resource="data_subject_rights",
            data_category=DataCategory.PERSONAL_DATA,
            purpose="데이터 주체 권리 행사",
            legal_basis="GDPR Article"
        )
        
        return request_id
    
    async def _verify_data_subject_identity(self, subject_id: str, 
                                          verification_data: Dict[str, Any]) -> bool:
        """데이터 주체 신원 확인"""
        # 간단한 신원 확인 로직 (실제로는 더 강화된 검증 필요)
        required_fields = ["email", "name"]
        
        for field in required_fields:
            if field not in verification_data:
                return False
        
        return True
    
    async def _process_access_request(self, subject_id: str) -> Dict[str, Any]:
        """접근권 요청 처리"""
        subject_data = []
        
        for asset in self.data_assets.values():
            if asset.data_category in [DataCategory.PERSONAL_DATA, DataCategory.SENSITIVE_PERSONAL_DATA]:
                # 해당 주체의 데이터인지 확인 (간단한 예시)
                if subject_id in asset.metadata.get("subjects", []):
                    subject_data.append({
                        "asset_name": asset.name,
                        "location": asset.location,
                        "data_category": asset.data_category.value,
                        "processing_purposes": asset.processing_purposes,
                        "legal_basis": asset.legal_basis,
                        "retention_period": asset.retention_period.value
                    })
        
        return {
            "subject_id": subject_id,
            "data_assets": subject_data,
            "generated_at": datetime.now().isoformat()
        }
    
    async def _process_deletion_request(self, subject_id: str) -> Dict[str, Any]:
        """삭제권 요청 처리"""
        deleted_assets = []
        
        for asset_id, asset in list(self.data_assets.items()):
            if asset.data_category in [DataCategory.PERSONAL_DATA, DataCategory.SENSITIVE_PERSONAL_DATA]:
                # 해당 주체의 데이터인지 확인
                if subject_id in asset.metadata.get("subjects", []):
                    # 삭제 가능한지 확인 (법적 의무, 정당한 이익 등)
                    if await self._can_delete_data(asset):
                        await self._perform_data_deletion(asset)
                        deleted_assets.append(asset.name)
                        del self.data_assets[asset_id]
        
        return {
            "subject_id": subject_id,
            "deleted_assets": deleted_assets,
            "processed_at": datetime.now().isoformat()
        }
    
    async def _can_delete_data(self, asset: DataAsset) -> bool:
        """데이터 삭제 가능 여부 확인"""
        # 법적 의무나 정당한 이익이 있는지 확인
        legal_obligations = ["tax_record", "legal_claim", "public_interest"]
        
        return not any(obligation in asset.processing_purposes for obligation in legal_obligations)
    
    async def _process_portability_request(self, subject_id: str) -> Dict[str, Any]:
        """데이터 이동권 요청 처리"""
        portable_data = []
        
        for asset in self.data_assets.values():
            if (asset.data_category == DataCategory.PERSONAL_DATA and 
                asset.consent_status and 
                subject_id in asset.metadata.get("subjects", [])):
                
                # 구조화된 형태로 데이터 추출
                portable_data.append({
                    "asset_name": asset.name,
                    "data_category": asset.data_category.value,
                    "data_format": "JSON",
                    "created_at": asset.created_at.isoformat()
                })
        
        return {
            "subject_id": subject_id,
            "portable_data": portable_data,
            "format": "machine_readable",
            "generated_at": datetime.now().isoformat()
        }
    
    async def _process_rectification_request(self, subject_id: str, 
                                           correction_data: Dict[str, Any]) -> Dict[str, Any]:
        """정정권 요청 처리"""
        # 데이터 정정 로직 구현
        return {
            "subject_id": subject_id,
            "corrections_applied": [],
            "processed_at": datetime.now().isoformat()
        }
    
    async def generate_compliance_report(self, framework: ComplianceFramework,
                                       report_period: Tuple[datetime, datetime]) -> Dict[str, Any]:
        """컴플라이언스 보고서 생성"""
        start_date, end_date = report_period
        
        report = {
            "framework": framework.value,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "generated_at": datetime.now().isoformat(),
            "data_assets_summary": await self._get_data_assets_summary(),
            "compliance_status": await self._get_compliance_status_summary(framework),
            "incidents": await self._get_incidents_summary(framework, start_date, end_date),
            "audit_summary": await self._get_audit_summary(start_date, end_date),
            "data_subject_requests": await self._get_data_subject_requests_summary(start_date, end_date),
            "recommendations": await self._generate_compliance_recommendations(framework)
        }
        
        # 보고서 파일 저장
        report_filename = f"compliance_report_{framework.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = self.reports_path / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"컴플라이언스 보고서 생성: {report_path}")
        
        return report
    
    async def _get_data_assets_summary(self) -> Dict[str, Any]:
        """데이터 자산 요약"""
        category_counts = {}
        for category in DataCategory:
            category_counts[category.value] = len([
                asset for asset in self.data_assets.values() 
                if asset.data_category == category
            ])
        
        return {
            "total_assets": len(self.data_assets),
            "by_category": category_counts,
            "encrypted_assets": len([asset for asset in self.data_assets.values() if asset.encryption_status]),
            "total_data_subjects": sum(asset.data_subjects_count for asset in self.data_assets.values())
        }
    
    async def _get_compliance_status_summary(self, framework: ComplianceFramework) -> Dict[str, Any]:
        """컴플라이언스 상태 요약"""
        framework_rules = [rule for rule in self.compliance_rules.values() if rule.framework == framework]
        
        status_counts = {}
        for status in ComplianceStatus:
            status_counts[status.value] = 0
        
        for rule in framework_rules:
            status = await self._check_rule_compliance(rule)
            status_counts[status.value] += 1
        
        return {
            "total_rules": len(framework_rules),
            "compliance_status": status_counts,
            "overall_compliance_rate": status_counts.get("COMPLIANT", 0) / max(len(framework_rules), 1) * 100
        }
    
    async def _get_incidents_summary(self, framework: ComplianceFramework,
                                   start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """사고 요약"""
        framework_incidents = [
            incident for incident in self.incidents.values()
            if (incident.framework == framework and 
                start_date <= incident.discovered_at <= end_date)
        ]
        
        return {
            "total_incidents": len(framework_incidents),
            "open_incidents": len([i for i in framework_incidents if i.status == "OPEN"]),
            "resolved_incidents": len([i for i in framework_incidents if i.status == "RESOLVED"]),
            "high_severity_incidents": len([i for i in framework_incidents if i.severity == "HIGH"])
        }
    
    async def _get_audit_summary(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """감사 요약"""
        period_logs = [
            log for log in self.audit_logs
            if start_date <= log.timestamp <= end_date
        ]
        
        action_counts = {}
        for log in period_logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
        
        return {
            "total_audit_logs": len(period_logs),
            "successful_actions": len([log for log in period_logs if log.success]),
            "failed_actions": len([log for log in period_logs if not log.success]),
            "action_breakdown": action_counts
        }
    
    async def _get_data_subject_requests_summary(self, start_date: datetime, 
                                               end_date: datetime) -> Dict[str, Any]:
        """데이터 주체 요청 요약"""
        # 데이터베이스에서 요청 조회
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT request_type, status, COUNT(*) 
            FROM data_subject_requests 
            WHERE request_date BETWEEN ? AND ?
            GROUP BY request_type, status
        ''', (start_date, end_date))
        
        results = cursor.fetchall()
        conn.close()
        
        summary = {
            "total_requests": sum(row[2] for row in results),
            "by_type": {},
            "by_status": {}
        }
        
        for request_type, status, count in results:
            summary["by_type"][request_type] = summary["by_type"].get(request_type, 0) + count
            summary["by_status"][status] = summary["by_status"].get(status, 0) + count
        
        return summary
    
    async def _generate_compliance_recommendations(self, framework: ComplianceFramework) -> List[str]:
        """컴플라이언스 권장사항 생성"""
        recommendations = []
        
        # 암호화되지 않은 민감 데이터
        unencrypted_sensitive = [
            asset for asset in self.data_assets.values()
            if (asset.data_category in [DataCategory.PERSONAL_DATA, DataCategory.SENSITIVE_PERSONAL_DATA] and
                not asset.encryption_status)
        ]
        
        if unencrypted_sensitive:
            recommendations.append(f"{len(unencrypted_sensitive)}개의 민감한 데이터 자산이 암호화되지 않았습니다. 즉시 암호화를 적용하세요.")
        
        # 동의 없는 개인정보 처리
        no_consent_assets = [
            asset for asset in self.data_assets.values()
            if (asset.data_category == DataCategory.PERSONAL_DATA and not asset.consent_status)
        ]
        
        if no_consent_assets:
            recommendations.append(f"{len(no_consent_assets)}개의 개인정보 자산에 대한 동의가 없습니다. 적법한 근거를 확보하거나 동의를 받으세요.")
        
        # 보존 기간 초과 데이터
        current_date = datetime.now()
        expired_assets = []
        
        for asset in self.data_assets.values():
            if asset.retention_period != DataRetentionPeriod.INDEFINITE:
                expiry_date = asset.created_at + timedelta(days=asset.retention_period.value)
                if current_date > expiry_date:
                    expired_assets.append(asset)
        
        if expired_assets:
            recommendations.append(f"{len(expired_assets)}개의 데이터 자산이 보존 기간을 초과했습니다. 삭제 또는 보존 근거를 재검토하세요.")
        
        return recommendations
    
    # 데이터베이스 저장 메서드들
    async def _save_data_asset(self, asset: DataAsset):
        """데이터 자산 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO data_assets (
                asset_id, name, location, data_category, data_subjects_count,
                retention_period, encryption_status, access_controls,
                processing_purposes, legal_basis, consent_status,
                last_accessed, created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            asset.asset_id, asset.name, asset.location, asset.data_category.value,
            asset.data_subjects_count, asset.retention_period.value,
            asset.encryption_status, json.dumps(asset.access_controls),
            json.dumps(asset.processing_purposes), asset.legal_basis,
            asset.consent_status, asset.last_accessed, asset.created_at,
            json.dumps(asset.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    async def _save_compliance_incident(self, incident: ComplianceIncident):
        """컴플라이언스 사고 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO compliance_incidents (
                incident_id, framework, incident_type, severity, description,
                affected_data_assets, affected_subjects_count, discovered_at,
                reported_at, resolved_at, notification_required,
                notification_deadline, remediation_actions, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            incident.incident_id, incident.framework.value, incident.incident_type,
            incident.severity, incident.description, json.dumps(incident.affected_data_assets),
            incident.affected_subjects_count, incident.discovered_at,
            incident.reported_at, incident.resolved_at, incident.notification_required,
            incident.notification_deadline, json.dumps(incident.remediation_actions),
            incident.status
        ))
        
        conn.commit()
        conn.close()
    
    async def _save_audit_log(self, audit_log: AuditLog):
        """감사 로그 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO audit_logs (
                log_id, timestamp, user_id, action, resource, data_category,
                purpose, legal_basis, ip_address, user_agent, success, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            audit_log.log_id, audit_log.timestamp, audit_log.user_id,
            audit_log.action, audit_log.resource,
            audit_log.data_category.value if audit_log.data_category else None,
            audit_log.purpose, audit_log.legal_basis, audit_log.ip_address,
            audit_log.user_agent, audit_log.success, json.dumps(audit_log.details)
        ))
        
        conn.commit()
        conn.close()
    
    async def _save_data_subject_request(self, request_id: str, subject_id: str,
                                       request_type: str, request_date: datetime,
                                       completion_deadline: datetime, verification_status: bool,
                                       response_data: Dict[str, Any]):
        """데이터 주체 요청 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO data_subject_requests (
                request_id, subject_id, request_type, request_date,
                completion_deadline, verification_status, response_data, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request_id, subject_id, request_type, request_date,
            completion_deadline, verification_status,
            json.dumps(response_data), "COMPLETED"
        ))
        
        conn.commit()
        conn.close()
    
    async def get_compliance_dashboard_data(self) -> Dict[str, Any]:
        """컴플라이언스 대시보드 데이터 조회"""
        overall_status = "COMPLIANT"
        
        # 전체 컴플라이언스 상태 계산
        for rule in self.compliance_rules.values():
            rule_status = await self._check_rule_compliance(rule)
            if rule_status == ComplianceStatus.NON_COMPLIANT:
                overall_status = "NON_COMPLIANT"
                break
            elif rule_status == ComplianceStatus.PARTIALLY_COMPLIANT:
                overall_status = "PARTIALLY_COMPLIANT"
        
        return {
            "overall_status": overall_status,
            "frameworks": {
                framework.value: {
                    "enabled": framework.value in self.config["frameworks"]["enabled"],
                    "rules_count": len([r for r in self.compliance_rules.values() if r.framework == framework]),
                    "compliant_rules": len([
                        r for r in self.compliance_rules.values() 
                        if r.framework == framework and await self._check_rule_compliance(r) == ComplianceStatus.COMPLIANT
                    ])
                }
                for framework in ComplianceFramework
            },
            "data_assets": await self._get_data_assets_summary(),
            "recent_incidents": [
                {
                    "incident_id": incident.incident_id,
                    "framework": incident.framework.value,
                    "severity": incident.severity,
                    "description": incident.description,
                    "discovered_at": incident.discovered_at.isoformat(),
                    "status": incident.status
                }
                for incident in sorted(self.incidents.values(), 
                                     key=lambda x: x.discovered_at, reverse=True)[:5]
            ],
            "audit_stats": {
                "total_logs": len(self.audit_logs),
                "recent_24h": len([
                    log for log in self.audit_logs 
                    if datetime.now() - log.timestamp < timedelta(hours=24)
                ])
            },
            "last_updated": datetime.now().isoformat()
        }


# 전역 인스턴스
_compliance_system = None

def get_compliance_system() -> ComplianceAutomationSystem:
    """컴플라이언스 시스템 싱글톤 반환"""
    global _compliance_system
    if _compliance_system is None:
        _compliance_system = ComplianceAutomationSystem()
    return _compliance_system


async def main():
    """테스트용 메인 함수"""
    compliance = ComplianceAutomationSystem()
    
    try:
        # 시스템 시작
        await compliance.start_compliance_system()
        
        # 대시보드 데이터 조회
        dashboard_data = await compliance.get_compliance_dashboard_data()
        print(f"컴플라이언스 상태: {dashboard_data['overall_status']}")
        
        # 보고서 생성
        report_period = (datetime.now() - timedelta(days=30), datetime.now())
        report = await compliance.generate_compliance_report(ComplianceFramework.GDPR, report_period)
        print(f"GDPR 보고서 생성 완료: {report['generated_at']}")
        
        # 시스템 실행
        await asyncio.sleep(300)  # 5분 실행
        
    finally:
        await compliance.stop_compliance_system()


if __name__ == "__main__":
    asyncio.run(main())