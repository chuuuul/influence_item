# Google Sheets 연동 설정 가이드

## 🔧 완료된 설정 현황

### 1. Google Cloud Console 설정
- ✅ **프로젝트**: influence-item-youtube
- ✅ **Google Sheets API**: 활성화 완료
- ✅ **서비스 계정**: Influence Item Sheets API 생성됨
  - 이메일: `influence-item-sheets@influence-item-youtube.iam.gserviceaccount.com`
  - 키 ID: `be67546c0c95f72d44f0937af57146c1df2cd90e`

### 2. 인증 파일
- ✅ **위치**: `/Users/chul/.config/gspread/credentials.json`
- ✅ **파일명**: `influence-item-youtube-be67546c0c95.json`
- ✅ **권한**: Google Sheets 읽기/쓰기 가능

### 3. 환경변수 설정 (.env)
```bash
# Google Sheets Settings
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY/edit?gid=0#gid=0
GOOGLE_SHEET_ID=1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY

# Google Sheets OAuth Settings
GOOGLE_SHEETS_CREDENTIALS_PATH=/Users/chul/.config/gspread/credentials.json
GOOGLE_SHEETS_SERVICE_ACCOUNT_EMAIL=influence-item-sheets@influence-item-youtube.iam.gserviceaccount.com

# API Keys
YOUTUBE_API_KEY=AIzaSyAz6Glv4zMYRv1MnZPRXTm5c97jks-2T34
```

### 4. 구현된 모듈들
- ✅ `dashboard/utils/google_sheets_oauth.py` - OAuth 인증 클라이언트
- ✅ `dashboard/utils/csv_data_manager.py` - CSV 백업 매니저  
- ✅ `dashboard/utils/google_sheets_api_key.py` - API 키 클라이언트
- ✅ `dashboard/views/google_sheets_management.py` - 대시보드 UI

## 🧪 테스트 스크립트들
- ✅ `test_google_sheets_direct.py` - 직접 API 테스트
- ✅ `test_oauth_google_sheets.py` - OAuth 통합 테스트
- ✅ `test_dashboard_integration.py` - 대시보드 통합 테스트

## 📋 실제 Google Sheets
- **시트명**: influence_item
- **URL**: https://docs.google.com/spreadsheets/d/1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY/edit
- **데이터 구조**:
  - 채널명 (A열)
  - 채널 ID (B열) 
  - 카테고리 (C열)
  - 구독자수 (D열)
  - 상태 (E열)
  - 마지막 업데이트 (F열)

## 🚀 사용 방법

### 대시보드에서 테스트
```bash
cd /Users/chul/Documents/claude/influence_item
python3 -m streamlit run dashboard/main_dashboard.py --server.port 8504
```

### 직접 API 테스트
```bash
python3 test_google_sheets_direct.py
python3 test_oauth_google_sheets.py
python3 test_dashboard_integration.py
```

## ⚠️ 중요 파일들
1. **인증 키**: `/Users/chul/.config/gspread/credentials.json` 
2. **환경 설정**: `/Users/chul/Documents/claude/influence_item/.env`
3. **백업 데이터**: `/Users/chul/Documents/claude/influence_item/data/channels.csv`

## 💡 문제 해결
만약 연결이 안 되면:
1. 인증 파일 경로 확인: `/Users/chul/.config/gspread/credentials.json`
2. Google Sheets API 활성화 확인: Google Cloud Console
3. 서비스 계정 키 유효성 확인
4. .env 파일 환경변수 확인

---
**✅ 모든 설정 완료됨 - 2025-06-27**