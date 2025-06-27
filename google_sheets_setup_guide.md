
# Google Sheets API 서비스 계정 설정 가이드

## 1단계: Google Cloud Console 접속
1. https://console.cloud.google.com 접속
2. 로그인 (Gemini API 키를 생성한 계정 사용)

## 2단계: 프로젝트 선택/생성
1. 기존 프로젝트 선택 또는 새 프로젝트 생성
2. 프로젝트 ID 확인 및 기록

## 3단계: Google Sheets API 활성화
1. "API 및 서비스" > "라이브러리" 이동
2. "Google Sheets API" 검색
3. "사용 설정" 클릭

## 4단계: 서비스 계정 생성
1. "API 및 서비스" > "사용자 인증 정보" 이동
2. "사용자 인증 정보 만들기" > "서비스 계정" 선택
3. 서비스 계정 이름 입력 (예: "n8n-sheets-service")
4. 역할: "편집자" 또는 "Sheets API 사용자" 선택

## 5단계: JSON 키 생성
1. 생성된 서비스 계정 클릭
2. "키" 탭으로 이동
3. "키 추가" > "새 키 만들기" > "JSON" 선택
4. 다운로드된 JSON 파일을 프로젝트에 저장

## 6단계: Google Sheets 권한 부여
1. Google Sheets 열기
2. "공유" 버튼 클릭
3. 서비스 계정 이메일 주소 입력 (JSON 파일에서 확인)
4. "편집자" 권한 부여

## 7단계: 환경변수 설정
프로젝트 .env 파일에 추가:
```
GOOGLE_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account-key.json
```

## 8단계: 코드 수정
Python 코드에서 서비스 계정 인증 사용
