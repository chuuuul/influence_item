#!/usr/bin/env python3
"""
Google Sheets 연동 문제 진단 및 해결 방안
"""

import os
import sys
import requests
from pathlib import Path

def diagnose_api_keys():
    """현재 API 키 상태 진단"""
    print("🔍 API 키 진단")
    print("=" * 50)
    
    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        print(f"✅ Gemini API 키: {gemini_key[:10]}...")
        
        # Gemini API 키로 어떤 서비스에 접근 가능한지 확인
        print("\n🧪 Gemini API 키로 접근 가능한 서비스:")
        
        # 1. Gemini AI 서비스
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                print(f"✅ Gemini AI: {len(models)}개 모델 접근 가능")
            else:
                print(f"❌ Gemini AI: {response.status_code}")
        except Exception as e:
            print(f"❌ Gemini AI: {e}")
        
        # 2. Google Sheets API (실패할 것으로 예상)
        try:
            sheet_id = os.getenv('GOOGLE_SHEET_ID')
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?key={gemini_key}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ Google Sheets API: 접근 가능")
            else:
                error_data = response.json()
                error_code = error_data.get('error', {}).get('code')
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                print(f"❌ Google Sheets API: {error_code} - {error_message}")
                
                # 에러 분석
                if error_code == 403:
                    if 'SERVICE_DISABLED' in error_message:
                        print("   📝 원인: Google Sheets API가 비활성화됨")
                        print("   🔧 해결: Google Cloud Console에서 API 활성화 필요")
                    elif 'PERMISSION_DENIED' in error_message:
                        print("   📝 원인: API 키 권한 부족")
                        print("   🔧 해결: 올바른 서비스 계정 키 필요")
                
        except Exception as e:
            print(f"❌ Google Sheets API: {e}")
    else:
        print("❌ Gemini API 키 없음")

def check_google_cloud_project():
    """Google Cloud 프로젝트 정보 확인"""
    print("\n☁️ Google Cloud 프로젝트 분석")
    print("=" * 50)
    
    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        print("❌ API 키가 없어 프로젝트 분석 불가")
        return
    
    # 에러 메시지에서 프로젝트 ID 추출
    try:
        sheet_id = os.getenv('GOOGLE_SHEET_ID')
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?key={gemini_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 403:
            error_data = response.json()
            error_details = error_data.get('error', {}).get('details', [])
            
            for detail in error_details:
                if 'metadata' in detail and 'consumer' in detail['metadata']:
                    project_info = detail['metadata']['consumer']
                    if project_info.startswith('projects/'):
                        project_id = project_info.replace('projects/', '')
                        print(f"📊 감지된 프로젝트 ID: {project_id}")
                        
                        activation_url = detail['metadata'].get('activationUrl', '')
                        if activation_url:
                            print(f"🔗 API 활성화 URL: {activation_url}")
                        
                        return project_id
        
    except Exception as e:
        print(f"❌ 프로젝트 정보 추출 실패: {e}")
    
    return None

def suggest_solutions():
    """해결 방안 제시"""
    print("\n💡 Google Sheets 연동 해결 방안")
    print("=" * 50)
    
    print("🚨 현재 문제:")
    print("  - Gemini API 키는 AI 서비스만 접근 가능")
    print("  - Google Sheets API는 별도 인증 필요")
    print("  - 현재 Google Sheets API가 비활성화됨")
    
    print("\n🔧 해결 방법 옵션:")
    
    print("\n1️⃣ Google Cloud Console 설정 (권장)")
    print("   a) https://console.cloud.google.com 접속")
    print("   b) 새 프로젝트 생성 또는 기존 프로젝트 선택")
    print("   c) Google Sheets API 활성화")
    print("   d) 서비스 계정 생성 및 JSON 키 다운로드")
    print("   e) Google Sheets에 서비스 계정 이메일 공유 권한 부여")
    
    print("\n2️⃣ 기존 Gemini 프로젝트에서 API 활성화")
    project_id = check_google_cloud_project()
    if project_id:
        print(f"   a) 프로젝트 {project_id}에서 Google Sheets API 활성화")
        print(f"   b) https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project={project_id}")
    
    print("\n3️⃣ 대안: Google Apps Script 사용")
    print("   a) Google Sheets에서 Apps Script 생성")
    print("   b) Webhook 엔드포인트 생성")
    print("   c) N8n에서 Apps Script 호출")
    
    print("\n4️⃣ 임시 해결: 수동 연동")
    print("   a) CSV 파일 생성 후 수동 업로드")
    print("   b) Google Forms를 통한 데이터 입력")

def create_service_account_setup_guide():
    """서비스 계정 설정 가이드 생성"""
    print("\n📋 서비스 계정 설정 단계별 가이드")
    print("=" * 50)
    
    guide_content = """
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
"""
    
    guide_file = Path(__file__).parent / "google_sheets_setup_guide.md"
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print(f"📄 설정 가이드 저장: {guide_file}")

if __name__ == "__main__":
    print("🚨 Google Sheets 연동 문제 진단")
    print("=" * 60)
    
    # 환경변수 로드
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # 진단 실행
    diagnose_api_keys()
    suggest_solutions()
    create_service_account_setup_guide()
    
    print(f"\n🎯 결론:")
    print(f"❌ 현재 Google Sheets 연동이 실제로 작동하지 않음")
    print(f"🔧 Google Cloud 서비스 계정 설정이 필수적으로 필요함")
    print(f"⚠️ 이전 '연동 완료' 보고는 잘못된 것이었음")