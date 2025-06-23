"""
Emergency Manager
긴급 상황 대응 관리자

예산 초과 및 시스템 문제 발생 시 긴급 대응 처리
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from src.api.budget_controller import get_budget_controller, BudgetThreshold
from src.api.api_limiter import get_api_limiter
from src.api.service_controller import get_service_controller
from dashboard.utils.error_handler import ErrorHandler

# 로깅 설정
logger = logging.getLogger(__name__)


class EmergencyLevel(Enum):
    """긴급 상황 레벨"""
    LOW = "low"           # 경고 수준
    MEDIUM = "medium"     # 주의 수준
    HIGH = "high"         # 위험 수준
    CRITICAL = "critical" # 치명적 수준


class EmergencyType(Enum):
    """긴급 상황 유형"""
    BUDGET_EXCEEDED = "budget_exceeded"
    SERVICE_FAILURE = "service_failure"
    API_LIMIT_REACHED = "api_limit_reached"
    SYSTEM_OVERLOAD = "system_overload"
    MANUAL_TRIGGER = "manual_trigger"


@dataclass
class EmergencyAction:
    """긴급 대응 액션"""
    action_id: str
    action_type: str
    description: str
    auto_execute: bool
    executed: bool = False
    execution_time: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class EmergencyResponse:
    """긴급 대응 결과"""
    emergency_id: str
    level: EmergencyLevel
    emergency_type: EmergencyType
    triggered_at: str
    description: str
    actions_taken: List[EmergencyAction]
    manual_actions_required: List[str]
    resolved: bool = False
    resolved_at: Optional[str] = None


class EmergencyManager:
    """긴급 상황 관리자"""
    
    def __init__(self):
        self.budget_controller = get_budget_controller()
        self.api_limiter = get_api_limiter()
        self.service_controller = get_service_controller()
        self.error_handler = ErrorHandler()
        
        self.emergency_history: List[EmergencyResponse] = []
        self.active_emergencies: Dict[str, EmergencyResponse] = {}
        
        # 긴급 대응 액션 정의
        self.emergency_actions = {
            EmergencyType.BUDGET_EXCEEDED: {
                EmergencyLevel.HIGH: [
                    EmergencyAction(
                        action_id="limit_optional_apis",
                        action_type="api_limit",
                        description="선택적 API 호출 제한",
                        auto_execute=True
                    ),
                    EmergencyAction(
                        action_id="stop_optional_services",
                        action_type="service_control",
                        description="선택적 서비스 중단",
                        auto_execute=True
                    )
                ],
                EmergencyLevel.CRITICAL: [
                    EmergencyAction(
                        action_id="emergency_budget_limit",
                        action_type="budget_control",
                        description="모든 비필수 서비스 중단",
                        auto_execute=True
                    ),
                    EmergencyAction(
                        action_id="enable_emergency_bypass",
                        action_type="manual_control",
                        description="긴급 우회 모드 활성화 대기",
                        auto_execute=False
                    )
                ]
            },
            EmergencyType.API_LIMIT_REACHED: {
                EmergencyLevel.MEDIUM: [
                    EmergencyAction(
                        action_id="enable_circuit_breaker",
                        action_type="api_limit",
                        description="회로 차단기 활성화",
                        auto_execute=True
                    )
                ],
                EmergencyLevel.HIGH: [
                    EmergencyAction(
                        action_id="temporary_api_block",
                        action_type="api_limit", 
                        description="임시 API 차단",
                        auto_execute=True
                    )
                ]
            }
        }
        
        logger.info("긴급 상황 관리자 초기화 완료")
    
    async def trigger_emergency(self, 
                               emergency_type: EmergencyType,
                               level: EmergencyLevel,
                               description: str,
                               context: Optional[Dict] = None) -> EmergencyResponse:
        """
        긴급 상황 발생 처리
        
        Args:
            emergency_type: 긴급 상황 유형
            level: 긴급 수준
            description: 상황 설명
            context: 추가 컨텍스트 정보
        """
        emergency_id = f"emergency_{emergency_type.value}_{int(datetime.now().timestamp())}"
        
        logger.critical(f"긴급 상황 발생: {emergency_id} - {description}")
        
        # 긴급 대응 액션 준비
        actions = self._get_emergency_actions(emergency_type, level)
        
        # 긴급 대응 객체 생성
        emergency_response = EmergencyResponse(
            emergency_id=emergency_id,
            level=level,
            emergency_type=emergency_type,
            triggered_at=datetime.now().isoformat(),
            description=description,
            actions_taken=actions,
            manual_actions_required=[]
        )
        
        # 활성 긴급 상황에 추가
        self.active_emergencies[emergency_id] = emergency_response
        
        # 즉시 알림 발송
        await self._send_emergency_notification(emergency_response, context)
        
        # 자동 액션 실행
        await self._execute_automatic_actions(emergency_response)
        
        # 수동 액션 안내
        self._prepare_manual_actions(emergency_response)
        
        # 이력에 추가
        self.emergency_history.append(emergency_response)
        
        return emergency_response
    
    def _get_emergency_actions(self, emergency_type: EmergencyType, level: EmergencyLevel) -> List[EmergencyAction]:
        """긴급 상황에 따른 액션 목록 가져오기"""
        actions = []
        
        if emergency_type in self.emergency_actions:
            type_actions = self.emergency_actions[emergency_type]
            
            # 현재 레벨 이하의 모든 액션 포함
            for action_level, action_list in type_actions.items():
                if self._level_priority(action_level) <= self._level_priority(level):
                    actions.extend([
                        EmergencyAction(
                            action_id=action.action_id,
                            action_type=action.action_type,
                            description=action.description,
                            auto_execute=action.auto_execute
                        ) for action in action_list
                    ])
        
        return actions
    
    def _level_priority(self, level: EmergencyLevel) -> int:
        """긴급 수준 우선순위 (숫자가 높을수록 더 심각)"""
        priorities = {
            EmergencyLevel.LOW: 1,
            EmergencyLevel.MEDIUM: 2,
            EmergencyLevel.HIGH: 3,
            EmergencyLevel.CRITICAL: 4
        }
        return priorities.get(level, 0)
    
    async def _send_emergency_notification(self, emergency: EmergencyResponse, context: Optional[Dict] = None):
        """긴급 상황 알림 발송"""
        try:
            # 긴급도에 따른 이모지
            level_emojis = {
                EmergencyLevel.LOW: "⚠️",
                EmergencyLevel.MEDIUM: "🚨",
                EmergencyLevel.HIGH: "🔥",
                EmergencyLevel.CRITICAL: "💥"
            }
            
            emoji = level_emojis.get(emergency.level, "🚨")
            
            notification_message = (
                f"{emoji} 긴급 상황 발생!\n\n"
                f"📋 ID: {emergency.emergency_id}\n"
                f"🎯 유형: {emergency.emergency_type.value}\n"
                f"⚡ 수준: {emergency.level.value.upper()}\n"
                f"📝 설명: {emergency.description}\n"
                f"⏰ 발생 시간: {emergency.triggered_at}\n\n"
                f"🔧 자동 대응 액션 {len([a for a in emergency.actions_taken if a.auto_execute])}개 실행 중...\n"
            )
            
            # 컨텍스트 정보 추가
            if context:
                notification_message += f"\n📊 추가 정보:\n"
                for key, value in context.items():
                    notification_message += f"• {key}: {value}\n"
            
            # 중요도에 따른 알림 설정
            is_critical = emergency.level in [EmergencyLevel.HIGH, EmergencyLevel.CRITICAL]
            
            emergency_context = {
                'emergency_id': emergency.emergency_id,
                'emergency_type': emergency.emergency_type.value,
                'emergency_level': emergency.level.value,
                'is_critical': is_critical
            }
            if context:
                emergency_context.update(context)
            
            self.error_handler.handle_error(
                Exception(f"Emergency: {emergency.description}"),
                context=emergency_context
            )
            
        except Exception as e:
            logger.error(f"긴급 알림 발송 실패: {e}")
    
    async def _execute_automatic_actions(self, emergency: EmergencyResponse):
        """자동 대응 액션 실행"""
        for action in emergency.actions_taken:
            if action.auto_execute:
                try:
                    logger.info(f"자동 액션 실행: {action.action_id} - {action.description}")
                    
                    result = await self._execute_action(action)
                    
                    action.executed = True
                    action.execution_time = datetime.now().isoformat()
                    action.result = result
                    
                    logger.info(f"자동 액션 완료: {action.action_id}")
                    
                except Exception as e:
                    action.error = str(e)
                    logger.error(f"자동 액션 실패: {action.action_id} - {e}")
    
    async def _execute_action(self, action: EmergencyAction) -> str:
        """개별 액션 실행"""
        if action.action_type == "api_limit":
            if action.action_id == "limit_optional_apis":
                self.api_limiter.limit_api_calls("coupang")
                self.api_limiter.limit_api_calls("whisper")
                return "선택적 API(Coupang, Whisper) 제한 완료"
            
            elif action.action_id == "enable_circuit_breaker":
                # 회로 차단기는 이미 자동으로 작동
                return "회로 차단기 상태 확인 완료"
            
            elif action.action_id == "temporary_api_block":
                self.api_limiter.limit_api_calls()  # 모든 API 차단
                return "모든 API 임시 차단 완료"
        
        elif action.action_type == "service_control":
            if action.action_id == "stop_optional_services":
                from src.api.service_controller import ServicePriority
                await self.service_controller._stop_services_by_priority([ServicePriority.OPTIONAL])
                return "선택적 서비스 중단 완료"
        
        elif action.action_type == "budget_control":
            if action.action_id == "emergency_budget_limit":
                await self.service_controller.emergency_stop_all_non_essential()
                return "필수 서비스 외 모든 서비스 중단 완료"
        
        return f"액션 실행 완료: {action.action_id}"
    
    def _prepare_manual_actions(self, emergency: EmergencyResponse):
        """수동 대응 액션 준비"""
        manual_actions = []
        
        # 수동 액션이 필요한 경우들
        for action in emergency.actions_taken:
            if not action.auto_execute:
                manual_actions.append(f"⚠️ {action.description} - 수동 실행 필요")
        
        # 긴급도에 따른 추가 수동 액션
        if emergency.level == EmergencyLevel.CRITICAL:
            manual_actions.extend([
                "💰 긴급 예산 증액 검토",
                "📞 운영팀에 즉시 연락",
                "🔧 시스템 긴급 점검 수행",
                "📊 비용 사용 패턴 긴급 분석"
            ])
        
        elif emergency.level == EmergencyLevel.HIGH:
            manual_actions.extend([
                "📈 사용량 패턴 분석",
                "🔍 비용 최적화 방안 검토",
                "⚙️ 시스템 설정 점검"
            ])
        
        emergency.manual_actions_required = manual_actions
    
    async def resolve_emergency(self, emergency_id: str, resolution_note: Optional[str] = None) -> bool:
        """긴급 상황 해결 처리"""
        if emergency_id not in self.active_emergencies:
            logger.warning(f"존재하지 않는 긴급 상황: {emergency_id}")
            return False
        
        try:
            emergency = self.active_emergencies[emergency_id]
            
            # 해결 마크
            emergency.resolved = True
            emergency.resolved_at = datetime.now().isoformat()
            
            # 활성 목록에서 제거
            del self.active_emergencies[emergency_id]
            
            # 해결 알림
            await self._send_resolution_notification(emergency, resolution_note)
            
            logger.info(f"긴급 상황 해결: {emergency_id}")
            return True
            
        except Exception as e:
            logger.error(f"긴급 상황 해결 처리 실패: {emergency_id} - {e}")
            return False
    
    async def _send_resolution_notification(self, emergency: EmergencyResponse, resolution_note: Optional[str] = None):
        """긴급 상황 해결 알림"""
        try:
            message = (
                f"✅ 긴급 상황 해결됨\n\n"
                f"📋 ID: {emergency.emergency_id}\n"
                f"🎯 유형: {emergency.emergency_type.value}\n"
                f"⏰ 해결 시간: {emergency.resolved_at}\n"
            )
            
            if resolution_note:
                message += f"📝 해결 내용: {resolution_note}\n"
            
            duration = (
                datetime.fromisoformat(emergency.resolved_at) - 
                datetime.fromisoformat(emergency.triggered_at)
            ).total_seconds() / 60
            
            message += f"⏱️ 지속 시간: {duration:.1f}분"
            
            self.error_handler.handle_error(
                Exception(f"Emergency Resolved: {emergency.emergency_id}"),
                context={'emergency_id': emergency.emergency_id, 'resolution': 'success'}
            )
            
        except Exception as e:
            logger.error(f"해결 알림 발송 실패: {e}")
    
    async def manual_emergency_override(self, override_type: str, context: Optional[Dict] = None) -> EmergencyResponse:
        """수동 긴급 모드 활성화"""
        if override_type == "budget_emergency":
            return await self.trigger_emergency(
                EmergencyType.MANUAL_TRIGGER,
                EmergencyLevel.CRITICAL,
                "수동 예산 긴급 모드 활성화",
                context
            )
        
        elif override_type == "service_emergency":
            return await self.trigger_emergency(
                EmergencyType.MANUAL_TRIGGER,
                EmergencyLevel.HIGH,
                "수동 서비스 긴급 모드 활성화",
                context
            )
        
        else:
            return await self.trigger_emergency(
                EmergencyType.MANUAL_TRIGGER,
                EmergencyLevel.MEDIUM,
                f"수동 긴급 모드: {override_type}",
                context
            )
    
    async def enable_emergency_bypass(self, duration_minutes: int = 60) -> bool:
        """긴급 우회 모드 활성화"""
        try:
            # API 제한 우회
            self.api_limiter.set_emergency_bypass(True)
            
            # 서비스 복구
            await self.service_controller.restore_all_services()
            
            # 자동 해제 스케줄링 (실제 운영에서는 별도 스케줄러 사용)
            logger.warning(f"긴급 우회 모드 활성화 - {duration_minutes}분간 유효")
            
            # 우회 모드 알림
            self.error_handler.handle_error(
                Exception("Emergency Bypass Mode Activated"),
                context={
                    'bypass_duration': duration_minutes,
                    'activated_at': datetime.now().isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"긴급 우회 모드 활성화 실패: {e}")
            return False
    
    def get_active_emergencies(self) -> List[Dict[str, Any]]:
        """활성 긴급 상황 목록 조회"""
        return [
            {
                **asdict(emergency),
                'level': emergency.level.value,
                'emergency_type': emergency.emergency_type.value
            }
            for emergency in self.active_emergencies.values()
        ]
    
    def get_emergency_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """긴급 상황 이력 조회"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_emergencies = []
        for emergency in self.emergency_history:
            emergency_time = datetime.fromisoformat(emergency.triggered_at)
            if emergency_time >= cutoff_date:
                emergency_dict = asdict(emergency)
                emergency_dict['level'] = emergency.level.value
                emergency_dict['emergency_type'] = emergency.emergency_type.value
                recent_emergencies.append(emergency_dict)
        
        return sorted(recent_emergencies, key=lambda x: x['triggered_at'], reverse=True)
    
    async def auto_check_emergency_conditions(self):
        """자동 긴급 상황 확인 (주기적 실행)"""
        try:
            # 예산 상태 확인
            budget_status = await self.budget_controller.check_budget_status()
            
            # 예산 기반 긴급 상황 체크
            if budget_status.threshold_status == BudgetThreshold.STOP_100:
                if not any(e.emergency_type == EmergencyType.BUDGET_EXCEEDED and e.level == EmergencyLevel.CRITICAL 
                          for e in self.active_emergencies.values()):
                    await self.trigger_emergency(
                        EmergencyType.BUDGET_EXCEEDED,
                        EmergencyLevel.CRITICAL,
                        f"예산 100% 초과: ₩{budget_status.current_spend:,.0f}",
                        {'usage_rate': budget_status.usage_rate, 'current_spend': budget_status.current_spend}
                    )
            
            elif budget_status.threshold_status == BudgetThreshold.EMERGENCY_95:
                if not any(e.emergency_type == EmergencyType.BUDGET_EXCEEDED and e.level == EmergencyLevel.HIGH 
                          for e in self.active_emergencies.values()):
                    await self.trigger_emergency(
                        EmergencyType.BUDGET_EXCEEDED,
                        EmergencyLevel.HIGH,
                        f"예산 95% 도달: ₩{budget_status.current_spend:,.0f}",
                        {'usage_rate': budget_status.usage_rate}
                    )
            
        except Exception as e:
            logger.error(f"자동 긴급 상황 확인 실패: {e}")


# 전역 긴급 관리자 인스턴스
_global_emergency_manager = None

def get_emergency_manager() -> EmergencyManager:
    """전역 긴급 관리자 인스턴스를 반환"""
    global _global_emergency_manager
    if _global_emergency_manager is None:
        _global_emergency_manager = EmergencyManager()
    return _global_emergency_manager