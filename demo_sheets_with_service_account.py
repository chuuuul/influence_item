#!/usr/bin/env python3
"""
서비스 계정을 사용한 Google Sheets 제어 데모
기존 계정의 서비스 계정 키를 생성해서 사용합니다.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

def demo_with_existing_auth():
    """기존 인증으로 간단한 테스트"""
    
    print("🔍 기존 인증 정보로 Google Sheets 기능 확인...")
    
    try:
        import google.auth
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        # 기존 인증 사용 (스코프 없이)
        credentials, project = google.auth.default()
        
        # Drive API로 파일 권한 확인
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # 스프레드시트 ID
        spreadsheet_id = "1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY"
        
        print(f"📄 스프레드시트 파일 정보 확인: {spreadsheet_id}")
        
        # Drive API로 파일 정보 조회
        file_info = drive_service.files().get(
            fileId=spreadsheet_id,
            fields='id,name,permissions,owners,webViewLink'
        ).execute()
        
        print(f"✅ 파일명: {file_info.get('name', 'Unknown')}")
        print(f"🔗 링크: {file_info.get('webViewLink', 'N/A')}")
        
        # 권한 정보 확인
        try:
            permissions = drive_service.permissions().list(fileId=spreadsheet_id).execute()
            print(f"🔐 권한 개수: {len(permissions.get('permissions', []))}")
            
            for perm in permissions.get('permissions', []):
                perm_type = perm.get('type', 'unknown')
                role = perm.get('role', 'unknown')
                email = perm.get('emailAddress', 'N/A')
                print(f"   - {perm_type}: {role} ({email})")
                
        except Exception as e:
            print(f"⚠️ 권한 정보 조회 제한: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return False

def create_manual_service_account_demo():
    """수동으로 서비스 계정 키 생성 가이드"""
    
    print("\n🔧 === 서비스 계정 키 생성 가이드 ===")
    print("1. Google Cloud Console 접속: https://console.cloud.google.com")
    print("2. IAM 및 관리 > 서비스 계정 메뉴")
    print("3. '서비스 계정 만들기' 클릭")
    print("4. 이름: influence-item-sheets")
    print("5. 역할: 편집자 (Editor)")
    print("6. 키 탭에서 '키 추가' > '새 키 만들기' > JSON")
    print("7. 다운로드된 JSON을 credentials/google_sheets_credentials.json에 저장")
    print("8. 서비스 계정 이메일을 스프레드시트에 편집자로 공유")
    
    print("\n또는 gcloud CLI 사용:")
    print("gcloud iam service-accounts create influence-item-sheets")
    print("gcloud iam service-accounts keys create credentials/google_sheets_credentials.json --iam-account=influence-item-sheets@{프로젝트ID}.iam.gserviceaccount.com")

def demo_sheets_read_only():
    """읽기 전용으로 가능한 기능 테스트"""
    
    print("\n📖 === 읽기 전용 기능 테스트 ===")
    
    try:
        import google.auth
        from googleapiclient.discovery import build
        
        # 기본 인증
        credentials, project = google.auth.default()
        
        # Sheets API (읽기 시도)
        sheets_service = build('sheets', 'v4', credentials=credentials)
        spreadsheet_id = "1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY"
        
        # 공개 범위 데이터 읽기 시도
        try:
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range='A1:E5'
            ).execute()
            
            values = result.get('values', [])
            if values:
                print("✅ 데이터 읽기 성공!")
                for i, row in enumerate(values):
                    print(f"   {i+1}: {row}")
            else:
                print("📊 데이터가 없습니다.")
                
            return True
            
        except Exception as read_error:
            print(f"❌ 읽기 실패: {read_error}")
            return False
            
    except Exception as e:
        print(f"❌ 설정 실패: {e}")
        return False

def demo_simple_web_interface():
    """웹 인터페이스로 확인할 수 있는 방법"""
    
    print("\n🌐 === 웹 인터페이스 확인 방법 ===")
    
    spreadsheet_id = "1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY"
    
    print(f"1. 스프레드시트 열기:")
    print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet_id}/")
    
    print(f"\n2. 공유 설정 확인:")
    print(f"   - 우측 상단 '공유' 버튼 클릭")
    print(f"   - 현재 권한 확인")
    print(f"   - API 사용을 위해 편집자 권한 필요")
    
    print(f"\n3. 테스트 데이터 직접 입력:")
    print(f"   - A1: 'API 테스트'")
    print(f"   - B1: '시간'") 
    print(f"   - C1: '상태'")
    print(f"   - A2: '읽기 테스트'")
    print(f"   - B2: '{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'")
    print(f"   - C2: '수동 입력'")

def main():
    """메인 함수"""
    print("🚀 Google Sheets 연결 상태 진단")
    print("=" * 50)
    
    # 1. 기존 인증으로 파일 접근 확인
    auth_success = demo_with_existing_auth()
    
    # 2. 읽기 전용 기능 테스트
    read_success = demo_sheets_read_only()
    
    # 3. 해결 방법 안내
    if not (auth_success and read_success):
        create_manual_service_account_demo()
        demo_simple_web_interface()
    
    print("\n" + "=" * 50)
    print("📊 진단 결과")
    print("=" * 50)
    print(f"📁 파일 접근: {'✅ 성공' if auth_success else '❌ 실패'}")
    print(f"📖 데이터 읽기: {'✅ 성공' if read_success else '❌ 실패'}")
    
    if auth_success and read_success:
        print("\n🎉 Google Sheets 기본 연결 성공!")
        print("쓰기 권한을 위해서는 서비스 계정 키가 필요합니다.")
    else:
        print("\n⚠️ 권한 설정이 필요합니다.")
        print("위의 가이드를 따라 설정해주세요.")

if __name__ == "__main__":
    main()