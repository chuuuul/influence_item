"""
Service Control System
서비스 중단/재개 자동화 시스템

예산 임계값에 따른 서비스 우선순위 기반 자동 제어
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path

from src.api.budget_controller import BudgetThreshold, get_budget_controller

# 로깅 설정
logger = logging.getLogger(__name__)


class ServicePriority(Enum):
    """서비스 우선순위"""
    ESSENTIAL = "essential"    # 필수 서비스 (항상 유지)
    IMPORTANT = "important"    # 중요 서비스 (95% 이후 제한)
    OPTIONAL = "optional"      # 선택적 서비스 (90% 이후 제한)


class ServiceStatus(Enum):
    """서비스 상태"""
    RUNNING = "running"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STARTING = "starting"
    ERROR = "error"


@dataclass
class ServiceConfig:
    """서비스 설정"""
    name: str
    priority: ServicePriority
    description: str
    dependencies: List[str]
    stop_command: Optional[str] = None
    start_command: Optional[str] = None
    health_check_url: Optional[str] = None
    timeout: int = 30
    enabled: bool = True


@dataclass
class ServiceState:
    """서비스 상태 정보"""
    name: str
    status: ServiceStatus
    priority: ServicePriority
    last_action: str
    last_action_time: str
    stop_reason: Optional[str] = None
    error_message: Optional[str] = None
    restart_count: int = 0


class ServiceController:
    """서비스 제어 시스템"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Args:
            config_file: 서비스 설정 파일 경로
        """
        self.services: Dict[str, ServiceConfig] = {}
        self.service_states: Dict[str, ServiceState] = {}
        self.stopped_services: Set[str] = set()
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # 기본 서비스 설정
        self._setup_default_services()
        
        # 설정 파일 로드 (선택사항)
        if config_file:
            self._load_config(config_file)
        
        logger.info("서비스 컨트롤러 초기화 완료")
    
    def _setup_default_services(self):
        """기본 서비스 설정"""
        default_services = [
            # 필수 서비스
            ServiceConfig(
                name="database",
                priority=ServicePriority.ESSENTIAL,
                description="SQLite 데이터베이스 서비스",
                dependencies=[]
            ),
            ServiceConfig(
                name="monitoring",
                priority=ServicePriority.ESSENTIAL,
                description="시스템 모니터링 서비스",
                dependencies=["database"]
            ),
            ServiceConfig(
                name="dashboard",
                priority=ServicePriority.ESSENTIAL,
                description="관리 대시보드 서비스",
                dependencies=["database", "monitoring"]
            ),
            ServiceConfig(
                name="core_api",
                priority=ServicePriority.ESSENTIAL,
                description="핵심 API 서비스",
                dependencies=["database"]
            ),
            
            # 중요 서비스
            ServiceConfig(
                name="gemini_api",
                priority=ServicePriority.IMPORTANT,
                description="Gemini AI 분석 서비스",
                dependencies=["core_api"]
            ),
            ServiceConfig(
                name="whisper_processing",
                priority=ServicePriority.IMPORTANT,
                description="음성 인식 처리 서비스",
                dependencies=["core_api"]
            ),
            ServiceConfig(
                name="coupang_api",
                priority=ServicePriority.IMPORTANT,
                description="쿠팡 파트너스 API 서비스",
                dependencies=["core_api"]
            ),
            ServiceConfig(
                name="visual_processing",
                priority=ServicePriority.IMPORTANT,
                description="시각 처리 서비스 (OCR, YOLO)",
                dependencies=["core_api"]
            ),
            
            # 선택적 서비스
            ServiceConfig(
                name="auto_scaling",
                priority=ServicePriority.OPTIONAL,
                description="자동 스케일링 서비스",
                dependencies=["monitoring"]
            ),
            ServiceConfig(
                name="analytics",
                priority=ServicePriority.OPTIONAL,
                description="분석 및 리포팅 서비스",
                dependencies=["database"]
            ),
            ServiceConfig(
                name="background_tasks",
                priority=ServicePriority.OPTIONAL,
                description="백그라운드 작업 처리",
                dependencies=["core_api"]
            ),
            ServiceConfig(
                name="notification_service",
                priority=ServicePriority.OPTIONAL,
                description="알림 발송 서비스",
                dependencies=["core_api"]
            )
        ]
        
        for service in default_services:
            self.services[service.name] = service
            self.service_states[service.name] = ServiceState(
                name=service.name,
                status=ServiceStatus.RUNNING,
                priority=service.priority,
                last_action="initialized",
                last_action_time=datetime.now().isoformat()
            )
        
        # 의존성 그래프 구성
        self._build_dependency_graph()
    
    def _build_dependency_graph(self):
        """서비스 의존성 그래프 구성"""
        self.dependency_graph.clear()
        
        for service_name, service in self.services.items():
            self.dependency_graph[service_name] = set(service.dependencies)
    
    def _load_config(self, config_file: str):
        """설정 파일에서 서비스 설정 로드"""
        try:
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                for service_data in config_data.get('services', []):
                    service = ServiceConfig(**service_data)
                    self.services[service.name] = service
                    
                    if service.name not in self.service_states:
                        self.service_states[service.name] = ServiceState(
                            name=service.name,
                            status=ServiceStatus.RUNNING,
                            priority=service.priority,
                            last_action="loaded",
                            last_action_time=datetime.now().isoformat()
                        )
                
                self._build_dependency_graph()
                logger.info(f"서비스 설정 로드 완료: {config_file}")
        
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
    
    async def limit_services_by_threshold(self, threshold: BudgetThreshold):
        """임계값에 따른 서비스 제한"""
        logger.info(f"임계값 {threshold.name}에 따른 서비스 제한 시작")
        
        if threshold == BudgetThreshold.CRITICAL_90:
            # 90%: 선택적 서비스 사전 준비 (아직 중단하지 않음)
            await self._prepare_service_limitation([ServicePriority.OPTIONAL])
        
        elif threshold == BudgetThreshold.EMERGENCY_95:
            # 95%: 선택적 서비스 중단
            await self._stop_services_by_priority([ServicePriority.OPTIONAL])
        
        elif threshold == BudgetThreshold.STOP_100:
            # 100%: 중요 서비스도 중단 (필수 서비스만 유지)
            await self._stop_services_by_priority([ServicePriority.OPTIONAL, ServicePriority.IMPORTANT])
    
    async def _prepare_service_limitation(self, priorities: List[ServicePriority]):
        """서비스 제한 사전 준비"""
        for priority in priorities:
            services_to_prepare = [
                name for name, service in self.services.items()
                if service.priority == priority and service.enabled
            ]
            
            for service_name in services_to_prepare:
                state = self.service_states[service_name]
                state.last_action = "prepared_for_limitation"
                state.last_action_time = datetime.now().isoformat()
                
                logger.info(f"서비스 제한 준비: {service_name} ({priority.value})")
    
    async def _stop_services_by_priority(self, priorities: List[ServicePriority]):
        """우선순위별 서비스 중단"""
        services_to_stop = []
        
        for priority in priorities:
            priority_services = [
                name for name, service in self.services.items()
                if service.priority == priority and service.enabled
            ]
            services_to_stop.extend(priority_services)
        
        # 의존성을 고려한 중단 순서 결정
        stop_order = self._calculate_stop_order(services_to_stop)
        
        for service_name in stop_order:
            await self._stop_service(service_name, f"budget_threshold_limitation")
    
    def _calculate_stop_order(self, services_to_stop: List[str]) -> List[str]:
        """의존성을 고려한 서비스 중단 순서 계산"""
        # 의존성이 많은 서비스부터 중단 (역순)
        remaining = set(services_to_stop)
        stop_order = []
        
        while remaining:
            # 다른 서비스가 의존하지 않는 서비스 찾기
            can_stop = []
            for service in remaining:
                is_depended = False
                for other_service in remaining:
                    if service in self.dependency_graph.get(other_service, set()):
                        is_depended = True
                        break
                
                if not is_depended:
                    can_stop.append(service)
            
            if not can_stop:
                # 순환 의존성이 있는 경우, 임의로 하나 선택
                can_stop = [list(remaining)[0]]
            
            stop_order.extend(can_stop)
            remaining -= set(can_stop)
        
        return stop_order
    
    async def _stop_service(self, service_name: str, reason: str):
        """개별 서비스 중단"""
        if service_name not in self.services:
            logger.warning(f"알 수 없는 서비스: {service_name}")
            return
        
        service = self.services[service_name]
        state = self.service_states[service_name]
        
        if state.status in [ServiceStatus.STOPPED, ServiceStatus.STOPPING]:
            logger.info(f"서비스 이미 중단됨 또는 중단 중: {service_name}")
            return
        
        try:
            state.status = ServiceStatus.STOPPING
            state.last_action = "stopping"
            state.last_action_time = datetime.now().isoformat()
            state.stop_reason = reason
            
            logger.info(f"서비스 중단 시작: {service_name} - 사유: {reason}")
            
            # 실제 서비스 중단 로직 (설정에 따라)
            if service.stop_command:
                # 외부 명령 실행
                process = await asyncio.create_subprocess_shell(
                    service.stop_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=service.timeout
                )
                
                if process.returncode != 0:
                    raise Exception(f"중단 명령 실패: {stderr.decode()}")
            
            # 서비스별 특수 중단 로직
            await self._service_specific_stop(service_name)
            
            state.status = ServiceStatus.STOPPED
            state.last_action = "stopped"
            state.last_action_time = datetime.now().isoformat()
            self.stopped_services.add(service_name)
            
            logger.info(f"서비스 중단 완료: {service_name}")
            
        except Exception as e:
            state.status = ServiceStatus.ERROR
            state.error_message = str(e)
            state.last_action = "stop_failed"
            state.last_action_time = datetime.now().isoformat()
            
            logger.error(f"서비스 중단 실패: {service_name} - {e}")
    
    async def _service_specific_stop(self, service_name: str):
        """서비스별 특수 중단 로직"""
        if service_name == "gemini_api":
            # Gemini API 호출 차단
            from src.api.api_limiter import get_api_limiter
            limiter = get_api_limiter()
            limiter.limit_api_calls("gemini")
        
        elif service_name == "coupang_api":
            # Coupang API 호출 차단
            from src.api.api_limiter import get_api_limiter
            limiter = get_api_limiter()
            limiter.limit_api_calls("coupang")
        
        elif service_name == "auto_scaling":
            # 자동 스케일링 중지
            pass  # 실제 구현 시 스케일링 매니저 중지
        
        elif service_name == "background_tasks":
            # 백그라운드 작업 중지
            pass  # 실제 구현 시 작업 큐 중지
    
    async def restore_all_services(self):
        """모든 중단된 서비스 복구"""
        logger.info("모든 서비스 복구 시작")
        
        # 중단된 서비스 목록
        stopped_services = list(self.stopped_services)
        
        if not stopped_services:
            logger.info("복구할 서비스가 없습니다")
            return
        
        # 의존성을 고려한 시작 순서 계산
        start_order = self._calculate_start_order(stopped_services)
        
        for service_name in start_order:
            await self._start_service(service_name)
        
        # API 제한 해제
        from src.api.api_limiter import get_api_limiter
        limiter = get_api_limiter()
        limiter.remove_api_limit()
        
        logger.info("모든 서비스 복구 완료")
    
    def _calculate_start_order(self, services_to_start: List[str]) -> List[str]:
        """의존성을 고려한 서비스 시작 순서 계산"""
        # 의존성이 적은 서비스부터 시작
        remaining = set(services_to_start)
        start_order = []
        
        while remaining:
            # 의존성이 모두 해결된 서비스 찾기
            can_start = []
            for service in remaining:
                dependencies = self.dependency_graph.get(service, set())
                unmet_deps = dependencies & remaining
                
                if not unmet_deps:
                    can_start.append(service)
            
            if not can_start:
                # 순환 의존성이 있는 경우, 필수 서비스부터 시작
                essential_services = [
                    s for s in remaining 
                    if self.services[s].priority == ServicePriority.ESSENTIAL
                ]
                can_start = essential_services[:1] if essential_services else [list(remaining)[0]]
            
            start_order.extend(can_start)
            remaining -= set(can_start)
        
        return start_order
    
    async def _start_service(self, service_name: str):
        """개별 서비스 시작"""
        if service_name not in self.services:
            logger.warning(f"알 수 없는 서비스: {service_name}")
            return
        
        service = self.services[service_name]
        state = self.service_states[service_name]
        
        if state.status == ServiceStatus.RUNNING:
            logger.info(f"서비스 이미 실행 중: {service_name}")
            return
        
        try:
            state.status = ServiceStatus.STARTING
            state.last_action = "starting"
            state.last_action_time = datetime.now().isoformat()
            state.error_message = None
            
            logger.info(f"서비스 시작: {service_name}")
            
            # 실제 서비스 시작 로직
            if service.start_command:
                process = await asyncio.create_subprocess_shell(
                    service.start_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=service.timeout
                )
                
                if process.returncode != 0:
                    raise Exception(f"시작 명령 실패: {stderr.decode()}")
            
            # 서비스별 특수 시작 로직
            await self._service_specific_start(service_name)
            
            state.status = ServiceStatus.RUNNING
            state.last_action = "started"
            state.last_action_time = datetime.now().isoformat()
            state.restart_count += 1
            self.stopped_services.discard(service_name)
            
            logger.info(f"서비스 시작 완료: {service_name}")
            
        except Exception as e:
            state.status = ServiceStatus.ERROR
            state.error_message = str(e)
            state.last_action = "start_failed"
            state.last_action_time = datetime.now().isoformat()
            
            logger.error(f"서비스 시작 실패: {service_name} - {e}")
    
    async def _service_specific_start(self, service_name: str):
        """서비스별 특수 시작 로직"""
        if service_name in ["gemini_api", "coupang_api"]:
            # API 제한 해제
            from src.api.api_limiter import get_api_limiter
            limiter = get_api_limiter()
            limiter.remove_api_limit(service_name.split('_')[0])
    
    def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """서비스 상태 조회"""
        if service_name not in self.services:
            return None
        
        service = self.services[service_name]
        state = self.service_states[service_name]
        
        return {
            'name': service.name,
            'description': service.description,
            'priority': service.priority.value,
            'status': state.status.value,
            'enabled': service.enabled,
            'dependencies': service.dependencies,
            'last_action': state.last_action,
            'last_action_time': state.last_action_time,
            'stop_reason': state.stop_reason,
            'error_message': state.error_message,
            'restart_count': state.restart_count,
            'is_stopped': service_name in self.stopped_services
        }
    
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 서비스 상태 조회"""
        return {
            name: self.get_service_status(name)
            for name in self.services.keys()
        }
    
    def get_services_by_priority(self, priority: ServicePriority) -> List[str]:
        """우선순위별 서비스 목록 조회"""
        return [
            name for name, service in self.services.items()
            if service.priority == priority
        ]
    
    async def emergency_stop_all_non_essential(self):
        """필수 서비스 외 모든 서비스 긴급 중단"""
        logger.critical("긴급 모드: 필수 서비스 외 모든 서비스 중단")
        
        non_essential = [
            name for name, service in self.services.items()
            if service.priority != ServicePriority.ESSENTIAL
        ]
        
        await self._stop_services_by_priority([ServicePriority.OPTIONAL, ServicePriority.IMPORTANT])


# 전역 서비스 컨트롤러 인스턴스
_global_service_controller = None

def get_service_controller() -> ServiceController:
    """전역 서비스 컨트롤러 인스턴스를 반환"""
    global _global_service_controller
    if _global_service_controller is None:
        _global_service_controller = ServiceController()
    return _global_service_controller