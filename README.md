# 연예인 추천 아이템 자동화 릴스 시스템

## 프로젝트 구조

```
influence_item/
├── src/                      # 핵심 소스 코드
│   ├── ai_analysis.py        # AI 분석 모듈
│   ├── api_server.py         # API 서버
│   ├── error_handling.py     # 에러 처리
│   ├── google_sheets_integration.py  # Google Sheets 연동
│   ├── slack_integration.py  # Slack 연동
│   ├── visual_analysis.py    # 시각 분석
│   └── youtube_api.py        # YouTube API
│
├── dashboard/                # Streamlit 대시보드
│   ├── main_dashboard.py     # 메인 대시보드
│   ├── views/               # 페이지별 뷰
│   └── utils/               # 대시보드 유틸리티
│
├── n8n/                     # n8n 워크플로우 자동화
│   ├── workflows/           # 워크플로우 JSON 파일들
│   ├── scripts/             # n8n 실행 스크립트
│   │   ├── n8n_start.sh    # n8n 시작
│   │   └── n8n_stop.sh     # n8n 종료
│   └── logs/               # n8n 로그
│
├── data/                    # 데이터 저장소
│   ├── db/                 # SQLite 데이터베이스
│   ├── exports/            # 내보낸 데이터 (CSV 등)
│   └── uploads/            # 업로드된 파일
│
├── tests/                   # 테스트 코드
│   ├── integration/        # 통합 테스트
│   └── *.py               # 단위 테스트
│
├── docs/                    # 문서
│   ├── README.md          # 프로젝트 설명
│   ├── prd.md             # 제품 요구사항 문서
│   └── *.md               # 기타 문서
│
├── scripts/                 # 유틸리티 스크립트
│   └── setup/              # 설정 스크립트
│
├── config/                  # 설정 파일
│   └── .env.example        # 환경 변수 예제
│
└── logs/                    # 애플리케이션 로그
```

## 시작하기

### 1. 환경 설정
```bash
cp config/.env.example .env
# .env 파일을 편집하여 필요한 환경 변수 설정
```

### 2. 의존성 설치
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. n8n 실행
```bash
./n8n/scripts/n8n_start.sh
# 브라우저에서 http://localhost:5678 접속
```

### 4. 대시보드 실행
```bash
streamlit run dashboard/main_dashboard.py
# 브라우저에서 http://localhost:8501 접속
```

## 주요 기능

1. **채널 탐색**: YouTube 채널 자동 검색 및 분석
2. **영상 수집**: RSS 피드를 통한 신규 영상 수집
3. **AI 분석**: Gemini API를 활용한 2-Pass 분석
4. **수익화 후보 관리**: 제품 추천 후보 필터링
5. **Google Sheets 연동**: 데이터 자동 동기화
6. **Slack 알림**: 실시간 상태 알림

## 환경 변수

`.env` 파일에 다음 변수들을 설정하세요:
- `GEMINI_API_KEY`: Google AI API 키
- `YOUTUBE_API_KEY`: YouTube Data API 키
- `SLACK_WEBHOOK_URL`: Slack 웹훅 URL
- `GOOGLE_SHEET_URL`: Google Sheets URL
- 기타 설정은 `config/.env.example` 참조

## 문서

- [제품 요구사항 문서 (PRD)](docs/prd.md)
- [Google Sheets 설정 가이드](docs/google_sheets_setup_guide.md)
- [설정 가이드](docs/setup_google_apps_script.md)

## 라이선스

이 프로젝트는 비공개 프로젝트입니다.