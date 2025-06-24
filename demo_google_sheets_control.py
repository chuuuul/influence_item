#!/usr/bin/env python3
"""
Google Sheets 제어 데모 스크립트
실제로 읽기, 쓰기, 업데이트, 포맷팅 등을 테스트합니다.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

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

def setup_google_sheets():
    """Google Sheets API 설정"""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        print("🔐 Google Sheets API 인증 중...")
        
        # 서비스 계정 키 파일 사용
        credentials_path = "credentials/google_sheets_credentials.json"
        credentials = Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        service = build('sheets', 'v4', credentials=credentials)
        print("✅ Google Sheets API 서비스 생성 완료")
        
        return service
        
    except Exception as e:
        print(f"❌ Google Sheets API 설정 실패: {e}")
        return None

def demo_read_sheets(service, spreadsheet_id):
    """Google Sheets 읽기 데모"""
    print("\n📖 === Google Sheets 읽기 데모 ===")
    
    try:
        # 스프레드시트 메타데이터 조회
        print("1️⃣ 스프레드시트 정보 조회...")
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        
        title = sheet_metadata.get('properties', {}).get('title', 'Unknown')
        sheets = sheet_metadata.get('sheets', [])
        
        print(f"   📋 제목: {title}")
        print(f"   📄 시트 개수: {len(sheets)}")
        
        for i, sheet in enumerate(sheets):
            sheet_title = sheet.get('properties', {}).get('title', f'Sheet{i+1}')
            print(f"   - {sheet_title}")
        
        # 첫 번째 시트에서 데이터 읽기
        if sheets:
            first_sheet = sheets[0].get('properties', {}).get('title', '시트1')
            print(f"\n2️⃣ '{first_sheet}' 시트에서 A1:E10 범위 읽기...")
            
            range_name = f"{first_sheet}!A1:E10"
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if values:
                print(f"   📊 {len(values)}행의 데이터를 읽었습니다:")
                for i, row in enumerate(values[:5]):  # 처음 5행만 출력
                    print(f"   {i+1:2d}: {row}")
                if len(values) > 5:
                    print(f"   ... (총 {len(values)}행)")
            else:
                print("   📊 범위에 데이터가 없습니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 읽기 실패: {e}")
        return False

def demo_write_sheets(service, spreadsheet_id):
    """Google Sheets 쓰기 데모"""
    print("\n✏️ === Google Sheets 쓰기 데모 ===")
    
    try:
        # 현재 시간으로 테스트 데이터 생성
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 테스트 데이터
        test_data = [
            ["🚀 Influence Item 데모", "데이터", "테스트", "시간", "상태"],
            ["읽기 테스트", "완료", "✅", current_time, "성공"],
            ["쓰기 테스트", "진행중", "🔄", current_time, "진행"],
            ["API 연동", "대기", "⏳", current_time, "대기"],
            ["최종 검증", "예정", "📋", current_time, "예정"]
        ]
        
        # 첫 번째 시트에 데이터 쓰기
        print("1️⃣ 테스트 데이터 쓰기...")
        range_name = "시트1!A1:E5"
        
        body = {
            'values': test_data
        }
        
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        updated_cells = result.get('updatedCells', 0)
        print(f"   ✅ {updated_cells}개 셀 업데이트 완료!")
        
        # 추가 데이터 행 삽입
        print("\n2️⃣ 새로운 데이터 행 추가...")
        new_row = [f"동적 데이터 {int(time.time())}", "추가됨", "🆕", current_time, "신규"]
        
        range_name = "시트1!A6:E6"
        body = {'values': [new_row]}
        
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print(f"   ✅ 새 행 추가 완료!")
        
        return True
        
    except Exception as e:
        print(f"❌ 쓰기 실패: {e}")
        return False

def demo_batch_update(service, spreadsheet_id):
    """Google Sheets 배치 업데이트 데모"""
    print("\n🔄 === Google Sheets 배치 업데이트 데모 ===")
    
    try:
        # 여러 범위를 한 번에 업데이트
        current_time = datetime.now().strftime("%H:%M:%S")
        
        data = [
            {
                'range': '시트1!B2',
                'values': [['배치 업데이트 완료']]
            },
            {
                'range': '시트1!D2:D6', 
                'values': [[f'업데이트 {current_time}'], [f'업데이트 {current_time}'], [f'업데이트 {current_time}'], [f'업데이트 {current_time}'], [f'업데이트 {current_time}']]
            },
            {
                'range': '시트1!E2:E6',
                'values': [['✅ 완료'], ['✅ 완료'], ['✅ 완료'], ['✅ 완료'], ['✅ 완료']]
            }
        ]
        
        body = {
            'valueInputOption': 'RAW',
            'data': data
        }
        
        result = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id, 
            body=body
        ).execute()
        
        total_updated = result.get('totalUpdatedCells', 0)
        print(f"   ✅ 배치 업데이트로 총 {total_updated}개 셀 업데이트!")
        
        return True
        
    except Exception as e:
        print(f"❌ 배치 업데이트 실패: {e}")
        return False

def demo_formatting(service, spreadsheet_id):
    """Google Sheets 포맷팅 데모"""
    print("\n🎨 === Google Sheets 포맷팅 데모 ===")
    
    try:
        # 첫 번째 행을 헤더로 포맷팅
        requests = [
            {
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': 5
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red': 0.2,
                                'green': 0.6,
                                'blue': 1.0
                            },
                            'textFormat': {
                                'foregroundColor': {
                                    'red': 1.0,
                                    'green': 1.0,
                                    'blue': 1.0
                                },
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            },
            {
                'autoResizeDimensions': {
                    'dimensions': {
                        'sheetId': 0,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,
                        'endIndex': 5
                    }
                }
            }
        ]
        
        body = {'requests': requests}
        
        result = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()
        
        print("   🎨 헤더 행 포맷팅 완료 (파란색 배경, 흰색 글자, 굵게)")
        print("   📏 열 너비 자동 조정 완료")
        
        return True
        
    except Exception as e:
        print(f"❌ 포맷팅 실패: {e}")
        return False

def demo_advanced_features(service, spreadsheet_id):
    """Google Sheets 고급 기능 데모"""
    print("\n⭐ === Google Sheets 고급 기능 데모 ===")
    
    try:
        # 수식 추가
        print("1️⃣ 수식 추가...")
        formula_data = [
            ['합계', '=SUM(B2:B6)'],
            ['개수', '=COUNTA(A2:A6)'],
            ['현재시간', '=NOW()']
        ]
        
        range_name = "시트1!G1:H3"
        body = {'values': formula_data}
        
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',  # 수식으로 해석
            body=body
        ).execute()
        
        print("   ✅ 수식 추가 완료 (합계, 개수, 현재시간)")
        
        # 데이터 검증 추가 (드롭다운)
        print("\n2️⃣ 데이터 검증 (드롭다운) 추가...")
        
        requests = [
            {
                'setDataValidation': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 1,
                        'endRowIndex': 6,
                        'startColumnIndex': 4,  # E열
                        'endColumnIndex': 5
                    },
                    'rule': {
                        'condition': {
                            'type': 'ONE_OF_LIST',
                            'values': [
                                {'userEnteredValue': '✅ 완료'},
                                {'userEnteredValue': '🔄 진행중'},
                                {'userEnteredValue': '⏳ 대기'},
                                {'userEnteredValue': '❌ 실패'}
                            ]
                        },
                        'showCustomUi': True
                    }
                }
            }
        ]
        
        body = {'requests': requests}
        result = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()
        
        print("   ✅ 상태 열에 드롭다운 메뉴 추가 완료")
        
        return True
        
    except Exception as e:
        print(f"❌ 고급 기능 실패: {e}")
        return False

def main():
    """메인 함수"""
    print("🚀 Google Sheets 제어 데모 시작!")
    print("=" * 50)
    
    # 환경 변수 로드
    env_vars = load_env_file()
    spreadsheet_id = env_vars.get('GOOGLE_SHEETS_SPREADSHEET_ID', '')
    
    if not spreadsheet_id:
        print("❌ 스프레드시트 ID가 설정되지 않았습니다.")
        return False
    
    print(f"📄 대상 스프레드시트: {spreadsheet_id}")
    print(f"🔗 URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/")
    
    # Google Sheets API 설정
    service = setup_google_sheets()
    if not service:
        return False
    
    success_count = 0
    total_tests = 5
    
    # 1. 읽기 테스트
    if demo_read_sheets(service, spreadsheet_id):
        success_count += 1
    
    # 2. 쓰기 테스트  
    if demo_write_sheets(service, spreadsheet_id):
        success_count += 1
    
    # 3. 배치 업데이트 테스트
    if demo_batch_update(service, spreadsheet_id):
        success_count += 1
    
    # 4. 포맷팅 테스트
    if demo_formatting(service, spreadsheet_id):
        success_count += 1
    
    # 5. 고급 기능 테스트
    if demo_advanced_features(service, spreadsheet_id):
        success_count += 1
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 Google Sheets 제어 데모 결과")
    print("=" * 50)
    print(f"✅ 성공: {success_count}/{total_tests}")
    print(f"❌ 실패: {total_tests - success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("\n🎉 모든 Google Sheets 제어 기능이 정상 작동합니다!")
        print("이제 실제 애플리케이션에서 Google Sheets를 완전히 제어할 수 있습니다.")
    else:
        print(f"\n⚠️ {total_tests - success_count}개 기능에서 문제가 발생했습니다.")
        print("스프레드시트 권한이나 API 설정을 확인해주세요.")
    
    print(f"\n🔗 결과 확인: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/")
    
    return success_count == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)