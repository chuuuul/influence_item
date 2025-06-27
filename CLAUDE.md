- 무조건 prd문서를 지켜가며 개발할 것
- 개발 되지 않은 PRD에 정의 된 기능을 우선으로 마일스톤,스프린트, 태스크를 수행 할 것
- 거짓으로 보고하거나 허언을 하지 않고 객관적인 상황과 현실적으로 수행할 것
- 통합 테스트를 적극 활용하고 반드시 에뮬레이터를 이용하여 실제로 잘 동작 되는지 통합 테스트 할 것. 
  - 스크린샷을 적극 활용할 것
  - 스크린샷은 프로젝트 폴더안에 screenshot 폴더에 저장해서 확인할 것.
- UI가 실제로 안보이는 경우가 많음. 서버 배포 후 실제로 배포환경으로 UI가 잘 나오고 설계대로 동작하는지 검증 할 것.
- 실패한 테스트는 무조건 성공 할 수 있도록 계속 수정하고 테스트해서 성공 시킬 것.
- 테스트 실패가 설정 문제라면 그냥 넘어가지 말고 설정의 문제를 파악하고 해결 할 것. 테스트환경도 적극 해결할 것.
- context7을 통해 n8n에 관한 문서를 꼭 읽을 것
- 기술을 사용 할 때 context7을 적극 활욜 할 것

# Google Sheets 연동 설정 (2025-06-27 완료)

## 🔧 완료된 설정
- ✅ Google Cloud Console: Sheets API 활성화 완료
- ✅ 서비스 계정: influence-item-sheets@influence-item-youtube.iam.gserviceaccount.com
- ✅ 인증 파일: /Users/chul/.config/gspread/credentials.json
- ✅ 시트 ID: 1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY
- ✅ OAuth 연동: 완전 작동 확인

## 📋 빠른 테스트 명령어
```bash
# 빠른 연결 테스트
python3 quick_test.py

# 전체 통합 테스트
python3 test_dashboard_integration.py

# 대시보드 실행
python3 -m streamlit run dashboard/main_dashboard.py --server.port 8504
```

## 🚨 중요 파일들
- 인증키: /Users/chul/.config/gspread/credentials.json (절대 삭제하지 말 것)
- 환경설정: .env (Google Sheets 설정 포함)
- 설정가이드: GOOGLE_SHEETS_SETUP.md
- 구현 모듈들: dashboard/utils/google_sheets_*.py

---
**Google Sheets 완전 연동 완료 - 다음에도 바로 사용 가능**