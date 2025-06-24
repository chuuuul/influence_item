# 📱 Slack 웹훅 설정 가이드

## 1단계: Slack 웹훅 생성

### 방법 1: Slack 워크스페이스에서 직접 설정

1. **Slack 워크스페이스에 로그인**
   - https://your-workspace.slack.com

2. **앱 관리 페이지로 이동**
   - 좌측 사이드바에서 "앱" 클릭
   - "앱 찾아보기" 클릭

3. **Incoming Webhooks 검색**
   - "Incoming Webhooks" 검색
   - "Slack에 추가" 버튼 클릭

4. **채널 선택**
   - 알림을 받을 채널 선택 (예: #channel-discovery)
   - "Incoming Webhook 통합 기능 추가" 클릭

5. **웹훅 URL 복사**
   - 생성된 웹훅 URL 복사 (예: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX)

### 방법 2: Slack API 사이트에서 설정

1. **Slack API 사이트 접속**
   - https://api.slack.com/apps

2. **앱 생성**
   - "Create New App" 클릭
   - "From scratch" 선택
   - 앱 이름: "Channel Discovery Bot"
   - 워크스페이스 선택

3. **Incoming Webhooks 활성화**
   - 좌측 메뉴에서 "Incoming Webhooks" 클릭
   - "Activate Incoming Webhooks" 토글 ON
   - "Add New Webhook to Workspace" 클릭
   - 채널 선택 후 "Allow" 클릭

4. **웹훅 URL 복사**
   - 생성된 웹훅 URL 복사

## 2단계: 환경변수 설정

웹훅 URL을 환경변수에 추가:

```bash
# .env 파일에 추가
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#channel-discovery
```

## 3단계: 테스트 메시지 전송

```bash
curl -X POST -H 'Content-type: application/json' \
--data '{"text":"🤖 채널 디스커버리 봇 테스트 메시지입니다!"}' \
YOUR_WEBHOOK_URL
```

## 권장 채널 설정

### 1. #channel-discovery (성공 알림)
- 새로 발견된 채널 후보 알림
- 탐색 완료 리포트

### 2. #alerts (실패 알림)  
- 오류 및 실패 알림
- 시스템 이슈 알림

### 3. #automation (상세 로그)
- 자세한 실행 로그
- 성능 통계