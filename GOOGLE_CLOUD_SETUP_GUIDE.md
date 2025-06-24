# Google Cloud Console 설정 가이드

## 1. Google Cloud Console 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 상단에서 "프로젝트 선택" 클릭
3. "새 프로젝트" 클릭
4. 프로젝트 이름 입력 (예: "influence-item")
5. "만들기" 클릭

## 2. Google Sheets API 활성화

1. 좌측 메뉴에서 "API 및 서비스" > "라이브러리" 클릭
2. "Google Sheets API" 검색
3. "Google Sheets API" 클릭
4. "사용 설정" 클릭

## 3. 서비스 계정 생성

1. 좌측 메뉴에서 "API 및 서비스" > "사용자 인증 정보" 클릭
2. "사용자 인증 정보 만들기" > "서비스 계정" 클릭
3. 서비스 계정 정보 입력:
   - 서비스 계정 이름: `influence-item-sheets`
   - 서비스 계정 ID: `influence-item-sheets`
   - 설명: `Google Sheets API access for influence-item`
4. "만들기 및 계속하기" 클릭
5. 역할에서 "편집자" 선택 (또는 "기본" > "편집자")
6. "계속" 클릭
7. "완료" 클릭

## 4. 서비스 계정 키 생성

1. 생성된 서비스 계정 클릭
2. "키" 탭 클릭
3. "키 추가" > "새 키 만들기" 클릭
4. "JSON" 선택
5. "만들기" 클릭
6. JSON 파일이 자동으로 다운로드됩니다

## 5. 서비스 계정 이메일 확인

다운로드된 JSON 파일에서 `client_email` 값을 확인하세요.
예: `influence-item-sheets@your-project.iam.gserviceaccount.com`

## 6. Google Sheets에 서비스 계정 공유

1. Google Sheets 스프레드시트 열기
2. 우측 상단 "공유" 버튼 클릭
3. 서비스 계정 이메일 주소 입력
4. 권한을 "편집자"로 설정
5. "보내기" 클릭

## 7. credentials.json 파일 저장

다운로드된 JSON 파일을 다음 경로에 저장:
```
/Users/chul/Documents/claude/influence_item/credentials/google_sheets_credentials.json
```

## 완료!

모든 설정이 완료되었습니다. 이제 애플리케이션에서 Google Sheets API를 사용할 수 있습니다.