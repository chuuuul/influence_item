"""
T01_S03_M03: n8n 워크플로우 모니터링
n8n 워크플로우 상태 및 성능 추적 시스템
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """워크플로우 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"


class ExecutionStatus(Enum):
    """실행 상태"""
    SUCCESS = "success"
    ERROR = "error"
    RUNNING = "running"
    WAITING = "waiting"
    CANCELED = "canceled"


@dataclass
class WorkflowInfo:
    """워크플로우 정보"""
    id: str
    name: str
    status: WorkflowStatus
    last_execution: Optional[datetime]
    total_executions: int
    success_rate: float
    avg_execution_time: float
    created_at: datetime
    updated_at: datetime


@dataclass
class ExecutionInfo:
    """실행 정보"""
    id: str
    workflow_id: str
    workflow_name: str
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime]
    execution_time: Optional[float]
    error_message: Optional[str]
    finished: bool


class N8NMonitor:
    """n8n 워크플로우 모니터링 관리자"""
    
    def __init__(self, n8n_base_url: str = "http://localhost:5678", api_key: str = None):
        """
        Args:
            n8n_base_url: n8n 서버 베이스 URL
            api_key: n8n API 키 (필요한 경우)
        """
        self.base_url = n8n_base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # API 키가 있는 경우 헤더에 추가
        if self.api_key:
            self.session.headers.update({
                'X-N8N-API-KEY': self.api_key
            })
        
        self.last_check = None
        self._workflow_cache = {}
        
    def check_connection(self) -> bool:
        """n8n 서버 연결 확인"""
        try:
            response = self.session.get(f"{self.base_url}/healthz", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to n8n server: {e}")
            return False
    
    def get_workflows(self) -> List[WorkflowInfo]:
        """모든 워크플로우 정보 조회"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/workflows", timeout=30)
            response.raise_for_status()
            
            workflows_data = response.json().get('data', [])
            workflows = []
            
            for wf_data in workflows_data:
                try:
                    # 각 워크플로우의 실행 통계 조회
                    execution_stats = self._get_workflow_execution_stats(wf_data['id'])
                    
                    workflow = WorkflowInfo(
                        id=wf_data['id'],
                        name=wf_data.get('name', 'Unknown'),
                        status=WorkflowStatus.ACTIVE if wf_data.get('active', False) else WorkflowStatus.INACTIVE,
                        last_execution=execution_stats.get('last_execution'),
                        total_executions=execution_stats.get('total_executions', 0),
                        success_rate=execution_stats.get('success_rate', 0.0),
                        avg_execution_time=execution_stats.get('avg_execution_time', 0.0),
                        created_at=datetime.fromisoformat(wf_data['createdAt'].replace('Z', '+00:00')) if wf_data.get('createdAt') else datetime.now(),
                        updated_at=datetime.fromisoformat(wf_data['updatedAt'].replace('Z', '+00:00')) if wf_data.get('updatedAt') else datetime.now()
                    )
                    
                    workflows.append(workflow)
                    
                except Exception as e:
                    logger.error(f"Failed to process workflow {wf_data.get('id', 'unknown')}: {e}")
                    continue
            
            return workflows
            
        except Exception as e:
            logger.error(f"Failed to get workflows: {e}")
            return []
    
    def _get_workflow_execution_stats(self, workflow_id: str) -> Dict[str, Any]:
        """워크플로우 실행 통계 조회"""
        try:
            # 최근 30일 실행 내역 조회
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)
            
            params = {
                'workflowId': workflow_id,
                'limit': 100,
                'includeData': 'false'
            }
            
            response = self.session.get(
                f"{self.base_url}/api/v1/executions",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            executions_data = response.json().get('data', [])
            
            if not executions_data:
                return {
                    'last_execution': None,
                    'total_executions': 0,
                    'success_rate': 0.0,
                    'avg_execution_time': 0.0
                }
            
            # 통계 계산
            total_executions = len(executions_data)
            successful_executions = sum(1 for ex in executions_data if ex.get('finished') and not ex.get('stoppedAt'))
            success_rate = (successful_executions / total_executions) * 100 if total_executions > 0 else 0.0
            
            # 평균 실행 시간 계산
            execution_times = []
            for ex in executions_data:
                if ex.get('startedAt') and ex.get('stoppedAt'):
                    start = datetime.fromisoformat(ex['startedAt'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(ex['stoppedAt'].replace('Z', '+00:00'))
                    execution_times.append((end - start).total_seconds())
            
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
            
            # 마지막 실행 시간
            last_execution = None
            if executions_data:
                last_ex = executions_data[0]  # 첫 번째가 가장 최근
                if last_ex.get('startedAt'):
                    last_execution = datetime.fromisoformat(last_ex['startedAt'].replace('Z', '+00:00'))
            
            return {
                'last_execution': last_execution,
                'total_executions': total_executions,
                'success_rate': success_rate,
                'avg_execution_time': avg_execution_time
            }
            
        except Exception as e:
            logger.error(f"Failed to get execution stats for workflow {workflow_id}: {e}")
            return {
                'last_execution': None,
                'total_executions': 0,
                'success_rate': 0.0,
                'avg_execution_time': 0.0
            }
    
    def get_recent_executions(self, limit: int = 20) -> List[ExecutionInfo]:
        """최근 실행 내역 조회"""
        try:
            params = {
                'limit': limit,
                'includeData': 'false'
            }
            
            response = self.session.get(
                f"{self.base_url}/api/v1/executions",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            executions_data = response.json().get('data', [])
            executions = []
            
            for ex_data in executions_data:
                try:
                    start_time = datetime.fromisoformat(ex_data['startedAt'].replace('Z', '+00:00')) if ex_data.get('startedAt') else datetime.now()
                    end_time = datetime.fromisoformat(ex_data['stoppedAt'].replace('Z', '+00:00')) if ex_data.get('stoppedAt') else None
                    
                    execution_time = None
                    if start_time and end_time:
                        execution_time = (end_time - start_time).total_seconds()
                    
                    # 상태 결정
                    if ex_data.get('finished'):
                        if ex_data.get('stoppedAt') and not ex_data.get('error'):
                            status = ExecutionStatus.SUCCESS
                        else:
                            status = ExecutionStatus.ERROR
                    elif ex_data.get('startedAt'):
                        status = ExecutionStatus.RUNNING
                    else:
                        status = ExecutionStatus.WAITING
                    
                    execution = ExecutionInfo(
                        id=ex_data['id'],
                        workflow_id=ex_data.get('workflowId', 'unknown'),
                        workflow_name=ex_data.get('workflowData', {}).get('name', 'Unknown'),
                        status=status,
                        start_time=start_time,
                        end_time=end_time,
                        execution_time=execution_time,
                        error_message=ex_data.get('error', {}).get('message') if ex_data.get('error') else None,
                        finished=ex_data.get('finished', False)
                    )
                    
                    executions.append(execution)
                    
                except Exception as e:
                    logger.error(f"Failed to process execution {ex_data.get('id', 'unknown')}: {e}")
                    continue
            
            return executions
            
        except Exception as e:
            logger.error(f"Failed to get recent executions: {e}")
            return []
    
    def get_workflow_execution_summary(self, hours: int = 24) -> Dict[str, Any]:
        """워크플로우 실행 요약 통계"""
        try:
            # 지정된 시간 내의 실행 내역 조회
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            params = {
                'limit': 1000,  # 충분히 큰 값
                'includeData': 'false'
            }
            
            response = self.session.get(
                f"{self.base_url}/api/v1/executions",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            executions_data = response.json().get('data', [])
            
            # 시간 범위 내 실행만 필터링
            filtered_executions = []
            for ex in executions_data:
                if ex.get('startedAt'):
                    ex_start = datetime.fromisoformat(ex['startedAt'].replace('Z', '+00:00'))
                    if ex_start >= start_time:
                        filtered_executions.append(ex)
            
            # 통계 계산
            total_executions = len(filtered_executions)
            successful_executions = sum(1 for ex in filtered_executions if ex.get('finished') and not ex.get('error'))
            failed_executions = sum(1 for ex in filtered_executions if ex.get('error'))
            running_executions = sum(1 for ex in filtered_executions if ex.get('startedAt') and not ex.get('stoppedAt'))
            
            success_rate = (successful_executions / total_executions) * 100 if total_executions > 0 else 0.0
            
            # 워크플로우별 통계
            workflow_stats = {}
            for ex in filtered_executions:
                wf_id = ex.get('workflowId', 'unknown')
                wf_name = ex.get('workflowData', {}).get('name', 'Unknown')
                
                if wf_id not in workflow_stats:
                    workflow_stats[wf_id] = {
                        'name': wf_name,
                        'total': 0,
                        'success': 0,
                        'failed': 0,
                        'running': 0
                    }
                
                workflow_stats[wf_id]['total'] += 1
                
                if ex.get('finished') and not ex.get('error'):
                    workflow_stats[wf_id]['success'] += 1
                elif ex.get('error'):
                    workflow_stats[wf_id]['failed'] += 1
                elif ex.get('startedAt') and not ex.get('stoppedAt'):
                    workflow_stats[wf_id]['running'] += 1
            
            return {
                'period_hours': hours,
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'failed_executions': failed_executions,
                'running_executions': running_executions,
                'success_rate': success_rate,
                'workflow_stats': workflow_stats,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get execution summary: {e}")
            return {
                'period_hours': hours,
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'running_executions': 0,
                'success_rate': 0.0,
                'workflow_stats': {},
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
    
    def get_system_health(self) -> Dict[str, Any]:
        """n8n 시스템 헬스 상태"""
        health_data = {
            'connection': False,
            'status': 'unknown',
            'total_workflows': 0,
            'active_workflows': 0,
            'recent_executions': 0,
            'system_load': 'unknown',
            'last_check': datetime.now().isoformat()
        }
        
        try:
            # 연결 확인
            if not self.check_connection():
                health_data['status'] = 'disconnected'
                return health_data
            
            health_data['connection'] = True
            
            # 워크플로우 통계
            workflows = self.get_workflows()
            health_data['total_workflows'] = len(workflows)
            health_data['active_workflows'] = sum(1 for wf in workflows if wf.status == WorkflowStatus.ACTIVE)
            
            # 최근 실행 통계 (지난 1시간)
            summary = self.get_workflow_execution_summary(hours=1)
            health_data['recent_executions'] = summary.get('total_executions', 0)
            
            # 전반적인 상태 결정
            if health_data['active_workflows'] > 0 and summary.get('success_rate', 0) >= 80:
                health_data['status'] = 'healthy'
            elif summary.get('failed_executions', 0) > 5:
                health_data['status'] = 'warning'
            else:
                health_data['status'] = 'healthy'
            
            self.last_check = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to get n8n system health: {e}")
            health_data['status'] = 'error'
            health_data['error'] = str(e)
        
        return health_data


# 전역 n8n 모니터 인스턴스
_n8n_monitor = None


def get_n8n_monitor(n8n_url: str = "http://localhost:5678", api_key: str = None) -> N8NMonitor:
    """싱글톤 n8n 모니터 반환"""
    global _n8n_monitor
    if _n8n_monitor is None:
        _n8n_monitor = N8NMonitor(n8n_url, api_key)
    return _n8n_monitor