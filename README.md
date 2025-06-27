# 연예인 추천 아이템 자동화 시스템

**PRD v1.0 기반 완전 자동화 파이프라인**

이 시스템은 YouTube 영상에서 연예인이 추천하는 제품을 AI로 자동 분석하고, 수익화 가능한 아이템을 발굴하는 24/7 자동화 솔루션입니다.

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Google Sheets │    │   n8n 마스터     │    │  Slack 알림     │
│   (채널 목록)    │◄──►│   오케스트레이터  │──►│   시스템        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   YouTube API   │◄──►│   FastAPI 서버   │◄──►│  Streamlit      │
│   (영상/채널)    │    │   (분석 엔진)     │    │  대시보드       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Whisper       │    │   Gemini 2.5     │    │  SQLite         │
│   (음성 분석)    │    │   Flash (AI)     │    │  데이터베이스   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 주요 기능

### ✨ AI 2-Pass 분석 파이프라인
- **1단계**: Whisper Small 모델로 고정밀 음성 인식
- **2단계**: Gemini 2.5 Flash로 제품 탐지 및 분석
- **3단계**: PPL 필터링 및 수익화 가능성 평가
- **4단계**: 매력도 스코어링 (감성분석 + 실사용 인증 + 인플루언서 신뢰도)

### 🔄 완전 자동화 워크플로우
- **매일 오전 7시** 자동 실행 (Cron)
- **Google Sheets** 채널 목록 자동 읽기
- **RSS 피드** 신규 영상 수집
- **AI 분석** 후보 아이템 발굴
- **Slack 알림** 결과 실시간 알림

### 📊 실시간 대시보드
- 수익화 후보 실시간 모니터링
- 채널별/연예인별 성과 분석
- 필터링된 아이템 복원 기능
- 매력도 점수 시각화

## 📋 사전 요구사항

### 필수 API 키
1. **YouTube Data API v3**
   - [Google Cloud Console](https://console.developers.google.com/apis/credentials)에서 발급
   - API 활성화 필요: YouTube Data API v3

2. **Google Gemini API**
   - [Google AI Studio](https://makersuite.google.com/app/apikey)에서 발급
   - Gemini 2.5 Flash 모델 사용

3. **Slack 웹훅 URL**
   - [Slack API](https://api.slack.com/messaging/webhooks)에서 생성
   - 워크스페이스 알림 채널 설정

### 시스템 요구사항
- **Python 3.9+**
- **Node.js 18+** (n8n 사용시)
- **최소 8GB RAM** (AI 모델 로딩용)
- **10GB 저장 공간** (모델 + 데이터)

## 🛠️ 설치 및 설정

### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd influence_item
```

### 2. 의존성 설치
```bash
# Python 의존성
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# Streamlit 설치 (대시보드용)
pip install streamlit

# 추가 AI 모델 의존성
pip install faster-whisper google-generativeai
```

### 3. 환경변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# 필수 API 키 설정
nano .env
```

**필수 환경변수:**
```env
YOUTUBE_API_KEY=your_youtube_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
GOOGLE_SHEETS_SPREADSHEET_ID=your_google_sheets_id_here
```

### 4. 데이터베이스 초기화
```bash
# 데이터베이스 디렉토리 생성
mkdir -p data

# 자동으로 SQLite DB가 생성됩니다
python -c "from dashboard.utils.database_manager import get_database_manager; get_database_manager()"
```

## 🚦 시스템 실행

### 개발 환경 실행
```bash
# 1. API 서버 실행 (포트 8000)
python src/api_server.py &

# 2. 대시보드 실행 (포트 8501)
streamlit run dashboard/main_dashboard.py &

# 3. 브라우저에서 확인
open http://localhost:8501
```

### 프로덕션 환경 실행
```bash
# 1. API 서버 (백그라운드)
nohup python src/api_server.py > logs/api_server.log 2>&1 &

# 2. 대시보드 (백그라운드)
nohup streamlit run dashboard/main_dashboard.py --server.port 8501 --server.headless true > logs/dashboard.log 2>&1 &

# 3. n8n 워크플로우 임포트 및 활성화
# n8n-workflows/master_automation_pipeline_v2.json 파일을 n8n에 임포트
```

## 🧪 테스트 실행

### 1. Slack 연동 테스트
```bash
python scripts/test_slack_integration.py
```

### 2. 전체 워크플로우 테스트
```bash
python tests/test_full_workflow.py
```

### 3. 개별 컴포넌트 테스트
```bash
# YouTube API 테스트
python src/youtube_api.py

# AI 분석 파이프라인 테스트
python src/ai_analysis.py

# 데이터베이스 테스트
python dashboard/utils/database_manager.py
```

## 📈 모니터링 및 관리

### 대시보드 메뉴
1. **📊 수익화 후보**: 분석 완료된 아이템 목록
2. **🔍 채널 발견**: 신규 채널 탐색
3. **🚫 필터링 목록**: 수익화 불가 아이템 (복원 가능)
4. **📺 영상 수집**: 채널별 영상 수집 현황

### API 엔드포인트
- **GET** `/health` - 시스템 상태 확인
- **GET** `/statistics` - 전체 통계
- **GET** `/candidates` - 후보 목록 조회
- **POST** `/collect-rss` - RSS 수집 시작
- **POST** `/analyze/batch` - 배치 분석 실행
- **POST** `/notifications/slack` - Slack 알림 발송

### 로그 모니터링
```bash
# API 서버 로그
tail -f logs/api_server.log

# 대시보드 로그
tail -f logs/dashboard.log

# n8n 워크플로우 로그 (n8n UI에서 확인)
```

## 🔧 n8n 워크플로우 설정

### 1. n8n 설치 및 실행
```bash
npm install -g n8n
n8n start
```

### 2. 워크플로우 임포트
1. n8n UI (http://localhost:5678) 접속
2. **Import** 클릭
3. `n8n-workflows/master_automation_pipeline_v2.json` 파일 선택
4. 워크플로우 활성화

### 3. 환경변수 설정 (n8n)
n8n UI에서 다음 환경변수 설정:
- `RSS_AUTOMATION_API_URL`: http://localhost:8000
- `GOOGLE_SHEETS_SPREADSHEET_ID`: Google Sheets ID
- `SLACK_WEBHOOK_URL`: Slack 웹훅 URL

## 📊 성능 최적화

### AI 모델 최적화
```python
# Whisper 모델 크기 조정 (.env 파일)
WHISPER_MODEL_SIZE=small  # tiny, base, small, medium, large

# Gemini API 요청 제한
# 분당 60회 제한 준수 (자동 제어됨)
```

### 데이터베이스 최적화
```sql
-- 인덱스 최적화 (자동 적용됨)
CREATE INDEX idx_status ON candidates(status);
CREATE INDEX idx_created_at ON candidates(created_at);
CREATE INDEX idx_celebrity_name ON candidates(celebrity_name);
```

## 🛡️ 보안 고려사항

### API 키 보안
- `.env` 파일은 절대 Git에 커밋하지 않음
- 프로덕션에서는 환경변수로 직접 설정
- API 키 권한을 최소한으로 제한

### 네트워크 보안
- API 서버는 방화벽 뒤에서 실행
- HTTPS 사용 권장 (프로덕션 환경)
- Rate Limiting 적용 (API 호출 제한)

## 🐛 문제 해결

### 자주 발생하는 문제

#### 1. YouTube API 할당량 초과
```
해결: API 키 로테이션 또는 요청 빈도 조정
설정: .env 파일의 YOUTUBE_API_KEY 업데이트
```

#### 2. Whisper 모델 로딩 실패
```
해결: 메모리 부족 시 모델 크기 축소
설정: WHISPER_MODEL_SIZE=tiny 또는 base
```

#### 3. Gemini API 응답 느림
```
해결: 요청 배치 크기 조정
설정: AI 분석 파이프라인의 배치 사이즈 조정
```

#### 4. Slack 알림 실패
```
확인사항:
- 웹훅 URL 유효성
- 네트워크 연결 상태
- Slack 워크스페이스 권한
```

### 로그 확인
```bash
# 전체 시스템 상태 확인
python tests/test_full_workflow.py

# 개별 컴포넌트 상태 확인
curl http://localhost:8000/health
```

## 📋 운영 체크리스트

### 일일 체크리스트
- [ ] n8n 워크플로우 실행 상태 확인
- [ ] Slack 알림 수신 확인
- [ ] 대시보드 접속 및 신규 후보 확인
- [ ] API 서버 로그 점검

### 주간 체크리스트
- [ ] 데이터베이스 백업
- [ ] API 키 할당량 확인
- [ ] 시스템 성능 모니터링
- [ ] 필터링된 아이템 검토

### 월간 체크리스트
- [ ] AI 모델 성능 평가
- [ ] 채널 목록 업데이트
- [ ] 시스템 보안 점검
- [ ] 수익화 성과 분석

## 🤝 기여 가이드

### 개발 환경 설정
```bash
# 개발 의존성 설치
pip install -r requirements-dev.txt

# 코드 품질 검사
flake8 src/ dashboard/
black src/ dashboard/

# 테스트 실행
pytest tests/
```

### 기여 방법
1. Fork 프로젝트
2. Feature 브랜치 생성
3. 변경사항 커밋
4. Pull Request 생성

## 📞 지원 및 문의

### 기술 지원
- 이슈 트래커: GitHub Issues
- 문서: 프로젝트 Wiki
- 토론: GitHub Discussions

### 라이선스
이 프로젝트는 MIT 라이선스를 따릅니다.

---

**🎯 PRD v1.0 완전 구현 완료**  
**🤖 AI 2-Pass 분석 파이프라인**  
**⚡ 24/7 자동화 워크플로우**  
**📊 실시간 모니터링 대시보드**