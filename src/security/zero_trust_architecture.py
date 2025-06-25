"""
제로 트러스트 아키텍처 구현

"절대 신뢰하지 말고, 항상 검증하라" 원칙에 따른 보안 아키텍처
- 모든 접근 요청을 인증 및 인가
- 최소 권한 원칙
- 마이크로 세그멘테이션
- 지속적인 모니터링
- 동적 정책 적용
"""

import asyncio
import hashlib
import hmac
import jwt
import time
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import ipaddress
import re
import base64
import secrets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import aiohttp
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    """접근 레벨"""
    DENY = "DENY"
    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class ResourceType(Enum):
    """리소스 유형"""
    API = "API"
    DATABASE = "DATABASE"
    FILE_SYSTEM = "FILE_SYSTEM"
    NETWORK = "NETWORK"
    SERVICE = "SERVICE"
    ADMIN_PANEL = "ADMIN_PANEL"


class TrustLevel(Enum):
    """신뢰 수준"""
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERIFIED = 4


class AuthMethod(Enum):
    """인증 방법"""
    PASSWORD = "PASSWORD"
    MFA = "MFA"
    CERTIFICATE = "CERTIFICATE"
    BIOMETRIC = "BIOMETRIC"
    API_KEY = "API_KEY"
    JWT_TOKEN = "JWT_TOKEN"


@dataclass
class Identity:
    """신원 정보"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    permissions: List[str]
    trust_level: TrustLevel
    auth_methods: List[AuthMethod]
    device_fingerprint: Optional[str]
    geo_location: Optional[Dict[str, str]]
    last_login: datetime
    failed_attempts: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class AccessContext:
    """접근 컨텍스트"""
    identity: Identity
    resource: str
    resource_type: ResourceType
    action: str
    source_ip: str
    user_agent: str
    timestamp: datetime
    session_id: str
    device_id: Optional[str]
    geo_location: Optional[Dict[str, str]]
    risk_score: float
    additional_data: Dict[str, Any]


@dataclass
class PolicyRule:
    """정책 규칙"""
    rule_id: str
    name: str
    description: str
    resource_pattern: str
    action_pattern: str
    conditions: Dict[str, Any]
    required_trust_level: TrustLevel
    required_auth_methods: List[AuthMethod]
    required_roles: List[str]
    allowed_ips: List[str]
    blocked_ips: List[str]
    time_restrictions: Optional[Dict[str, Any]]
    access_level: AccessLevel
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime


@dataclass
class AccessLog:
    """접근 로그"""
    log_id: str
    identity_id: str
    resource: str
    action: str
    decision: str
    reason: str
    risk_score: float
    source_ip: str
    user_agent: str
    timestamp: datetime
    session_id: str
    policy_applied: str


class ZeroTrustArchitecture:
    """제로 트러스트 아키텍처"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or Path("config/zero_trust_config.json")
        self.db_path = Path("security/zero_trust.db")
        self.keys_path = Path("security/keys")
        
        # 설정 로드
        self.config = self._load_config()
        
        # 암호화 키 관리
        self.encryption_key = None
        self.signing_key = None
        self.verification_key = None
        
        # 정책 및 신원 관리
        self.policies: Dict[str, PolicyRule] = {}
        self.identities: Dict[str, Identity] = {}
        self.active_sessions: Dict[str, AccessContext] = {}
        
        # 토큰 관리
        self.jwt_secret = secrets.token_urlsafe(32)
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        
        # 위험 평가
        self.risk_factors: Dict[str, float] = {
            "unknown_ip": 0.3,
            "unusual_location": 0.2,
            "failed_attempts": 0.4,
            "suspicious_user_agent": 0.1,
            "off_hours_access": 0.1,
            "privilege_escalation": 0.5,
            "rapid_requests": 0.2
        }
        
        # 캐시 관리
        self.policy_cache: Dict[str, Tuple[PolicyRule, datetime]] = {}
        self.cache_ttl = 300  # 5분
        
        # 초기화
        self._init_database()
        self._init_crypto_keys()
        self._load_default_policies()
        
        logger.info("제로 트러스트 아키텍처 초기화 완료")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "authentication": {
                "require_mfa": True,
                "password_policy": {
                    "min_length": 12,
                    "require_uppercase": True,
                    "require_lowercase": True,
                    "require_numbers": True,
                    "require_symbols": True,
                    "max_age_days": 90
                },
                "session_timeout": 3600,  # 1시간
                "max_failed_attempts": 5,
                "lockout_duration": 1800  # 30분
            },
            "authorization": {
                "default_access_level": "DENY",
                "require_explicit_permissions": True,
                "policy_inheritance": True,
                "dynamic_permissions": True
            },
            "monitoring": {
                "log_all_access": True,
                "real_time_alerts": True,
                "anomaly_detection": True,
                "geo_fencing": True
            },
            "encryption": {
                "algorithm": "AES-256-GCM",
                "key_rotation_days": 30,
                "transport_encryption": True,
                "data_at_rest_encryption": True
            },
            "network_security": {
                "micro_segmentation": True,
                "network_isolation": True,
                "zero_trust_networking": True
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
        
        # 신원 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS identities (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                salt TEXT,
                roles TEXT,
                permissions TEXT,
                trust_level INTEGER,
                auth_methods TEXT,
                device_fingerprint TEXT,
                geo_location TEXT,
                last_login DATETIME,
                failed_attempts INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 정책 규칙 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS policy_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                resource_pattern TEXT NOT NULL,
                action_pattern TEXT NOT NULL,
                conditions TEXT,
                required_trust_level INTEGER,
                required_auth_methods TEXT,
                required_roles TEXT,
                allowed_ips TEXT,
                blocked_ips TEXT,
                time_restrictions TEXT,
                access_level TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 100,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 접근 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_logs (
                log_id TEXT PRIMARY KEY,
                identity_id TEXT,
                resource TEXT NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                risk_score REAL,
                source_ip TEXT,
                user_agent TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                policy_applied TEXT
            )
        ''')
        
        # 세션 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                identity_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                source_ip TEXT,
                user_agent TEXT,
                device_id TEXT
            )
        ''')
        
        # API 키 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL,
                identity_id TEXT NOT NULL,
                name TEXT,
                permissions TEXT,
                rate_limit INTEGER,
                expires_at DATETIME,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("제로 트러스트 데이터베이스 초기화 완료")
    
    def _init_crypto_keys(self):
        """암호화 키 초기화"""
        self.keys_path.mkdir(parents=True, exist_ok=True)
        
        # 데이터 암호화 키
        encryption_key_path = self.keys_path / "encryption.key"
        if encryption_key_path.exists():
            with open(encryption_key_path, 'rb') as f:
                self.encryption_key = f.read()
        else:
            self.encryption_key = secrets.token_bytes(32)  # AES-256
            with open(encryption_key_path, 'wb') as f:
                f.write(self.encryption_key)
        
        # JWT 서명 키
        signing_key_path = self.keys_path / "signing.key"
        if signing_key_path.exists():
            with open(signing_key_path, 'rb') as f:
                self.signing_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
        else:
            self.signing_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            with open(signing_key_path, 'wb') as f:
                f.write(self.signing_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
        
        self.verification_key = self.signing_key.public_key()
        
        logger.info("암호화 키 초기화 완료")
    
    def _load_default_policies(self):
        """기본 정책 로드"""
        default_policies = [
            {
                "rule_id": "deny_all_default",
                "name": "기본 거부 정책",
                "description": "명시적으로 허용되지 않은 모든 접근 거부",
                "resource_pattern": ".*",
                "action_pattern": ".*",
                "conditions": {},
                "required_trust_level": TrustLevel.VERIFIED.value,
                "required_auth_methods": [AuthMethod.PASSWORD.value],
                "required_roles": [],
                "allowed_ips": [],
                "blocked_ips": [],
                "time_restrictions": None,
                "access_level": AccessLevel.DENY.value,
                "is_active": True,
                "priority": 1000
            },
            {
                "rule_id": "admin_full_access",
                "name": "관리자 전체 접근",
                "description": "관리자 역할의 전체 시스템 접근 허용",
                "resource_pattern": ".*",
                "action_pattern": ".*",
                "conditions": {"roles": ["admin", "super_admin"]},
                "required_trust_level": TrustLevel.HIGH.value,
                "required_auth_methods": [AuthMethod.MFA.value],
                "required_roles": ["admin"],
                "allowed_ips": [],
                "blocked_ips": [],
                "time_restrictions": None,
                "access_level": AccessLevel.ADMIN.value,
                "is_active": True,
                "priority": 10
            },
            {
                "rule_id": "api_read_access",
                "name": "API 읽기 접근",
                "description": "인증된 사용자의 API 읽기 접근 허용",
                "resource_pattern": "^/api/.*",
                "action_pattern": "^(GET|HEAD|OPTIONS)$",
                "conditions": {"authenticated": True},
                "required_trust_level": TrustLevel.MEDIUM.value,
                "required_auth_methods": [AuthMethod.JWT_TOKEN.value],
                "required_roles": ["user"],
                "allowed_ips": [],
                "blocked_ips": [],
                "time_restrictions": None,
                "access_level": AccessLevel.READ.value,
                "is_active": True,
                "priority": 50
            },
            {
                "rule_id": "database_admin_only",
                "name": "데이터베이스 관리자 전용",
                "description": "데이터베이스 직접 접근은 관리자만 허용",
                "resource_pattern": "^database:.*",
                "action_pattern": ".*",
                "conditions": {},
                "required_trust_level": TrustLevel.VERIFIED.value,
                "required_auth_methods": [AuthMethod.MFA.value],
                "required_roles": ["db_admin", "super_admin"],
                "allowed_ips": [],
                "blocked_ips": [],
                "time_restrictions": {
                    "business_hours_only": True,
                    "start_time": "09:00",
                    "end_time": "18:00"
                },
                "access_level": AccessLevel.ADMIN.value,
                "is_active": True,
                "priority": 20
            }
        ]
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for policy_data in default_policies:
            cursor.execute('''
                INSERT OR REPLACE INTO policy_rules (
                    rule_id, name, description, resource_pattern, action_pattern,
                    conditions, required_trust_level, required_auth_methods,
                    required_roles, allowed_ips, blocked_ips, time_restrictions,
                    access_level, is_active, priority
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                policy_data["rule_id"], policy_data["name"], policy_data["description"],
                policy_data["resource_pattern"], policy_data["action_pattern"],
                json.dumps(policy_data["conditions"]), policy_data["required_trust_level"],
                json.dumps(policy_data["required_auth_methods"]),
                json.dumps(policy_data["required_roles"]),
                json.dumps(policy_data["allowed_ips"]),
                json.dumps(policy_data["blocked_ips"]),
                json.dumps(policy_data["time_restrictions"]),
                policy_data["access_level"], policy_data["is_active"], policy_data["priority"]
            ))
        
        conn.commit()
        conn.close()
        
        # 메모리에 정책 로드
        self._reload_policies()
        
        logger.info(f"{len(default_policies)}개 기본 정책 로드 완료")
    
    def _reload_policies(self):
        """정책 다시 로드"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM policy_rules WHERE is_active = TRUE
            ORDER BY priority ASC
        ''')
        
        policies = cursor.fetchall()
        conn.close()
        
        self.policies.clear()
        for policy_row in policies:
            rule_id = policy_row[0]
            policy = PolicyRule(
                rule_id=rule_id,
                name=policy_row[1],
                description=policy_row[2],
                resource_pattern=policy_row[3],
                action_pattern=policy_row[4],
                conditions=json.loads(policy_row[5]) if policy_row[5] else {},
                required_trust_level=TrustLevel(policy_row[6]),
                required_auth_methods=[AuthMethod(m) for m in json.loads(policy_row[7])],
                required_roles=json.loads(policy_row[8]),
                allowed_ips=json.loads(policy_row[9]),
                blocked_ips=json.loads(policy_row[10]),
                time_restrictions=json.loads(policy_row[11]) if policy_row[11] else None,
                access_level=AccessLevel(policy_row[12]),
                is_active=bool(policy_row[13]),
                priority=policy_row[14],
                created_at=datetime.fromisoformat(policy_row[15]),
                updated_at=datetime.fromisoformat(policy_row[16])
            )
            self.policies[rule_id] = policy
    
    async def authenticate(self, username: str, password: str, 
                          additional_factors: Optional[Dict[str, Any]] = None,
                          context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str], Optional[Identity]]:
        """
        사용자 인증
        
        Args:
            username: 사용자명
            password: 패스워드
            additional_factors: 추가 인증 요소 (MFA 등)
            context: 접근 컨텍스트 (IP, User-Agent 등)
            
        Returns:
            (인증성공여부, 세션ID, 신원정보)
        """
        try:
            # 사용자 조회
            identity = await self._get_identity(username)
            if not identity:
                await self._log_access_attempt(None, "authentication", "DENY", 
                                             "사용자 없음", context)
                return False, None, None
            
            # 계정 잠금 확인
            if identity.failed_attempts >= self.config["authentication"]["max_failed_attempts"]:
                await self._log_access_attempt(identity.user_id, "authentication", "DENY",
                                             "계정 잠금", context)
                return False, None, None
            
            # 패스워드 검증
            if not await self._verify_password(password, identity):
                await self._increment_failed_attempts(identity.user_id)
                await self._log_access_attempt(identity.user_id, "authentication", "DENY",
                                             "패스워드 불일치", context)
                return False, None, None
            
            # MFA 검증 (필요시)
            if self.config["authentication"]["require_mfa"]:
                if not additional_factors or not await self._verify_mfa(identity, additional_factors):
                    await self._log_access_attempt(identity.user_id, "authentication", "DENY",
                                                 "MFA 실패", context)
                    return False, None, None
            
            # 위험 평가
            risk_score = await self._calculate_authentication_risk(identity, context)
            if risk_score > 0.7:  # 높은 위험
                await self._log_access_attempt(identity.user_id, "authentication", "DENY",
                                             f"높은 위험 점수: {risk_score}", context)
                return False, None, None
            
            # 세션 생성
            session_id = await self._create_session(identity, context)
            
            # 실패 횟수 초기화
            await self._reset_failed_attempts(identity.user_id)
            
            # 신뢰 수준 업데이트
            identity.trust_level = await self._calculate_trust_level(identity, context)
            identity.last_login = datetime.now()
            await self._update_identity(identity)
            
            await self._log_access_attempt(identity.user_id, "authentication", "ALLOW",
                                         "인증 성공", context)
            
            logger.info(f"사용자 인증 성공: {username}")
            return True, session_id, identity
            
        except Exception as e:
            logger.error(f"인증 처리 오류: {e}")
            return False, None, None
    
    async def authorize(self, session_id: str, resource: str, action: str,
                       context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, AccessLevel]:
        """
        접근 권한 검사
        
        Args:
            session_id: 세션 ID
            resource: 접근하려는 리소스
            action: 수행하려는 액션
            context: 추가 컨텍스트
            
        Returns:
            (허용여부, 사유, 접근레벨)
        """
        try:
            # 세션 검증
            identity = await self._validate_session(session_id)
            if not identity:
                await self._log_access(None, resource, action, "DENY", "유효하지 않은 세션", context)
                return False, "유효하지 않은 세션", AccessLevel.DENY
            
            # 접근 컨텍스트 구성
            access_context = AccessContext(
                identity=identity,
                resource=resource,
                resource_type=self._classify_resource(resource),
                action=action,
                source_ip=context.get('source_ip', '') if context else '',
                user_agent=context.get('user_agent', '') if context else '',
                timestamp=datetime.now(),
                session_id=session_id,
                device_id=context.get('device_id') if context else None,
                geo_location=context.get('geo_location') if context else None,
                risk_score=0.0,
                additional_data=context or {}
            )
            
            # 위험 평가
            access_context.risk_score = await self._calculate_access_risk(access_context)
            
            # 정책 평가
            decision, reason, applied_policy = await self._evaluate_policies(access_context)
            
            # 접근 로그
            await self._log_access(
                identity.user_id, resource, action, decision.value, reason, context, 
                access_context.risk_score, applied_policy.rule_id if applied_policy else None
            )
            
            if decision == AccessLevel.DENY:
                logger.warning(f"접근 거부: {identity.username} -> {resource} ({reason})")
            else:
                logger.info(f"접근 허용: {identity.username} -> {resource} ({decision.value})")
            
            return decision != AccessLevel.DENY, reason, decision
            
        except Exception as e:
            logger.error(f"권한 검사 오류: {e}")
            await self._log_access(None, resource, action, "DENY", f"시스템 오류: {str(e)}", context)
            return False, "시스템 오류", AccessLevel.DENY
    
    async def _get_identity(self, username: str) -> Optional[Identity]:
        """신원 정보 조회"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM identities WHERE username = ? AND is_active = TRUE
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Identity(
            user_id=row[0],
            username=row[1],
            email=row[2],
            roles=json.loads(row[5]) if row[5] else [],
            permissions=json.loads(row[6]) if row[6] else [],
            trust_level=TrustLevel(row[7]),
            auth_methods=[AuthMethod(m) for m in json.loads(row[8])] if row[8] else [],
            device_fingerprint=row[9],
            geo_location=json.loads(row[10]) if row[10] else None,
            last_login=datetime.fromisoformat(row[11]) if row[11] else datetime.now(),
            failed_attempts=row[12],
            is_active=bool(row[13]),
            is_verified=bool(row[14]),
            created_at=datetime.fromisoformat(row[15]),
            updated_at=datetime.fromisoformat(row[16])
        )
    
    async def _verify_password(self, password: str, identity: Identity) -> bool:
        """패스워드 검증"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT password_hash, salt FROM identities WHERE user_id = ?
        ''', (identity.user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False
        
        stored_hash, salt = row
        if not stored_hash or not salt:
            return False
        
        # PBKDF2 해시 검증
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 100000
        )
        
        return hmac.compare_digest(
            stored_hash.encode(), 
            base64.b64encode(password_hash).decode()
        )
    
    async def _verify_mfa(self, identity: Identity, factors: Dict[str, Any]) -> bool:
        """다중 인증 검증"""
        # TOTP, SMS, 생체인증 등 구현
        # 현재는 간단한 검증만 구현
        totp_code = factors.get('totp_code')
        if totp_code:
            # TOTP 검증 로직
            expected_code = self._generate_totp(identity.user_id)
            return totp_code == expected_code
        
        return True  # 임시로 항상 성공
    
    def _generate_totp(self, user_id: str) -> str:
        """TOTP 코드 생성 (예시)"""
        # 실제로는 pyotp 등의 라이브러리 사용
        import time
        current_time = int(time.time()) // 30
        secret = f"{user_id}_secret"
        code = hashlib.sha256(f"{secret}_{current_time}".encode()).hexdigest()[:6]
        return code
    
    async def _calculate_authentication_risk(self, identity: Identity, 
                                           context: Optional[Dict[str, Any]]) -> float:
        """인증 위험 평가"""
        risk_score = 0.0
        
        if not context:
            return risk_score
        
        source_ip = context.get('source_ip', '')
        user_agent = context.get('user_agent', '')
        
        # 새로운 IP 주소
        if source_ip and source_ip != identity.device_fingerprint:
            risk_score += self.risk_factors.get("unknown_ip", 0.3)
        
        # 비정상적인 시간대 접근
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:  # 밤 10시 ~ 새벽 6시
            risk_score += self.risk_factors.get("off_hours_access", 0.1)
        
        # 실패 이력
        if identity.failed_attempts > 0:
            risk_score += identity.failed_attempts * 0.1
        
        # 지리적 위치 변화
        current_location = context.get('geo_location')
        if current_location and identity.geo_location:
            if current_location.get('country') != identity.geo_location.get('country'):
                risk_score += self.risk_factors.get("unusual_location", 0.2)
        
        return min(risk_score, 1.0)
    
    async def _calculate_trust_level(self, identity: Identity, 
                                   context: Optional[Dict[str, Any]]) -> TrustLevel:
        """신뢰 수준 계산"""
        trust_score = 0
        
        # 기본 신뢰도
        if identity.is_verified:
            trust_score += 1
        
        # MFA 사용
        if AuthMethod.MFA in identity.auth_methods:
            trust_score += 1
        
        # 인증서 기반 인증
        if AuthMethod.CERTIFICATE in identity.auth_methods:
            trust_score += 1
        
        # 신뢰할 수 있는 네트워크
        if context and self._is_trusted_network(context.get('source_ip', '')):
            trust_score += 1
        
        # 신뢰 수준 매핑
        if trust_score >= 4:
            return TrustLevel.VERIFIED
        elif trust_score >= 3:
            return TrustLevel.HIGH
        elif trust_score >= 2:
            return TrustLevel.MEDIUM
        elif trust_score >= 1:
            return TrustLevel.LOW
        else:
            return TrustLevel.UNTRUSTED
    
    def _is_trusted_network(self, ip: str) -> bool:
        """신뢰할 수 있는 네트워크 확인"""
        trusted_networks = [
            "192.168.0.0/16",
            "10.0.0.0/8",
            "172.16.0.0/12"
        ]
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            for network in trusted_networks:
                if ip_obj in ipaddress.ip_network(network):
                    return True
        except ValueError:
            pass
        
        return False
    
    async def _create_session(self, identity: Identity, 
                            context: Optional[Dict[str, Any]]) -> str:
        """세션 생성"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(
            seconds=self.config["authentication"]["session_timeout"]
        )
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sessions (
                session_id, identity_id, expires_at, source_ip, user_agent, device_id
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session_id, identity.user_id, expires_at,
            context.get('source_ip') if context else None,
            context.get('user_agent') if context else None,
            context.get('device_id') if context else None
        ))
        
        conn.commit()
        conn.close()
        
        # 메모리 세션 저장
        self.active_sessions[session_id] = AccessContext(
            identity=identity,
            resource="session",
            resource_type=ResourceType.SERVICE,
            action="login",
            source_ip=context.get('source_ip', '') if context else '',
            user_agent=context.get('user_agent', '') if context else '',
            timestamp=datetime.now(),
            session_id=session_id,
            device_id=context.get('device_id') if context else None,
            geo_location=context.get('geo_location') if context else None,
            risk_score=0.0,
            additional_data=context or {}
        )
        
        return session_id
    
    async def _validate_session(self, session_id: str) -> Optional[Identity]:
        """세션 유효성 검사"""
        if session_id in self.active_sessions:
            session_context = self.active_sessions[session_id]
            # 세션 만료 확인
            if datetime.now() > (session_context.timestamp + 
                               timedelta(seconds=self.config["authentication"]["session_timeout"])):
                del self.active_sessions[session_id]
                return None
            return session_context.identity
        
        # 데이터베이스에서 세션 확인
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.identity_id, s.expires_at, i.*
            FROM sessions s
            JOIN identities i ON s.identity_id = i.user_id
            WHERE s.session_id = ? AND s.is_active = TRUE AND s.expires_at > ?
        ''', (session_id, datetime.now()))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # Identity 객체 재구성
        identity_data = row[2:]  # sessions 테이블 컬럼 제외
        identity = Identity(
            user_id=identity_data[0],
            username=identity_data[1],
            email=identity_data[2],
            roles=json.loads(identity_data[5]) if identity_data[5] else [],
            permissions=json.loads(identity_data[6]) if identity_data[6] else [],
            trust_level=TrustLevel(identity_data[7]),
            auth_methods=[AuthMethod(m) for m in json.loads(identity_data[8])] if identity_data[8] else [],
            device_fingerprint=identity_data[9],
            geo_location=json.loads(identity_data[10]) if identity_data[10] else None,
            last_login=datetime.fromisoformat(identity_data[11]) if identity_data[11] else datetime.now(),
            failed_attempts=identity_data[12],
            is_active=bool(identity_data[13]),
            is_verified=bool(identity_data[14]),
            created_at=datetime.fromisoformat(identity_data[15]),
            updated_at=datetime.fromisoformat(identity_data[16])
        )
        
        return identity
    
    def _classify_resource(self, resource: str) -> ResourceType:
        """리소스 분류"""
        if resource.startswith('/api/'):
            return ResourceType.API
        elif resource.startswith('database:'):
            return ResourceType.DATABASE
        elif resource.startswith('/admin'):
            return ResourceType.ADMIN_PANEL
        elif resource.startswith('file:'):
            return ResourceType.FILE_SYSTEM
        elif resource.startswith('network:'):
            return ResourceType.NETWORK
        else:
            return ResourceType.SERVICE
    
    async def _calculate_access_risk(self, context: AccessContext) -> float:
        """접근 위험 평가"""
        risk_score = 0.0
        
        # 권한 상승 시도
        if context.action in ['admin', 'sudo', 'elevate']:
            risk_score += self.risk_factors.get("privilege_escalation", 0.5)
        
        # 민감한 리소스 접근
        sensitive_patterns = [
            r'/admin', r'/config', r'/secret', r'/private',
            r'database:', r'file:/etc', r'file:/var/log'
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, context.resource):
                risk_score += 0.2
                break
        
        # 신뢰 수준 기반 위험
        trust_risk = {
            TrustLevel.UNTRUSTED: 0.8,
            TrustLevel.LOW: 0.6,
            TrustLevel.MEDIUM: 0.3,
            TrustLevel.HIGH: 0.1,
            TrustLevel.VERIFIED: 0.0
        }
        
        risk_score += trust_risk.get(context.identity.trust_level, 0.5)
        
        # 시간 기반 위험
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:
            risk_score += self.risk_factors.get("off_hours_access", 0.1)
        
        # 빈번한 요청
        recent_requests = self._count_recent_requests(context.session_id)
        if recent_requests > 100:  # 1분간 100회 이상
            risk_score += self.risk_factors.get("rapid_requests", 0.2)
        
        return min(risk_score, 1.0)
    
    def _count_recent_requests(self, session_id: str) -> int:
        """최근 요청 횟수 계산"""
        # 실제로는 Redis 등을 사용하여 구현
        return 0
    
    async def _evaluate_policies(self, context: AccessContext) -> Tuple[AccessLevel, str, Optional[PolicyRule]]:
        """정책 평가"""
        # 정책을 우선순위 순으로 평가
        sorted_policies = sorted(self.policies.values(), key=lambda p: p.priority)
        
        for policy in sorted_policies:
            if not policy.is_active:
                continue
            
            # 리소스 패턴 매칭
            if not re.match(policy.resource_pattern, context.resource):
                continue
            
            # 액션 패턴 매칭
            if not re.match(policy.action_pattern, context.action):
                continue
            
            # 정책 조건 평가
            if not await self._evaluate_policy_conditions(policy, context):
                continue
            
            # 첫 번째 매칭되는 정책 적용
            return policy.access_level, f"정책 적용: {policy.name}", policy
        
        # 기본 정책: 거부
        return AccessLevel.DENY, "적용 가능한 정책 없음", None
    
    async def _evaluate_policy_conditions(self, policy: PolicyRule, context: AccessContext) -> bool:
        """정책 조건 평가"""
        # 신뢰 수준 확인
        if context.identity.trust_level.value < policy.required_trust_level.value:
            return False
        
        # 인증 방법 확인
        if policy.required_auth_methods:
            if not any(method in context.identity.auth_methods for method in policy.required_auth_methods):
                return False
        
        # 역할 확인
        if policy.required_roles:
            if not any(role in context.identity.roles for role in policy.required_roles):
                return False
        
        # IP 주소 확인
        if policy.blocked_ips:
            if context.source_ip in policy.blocked_ips:
                return False
        
        if policy.allowed_ips:
            if context.source_ip not in policy.allowed_ips:
                return False
        
        # 시간 제한 확인
        if policy.time_restrictions:
            if not await self._check_time_restrictions(policy.time_restrictions, context):
                return False
        
        # 추가 조건 확인
        for condition_key, condition_value in policy.conditions.items():
            if not await self._evaluate_condition(condition_key, condition_value, context):
                return False
        
        return True
    
    async def _check_time_restrictions(self, restrictions: Dict[str, Any], context: AccessContext) -> bool:
        """시간 제한 확인"""
        if restrictions.get("business_hours_only", False):
            current_time = datetime.now().time()
            start_time_str = restrictions.get("start_time", "09:00")
            end_time_str = restrictions.get("end_time", "18:00")
            
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
            
            if not (start_time <= current_time <= end_time):
                return False
        
        return True
    
    async def _evaluate_condition(self, key: str, value: Any, context: AccessContext) -> bool:
        """개별 조건 평가"""
        if key == "authenticated":
            return value == True  # 세션이 있으면 인증된 것으로 간주
        
        elif key == "roles":
            if isinstance(value, list):
                return any(role in context.identity.roles for role in value)
            else:
                return value in context.identity.roles
        
        elif key == "permissions":
            if isinstance(value, list):
                return any(perm in context.identity.permissions for perm in value)
            else:
                return value in context.identity.permissions
        
        elif key == "risk_threshold":
            return context.risk_score <= value
        
        elif key == "geo_location":
            if context.geo_location and isinstance(value, dict):
                for geo_key, geo_value in value.items():
                    if context.geo_location.get(geo_key) != geo_value:
                        return False
                return True
        
        return True
    
    async def _increment_failed_attempts(self, user_id: str):
        """실패 횟수 증가"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE identities 
            SET failed_attempts = failed_attempts + 1, updated_at = ?
            WHERE user_id = ?
        ''', (datetime.now(), user_id))
        
        conn.commit()
        conn.close()
    
    async def _reset_failed_attempts(self, user_id: str):
        """실패 횟수 초기화"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE identities 
            SET failed_attempts = 0, updated_at = ?
            WHERE user_id = ?
        ''', (datetime.now(), user_id))
        
        conn.commit()
        conn.close()
    
    async def _update_identity(self, identity: Identity):
        """신원 정보 업데이트"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE identities 
            SET trust_level = ?, last_login = ?, updated_at = ?
            WHERE user_id = ?
        ''', (identity.trust_level.value, identity.last_login, datetime.now(), identity.user_id))
        
        conn.commit()
        conn.close()
    
    async def _log_access_attempt(self, user_id: Optional[str], action: str, decision: str,
                                reason: str, context: Optional[Dict[str, Any]]):
        """접근 시도 로그"""
        await self._log_access(user_id, "authentication", action, decision, reason, context)
    
    async def _log_access(self, user_id: Optional[str], resource: str, action: str,
                         decision: str, reason: str, context: Optional[Dict[str, Any]],
                         risk_score: float = 0.0, policy_applied: Optional[str] = None):
        """접근 로그 기록"""
        log_id = secrets.token_urlsafe(16)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO access_logs (
                log_id, identity_id, resource, action, decision, reason,
                risk_score, source_ip, user_agent, session_id, policy_applied
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log_id, user_id, resource, action, decision, reason,
            risk_score,
            context.get('source_ip') if context else None,
            context.get('user_agent') if context else None,
            context.get('session_id') if context else None,
            policy_applied
        ))
        
        conn.commit()
        conn.close()
    
    async def create_identity(self, username: str, email: str, password: str,
                            roles: List[str], permissions: List[str]) -> str:
        """신원 생성"""
        user_id = secrets.token_urlsafe(16)
        salt = secrets.token_urlsafe(16)
        
        # 패스워드 해시
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 100000
        )
        password_hash_b64 = base64.b64encode(password_hash).decode()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO identities (
                user_id, username, email, password_hash, salt,
                roles, permissions, trust_level, auth_methods
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, username, email, password_hash_b64, salt,
            json.dumps(roles), json.dumps(permissions),
            TrustLevel.LOW.value, json.dumps([AuthMethod.PASSWORD.value])
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"신원 생성: {username}")
        return user_id
    
    async def create_api_key(self, user_id: str, name: str, permissions: List[str],
                           rate_limit: int = 1000) -> str:
        """API 키 생성"""
        api_key = f"zt_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_id = secrets.token_urlsafe(16)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_keys (
                key_id, key_hash, identity_id, name, permissions, rate_limit
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (key_id, key_hash, user_id, name, json.dumps(permissions), rate_limit))
        
        conn.commit()
        conn.close()
        
        logger.info(f"API 키 생성: {name} (사용자: {user_id})")
        return api_key
    
    async def validate_api_key(self, api_key: str) -> Optional[Identity]:
        """API 키 검증"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ak.identity_id, ak.permissions, i.*
            FROM api_keys ak
            JOIN identities i ON ak.identity_id = i.user_id
            WHERE ak.key_hash = ? AND ak.is_active = TRUE 
            AND (ak.expires_at IS NULL OR ak.expires_at > ?)
        ''', (key_hash, datetime.now()))
        
        row = cursor.fetchone()
        
        if row:
            # 마지막 사용 시간 업데이트
            cursor.execute('''
                UPDATE api_keys SET last_used = ? WHERE key_hash = ?
            ''', (datetime.now(), key_hash))
            conn.commit()
        
        conn.close()
        
        if not row:
            return None
        
        # Identity 객체 구성
        api_permissions = json.loads(row[1]) if row[1] else []
        identity_data = row[2:]
        
        identity = Identity(
            user_id=identity_data[0],
            username=identity_data[1],
            email=identity_data[2],
            roles=json.loads(identity_data[5]) if identity_data[5] else [],
            permissions=api_permissions,  # API 키 권한 사용
            trust_level=TrustLevel(identity_data[7]),
            auth_methods=[AuthMethod.API_KEY],
            device_fingerprint=identity_data[9],
            geo_location=json.loads(identity_data[10]) if identity_data[10] else None,
            last_login=datetime.now(),
            failed_attempts=identity_data[12],
            is_active=bool(identity_data[13]),
            is_verified=bool(identity_data[14]),
            created_at=datetime.fromisoformat(identity_data[15]),
            updated_at=datetime.fromisoformat(identity_data[16])
        )
        
        return identity
    
    async def generate_jwt_token(self, identity: Identity, expires_in: int = 3600) -> str:
        """JWT 토큰 생성"""
        payload = {
            'user_id': identity.user_id,
            'username': identity.username,
            'roles': identity.roles,
            'permissions': identity.permissions,
            'trust_level': identity.trust_level.value,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(seconds=expires_in)
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        return token
    
    async def validate_jwt_token(self, token: str) -> Optional[Identity]:
        """JWT 토큰 검증"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            identity = Identity(
                user_id=payload['user_id'],
                username=payload['username'],
                email='',  # JWT에서 이메일 정보 없음
                roles=payload.get('roles', []),
                permissions=payload.get('permissions', []),
                trust_level=TrustLevel(payload.get('trust_level', TrustLevel.LOW.value)),
                auth_methods=[AuthMethod.JWT_TOKEN],
                device_fingerprint=None,
                geo_location=None,
                last_login=datetime.now(),
                failed_attempts=0,
                is_active=True,
                is_verified=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            return identity
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT 토큰 만료")
            return None
        except jwt.InvalidTokenError:
            logger.warning("유효하지 않은 JWT 토큰")
            return None
    
    async def get_security_dashboard(self) -> Dict[str, Any]:
        """보안 대시보드 데이터"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 오늘의 접근 통계
        today = datetime.now().date()
        cursor.execute('''
            SELECT decision, COUNT(*) 
            FROM access_logs 
            WHERE DATE(timestamp) = ?
            GROUP BY decision
        ''', (today,))
        
        today_stats = dict(cursor.fetchall())
        
        # 위험 점수 분포
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN risk_score < 0.3 THEN 'LOW'
                    WHEN risk_score < 0.7 THEN 'MEDIUM'
                    ELSE 'HIGH'
                END as risk_level,
                COUNT(*)
            FROM access_logs 
            WHERE DATE(timestamp) = ?
            GROUP BY risk_level
        ''', (today,))
        
        risk_distribution = dict(cursor.fetchall())
        
        # 활성 세션 수
        cursor.execute('''
            SELECT COUNT(*) FROM sessions 
            WHERE is_active = TRUE AND expires_at > ?
        ''', (datetime.now(),))
        
        active_sessions = cursor.fetchone()[0]
        
        # 최근 보안 이벤트
        cursor.execute('''
            SELECT resource, action, decision, reason, timestamp
            FROM access_logs 
            WHERE decision = 'DENY' 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        
        recent_denials = cursor.fetchall()
        
        conn.close()
        
        return {
            "overview": {
                "active_sessions": active_sessions,
                "total_policies": len(self.policies),
                "total_identities": len(self.identities)
            },
            "today_stats": today_stats,
            "risk_distribution": risk_distribution,
            "recent_security_events": [
                {
                    "resource": event[0],
                    "action": event[1],
                    "decision": event[2],
                    "reason": event[3],
                    "timestamp": event[4]
                }
                for event in recent_denials
            ],
            "policies": [
                {
                    "name": policy.name,
                    "resource_pattern": policy.resource_pattern,
                    "access_level": policy.access_level.value,
                    "is_active": policy.is_active
                }
                for policy in sorted(self.policies.values(), key=lambda p: p.priority)[:10]
            ]
        }


# 전역 인스턴스
_zero_trust_system = None

def get_zero_trust_system() -> ZeroTrustArchitecture:
    """제로 트러스트 시스템 싱글톤 반환"""
    global _zero_trust_system
    if _zero_trust_system is None:
        _zero_trust_system = ZeroTrustArchitecture()
    return _zero_trust_system


# 데코레이터
def require_zero_trust(resource: str, action: str):
    """제로 트러스트 검사 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 세션 ID 추출 (request에서)
            session_id = kwargs.get('session_id') or getattr(args[0], 'session_id', None) if args else None
            
            if not session_id:
                raise PermissionError("세션 ID가 필요합니다")
            
            zt_system = get_zero_trust_system()
            allowed, reason, access_level = await zt_system.authorize(session_id, resource, action)
            
            if not allowed:
                raise PermissionError(f"접근 거부: {reason}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def main():
    """테스트용 메인 함수"""
    zt = ZeroTrustArchitecture()
    
    # 테스트 사용자 생성
    user_id = await zt.create_identity(
        username="testuser",
        email="test@example.com",
        password="SecurePassword123!",
        roles=["user"],
        permissions=["read", "write"]
    )
    
    # 인증 테스트
    success, session_id, identity = await zt.authenticate("testuser", "SecurePassword123!")
    
    if success and session_id:
        print(f"인증 성공: {session_id}")
        
        # 권한 테스트
        allowed, reason, level = await zt.authorize(session_id, "/api/data", "GET")
        print(f"권한 검사: {allowed} - {reason} ({level.value})")
        
        # 대시보드 데이터
        dashboard = await zt.get_security_dashboard()
        print(f"대시보드: {dashboard}")


if __name__ == "__main__":
    asyncio.run(main())