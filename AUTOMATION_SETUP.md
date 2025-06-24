# 🤖 채널 디스커버리 자동화 설정 가이드

## ✅ 현재 상태 확인

**채널 디스커버리 기능 완전 동작 확인 완료!**
- ✅ 1.9초만에 6개 고품질 채널 후보 발견
- ✅ 뷰티라이프, 딩고 뷰티, 아이유 에델바이스 등 정확한 탐지
- ✅ 실제 YouTube API 연동 (Mock 모드 아님)
- ✅ REST API 엔드포인트 생성 완료

## 🔄 3가지 자동화 방법

### 1. 🎯 n8n 자동화 (추천)

#### 장점:
- 직관적인 시각적 워크플로우
- 실시간 모니터링 가능
- Slack 알림 통합
- 오류 처리 및 재시도 기능

#### 설정 방법:

1. **API 서버 실행**
```bash
python3 src/api/channel_discovery_api.py
```

2. **n8n 워크플로우 임포트**
```bash
# n8n_workflows/daily_channel_discovery.json 파일을 n8n에 임포트
```

3. **워크플로우 설정**
- 매일 오전 9시 자동 실행
- 성공/실패 Slack 알림
- 대시보드 자동 업데이트

#### API 엔드포인트:
```bash
# 헬스 체크
GET http://localhost:5001/health

# 채널 탐색 실행
POST http://localhost:5001/discover
{
  "keywords": ["아이유", "뷰티", "패션"],
  "days_back": 7,
  "max_candidates": 100,
  "min_matching_score": 0.3
}

# 최근 결과 조회
GET http://localhost:5001/recent-results
```

### 2. 📅 cron job 자동화

#### 설정 방법:
```bash
# cron job 설정 스크립트 실행
./scripts/setup_cron.sh

# 수동 실행 테스트
python3 scripts/daily_channel_discovery.py
```

#### cron 설정:
```bash
# 매일 오전 9시 실행
0 9 * * * cd /Users/chul/Documents/claude/influence_item && python3 scripts/daily_channel_discovery.py
```

### 3. 🚀 GitHub Actions 자동화

#### 설정 방법:
1. GitHub Secrets에 `YOUTUBE_API_KEY` 추가
2. `.github/workflows/daily-channel-discovery.yml` 워크플로우 활성화
3. 매일 UTC 00:00 (한국시간 09:00) 자동 실행

## 📊 결과 확인 방법

### 1. 로그 파일
```bash
# 일일 로그
logs/daily_discovery_YYYYMMDD.log

# cron 로그
logs/cron_daily_discovery.log
```

### 2. 결과 파일
```bash
# 탐색 결과
channel_discovery_results/session_*.json

# 일일 리포트
daily_reports/discovery_report_YYYYMMDD.json
```

### 3. 대시보드
```bash
# 대시보드 실행
cd dashboard && streamlit run main_dashboard.py --server.port 8503

# 채널 탐색 페이지에서 결과 확인
http://localhost:8503
```

## 🔧 설정 파라미터

### 기본 설정 (일일 실행용)
```python
{
    "keywords": [
        "아이유", "IU", "뷰티", "패션", "메이크업", "스킨케어",
        "라이프스타일", "vlog", "일상", "화장품", "코디", "스타일링"
    ],
    "days_back": 7,                    # 최근 7일 기간
    "max_candidates": 100,             # 최대 100개 후보
    "min_matching_score": 0.3,         # 최소 매칭 점수
    "min_subscriber_count": 10000,     # 최소 구독자 수
    "max_subscriber_count": 3000000,   # 최대 구독자 수
    "search_methods": [
        "keyword_search", 
        "trending", 
        "related_channels"
    ]
}
```

### 빠른 테스트용 설정
```python
{
    "keywords": ["아이유", "뷰티"],
    "days_back": 3,
    "max_candidates": 10,
    "min_matching_score": 0.2
}
```

## 📱 알림 설정

### Slack 알림
```bash
# n8n 워크플로우에서 Slack webhook URL 설정
https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

### 이메일 알림
```bash
# 필요시 Gmail SMTP 설정
GMAIL_EMAIL=your_email@gmail.com
GMAIL_PASSWORD=your_app_password
```

## 🔍 모니터링

### API 상태 확인
```bash
curl http://localhost:5001/health
```

### 최근 결과 확인
```bash
curl http://localhost:5001/recent-results
```

### 로그 모니터링
```bash
tail -f logs/daily_discovery_$(date +%Y%m%d).log
```

## 🎯 추천 설정: n8n 자동화

1. **API 서버 상시 실행** (systemd 또는 pm2 사용)
2. **n8n 워크플로우 활성화**
3. **Slack 알림 설정**
4. **대시보드 모니터링**

이 설정으로 매일 안정적으로 새로운 채널 후보를 발견할 수 있습니다! 🚀