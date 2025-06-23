#!/usr/bin/env python3
"""
알림 시스템 통합 테스트 스크립트
Google Sheets 연동 및 모든 알림 워크플로우 테스트
"""

import asyncio
import aiohttp
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# 환경 변수에서 설정 로드
N8N_WEBHOOK_BASE_URL = os.getenv('N8N_WEBHOOK_BASE_URL', 'http://localhost:5678')
PYTHON_ANALYSIS_ENDPOINT = os.getenv('PYTHON_ANALYSIS_ENDPOINT', 'http://localhost:8000')

class NotificationSystemTester:
    """알림 시스템 테스트 클래스"""
    
    def __init__(self):
        self.test_results = []
        self.session = None
    
    async def setup(self):
        """테스트 환경 설정"""
        self.session = aiohttp.ClientSession()
        print("🔧 알림 시스템 테스트 환경 설정 완료")
    
    async def cleanup(self):
        """테스트 환경 정리"""
        if self.session:
            await self.session.close()
        print("🧹 테스트 환경 정리 완료")
    
    async def test_webhook_endpoint(self, endpoint: str, payload: Dict[str, Any], test_name: str) -> bool:
        """웹훅 엔드포인트 테스트"""
        try:
            url = f"{N8N_WEBHOOK_BASE_URL}/webhook/{endpoint}"
            
            async with self.session.post(url, json=payload, timeout=30) as response:
                success = response.status == 200
                result_data = await response.json() if response.content_type == 'application/json' else await response.text()
                
                self.test_results.append({
                    'test_name': test_name,
                    'endpoint': endpoint,
                    'status_code': response.status,
                    'success': success,
                    'response': result_data,
                    'timestamp': datetime.now().isoformat()
                })
                
                status_emoji = "✅" if success else "❌"
                print(f"{status_emoji} {test_name}: {response.status}")
                
                return success
                
        except Exception as e:
            print(f"❌ {test_name}: 오류 - {str(e)}")
            self.test_results.append({
                'test_name': test_name,
                'endpoint': endpoint,
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return False
    
    async def test_google_sheets_sync(self):
        """Google Sheets 동기화 테스트"""
        print("\\n📋 Google Sheets 동기화 테스트 시작")
        
        # 테스트 데이터: 채널 목록 변경사항
        sheets_webhook_payload = {
            "eventType": "SHEET_EDIT",
            "spreadsheetId": "test-spreadsheet-id",
            "sheetId": "test-sheet-id",
            "range": "A2:D5",
            "changeType": "edit"
        }
        
        return await self.test_webhook_endpoint(
            "sheets-webhook",
            sheets_webhook_payload,
            "Google Sheets 변경사항 감지"
        )
    
    async def test_analysis_result_notification(self):
        """분석 결과 알림 테스트"""
        print("\\n🎯 분석 결과 알림 테스트 시작")
        
        # 성공적인 분석 결과
        success_payload = {
            "job_id": "test-job-123",
            "video_title": "강민경의 파리 여행 VLOG",
            "channel_name": "걍밍경",
            "video_url": "https://www.youtube.com/watch?v=test123",
            "status": "completed",
            "candidates_found": 5,
            "approved_candidates": 3,
            "rejected_candidates": 2,
            "avg_score": 82.5,
            "top_product": {
                "name": "아비에무아 숄더백",
                "score": 88
            },
            "processing_time_seconds": 145
        }
        
        success_test = await self.test_webhook_endpoint(
            "analysis-complete",
            success_payload,
            "분석 완료 알림 (성공)"
        )
        
        # 실패한 분석 결과
        failure_payload = {
            "job_id": "test-job-456",
            "video_title": "테스트 영상",
            "channel_name": "테스트 채널",
            "video_url": "https://www.youtube.com/watch?v=test456",
            "status": "failed",
            "candidates_found": 0,
            "error_message": "영상 다운로드 실패",
            "processing_time_seconds": 30
        }
        
        failure_test = await self.test_webhook_endpoint(
            "analysis-complete",
            failure_payload,
            "분석 실패 알림"
        )
        
        return success_test and failure_test
    
    async def test_error_notification_system(self):
        """에러 알림 시스템 테스트"""
        print("\\n🚨 에러 알림 시스템 테스트 시작")
        
        # 심각한 시스템 에러
        critical_error_payload = {
            "error_id": "ERR-CRITICAL-001",
            "error_type": "DatabaseConnectionFailure",
            "error_message": "데이터베이스 연결 실패: Connection timeout after 30 seconds",
            "component": "analysis-engine",
            "stack_trace": "Traceback (most recent call last):\\n  File ...",
            "environment": "production",
            "timestamp": datetime.now().isoformat()
        }
        
        critical_test = await self.test_webhook_endpoint(
            "system-error",
            critical_error_payload,
            "심각한 시스템 에러 알림"
        )
        
        # 일반 경고
        warning_payload = {
            "error_id": "WARN-001",
            "error_type": "APIRateLimit",
            "error_message": "Gemini API 요청 한도 근접",
            "component": "ai-analyzer",
            "environment": "production",
            "timestamp": datetime.now().isoformat()
        }
        
        warning_test = await self.test_webhook_endpoint(
            "system-error",
            warning_payload,
            "일반 경고 알림"
        )
        
        return critical_test and warning_test
    
    async def test_notification_routing(self):
        """알림 라우팅 시스템 테스트"""
        print("\\n🔀 알림 라우팅 시스템 테스트 시작")
        
        # 다양한 우선순위 알림 테스트
        test_cases = [
            {
                "payload": {
                    "type": "system_error",
                    "message": "Critical database failure",
                    "component": "database",
                    "source": "monitoring"
                },
                "name": "CRITICAL 우선순위 라우팅"
            },
            {
                "payload": {
                    "type": "analysis_completed",
                    "message": "분석 완료",
                    "component": "analyzer",
                    "source": "workflow"
                },
                "name": "MEDIUM 우선순위 라우팅"
            },
            {
                "payload": {
                    "type": "channel_sync",
                    "message": "채널 목록 동기화",
                    "component": "sync",
                    "source": "sheets"
                },
                "name": "LOW 우선순위 라우팅"
            }
        ]
        
        results = []
        for case in test_cases:
            result = await self.test_webhook_endpoint(
                "notification-router",
                case["payload"],
                case["name"]
            )
            results.append(result)
        
        return all(results)
    
    async def test_daily_report_generation(self):
        """일일 리포트 생성 테스트"""
        print("\\n📊 일일 리포트 생성 테스트 시작")
        
        # 통계 API 테스트
        try:
            url = f"{PYTHON_ANALYSIS_ENDPOINT}/api/notifications/stats/daily"
            params = {
                "start_date": "2025-06-22",
                "end_date": "2025-06-23"
            }
            
            async with self.session.get(url, params=params, timeout=30) as response:
                success = response.status == 200
                if success:
                    stats_data = await response.json()
                    print(f"✅ 통계 API 호출 성공: {len(stats_data)} 항목")
                else:
                    print(f"❌ 통계 API 호출 실패: {response.status}")
                
                self.test_results.append({
                    'test_name': '일일 통계 API 테스트',
                    'endpoint': 'stats/daily',
                    'success': success,
                    'status_code': response.status,
                    'timestamp': datetime.now().isoformat()
                })
                
                return success
                
        except Exception as e:
            print(f"❌ 통계 API 테스트 오류: {str(e)}")
            return False
    
    async def test_throttling_system(self):
        """스로틀링 시스템 테스트"""
        print("\\n⏱️ 스로틀링 시스템 테스트 시작")
        
        try:
            # 스로틀링 체크 API 테스트
            check_url = f"{PYTHON_ANALYSIS_ENDPOINT}/api/notifications/throttle/check"
            check_params = {
                "key": "test_throttle_key",
                "seconds": "300"
            }
            
            async with self.session.get(check_url, params=check_params, timeout=10) as response:
                check_success = response.status == 200
                print(f"{'✅' if check_success else '❌'} 스로틀링 체크: {response.status}")
            
            # 스로틀링 설정 API 테스트
            set_url = f"{PYTHON_ANALYSIS_ENDPOINT}/api/notifications/throttle/set"
            set_payload = {
                "key": "test_throttle_key",
                "seconds": 300,
                "metadata": {"test": True}
            }
            
            async with self.session.post(set_url, json=set_payload, timeout=10) as response:
                set_success = response.status == 200
                print(f"{'✅' if set_success else '❌'} 스로틀링 설정: {response.status}")
            
            success = check_success and set_success
            
            self.test_results.append({
                'test_name': '스로틀링 시스템 테스트',
                'success': success,
                'check_status': check_success,
                'set_status': set_success,
                'timestamp': datetime.now().isoformat()
            })
            
            return success
            
        except Exception as e:
            print(f"❌ 스로틀링 시스템 테스트 오류: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 알림 시스템 통합 테스트 시작")
        print("=" * 60)
        
        await self.setup()
        
        try:
            # 테스트 실행
            test_functions = [
                self.test_google_sheets_sync,
                self.test_analysis_result_notification,
                self.test_error_notification_system,
                self.test_notification_routing,
                self.test_daily_report_generation,
                self.test_throttling_system
            ]
            
            results = []
            for test_func in test_functions:
                result = await test_func()
                results.append(result)
                await asyncio.sleep(1)  # 테스트 간 대기
            
            # 결과 요약
            self.print_test_summary(results)
            
        finally:
            await self.cleanup()
    
    def print_test_summary(self, results: List[bool]):
        """테스트 결과 요약 출력"""
        print("\\n" + "=" * 60)
        print("📊 테스트 결과 요약")
        print("=" * 60)
        
        total_tests = len(results)
        passed_tests = sum(results)
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"총 테스트: {total_tests}")
        print(f"성공: {passed_tests} ✅")
        print(f"실패: {failed_tests} ❌")
        print(f"성공률: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("\\n🎉 알림 시스템이 정상적으로 작동합니다!")
        elif success_rate >= 60:
            print("\\n⚠️ 일부 개선이 필요합니다.")
        else:
            print("\\n🚨 심각한 문제가 발견되었습니다. 시스템 점검이 필요합니다.")
        
        # 상세 결과 저장
        self.save_detailed_results()
    
    def save_detailed_results(self):
        """상세 테스트 결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"notification_test_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'test_summary': {
                    'timestamp': datetime.now().isoformat(),
                    'total_tests': len(self.test_results),
                    'results': self.test_results
                }
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\\n📄 상세 결과가 {filename}에 저장되었습니다.")

async def main():
    """메인 함수"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("""
알림 시스템 통합 테스트 스크립트

사용법:
  python test_notification_system.py

환경 변수:
  N8N_WEBHOOK_BASE_URL: n8n 웹훅 기본 URL (기본: http://localhost:5678)
  PYTHON_ANALYSIS_ENDPOINT: Python API 엔드포인트 (기본: http://localhost:8000)

테스트 항목:
  - Google Sheets 동기화
  - 분석 결과 알림
  - 에러 알림 시스템
  - 알림 라우팅
  - 일일 리포트 생성
  - 스로틀링 시스템
        """)
        return
    
    tester = NotificationSystemTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())