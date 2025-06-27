#!/usr/bin/env python3
"""
최종 시스템 검증 스크립트
PRD v1.0 - End-to-End 테스트 및 운영 준비 확인
"""

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict

# 프로젝트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from src.youtube_api import YouTubeAPIManager
    from src.ai_analysis import AIAnalysisPipeline
    from src.google_sheets_integration import GoogleSheetsManager
    from src.slack_integration import SlackNotifier, NotificationType
    from dashboard.utils.database_manager import get_database_manager
except ImportError as e:
    print(f"❌ 모듈 import 실패: {e}")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemVerifier:
    """시스템 전체 검증"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "unknown",
            "components": {},
            "end_to_end_tests": {},
            "readiness_score": 0,
            "critical_issues": [],
            "recommendations": []
        }
        
        self.api_base_url = os.getenv('RSS_AUTOMATION_API_URL', 'http://localhost:5002')
        self.dashboard_url = "http://localhost:8501"
        self.n8n_url = "http://localhost:5678"
    
    def verify_environment_variables(self) -> bool:
        """환경변수 확인"""
        print("🔍 환경변수 검증 중...")
        
        required_vars = [
            'GEMINI_API_KEY',
            'YOUTUBE_API_KEY',
            'GOOGLE_SHEET_ID',
            'GOOGLE_CREDENTIALS_PATH'
        ]
        
        optional_vars = [
            'SLACK_WEBHOOK_URL',
            'API_SECRET_KEY',
            'GOOGLE_SHEET_URL'
        ]
        
        missing_required = []
        missing_optional = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
        
        for var in optional_vars:
            if not os.getenv(var):
                missing_optional.append(var)
        
        self.results["components"]["environment"] = {
            "status": "healthy" if not missing_required else "unhealthy",
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "total_vars_checked": len(required_vars) + len(optional_vars)
        }
        
        if missing_required:
            self.results["critical_issues"].append(f"필수 환경변수 누락: {', '.join(missing_required)}")
            print(f"❌ 필수 환경변수 누락: {missing_required}")
            return False
        
        if missing_optional:
            print(f"⚠️  선택적 환경변수 누락: {missing_optional}")
        
        print("✅ 환경변수 검증 완료")
        return True
    
    def verify_api_components(self) -> bool:
        """API 컴포넌트들 검증"""
        print("🔍 API 컴포넌트 검증 중...")
        
        components_status = {}
        
        # YouTube API 검증
        try:
            youtube_manager = YouTubeAPIManager()
            if youtube_manager.youtube:
                # 간단한 채널 정보 조회 테스트
                test_channel = youtube_manager.get_channel_info("UCXuqSBlHAE6Xw-yeJA0Tunw")  # Linus Tech Tips
                if test_channel:
                    components_status["youtube_api"] = {
                        "status": "healthy",
                        "test_result": "채널 정보 조회 성공"
                    }
                else:
                    components_status["youtube_api"] = {
                        "status": "degraded",
                        "test_result": "채널 정보 조회 실패"
                    }
            else:
                components_status["youtube_api"] = {
                    "status": "unhealthy",
                    "error": "YouTube API 초기화 실패"
                }
        except Exception as e:
            components_status["youtube_api"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Gemini API 검증
        try:
            from src.ai_analysis import GeminiAnalyzer
            gemini_analyzer = GeminiAnalyzer()
            if gemini_analyzer.model:
                components_status["gemini_api"] = {
                    "status": "healthy",
                    "test_result": "Gemini 모델 초기화 성공"
                }
            else:
                components_status["gemini_api"] = {
                    "status": "unhealthy",
                    "error": "Gemini 모델 초기화 실패"
                }
        except Exception as e:
            components_status["gemini_api"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Google Sheets 검증
        try:
            sheets_manager = GoogleSheetsManager()
            test_result = sheets_manager.test_connection()
            if test_result["connected"]:
                components_status["google_sheets"] = {
                    "status": "healthy",
                    "test_result": f"연결 성공: {test_result['workbook_title']}"
                }
            else:
                components_status["google_sheets"] = {
                    "status": "unhealthy",
                    "error": test_result.get("error", "연결 실패")
                }
        except Exception as e:
            components_status["google_sheets"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Slack 검증
        try:
            slack_notifier = SlackNotifier()
            if slack_notifier.webhook_url:
                components_status["slack"] = {
                    "status": "healthy",
                    "test_result": "웹훅 URL 설정됨"
                }
            else:
                components_status["slack"] = {
                    "status": "degraded",
                    "note": "웹훅 URL 미설정 (선택사항)"
                }
        except Exception as e:
            components_status["slack"] = {
                "status": "degraded",
                "error": str(e)
            }
        
        self.results["components"].update(components_status)
        
        # 상태 확인
        unhealthy_components = [name for name, info in components_status.items() 
                              if info["status"] == "unhealthy"]
        
        if unhealthy_components:
            print(f"❌ 문제가 있는 컴포넌트: {unhealthy_components}")
            return False
        
        print("✅ API 컴포넌트 검증 완료")
        return True
    
    def verify_services(self) -> bool:
        """실행 중인 서비스들 검증"""
        print("🔍 서비스 상태 검증 중...")
        
        services_status = {}
        
        # API 서버 확인
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                services_status["api_server"] = {
                    "status": "healthy",
                    "url": self.api_base_url,
                    "health_data": health_data
                }
            else:
                services_status["api_server"] = {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            services_status["api_server"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Streamlit 대시보드 확인
        try:
            response = requests.get(self.dashboard_url, timeout=5)
            if response.status_code == 200:
                services_status["dashboard"] = {
                    "status": "healthy",
                    "url": self.dashboard_url
                }
            else:
                services_status["dashboard"] = {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            services_status["dashboard"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # n8n 확인
        try:
            response = requests.get(f"{self.n8n_url}/rest/active", timeout=5)
            services_status["n8n"] = {
                "status": "healthy" if response.status_code == 200 else "degraded",
                "url": self.n8n_url
            }
        except Exception as e:
            services_status["n8n"] = {
                "status": "degraded",
                "error": str(e),
                "note": "n8n이 실행되지 않았을 수 있습니다"
            }
        
        self.results["components"]["services"] = services_status
        
        # 핵심 서비스 확인
        critical_services = ["api_server", "dashboard"]
        unhealthy_critical = [name for name in critical_services 
                            if services_status.get(name, {}).get("status") == "unhealthy"]
        
        if unhealthy_critical:
            self.results["critical_issues"].append(f"핵심 서비스 문제: {unhealthy_critical}")
            print(f"❌ 핵심 서비스 문제: {unhealthy_critical}")
            return False
        
        print("✅ 서비스 상태 검증 완료")
        return True
    
    def run_end_to_end_test(self) -> bool:
        """End-to-End 테스트 실행"""
        print("🚀 End-to-End 테스트 시작...")
        
        test_results = {}
        
        # 1. API 서버 헬스체크
        try:
            response = requests.get(f"{self.api_base_url}/health")
            test_results["api_health"] = {
                "passed": response.status_code == 200,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            test_results["api_health"] = {
                "passed": False,
                "error": str(e)
            }
        
        # 2. 채널 목록 API 테스트
        try:
            response = requests.post(
                f"{self.api_base_url}/rss/collect",
                json={
                    "channels": [
                        {
                            "channel_id": "UCXuqSBlHAE6Xw-yeJA0Tunw",
                            "channel_name": "Linus Tech Tips",
                            "channel_type": "tech",
                            "celebrity_name": "Linus Sebastian"
                        }
                    ],
                    "session_id": "e2e_test",
                    "days_back": 1
                },
                timeout=30
            )
            test_results["rss_collection"] = {
                "passed": response.status_code == 200,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            test_results["rss_collection"] = {
                "passed": False,
                "error": str(e)
            }
        
        # 3. 데이터베이스 연결 테스트
        try:
            db_manager = get_database_manager()
            candidates = db_manager.get_all_candidates(limit=1)
            test_results["database"] = {
                "passed": True,
                "candidates_count": len(candidates)
            }
        except Exception as e:
            test_results["database"] = {
                "passed": False,
                "error": str(e)
            }
        
        self.results["end_to_end_tests"] = test_results
        
        # 통과한 테스트 개수 확인
        passed_tests = sum(1 for test in test_results.values() if test.get("passed", False))
        total_tests = len(test_results)
        
        print(f"📊 E2E 테스트 결과: {passed_tests}/{total_tests} 통과")
        
        return passed_tests == total_tests
    
    def calculate_readiness_score(self) -> int:
        """운영 준비도 점수 계산 (0-100)"""
        score = 0
        max_score = 100
        
        # 환경변수 (20점)
        env_status = self.results["components"].get("environment", {})
        if env_status.get("status") == "healthy":
            score += 20
        elif not env_status.get("missing_required", []):
            score += 15
        
        # API 컴포넌트 (30점)
        api_components = ["youtube_api", "gemini_api", "google_sheets"]
        healthy_apis = sum(1 for comp in api_components 
                          if self.results["components"].get(comp, {}).get("status") == "healthy")
        score += int((healthy_apis / len(api_components)) * 30)
        
        # 서비스 (30점)
        services = self.results["components"].get("services", {})
        critical_services = ["api_server", "dashboard"]
        healthy_services = sum(1 for service in critical_services
                             if services.get(service, {}).get("status") == "healthy")
        score += int((healthy_services / len(critical_services)) * 30)
        
        # E2E 테스트 (20점)
        e2e_tests = self.results.get("end_to_end_tests", {})
        if e2e_tests:
            passed_tests = sum(1 for test in e2e_tests.values() if test.get("passed", False))
            total_tests = len(e2e_tests)
            score += int((passed_tests / total_tests) * 20)
        
        return min(score, max_score)
    
    def generate_recommendations(self):
        """권장사항 생성"""
        recommendations = []
        
        # 환경변수 관련
        env_status = self.results["components"].get("environment", {})
        if env_status.get("missing_required"):
            recommendations.append("필수 환경변수를 설정하세요: " + ", ".join(env_status["missing_required"]))
        
        if env_status.get("missing_optional"):
            recommendations.append("선택적 환경변수 설정을 고려하세요: " + ", ".join(env_status["missing_optional"]))
        
        # API 컴포넌트 관련
        for comp_name, comp_info in self.results["components"].items():
            if isinstance(comp_info, dict) and comp_info.get("status") == "unhealthy":
                if "error" in comp_info:
                    recommendations.append(f"{comp_name} 문제 해결 필요: {comp_info['error']}")
        
        # 서비스 관련
        services = self.results["components"].get("services", {})
        for service_name, service_info in services.items():
            if service_info.get("status") == "unhealthy":
                recommendations.append(f"{service_name} 서비스를 시작하거나 재시작하세요")
        
        # 점수 기반 권장사항
        if self.results["readiness_score"] < 70:
            recommendations.append("운영 환경 배포 전에 모든 컴포넌트를 수정하세요")
        elif self.results["readiness_score"] < 90:
            recommendations.append("일부 개선사항이 있지만 운영 배포가 가능합니다")
        
        self.results["recommendations"] = recommendations
    
    def run_verification(self) -> Dict:
        """전체 검증 실행"""
        print("🔥 연예인 추천 아이템 자동화 시스템 v1.0 최종 검증")
        print("=" * 60)
        
        # 단계별 검증
        steps = [
            ("환경변수", self.verify_environment_variables),
            ("API 컴포넌트", self.verify_api_components),
            ("서비스 상태", self.verify_services),
            ("End-to-End 테스트", self.run_end_to_end_test)
        ]
        
        all_passed = True
        
        for step_name, step_func in steps:
            print(f"\n📋 {step_name} 검증 중...")
            try:
                result = step_func()
                if not result:
                    all_passed = False
                    print(f"❌ {step_name} 검증 실패")
                else:
                    print(f"✅ {step_name} 검증 성공")
            except Exception as e:
                all_passed = False
                print(f"❌ {step_name} 검증 오류: {e}")
                self.results["critical_issues"].append(f"{step_name} 검증 오류: {str(e)}")
        
        # 최종 점수 및 상태 결정
        self.results["readiness_score"] = self.calculate_readiness_score()
        
        if all_passed and self.results["readiness_score"] >= 90:
            self.results["overall_status"] = "ready"
        elif self.results["readiness_score"] >= 70:
            self.results["overall_status"] = "mostly_ready"
        else:
            self.results["overall_status"] = "not_ready"
        
        # 권장사항 생성
        self.generate_recommendations()
        
        return self.results
    
    def print_final_report(self):
        """최종 보고서 출력"""
        print("\n" + "=" * 60)
        print("📋 최종 시스템 검증 보고서")
        print("=" * 60)
        
        # 전체 상태
        status_emoji = {
            "ready": "🎉",
            "mostly_ready": "⚠️",
            "not_ready": "❌"
        }
        status_text = {
            "ready": "운영 준비 완료",
            "mostly_ready": "운영 준비 거의 완료",
            "not_ready": "운영 준비 미완료"
        }
        
        print(f"\n{status_emoji.get(self.results['overall_status'], '❓')} "
              f"전체 상태: {status_text.get(self.results['overall_status'], 'Unknown')}")
        print(f"🎯 준비도 점수: {self.results['readiness_score']}/100")
        
        # 중요 이슈
        if self.results["critical_issues"]:
            print(f"\n🚨 중요 이슈 ({len(self.results['critical_issues'])}개):")
            for issue in self.results["critical_issues"]:
                print(f"   • {issue}")
        
        # 권장사항
        if self.results["recommendations"]:
            print(f"\n💡 권장사항 ({len(self.results['recommendations'])}개):")
            for rec in self.results["recommendations"]:
                print(f"   • {rec}")
        
        # 컴포넌트 상태 요약
        print(f"\n📊 컴포넌트 상태 요약:")
        for comp_name, comp_info in self.results["components"].items():
            if isinstance(comp_info, dict):
                if comp_name == "environment":
                    status = comp_info.get("status", "unknown")
                    print(f"   • 환경변수: {status}")
                elif comp_name == "services":
                    for service_name, service_info in comp_info.items():
                        status = service_info.get("status", "unknown")
                        print(f"   • {service_name}: {status}")
                else:
                    status = comp_info.get("status", "unknown")
                    print(f"   • {comp_name}: {status}")
        
        # 다음 단계
        print(f"\n🚀 다음 단계:")
        if self.results["overall_status"] == "ready":
            print("   ✅ 내일 아침 7시 자동 실행이 완벽하게 준비되었습니다!")
            print("   📋 n8n 워크플로우를 활성화하여 24/7 자동화를 시작하세요.")
            print("   📊 Slack에서 알림을 받고 Google Sheets에서 결과를 확인하세요.")
        elif self.results["overall_status"] == "mostly_ready":
            print("   ⚠️  대부분 준비되었지만 일부 개선이 필요합니다.")
            print("   🔧 위의 권장사항을 적용한 후 재테스트하세요.")
        else:
            print("   ❌ 중요한 문제들을 해결한 후 다시 테스트하세요.")
            print("   📖 PRD 문서와 설정 가이드를 참조하세요.")
        
        print("\n" + "=" * 60)


def main():
    """메인 실행 함수"""
    verifier = SystemVerifier()
    
    try:
        # 검증 실행
        results = verifier.run_verification()
        
        # 보고서 출력
        verifier.print_final_report()
        
        # 결과 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = project_root / f"final_verification_report_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 상세 보고서 저장됨: {results_file}")
        
        # 스크린샷 저장
        screenshot_dir = project_root / "screenshot"
        screenshot_dir.mkdir(exist_ok=True)
        
        screenshot_file = screenshot_dir / f"final_system_status_{timestamp}.md"
        with open(screenshot_file, 'w', encoding='utf-8') as f:
            f.write(f"# 최종 시스템 검증 보고서\n\n")
            f.write(f"**검증 시간:** {results['timestamp']}\n")
            f.write(f"**전체 상태:** {results['overall_status']}\n")
            f.write(f"**준비도 점수:** {results['readiness_score']}/100\n\n")
            
            if results["critical_issues"]:
                f.write("## 중요 이슈\n\n")
                for issue in results["critical_issues"]:
                    f.write(f"- {issue}\n")
                f.write("\n")
            
            if results["recommendations"]:
                f.write("## 권장사항\n\n")
                for rec in results["recommendations"]:
                    f.write(f"- {rec}\n")
                f.write("\n")
            
            f.write("## 상세 결과\n\n")
            f.write(f"```json\n{json.dumps(results, indent=2, ensure_ascii=False)}\n```\n")
        
        print(f"📸 스크린샷 저장됨: {screenshot_file}")
        
        # 종료 코드 결정
        if results["overall_status"] == "ready":
            sys.exit(0)
        elif results["overall_status"] == "mostly_ready":
            sys.exit(1)
        else:
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  검증이 중단되었습니다.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 검증 중 오류 발생: {e}")
        logger.exception("검증 오류")
        sys.exit(1)


if __name__ == "__main__":
    main()