#!/usr/bin/env python3
"""
전체 인프라 API 키 적용 상태 체크 스크립트
"""

import os
import sys
from pathlib import Path

def load_env_files():
    """모든 .env 파일 로드"""
    project_root = Path(__file__).parent
    env_files = [
        '.env',
        '.env.example', 
        '.env.n8n'
    ]
    
    all_env_vars = {}
    
    for env_file in env_files:
        file_path = project_root / env_file
        if file_path.exists():
            print(f"\n📄 {env_file} 파일 분석 중...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        continue
                    
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key not in all_env_vars:
                            all_env_vars[key] = {}
                        
                        all_env_vars[key][env_file] = value
    
    return all_env_vars

def analyze_api_keys():
    """API 키 상태 분석"""
    print("🔍 API 키 적용 상태 체크 시작...")
    print("=" * 60)
    
    # 필수 API 키들
    critical_keys = {
        'GEMINI_API_KEY': 'Google Gemini AI',
        'GOOGLE_API_KEY': 'Google Gemini AI (Alternative)',
        'YOUTUBE_API_KEY': 'YouTube Data API v3',
        'GOOGLE_SHEETS_SPREADSHEET_ID': 'Google Sheets 연동',
        'GOOGLE_SHEETS_CREDENTIALS_PATH': 'Google Sheets 인증'
    }
    
    # 선택적 API 키들
    optional_keys = {
        'OPENAI_API_KEY': 'OpenAI GPT',
        'COUPANG_API_KEY': '쿠팡 파트너스',
        'COUPANG_SECRET_KEY': '쿠팡 파트너스 시크릿',
        'RESEND_API_KEY': 'Resend 이메일',
        'SLACK_WEBHOOK_URL': 'Slack 알림',
        'TELEGRAM_BOT_TOKEN': 'Telegram 봇'
    }
    
    # 보안 관련 키들
    security_keys = {
        'JWT_SECRET': 'JWT 토큰 시크릿',
        'ENCRYPTION_KEY': '데이터 암호화 키',
        'N8N_ENCRYPTION_KEY': 'n8n 암호화 키',
        'N8N_USER_MANAGEMENT_JWT_SECRET': 'n8n JWT 시크릿'
    }
    
    env_vars = load_env_files()
    
    print("\n🔑 === 필수 API 키 상태 ===")
    critical_ready = 0
    for key, description in critical_keys.items():
        status = check_key_status(env_vars, key, description)
        if status:
            critical_ready += 1
    
    print(f"\n📊 필수 키 상태: {critical_ready}/{len(critical_keys)} ({'✅ 완료' if critical_ready == len(critical_keys) else '⚠️ 미완료'})")
    
    print("\n🔧 === 선택적 API 키 상태 ===")
    optional_ready = 0
    for key, description in optional_keys.items():
        status = check_key_status(env_vars, key, description)
        if status:
            optional_ready += 1
    
    print(f"\n📊 선택적 키 상태: {optional_ready}/{len(optional_keys)}")
    
    print("\n🔒 === 보안 키 상태 ===")
    security_ready = 0
    for key, description in security_keys.items():
        status = check_key_status(env_vars, key, description)
        if status:
            security_ready += 1
    
    print(f"\n📊 보안 키 상태: {security_ready}/{len(security_keys)} ({'✅ 완료' if security_ready == len(security_keys) else '⚠️ 미완료'})")
    
    return critical_ready, optional_ready, security_ready, len(critical_keys), len(optional_keys), len(security_keys)

def check_key_status(env_vars, key, description):
    """개별 키 상태 체크"""
    if key in env_vars:
        values = env_vars[key]
        
        # 실제 값이 설정되었는지 확인
        has_real_value = False
        files_with_values = []
        
        for file_name, value in values.items():
            if value and not value.startswith('your_') and not value == 'your-' and value != 'TODO':
                has_real_value = True
                files_with_values.append(file_name)
        
        if has_real_value:
            files_str = ', '.join(files_with_values)
            value_preview = list(values.values())[0]
            if len(value_preview) > 20:
                value_preview = value_preview[:15] + "..."
            print(f"   ✅ {key:35} | {description:25} | {files_str} | {value_preview}")
            return True
        else:
            files_str = ', '.join(values.keys())
            print(f"   ❌ {key:35} | {description:25} | {files_str} | 기본값")
            return False
    else:
        print(f"   ❌ {key:35} | {description:25} | 없음")
        return False

def check_service_readiness():
    """서비스별 준비 상태 체크"""
    print("\n🚀 === 서비스별 준비 상태 ===")
    
    services = {
        '대시보드': ['GEMINI_API_KEY', 'YOUTUBE_API_KEY', 'GOOGLE_SHEETS_SPREADSHEET_ID'],
        'Google Sheets 연동': ['GOOGLE_SHEETS_CREDENTIALS_PATH', 'GOOGLE_SHEETS_SPREADSHEET_ID'],
        'n8n 워크플로우': ['N8N_ENCRYPTION_KEY', 'N8N_USER_MANAGEMENT_JWT_SECRET'],
        'AI 분석': ['GEMINI_API_KEY'],
        'YouTube 데이터': ['YOUTUBE_API_KEY']
    }
    
    env_vars = load_env_files()
    
    for service_name, required_keys in services.items():
        ready_keys = 0
        for key in required_keys:
            if key in env_vars:
                values = env_vars[key]
                has_real_value = any(
                    value and not value.startswith('your_') and not value == 'your-' and value != 'TODO'
                    for value in values.values()
                )
                if has_real_value:
                    ready_keys += 1
        
        status = "✅ 준비완료" if ready_keys == len(required_keys) else f"⚠️ {ready_keys}/{len(required_keys)}"
        print(f"   {service_name:20} | {status}")

def check_credentials_files():
    """인증 파일 존재 확인"""
    print("\n📁 === 인증 파일 상태 ===")
    
    credential_files = [
        'credentials/google_sheets_credentials.json',
        '.firebaserc',
        'firebase.json'
    ]
    
    project_root = Path(__file__).parent
    
    for file_path in credential_files:
        full_path = project_root / file_path
        if full_path.exists():
            file_size = full_path.stat().st_size
            print(f"   ✅ {file_path:40} | {file_size:,} bytes")
        else:
            print(f"   ❌ {file_path:40} | 파일 없음")

def main():
    """메인 함수"""
    print("🔍 Influence Item - 전체 인프라 API 키 적용 상태 체크")
    print("=" * 60)
    
    # API 키 분석
    critical_ready, optional_ready, security_ready, total_critical, total_optional, total_security = analyze_api_keys()
    
    # 서비스별 준비 상태
    check_service_readiness()
    
    # 인증 파일 확인
    check_credentials_files()
    
    # 전체 요약
    print("\n" + "=" * 60)
    print("📊 === 전체 상태 요약 ===")
    print("=" * 60)
    
    print(f"🔑 필수 API 키:     {critical_ready:2d}/{total_critical:2d} ({'✅ 완료' if critical_ready == total_critical else '❌ 미완료'})")
    print(f"🔧 선택적 API 키:   {optional_ready:2d}/{total_optional:2d}")
    print(f"🔒 보안 키:         {security_ready:2d}/{total_security:2d} ({'✅ 완료' if security_ready == total_security else '❌ 미완료'})")
    
    # 전체 준비 상태 판정
    is_production_ready = (critical_ready == total_critical) and (security_ready == total_security)
    
    if is_production_ready:
        print("\n🎉 === 프로덕션 준비 완료! ===")
        print("모든 필수 API 키와 보안 키가 설정되었습니다.")
        print("대시보드, n8n, AI 분석 시스템을 안전하게 실행할 수 있습니다.")
    else:
        print("\n⚠️ === 추가 설정 필요 ===")
        if critical_ready < total_critical:
            print("- 필수 API 키가 누락되었습니다.")
        if security_ready < total_security:
            print("- 보안 키 설정이 필요합니다.")
        print("위 항목들을 설정 후 다시 실행하세요.")
    
    return is_production_ready

if __name__ == "__main__":
    ready = main()
    sys.exit(0 if ready else 1)