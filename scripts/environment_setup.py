#!/usr/bin/env python3
"""
환경 설정 자동화 스크립트
T10_S01_M04: Environment Setup Automation

이 스크립트는 개발, 테스트, 프로덕션 환경을 자동으로 설정합니다.
"""

import os
import sys
import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import secrets
import string

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    """환경 설정"""
    name: str
    database_url: str
    redis_url: str
    debug: bool
    log_level: str
    api_rate_limit: int
    cache_ttl: int
    backup_enabled: bool
    monitoring_enabled: bool
    ssl_enabled: bool


class EnvironmentSetup:
    """환경 설정 자동화"""
    
    def __init__(self):
        """초기화"""
        self.project_root = project_root
        self.environments = {
            "development": EnvironmentConfig(
                name="development",
                database_url="sqlite:///influence_item_dev.db",
                redis_url="redis://localhost:6379/0",
                debug=True,
                log_level="DEBUG",
                api_rate_limit=1000,
                cache_ttl=300,
                backup_enabled=False,
                monitoring_enabled=False,
                ssl_enabled=False
            ),
            "testing": EnvironmentConfig(
                name="testing",
                database_url="sqlite:///influence_item_test.db",
                redis_url="redis://localhost:6379/1",
                debug=False,
                log_level="INFO",
                api_rate_limit=500,
                cache_ttl=600,
                backup_enabled=True,
                monitoring_enabled=True,
                ssl_enabled=False
            ),
            "production": EnvironmentConfig(
                name="production",
                database_url="postgresql://user:pass@localhost:5432/influence_item",
                redis_url="redis://localhost:6379/2",
                debug=False,
                log_level="WARNING",
                api_rate_limit=100,
                cache_ttl=3600,
                backup_enabled=True,
                monitoring_enabled=True,
                ssl_enabled=True
            )
        }
        
        # 필수 디렉토리
        self.required_directories = [
            "logs",
            "temp",
            "backups",
            "ssl",
            "screenshots",
            "channel_discovery_results",
            "daily_reports",
            "credentials"
        ]
        
        # 환경별 설정 파일 템플릿
        self.config_templates = {
            ".env": self._get_env_template(),
            "docker-compose.override.yml": self._get_docker_override_template(),
            "nginx.conf": self._get_nginx_template(),
            "monitoring.yml": self._get_monitoring_template()
        }
    
    def setup_environment(self, env_name: str) -> bool:
        """특정 환경 설정"""
        try:
            if env_name not in self.environments:
                raise ValueError(f"Unknown environment: {env_name}")
            
            config = self.environments[env_name]
            logger.info(f"🚀 {env_name} 환경 설정을 시작합니다...")
            
            # 1. 디렉토리 생성
            self._create_directories()
            
            # 2. 환경 변수 파일 생성
            self._create_env_files(config)
            
            # 3. 설정 파일 생성
            self._create_config_files(config)
            
            # 4. 데이터베이스 초기화
            self._initialize_database(config)
            
            # 5. SSL 인증서 설정 (프로덕션만)
            if config.ssl_enabled:
                self._setup_ssl_certificates()
            
            # 6. 모니터링 설정
            if config.monitoring_enabled:
                self._setup_monitoring(config)
            
            # 7. 백업 설정
            if config.backup_enabled:
                self._setup_backup_system(config)
            
            # 8. 서비스 설정 검증
            self._validate_setup(config)
            
            logger.info(f"✅ {env_name} 환경 설정이 완료되었습니다!")
            return True
            
        except Exception as e:
            logger.error(f"❌ {env_name} 환경 설정 실패: {e}")
            return False
    
    def _create_directories(self):
        """필수 디렉토리 생성"""
        logger.info("📁 필수 디렉토리 생성 중...")
        
        for directory in self.required_directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True, parents=True)
            logger.debug(f"디렉토리 생성: {dir_path}")
        
        # 특별한 권한이 필요한 디렉토리
        sensitive_dirs = ["credentials", "ssl", "backups"]
        for directory in sensitive_dirs:
            dir_path = self.project_root / directory
            if dir_path.exists():
                os.chmod(dir_path, 0o700)  # rwx------
    
    def _create_env_files(self, config: EnvironmentConfig):
        """환경 변수 파일 생성"""
        logger.info("🔧 환경 변수 파일 생성 중...")
        
        # 기본 .env 파일
        env_content = self._generate_env_content(config)
        env_path = self.project_root / f".env.{config.name}"
        
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        # 메인 .env 파일에 링크 (개발 환경만)
        if config.name == "development":
            main_env_path = self.project_root / ".env"
            if not main_env_path.exists():
                shutil.copy2(env_path, main_env_path)
        
        # 파일 권한 설정
        os.chmod(env_path, 0o600)  # rw-------
        
        logger.info(f"환경 변수 파일 생성: {env_path}")
    
    def _generate_env_content(self, config: EnvironmentConfig) -> str:
        """환경 변수 내용 생성"""
        # API 키 생성 (실제로는 실제 값으로 설정해야 함)
        api_keys = {
            "YOUTUBE_API_KEY": self._generate_secure_key(40),
            "OPENAI_API_KEY": self._generate_secure_key(32),
            "GOOGLE_API_KEY": self._generate_secure_key(39),
            "SLACK_BOT_TOKEN": self._generate_secure_key(55),
            "SLACK_WEBHOOK_URL": f"https://hooks.slack.com/services/{self._generate_secure_key(11)}/{self._generate_secure_key(11)}/{self._generate_secure_key(24)}"
        }
        
        content = f"""# {config.name.upper()} Environment Configuration
# Generated on {datetime.now().isoformat()}

# Environment
ENVIRONMENT={config.name}
DEBUG={str(config.debug).lower()}
LOG_LEVEL={config.log_level}

# Database
DATABASE_URL={config.database_url}
DB_POOL_SIZE=20
DB_TIMEOUT=30

# Cache
REDIS_URL={config.redis_url}
CACHE_TTL={config.cache_ttl}
CACHE_MAX_CONNECTIONS=100

# API Configuration
API_RATE_LIMIT={config.api_rate_limit}
API_TIMEOUT=30
MAX_CONCURRENT_REQUESTS=100

# Security
SECRET_KEY={self._generate_secure_key(32)}
JWT_SECRET={self._generate_secure_key(32)}
ENCRYPTION_KEY={self._generate_secure_key(32)}

# API Keys (Replace with actual values)
{chr(10).join(f'{key}={value}' for key, value in api_keys.items())}

# Google Sheets
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_APPLICATION_CREDENTIALS=./credentials/google_sheets_credentials.json

# Monitoring
MONITORING_ENABLED={str(config.monitoring_enabled).lower()}
HEALTH_CHECK_INTERVAL=30
METRICS_COLLECTION_INTERVAL=60

# Backup
BACKUP_ENABLED={str(config.backup_enabled).lower()}
BACKUP_RETENTION_DAYS=7
BACKUP_SCHEDULE=0 3 * * *

# SSL
SSL_ENABLED={str(config.ssl_enabled).lower()}
SSL_CERT_PATH=./ssl/cert.pem
SSL_KEY_PATH=./ssl/key.pem

# Performance
WORKER_PROCESSES=4
WORKER_THREADS=2
MAX_MEMORY_PER_WORKER=512MB

# Feature Flags
ENABLE_GPU_ACCELERATION=true
ENABLE_ADVANCED_FILTERING=true
ENABLE_REAL_TIME_MONITORING=true
ENABLE_AUTO_SCALING=false
"""
        return content
    
    def _generate_secure_key(self, length: int) -> str:
        """안전한 키 생성"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _create_config_files(self, config: EnvironmentConfig):
        """설정 파일 생성"""
        logger.info("📄 설정 파일 생성 중...")
        
        # Docker Compose override 파일
        self._create_docker_override(config)
        
        # Nginx 설정 파일
        if config.ssl_enabled:
            self._create_nginx_config(config)
        
        # 모니터링 설정 파일
        if config.monitoring_enabled:
            self._create_monitoring_config(config)
        
        # 로깅 설정 파일
        self._create_logging_config(config)
    
    def _create_docker_override(self, config: EnvironmentConfig):
        """Docker Compose override 파일 생성"""
        override_content = f"""version: '3.8'

services:
  cpu-server:
    environment:
      - ENVIRONMENT={config.name}
      - DEBUG={str(config.debug).lower()}
      - LOG_LEVEL={config.log_level}
    {"restart: unless-stopped" if config.name == "production" else ""}
    
  gpu-server:
    environment:
      - ENVIRONMENT={config.name}
      - DEBUG={str(config.debug).lower()}
      - LOG_LEVEL={config.log_level}
    {"restart: unless-stopped" if config.name == "production" else ""}
    
  {"redis:" if config.name == "production" else "# redis:"}
  {"  image: redis:7-alpine" if config.name == "production" else ""}
  {"  restart: unless-stopped" if config.name == "production" else ""}
  {"  ports:" if config.name == "production" else ""}
  {"    - '6379:6379'" if config.name == "production" else ""}
  {"  volumes:" if config.name == "production" else ""}
  {"    - redis_data:/data" if config.name == "production" else ""}

{"volumes:" if config.name == "production" else ""}
{"  redis_data:" if config.name == "production" else ""}
"""
        
        override_path = self.project_root / f"docker-compose.{config.name}.yml"
        with open(override_path, 'w') as f:
            f.write(override_content)
    
    def _create_nginx_config(self, config: EnvironmentConfig):
        """Nginx 설정 파일 생성"""
        nginx_content = f"""events {{
    worker_connections 1024;
}}

http {{
    upstream cpu_backend {{
        server cpu-server:8501;
    }}
    
    upstream gpu_backend {{
        server gpu-server:8001;
    }}
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate={config.api_rate_limit}r/h;
    
    server {{
        listen 80;
        server_name localhost;
        
        {"# Redirect HTTP to HTTPS" if config.ssl_enabled else ""}
        {"return 301 https://$server_name$request_uri;" if config.ssl_enabled else ""}
    }}
    
    {"server {" if config.ssl_enabled else ""}
    {"    listen 443 ssl http2;" if config.ssl_enabled else ""}
    {"    server_name localhost;" if config.ssl_enabled else ""}
    {"" if config.ssl_enabled else ""}
    {"    ssl_certificate /etc/nginx/ssl/cert.pem;" if config.ssl_enabled else ""}
    {"    ssl_certificate_key /etc/nginx/ssl/key.pem;" if config.ssl_enabled else ""}
    {"    ssl_protocols TLSv1.2 TLSv1.3;" if config.ssl_enabled else ""}
    {"    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;" if config.ssl_enabled else ""}
    {"" if config.ssl_enabled else ""}
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        {"add_header Strict-Transport-Security 'max-age=31536000; includeSubDomains; preload';" if config.ssl_enabled else ""}
        
        # API endpoints
        location /api/ {{
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://gpu_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            {"proxy_set_header X-Forwarded-Proto https;" if config.ssl_enabled else ""}
        }}
        
        # Dashboard
        location / {{
            proxy_pass http://cpu_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            {"proxy_set_header X-Forwarded-Proto https;" if config.ssl_enabled else ""}
            
            # WebSocket support for Streamlit
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 86400;
        }}
    {"}" if config.ssl_enabled else ""}
}}
"""
        
        nginx_path = self.project_root / f"nginx.{config.name}.conf"
        with open(nginx_path, 'w') as f:
            f.write(nginx_content)
    
    def _create_monitoring_config(self, config: EnvironmentConfig):
        """모니터링 설정 파일 생성"""
        monitoring_content = f"""# Monitoring Configuration for {config.name}
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'influence-item-cpu'
    static_configs:
      - targets: ['cpu-server:8501']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'influence-item-gpu'
    static_configs:
      - targets: ['gpu-server:8001']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

# Alert rules
groups:
  - name: influence-item-alerts
    rules:
      - alert: HighCPUUsage
        expr: cpu_usage_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          
      - alert: HighMemoryUsage
        expr: memory_usage_percent > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"
          
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
"""
        
        monitoring_path = self.project_root / f"monitoring.{config.name}.yml"
        with open(monitoring_path, 'w') as f:
            f.write(monitoring_content)
    
    def _create_logging_config(self, config: EnvironmentConfig):
        """로깅 설정 파일 생성"""
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                },
                "detailed": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": config.log_level,
                    "formatter": "standard",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": config.log_level,
                    "formatter": "detailed",
                    "filename": f"logs/{config.name}.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5
                }
            },
            "loggers": {
                "": {
                    "level": config.log_level,
                    "handlers": ["console", "file"],
                    "propagate": False
                }
            }
        }
        
        logging_path = self.project_root / f"logging.{config.name}.json"
        with open(logging_path, 'w') as f:
            json.dump(logging_config, f, indent=2)
    
    def _initialize_database(self, config: EnvironmentConfig):
        """데이터베이스 초기화"""
        logger.info("🗄️ 데이터베이스 초기화 중...")
        
        try:
            # SQLite 데이터베이스인 경우
            if "sqlite" in config.database_url:
                db_path = config.database_url.split("///")[1]
                db_file = self.project_root / db_path
                
                # 데이터베이스 파일이 없으면 생성
                if not db_file.exists():
                    db_file.touch()
                    logger.info(f"SQLite 데이터베이스 생성: {db_file}")
                
                # 기본 테이블 생성 (실제로는 마이그레이션 스크립트 실행)
                # 여기서는 단순화된 버전으로 구현
                
            # PostgreSQL 데이터베이스인 경우
            elif "postgresql" in config.database_url:
                logger.info("PostgreSQL 데이터베이스 연결 확인...")
                # 실제로는 psycopg2나 SQLAlchemy를 사용하여 연결 테스트
                
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
    
    def _setup_ssl_certificates(self):
        """SSL 인증서 설정"""
        logger.info("🔒 SSL 인증서 설정 중...")
        
        ssl_dir = self.project_root / "ssl"
        cert_path = ssl_dir / "cert.pem"
        key_path = ssl_dir / "key.pem"
        
        # 자체 서명 인증서 생성 (개발용)
        if not cert_path.exists() or not key_path.exists():
            try:
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:4096",
                    "-keyout", str(key_path),
                    "-out", str(cert_path),
                    "-days", "365",
                    "-nodes",
                    "-subj", "/C=KR/ST=Seoul/L=Seoul/O=InfluenceItem/OU=IT/CN=localhost"
                ], check=True, capture_output=True)
                
                # 파일 권한 설정
                os.chmod(cert_path, 0o644)
                os.chmod(key_path, 0o600)
                
                logger.info("자체 서명 SSL 인증서 생성 완료")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"SSL 인증서 생성 실패: {e}")
        else:
            logger.info("기존 SSL 인증서 사용")
    
    def _setup_monitoring(self, config: EnvironmentConfig):
        """모니터링 시스템 설정"""
        logger.info("📊 모니터링 시스템 설정 중...")
        
        # Prometheus 설정 파일 생성
        prometheus_config = f"""global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'influence-item'
    static_configs:
      - targets: ['localhost:8501', 'localhost:8001']
    scrape_interval: 30s
"""
        
        prometheus_path = self.project_root / "prometheus.yml"
        with open(prometheus_path, 'w') as f:
            f.write(prometheus_config)
        
        # Grafana 대시보드 설정 생성
        grafana_dashboard = {
            "dashboard": {
                "title": f"Influence Item - {config.name.title()}",
                "panels": [
                    {
                        "title": "CPU Usage",
                        "type": "graph",
                        "targets": [{"expr": "cpu_usage_percent"}]
                    },
                    {
                        "title": "Memory Usage",
                        "type": "graph",
                        "targets": [{"expr": "memory_usage_percent"}]
                    },
                    {
                        "title": "Request Rate",
                        "type": "graph",
                        "targets": [{"expr": "http_requests_per_second"}]
                    }
                ]
            }
        }
        
        grafana_path = self.project_root / f"grafana-dashboard-{config.name}.json"
        with open(grafana_path, 'w') as f:
            json.dump(grafana_dashboard, f, indent=2)
    
    def _setup_backup_system(self, config: EnvironmentConfig):
        """백업 시스템 설정"""
        logger.info("💾 백업 시스템 설정 중...")
        
        # 백업 스크립트 생성
        backup_script = f"""#!/bin/bash
# Backup script for {config.name} environment
# Generated on {datetime.now().isoformat()}

set -euo pipefail

BACKUP_DIR="{self.project_root}/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.tar.gz"

echo "Starting backup for {config.name} environment..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
if [[ "{config.database_url}" == sqlite* ]]; then
    DB_FILE=$(echo "{config.database_url}" | sed 's/sqlite:\/\/\///')
    if [[ -f "$DB_FILE" ]]; then
        cp "$DB_FILE" "$BACKUP_DIR/database_$DATE.db"
        echo "Database backup completed"
    fi
fi

# Configuration backup
tar -czf "$BACKUP_FILE" \\
    --exclude="*.log" \\
    --exclude="temp/*" \\
    --exclude="node_modules/*" \\
    --exclude="venv/*" \\
    --exclude=".git/*" \\
    config/ \\
    credentials/ \\
    ssl/ \\
    .env.{config.name} \\
    2>/dev/null || true

echo "Backup completed: $BACKUP_FILE"

# Cleanup old backups (keep last 7 days)
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete 2>/dev/null || true

echo "Old backups cleaned up"
"""
        
        backup_script_path = self.project_root / f"backup_{config.name}.sh"
        with open(backup_script_path, 'w') as f:
            f.write(backup_script)
        
        # 실행 권한 부여
        os.chmod(backup_script_path, 0o755)
        
        # Cron 작업 설정 (프로덕션만)
        if config.name == "production":
            crontab_entry = f"0 3 * * * {backup_script_path}\n"
            crontab_path = self.project_root / "crontab.txt"
            with open(crontab_path, 'a') as f:
                f.write(crontab_entry)
    
    def _validate_setup(self, config: EnvironmentConfig):
        """설정 검증"""
        logger.info("✅ 설정 검증 중...")
        
        validations = []
        
        # 필수 파일 확인
        required_files = [
            f".env.{config.name}",
            f"docker-compose.{config.name}.yml",
            f"logging.{config.name}.json"
        ]
        
        for file_name in required_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                validations.append(f"✅ {file_name} 존재")
            else:
                validations.append(f"❌ {file_name} 누락")
        
        # SSL 인증서 확인 (필요한 경우)
        if config.ssl_enabled:
            ssl_files = ["ssl/cert.pem", "ssl/key.pem"]
            for ssl_file in ssl_files:
                ssl_path = self.project_root / ssl_file
                if ssl_path.exists():
                    validations.append(f"✅ {ssl_file} 존재")
                else:
                    validations.append(f"❌ {ssl_file} 누락")
        
        # 디렉토리 권한 확인
        sensitive_dirs = ["credentials", "ssl", "backups"]
        for directory in sensitive_dirs:
            dir_path = self.project_root / directory
            if dir_path.exists():
                stat = dir_path.stat()
                mode = oct(stat.st_mode)[-3:]
                if mode == "700":
                    validations.append(f"✅ {directory} 권한 올바름")
                else:
                    validations.append(f"⚠️ {directory} 권한 확인 필요: {mode}")
        
        for validation in validations:
            logger.info(validation)
    
    def _get_env_template(self):
        """환경 변수 템플릿"""
        return "# Environment template will be generated dynamically"
    
    def _get_docker_override_template(self):
        """Docker override 템플릿"""
        return "# Docker override template will be generated dynamically"
    
    def _get_nginx_template(self):
        """Nginx 템플릿"""
        return "# Nginx template will be generated dynamically"
    
    def _get_monitoring_template(self):
        """모니터링 템플릿"""
        return "# Monitoring template will be generated dynamically"
    
    def setup_all_environments(self) -> Dict[str, bool]:
        """모든 환경 설정"""
        results = {}
        
        for env_name in self.environments.keys():
            logger.info(f"🔧 {env_name} 환경 설정 중...")
            results[env_name] = self.setup_environment(env_name)
        
        return results
    
    def cleanup_environment(self, env_name: str):
        """환경 정리"""
        logger.info(f"🧹 {env_name} 환경 정리 중...")
        
        files_to_remove = [
            f".env.{env_name}",
            f"docker-compose.{env_name}.yml",
            f"nginx.{env_name}.conf",
            f"monitoring.{env_name}.yml",
            f"logging.{env_name}.json",
            f"grafana-dashboard-{env_name}.json",
            f"backup_{env_name}.sh"
        ]
        
        for file_name in files_to_remove:
            file_path = self.project_root / file_name
            if file_path.exists():
                file_path.unlink()
                logger.info(f"삭제됨: {file_name}")


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="환경 설정 자동화")
    parser.add_argument("action", choices=["setup", "cleanup", "all"], help="실행할 액션")
    parser.add_argument("--env", choices=["development", "testing", "production"], help="대상 환경")
    
    args = parser.parse_args()
    
    setup = EnvironmentSetup()
    
    if args.action == "setup":
        if args.env:
            success = setup.setup_environment(args.env)
            return 0 if success else 1
        else:
            print("❌ --env 옵션이 필요합니다")
            return 1
    
    elif args.action == "cleanup":
        if args.env:
            setup.cleanup_environment(args.env)
            return 0
        else:
            print("❌ --env 옵션이 필요합니다")
            return 1
    
    elif args.action == "all":
        results = setup.setup_all_environments()
        success_count = sum(results.values())
        total_count = len(results)
        
        print(f"\n📊 결과: {success_count}/{total_count} 환경 설정 완료")
        for env, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {env}")
        
        return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())