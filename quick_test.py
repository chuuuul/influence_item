#!/usr/bin/env python3
"""
Google Sheets 빠른 연결 테스트
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

def quick_test():
    print("🔗 Google Sheets 빠른 연결 테스트")
    
    try:
        # 인증
        cred_path = "/Users/chul/.config/gspread/credentials.json"
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(cred_path, scopes=scope)
        client = gspread.authorize(credentials)
        
        # 시트 열기
        sheet_id = "1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY"
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.sheet1
        
        print(f"✅ 연결 성공: {sheet.title}")
        
        # 데이터 읽기
        all_values = worksheet.get_all_values()
        print(f"✅ 데이터 {len(all_values)}행 읽기 성공")
        
        # 간단한 테스트 데이터 추가
        test_data = [
            [f"빠른테스트 {datetime.now().strftime('%H:%M:%S')}", "UC_QUICK_TEST", "테스트", "1", "활성", datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        worksheet.append_rows(test_data)
        print("✅ 테스트 데이터 추가 성공")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    success = quick_test()
    print(f"\n🎯 결과: {'성공' if success else '실패'}")