#!/usr/bin/env python3
"""
자동 롤백 시스템

배포 실패 시 자동으로 이전 버전으로 롤백하는 시스템
"""

import os
import sys
import time
import json
import logging
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutomatedRollback:
    def __init__(self):
        self.namespace = "influence-item"
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.services = {
            "cpu-server": {
                "deployment": "cpu-server",
                "health_endpoint": "http://cpu-service:8501/_stcore/health",
                "rollout": "cpu-server-rollout"
            },
            "gpu-server": {
                "deployment": "gpu-server", 
                "health_endpoint": "http://gpu-service:8001/health",
                "rollout": None
            }
        }
        
    def run_kubectl_command(self, command: List[str]) -> Tuple[bool, str]:
        """kubectl 명령어 실행"""
        try:
            result = subprocess.run(
                ["kubectl"] + command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"kubectl 명령어 타임아웃: {' '.join(command)}")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"kubectl 명령어 실행 실패: {e}")
            return False, str(e)
    
    def get_deployment_status(self, service_name: str) -> Dict:
        """배포 상태 확인"""
        deployment = self.services[service_name]["deployment"]
        
        # 배포 상태 조회
        success, output = self.run_kubectl_command([
            "get", "deployment", deployment,
            "-n", self.namespace,
            "-o", "json"
        ])
        
        if not success:
            return {"status": "error", "message": output}
        
        try:
            deployment_data = json.loads(output)
            status = deployment_data["status"]
            
            return {
                "status": "ready" if status.get("readyReplicas", 0) == status.get("replicas", 0) else "not_ready",
                "ready_replicas": status.get("readyReplicas", 0),
                "replicas": status.get("replicas", 0),
                "unavailable_replicas": status.get("unavailableReplicas", 0),
                "conditions": status.get("conditions", [])
            }
        except json.JSONDecodeError as e:
            logger.error(f"배포 상태 파싱 실패: {e}")
            return {"status": "error", "message": "JSON 파싱 실패"}
    
    def check_service_health(self, service_name: str) -> bool:
        """서비스 헬스체크"""
        endpoint = self.services[service_name]["health_endpoint"]
        
        try:
            # Kubernetes 내부에서 curl을 사용한 헬스체크
            success, _ = self.run_kubectl_command([
                "run", "health-check-temp",
                "--image=curlimages/curl:latest",
                "--rm", "-i", "--restart=Never",
                "-n", self.namespace,
                "--", "curl", "-f", endpoint
            ])
            return success
        except Exception as e:
            logger.error(f"헬스체크 실패 ({service_name}): {e}")
            return False
    
    def get_rollout_status(self, service_name: str) -> Dict:
        """Argo Rollout 상태 확인"""
        rollout = self.services[service_name].get("rollout")
        if not rollout:
            return {"status": "no_rollout"}
        
        success, output = self.run_kubectl_command([
            "argo", "rollouts", "get", "rollout", rollout,
            "-n", self.namespace,
            "-o", "json"
        ])
        
        if not success:
            return {"status": "error", "message": output}
        
        try:
            rollout_data = json.loads(output)
            return {
                "status": rollout_data["status"]["phase"],
                "current_step": rollout_data["status"].get("currentStepIndex", 0),
                "message": rollout_data["status"].get("message", "")
            }
        except json.JSONDecodeError as e:
            logger.error(f"롤아웃 상태 파싱 실패: {e}")
            return {"status": "error", "message": "JSON 파싱 실패"}
    
    def rollback_deployment(self, service_name: str) -> bool:
        """배포 롤백 실행"""
        deployment = self.services[service_name]["deployment"]
        rollout = self.services[service_name].get("rollout")
        
        logger.info(f"{service_name} 롤백 시작...")
        
        if rollout:
            # Argo Rollout 사용하는 경우
            success, output = self.run_kubectl_command([
                "argo", "rollouts", "abort", rollout,
                "-n", self.namespace
            ])
            
            if success:
                success, output = self.run_kubectl_command([
                    "argo", "rollouts", "undo", rollout,
                    "-n", self.namespace
                ])
        else:
            # 일반 Deployment 롤백
            success, output = self.run_kubectl_command([
                "rollout", "undo", f"deployment/{deployment}",
                "-n", self.namespace
            ])
        
        if success:
            logger.info(f"{service_name} 롤백 명령 성공")
            return self.wait_for_rollback_completion(service_name)
        else:
            logger.error(f"{service_name} 롤백 명령 실패: {output}")
            return False
    
    def wait_for_rollback_completion(self, service_name: str, timeout: int = 300) -> bool:
        """롤백 완료 대기"""
        start_time = time.time()
        deployment = self.services[service_name]["deployment"]
        
        while time.time() - start_time < timeout:
            # 배포 상태 확인
            success, _ = self.run_kubectl_command([
                "rollout", "status", f"deployment/{deployment}",
                "-n", self.namespace,
                "--timeout=30s"
            ])
            
            if success:
                # 헬스체크 확인
                if self.check_service_health(service_name):
                    logger.info(f"{service_name} 롤백 완료 및 헬스체크 성공")
                    return True
                else:
                    logger.warning(f"{service_name} 롤백 완료되었지만 헬스체크 실패")
            
            time.sleep(10)
        
        logger.error(f"{service_name} 롤백 타임아웃")
        return False
    
    def send_slack_notification(self, message: str, color: str = "danger"):
        """슬랙 알림 전송"""
        if not self.slack_webhook:
            logger.warning("슬랙 웹훅이 설정되지 않음")
            return
        
        payload = {
            "attachments": [{
                "color": color,
                "title": "🔄 자동 롤백 시스템",
                "text": message,
                "timestamp": time.time()
            }]
        }
        
        try:
            response = requests.post(self.slack_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("슬랙 알림 전송 성공")
            else:
                logger.error(f"슬랙 알림 전송 실패: {response.status_code}")
        except Exception as e:
            logger.error(f"슬랙 알림 전송 예외: {e}")
    
    def detect_deployment_issues(self) -> List[str]:
        """배포 이슈 감지"""
        failed_services = []
        
        for service_name in self.services.keys():
            logger.info(f"{service_name} 상태 확인 중...")
            
            # 배포 상태 확인
            deployment_status = self.get_deployment_status(service_name)
            if deployment_status["status"] == "error":
                logger.error(f"{service_name} 배포 상태 조회 실패: {deployment_status['message']}")
                failed_services.append(service_name)
                continue
            
            if deployment_status["status"] != "ready":
                logger.warning(f"{service_name} 배포가 Ready 상태가 아님")
                failed_services.append(service_name)
                continue
            
            # 헬스체크 확인
            if not self.check_service_health(service_name):
                logger.error(f"{service_name} 헬스체크 실패")
                failed_services.append(service_name)
                continue
            
            # Rollout 상태 확인 (해당하는 경우)
            rollout_status = self.get_rollout_status(service_name)
            if rollout_status["status"] == "Degraded":
                logger.error(f"{service_name} 롤아웃 상태가 Degraded")
                failed_services.append(service_name)
                continue
            
            logger.info(f"{service_name} 정상 상태")
        
        return failed_services
    
    def execute_rollback(self, failed_services: List[str]) -> Dict[str, bool]:
        """롤백 실행"""
        rollback_results = {}
        
        for service_name in failed_services:
            logger.info(f"{service_name} 롤백 시작...")
            
            # 롤백 알림
            self.send_slack_notification(
                f"🚨 {service_name} 서비스에서 이슈 감지, 자동 롤백을 시작합니다.",
                color="warning"
            )
            
            # 롤백 실행
            success = self.rollback_deployment(service_name)
            rollback_results[service_name] = success
            
            if success:
                self.send_slack_notification(
                    f"✅ {service_name} 서비스 롤백이 성공적으로 완료되었습니다.",
                    color="good"
                )
            else:
                self.send_slack_notification(
                    f"❌ {service_name} 서비스 롤백이 실패했습니다. 수동 개입이 필요합니다.",
                    color="danger"
                )
        
        return rollback_results
    
    def run_monitoring_cycle(self):
        """모니터링 사이클 실행"""
        logger.info("자동 롤백 시스템 모니터링 시작")
        
        # 배포 이슈 감지
        failed_services = self.detect_deployment_issues()
        
        if not failed_services:
            logger.info("모든 서비스가 정상 상태입니다")
            return {"status": "healthy"}
        
        logger.warning(f"이슈 감지된 서비스: {failed_services}")
        
        # 롤백 실행
        rollback_results = self.execute_rollback(failed_services)
        
        # 결과 요약
        successful_rollbacks = [k for k, v in rollback_results.items() if v]
        failed_rollbacks = [k for k, v in rollback_results.items() if not v]
        
        result = {
            "status": "rollback_executed",
            "failed_services": failed_services,
            "successful_rollbacks": successful_rollbacks,
            "failed_rollbacks": failed_rollbacks
        }
        
        # 최종 상태 알림
        if failed_rollbacks:
            self.send_slack_notification(
                f"⚠️ 일부 서비스의 롤백이 실패했습니다: {', '.join(failed_rollbacks)}\n"
                f"수동 개입이 필요합니다.",
                color="danger"
            )
        else:
            self.send_slack_notification(
                f"✅ 모든 문제 서비스의 롤백이 성공적으로 완료되었습니다: {', '.join(successful_rollbacks)}",
                color="good"
            )
        
        return result

def main():
    """메인 함수"""
    rollback_system = AutomatedRollback()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        # 연속 모니터링 모드
        logger.info("연속 모니터링 모드 시작")
        while True:
            try:
                rollback_system.run_monitoring_cycle()
                time.sleep(60)  # 1분 간격
            except KeyboardInterrupt:
                logger.info("모니터링 중단")
                break
            except Exception as e:
                logger.error(f"모니터링 사이클 오류: {e}")
                time.sleep(30)
    else:
        # 단일 실행 모드
        result = rollback_system.run_monitoring_cycle()
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()