#!/usr/bin/env python3
"""
통합 모듈 설정 및 테스트 스크립트
Google Sheets, Slack, n8n 통합 기능을 설정하고 테스트
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env_file():
    """환경변수 로드"""
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    if not os.getenv(key):
                        os.environ[key] = value

def test_google_sheets_integration():
    """Google Sheets 통합 테스트"""
    print("🔍 Google Sheets 통합 테스트 중...")
    
    try:
        from src.integrations.google_sheets_integration import GoogleSheetsIntegration
        
        # 통합 초기화
        sheets = GoogleSheetsIntegration()
        
        # 스프레드시트 정보 조회
        info = sheets.get_spreadsheet_info()
        print(f"✅ Google Sheets 연결 성공")
        print(f"   - 제목: {info['title']}")
        print(f"   - 시트 수: {len(info['sheets'])}")
        print(f"   - URL: {info['url']}")
        
        # 통계 조회
        stats = sheets.get_statistics()
        print(f"   - 총 탐색 결과: {stats['total_discoveries']}")
        print(f"   - 고유 채널: {stats['unique_channels']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Google Sheets 테스트 실패: {str(e)}")
        return False

def test_slack_integration():
    """Slack 통합 테스트"""
    print("🔍 Slack 통합 테스트 중...")
    
    try:
        from src.integrations.slack_integration import SlackIntegration
        
        # 통합 초기화
        slack = SlackIntegration()
        
        # 연결 테스트
        if slack.test_connection():
            print("✅ Slack 연결 성공")
            
            # 테스트 메시지 전송
            test_message = f"🧪 통합 설정 테스트\n\n시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n상태: 모든 통합 모듈이 정상 작동합니다!"
            
            if slack.send_simple_message("통합 설정 완료", test_message):
                print("✅ Slack 테스트 메시지 전송 성공")
                return True
            else:
                print("❌ Slack 테스트 메시지 전송 실패")
                return False
        else:
            print("❌ Slack 연결 실패")
            return False
            
    except Exception as e:
        print(f"❌ Slack 테스트 실패: {str(e)}")
        return False

def test_api_server():
    """API 서버 테스트"""
    print("🔍 API 서버 테스트 중...")
    
    try:
        import requests
        
        api_url = os.getenv('CHANNEL_DISCOVERY_API_URL', 'http://localhost:5001')
        
        # 헬스 체크
        response = requests.get(f"{api_url}/health", timeout=5)
        
        if response.status_code == 200:
            print("✅ API 서버 연결 성공")
            
            # 통합 상태 확인
            response = requests.get(f"{api_url}/integrations/status", timeout=10)
            
            if response.status_code == 200:
                status = response.json()
                integrations = status.get('integrations', {})
                
                print("📊 통합 모듈 상태:")
                for service, info in integrations.items():
                    status_icon = "✅" if info.get('available') else "❌"
                    print(f"   - {service}: {status_icon}")
                    if info.get('error'):
                        print(f"     오류: {info['error']}")
                
                return True
            else:
                print(f"❌ 통합 상태 확인 실패: {response.status_code}")
                return False
        else:
            print(f"❌ API 서버 연결 실패: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API 서버 테스트 실패: {str(e)}")
        print("💡 API 서버가 실행 중인지 확인하세요: python src/api/channel_discovery_api.py")
        return False

def validate_environment():
    """환경변수 검증"""
    print("🔍 환경변수 검증 중...")
    
    required_vars = [
        'YOUTUBE_API_KEY',
        'GOOGLE_SHEETS_SPREADSHEET_ID',
        'SLACK_WEBHOOK_URL'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value in ['your_api_key_here', 'your_slack_webhook_url_here']:
            missing_vars.append(var)
        else:
            print(f"✅ {var}: 설정됨")
    
    if missing_vars:
        print("❌ 누락된 환경변수:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    return True

def validate_files():
    """필수 파일 검증"""
    print("🔍 필수 파일 검증 중...")
    
    required_files = [
        '.env',
        'credentials/google_sheets_credentials.json'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}: 존재함")
        else:
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ 누락된 파일:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    return True

def create_setup_summary():
    """설정 요약 생성"""
    summary = {
        "setup_completed_at": datetime.now().isoformat(),
        "integrations": {
            "google_sheets": {
                "enabled": True,
                "spreadsheet_id": os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID'),
                "credentials_path": os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
            },
            "slack": {
                "enabled": True,
                "webhook_configured": bool(os.getenv('SLACK_WEBHOOK_URL'))
            },
            "api_server": {
                "url": os.getenv('CHANNEL_DISCOVERY_API_URL', 'http://localhost:5001'),
                "endpoints": [
                    "/health",
                    "/discover",
                    "/sheets/statistics",
                    "/slack/test",
                    "/integrations/status"
                ]
            }
        },
        "n8n_workflows": [
            "complete_channel_discovery_workflow.json",
            "google-sheets-sync-workflow.json"
        ],
        "dashboard_pages": [
            "channel_discovery_results.py",
            "google_sheets_management.py"
        ]
    }
    
    summary_file = project_root / "integration_setup_summary.json"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"📄 설정 요약 저장: {summary_file}")
    return summary

def main():
    """메인 함수"""
    print("🚀 통합 모듈 설정 및 테스트 시작")
    print("=" * 60)
    
    # 환경변수 로드
    load_env_file()
    
    # 검증 단계
    print("\n1️⃣ 환경변수 및 파일 검증")
    env_valid = validate_environment()
    files_valid = validate_files()
    
    if not (env_valid and files_valid):
        print("\n❌ 설정 검증 실패. 위의 오류를 수정한 후 다시 시도하세요.")
        return False
    
    # 통합 테스트
    print("\n2️⃣ 통합 모듈 테스트")
    
    sheets_ok = test_google_sheets_integration()
    slack_ok = test_slack_integration()
    api_ok = test_api_server()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📋 설정 및 테스트 결과:")
    print(f"• 환경변수: {'✅ 검증됨' if env_valid else '❌ 실패'}")
    print(f"• 필수 파일: {'✅ 검증됨' if files_valid else '❌ 실패'}")
    print(f"• Google Sheets: {'✅ 정상' if sheets_ok else '❌ 실패'}")
    print(f"• Slack 알림: {'✅ 정상' if slack_ok else '❌ 실패'}")
    print(f"• API 서버: {'✅ 정상' if api_ok else '❌ 실패'}")
    
    all_success = all([env_valid, files_valid, sheets_ok, slack_ok, api_ok])
    
    if all_success:
        print("\n🎉 모든 통합 설정이 완료되었습니다!")
        
        # 설정 요약 생성
        summary = create_setup_summary()
        
        print("\n📚 사용 가능한 기능:")
        print("• 매일 자동 채널 탐색")
        print("• Google Sheets 자동 저장")
        print("• Slack 실시간 알림")
        print("• n8n 워크플로우 자동화")
        print("• 웹 대시보드 관리")
        
        print("\n🔧 다음 단계:")
        print("1. n8n에서 워크플로우 import")
        print("2. 대시보드 실행: streamlit run dashboard/main.py")
        print("3. API 서버 실행: python src/api/channel_discovery_api.py")
        
    else:
        print("\n⚠️ 일부 설정에 문제가 있습니다. 위의 오류를 확인하고 수정하세요.")
    
    return all_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)