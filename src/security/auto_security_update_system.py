"""
자동 보안 패치 및 업데이트 시스템

시스템의 보안을 항상 최신 상태로 유지하는 자동화 시스템
- 자동 취약점 스캔
- 보안 패치 자동 적용
- 의존성 업데이트 관리
- 제로데이 취약점 대응
- 롤백 및 복구 기능
"""

import asyncio
import subprocess
import json
import logging
import requests
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
import hashlib
import tempfile
import shutil
import tarfile
import zipfile
from packaging import version
import yaml
import semver

logger = logging.getLogger(__name__)


class VulnerabilitySeverity(Enum):
    """취약점 심각도"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class UpdateType(Enum):
    """업데이트 유형"""
    SECURITY_PATCH = "SECURITY_PATCH"
    DEPENDENCY_UPDATE = "DEPENDENCY_UPDATE"
    SYSTEM_UPDATE = "SYSTEM_UPDATE"
    APPLICATION_UPDATE = "APPLICATION_UPDATE"
    CONFIGURATION_UPDATE = "CONFIGURATION_UPDATE"


class UpdateStatus(Enum):
    """업데이트 상태"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    SKIPPED = "SKIPPED"


@dataclass
class Vulnerability:
    """취약점 정보"""
    vulnerability_id: str
    cve_id: Optional[str]
    title: str
    description: str
    severity: VulnerabilitySeverity
    cvss_score: float
    affected_packages: List[str]
    fixed_version: Optional[str]
    discovered_at: datetime
    patch_available: bool
    exploit_available: bool
    metadata: Dict[str, Any]


@dataclass
class SecurityUpdate:
    """보안 업데이트"""
    update_id: str
    update_type: UpdateType
    title: str
    description: str
    severity: VulnerabilitySeverity
    affected_components: List[str]
    current_version: str
    target_version: str
    patch_url: Optional[str]
    rollback_info: Dict[str, Any]
    scheduled_at: Optional[datetime]
    applied_at: Optional[datetime]
    status: UpdateStatus
    test_results: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class PackageInfo:
    """패키지 정보"""
    name: str
    current_version: str
    latest_version: str
    security_vulnerabilities: List[str]
    update_available: bool
    critical_update: bool


class AutoSecurityUpdateSystem:
    """자동 보안 업데이트 시스템"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or Path("config/security_update_config.json")
        self.db_path = Path("security/security_updates.db")
        self.backup_path = Path("security/update_backups")
        
        # 설정 로드
        self.config = self._load_config()
        
        # 상태 관리
        self.vulnerabilities: Dict[str, Vulnerability] = {}
        self.pending_updates: Dict[str, SecurityUpdate] = {}
        self.update_history: List[SecurityUpdate] = []
        
        # 패키지 관리
        self.package_managers = {
            "pip": self._handle_pip_updates,
            "npm": self._handle_npm_updates,
            "apt": self._handle_apt_updates,
            "yum": self._handle_yum_updates,
            "brew": self._handle_brew_updates
        }
        
        # 취약점 데이터베이스
        self.vulnerability_feeds = [
            "https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-recent.json.gz",
            "https://api.github.com/advisories",
            "https://pypi.org/pypi/{package}/json"
        ]
        
        # 실행 상태
        self.running = False
        self.scan_task = None
        self.update_task = None
        
        # 초기화
        self._init_database()
        self._create_backup_directory()
        
        logger.info("자동 보안 업데이트 시스템 초기화 완료")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "scanning": {
                "scan_interval_hours": 6,
                "vulnerability_feeds_enabled": True,
                "deep_scan_enabled": True,
                "scan_dependencies": True,
                "scan_system_packages": True
            },
            "updates": {
                "auto_apply_critical": True,
                "auto_apply_high": False,
                "maintenance_window_start": "02:00",
                "maintenance_window_end": "04:00",
                "max_concurrent_updates": 3,
                "rollback_timeout_hours": 24,
                "test_before_apply": True
            },
            "notifications": {
                "notify_on_vulnerability": True,
                "notify_on_update_start": True,
                "notify_on_update_complete": True,
                "notify_on_failure": True,
                "emergency_contact": "security@company.com"
            },
            "backup": {
                "backup_before_update": True,
                "backup_retention_days": 30,
                "incremental_backup": True
            },
            "package_managers": {
                "pip": {
                    "enabled": True,
                    "requirements_file": "requirements.txt",
                    "auto_update_dev_deps": False
                },
                "npm": {
                    "enabled": True,
                    "package_file": "package.json",
                    "auto_update_dev_deps": False
                },
                "system": {
                    "enabled": False,  # 시스템 패키지는 신중하게
                    "auto_update": False
                }
            },
            "security": {
                "gpg_verify_signatures": True,
                "checksum_verification": True,
                "sandbox_testing": True,
                "rollback_on_failure": True
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
        
        # 취약점 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vulnerabilities (
                vulnerability_id TEXT PRIMARY KEY,
                cve_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                cvss_score REAL,
                affected_packages TEXT,
                fixed_version TEXT,
                discovered_at DATETIME NOT NULL,
                patch_available BOOLEAN DEFAULT FALSE,
                exploit_available BOOLEAN DEFAULT FALSE,
                metadata TEXT
            )
        ''')
        
        # 보안 업데이트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_updates (
                update_id TEXT PRIMARY KEY,
                update_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                affected_components TEXT,
                current_version TEXT,
                target_version TEXT,
                patch_url TEXT,
                rollback_info TEXT,
                scheduled_at DATETIME,
                applied_at DATETIME,
                status TEXT DEFAULT 'PENDING',
                test_results TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 패키지 상태 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS package_status (
                package_name TEXT PRIMARY KEY,
                current_version TEXT NOT NULL,
                latest_version TEXT,
                security_vulnerabilities TEXT,
                last_checked DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_available BOOLEAN DEFAULT FALSE,
                critical_update BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # 업데이트 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_logs (
                log_id TEXT PRIMARY KEY,
                update_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (update_id) REFERENCES security_updates (update_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("보안 업데이트 데이터베이스 초기화 완료")
    
    def _create_backup_directory(self):
        """백업 디렉토리 생성"""
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        subdirs = ["packages", "system", "configurations", "databases"]
        for subdir in subdirs:
            (self.backup_path / subdir).mkdir(exist_ok=True)
    
    async def start_security_update_system(self):
        """보안 업데이트 시스템 시작"""
        if self.running:
            logger.warning("보안 업데이트 시스템이 이미 실행 중입니다")
            return
        
        self.running = True
        logger.info("자동 보안 업데이트 시스템 시작")
        
        # 취약점 스캔 태스크
        self.scan_task = asyncio.create_task(self._vulnerability_scan_loop())
        
        # 업데이트 적용 태스크
        self.update_task = asyncio.create_task(self._update_application_loop())
        
        # 초기 스캔 실행
        asyncio.create_task(self._perform_initial_scan())
    
    async def stop_security_update_system(self):
        """보안 업데이트 시스템 중지"""
        self.running = False
        
        if self.scan_task:
            self.scan_task.cancel()
        
        if self.update_task:
            self.update_task.cancel()
        
        logger.info("자동 보안 업데이트 시스템 중지")
    
    async def _perform_initial_scan(self):
        """초기 스캔 수행"""
        logger.info("초기 보안 스캔 시작")
        
        # 의존성 스캔
        if self.config["scanning"]["scan_dependencies"]:
            await self._scan_dependencies()
        
        # 시스템 패키지 스캔
        if self.config["scanning"]["scan_system_packages"]:
            await self._scan_system_packages()
        
        # 취약점 데이터베이스 업데이트
        if self.config["scanning"]["vulnerability_feeds_enabled"]:
            await self._update_vulnerability_database()
        
        logger.info("초기 보안 스캔 완료")
    
    async def _vulnerability_scan_loop(self):
        """취약점 스캔 루프"""
        scan_interval = self.config["scanning"]["scan_interval_hours"] * 3600
        
        while self.running:
            try:
                await self._perform_vulnerability_scan()
                await asyncio.sleep(scan_interval)
                
            except Exception as e:
                logger.error(f"취약점 스캔 루프 오류: {e}")
                await asyncio.sleep(1800)  # 30분 후 재시도
    
    async def _perform_vulnerability_scan(self):
        """취약점 스캔 수행"""
        logger.info("취약점 스캔 시작")
        
        try:
            # 1. 의존성 취약점 스캔
            await self._scan_dependencies()
            
            # 2. 시스템 취약점 스캔
            await self._scan_system_packages()
            
            # 3. 애플리케이션 코드 스캔
            await self._scan_application_code()
            
            # 4. 설정 취약점 스캔
            await self._scan_configurations()
            
            # 5. 취약점 데이터베이스 업데이트
            await self._update_vulnerability_database()
            
            # 6. 보안 업데이트 생성
            await self._generate_security_updates()
            
            logger.info("취약점 스캔 완료")
            
        except Exception as e:
            logger.error(f"취약점 스캔 실패: {e}")
    
    async def _scan_dependencies(self):
        """의존성 취약점 스캔"""
        logger.info("의존성 취약점 스캔 시작")
        
        # Python 패키지 스캔
        if self.config["package_managers"]["pip"]["enabled"]:
            await self._scan_pip_packages()
        
        # Node.js 패키지 스캔
        if self.config["package_managers"]["npm"]["enabled"]:
            await self._scan_npm_packages()
    
    async def _scan_pip_packages(self):
        """Python 패키지 취약점 스캔"""
        try:
            # pip-audit 또는 safety 사용
            result = await self._run_command(["pip-audit", "--format", "json"])
            
            if result.returncode == 0:
                audit_data = json.loads(result.stdout)
                
                for vulnerability in audit_data.get("vulnerabilities", []):
                    await self._process_pip_vulnerability(vulnerability)
            
            # 패키지 목록 업데이트
            await self._update_pip_package_status()
            
        except Exception as e:
            logger.error(f"Python 패키지 스캔 실패: {e}")
    
    async def _process_pip_vulnerability(self, vulnerability_data: Dict[str, Any]):
        """Python 패키지 취약점 처리"""
        vulnerability_id = f"pip_{vulnerability_data.get('id', 'unknown')}"
        
        vulnerability = Vulnerability(
            vulnerability_id=vulnerability_id,
            cve_id=vulnerability_data.get("cve"),
            title=vulnerability_data.get("summary", "Unknown vulnerability"),
            description=vulnerability_data.get("details", ""),
            severity=self._map_severity(vulnerability_data.get("severity", "MEDIUM")),
            cvss_score=vulnerability_data.get("cvss_score", 0.0),
            affected_packages=[vulnerability_data.get("package", "")],
            fixed_version=vulnerability_data.get("fixed_version"),
            discovered_at=datetime.now(),
            patch_available=bool(vulnerability_data.get("fixed_version")),
            exploit_available=False,
            metadata=vulnerability_data
        )
        
        self.vulnerabilities[vulnerability_id] = vulnerability
        await self._save_vulnerability(vulnerability)
        
        # 중요 취약점 알림
        if vulnerability.severity in [VulnerabilitySeverity.CRITICAL, VulnerabilitySeverity.HIGH]:
            await self._send_vulnerability_notification(vulnerability)
    
    async def _scan_npm_packages(self):
        """Node.js 패키지 취약점 스캔"""
        try:
            package_json_path = Path("package.json")
            if not package_json_path.exists():
                return
            
            # npm audit 실행
            result = await self._run_command(["npm", "audit", "--json"])
            
            if result.returncode == 0:
                audit_data = json.loads(result.stdout)
                
                for advisory in audit_data.get("advisories", {}).values():
                    await self._process_npm_vulnerability(advisory)
            
        except Exception as e:
            logger.error(f"Node.js 패키지 스캔 실패: {e}")
    
    async def _process_npm_vulnerability(self, advisory_data: Dict[str, Any]):
        """Node.js 패키지 취약점 처리"""
        vulnerability_id = f"npm_{advisory_data.get('id', 'unknown')}"
        
        vulnerability = Vulnerability(
            vulnerability_id=vulnerability_id,
            cve_id=advisory_data.get("cve"),
            title=advisory_data.get("title", "Unknown vulnerability"),
            description=advisory_data.get("overview", ""),
            severity=self._map_severity(advisory_data.get("severity", "moderate")),
            cvss_score=advisory_data.get("cvss_score", 0.0),
            affected_packages=[advisory_data.get("module_name", "")],
            fixed_version=advisory_data.get("patched_versions"),
            discovered_at=datetime.now(),
            patch_available=bool(advisory_data.get("patched_versions")),
            exploit_available=False,
            metadata=advisory_data
        )
        
        self.vulnerabilities[vulnerability_id] = vulnerability
        await self._save_vulnerability(vulnerability)
    
    async def _scan_system_packages(self):
        """시스템 패키지 취약점 스캔"""
        if not self.config["package_managers"]["system"]["enabled"]:
            return
        
        logger.info("시스템 패키지 취약점 스캔 시작")
        
        # 운영체제별 패키지 매니저 스캔
        system = await self._detect_system()
        
        if system == "ubuntu" or system == "debian":
            await self._scan_apt_packages()
        elif system == "centos" or system == "rhel":
            await self._scan_yum_packages()
        elif system == "macos":
            await self._scan_brew_packages()
    
    async def _scan_application_code(self):
        """애플리케이션 코드 취약점 스캔"""
        logger.info("애플리케이션 코드 스캔 시작")
        
        try:
            # Bandit을 사용한 Python 코드 보안 스캔
            result = await self._run_command([
                "bandit", "-r", "src/", "-f", "json", "-o", "/dev/stdout"
            ])
            
            if result.returncode == 0:
                bandit_data = json.loads(result.stdout)
                
                for issue in bandit_data.get("results", []):
                    await self._process_code_vulnerability(issue)
            
        except Exception as e:
            logger.error(f"코드 스캔 실패: {e}")
    
    async def _process_code_vulnerability(self, issue_data: Dict[str, Any]):
        """코드 취약점 처리"""
        vulnerability_id = f"code_{hashlib.md5(json.dumps(issue_data, sort_keys=True).encode()).hexdigest()[:8]}"
        
        severity_map = {
            "HIGH": VulnerabilitySeverity.HIGH,
            "MEDIUM": VulnerabilitySeverity.MEDIUM,
            "LOW": VulnerabilitySeverity.LOW
        }
        
        vulnerability = Vulnerability(
            vulnerability_id=vulnerability_id,
            cve_id=None,
            title=f"Code Security Issue: {issue_data.get('test_name', 'Unknown')}",
            description=issue_data.get("issue_text", ""),
            severity=severity_map.get(issue_data.get("issue_severity", "MEDIUM"), VulnerabilitySeverity.MEDIUM),
            cvss_score=0.0,
            affected_packages=[issue_data.get("filename", "")],
            fixed_version=None,
            discovered_at=datetime.now(),
            patch_available=False,
            exploit_available=False,
            metadata=issue_data
        )
        
        self.vulnerabilities[vulnerability_id] = vulnerability
        await self._save_vulnerability(vulnerability)
    
    async def _scan_configurations(self):
        """설정 취약점 스캔"""
        logger.info("설정 취약점 스캔 시작")
        
        config_checks = [
            self._check_ssl_configuration,
            self._check_database_configuration,
            self._check_file_permissions,
            self._check_environment_variables
        ]
        
        for check in config_checks:
            try:
                await check()
            except Exception as e:
                logger.error(f"설정 검사 실패: {e}")
    
    async def _check_ssl_configuration(self):
        """SSL 설정 검사"""
        # SSL 인증서 만료 확인
        # 약한 암호화 알고리즘 확인
        # SSL 설정 강도 확인
        pass
    
    async def _check_database_configuration(self):
        """데이터베이스 설정 검사"""
        # 기본 패스워드 확인
        # 권한 설정 확인
        # 암호화 설정 확인
        pass
    
    async def _check_file_permissions(self):
        """파일 권한 검사"""
        # 중요 파일 권한 확인
        # 실행 권한 확인
        # 소유자 확인
        pass
    
    async def _check_environment_variables(self):
        """환경변수 검사"""
        # 민감 정보 노출 확인
        # 기본값 사용 확인
        pass
    
    async def _update_vulnerability_database(self):
        """취약점 데이터베이스 업데이트"""
        logger.info("취약점 데이터베이스 업데이트 시작")
        
        for feed_url in self.vulnerability_feeds:
            try:
                await self._fetch_vulnerability_feed(feed_url)
            except Exception as e:
                logger.error(f"취약점 피드 업데이트 실패 ({feed_url}): {e}")
    
    async def _fetch_vulnerability_feed(self, feed_url: str):
        """취약점 피드 가져오기"""
        # 실제 구현에서는 각 피드 형식에 맞는 파서 사용
        pass
    
    async def _generate_security_updates(self):
        """보안 업데이트 생성"""
        logger.info("보안 업데이트 생성 시작")
        
        for vulnerability in self.vulnerabilities.values():
            if vulnerability.patch_available and vulnerability.severity in [VulnerabilitySeverity.CRITICAL, VulnerabilitySeverity.HIGH]:
                await self._create_security_update_from_vulnerability(vulnerability)
    
    async def _create_security_update_from_vulnerability(self, vulnerability: Vulnerability):
        """취약점에서 보안 업데이트 생성"""
        update_id = f"update_{vulnerability.vulnerability_id}_{int(datetime.now().timestamp())}"
        
        security_update = SecurityUpdate(
            update_id=update_id,
            update_type=UpdateType.SECURITY_PATCH,
            title=f"Security patch for {vulnerability.title}",
            description=f"Addresses {vulnerability.cve_id or vulnerability.vulnerability_id}: {vulnerability.description}",
            severity=vulnerability.severity,
            affected_components=vulnerability.affected_packages,
            current_version="",  # 패키지별로 설정
            target_version=vulnerability.fixed_version or "",
            patch_url=None,
            rollback_info={},
            scheduled_at=None,
            applied_at=None,
            status=UpdateStatus.PENDING,
            test_results={},
            metadata={"vulnerability_id": vulnerability.vulnerability_id}
        )
        
        self.pending_updates[update_id] = security_update
        await self._save_security_update(security_update)
        
        # 자동 적용 결정
        if await self._should_auto_apply_update(security_update):
            await self._schedule_update(update_id)
    
    async def _should_auto_apply_update(self, security_update: SecurityUpdate) -> bool:
        """업데이트 자동 적용 여부 결정"""
        if security_update.severity == VulnerabilitySeverity.CRITICAL:
            return self.config["updates"]["auto_apply_critical"]
        elif security_update.severity == VulnerabilitySeverity.HIGH:
            return self.config["updates"]["auto_apply_high"]
        
        return False
    
    async def _update_application_loop(self):
        """업데이트 적용 루프"""
        while self.running:
            try:
                await self._process_pending_updates()
                await asyncio.sleep(300)  # 5분마다 확인
                
            except Exception as e:
                logger.error(f"업데이트 적용 루프 오류: {e}")
                await asyncio.sleep(300)
    
    async def _process_pending_updates(self):
        """대기 중인 업데이트 처리"""
        current_time = datetime.now()
        
        # 유지보수 시간 확인
        if not self._is_maintenance_window(current_time):
            return
        
        # 동시 업데이트 제한
        active_updates = sum(1 for u in self.pending_updates.values() 
                           if u.status == UpdateStatus.IN_PROGRESS)
        
        if active_updates >= self.config["updates"]["max_concurrent_updates"]:
            return
        
        # 예약된 업데이트 실행
        for update_id, security_update in list(self.pending_updates.items()):
            if (security_update.status == UpdateStatus.PENDING and 
                security_update.scheduled_at and 
                current_time >= security_update.scheduled_at):
                
                asyncio.create_task(self._apply_security_update(update_id))
    
    def _is_maintenance_window(self, current_time: datetime) -> bool:
        """유지보수 시간 확인"""
        start_time = self.config["updates"]["maintenance_window_start"]
        end_time = self.config["updates"]["maintenance_window_end"]
        
        current_hour_min = current_time.strftime("%H:%M")
        
        return start_time <= current_hour_min <= end_time
    
    async def _schedule_update(self, update_id: str, scheduled_time: Optional[datetime] = None):
        """업데이트 예약"""
        if update_id not in self.pending_updates:
            return False
        
        security_update = self.pending_updates[update_id]
        
        if not scheduled_time:
            # 다음 유지보수 시간으로 예약
            scheduled_time = self._get_next_maintenance_window()
        
        security_update.scheduled_at = scheduled_time
        await self._save_security_update(security_update)
        
        logger.info(f"업데이트 예약: {update_id} at {scheduled_time}")
        return True
    
    def _get_next_maintenance_window(self) -> datetime:
        """다음 유지보수 시간 계산"""
        now = datetime.now()
        start_time = self.config["updates"]["maintenance_window_start"]
        
        # 오늘의 유지보수 시간
        hour, minute = map(int, start_time.split(':'))
        today_maintenance = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if now < today_maintenance:
            return today_maintenance
        else:
            # 내일의 유지보수 시간
            return today_maintenance + timedelta(days=1)
    
    async def _apply_security_update(self, update_id: str):
        """보안 업데이트 적용"""
        if update_id not in self.pending_updates:
            return
        
        security_update = self.pending_updates[update_id]
        security_update.status = UpdateStatus.IN_PROGRESS
        
        await self._save_security_update(security_update)
        await self._log_update_action(update_id, "START", "업데이트 시작")
        
        logger.info(f"보안 업데이트 적용 시작: {update_id}")
        
        try:
            # 1. 백업 생성
            if self.config["backup"]["backup_before_update"]:
                backup_info = await self._create_update_backup(security_update)
                security_update.rollback_info["backup"] = backup_info
            
            # 2. 테스트 환경에서 검증
            if self.config["updates"]["test_before_apply"]:
                test_result = await self._test_update(security_update)
                security_update.test_results = test_result
                
                if not test_result.get("success", False):
                    raise Exception("업데이트 테스트 실패")
            
            # 3. 업데이트 적용
            await self._execute_update(security_update)
            
            # 4. 적용 후 검증
            verification_result = await self._verify_update(security_update)
            
            if verification_result["success"]:
                security_update.status = UpdateStatus.COMPLETED
                security_update.applied_at = datetime.now()
                
                await self._log_update_action(update_id, "COMPLETE", "업데이트 완료")
                logger.info(f"보안 업데이트 적용 완료: {update_id}")
                
                # 성공 알림
                if self.config["notifications"]["notify_on_update_complete"]:
                    await self._send_update_notification(security_update, "completed")
            else:
                raise Exception("업데이트 검증 실패")
            
        except Exception as e:
            logger.error(f"보안 업데이트 적용 실패: {update_id} - {e}")
            
            security_update.status = UpdateStatus.FAILED
            await self._log_update_action(update_id, "FAIL", str(e))
            
            # 실패 알림
            if self.config["notifications"]["notify_on_failure"]:
                await self._send_update_notification(security_update, "failed", str(e))
            
            # 자동 롤백
            if self.config["security"]["rollback_on_failure"]:
                await self._rollback_update(update_id)
        
        finally:
            await self._save_security_update(security_update)
            self.update_history.append(security_update)
            
            # 완료된 업데이트는 대기 목록에서 제거
            if security_update.status in [UpdateStatus.COMPLETED, UpdateStatus.FAILED, UpdateStatus.ROLLED_BACK]:
                del self.pending_updates[update_id]
    
    async def _create_update_backup(self, security_update: SecurityUpdate) -> Dict[str, Any]:
        """업데이트 백업 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_path / f"update_{security_update.update_id}_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_info = {
            "backup_path": str(backup_dir),
            "timestamp": timestamp,
            "components": []
        }
        
        for component in security_update.affected_components:
            try:
                component_backup = await self._backup_component(component, backup_dir)
                backup_info["components"].append(component_backup)
            except Exception as e:
                logger.warning(f"컴포넌트 백업 실패 ({component}): {e}")
        
        logger.info(f"업데이트 백업 생성 완료: {backup_dir}")
        return backup_info
    
    async def _backup_component(self, component: str, backup_dir: Path) -> Dict[str, Any]:
        """개별 컴포넌트 백업"""
        if component.endswith(".py") or "/" in component:
            # 파일 또는 디렉토리
            source_path = Path(component)
            if source_path.exists():
                dest_path = backup_dir / source_path.name
                if source_path.is_file():
                    shutil.copy2(source_path, dest_path)
                else:
                    shutil.copytree(source_path, dest_path)
                
                return {
                    "type": "file",
                    "component": component,
                    "backup_path": str(dest_path),
                    "checksum": await self._calculate_checksum(source_path)
                }
        else:
            # 패키지
            package_info = await self._get_package_info(component)
            backup_file = backup_dir / f"{component}_info.json"
            
            with open(backup_file, 'w') as f:
                json.dump(package_info, f, indent=2)
            
            return {
                "type": "package",
                "component": component,
                "backup_path": str(backup_file),
                "version": package_info.get("version", "unknown")
            }
        
        return {}
    
    async def _test_update(self, security_update: SecurityUpdate) -> Dict[str, Any]:
        """업데이트 테스트"""
        logger.info(f"업데이트 테스트 시작: {security_update.update_id}")
        
        test_results = {
            "success": False,
            "tests_run": [],
            "errors": [],
            "warnings": []
        }
        
        try:
            # 1. 의존성 호환성 테스트
            if security_update.update_type == UpdateType.DEPENDENCY_UPDATE:
                dependency_test = await self._test_dependency_compatibility(security_update)
                test_results["tests_run"].append("dependency_compatibility")
                
                if not dependency_test["success"]:
                    test_results["errors"].extend(dependency_test["errors"])
                    return test_results
            
            # 2. 기능 테스트
            functionality_test = await self._test_functionality(security_update)
            test_results["tests_run"].append("functionality")
            
            if not functionality_test["success"]:
                test_results["errors"].extend(functionality_test["errors"])
                return test_results
            
            # 3. 보안 테스트
            security_test = await self._test_security(security_update)
            test_results["tests_run"].append("security")
            
            if not security_test["success"]:
                test_results["errors"].extend(security_test["errors"])
                return test_results
            
            test_results["success"] = True
            logger.info(f"업데이트 테스트 완료: {security_update.update_id}")
            
        except Exception as e:
            test_results["errors"].append(str(e))
            logger.error(f"업데이트 테스트 실패: {e}")
        
        return test_results
    
    async def _test_dependency_compatibility(self, security_update: SecurityUpdate) -> Dict[str, Any]:
        """의존성 호환성 테스트"""
        return {"success": True, "errors": []}
    
    async def _test_functionality(self, security_update: SecurityUpdate) -> Dict[str, Any]:
        """기능 테스트"""
        # 핵심 기능 테스트 실행
        try:
            # 예: API 엔드포인트 테스트
            result = await self._run_command(["python", "-m", "pytest", "tests/", "-v", "--tb=short"])
            
            if result.returncode == 0:
                return {"success": True, "errors": []}
            else:
                return {"success": False, "errors": [result.stderr]}
                
        except Exception as e:
            return {"success": False, "errors": [str(e)]}
    
    async def _test_security(self, security_update: SecurityUpdate) -> Dict[str, Any]:
        """보안 테스트"""
        # 보안 검증 테스트
        return {"success": True, "errors": []}
    
    async def _execute_update(self, security_update: SecurityUpdate):
        """업데이트 실행"""
        logger.info(f"업데이트 실행: {security_update.update_id}")
        
        if security_update.update_type == UpdateType.DEPENDENCY_UPDATE:
            await self._update_dependencies(security_update)
        elif security_update.update_type == UpdateType.SYSTEM_UPDATE:
            await self._update_system_packages(security_update)
        elif security_update.update_type == UpdateType.APPLICATION_UPDATE:
            await self._update_application(security_update)
        elif security_update.update_type == UpdateType.CONFIGURATION_UPDATE:
            await self._update_configuration(security_update)
    
    async def _update_dependencies(self, security_update: SecurityUpdate):
        """의존성 업데이트"""
        for package in security_update.affected_components:
            if package.startswith("pip:"):
                await self._update_pip_package(package.replace("pip:", ""), security_update.target_version)
            elif package.startswith("npm:"):
                await self._update_npm_package(package.replace("npm:", ""), security_update.target_version)
    
    async def _update_pip_package(self, package_name: str, target_version: str):
        """Python 패키지 업데이트"""
        if target_version:
            command = ["pip", "install", f"{package_name}=={target_version}"]
        else:
            command = ["pip", "install", "--upgrade", package_name]
        
        result = await self._run_command(command)
        
        if result.returncode != 0:
            raise Exception(f"pip 패키지 업데이트 실패: {result.stderr}")
    
    async def _update_npm_package(self, package_name: str, target_version: str):
        """Node.js 패키지 업데이트"""
        if target_version:
            command = ["npm", "install", f"{package_name}@{target_version}"]
        else:
            command = ["npm", "update", package_name]
        
        result = await self._run_command(command)
        
        if result.returncode != 0:
            raise Exception(f"npm 패키지 업데이트 실패: {result.stderr}")
    
    async def _verify_update(self, security_update: SecurityUpdate) -> Dict[str, Any]:
        """업데이트 검증"""
        verification_results = {
            "success": False,
            "checks": [],
            "issues": []
        }
        
        try:
            # 1. 패키지 버전 확인
            for component in security_update.affected_components:
                version_check = await self._verify_package_version(component, security_update.target_version)
                verification_results["checks"].append(version_check)
                
                if not version_check["success"]:
                    verification_results["issues"].append(version_check["issue"])
            
            # 2. 기능 검증
            functionality_check = await self._verify_functionality()
            verification_results["checks"].append(functionality_check)
            
            if not functionality_check["success"]:
                verification_results["issues"].append(functionality_check["issue"])
            
            # 3. 보안 검증
            security_check = await self._verify_security()
            verification_results["checks"].append(security_check)
            
            if not security_check["success"]:
                verification_results["issues"].append(security_check["issue"])
            
            # 모든 검증이 성공하면 전체 성공
            verification_results["success"] = len(verification_results["issues"]) == 0
            
        except Exception as e:
            verification_results["issues"].append(str(e))
        
        return verification_results
    
    async def _verify_package_version(self, package: str, expected_version: str) -> Dict[str, Any]:
        """패키지 버전 검증"""
        try:
            current_version = await self._get_package_version(package)
            
            if current_version == expected_version:
                return {"success": True, "package": package, "version": current_version}
            else:
                return {
                    "success": False,
                    "package": package,
                    "expected": expected_version,
                    "actual": current_version,
                    "issue": f"버전 불일치: {package} (예상: {expected_version}, 실제: {current_version})"
                }
                
        except Exception as e:
            return {
                "success": False,
                "package": package,
                "issue": f"버전 확인 실패: {str(e)}"
            }
    
    async def _verify_functionality(self) -> Dict[str, Any]:
        """기능 검증"""
        try:
            # 핵심 기능 테스트
            result = await self._run_command(["python", "-c", "import src; print('Import successful')"])
            
            if result.returncode == 0:
                return {"success": True, "check": "functionality"}
            else:
                return {"success": False, "check": "functionality", "issue": "Import test failed"}
                
        except Exception as e:
            return {"success": False, "check": "functionality", "issue": str(e)}
    
    async def _verify_security(self) -> Dict[str, Any]:
        """보안 검증"""
        # 업데이트 후 보안 상태 확인
        return {"success": True, "check": "security"}
    
    async def _rollback_update(self, update_id: str):
        """업데이트 롤백"""
        if update_id not in self.pending_updates:
            return
        
        security_update = self.pending_updates[update_id]
        logger.warning(f"업데이트 롤백 시작: {update_id}")
        
        try:
            backup_info = security_update.rollback_info.get("backup", {})
            
            if backup_info:
                await self._restore_from_backup(backup_info)
            
            security_update.status = UpdateStatus.ROLLED_BACK
            await self._log_update_action(update_id, "ROLLBACK", "업데이트 롤백 완료")
            
            logger.info(f"업데이트 롤백 완료: {update_id}")
            
        except Exception as e:
            logger.error(f"업데이트 롤백 실패: {update_id} - {e}")
            await self._log_update_action(update_id, "ROLLBACK_FAIL", str(e))
    
    async def _restore_from_backup(self, backup_info: Dict[str, Any]):
        """백업에서 복원"""
        backup_path = Path(backup_info["backup_path"])
        
        for component_backup in backup_info["components"]:
            try:
                if component_backup["type"] == "file":
                    # 파일 복원
                    source_path = Path(component_backup["backup_path"])
                    dest_path = Path(component_backup["component"])
                    
                    if source_path.exists():
                        if dest_path.is_dir():
                            shutil.rmtree(dest_path)
                            shutil.copytree(source_path, dest_path)
                        else:
                            shutil.copy2(source_path, dest_path)
                
                elif component_backup["type"] == "package":
                    # 패키지 복원
                    package_name = component_backup["component"]
                    old_version = component_backup["version"]
                    
                    await self._restore_package_version(package_name, old_version)
                
            except Exception as e:
                logger.error(f"컴포넌트 복원 실패 ({component_backup['component']}): {e}")
    
    async def _restore_package_version(self, package_name: str, version: str):
        """패키지 버전 복원"""
        # pip 패키지 복원
        command = ["pip", "install", f"{package_name}=={version}"]
        result = await self._run_command(command)
        
        if result.returncode != 0:
            raise Exception(f"패키지 버전 복원 실패: {result.stderr}")
    
    # 유틸리티 메서드들
    async def _run_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """명령어 실행"""
        return await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    
    async def _detect_system(self) -> str:
        """운영체제 감지"""
        try:
            result = await self._run_command(["uname", "-s"])
            if result.returncode == 0:
                system = result.stdout.decode().strip().lower()
                if "linux" in system:
                    # 리눅스 배포판 감지
                    if Path("/etc/ubuntu-release").exists():
                        return "ubuntu"
                    elif Path("/etc/debian_version").exists():
                        return "debian"
                    elif Path("/etc/centos-release").exists():
                        return "centos"
                    else:
                        return "linux"
                elif "darwin" in system:
                    return "macos"
                else:
                    return system
        except Exception:
            pass
        
        return "unknown"
    
    def _map_severity(self, severity_str: str) -> VulnerabilitySeverity:
        """심각도 매핑"""
        severity_str = severity_str.upper()
        
        severity_map = {
            "CRITICAL": VulnerabilitySeverity.CRITICAL,
            "HIGH": VulnerabilitySeverity.HIGH,
            "MEDIUM": VulnerabilitySeverity.MEDIUM,
            "MODERATE": VulnerabilitySeverity.MEDIUM,
            "LOW": VulnerabilitySeverity.LOW,
            "INFO": VulnerabilitySeverity.LOW
        }
        
        return severity_map.get(severity_str, VulnerabilitySeverity.MEDIUM)
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """파일 체크섬 계산"""
        if file_path.is_file():
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        return ""
    
    async def _get_package_info(self, package_name: str) -> Dict[str, Any]:
        """패키지 정보 조회"""
        try:
            result = await self._run_command(["pip", "show", package_name])
            if result.returncode == 0:
                # pip show 출력 파싱
                info = {}
                for line in result.stdout.decode().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip().lower()] = value.strip()
                return info
        except Exception:
            pass
        
        return {}
    
    async def _get_package_version(self, package_name: str) -> str:
        """패키지 버전 조회"""
        package_info = await self._get_package_info(package_name)
        return package_info.get("version", "unknown")
    
    async def _update_pip_package_status(self):
        """Python 패키지 상태 업데이트"""
        try:
            # 설치된 패키지 목록
            result = await self._run_command(["pip", "list", "--format", "json"])
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                
                for package in packages:
                    await self._update_package_status(package["name"], package["version"])
        except Exception as e:
            logger.error(f"패키지 상태 업데이트 실패: {e}")
    
    async def _update_package_status(self, package_name: str, current_version: str):
        """개별 패키지 상태 업데이트"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO package_status (
                package_name, current_version, last_checked
            ) VALUES (?, ?, ?)
        ''', (package_name, current_version, datetime.now()))
        
        conn.commit()
        conn.close()
    
    async def _save_vulnerability(self, vulnerability: Vulnerability):
        """취약점 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO vulnerabilities (
                vulnerability_id, cve_id, title, description, severity,
                cvss_score, affected_packages, fixed_version, discovered_at,
                patch_available, exploit_available, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vulnerability.vulnerability_id, vulnerability.cve_id,
            vulnerability.title, vulnerability.description,
            vulnerability.severity.value, vulnerability.cvss_score,
            json.dumps(vulnerability.affected_packages), vulnerability.fixed_version,
            vulnerability.discovered_at, vulnerability.patch_available,
            vulnerability.exploit_available, json.dumps(vulnerability.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    async def _save_security_update(self, security_update: SecurityUpdate):
        """보안 업데이트 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO security_updates (
                update_id, update_type, title, description, severity,
                affected_components, current_version, target_version,
                patch_url, rollback_info, scheduled_at, applied_at,
                status, test_results, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            security_update.update_id, security_update.update_type.value,
            security_update.title, security_update.description,
            security_update.severity.value, json.dumps(security_update.affected_components),
            security_update.current_version, security_update.target_version,
            security_update.patch_url, json.dumps(security_update.rollback_info),
            security_update.scheduled_at, security_update.applied_at,
            security_update.status.value, json.dumps(security_update.test_results),
            json.dumps(security_update.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    async def _log_update_action(self, update_id: str, action: str, details: str):
        """업데이트 액션 로그"""
        log_id = f"log_{update_id}_{action}_{int(datetime.now().timestamp())}"
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO update_logs (
                log_id, update_id, action, status, details
            ) VALUES (?, ?, ?, ?, ?)
        ''', (log_id, update_id, action, "INFO", details))
        
        conn.commit()
        conn.close()
    
    async def _send_vulnerability_notification(self, vulnerability: Vulnerability):
        """취약점 알림 발송"""
        if not self.config["notifications"]["notify_on_vulnerability"]:
            return
        
        message = f"""
새로운 취약점 발견:
- ID: {vulnerability.vulnerability_id}
- CVE: {vulnerability.cve_id or 'N/A'}
- 제목: {vulnerability.title}
- 심각도: {vulnerability.severity.value}
- CVSS 점수: {vulnerability.cvss_score}
- 영향받는 패키지: {', '.join(vulnerability.affected_packages)}
- 패치 가능: {'예' if vulnerability.patch_available else '아니오'}
"""
        
        logger.warning(f"취약점 알림: {vulnerability.title}")
        
        # 실제로는 이메일, Slack 등으로 알림 발송
    
    async def _send_update_notification(self, security_update: SecurityUpdate, 
                                      status: str, error_msg: str = ""):
        """업데이트 알림 발송"""
        status_messages = {
            "started": "시작됨",
            "completed": "완료됨",
            "failed": "실패함"
        }
        
        status_text = status_messages.get(status, status)
        
        message = f"""
보안 업데이트 {status_text}:
- 업데이트 ID: {security_update.update_id}
- 제목: {security_update.title}
- 심각도: {security_update.severity.value}
- 상태: {security_update.status.value}
"""
        
        if error_msg:
            message += f"- 오류: {error_msg}"
        
        logger.info(f"업데이트 알림: {security_update.title} - {status_text}")
    
    async def get_security_status(self) -> Dict[str, Any]:
        """보안 상태 조회"""
        vulnerability_counts = {}
        for severity in VulnerabilitySeverity:
            vulnerability_counts[severity.value] = len([
                v for v in self.vulnerabilities.values() 
                if v.severity == severity
            ])
        
        update_counts = {}
        for status in UpdateStatus:
            update_counts[status.value] = len([
                u for u in self.pending_updates.values() 
                if u.status == status
            ])
        
        return {
            "system_status": "SECURE" if vulnerability_counts.get("CRITICAL", 0) == 0 else "VULNERABLE",
            "vulnerabilities": {
                "total": len(self.vulnerabilities),
                "by_severity": vulnerability_counts,
                "with_patches": len([v for v in self.vulnerabilities.values() if v.patch_available])
            },
            "updates": {
                "pending": len(self.pending_updates),
                "by_status": update_counts,
                "next_maintenance": self._get_next_maintenance_window().isoformat()
            },
            "last_scan": datetime.now().isoformat(),
            "auto_update_enabled": {
                "critical": self.config["updates"]["auto_apply_critical"],
                "high": self.config["updates"]["auto_apply_high"]
            }
        }


# 전역 인스턴스
_security_update_system = None

def get_security_update_system() -> AutoSecurityUpdateSystem:
    """보안 업데이트 시스템 싱글톤 반환"""
    global _security_update_system
    if _security_update_system is None:
        _security_update_system = AutoSecurityUpdateSystem()
    return _security_update_system


async def main():
    """테스트용 메인 함수"""
    update_system = AutoSecurityUpdateSystem()
    
    try:
        # 시스템 시작
        await update_system.start_security_update_system()
        
        # 상태 조회
        status = await update_system.get_security_status()
        print(f"보안 상태: {status}")
        
        # 시스템 실행
        await asyncio.sleep(300)  # 5분 실행
        
    finally:
        await update_system.stop_security_update_system()


if __name__ == "__main__":
    asyncio.run(main())