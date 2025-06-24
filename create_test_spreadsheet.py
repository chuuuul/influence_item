#!/usr/bin/env python3
"""
테스트용 공개 스프레드시트 생성 스크립트
"""

import google.auth
from googleapiclient.discovery import build

def create_test_spreadsheet():
    """테스트용 스프레드시트 생성"""
    
    try:
        # 인증
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        )
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # 새 스프레드시트 생성
        print("📄 새 스프레드시트 생성 중...")
        
        spreadsheet = {
            'properties': {
                'title': 'Influence Item - API 테스트용 시트'
            },
            'sheets': [
                {
                    'properties': {
                        'title': 'API 테스트',
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': 10
                        }
                    }
                }
            ]
        }
        
        result = sheets_service.spreadsheets().create(body=spreadsheet).execute()
        spreadsheet_id = result.get('spreadsheetId')
        
        print(f"✅ 스프레드시트 생성 완료!")
        print(f"📋 ID: {spreadsheet_id}")
        print(f"🔗 URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/")
        
        # 공개 권한 설정
        print("\n🔓 공개 권한 설정 중...")
        
        permission = {
            'type': 'anyone',
            'role': 'writer'  # 편집 가능
        }
        
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body=permission
        ).execute()
        
        print("✅ 공개 편집 권한 설정 완료!")
        
        # 기본 데이터 추가
        print("\n📝 기본 데이터 추가 중...")
        
        values = [
            ['컬럼1', '컬럼2', '컬럼3', '컬럼4', '컬럼5'],
            ['데이터1', '데이터2', '데이터3', '데이터4', '데이터5'],
            ['테스트', 'API', '연동', '성공', '확인']
        ]
        
        body = {
            'values': values
        }
        
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='API 테스트!A1:E3',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print("✅ 기본 데이터 추가 완료!")
        
        return spreadsheet_id
        
    except Exception as e:
        print(f"❌ 실패: {e}")
        return None

if __name__ == "__main__":
    spreadsheet_id = create_test_spreadsheet()
    
    if spreadsheet_id:
        print(f"\n🎉 테스트용 스프레드시트 준비 완료!")
        print(f"이 ID를 .env 파일에 설정하세요:")
        print(f"GOOGLE_SHEETS_SPREADSHEET_ID={spreadsheet_id}")
    else:
        print("\n💥 스프레드시트 생성 실패!")