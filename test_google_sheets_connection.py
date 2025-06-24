#!/usr/bin/env python3
"""
Google Sheets 연결 테스트 스크립트
"""

import os
import sys
import json
from pathlib import Path

# 환경 변수 로드
sys.path.append(str(Path(__file__).parent))

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("❌ Google API 라이브러리가 설치되지 않았습니다.")
    print("pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client 실행하세요.")
    sys.exit(1)

def load_env_file():
    """환경 변수를 .env 파일에서 로드"""
    env_path = Path(__file__).parent / ".env.example"
    env_vars = {}
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    return env_vars

def test_google_sheets_connection():
    """Google Sheets API 연결 테스트"""
    
    # 환경 변수 로드
    env_vars = load_env_file()
    
    # 필수 설정값 확인
    credentials_path = env_vars.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'credentials/google_sheets_credentials.json')
    spreadsheet_id = env_vars.get('GOOGLE_SHEETS_SPREADSHEET_ID', '')
    
    print("🔍 Google Sheets 연결 테스트 시작...")
    print(f"📁 Credentials 경로: {credentials_path}")
    print(f"📄 스프레드시트 ID: {spreadsheet_id}")
    
    # credentials.json 파일 존재 확인
    if not os.path.exists(credentials_path):
        print(f"❌ Credentials 파일이 없습니다: {credentials_path}")
        print("🔧 Google Cloud Console에서 서비스 계정 키를 다운로드하고 해당 경로에 저장하세요.")
        return False
    
    if not spreadsheet_id:
        print("❌ 스프레드시트 ID가 설정되지 않았습니다.")
        print("🔧 .env.example 파일에서 GOOGLE_SHEETS_SPREADSHEET_ID를 설정하세요.")
        return False
    
    try:
        # 서비스 계정 인증
        print("🔐 서비스 계정 인증 중...")
        credentials = Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        # Google Sheets API 서비스 생성
        service = build('sheets', 'v4', credentials=credentials)
        
        # 스프레드시트 메타데이터 조회
        print("📊 스프레드시트 메타데이터 조회 중...")
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        
        print("✅ Google Sheets 연결 성공!")
        print(f"📋 스프레드시트 제목: {sheet_metadata.get('properties', {}).get('title', 'Unknown')}")
        
        # 시트 목록 출력
        sheets = sheet_metadata.get('sheets', [])
        print(f"📄 시트 개수: {len(sheets)}")
        for i, sheet in enumerate(sheets):
            sheet_title = sheet.get('properties', {}).get('title', f'Sheet{i+1}')
            print(f"   - {sheet_title}")
        
        # 간단한 읽기 테스트
        print("📖 첫 번째 시트의 A1:C3 범위 읽기 테스트...")
        if sheets:
            first_sheet = sheets[0].get('properties', {}).get('title', 'Sheet1')
            range_name = f"{first_sheet}!A1:C3"
            
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if values:
                print("📊 읽어온 데이터:")
                for row in values:
                    print(f"   {row}")
            else:
                print("📊 범위에 데이터가 없습니다.")
        
        # 간단한 쓰기 테스트
        print("✏️  테스트 데이터 쓰기...")
        test_range = f"{first_sheet}!A1:B2"
        test_values = [
            ['테스트', '시간'],
            ['Connection Test', str(int(__import__('time').time()))]
        ]
        
        body = {
            'values': test_values
        }
        
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=test_range,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print(f"✅ {result.get('updatedCells')} 개 셀 업데이트 완료!")
        
        return True
        
    except HttpError as error:
        print(f"❌ HTTP 오류: {error}")
        if error.resp.status == 403:
            print("🔧 권한 오류: 스프레드시트에 서비스 계정을 공유했는지 확인하세요.")
        elif error.resp.status == 404:
            print("🔧 스프레드시트를 찾을 수 없습니다. ID를 확인하세요.")
        return False
        
    except Exception as error:
        print(f"❌ 예상치 못한 오류: {error}")
        return False

if __name__ == "__main__":
    success = test_google_sheets_connection()
    
    if success:
        print("\n🎉 Google Sheets 연결 테스트 완료!")
        print("이제 애플리케이션에서 Google Sheets API를 사용할 수 있습니다.")
    else:
        print("\n💥 Google Sheets 연결 테스트 실패!")
        print("위의 오류 메시지를 확인하고 설정을 다시 확인하세요.")
    
    sys.exit(0 if success else 1)