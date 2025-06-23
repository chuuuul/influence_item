"""
T03B_S03_M03: 통합 스케일링 관리자
T03A의 메트릭 수집 및 예측 시스템과 T03B의 클라우드 실행 시스템을 통합하는 메인 관리자
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from dataclasses import dataclass

from .scaling_metrics_collector import ScalingMetricsCollector
from .scaling_prediction_system import ScalingPredictionSystem
from .scaling_decision_engine import ScalingDecisionEngine, ScalingAction
from .cloud_scaling_executor import CloudScalingExecutor

logger = logging.getLogger(__name__)


@dataclass
class ScalingEvent:
    """스케일링 이벤트"""
    event_id: str
    timestamp: datetime
    event_type: str  # 'decision_made', 'execution_started', 'execution_completed', 'execution_failed'
    details: Dict[str, Any]
    metrics: Optional[Dict[str, Any]] = None
    cost_impact: Optional[float] = None


class IntegratedScalingManager:
    """통합 스케일링 관리자"""
    
    def __init__(self, 
                 region: str = 'us-west-2',
                 monitoring_interval: int = 60,  # 초
                 enable_auto_scaling: bool = True,
                 cost_limit_per_hour: float = 10.0):  # USD
        """
        Args:
            region: AWS 리전
            monitoring_interval: 모니터링 간격 (초)
            enable_auto_scaling: 자동 스케일링 활성화 여부
            cost_limit_per_hour: 시간당 비용 제한 (USD)
        """
        self.region = region
        self.monitoring_interval = monitoring_interval
        self.enable_auto_scaling = enable_auto_scaling
        self.cost_limit_per_hour = cost_limit_per_hour
        
        # 서브시스템 초기화
        self.metrics_collector = ScalingMetricsCollector()
        self.prediction_system = ScalingPredictionSystem()
        self.decision_engine = ScalingDecisionEngine()
        self.cloud_executor = CloudScalingExecutor(region=region)
        
        # 상태 관리
        self.is_running = False
        self.last_scaling_time = None
        self.events_history = []
        
        # 비용 추적
        self.current_hourly_cost = 0.0
        self.cost_alerts_sent = []
        
        logger.info("Integrated Scaling Manager initialized")
    
    async def start_monitoring(self):
        """모니터링 시작"""
        if self.is_running:
            logger.warning("Monitoring is already running")
            return
        
        self.is_running = True
        logger.info("Starting integrated scaling monitoring")
        
        try:
            while self.is_running:
                await self._monitoring_cycle()
                await asyncio.sleep(self.monitoring_interval)
                
        except Exception as e:
            logger.error(f"Monitoring loop failed: {e}")
            self.is_running = False
            raise
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.is_running = False
        logger.info("Stopping integrated scaling monitoring")
    
    async def _monitoring_cycle(self):
        """모니터링 사이클"""
        try:
            cycle_start = datetime.now()
            
            # 1. 현재 메트릭 수집
            current_metrics = await self._collect_current_metrics()
            if not current_metrics:
                logger.warning("Failed to collect metrics, skipping cycle")
                return
            
            # 2. 비용 확인
            cost_check = await self._check_cost_limits()
            if not cost_check:
                logger.warning("Cost limit exceeded, auto scaling disabled for this cycle")
                return
            
            # 3. 예측 수행
            predicted_metrics = await self._get_predictions(current_metrics)
            
            # 4. 스케일링 결정
            decision = await self._make_scaling_decision(current_metrics, predicted_metrics)
            
            # 5. 결정 실행 (자동 스케일링이 활성화된 경우)
            if self.enable_auto_scaling and decision.action != ScalingAction.MAINTAIN:
                execution_result = await self._execute_scaling_decision(decision)
                
                # 실행 이벤트 기록
                await self._record_event('execution_completed', {
                    'decision': decision.action.value,
                    'execution_id': execution_result.execution_id,
                    'success': execution_result.status.value == 'completed'
                }, current_metrics, decision.cost_impact)
            
            # 6. 이벤트 정리
            await self._cleanup_old_events()
            
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.debug(f"Monitoring cycle completed in {cycle_duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            await self._record_event('cycle_error', {'error': str(e)})
    
    async def _collect_current_metrics(self) -> Optional[Dict[str, Any]]:
        """현재 메트릭 수집"""
        try:
            # 시스템 메트릭 수집
            system_metrics = self.metrics_collector.collect_system_metrics()
            
            # 처리 큐 메트릭 수집
            queue_metrics = self.metrics_collector.collect_queue_metrics()
            
            # 응답 시간 메트릭 수집
            response_metrics = self.metrics_collector.collect_response_time_metrics()
            
            # AWS 인스턴스 메트릭 수집
            aws_metrics = await self._collect_aws_metrics()
            
            # 통합 메트릭 구성
            integrated_metrics = {
                **system_metrics,
                **queue_metrics,
                **response_metrics,
                **aws_metrics,
                'collection_time': datetime.now().isoformat(),
                'region': self.region
            }
            
            return integrated_metrics
            
        except Exception as e:
            logger.error(f"Failed to collect current metrics: {e}")
            return None
    
    async def _collect_aws_metrics(self) -> Dict[str, Any]:
        """AWS 메트릭 수집"""
        try:
            # 현재 인스턴스 정보
            instances = await self.cloud_executor._get_current_instances()
            running_instances = [i for i in instances if i['State']['Name'] == 'running']
            
            # 비용 정보
            cost_estimate = await self.cloud_executor.get_current_cost_estimate()
            
            return {
                'aws_instances_total': len(instances),
                'aws_instances_running': len(running_instances),
                'aws_cost_per_hour': cost_estimate.get('cost_per_hour', 0.0),
                'aws_cost_per_day': cost_estimate.get('cost_per_day', 0.0),
                'aws_region': self.region
            }
            
        except Exception as e:
            logger.error(f"Failed to collect AWS metrics: {e}")
            return {}
    
    async def _get_predictions(self, current_metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """예측 수행"""
        try:
            # 1시간 후 수요 예측
            predictions = self.prediction_system.predict_demand(
                current_metrics=current_metrics,
                prediction_horizon_minutes=60
            )
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to get predictions: {e}")
            return None
    
    async def _make_scaling_decision(self, current_metrics: Dict[str, Any], 
                                   predicted_metrics: Optional[Dict[str, Any]]) -> Any:
        """스케일링 결정"""
        try:
            # 현재 인스턴스 수 확인
            current_instance_count = current_metrics.get('aws_instances_running', 1)
            
            # 결정 생성
            decision = self.decision_engine.make_scaling_decision(
                current_metrics=current_metrics,
                predicted_metrics=predicted_metrics,
                current_instance_count=current_instance_count
            )
            
            # 결정 이벤트 기록
            await self._record_event('decision_made', {
                'action': decision.action.value,
                'reasons': [r.value for r in decision.reasons],
                'confidence': decision.confidence,
                'urgency': decision.urgency,
                'recommended_instances': decision.recommended_instances
            }, current_metrics, decision.cost_impact)
            
            return decision
            
        except Exception as e:
            logger.error(f"Failed to make scaling decision: {e}")
            # 기본 유지 결정 반환
            from .scaling_decision_engine import ScalingDecision
            return ScalingDecision(
                action=ScalingAction.MAINTAIN,
                reasons=[],
                confidence=1.0,
                urgency=1,
                recommended_instances=1,
                current_metrics=current_metrics,
                predicted_metrics=predicted_metrics,
                cost_impact=0.0,
                decision_time=datetime.now(),
                cooldown_until=None
            )
    
    async def _execute_scaling_decision(self, decision) -> Any:
        """스케일링 결정 실행"""
        try:
            logger.info(f"Executing scaling decision: {decision.action.value}")
            
            # 실행 시작 이벤트 기록
            await self._record_event('execution_started', {
                'action': decision.action.value,
                'target_instances': decision.recommended_instances
            })
            
            # 클라우드 실행
            execution_result = await self.cloud_executor.execute_scaling_decision(decision)
            
            # 마지막 스케일링 시간 업데이트
            self.last_scaling_time = datetime.now()
            
            logger.info(f"Scaling execution completed: {execution_result.execution_id}")
            return execution_result
            
        except Exception as e:
            logger.error(f"Failed to execute scaling decision: {e}")
            
            # 실행 실패 이벤트 기록
            await self._record_event('execution_failed', {
                'action': decision.action.value,
                'error': str(e)
            })
            
            raise
    
    async def _check_cost_limits(self) -> bool:
        """비용 한도 확인"""
        try:
            cost_estimate = await self.cloud_executor.get_current_cost_estimate()
            self.current_hourly_cost = cost_estimate.get('cost_per_hour', 0.0)
            
            if self.current_hourly_cost > self.cost_limit_per_hour:
                logger.warning(f"Current cost ${self.current_hourly_cost:.4f}/hour exceeds limit ${self.cost_limit_per_hour:.4f}/hour")
                
                # 비용 알림 (1시간에 한 번만)
                now = datetime.now()
                last_alert = None
                for alert_time in self.cost_alerts_sent:
                    if now - alert_time < timedelta(hours=1):
                        last_alert = alert_time
                        break
                
                if not last_alert:
                    await self._record_event('cost_limit_exceeded', {
                        'current_cost': self.current_hourly_cost,
                        'limit': self.cost_limit_per_hour
                    })
                    self.cost_alerts_sent.append(now)
                
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check cost limits: {e}")
            return True  # 오류 시 안전하게 계속 진행
    
    async def _record_event(self, event_type: str, details: Dict[str, Any], 
                          metrics: Optional[Dict[str, Any]] = None,
                          cost_impact: Optional[float] = None):
        """이벤트 기록"""
        try:
            event = ScalingEvent(
                event_id=f"{event_type}_{int(datetime.now().timestamp())}",
                timestamp=datetime.now(),
                event_type=event_type,
                details=details,
                metrics=metrics,
                cost_impact=cost_impact
            )
            
            self.events_history.append(event)
            
            # 로그 출력
            logger.info(f"Event recorded: {event_type} - {details}")
            
        except Exception as e:
            logger.error(f"Failed to record event: {e}")
    
    async def _cleanup_old_events(self, hours: int = 48):
        """오래된 이벤트 정리"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            original_count = len(self.events_history)
            self.events_history = [
                event for event in self.events_history 
                if event.timestamp > cutoff_time
            ]
            
            cleaned_count = original_count - len(self.events_history)
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} old events")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
    
    async def manual_scale(self, target_instances: int, reason: str = "Manual Override") -> Any:
        """수동 스케일링"""
        logger.info(f"Manual scaling requested: {target_instances} instances, reason: {reason}")
        
        try:
            # 비용 확인
            if target_instances > 10:  # 안전 제한
                raise ValueError(f"Target instances {target_instances} exceeds safety limit (10)")
            
            estimated_cost = target_instances * 0.1  # 대략적인 시간당 비용
            if estimated_cost > self.cost_limit_per_hour * 2:  # 2배 초과 시 차단
                raise ValueError(f"Estimated cost ${estimated_cost:.2f}/hour exceeds safety limit")
            
            # 수동 오버라이드 실행
            execution_result = await self.cloud_executor.manual_override_scaling(
                target_instances=target_instances, 
                reason=reason
            )
            
            # 이벤트 기록
            await self._record_event('manual_scaling', {
                'target_instances': target_instances,
                'reason': reason,
                'execution_id': execution_result.execution_id
            })
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Manual scaling failed: {e}")
            await self._record_event('manual_scaling_failed', {
                'target_instances': target_instances,
                'reason': reason,
                'error': str(e)
            })
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        try:
            recent_events = [
                {
                    'event_type': event.event_type,
                    'timestamp': event.timestamp.isoformat(),
                    'details': event.details
                }
                for event in self.events_history[-10:]  # 최근 10개 이벤트
            ]
            
            return {
                'is_running': self.is_running,
                'region': self.region,
                'monitoring_interval': self.monitoring_interval,
                'enable_auto_scaling': self.enable_auto_scaling,
                'cost_limit_per_hour': self.cost_limit_per_hour,
                'current_hourly_cost': self.current_hourly_cost,
                'last_scaling_time': self.last_scaling_time.isoformat() if self.last_scaling_time else None,
                'total_events': len(self.events_history),
                'recent_events': recent_events
            }
            
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {'error': str(e)}
    
    async def get_detailed_metrics(self) -> Dict[str, Any]:
        """상세 메트릭 조회"""
        try:
            # 현재 메트릭 수집
            current_metrics = await self._collect_current_metrics()
            
            # 예측 조회
            predictions = None
            if current_metrics:
                predictions = await self._get_predictions(current_metrics)
            
            # 비용 정보
            cost_estimate = await self.cloud_executor.get_current_cost_estimate()
            
            # 실행 이력
            execution_history = await self.cloud_executor.get_execution_history(hours=24)
            
            # 결정 이력
            decision_history = self.decision_engine.get_decision_history(hours=24)
            
            return {
                'current_metrics': current_metrics,
                'predictions': predictions,
                'cost_estimate': cost_estimate,
                'execution_history': execution_history[-5:],  # 최근 5개
                'decision_history': decision_history[-5:],    # 최근 5개
                'system_status': self.get_status()
            }
            
        except Exception as e:
            logger.error(f"Failed to get detailed metrics: {e}")
            return {'error': str(e)}
    
    async def update_configuration(self, config_updates: Dict[str, Any]):
        """설정 업데이트"""
        try:
            updated_fields = []
            
            if 'monitoring_interval' in config_updates:
                self.monitoring_interval = max(30, config_updates['monitoring_interval'])  # 최소 30초
                updated_fields.append('monitoring_interval')
            
            if 'enable_auto_scaling' in config_updates:
                self.enable_auto_scaling = bool(config_updates['enable_auto_scaling'])
                updated_fields.append('enable_auto_scaling')
            
            if 'cost_limit_per_hour' in config_updates:
                self.cost_limit_per_hour = max(1.0, config_updates['cost_limit_per_hour'])  # 최소 $1/hour
                updated_fields.append('cost_limit_per_hour')
            
            # 스케일링 임계값 업데이트
            if 'scaling_thresholds' in config_updates:
                self.decision_engine.update_thresholds(config_updates['scaling_thresholds'])
                updated_fields.append('scaling_thresholds')
            
            # 이벤트 기록
            await self._record_event('configuration_updated', {
                'updated_fields': updated_fields,
                'config_updates': config_updates
            })
            
            logger.info(f"Configuration updated: {updated_fields}")
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            raise


# 글로벌 관리자 인스턴스
_global_scaling_manager = None


async def get_scaling_manager(region: str = 'us-west-2') -> IntegratedScalingManager:
    """글로벌 스케일링 관리자 인스턴스 조회"""
    global _global_scaling_manager
    
    if _global_scaling_manager is None:
        _global_scaling_manager = IntegratedScalingManager(region=region)
        logger.info("Global scaling manager created")
    
    return _global_scaling_manager


async def start_auto_scaling(region: str = 'us-west-2'):
    """자동 스케일링 시작"""
    manager = await get_scaling_manager(region)
    await manager.start_monitoring()


def stop_auto_scaling():
    """자동 스케일링 중지"""
    global _global_scaling_manager
    if _global_scaling_manager:
        _global_scaling_manager.stop_monitoring()


if __name__ == "__main__":
    # 테스트 실행
    async def test_integrated_manager():
        manager = await get_scaling_manager()
        
        # 상태 확인
        status = manager.get_status()
        print(f"Manager status: {status}")
        
        # 상세 메트릭 확인
        detailed_metrics = await manager.get_detailed_metrics()
        print(f"Detailed metrics collected: {bool(detailed_metrics)}")
        
        return True
    
    asyncio.run(test_integrated_manager())