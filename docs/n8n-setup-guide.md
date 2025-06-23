# n8n 설정 및 배포 가이드

## 개요
이 문서는 n8n 자동화 서버의 설정, 배포 및 운영 방법을 설명합니다.

## 사전 요구사항

### 시스템 요구사항
- Docker 및 Docker Compose 설치
- 도메인 및 DNS 설정
- SSL 인증서 (Let's Encrypt 자동 발급)
- 최소 2GB RAM, 20GB 디스크 공간

### 필요한 서비스
- Google Sheets API 키
- Gemini API 키
- 쿠팡 파트너스 API 키
- SMTP 서버 설정 (Gmail 권장)
- Slack 웹훅 (선택사항)

## 설치 및 배포

### 1. 환경 설정 파일 생성

```bash
# 환경 변수 템플릿 복사
cp .env.n8n.template .env.n8n

# 환경 변수 편집
vi .env.n8n
```

### 2. 필수 환경 변수 설정

```bash
# 도메인 설정
DOMAIN_NAME=your-domain.com
N8N_SUBDOMAIN=n8n
SSL_EMAIL=admin@your-domain.com

# 인증 설정
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=secure-password-here

# SMTP 설정
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### 3. 배포 실행

```bash
# 배포 스크립트 실행
./scripts/deploy_n8n.sh deploy

# 상태 확인
./scripts/deploy_n8n.sh status
```

## 접속 및 초기 설정

### 웹 UI 접속
- URL: `https://n8n.your-domain.com`
- 사용자명: 환경 변수에서 설정한 값
- 비밀번호: 환경 변수에서 설정한 값

### 초기 워크플로우 가져오기

```bash
# n8n 컨테이너 내부로 접속
docker exec -it n8n sh

# 워크플로우 가져오기
n8n import:workflow --input=/workflows/basic-health-check.json
n8n import:workflow --input=/workflows/error-notification.json
```

## 워크플로우 설정

### 1. 기본 헬스체크 워크플로우
- **목적**: n8n 서비스 상태 모니터링
- **실행 주기**: 5분마다
- **기능**: 
  - HTTP 헬스체크 실행
  - 상태 정보 로깅
  - 실패 시 알림

### 2. 에러 알림 워크플로우
- **목적**: 워크플로우 실행 실패 시 자동 알림
- **트리거**: 에러 발생 시
- **기능**:
  - Slack 알림 발송
  - 이메일 알림 발송
  - 에러 정보 상세 로깅

## 모니터링 및 운영

### 상태 모니터링

```bash
# 전체 상태 확인
./scripts/n8n_monitor.sh status

# 연속 모니터링 시작
./scripts/n8n_monitor.sh monitor

# 리포트 생성
./scripts/n8n_monitor.sh report
```

### 백업 및 복구

```bash
# 수동 백업 생성
./scripts/deploy_n8n.sh backup

# 백업 파일 확인
ls -la backups/

# 백업 복원 (필요시)
docker cp backups/n8n-backup-YYYYMMDD_HHMMSS.tar.gz n8n:/tmp/
docker exec -it n8n sh
cd /home/node/.n8n
tar -xzf /tmp/n8n-backup-YYYYMMDD_HHMMSS.tar.gz
```

### 로그 확인

```bash
# n8n 로그 실시간 확인
./scripts/deploy_n8n.sh logs

# 모니터링 로그 확인
tail -f /var/log/n8n/monitor.log

# 알림 로그 확인
tail -f /var/log/n8n/alerts.log
```

## 문제 해결

### 컨테이너가 시작되지 않는 경우

1. 환경 변수 확인
```bash
# .env.n8n 파일 검증
cat .env.n8n | grep -v '^#' | grep '='
```

2. Docker 로그 확인
```bash
docker logs n8n
docker logs traefik
```

3. 포트 충돌 확인
```bash
netstat -tulpn | grep -E ':(80|443|5678)'
```

### SSL 인증서 문제

1. DNS 설정 확인
```bash
nslookup n8n.your-domain.com
```

2. Let's Encrypt 로그 확인
```bash
docker logs traefik | grep -i "certificate"
```

3. 수동 인증서 갱신
```bash
docker exec traefik sh -c "rm -rf /letsencrypt/acme.json"
docker restart traefik
```

### 성능 문제

1. 리소스 사용량 확인
```bash
./scripts/n8n_monitor.sh status
```

2. 워크플로우 최적화
- 실행 시간 제한 설정
- 불필요한 로깅 비활성화
- 데이터 크기 최적화

3. 자동 재시작 설정
```bash
# 크론탭에 헬스체크 추가
crontab -e
*/5 * * * * /path/to/scripts/n8n_monitor.sh restart
```

## 보안 고려사항

### 1. 네트워크 보안
- Traefik를 통한 SSL/TLS 종료
- 불필요한 포트 노출 방지
- VPN 또는 IP 제한 설정

### 2. 인증 및 권한
- 강력한 Basic Auth 비밀번호 설정
- 정기적인 비밀번호 변경
- API 키 로테이션

### 3. 데이터 보호
- 정기적인 백업 수행
- 백업 데이터 암호화
- 민감한 데이터 마스킹

## 성능 최적화

### 1. 메모리 관리
```bash
# Docker 메모리 제한 설정
# docker-compose.yml에 추가:
# deploy:
#   resources:
#     limits:
#       memory: 2G
```

### 2. 실행 최적화
```bash
# 환경 변수 추가
EXECUTIONS_TIMEOUT=3600
EXECUTIONS_TIMEOUT_MAX=7200
N8N_PAYLOAD_SIZE_MAX=16
```

### 3. 데이터베이스 최적화
- SQLite에서 PostgreSQL로 마이그레이션 (대용량 처리 시)
- 정기적인 실행 데이터 정리
- 인덱스 최적화

## 확장 및 통합

### 1. 외부 서비스 연동
- Google Sheets API 설정
- Slack 웹훅 연동
- 이메일 서비스 통합

### 2. 커스텀 노드 설치
```bash
# 컨테이너 내부에서 실행
docker exec -it n8n sh
cd ~/.n8n/nodes
npm install n8n-nodes-custom-package
```

### 3. 워크플로우 템플릿
- 채널별 RSS 피드 모니터링
- 자동 데이터 분석 파이프라인
- 알림 및 리포팅 시스템

## 유지보수 체크리스트

### 일일 점검
- [ ] 서비스 상태 확인
- [ ] 로그 에러 점검
- [ ] 백업 상태 확인

### 주간 점검
- [ ] 성능 메트릭 리뷰
- [ ] 워크플로우 실행 통계 분석
- [ ] 보안 로그 검토

### 월간 점검
- [ ] 시스템 업데이트 적용
- [ ] 백업 복구 테스트
- [ ] 용량 및 확장성 검토
- [ ] 비밀번호 변경

## 연락처 및 지원

문제 발생 시 연락처:
- 시스템 관리자: admin@your-domain.com
- 긴급 알림: Slack #alerts 채널

추가 문서:
- [n8n 공식 문서](https://docs.n8n.io)
- [Docker Compose 가이드](https://docs.docker.com/compose/)
- [Traefik 설정 가이드](https://doc.traefik.io/traefik/)