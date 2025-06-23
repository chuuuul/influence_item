"""
Budget Threshold Alert and Auto-Limitation System
비용 임계값 알림 및 자동 제한 시스템

T05_S03_M03의 핵심 구현 - PRD 섹션 6.2 예산 구조에 기반한 
월 15,000원 예산 내 실시간 모니터링 및 자동 제한 시스템
"""

import asyncio
import threading
import time
import json
import calendar
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
from functools import wraps
import numpy as np
import pandas as pd

from config.config import Config
from dashboard.utils.error_handler import ErrorHandler
from src.api.usage_tracker import APIUsageTracker, get_tracker

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BudgetThreshold(Enum):
    """예산 임계값 상태"""
    WARNING_70 = 0.70    # 70% - 경고 단계
    ALERT_80 = 0.80      # 80% - 주의 단계  
    CRITICAL_90 = 0.90   # 90% - 위험 단계
    EMERGENCY_95 = 0.95  # 95% - 비상 단계 (신규 API 호출 제한)
    STOP_100 = 1.00      # 100% - 완전 중단


@dataclass
class BudgetStatus:
    """예산 상태 정보"""
    total_budget: float
    current_spend: float
    usage_rate: float
    predicted_monthly_spend: float
    days_remaining: int
    threshold_status: Optional[BudgetThreshold]
    services_limited: List[str]
    last_updated: str
    monthly_target: float
    daily_average: float
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        if self.threshold_status:
            data['threshold_status'] = self.threshold_status.name
        return data


@dataclass
class BudgetAlert:
    """예산 알림 정보"""
    alert_id: str
    threshold: BudgetThreshold
    usage_rate: float
    current_spend: float
    predicted_spend: float
    message: str
    action_taken: List[str]
    timestamp: str


class BudgetExceededException(Exception):
    """예산 초과 예외"""
    def __init__(self, message: str, current_usage: float, threshold: float):
        super().__init__(message)
        self.current_usage = current_usage
        self.threshold = threshold


class BudgetController:
    """예산 관리 및 제어 시스템"""
    
    def __init__(self, monthly_budget: float = 15000.0):
        """
        Args:
            monthly_budget: 월 예산 (원) - PRD 기준 15,000원
        """
        self.monthly_budget = monthly_budget
        self.usage_tracker = get_tracker()
        self.current_spend = 0.0
        self.threshold_callbacks = {}
        self.limited_services = set()
        self.emergency_mode = False
        self.last_threshold_check = None
        self.alert_history = []
        
        # 서비스 우선순위 정의
        self.service_priorities = {
            'essential': ['database', 'monitoring', 'dashboard', 'core_api'],
            'important': ['gemini_api', 'whisper_processing', 'coupang_api'],
            'optional': ['auto_scaling', 'analytics', 'background_tasks']
        }
        
        # 임계값별 콜백 등록
        self._register_default_callbacks()
        
        logger.info(f"예산 관리자 초기화 - 월 예산: ₩{monthly_budget:,}")
    
    def _register_default_callbacks(self):
        """기본 임계값 콜백 등록"""
        self.threshold_callbacks[BudgetThreshold.WARNING_70] = self._handle_warning_threshold
        self.threshold_callbacks[BudgetThreshold.ALERT_80] = self._handle_alert_threshold
        self.threshold_callbacks[BudgetThreshold.CRITICAL_90] = self._handle_critical_threshold
        self.threshold_callbacks[BudgetThreshold.EMERGENCY_95] = self._handle_emergency_threshold
        self.threshold_callbacks[BudgetThreshold.STOP_100] = self._handle_stop_threshold
    
    async def check_budget_status(self) -> BudgetStatus:
        """실시간 예산 상태 확인"""
        try:
            # 현재 월 사용량 계산
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            days_passed = datetime.now().day
            days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
            days_remaining = days_in_month - days_passed
            
            # API 사용량에서 현재 비용 가져오기
            monthly_summary = self.usage_tracker.get_usage_summary(days=days_passed)
            self.current_spend = monthly_summary['total_cost_krw']
            
            # 사용률 계산
            usage_rate = self.current_spend / self.monthly_budget if self.monthly_budget > 0 else 0
            
            # 월말 예상 비용 계산
            if days_passed > 0:
                daily_avg = self.current_spend / days_passed
                predicted_spend = daily_avg * days_in_month
            else:
                predicted_spend = self.current_spend
            
            # 임계값 확인
            threshold = self._get_current_threshold(usage_rate)
            
            # 월 목표 대비 진행률
            expected_spend_by_now = (self.monthly_budget * days_passed) / days_in_month
            
            status = BudgetStatus(
                total_budget=self.monthly_budget,
                current_spend=self.current_spend,
                usage_rate=usage_rate,
                predicted_monthly_spend=predicted_spend,
                days_remaining=days_remaining,
                threshold_status=threshold,
                services_limited=list(self.limited_services),
                last_updated=datetime.now().isoformat(),
                monthly_target=expected_spend_by_now,
                daily_average=daily_avg if days_passed > 0 else 0
            )
            
            # 임계값 변화 감지 및 처리
            await self._handle_threshold_change(threshold, status)
            
            return status
            
        except Exception as e:
            logger.error(f"예산 상태 확인 중 오류: {e}")
            raise
    
    def _get_current_threshold(self, usage_rate: float) -> Optional[BudgetThreshold]:
        """현재 사용률에 따른 임계값 상태 반환"""
        if usage_rate >= 1.0:
            return BudgetThreshold.STOP_100
        elif usage_rate >= 0.95:
            return BudgetThreshold.EMERGENCY_95
        elif usage_rate >= 0.90:
            return BudgetThreshold.CRITICAL_90
        elif usage_rate >= 0.80:
            return BudgetThreshold.ALERT_80
        elif usage_rate >= 0.70:
            return BudgetThreshold.WARNING_70
        else:
            return None
    
    async def _handle_threshold_change(self, current_threshold: Optional[BudgetThreshold], status: BudgetStatus):
        """임계값 변화 처리"""
        if current_threshold != self.last_threshold_check:
            if current_threshold and current_threshold in self.threshold_callbacks:
                await self.threshold_callbacks[current_threshold](status)
            self.last_threshold_check = current_threshold
    
    async def _handle_warning_threshold(self, status: BudgetStatus):
        """70% 경고 임계값 처리"""
        alert = self._create_alert(
            BudgetThreshold.WARNING_70,
            status,
            "예산 사용률 70% 도달 - 비용 모니터링 강화",
            ["모니터링 강화", "일일 리포트 활성화"]
        )
        await self._send_alert(alert)
        logger.warning(f"예산 경고: 70% 도달 (₩{status.current_spend:,.0f}/₩{status.total_budget:,.0f})")
    
    async def _handle_alert_threshold(self, status: BudgetStatus):
        """80% 주의 임계값 처리"""
        alert = self._create_alert(
            BudgetThreshold.ALERT_80,
            status,
            "예산 사용률 80% 도달 - 주의 필요",
            ["비용 최적화 권장사항 생성", "관리자 알림"]
        )
        await self._send_alert(alert)
        logger.warning(f"예산 주의: 80% 도달 (₩{status.current_spend:,.0f}/₩{status.total_budget:,.0f})")
    
    async def _handle_critical_threshold(self, status: BudgetStatus):
        """90% 위험 임계값 처리"""
        # 선택적 서비스 사전 준비
        actions = ["비필수 서비스 사전 준비", "긴급 대응 체계 활성화"]
        
        alert = self._create_alert(
            BudgetThreshold.CRITICAL_90,
            status,
            "예산 사용률 90% 도달 - 위험 단계",
            actions
        )
        await self._send_alert(alert)
        logger.error(f"예산 위험: 90% 도달 (₩{status.current_spend:,.0f}/₩{status.total_budget:,.0f})")
    
    async def _handle_emergency_threshold(self, status: BudgetStatus):
        """95% 비상 임계값 처리 - 신규 API 호출 제한"""
        # 선택적 서비스 중단
        await self._limit_services(['optional'])
        
        actions = ["선택적 서비스 제한", "신규 API 호출 제한"]
        
        alert = self._create_alert(
            BudgetThreshold.EMERGENCY_95,
            status,
            "예산 사용률 95% 도달 - 긴급 제한 활성화",
            actions
        )
        await self._send_alert(alert)
        logger.critical(f"예산 비상: 95% 도달 - 서비스 제한 활성화 (₩{status.current_spend:,.0f}/₩{status.total_budget:,.0f})")
    
    async def _handle_stop_threshold(self, status: BudgetStatus):
        """100% 완전 중단 임계값 처리"""
        # 필수 서비스만 유지
        await self._limit_services(['optional', 'important'])
        self.emergency_mode = True
        
        actions = ["모든 비필수 서비스 중단", "긴급 모드 활성화"]
        
        alert = self._create_alert(
            BudgetThreshold.STOP_100,
            status,
            "예산 100% 초과 - 긴급 모드 활성화",
            actions
        )
        await self._send_alert(alert)
        logger.critical(f"예산 완전 초과: 100% 도달 - 긴급 모드 (₩{status.current_spend:,.0f}/₩{status.total_budget:,.0f})")
    
    async def _limit_services(self, priority_levels: List[str]):
        """지정된 우선순위 서비스들 제한"""
        for level in priority_levels:
            if level in self.service_priorities:
                for service in self.service_priorities[level]:
                    self.limited_services.add(service)
                    logger.info(f"서비스 제한: {service} ({level})")
    
    def _create_alert(self, threshold: BudgetThreshold, status: BudgetStatus, 
                     message: str, actions: List[str]) -> BudgetAlert:
        """알림 객체 생성"""
        alert_id = f"budget_alert_{threshold.name}_{int(time.time())}"
        
        alert = BudgetAlert(
            alert_id=alert_id,
            threshold=threshold,
            usage_rate=status.usage_rate,
            current_spend=status.current_spend,
            predicted_spend=status.predicted_monthly_spend,
            message=message,
            action_taken=actions,
            timestamp=datetime.now().isoformat()
        )
        
        self.alert_history.append(alert)
        return alert
    
    async def _send_alert(self, alert: BudgetAlert):
        """알림 발송"""
        try:
            # ErrorHandler를 통한 알림 발송
            error_handler = ErrorHandler()
            
            alert_message = (
                f"🚨 예산 알림: {alert.threshold.name}\n"
                f"💰 현재 사용률: {alert.usage_rate:.1%}\n"
                f"💸 현재 비용: ₩{alert.current_spend:,.0f}\n"
                f"📊 예상 월말 비용: ₩{alert.predicted_spend:,.0f}\n"
                f"📝 조치사항: {', '.join(alert.action_taken)}\n"
                f"⏰ 시간: {alert.timestamp}"
            )
            
            # 임계값에 따른 우선순위 설정
            is_critical = alert.threshold in [BudgetThreshold.EMERGENCY_95, BudgetThreshold.STOP_100]
            
            await error_handler.handle_error(
                Exception(alert.message),
                context={
                    'alert_type': 'budget_threshold',
                    'threshold': alert.threshold.name,
                    'usage_rate': alert.usage_rate,
                    'is_critical': is_critical
                },
                notify=True
            )
            
        except Exception as e:
            logger.error(f"알림 발송 실패: {e}")
    
    def is_service_limited(self, service_name: str) -> bool:
        """서비스 제한 여부 확인"""
        if self.emergency_mode:
            return service_name not in self.service_priorities['essential']
        return service_name in self.limited_services
    
    def can_make_api_call(self, api_name: str, essential: bool = False) -> bool:
        """API 호출 허용 여부 확인"""
        # 필수 API는 항상 허용 (긴급 모드에서도)
        if essential:
            return True
        
        if self.emergency_mode:
            return api_name in self.service_priorities['essential']
        
        return api_name not in self.limited_services
    
    async def restore_services(self, force: bool = False):
        """서비스 복구 (다음 월 시작 시 자동 호출)"""
        if force or datetime.now().day == 1:
            self.limited_services.clear()
            self.emergency_mode = False
            self.last_threshold_check = None
            logger.info("모든 서비스 제한 해제 - 월 초기화")
    
    def get_alert_history(self, days: int = 7) -> List[Dict]:
        """최근 알림 이력 조회"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_alerts = []
        for alert in self.alert_history:
            alert_time = datetime.fromisoformat(alert.timestamp)
            if alert_time >= cutoff_date:
                alert_dict = asdict(alert)
                alert_dict['threshold'] = alert.threshold.name
                recent_alerts.append(alert_dict)
        
        return sorted(recent_alerts, key=lambda x: x['timestamp'], reverse=True)
    
    async def get_cost_optimization_recommendations(self, status: BudgetStatus) -> List[str]:
        """비용 최적화 권장사항 생성"""
        recommendations = []
        
        # 예상 초과 시 권장사항
        if status.predicted_monthly_spend > self.monthly_budget:
            over_amount = status.predicted_monthly_spend - self.monthly_budget
            recommendations.append(
                f"월말 예상 초과: ₩{over_amount:,.0f} - 즉시 비용 절감 조치 필요"
            )
        
        # 일일 평균 기반 권장사항
        target_daily_avg = self.monthly_budget / calendar.monthrange(datetime.now().year, datetime.now().month)[1]
        if status.daily_average > target_daily_avg * 1.2:
            recommendations.append(
                f"일일 평균 사용량이 목표의 120% 초과 (₩{status.daily_average:.0f} > ₩{target_daily_avg:.0f})"
            )
        
        # API 사용 패턴 분석
        monthly_summary = self.usage_tracker.get_usage_summary(days=datetime.now().day)
        
        for api_data in monthly_summary['api_breakdown']:
            if api_data['api_name'] == 'gemini' and api_data['total_cost'] > self.monthly_budget * 0.5:
                recommendations.append(
                    f"Gemini API 사용량이 예산의 50% 초과 - 프롬프트 최적화 권장"
                )
        
        # 기본 권장사항
        if not recommendations:
            recommendations.append("현재 예산 사용량이 정상 범위 내에 있습니다.")
        
        return recommendations


# 전역 예산 관리자 인스턴스
_global_budget_controller = None

def get_budget_controller() -> BudgetController:
    """전역 예산 관리자 인스턴스를 반환"""
    global _global_budget_controller
    if _global_budget_controller is None:
        _global_budget_controller = BudgetController()
    return _global_budget_controller


def budget_controlled_api(api_name: str, essential: bool = False):
    """예산 제어 API 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            controller = get_budget_controller()
            
            if not controller.can_make_api_call(api_name, essential):
                raise BudgetExceededException(
                    f"API 호출이 예산 제한으로 차단됨: {api_name}",
                    controller.current_spend / controller.monthly_budget,
                    1.0 if controller.emergency_mode else 0.95
                )
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            controller = get_budget_controller()
            
            if not controller.can_make_api_call(api_name, essential):
                raise BudgetExceededException(
                    f"API 호출이 예산 제한으로 차단됨: {api_name}",
                    controller.current_spend / controller.monthly_budget,
                    1.0 if controller.emergency_mode else 0.95
                )
            
            return func(*args, **kwargs)
        
        # 비동기 함수인지 확인
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator