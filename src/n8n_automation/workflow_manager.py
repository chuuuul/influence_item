#!/usr/bin/env python3
"""
n8n 워크플로우 완전 자동화 및 에러 복구 시스템

워크플로우 모니터링, 자동 복구, 성능 최적화, 스케줄링 관리
"""

import os
import json
import asyncio
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

import requests
from src.notifications.alert_manager import send_warning_alert, send_critical_alert, send_info_alert
from src.config.config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    """워크플로우 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class WorkflowType(Enum):
    """워크플로우 타입"""
    RSS_COLLECTION = "rss_collection"
    CHANNEL_DISCOVERY = "channel_discovery"
    AI_ANALYSIS = "ai_analysis"
    HISTORICAL_ANALYSIS = "historical_analysis"
    NOTIFICATION = "notification"
    MONITORING = "monitoring"
    BACKUP = "backup"

@dataclass
class WorkflowExecution:
    """워크플로우 실행 데이터"""
    workflow_id: str
    execution_id: str
    status: WorkflowStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    error_message: Optional[str]
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    retry_count: int = 0
    
    @property
    def is_successful(self) -> bool:
        return self.status == WorkflowStatus.SUCCESS
    
    @property
    def is_failed(self) -> bool:
        return self.status == WorkflowStatus.FAILED
    
    @property
    def is_running(self) -> bool:
        return self.status in [WorkflowStatus.RUNNING, WorkflowStatus.WAITING]

@dataclass
class WorkflowMetrics:
    """워크플로우 메트릭"""
    workflow_id: str
    workflow_name: str
    workflow_type: WorkflowType
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration: float
    last_execution: Optional[datetime]
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    success_rate: float
    
    @property
    def failure_rate(self) -> float:
        return 100.0 - self.success_rate

class N8nAPIClient:
    """n8n API 클라이언트"""
    
    def __init__(self):
        self.base_url = os.getenv("N8N_API_URL", "http://n8n:5678")
        self.auth_token = os.getenv("N8N_API_TOKEN")
        self.username = os.getenv("N8N_USER")
        self.password = os.getenv("N8N_PASSWORD")
        self.session = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 생성"""
        if self.session is None:
            headers = {}
            
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            # Basic Auth 로그인 (토큰이 없는 경우)
            if not self.auth_token and self.username and self.password:
                await self.login()
        
        return self.session
    
    async def login(self):
        """n8n 로그인"""
        try:
            login_data = {
                "email": self.username,
                "password": self.password
            }
            
            async with self.session.post(f"{self.base_url}/rest/login", json=login_data) as response:
                if response.status == 200:
                    logger.info("n8n 로그인 성공")
                else:
                    logger.error(f"n8n 로그인 실패: {response.status}")
        except Exception as e:
            logger.error(f"n8n 로그인 예외: {e}")
    
    async def get_workflows(self) -> List[Dict[str, Any]]:
        """워크플로우 목록 조회"""
        try:
            session = await self.get_session()
            async with session.get(f"{self.base_url}/rest/workflows") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.error(f"워크플로우 목록 조회 실패: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"워크플로우 목록 조회 예외: {e}")
            return []
    
    async def get_workflow_executions(self, workflow_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """워크플로우 실행 내역 조회"""
        try:
            session = await self.get_session()
            params = {
                "filter": json.dumps({"workflowId": workflow_id}),
                "limit": limit,
                "includeData": "true"
            }
            
            async with session.get(f"{self.base_url}/rest/executions", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.error(f"실행 내역 조회 실패: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"실행 내역 조회 예외: {e}")
            return []
    
    async def trigger_workflow(self, workflow_id: str, input_data: Dict[str, Any] = None) -> Optional[str]:
        """워크플로우 실행 트리거"""
        try:
            session = await self.get_session()
            
            trigger_data = input_data or {}
            
            async with session.post(
                f"{self.base_url}/rest/workflows/{workflow_id}/activate",
                json=trigger_data
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    return data.get("data", {}).get("id")
                else:
                    logger.error(f"워크플로우 트리거 실패: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"워크플로우 트리거 예외: {e}")
            return None
    
    async def stop_execution(self, execution_id: str) -> bool:
        """실행 중지"""
        try:
            session = await self.get_session()
            
            async with session.post(f"{self.base_url}/rest/executions/{execution_id}/stop") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"실행 중지 예외: {e}")
            return False
    
    async def retry_execution(self, execution_id: str) -> Optional[str]:
        """실행 재시도"""
        try:
            session = await self.get_session()
            
            async with session.post(f"{self.base_url}/rest/executions/{execution_id}/retry") as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    return data.get("data", {}).get("id")
                else:
                    logger.error(f"실행 재시도 실패: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"실행 재시도 예외: {e}")
            return None
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """워크플로우 상태 조회"""
        try:
            session = await self.get_session()
            
            async with session.get(f"{self.base_url}/rest/workflows/{workflow_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"워크플로우 상태 조회 실패: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"워크플로우 상태 조회 예외: {e}")
            return {}
    
    async def activate_workflow(self, workflow_id: str) -> bool:
        """워크플로우 활성화"""
        try:
            session = await self.get_session()
            
            async with session.patch(
                f"{self.base_url}/rest/workflows/{workflow_id}",
                json={"active": True}
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"워크플로우 활성화 예외: {e}")
            return False
    
    async def deactivate_workflow(self, workflow_id: str) -> bool:
        """워크플로우 비활성화"""
        try:
            session = await self.get_session()
            
            async with session.patch(
                f"{self.base_url}/rest/workflows/{workflow_id}",
                json={"active": False}
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"워크플로우 비활성화 예외: {e}")
            return False
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()

class WorkflowMonitor:
    """워크플로우 모니터링"""
    
    def __init__(self):
        self.client = N8nAPIClient()
        self.metrics_file = Path("data/workflow_metrics.json")
        self.metrics_file.parent.mkdir(exist_ok=True)
        
        # 워크플로우 타입 매핑
        self.workflow_types = {
            "daily_rss_collection": WorkflowType.RSS_COLLECTION,
            "channel_discovery": WorkflowType.CHANNEL_DISCOVERY,
            "ai_analysis_pipeline": WorkflowType.AI_ANALYSIS,
            "historical_video_analysis": WorkflowType.HISTORICAL_ANALYSIS,
            "notification_routing": WorkflowType.NOTIFICATION,
            "monitoring_workflow": WorkflowType.MONITORING,
            "backup_workflow": WorkflowType.BACKUP
        }
    
    def load_metrics(self) -> Dict[str, Any]:
        """메트릭 데이터 로드"""
        if not self.metrics_file.exists():
            return {"workflows": {}, "executions": []}
        
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"메트릭 데이터 로드 실패: {e}")
            return {"workflows": {}, "executions": []}
    
    def save_metrics(self, data: Dict[str, Any]):
        """메트릭 데이터 저장"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"메트릭 데이터 저장 실패: {e}")
    
    async def collect_workflow_metrics(self) -> List[WorkflowMetrics]:
        """워크플로우 메트릭 수집"""
        workflows = await self.client.get_workflows()
        metrics_list = []
        
        for workflow in workflows:
            workflow_id = workflow.get("id")
            workflow_name = workflow.get("name", "Unknown")
            
            if not workflow_id:
                continue
            
            # 실행 내역 조회
            executions = await self.client.get_workflow_executions(workflow_id)
            
            if not executions:
                continue
            
            # 메트릭 계산
            total_executions = len(executions)
            successful_executions = len([e for e in executions if e.get("finished") and not e.get("stoppedAt")])
            failed_executions = total_executions - successful_executions
            
            success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
            
            # 평균 실행 시간 계산
            durations = []
            for execution in executions:
                if execution.get("startedAt") and execution.get("stoppedAt"):
                    start = datetime.fromisoformat(execution["startedAt"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(execution["stoppedAt"].replace("Z", "+00:00"))
                    durations.append((end - start).total_seconds())
            
            average_duration = sum(durations) / len(durations) if durations else 0
            
            # 최근 실행 시간
            last_execution = None
            last_success = None
            last_failure = None
            
            for execution in executions:
                exec_time = datetime.fromisoformat(execution["startedAt"].replace("Z", "+00:00"))
                
                if last_execution is None or exec_time > last_execution:
                    last_execution = exec_time
                
                if execution.get("finished") and not execution.get("stoppedAt"):
                    if last_success is None or exec_time > last_success:
                        last_success = exec_time
                else:
                    if last_failure is None or exec_time > last_failure:
                        last_failure = exec_time
            
            # 워크플로우 타입 결정
            workflow_type = WorkflowType.MONITORING  # 기본값
            for name_pattern, wf_type in self.workflow_types.items():
                if name_pattern.lower() in workflow_name.lower():
                    workflow_type = wf_type
                    break
            
            metrics = WorkflowMetrics(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                workflow_type=workflow_type,
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_duration=average_duration,
                last_execution=last_execution,
                last_success=last_success,
                last_failure=last_failure,
                success_rate=success_rate
            )
            
            metrics_list.append(metrics)
        
        return metrics_list
    
    async def analyze_workflow_health(self, metrics: List[WorkflowMetrics]) -> List[Dict[str, Any]]:
        """워크플로우 건강 상태 분석"""
        issues = []
        
        for metric in metrics:
            # 성공률 체크
            if metric.success_rate < 50:
                issues.append({
                    "type": "low_success_rate",
                    "severity": "critical",
                    "workflow_id": metric.workflow_id,
                    "workflow_name": metric.workflow_name,
                    "success_rate": metric.success_rate,
                    "message": f"워크플로우 성공률이 매우 낮습니다: {metric.success_rate:.1f}%"
                })
            elif metric.success_rate < 80:
                issues.append({
                    "type": "moderate_success_rate",
                    "severity": "warning",
                    "workflow_id": metric.workflow_id,
                    "workflow_name": metric.workflow_name,
                    "success_rate": metric.success_rate,
                    "message": f"워크플로우 성공률이 낮습니다: {metric.success_rate:.1f}%"
                })
            
            # 최근 실행 체크
            if metric.last_execution:
                time_since_last = datetime.now() - metric.last_execution.replace(tzinfo=None)
                if time_since_last > timedelta(hours=24):
                    issues.append({
                        "type": "stale_workflow",
                        "severity": "warning",
                        "workflow_id": metric.workflow_id,
                        "workflow_name": metric.workflow_name,
                        "last_execution": metric.last_execution,
                        "message": f"워크플로우가 24시간 이상 실행되지 않았습니다"
                    })
            
            # 실행 시간 체크
            if metric.average_duration > 300:  # 5분 이상
                issues.append({
                    "type": "slow_execution",
                    "severity": "info",
                    "workflow_id": metric.workflow_id,
                    "workflow_name": metric.workflow_name,
                    "average_duration": metric.average_duration,
                    "message": f"워크플로우 실행 시간이 길습니다: {metric.average_duration:.1f}초"
                })
            
            # 최근 실패 체크
            if metric.last_failure and metric.last_success:
                if metric.last_failure > metric.last_success:
                    issues.append({
                        "type": "recent_failure",
                        "severity": "warning",
                        "workflow_id": metric.workflow_id,
                        "workflow_name": metric.workflow_name,
                        "last_failure": metric.last_failure,
                        "message": f"최근 실행이 실패했습니다"
                    })
        
        return issues

class WorkflowRecovery:
    """워크플로우 자동 복구"""
    
    def __init__(self):
        self.client = N8nAPIClient()
        self.recovery_strategies = {
            "low_success_rate": self.recover_low_success_rate,
            "stale_workflow": self.recover_stale_workflow,
            "recent_failure": self.recover_recent_failure,
            "execution_timeout": self.recover_execution_timeout
        }
        self.max_retry_attempts = 3
        self.retry_delay = 60  # 초
    
    async def execute_recovery(self, issues: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """복구 실행"""
        recovery_results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        for issue in issues:
            issue_type = issue.get("type")
            severity = issue.get("severity", "info")
            
            # 심각도가 낮은 이슈는 건너뛰기
            if severity == "info":
                recovery_results["skipped"].append(f"{issue['workflow_name']}: {issue['message']}")
                continue
            
            if issue_type in self.recovery_strategies:
                try:
                    success = await self.recovery_strategies[issue_type](issue)
                    if success:
                        recovery_results["successful"].append(f"{issue['workflow_name']}: {issue_type} 복구 성공")
                    else:
                        recovery_results["failed"].append(f"{issue['workflow_name']}: {issue_type} 복구 실패")
                except Exception as e:
                    logger.error(f"복구 실행 오류 ({issue_type}): {e}")
                    recovery_results["failed"].append(f"{issue['workflow_name']}: {issue_type} 복구 예외 - {e}")
            else:
                recovery_results["skipped"].append(f"{issue['workflow_name']}: {issue_type} - 복구 전략 없음")
        
        return recovery_results
    
    async def recover_low_success_rate(self, issue: Dict[str, Any]) -> bool:
        """낮은 성공률 복구"""
        workflow_id = issue["workflow_id"]
        
        try:
            # 1. 워크플로우 비활성화
            await self.client.deactivate_workflow(workflow_id)
            await asyncio.sleep(5)
            
            # 2. 다시 활성화
            success = await self.client.activate_workflow(workflow_id)
            
            if success:
                logger.info(f"워크플로우 재시작 완료: {issue['workflow_name']}")
                
                await send_info_alert(
                    "워크플로우 자동 복구",
                    f"성공률이 낮은 워크플로우를 재시작했습니다: {issue['workflow_name']}",
                    service="n8n_automation",
                    workflow_id=workflow_id,
                    recovery_action="restart"
                )
                
                return True
            
        except Exception as e:
            logger.error(f"낮은 성공률 복구 실패: {e}")
        
        return False
    
    async def recover_stale_workflow(self, issue: Dict[str, Any]) -> bool:
        """오래된 워크플로우 복구"""
        workflow_id = issue["workflow_id"]
        
        try:
            # 워크플로우 상태 확인
            status = await self.client.get_workflow_status(workflow_id)
            
            if not status.get("active", False):
                # 비활성화된 경우 활성화
                success = await self.client.activate_workflow(workflow_id)
                
                if success:
                    logger.info(f"비활성화된 워크플로우 활성화: {issue['workflow_name']}")
                    
                    await send_info_alert(
                        "워크플로우 자동 활성화",
                        f"비활성화된 워크플로우를 활성화했습니다: {issue['workflow_name']}",
                        service="n8n_automation",
                        workflow_id=workflow_id,
                        recovery_action="activate"
                    )
                    
                    return True
            else:
                # 수동 트리거 시도
                execution_id = await self.client.trigger_workflow(workflow_id)
                
                if execution_id:
                    logger.info(f"워크플로우 수동 트리거 완료: {issue['workflow_name']}")
                    
                    await send_info_alert(
                        "워크플로우 수동 트리거",
                        f"오래된 워크플로우를 수동으로 트리거했습니다: {issue['workflow_name']}",
                        service="n8n_automation",
                        workflow_id=workflow_id,
                        execution_id=execution_id,
                        recovery_action="manual_trigger"
                    )
                    
                    return True
        
        except Exception as e:
            logger.error(f"오래된 워크플로우 복구 실패: {e}")
        
        return False
    
    async def recover_recent_failure(self, issue: Dict[str, Any]) -> bool:
        """최근 실패 복구"""
        workflow_id = issue["workflow_id"]
        
        try:
            # 최근 실행 내역 조회
            executions = await self.client.get_workflow_executions(workflow_id, limit=1)
            
            if executions:
                last_execution = executions[0]
                execution_id = last_execution.get("id")
                
                if execution_id and not last_execution.get("finished"):
                    # 실행 중인 경우 중지 후 재시도
                    await self.client.stop_execution(execution_id)
                    await asyncio.sleep(10)
                
                # 재시도
                new_execution_id = await self.client.retry_execution(execution_id)
                
                if new_execution_id:
                    logger.info(f"워크플로우 재시도 완료: {issue['workflow_name']}")
                    
                    await send_info_alert(
                        "워크플로우 자동 재시도",
                        f"실패한 워크플로우를 재시도했습니다: {issue['workflow_name']}",
                        service="n8n_automation",
                        workflow_id=workflow_id,
                        execution_id=new_execution_id,
                        recovery_action="retry"
                    )
                    
                    return True
        
        except Exception as e:
            logger.error(f"최근 실패 복구 실패: {e}")
        
        return False
    
    async def recover_execution_timeout(self, issue: Dict[str, Any]) -> bool:
        """실행 타임아웃 복구"""
        workflow_id = issue["workflow_id"]
        execution_id = issue.get("execution_id")
        
        if not execution_id:
            return False
        
        try:
            # 실행 중지
            stopped = await self.client.stop_execution(execution_id)
            
            if stopped:
                await asyncio.sleep(5)
                
                # 새로운 실행 시작
                new_execution_id = await self.client.trigger_workflow(workflow_id)
                
                if new_execution_id:
                    logger.info(f"타임아웃 워크플로우 복구 완료: {issue['workflow_name']}")
                    
                    await send_warning_alert(
                        "워크플로우 타임아웃 복구",
                        f"타임아웃된 워크플로우를 중지하고 재시작했습니다: {issue['workflow_name']}",
                        service="n8n_automation",
                        workflow_id=workflow_id,
                        old_execution_id=execution_id,
                        new_execution_id=new_execution_id,
                        recovery_action="timeout_recovery"
                    )
                    
                    return True
        
        except Exception as e:
            logger.error(f"실행 타임아웃 복구 실패: {e}")
        
        return False

class WorkflowOptimizer:
    """워크플로우 최적화"""
    
    def __init__(self):
        self.client = N8nAPIClient()
    
    async def optimize_workflows(self, metrics: List[WorkflowMetrics]) -> Dict[str, Any]:
        """워크플로우 최적화"""
        optimization_results = {
            "optimized": [],
            "suggestions": []
        }
        
        for metric in metrics:
            # 실행 시간 최적화
            if metric.average_duration > 180:  # 3분 이상
                optimization_results["suggestions"].append({
                    "workflow_id": metric.workflow_id,
                    "workflow_name": metric.workflow_name,
                    "type": "performance",
                    "suggestion": "워크플로우 실행 시간이 깁니다. 병렬 처리나 배치 크기 조정을 고려하세요.",
                    "current_duration": metric.average_duration
                })
            
            # 실패율 최적화
            if metric.failure_rate > 20:
                optimization_results["suggestions"].append({
                    "workflow_id": metric.workflow_id,
                    "workflow_name": metric.workflow_name,
                    "type": "reliability",
                    "suggestion": "워크플로우 실패율이 높습니다. 에러 핸들링과 재시도 로직을 강화하세요.",
                    "failure_rate": metric.failure_rate
                })
            
            # 실행 빈도 최적화
            if metric.workflow_type == WorkflowType.RSS_COLLECTION:
                if metric.total_executions > 100:  # 일일 실행 기준
                    optimization_results["suggestions"].append({
                        "workflow_id": metric.workflow_id,
                        "workflow_name": metric.workflow_name,
                        "type": "frequency",
                        "suggestion": "RSS 수집 빈도가 높습니다. 스케줄을 조정하여 리소스를 절약하세요.",
                        "daily_executions": metric.total_executions
                    })
        
        return optimization_results

class N8nAutomationManager:
    """n8n 자동화 통합 관리자"""
    
    def __init__(self):
        self.monitor = WorkflowMonitor()
        self.recovery = WorkflowRecovery()
        self.optimizer = WorkflowOptimizer()
        self.client = N8nAPIClient()
    
    async def run_automation_cycle(self):
        """자동화 사이클 실행"""
        logger.info("n8n 자동화 사이클 시작")
        
        try:
            # 1. 워크플로우 메트릭 수집
            metrics = await self.monitor.collect_workflow_metrics()
            
            if not metrics:
                logger.warning("수집된 워크플로우 메트릭이 없습니다")
                return
            
            # 2. 건강 상태 분석
            issues = await self.monitor.analyze_workflow_health(metrics)
            
            # 3. 자동 복구 실행
            if issues:
                recovery_results = await self.recovery.execute_recovery(issues)
                await self.report_recovery_results(recovery_results)
            
            # 4. 최적화 제안
            optimization_results = await self.optimizer.optimize_workflows(metrics)
            await self.report_optimization_suggestions(optimization_results)
            
            # 5. 전체 상태 리포트
            await self.generate_status_report(metrics, issues)
            
            logger.info("n8n 자동화 사이클 완료")
            
        except Exception as e:
            logger.error(f"n8n 자동화 사이클 실패: {e}")
            await send_critical_alert(
                "n8n 자동화 시스템 오류",
                f"n8n 자동화 시스템에서 오류가 발생했습니다: {e}",
                service="n8n_automation"
            )
        finally:
            await self.client.close()
    
    async def report_recovery_results(self, results: Dict[str, List[str]]):
        """복구 결과 리포트"""
        if results["successful"]:
            await send_info_alert(
                "워크플로우 자동 복구 성공",
                f"다음 워크플로우가 자동으로 복구되었습니다:\n" + "\n".join(results["successful"]),
                service="n8n_automation",
                recovery_count=len(results["successful"])
            )
        
        if results["failed"]:
            await send_warning_alert(
                "워크플로우 복구 실패",
                f"다음 워크플로우 복구가 실패했습니다:\n" + "\n".join(results["failed"]),
                service="n8n_automation",
                failed_recovery_count=len(results["failed"])
            )
    
    async def report_optimization_suggestions(self, results: Dict[str, Any]):
        """최적화 제안 리포트"""
        if results["suggestions"]:
            suggestions_text = "\n".join([
                f"- {s['workflow_name']}: {s['suggestion']}" 
                for s in results["suggestions"]
            ])
            
            await send_info_alert(
                "워크플로우 최적화 제안",
                f"다음 워크플로우들의 최적화를 고려해보세요:\n{suggestions_text}",
                service="n8n_automation",
                optimization_count=len(results["suggestions"])
            )
    
    async def generate_status_report(self, metrics: List[WorkflowMetrics], issues: List[Dict[str, Any]]):
        """상태 리포트 생성"""
        total_workflows = len(metrics)
        total_executions = sum(m.total_executions for m in metrics)
        avg_success_rate = sum(m.success_rate for m in metrics) / total_workflows if total_workflows > 0 else 0
        
        critical_issues = len([i for i in issues if i.get("severity") == "critical"])
        warning_issues = len([i for i in issues if i.get("severity") == "warning"])
        
        report = f"""
🤖 n8n 워크플로우 상태 리포트
================================

📊 전체 현황:
- 총 워크플로우: {total_workflows}개
- 총 실행 횟수: {total_executions}회
- 평균 성공률: {avg_success_rate:.1f}%

⚠️ 이슈 현황:
- 심각: {critical_issues}개
- 경고: {warning_issues}개

🎯 상태: {"🔴 주의 필요" if critical_issues > 0 else "🟡 양호" if warning_issues > 0 else "🟢 정상"}
"""
        
        await send_info_alert(
            "n8n 워크플로우 상태 리포트",
            report,
            service="n8n_automation",
            total_workflows=total_workflows,
            total_executions=total_executions,
            avg_success_rate=avg_success_rate,
            critical_issues=critical_issues,
            warning_issues=warning_issues
        )

async def main():
    """메인 함수"""
    automation_manager = N8nAutomationManager()
    
    # 지속적 자동화 모니터링
    while True:
        try:
            await automation_manager.run_automation_cycle()
            await asyncio.sleep(1800)  # 30분 간격
        except KeyboardInterrupt:
            logger.info("n8n 자동화 시스템 중단")
            break
        except Exception as e:
            logger.error(f"n8n 자동화 시스템 오류: {e}")
            await asyncio.sleep(300)  # 5분 후 재시도

if __name__ == "__main__":
    asyncio.run(main())