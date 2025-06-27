#!/usr/bin/env python3
"""
최종 연동 테스트 - 모든 컴포넌트 통합 검증
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def load_environment():
    """환경변수 로드"""
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    return env_file.exists()

def test_gemini_api():
    """Gemini API 테스트"""
    print("🤖 Gemini API 테스트")
    print("-" * 30)
    
    try:
        from dashboard.utils.env_loader import ensure_gemini_api_key
        import requests
        
        api_key = ensure_gemini_api_key()
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": "이것은 연예인 추천 아이템 시스템의 최종 연동 테스트입니다. '테스트 성공'이라고 한국어로 답변해주세요."
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 50
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                ai_response = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ Gemini API 응답: {ai_response}")
                return True
        
        print(f"❌ Gemini API 실패: {response.status_code}")
        return False
        
    except Exception as e:
        print(f"❌ Gemini API 오류: {e}")
        return False

def test_csv_generation():
    """CSV 생성 테스트"""
    print("\n📊 CSV 생성 테스트")
    print("-" * 30)
    
    try:
        import csv
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_data = [
            {
                "시간": timestamp,
                "채널명": "최종 테스트 채널",
                "연예인": "테스트용 아이유",
                "제품명": "MacBook Pro M3",
                "브랜드": "Apple",
                "카테고리": "전자제품",
                "신뢰도": "0.98",
                "감정": "positive",
                "상태": "approved",
                "테스트노트": "최종 통합 테스트 - 모든 시스템 연동 완료"
            }
        ]
        
        csv_file = project_root / f"final_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=test_data[0].keys())
            writer.writeheader()
            writer.writerows(test_data)
        
        print(f"✅ CSV 파일 생성: {csv_file}")
        print(f"📄 파일 크기: {csv_file.stat().st_size} bytes")
        return True, csv_file
        
    except Exception as e:
        print(f"❌ CSV 생성 오류: {e}")
        return False, None

def test_dashboard_modules():
    """대시보드 모듈 테스트"""
    print("\n🎨 대시보드 모듈 테스트")
    print("-" * 30)
    
    try:
        # 핵심 모듈들 import 테스트
        from dashboard.utils.env_loader import ensure_gemini_api_key, get_google_sheet_settings
        from dashboard.utils.database_manager import get_database_manager
        from dashboard.views.google_sheets_management import render_google_sheets_management
        
        print("✅ 환경변수 로더 모듈")
        print("✅ 데이터베이스 매니저 모듈")
        print("✅ Google Sheets 관리 뷰 모듈")
        
        # 환경변수 함수 테스트
        api_key = ensure_gemini_api_key()
        sheet_settings = get_google_sheet_settings()
        
        print(f"✅ Gemini API 키: {api_key[:10]}...")
        print(f"✅ Google Sheets ID: {sheet_settings['sheet_id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 대시보드 모듈 오류: {e}")
        return False

def test_n8n_workflow_format():
    """N8n 워크플로우 형식 테스트"""
    print("\n🔄 N8n 워크플로우 테스트")
    print("-" * 30)
    
    try:
        # Gemini 통합 워크플로우 파일 확인
        workflow_file = project_root / 'n8n-workflows' / 'gemini-integration-workflow.json'
        
        if workflow_file.exists():
            with open(workflow_file, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            print(f"✅ 워크플로우 파일: {workflow_file.name}")
            print(f"✅ 워크플로우 이름: {workflow_data.get('name', 'Unknown')}")
            print(f"✅ 노드 수: {len(workflow_data.get('nodes', []))}")
            print(f"✅ 연결 수: {len(workflow_data.get('connections', {}))}")
            
            # 환경변수 설정 확인
            n8n_env_file = Path.home() / '.n8n' / '.env'
            if n8n_env_file.exists():
                print(f"✅ N8n 환경변수 파일: {n8n_env_file}")
            else:
                print(f"⚠️ N8n 환경변수 파일 없음")
            
            return True
        else:
            print(f"❌ 워크플로우 파일 없음: {workflow_file}")
            return False
            
    except Exception as e:
        print(f"❌ N8n 워크플로우 오류: {e}")
        return False

def create_final_report():
    """최종 보고서 생성"""
    print("\n📋 최종 보고서 생성")
    print("-" * 30)
    
    timestamp = datetime.now()
    
    report = {
        "test_timestamp": timestamp.isoformat(),
        "test_results": {
            "gemini_api": False,
            "csv_generation": False,
            "dashboard_modules": False,
            "n8n_workflows": False
        },
        "environment": {
            "gemini_api_key": bool(os.getenv('GEMINI_API_KEY')),
            "google_sheet_id": bool(os.getenv('GOOGLE_SHEET_ID')),
            "google_sheet_url": bool(os.getenv('GOOGLE_SHEET_URL')),
            "python_version": sys.version.split()[0],
            "project_path": str(project_root)
        },
        "available_features": {
            "ai_analysis": "Gemini API 연동",
            "data_export": "CSV 파일 생성",
            "dashboard": "Streamlit 대시보드",
            "automation": "N8n 워크플로우",
            "notification": "이메일 알림 템플릿"
        },
        "working_solutions": {
            "immediate": [
                "CSV 파일 생성 후 수동 Google Sheets 업로드",
                "Gemini API를 통한 AI 분석",
                "Streamlit 대시보드 실행",
                "이메일 알림 템플릿 생성"
            ],
            "with_setup": [
                "Google Apps Script 자동화",
                "Google Forms 연동",
                "완전한 N8n 워크플로우 자동화"
            ]
        },
        "next_steps": [
            "Google Apps Script 설정으로 완전 자동화",
            "실제 YouTube 채널 데이터로 테스트",
            "대시보드 UI 개선",
            "오류 처리 및 모니터링 강화"
        ]
    }
    
    # 개별 테스트 실행
    report["test_results"]["gemini_api"] = test_gemini_api()
    report["test_results"]["csv_generation"], csv_file = test_csv_generation()
    report["test_results"]["dashboard_modules"] = test_dashboard_modules()
    report["test_results"]["n8n_workflows"] = test_n8n_workflow_format()
    
    # 보고서 파일 저장
    report_file = project_root / f"final_integration_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 최종 보고서 저장: {report_file}")
    
    # 결과 요약
    total_tests = len(report["test_results"])
    passed_tests = sum(report["test_results"].values())
    
    print(f"\n🎯 테스트 결과 요약:")
    print(f"✅ 성공: {passed_tests}/{total_tests}")
    print(f"❌ 실패: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print(f"\n🎉 모든 테스트 통과! 시스템이 정상적으로 작동합니다.")
    else:
        print(f"\n⚠️ 일부 테스트 실패. 세부 내용을 확인하세요.")
    
    return report

def show_usage_instructions():
    """사용 방법 안내"""
    print(f"\n📚 시스템 사용 방법")
    print("=" * 50)
    
    print(f"🚀 즉시 사용 가능한 기능:")
    print(f"1. 대시보드 실행:")
    print(f"   streamlit run dashboard/main_dashboard.py")
    
    print(f"\n2. CSV 데이터 생성:")
    print(f"   python test_alternative_sheets_method.py")
    
    print(f"\n3. Gemini API 테스트:")
    print(f"   python test_gemini_api.py")
    
    print(f"\n📊 Google Sheets 연동:")
    print(f"1. 생성된 CSV 파일을 Google Sheets에 수동 업로드")
    print(f"2. 또는 setup_google_apps_script.md 가이드 따라 자동화 설정")
    
    print(f"\n🔄 N8n 자동화:")
    print(f"1. N8n 실행: n8n start")
    print(f"2. 워크플로우 import: n8n-workflows/ 폴더의 JSON 파일들")
    print(f"3. 환경변수 설정: ~/.n8n/.env 파일 확인")

if __name__ == "__main__":
    print("🔬 연예인 추천 아이템 시스템 - 최종 통합 테스트")
    print("=" * 60)
    
    # 환경변수 로드
    env_loaded = load_environment()
    if not env_loaded:
        print("⚠️ .env 파일을 찾을 수 없습니다.")
    
    # 최종 보고서 생성 및 테스트 실행
    report = create_final_report()
    
    # 사용 방법 안내
    show_usage_instructions()
    
    print(f"\n✨ 최종 통합 테스트 완료!")
    print(f"📄 상세 보고서는 생성된 JSON 파일을 확인하세요.")