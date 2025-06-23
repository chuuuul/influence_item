#!/usr/bin/env python3
"""
n8n 워크플로우 통합 테스트 스크립트
자동 영상 수집 워크플로우의 모든 구성 요소를 테스트합니다.
"""

import asyncio
import json
import os
import sys
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('n8n_workflow_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class N8NWorkflowTester:
    """N8N 워크플로우 테스트 클래스"""
    
    def __init__(self):
        self.n8n_base_url = os.getenv('N8N_BASE_URL', 'http://localhost:5678')
        self.n8n_api_key = os.getenv('N8N_API_KEY')
        self.python_api_url = os.getenv('PYTHON_ANALYSIS_ENDPOINT', 'http://localhost:8000')
        self.test_results = []
        
        if not self.n8n_api_key:
            logger.warning("N8N_API_KEY가 설정되지 않았습니다. 일부 테스트가 제한될 수 있습니다.")
    
    def log_test_result(self, test_name: str, success: bool, message: str, details: Optional[Dict] = None):
        """테스트 결과 로깅"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}: {message}")
        
        if details:
            logger.debug(f"Details: {json.dumps(details, indent=2)}")
    
    async def test_n8n_server_health(self) -> bool:
        """n8n 서버 헬스 체크"""
        try:
            response = requests.get(f"{self.n8n_base_url}/healthz", timeout=10)
            success = response.status_code == 200
            
            self.log_test_result(
                "N8N Server Health Check",
                success,
                f"서버 응답: {response.status_code}",
                {"response_time": response.elapsed.total_seconds()}
            )
            return success
            
        except Exception as e:
            self.log_test_result(
                "N8N Server Health Check",
                False,
                f"서버 연결 실패: {str(e)}"
            )
            return False
    
    async def test_python_analysis_api(self) -> bool:
        """Python 분석 API 헬스 체크"""
        try:
            response = requests.get(f"{self.python_api_url}/health", timeout=10)
            success = response.status_code == 200
            
            if success:
                health_data = response.json()
                self.log_test_result(
                    "Python Analysis API Health",
                    True,
                    "분석 API 정상 응답",
                    health_data
                )
            else:
                self.log_test_result(
                    "Python Analysis API Health",
                    False,
                    f"API 응답 오류: {response.status_code}"
                )
            
            return success
            
        except Exception as e:
            self.log_test_result(
                "Python Analysis API Health",
                False,
                f"API 연결 실패: {str(e)}"
            )
            return False
    
    async def test_workflow_import(self) -> bool:
        """워크플로우 JSON 파일 유효성 검사"""
        workflow_files = [
            'n8n-workflows/video-collection-workflow.json',
            'n8n-workflows/error-handling-workflow.json',
            'n8n-workflows/monitoring-workflow.json'
        ]
        
        all_valid = True
        
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow_data = json.load(f)
                
                # 필수 필드 검사
                required_fields = ['name', 'nodes', 'connections']
                missing_fields = [field for field in required_fields if field not in workflow_data]
                
                if missing_fields:
                    self.log_test_result(
                        f"Workflow Import - {workflow_file}",
                        False,
                        f"필수 필드 누락: {missing_fields}"
                    )
                    all_valid = False
                else:
                    node_count = len(workflow_data.get('nodes', []))
                    self.log_test_result(
                        f"Workflow Import - {workflow_file}",
                        True,
                        f"유효한 워크플로우 ({node_count}개 노드)",
                        {"node_count": node_count}
                    )
                    
            except Exception as e:
                self.log_test_result(
                    f"Workflow Import - {workflow_file}",
                    False,
                    f"파일 읽기 오류: {str(e)}"
                )
                all_valid = False
        
        return all_valid
    
    async def test_google_sheets_credentials(self) -> bool:
        """Google Sheets API 자격 증명 테스트"""
        try:
            # 환경 변수 확인
            sheets_id = os.getenv('GOOGLE_SHEETS_CHANNEL_LIST_ID')
            if not sheets_id:
                self.log_test_result(
                    "Google Sheets Credentials",
                    False,
                    "GOOGLE_SHEETS_CHANNEL_LIST_ID 환경 변수가 설정되지 않음"
                )
                return False
            
            # 실제 API 호출은 구현되지 않았으므로 환경 변수 존재만 확인
            self.log_test_result(
                "Google Sheets Credentials",
                True,
                "Google Sheets 설정 확인됨",
                {"sheets_id": sheets_id[:10] + "..."}
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Google Sheets Credentials",
                False,
                f"자격 증명 확인 실패: {str(e)}"
            )
            return False
    
    async def test_slack_integration(self) -> bool:
        """Slack 연동 설정 테스트"""
        try:
            slack_token = os.getenv('SLACK_BOT_TOKEN')
            slack_channel = os.getenv('SLACK_CHANNEL')
            
            if not slack_token:
                self.log_test_result(
                    "Slack Integration",
                    False,
                    "SLACK_BOT_TOKEN 환경 변수가 설정되지 않음"
                )
                return False
            
            if not slack_channel:
                self.log_test_result(
                    "Slack Integration",
                    False,
                    "SLACK_CHANNEL 환경 변수가 설정되지 않음"
                )
                return False
            
            self.log_test_result(
                "Slack Integration",
                True,
                "Slack 설정 확인됨",
                {"channel": slack_channel}
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Slack Integration",
                False,
                f"Slack 설정 확인 실패: {str(e)}"
            )
            return False
    
    async def test_cron_expression_validation(self) -> bool:
        """Cron 표현식 유효성 검사"""
        try:
            # 매일 오전 7시 실행을 위한 cron 표현식
            cron_expression = "0 7 * * *"
            
            # 간단한 cron 표현식 검증
            parts = cron_expression.split()
            if len(parts) != 5:
                self.log_test_result(
                    "Cron Expression Validation",
                    False,
                    f"잘못된 cron 표현식 형식: {cron_expression}"
                )
                return False
            
            self.log_test_result(
                "Cron Expression Validation",
                True,
                f"유효한 cron 표현식: {cron_expression}"
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Cron Expression Validation",
                False,
                f"Cron 표현식 검증 실패: {str(e)}"
            )
            return False
    
    async def test_error_handling_logic(self) -> bool:
        """에러 핸들링 로직 테스트"""
        try:
            # 에러 워크플로우 JSON 파일 확인
            with open('n8n-workflows/error-handling-workflow.json', 'r', encoding='utf-8') as f:
                error_workflow = json.load(f)
            
            # 에러 트리거 노드 확인
            error_trigger_nodes = [
                node for node in error_workflow['nodes'] 
                if node['type'] == 'n8n-nodes-base.errorTrigger'
            ]
            
            if not error_trigger_nodes:
                self.log_test_result(
                    "Error Handling Logic",
                    False,
                    "에러 트리거 노드가 없음"
                )
                return False
            
            # 재시도 로직 노드 확인
            retry_nodes = [
                node for node in error_workflow['nodes']
                if 'retry' in node.get('name', '').lower()
            ]
            
            if not retry_nodes:
                self.log_test_result(
                    "Error Handling Logic",
                    False,
                    "재시도 로직 노드가 없음"
                )
                return False
            
            self.log_test_result(
                "Error Handling Logic",
                True,
                f"에러 핸들링 로직 확인됨 (재시도 노드: {len(retry_nodes)}개)"
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Error Handling Logic",
                False,
                f"에러 핸들링 로직 확인 실패: {str(e)}"
            )
            return False
    
    async def test_monitoring_configuration(self) -> bool:
        """모니터링 설정 테스트"""
        try:
            # 모니터링 워크플로우 확인
            with open('n8n-workflows/monitoring-workflow.json', 'r', encoding='utf-8') as f:
                monitoring_workflow = json.load(f)
            
            # 스케줄 트리거 노드 확인
            schedule_nodes = [
                node for node in monitoring_workflow['nodes']
                if node['type'] == 'n8n-nodes-base.scheduleTrigger'
            ]
            
            if len(schedule_nodes) < 2:  # 30분마다 + 일일 리포트
                self.log_test_result(
                    "Monitoring Configuration",
                    False,
                    f"모니터링 스케줄 노드 부족: {len(schedule_nodes)}개"
                )
                return False
            
            # Slack 알림 노드 확인
            slack_nodes = [
                node for node in monitoring_workflow['nodes']
                if node['type'] == 'n8n-nodes-base.slack'
            ]
            
            if not slack_nodes:
                self.log_test_result(
                    "Monitoring Configuration",
                    False,
                    "Slack 알림 노드가 없음"
                )
                return False
            
            self.log_test_result(
                "Monitoring Configuration",
                True,
                f"모니터링 설정 확인됨 (스케줄: {len(schedule_nodes)}개, 알림: {len(slack_nodes)}개)"
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Monitoring Configuration",
                False,
                f"모니터링 설정 확인 실패: {str(e)}"
            )
            return False
    
    async def test_environment_variables(self) -> bool:
        """필수 환경 변수 확인"""
        required_env_vars = [
            'GOOGLE_SHEETS_CHANNEL_LIST_ID',
            'PYTHON_ANALYSIS_ENDPOINT',
            'SLACK_CHANNEL',
            'ANALYSIS_API_KEY'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.log_test_result(
                "Environment Variables",
                False,
                f"누락된 환경 변수: {missing_vars}"
            )
            return False
        
        self.log_test_result(
            "Environment Variables",
            True,
            "모든 필수 환경 변수 확인됨"
        )
        return True
    
    async def run_all_tests(self) -> Dict:
        """모든 테스트 실행"""
        logger.info("=== N8N 워크플로우 통합 테스트 시작 ===")
        start_time = time.time()
        
        # 테스트 실행
        tests = [
            self.test_n8n_server_health(),
            self.test_python_analysis_api(),
            self.test_workflow_import(),
            self.test_google_sheets_credentials(),
            self.test_slack_integration(),
            self.test_cron_expression_validation(),
            self.test_error_handling_logic(),
            self.test_monitoring_configuration(),
            self.test_environment_variables()
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        # 결과 집계
        total_tests = len(results)
        passed_tests = sum(1 for result in results if result is True)
        failed_tests = total_tests - passed_tests
        
        duration = time.time() - start_time
        
        # 요약 생성
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            "test_results": self.test_results
        }
        
        logger.info(f"=== 테스트 완료 ===")
        logger.info(f"총 테스트: {total_tests}")
        logger.info(f"성공: {passed_tests}")
        logger.info(f"실패: {failed_tests}")
        logger.info(f"성공률: {summary['success_rate']:.1f}%")
        logger.info(f"소요시간: {duration:.2f}초")
        
        # 결과를 JSON 파일로 저장
        with open('n8n_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary

async def main():
    """메인 실행 함수"""
    tester = N8NWorkflowTester()
    
    try:
        summary = await tester.run_all_tests()
        
        # 성공률에 따라 종료 코드 결정
        if summary['success_rate'] >= 80:
            logger.info("테스트 성공! (80% 이상 통과)")
            sys.exit(0)
        else:
            logger.error("테스트 실패! (80% 미만 통과)")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())