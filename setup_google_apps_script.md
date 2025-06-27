# Google Apps Script를 이용한 Google Sheets 연동 설정

## 🚀 빠른 설정 방법 (서비스 계정 없이)

### 1단계: Google Apps Script 프로젝트 생성

1. **Google Sheets 열기**
   - https://docs.google.com/spreadsheets/d/1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY/edit
   - 위 URL로 접속

2. **Apps Script 열기**
   - 메뉴에서 `확장 프로그램` → `Apps Script` 클릭
   - 또는 https://script.google.com 에서 새 프로젝트 생성

3. **코드 복사**
   - 기본 `function myFunction()` 삭제
   - `google_apps_script_solution.js` 파일의 모든 코드를 복사하여 붙여넣기

4. **시트 ID 수정**
   ```javascript
   const SHEET_ID = '1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY'; // 실제 시트 ID
   ```

### 2단계: 웹앱 배포

1. **배포 설정**
   - Apps Script 에디터에서 `배포` → `새 배포` 클릭
   - 유형: `웹앱` 선택

2. **권한 설정**
   - 설명: "N8n Google Sheets 연동"
   - 다음 사용자로 실행: `나`
   - 액세스 권한: `모든 사용자` (또는 `Google 계정이 있는 모든 사용자`)

3. **배포 완료**
   - `배포` 버튼 클릭
   - 권한 승인 (Google 계정 로그인 필요)
   - **웹앱 URL 복사 및 저장** (매우 중요!)

### 3단계: 수동 테스트

1. **Apps Script 에디터에서 테스트**
   ```javascript
   manualTest() // 이 함수를 실행
   ```

2. **웹앱 URL로 테스트**
   ```bash
   curl -X GET "웹앱_URL"
   ```

3. **POST 테스트**
   ```bash
   curl -X POST "웹앱_URL" \
     -H "Content-Type: application/json" \
     -d '{"type": "test"}'
   ```

### 4단계: N8n 워크플로우 설정

1. **.env 파일 업데이트**
   ```env
   GOOGLE_APPS_SCRIPT_URL=웹앱_URL
   ```

2. **N8n 워크플로우에서 사용**
   ```json
   {
     "method": "POST",
     "url": "{{ $env.GOOGLE_APPS_SCRIPT_URL }}",
     "sendBody": true,
     "bodyParameters": {
       "parameters": [
         {
           "name": "type",
           "value": "single"
         },
         {
           "name": "payload",
           "value": "={{ JSON.stringify($json) }}"
         }
       ]
     }
   }
   ```

## 🧪 테스트 시나리오

### 1. 기본 연결 테스트
```bash
curl -X GET "웹앱_URL"
```

### 2. 테스트 데이터 추가
```bash
curl -X POST "웹앱_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test"
  }'
```

### 3. 실제 데이터 추가
```bash
curl -X POST "웹앱_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "single",
    "payload": {
      "channel_name": "테스트 채널",
      "celebrity_name": "아이유",
      "product_name": "아이폰 15",
      "brand": "Apple",
      "category": "전자제품",
      "confidence": "0.95",
      "sentiment": "positive",
      "status": "needs_review",
      "notes": "cURL 테스트"
    }
  }'
```

## 🔧 문제 해결

### 권한 오류
- Apps Script 프로젝트의 권한 설정 확인
- Google 계정 로그인 상태 확인

### 시트 접근 오류
- SHEET_ID가 올바른지 확인
- 시트 공유 권한 확인

### 웹앱 접근 오류
- 배포 설정에서 "모든 사용자" 권한 확인
- 웹앱 URL이 올바른지 확인

## 💡 장점

1. **빠른 설정**: 서비스 계정 없이 즉시 사용 가능
2. **무료**: Google Apps Script는 무료 서비스
3. **안전**: Google 계정 기반 인증
4. **실시간**: 즉시 Google Sheets에 반영

## ⚠️ 제한사항

1. **실행 시간**: 최대 6분
2. **요청 제한**: 일일 제한 있음
3. **동시성**: 동시 실행 제한
4. **복잡도**: 복잡한 로직에는 부적합

하지만 이 프로젝트의 용도에는 충분합니다!