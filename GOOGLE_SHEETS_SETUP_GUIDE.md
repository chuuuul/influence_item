# Google Sheets API 설정 가이드

## 1. Google Cloud Console 설정

### 1.1 프로젝트 생성 및 API 활성화
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. API 및 서비스 > 라이브러리로 이동
4. 다음 API들을 활성화:
   - Google Sheets API
   - Google Drive API

### 1.2 서비스 계정 생성
1. IAM 및 관리 > 서비스 계정으로 이동
2. "서비스 계정 만들기" 클릭
3. 서비스 계정 이름: `influence-item-sheets`
4. 설명: `Influence Item Google Sheets 연동용`
5. 역할: 편집자 또는 뷰어 (필요에 따라)

### 1.3 서비스 계정 키 생성
1. 생성된 서비스 계정 클릭
2. "키" 탭으로 이동
3. "키 추가" > "새 키 만들기"
4. JSON 형식 선택
5. 다운로드된 JSON 파일을 `credentials/google_sheets_credentials.json`으로 저장

## 2. 필요한 Python 패키지 설치

```bash
pip install gspread google-auth google-auth-oauthlib google-auth-httplib2
```

## 3. Google Sheets 생성 및 공유

### 3.1 테스트용 스프레드시트 생성
1. [Google Sheets](https://sheets.google.com) 접속
2. 새 스프레드시트 생성
3. 제목: "Influence Item - 채널 관리"

### 3.2 서비스 계정과 공유
1. 생성된 스프레드시트에서 "공유" 버튼 클릭
2. JSON 파일의 `client_email` 값을 복사
3. 해당 이메일 주소를 편집자 권한으로 추가

## 4. 스프레드시트 구조

### 4.1 "승인된 채널" 시트
| 컬럼 | 설명 |
|------|------|
| 채널ID | YouTube 채널 ID |
| 채널명 | 채널 이름 |
| 채널유형 | personal/media |
| RSS URL | 채널 RSS 피드 URL |
| 활성상태 | 활성/비활성 |
| 마지막수집일 | 마지막 영상 수집 일시 |
| 등록일 | 채널 등록 일시 |
| 업데이트일 | 마지막 업데이트 일시 |
| 비고 | 기타 메모 |

### 4.2 "후보 채널" 시트
| 컬럼 | 설명 |
|------|------|
| 채널ID | YouTube 채널 ID |
| 채널명 | 채널 이름 |
| 채널유형 | personal/media |
| RSS URL | 채널 RSS 피드 URL |
| 발견점수 | 자동 탐지 점수 |
| 발견사유 | 발견 이유 |
| 발견일시 | 발견 일시 |
| 검토상태 | pending/approved/rejected |
| 검토자 | 검토한 운영자 |
| 검토일시 | 검토 일시 |
| 승인여부 | 승인/거부/보류 (드롭다운) |
| 비고 | 검토 메모 |

## 5. 환경 변수 설정

`.env` 파일에 다음 추가:
```
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials/google_sheets_credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=<스프레드시트_ID>
```

스프레드시트 ID는 URL에서 추출:
`https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`

## 6. 보안 주의사항

1. `credentials/` 폴더를 `.gitignore`에 추가
2. 서비스 계정 JSON 파일은 절대 공개 저장소에 커밋하지 말 것
3. 서비스 계정 권한을 최소한으로 제한
4. 정기적으로 사용하지 않는 키 삭제

## 7. 테스트 방법

```python
import gspread
from google.oauth2.service_account import Credentials

# 인증 테스트
gc = gspread.service_account(filename='credentials/google_sheets_credentials.json')
sheets = gc.open('Influence Item - 채널 관리')
print("인증 성공:", sheets.title)
```