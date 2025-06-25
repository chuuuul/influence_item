# 🔧 n8n 워크플로우 활성화 가이드

## 현재 상태
- ✅ n8n 설치됨
- ✅ n8n 실행 중 (프로세스 ID: 7366)
- ✅ 워크플로우 파일 준비됨
- ❌ 워크플로우 활성화 필요

## 🚀 활성화 단계

### 1. n8n 웹 인터페이스 접속
브라우저에서 다음 URL 접속:
```
http://localhost:5678
```

### 2. 워크플로우 Import
1. **"+" 버튼** 클릭 (새 워크플로우 생성)
2. **"Import from File"** 선택
3. **파일 선택**: `n8n-workflows/complete_channel_discovery_workflow.json`
4. **Import** 버튼 클릭

### 3. 환경변수 설정
워크플로우에서 사용하는 환경변수들을 n8n에 설정해야 합니다:

**Settings > Environment Variables에서 설정:**
```
YOUTUBE_API_KEY=AIzaSyB4WMYxl2ED4OQD9TJqF3DnrSlYeS7onyc
GOOGLE_SHEETS_SPREADSHEET_ID=1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/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
CHANNEL_DISCOVERY_API_URL=http://localhost:5001
```

### 4. 워크플로우 활성화
1. **워크플로우 이름**: "Complete Channel Discovery with Google Sheets & Slack"
2. **우상단 토글 버튼**: "Inactive" → **"Active"**로 변경
3. **Save** 버튼 클릭

### 5. 실행 스케줄 확인
- **Daily Schedule (9 AM)** 노드가 `0 9 * * *` (매일 오전 9시)로 설정되어 있는지 확인

## 🧪 테스트 방법

### 수동 테스트
1. **Manual Trigger Webhook** 노드 우클릭
2. **"Execute Node"** 선택
3. 워크플로우가 정상 실행되는지 확인

### API 호출로 테스트
```bash
curl -X POST http://localhost:5678/webhook/trigger-discovery \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["테스트"], "days_back": 3, "max_candidates": 5}'
```

## 📊 실행 결과 확인

### n8n 로그
- **Executions** 탭에서 실행 기록 확인
- 각 노드별 입/출력 데이터 확인

### 외부 확인
- **Google Sheets**: 결과 저장 확인
- **Slack**: 알림 메시지 확인
- **API 로그**: `http://localhost:5001/health`

## 🔍 문제 해결

### 일반적인 문제들

1. **API 서버 연결 실패**
   ```bash
   # API 서버 실행 확인
   curl http://localhost:5001/health
   
   # 안되면 API 서버 재시작
   python src/api/channel_discovery_api.py
   ```

2. **Google Sheets 연결 실패**
   - 서비스 계정 권한 확인
   - 스프레드시트 공유 설정 확인

3. **Slack 알림 실패**
   - 웹훅 URL 유효성 확인
   - 네트워크 연결 확인

### 로그 확인
```bash
# n8n 로그 (콘솔에서 확인)
# API 서버 로그
tail -f logs/api_server.log

# 채널 탐색 로그
tail -f logs/daily_discovery_*.log
```

## ✅ 활성화 완료 체크리스트

- [ ] n8n 웹 인터페이스 접속
- [ ] 워크플로우 Import 완료
- [ ] 환경변수 설정 완료
- [ ] 워크플로우 Active 상태로 변경
- [ ] 수동 테스트 성공
- [ ] 스케줄 확인 (매일 9시)
- [ ] Google Sheets 저장 테스트
- [ ] Slack 알림 테스트

## 🎯 예상 결과

활성화 후:
- **매일 오전 9시**에 자동 실행
- **Google Sheets**에 결과 저장
- **Slack**으로 알림 전송
- **웹훅**으로 수동 실행 가능

---

**다음 단계**: 위 가이드를 따라 n8n에서 워크플로우를 import하고 활성화하세요!