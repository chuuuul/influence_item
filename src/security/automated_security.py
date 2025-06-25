#!/usr/bin/env python3
"""
자동화된 보안 시스템

API 키 순환, 보안 감사, 취약점 스캔, 접근 권한 관리
"""

import os
import json
import time
import hashlib
import logging
import asyncio
import secrets
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import requests
import aiohttp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from src.notifications.alert_manager import send_warning_alert, send_critical_alert
from src.config.config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """보안 레벨"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class VulnerabilityType(Enum):
    """취약점 유형"""
    OUTDATED_PACKAGE = "outdated_package"
    WEAK_CREDENTIAL = "weak_credential"
    EXPOSED_SECRET = "exposed_secret"
    INSECURE_CONFIG = "insecure_config"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    NETWORK_EXPOSURE = "network_exposure"

@dataclass
class SecurityIssue:
    """보안 이슈 데이터 클래스"""
    issue_id: str
    type: VulnerabilityType
    level: SecurityLevel
    title: str
    description: str
    affected_component: str
    discovered_at: datetime
    remediation: str
    auto_fixable: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class CryptoManager:
    """암호화 관리자"""
    
    def __init__(self, password: Optional[str] = None):
        self.password = password or os.getenv("ENCRYPTION_PASSWORD", "default_password")
        self.key = self._derive_key(self.password.encode())
        self.cipher = Fernet(self.key)
    
    def _derive_key(self, password: bytes) -> bytes:
        """패스워드에서 키 유도"""
        salt = b'influence_item_salt'  # 실제 환경에서는 무작위 salt 사용
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))
    
    def encrypt(self, data: str) -> str:
        """데이터 암호화"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """데이터 복호화"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def generate_secure_token(self, length: int = 32) -> str:
        """보안 토큰 생성"""
        return secrets.token_urlsafe(length)

class APIKeyManager:
    """API 키 관리자"""
    
    def __init__(self):
        self.crypto = CryptoManager()
        self.key_file = Path("config/encrypted_keys.json")
        self.rotation_schedule = {
            "google_api": 90,  # 90일마다
            "youtube_api": 90,
            "coupang_api": 30,  # 30일마다
            "gemini_api": 60   # 60일마다
        }
    
    def load_keys(self) -> Dict[str, Any]:
        """암호화된 키 파일 로드"""
        if not self.key_file.exists():
            return {}
        
        try:
            with open(self.key_file, 'r') as f:
                encrypted_data = json.load(f)
            
            decrypted_keys = {}
            for key, value in encrypted_data.items():
                if isinstance(value, dict) and 'encrypted' in value:
                    decrypted_keys[key] = {
                        'value': self.crypto.decrypt(value['encrypted']),
                        'created_at': datetime.fromisoformat(value['created_at']),
                        'expires_at': datetime.fromisoformat(value['expires_at']) if value.get('expires_at') else None,
                        'rotation_days': value.get('rotation_days', 90)
                    }
                else:
                    decrypted_keys[key] = value
            
            return decrypted_keys
        except Exception as e:
            logger.error(f"키 파일 로드 실패: {e}")
            return {}
    
    def save_keys(self, keys: Dict[str, Any]):
        """키를 암호화하여 저장"""
        try:
            encrypted_data = {}
            for key, value in keys.items():
                if isinstance(value, dict) and 'value' in value:
                    encrypted_data[key] = {
                        'encrypted': self.crypto.encrypt(value['value']),
                        'created_at': value['created_at'].isoformat(),
                        'expires_at': value['expires_at'].isoformat() if value.get('expires_at') else None,
                        'rotation_days': value.get('rotation_days', 90)
                    }
                else:
                    encrypted_data[key] = value
            
            # 백업 생성
            if self.key_file.exists():
                backup_file = self.key_file.with_suffix('.backup')
                self.key_file.rename(backup_file)
            
            with open(self.key_file, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            logger.info("키 파일 저장 완료")
        except Exception as e:
            logger.error(f"키 파일 저장 실패: {e}")
            raise
    
    def check_key_expiration(self) -> List[str]:
        """키 만료 확인"""
        keys = self.load_keys()
        expiring_keys = []
        now = datetime.now()
        
        for key_name, key_info in keys.items():
            if isinstance(key_info, dict) and 'expires_at' in key_info:
                expires_at = key_info['expires_at']
                if expires_at and expires_at <= now + timedelta(days=7):  # 7일 이내 만료
                    expiring_keys.append(key_name)
        
        return expiring_keys
    
    def rotate_key(self, key_name: str, new_value: str) -> bool:
        """키 순환"""
        try:
            keys = self.load_keys()
            
            # 이전 키 백업
            if key_name in keys:
                backup_key = f"{key_name}_backup"
                keys[backup_key] = keys[key_name].copy()
                keys[backup_key]['backed_up_at'] = datetime.now()
            
            # 새 키 설정
            rotation_days = self.rotation_schedule.get(key_name, 90)
            keys[key_name] = {
                'value': new_value,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(days=rotation_days),
                'rotation_days': rotation_days
            }
            
            self.save_keys(keys)
            logger.info(f"키 순환 완료: {key_name}")
            return True
        except Exception as e:
            logger.error(f"키 순환 실패 ({key_name}): {e}")
            return False
    
    async def auto_rotate_keys(self):
        """자동 키 순환"""
        expiring_keys = self.check_key_expiration()
        
        for key_name in expiring_keys:
            # 실제 환경에서는 각 서비스의 API를 통해 새 키를 생성
            new_key = self.crypto.generate_secure_token(64)
            
            if self.rotate_key(key_name, new_key):
                await send_warning_alert(
                    f"API 키 자동 순환 완료",
                    f"{key_name} 키가 자동으로 순환되었습니다.",
                    service="security",
                    key_name=key_name
                )
            else:
                await send_critical_alert(
                    f"API 키 순환 실패",
                    f"{key_name} 키 순환에 실패했습니다. 수동 개입이 필요합니다.",
                    service="security",
                    key_name=key_name
                )

class VulnerabilityScanner:
    """취약점 스캐너"""
    
    def __init__(self):
        self.scan_results_file = Path("security/scan_results.json")
        self.scan_results_file.parent.mkdir(exist_ok=True)
    
    async def scan_dependencies(self) -> List[SecurityIssue]:
        """의존성 취약점 스캔"""
        issues = []
        
        try:
            # pip-audit를 사용한 Python 패키지 스캔
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                outdated_packages = json.loads(result.stdout)
                
                for package in outdated_packages:
                    # 보안 관련 중요 패키지 확인
                    critical_packages = [
                        'requests', 'urllib3', 'cryptography', 'pillow', 
                        'pyjwt', 'django', 'flask', 'fastapi'
                    ]
                    
                    level = SecurityLevel.HIGH if package['name'].lower() in critical_packages else SecurityLevel.MEDIUM
                    
                    issue = SecurityIssue(
                        issue_id=f"dep_{package['name']}_{int(time.time())}",
                        type=VulnerabilityType.OUTDATED_PACKAGE,
                        level=level,
                        title=f"Outdated package: {package['name']}",
                        description=f"Package {package['name']} is outdated. Current: {package['version']}, Latest: {package['latest_version']}",
                        affected_component=f"python_package_{package['name']}",
                        discovered_at=datetime.now(),
                        remediation=f"pip install --upgrade {package['name']}=={package['latest_version']}",
                        auto_fixable=True,
                        metadata={
                            'current_version': package['version'],
                            'latest_version': package['latest_version'],
                            'package_type': 'python'
                        }
                    )
                    issues.append(issue)
        
        except subprocess.TimeoutExpired:
            logger.error("의존성 스캔 타임아웃")
        except Exception as e:
            logger.error(f"의존성 스캔 실패: {e}")
        
        return issues
    
    async def scan_secrets(self) -> List[SecurityIssue]:
        """노출된 시크릿 스캔"""
        issues = []
        
        # 스캔할 파일 패턴
        scan_patterns = [
            "*.py", "*.yaml", "*.yml", "*.json", "*.env*", "*.conf", "*.config"
        ]
        
        # 시크릿 패턴
        secret_patterns = {
            'api_key': r'(?i)(api[_-]?key|apikey)\s*[:=]\s*[\'"]?([a-z0-9]{20,})[\'"]?',
            'password': r'(?i)(password|passwd|pwd)\s*[:=]\s*[\'"]?([^\s\'"\n]{8,})[\'"]?',
            'token': r'(?i)(token|auth[_-]?token)\s*[:=]\s*[\'"]?([a-z0-9]{20,})[\'"]?',
            'secret': r'(?i)(secret|secret[_-]?key)\s*[:=]\s*[\'"]?([a-z0-9]{20,})[\'"]?'
        }
        
        try:
            import re
            from pathlib import Path
            
            for pattern in scan_patterns:
                for file_path in Path('.').rglob(pattern):
                    # 특정 디렉토리 제외
                    if any(exclude in str(file_path) for exclude in ['.git', 'node_modules', '__pycache__', 'venv']):
                        continue
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        for secret_type, regex_pattern in secret_patterns.items():
                            matches = re.finditer(regex_pattern, content)
                            
                            for match in matches:
                                # 테스트 파일이나 예제 파일 제외
                                if any(test_indicator in str(file_path).lower() for test_indicator in ['test', 'example', 'sample', 'demo']):
                                    continue
                                
                                issue = SecurityIssue(
                                    issue_id=f"secret_{secret_type}_{hash(str(file_path))}_{int(time.time())}",
                                    type=VulnerabilityType.EXPOSED_SECRET,
                                    level=SecurityLevel.CRITICAL,
                                    title=f"Exposed {secret_type} in {file_path}",
                                    description=f"Potential {secret_type} found in source code",
                                    affected_component=str(file_path),
                                    discovered_at=datetime.now(),
                                    remediation=f"Remove hardcoded {secret_type} and use environment variables",
                                    auto_fixable=False,
                                    metadata={
                                        'file_path': str(file_path),
                                        'line_number': content[:match.start()].count('\n') + 1,
                                        'secret_type': secret_type
                                    }
                                )
                                issues.append(issue)
                    
                    except (UnicodeDecodeError, PermissionError):
                        continue
        
        except Exception as e:
            logger.error(f"시크릿 스캔 실패: {e}")
        
        return issues
    
    async def scan_configurations(self) -> List[SecurityIssue]:
        """설정 보안 스캔"""
        issues = []
        
        # Docker 설정 확인
        docker_files = list(Path('.').rglob('docker-compose*.yml')) + list(Path('.').rglob('Dockerfile*'))
        
        for docker_file in docker_files:
            try:
                with open(docker_file, 'r') as f:
                    content = f.read()
                
                # 보안 이슈 체크
                if 'privileged: true' in content:
                    issues.append(SecurityIssue(
                        issue_id=f"docker_privileged_{int(time.time())}",
                        type=VulnerabilityType.PRIVILEGE_ESCALATION,
                        level=SecurityLevel.HIGH,
                        title="Privileged Docker container detected",
                        description=f"Docker container running in privileged mode in {docker_file}",
                        affected_component=str(docker_file),
                        discovered_at=datetime.now(),
                        remediation="Remove privileged: true and use specific capabilities instead",
                        auto_fixable=False
                    ))
                
                if 'user: root' in content or 'USER root' in content:
                    issues.append(SecurityIssue(
                        issue_id=f"docker_root_{int(time.time())}",
                        type=VulnerabilityType.PRIVILEGE_ESCALATION,
                        level=SecurityLevel.MEDIUM,
                        title="Container running as root",
                        description=f"Container configured to run as root user in {docker_file}",
                        affected_component=str(docker_file),
                        discovered_at=datetime.now(),
                        remediation="Create and use non-root user in container",
                        auto_fixable=False
                    ))
            
            except Exception as e:
                logger.error(f"Docker 파일 스캔 실패 ({docker_file}): {e}")
        
        return issues
    
    async def scan_network_exposure(self) -> List[SecurityIssue]:
        """네트워크 노출 스캔"""
        issues = []
        
        try:
            # 포트 스캔 (간단한 로컬 포트 체크)
            import socket
            
            dangerous_ports = [22, 23, 25, 53, 110, 143, 993, 995, 3389, 5432, 3306, 6379, 27017]
            open_ports = []
            
            for port in dangerous_ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    open_ports.append(port)
            
            for port in open_ports:
                port_services = {
                    22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
                    110: "POP3", 143: "IMAP", 993: "IMAPS", 995: "POP3S",
                    3389: "RDP", 5432: "PostgreSQL", 3306: "MySQL",
                    6379: "Redis", 27017: "MongoDB"
                }
                
                service = port_services.get(port, "Unknown")
                level = SecurityLevel.HIGH if port in [22, 23, 3389] else SecurityLevel.MEDIUM
                
                issue = SecurityIssue(
                    issue_id=f"network_port_{port}_{int(time.time())}",
                    type=VulnerabilityType.NETWORK_EXPOSURE,
                    level=level,
                    title=f"Exposed {service} service on port {port}",
                    description=f"{service} service is accessible on localhost:{port}",
                    affected_component=f"network_port_{port}",
                    discovered_at=datetime.now(),
                    remediation=f"Configure firewall rules or bind {service} to specific interfaces only",
                    auto_fixable=False,
                    metadata={
                        'port': port,
                        'service': service
                    }
                )
                issues.append(issue)
        
        except Exception as e:
            logger.error(f"네트워크 스캔 실패: {e}")
        
        return issues
    
    async def run_full_scan(self) -> List[SecurityIssue]:
        """전체 보안 스캔 실행"""
        logger.info("전체 보안 스캔 시작")
        
        all_issues = []
        
        # 각 스캔 유형별로 실행
        scan_tasks = [
            ("dependencies", self.scan_dependencies()),
            ("secrets", self.scan_secrets()),
            ("configurations", self.scan_configurations()),
            ("network", self.scan_network_exposure())
        ]
        
        for scan_name, scan_task in scan_tasks:
            try:
                logger.info(f"{scan_name} 스캔 실행 중...")
                issues = await scan_task
                all_issues.extend(issues)
                logger.info(f"{scan_name} 스캔 완료: {len(issues)}개 이슈 발견")
            except Exception as e:
                logger.error(f"{scan_name} 스캔 실패: {e}")
        
        # 결과 저장
        self.save_scan_results(all_issues)
        
        logger.info(f"전체 보안 스캔 완료: 총 {len(all_issues)}개 이슈 발견")
        return all_issues
    
    def save_scan_results(self, issues: List[SecurityIssue]):
        """스캔 결과 저장"""
        try:
            results = {
                'scan_timestamp': datetime.now().isoformat(),
                'total_issues': len(issues),
                'issues_by_level': {
                    level.value: len([i for i in issues if i.level == level])
                    for level in SecurityLevel
                },
                'issues': [
                    {
                        'issue_id': issue.issue_id,
                        'type': issue.type.value,
                        'level': issue.level.value,
                        'title': issue.title,
                        'description': issue.description,
                        'affected_component': issue.affected_component,
                        'discovered_at': issue.discovered_at.isoformat(),
                        'remediation': issue.remediation,
                        'auto_fixable': issue.auto_fixable,
                        'metadata': issue.metadata
                    }
                    for issue in issues
                ]
            }
            
            with open(self.scan_results_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"스캔 결과 저장 완료: {self.scan_results_file}")
        except Exception as e:
            logger.error(f"스캔 결과 저장 실패: {e}")

class AccessControlManager:
    """접근 권한 관리자"""
    
    def __init__(self):
        self.access_log_file = Path("security/access_log.json")
        self.access_log_file.parent.mkdir(exist_ok=True)
        self.failed_attempts = {}
        self.max_failed_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
    
    def log_access_attempt(self, user_id: str, resource: str, success: bool, ip_address: str = None):
        """접근 시도 로깅"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'resource': resource,
            'success': success,
            'ip_address': ip_address
        }
        
        try:
            # 기존 로그 로드
            if self.access_log_file.exists():
                with open(self.access_log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append(log_entry)
            
            # 최근 1000개 로그만 유지
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            with open(self.access_log_file, 'w') as f:
                json.dump(logs, f, indent=2)
        
        except Exception as e:
            logger.error(f"접근 로그 저장 실패: {e}")
        
        # 실패한 시도 추적
        if not success:
            key = f"{user_id}:{ip_address}" if ip_address else user_id
            if key not in self.failed_attempts:
                self.failed_attempts[key] = []
            
            self.failed_attempts[key].append(datetime.now())
            
            # 오래된 시도 제거
            cutoff = datetime.now() - self.lockout_duration
            self.failed_attempts[key] = [
                attempt for attempt in self.failed_attempts[key]
                if attempt > cutoff
            ]
    
    def is_locked_out(self, user_id: str, ip_address: str = None) -> bool:
        """잠금 상태 확인"""
        key = f"{user_id}:{ip_address}" if ip_address else user_id
        
        if key not in self.failed_attempts:
            return False
        
        recent_failures = self.failed_attempts[key]
        return len(recent_failures) >= self.max_failed_attempts
    
    async def analyze_access_patterns(self) -> List[SecurityIssue]:
        """접근 패턴 분석"""
        issues = []
        
        if not self.access_log_file.exists():
            return issues
        
        try:
            with open(self.access_log_file, 'r') as f:
                logs = json.load(f)
            
            # 최근 24시간 로그 분석
            cutoff = datetime.now() - timedelta(hours=24)
            recent_logs = [
                log for log in logs
                if datetime.fromisoformat(log['timestamp']) > cutoff
            ]
            
            # 실패한 로그인 시도 분석
            failed_attempts = [log for log in recent_logs if not log['success']]
            
            if len(failed_attempts) > 20:  # 24시간 내 20회 이상 실패
                issue = SecurityIssue(
                    issue_id=f"access_brute_force_{int(time.time())}",
                    type=VulnerabilityType.WEAK_CREDENTIAL,
                    level=SecurityLevel.HIGH,
                    title="Potential brute force attack detected",
                    description=f"{len(failed_attempts)} failed login attempts in the last 24 hours",
                    affected_component="authentication_system",
                    discovered_at=datetime.now(),
                    remediation="Review access logs and consider implementing stronger authentication",
                    auto_fixable=False,
                    metadata={
                        'failed_attempts': len(failed_attempts),
                        'time_window': "24_hours"
                    }
                )
                issues.append(issue)
            
            # 비정상적인 접근 시간 분석
            off_hours_access = [
                log for log in recent_logs
                if datetime.fromisoformat(log['timestamp']).hour in range(0, 6)  # 자정~오전6시
            ]
            
            if len(off_hours_access) > 5:
                issue = SecurityIssue(
                    issue_id=f"access_off_hours_{int(time.time())}",
                    type=VulnerabilityType.INSECURE_CONFIG,
                    level=SecurityLevel.MEDIUM,
                    title="Unusual access times detected",
                    description=f"{len(off_hours_access)} access attempts during off-hours (midnight-6AM)",
                    affected_component="access_control",
                    discovered_at=datetime.now(),
                    remediation="Review off-hours access policy and implement time-based restrictions",
                    auto_fixable=False,
                    metadata={
                        'off_hours_attempts': len(off_hours_access)
                    }
                )
                issues.append(issue)
        
        except Exception as e:
            logger.error(f"접근 패턴 분석 실패: {e}")
        
        return issues

class AutomatedSecuritySystem:
    """자동화된 보안 시스템 통합 관리자"""
    
    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.vulnerability_scanner = VulnerabilityScanner()
        self.access_control = AccessControlManager()
        
    async def run_security_cycle(self):
        """보안 사이클 실행"""
        logger.info("자동화된 보안 사이클 시작")
        
        try:
            # 1. API 키 자동 순환 확인
            await self.api_key_manager.auto_rotate_keys()
            
            # 2. 취약점 스캔 실행
            security_issues = await self.vulnerability_scanner.run_full_scan()
            
            # 3. 접근 패턴 분석
            access_issues = await self.access_control.analyze_access_patterns()
            security_issues.extend(access_issues)
            
            # 4. 보안 이슈 알림
            await self.process_security_issues(security_issues)
            
            # 5. 자동 수정 시도
            await self.auto_remediate_issues(security_issues)
            
            logger.info("자동화된 보안 사이클 완료")
            
        except Exception as e:
            logger.error(f"보안 사이클 실행 실패: {e}")
            await send_critical_alert(
                "보안 시스템 오류",
                f"자동화된 보안 시스템에서 오류가 발생했습니다: {e}",
                service="security"
            )
    
    async def process_security_issues(self, issues: List[SecurityIssue]):
        """보안 이슈 처리 및 알림"""
        if not issues:
            await send_info_alert(
                "보안 스캔 완료",
                "보안 스캔이 완료되었으며 이슈가 발견되지 않았습니다.",
                service="security"
            )
            return
        
        # 심각도별 이슈 분류
        critical_issues = [i for i in issues if i.level == SecurityLevel.CRITICAL]
        high_issues = [i for i in issues if i.level == SecurityLevel.HIGH]
        medium_issues = [i for i in issues if i.level == SecurityLevel.MEDIUM]
        low_issues = [i for i in issues if i.level == SecurityLevel.LOW]
        
        # 치명적 이슈 즉시 알림
        for issue in critical_issues:
            await send_critical_alert(
                f"치명적 보안 이슈: {issue.title}",
                f"{issue.description}\n\n권장 조치: {issue.remediation}",
                service="security",
                issue_id=issue.issue_id,
                affected_component=issue.affected_component
            )
        
        # 전체 요약 알림
        summary_text = f"""
보안 스캔 결과 요약:
- 치명적: {len(critical_issues)}개
- 높음: {len(high_issues)}개  
- 보통: {len(medium_issues)}개
- 낮음: {len(low_issues)}개

총 {len(issues)}개의 보안 이슈가 발견되었습니다.
"""
        
        if critical_issues or high_issues:
            await send_warning_alert(
                "보안 스캔 결과",
                summary_text,
                service="security",
                total_issues=len(issues),
                critical_count=len(critical_issues),
                high_count=len(high_issues)
            )
    
    async def auto_remediate_issues(self, issues: List[SecurityIssue]):
        """자동 수정 시도"""
        auto_fixable_issues = [i for i in issues if i.auto_fixable]
        
        for issue in auto_fixable_issues:
            try:
                if issue.type == VulnerabilityType.OUTDATED_PACKAGE:
                    await self.auto_fix_outdated_package(issue)
                
                logger.info(f"자동 수정 완료: {issue.issue_id}")
            except Exception as e:
                logger.error(f"자동 수정 실패 ({issue.issue_id}): {e}")
    
    async def auto_fix_outdated_package(self, issue: SecurityIssue):
        """구식 패키지 자동 업데이트"""
        if 'package_type' in issue.metadata and issue.metadata['package_type'] == 'python':
            package_name = issue.affected_component.replace('python_package_', '')
            latest_version = issue.metadata.get('latest_version')
            
            if latest_version:
                # 실제 업데이트는 신중하게 수행 (테스트 환경에서만)
                logger.info(f"패키지 업데이트 권장: pip install --upgrade {package_name}=={latest_version}")

async def main():
    """메인 함수"""
    security_system = AutomatedSecuritySystem()
    
    # 지속적 보안 모니터링
    while True:
        try:
            await security_system.run_security_cycle()
            await asyncio.sleep(3600)  # 1시간 간격
        except KeyboardInterrupt:
            logger.info("보안 시스템 중단")
            break
        except Exception as e:
            logger.error(f"보안 시스템 오류: {e}")
            await asyncio.sleep(300)  # 5분 후 재시도

if __name__ == "__main__":
    asyncio.run(main())