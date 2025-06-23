"""
T04_S03_M03: 장애 감지 및 자동 복구 시스템 - 통합 시스템
모든 장애 감지, 복구, 알림, 분석 컴포넌트를 통합하는 메인 시스템
"""

import asyncio
import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# 하위 시스템들 임포트
from dashboard.utils.failure_detector import get_failure_detector, FailureDetector
from dashboard.utils.auto_recovery import get_auto_recovery, AutoRecovery
from dashboard.utils.recovery_orchestrator import get_recovery_orchestrator, RecoveryOrchestrator
from dashboard.utils.alert_manager import get_alert_manager, AlertManager, AlertType
from dashboard.utils.failure_analytics import get_failure_analytics, FailureAnalytics
from dashboard.utils.error_handler import get_error_handler

logger = logging.getLogger(__name__)


class FailureRecoverySystem:
    """장애 감지 및 자동 복구 통합 시스템"""
    
    def __init__(self):
        """통합 시스템 초기화"""
        # 하위 시스템들
        self.failure_detector: FailureDetector = get_failure_detector()
        self.auto_recovery: AutoRecovery = get_auto_recovery()
        self.recovery_orchestrator: RecoveryOrchestrator = get_recovery_orchestrator()
        self.alert_manager: AlertManager = get_alert_manager()
        self.failure_analytics: FailureAnalytics = get_failure_analytics()
        self.error_handler = get_error_handler()
        
        # 시스템 상태
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
        # 통계
        self.system_stats = {
            'total_failures_detected': 0,
            'total_recoveries_attempted': 0,
            'successful_recoveries': 0,
            'escalated_failures': 0,
            'alerts_sent': 0,
            'uptime_seconds': 0
        }
        
        # 설정
        self.config = {
            'enable_auto_recovery': True,
            'enable_alerts': True,
            'enable_analytics': True,
            'health_check_interval': 30,  # 30초
            'analytics_interval': 3600,   # 1시간
            'status_report_interval': 86400,  # 24시간
        }
        
        logger.info("Failure Recovery System initialized")
    
    def start_system(self):
        """전체 시스템 시작"""
        try:
            if self.is_running:
                logger.info("Failure Recovery System is already running")
                return
            
            logger.info("Starting Failure Recovery System...")
            
            # 시스템 상태 설정
            self.is_running = True
            self.start_time = datetime.now()
            
            # 하위 시스템들 시작
            self.failure_detector.start_monitoring()
            self.recovery_orchestrator.start_orchestrator()
            
            # 시스템 상태 확인을 위한 스레드 시작
            self._start_system_monitor()
            
            # 정기 분석을 위한 스레드 시작
            self._start_analytics_scheduler()
            
            # 시작 알림 발송
            asyncio.run(self.alert_manager.send_alert(
                alert_type=AlertType.SYSTEM_STATUS,
                title="Failure Recovery System Started",
                message="자동 장애 감지 및 복구 시스템이 시작되었습니다.",
                source_component="failure_recovery_system",
                context={
                    'start_time': self.start_time.isoformat(),
                    'enabled_features': {
                        'auto_recovery': self.config['enable_auto_recovery'],
                        'alerts': self.config['enable_alerts'],
                        'analytics': self.config['enable_analytics']
                    }
                }
            ))
            
            logger.info("Failure Recovery System started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Failure Recovery System: {e}")
            self.error_handler.handle_error(e, 
                context={'operation': 'system_start'},
                user_message="장애 복구 시스템 시작 중 오류가 발생했습니다."
            )
            raise
    
    def stop_system(self):
        """전체 시스템 중지"""
        try:
            if not self.is_running:
                logger.info("Failure Recovery System is not running")
                return
            
            logger.info("Stopping Failure Recovery System...")
            
            # 시스템 상태 설정
            self.is_running = False
            
            # 하위 시스템들 중지
            self.failure_detector.stop_monitoring()
            self.recovery_orchestrator.stop_orchestrator()
            
            # 중지 알림 발송
            uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0
            
            asyncio.run(self.alert_manager.send_alert(
                alert_type=AlertType.SYSTEM_STATUS,
                title="Failure Recovery System Stopped",
                message=f"자동 장애 감지 및 복구 시스템이 중지되었습니다. (운영 시간: {uptime_hours:.1f}시간)",
                source_component="failure_recovery_system",
                context={
                    'stop_time': datetime.now().isoformat(),
                    'uptime_hours': uptime_hours,
                    'final_stats': self.get_system_statistics()
                }
            ))
            
            logger.info("Failure Recovery System stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop Failure Recovery System: {e}")
            raise
    
    def _start_system_monitor(self):
        """시스템 모니터링 스레드 시작"""
        def monitor_loop():
            while self.is_running:
                try:
                    # 시스템 헬스체크
                    self._perform_system_health_check()
                    
                    # 통계 업데이트
                    self._update_system_stats()
                    
                    time.sleep(self.config['health_check_interval'])
                    
                except Exception as e:
                    logger.error(f"Error in system monitor loop: {e}")
                    time.sleep(60)  # 에러 시 1분 대기
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("System monitor started")
    
    def _start_analytics_scheduler(self):
        """분석 스케줄러 시작"""
        def analytics_loop():
            last_analytics_time = datetime.now()
            last_report_time = datetime.now()
            
            while self.is_running:
                try:
                    current_time = datetime.now()
                    
                    # 정기 분석 실행
                    if (current_time - last_analytics_time).total_seconds() >= self.config['analytics_interval']:
                        if self.config['enable_analytics']:
                            self._run_periodic_analytics()
                        last_analytics_time = current_time
                    
                    # 정기 상태 보고
                    if (current_time - last_report_time).total_seconds() >= self.config['status_report_interval']:
                        asyncio.run(self._send_status_report())
                        last_report_time = current_time
                    
                    time.sleep(300)  # 5분마다 체크
                    
                except Exception as e:
                    logger.error(f"Error in analytics scheduler: {e}")
                    time.sleep(600)  # 에러 시 10분 대기
        
        analytics_thread = threading.Thread(target=analytics_loop, daemon=True)
        analytics_thread.start()
        logger.info("Analytics scheduler started")
    
    def _perform_system_health_check(self):
        """시스템 헬스체크 수행"""
        try:
            health_issues = []
            
            # 각 하위 시스템 상태 확인
            if not self.failure_detector.is_monitoring:
                health_issues.append("Failure detector is not monitoring")
            
            if not self.recovery_orchestrator.is_running:
                health_issues.append("Recovery orchestrator is not running")
            
            # 활성 세션 수 확인
            active_sessions = self.recovery_orchestrator.get_active_sessions()
            if len(active_sessions) > 10:
                health_issues.append(f"Too many active recovery sessions: {len(active_sessions)}")
            
            # 장기간 실행 중인 세션 확인
            for session in active_sessions:
                try:
                    start_time = datetime.fromisoformat(session['start_time'])
                    if (datetime.now() - start_time).total_seconds() > 3600:  # 1시간 이상
                        health_issues.append(f"Long-running recovery session: {session['session_id']}")
                except Exception:
                    continue
            
            # 문제가 발견된 경우 알림
            if health_issues and self.config['enable_alerts']:
                asyncio.run(self.alert_manager.send_alert(
                    alert_type=AlertType.SYSTEM_STATUS,
                    title="System Health Issues Detected",
                    message=f"시스템 헬스체크에서 {len(health_issues)}개의 문제가 발견되었습니다.",
                    source_component="failure_recovery_system",
                    context={'health_issues': health_issues}
                ))
            
        except Exception as e:
            logger.error(f"Failed to perform system health check: {e}")
    
    def _update_system_stats(self):
        """시스템 통계 업데이트"""
        try:
            # 업타임 계산
            if self.start_time:
                self.system_stats['uptime_seconds'] = (datetime.now() - self.start_time).total_seconds()
            
            # 하위 시스템들로부터 통계 수집
            try:
                failure_stats = self.failure_detector.get_failure_statistics()
                self.system_stats['total_failures_detected'] = failure_stats.get('total_failures', 0)
            except Exception:
                pass
            
            try:
                recovery_stats = self.auto_recovery.get_recovery_statistics()
                self.system_stats['total_recoveries_attempted'] = recovery_stats.get('total_attempts', 0)
                self.system_stats['successful_recoveries'] = recovery_stats.get('successful_attempts', 0)
            except Exception:
                pass
            
            try:
                orchestrator_stats = self.recovery_orchestrator.get_orchestrator_statistics()
                self.system_stats['escalated_failures'] = orchestrator_stats.get('escalations', {}).get('total', 0)
            except Exception:
                pass
            
            try:
                alert_stats = self.alert_manager.get_alert_statistics()
                self.system_stats['alerts_sent'] = alert_stats.get('total_alerts', 0)
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Failed to update system stats: {e}")
    
    def _run_periodic_analytics(self):
        """정기 분석 실행"""
        try:
            logger.info("Running periodic failure analytics...")
            
            # 트렌드 분석
            trend_analysis = self.failure_analytics.analyze_failure_trends(7)  # 7일
            
            # 패턴 감지
            patterns = self.failure_analytics.detect_failure_patterns(30)  # 30일
            
            # 예측 분석
            predictions = self.failure_analytics.predict_future_failures(7)  # 7일 앞
            
            # 중요한 발견사항이 있으면 알림
            if self.config['enable_alerts']:
                self._send_analytics_alerts(trend_analysis, patterns, predictions)
            
            logger.info(f"Periodic analytics completed: {len(patterns)} patterns, {len(predictions)} predictions")
            
        except Exception as e:
            logger.error(f"Failed to run periodic analytics: {e}")
    
    def _send_analytics_alerts(self, trend_analysis, patterns, predictions):
        """분석 결과 기반 알림 발송"""
        try:
            # 증가 트렌드 알림
            if trend_analysis.trend_direction.value == 'increasing' and trend_analysis.trend_percentage > 20:
                asyncio.run(self.alert_manager.send_alert(
                    alert_type=AlertType.SYSTEM_STATUS,
                    title="Increasing Failure Trend Detected",
                    message=f"장애 발생률이 {trend_analysis.trend_percentage:.1f}% 증가하고 있습니다.",
                    source_component="failure_analytics",
                    context={'trend_analysis': trend_analysis.__dict__}
                ))
            
            # 새 패턴 발견 알림
            if patterns:
                high_confidence_patterns = [p for p in patterns if p.confidence_score > 0.8]
                if high_confidence_patterns:
                    asyncio.run(self.alert_manager.send_alert(
                        alert_type=AlertType.SYSTEM_STATUS,
                        title="New Failure Patterns Detected",
                        message=f"{len(high_confidence_patterns)}개의 새로운 장애 패턴이 감지되었습니다.",
                        source_component="failure_analytics",
                        context={'pattern_count': len(high_confidence_patterns)}
                    ))
            
            # 고위험 예측 알림
            high_risk_predictions = [p for p in predictions if p.get('probability', 0) > 0.7]
            if high_risk_predictions:
                components = [p['component'] for p in high_risk_predictions]
                asyncio.run(self.alert_manager.send_alert(
                    alert_type=AlertType.SYSTEM_STATUS,
                    title="High Risk Failure Predictions",
                    message=f"다음 컴포넌트들의 장애 위험이 높습니다: {', '.join(components)}",
                    source_component="failure_analytics",
                    context={'high_risk_components': components}
                ))
                
        except Exception as e:
            logger.error(f"Failed to send analytics alerts: {e}")
    
    async def _send_status_report(self):
        """정기 상태 보고 발송"""
        try:
            # 종합 보고서 생성
            report = self.failure_analytics.get_failure_report(7)  # 지난 7일
            system_stats = self.get_system_statistics()
            
            await self.alert_manager.send_alert(
                alert_type=AlertType.SYSTEM_STATUS,
                title="Daily System Status Report",
                message="일일 시스템 상태 보고서가 생성되었습니다.",
                source_component="failure_recovery_system",
                context={
                    'system_stats': system_stats,
                    'failure_report_summary': report.get('summary', {}),
                    'uptime_hours': system_stats.get('uptime_hours', 0)
                }
            )
            
            logger.info("Daily status report sent")
            
        except Exception as e:
            logger.error(f"Failed to send status report: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """전체 시스템 상태 조회"""
        try:
            return {
                'is_running': self.is_running,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0,
                'subsystems': {
                    'failure_detector': {
                        'monitoring': self.failure_detector.is_monitoring,
                        'active_monitors': len(self.failure_detector.monitors),
                        'enabled_monitors': len([m for m in self.failure_detector.monitors.values() if m['enabled']])
                    },
                    'recovery_orchestrator': {
                        'running': self.recovery_orchestrator.is_running,
                        'active_sessions': len(self.recovery_orchestrator.get_active_sessions())
                    },
                    'alert_manager': {
                        'enabled_channels': len([n for n in self.alert_manager.notifiers.values() 
                                               if getattr(n, 'enabled', True)])
                    }
                },
                'configuration': self.config.copy(),
                'statistics': self.get_system_statistics()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {'error': str(e)}
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """시스템 통계 조회"""
        try:
            self._update_system_stats()
            
            stats = self.system_stats.copy()
            
            # 추가 계산된 지표
            if stats['total_recoveries_attempted'] > 0:
                stats['recovery_success_rate'] = stats['successful_recoveries'] / stats['total_recoveries_attempted']
            else:
                stats['recovery_success_rate'] = 0.0
            
            if self.start_time:
                stats['uptime_hours'] = (datetime.now() - self.start_time).total_seconds() / 3600
            else:
                stats['uptime_hours'] = 0.0
            
            # 일일 평균 계산
            if stats['uptime_hours'] > 0:
                stats['failures_per_day'] = stats['total_failures_detected'] / (stats['uptime_hours'] / 24)
                stats['recoveries_per_day'] = stats['total_recoveries_attempted'] / (stats['uptime_hours'] / 24)
            else:
                stats['failures_per_day'] = 0.0
                stats['recoveries_per_day'] = 0.0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get system statistics: {e}")
            return {'error': str(e)}
    
    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """시스템 설정 업데이트"""
        try:
            # 설정 검증
            valid_keys = set(self.config.keys())
            invalid_keys = set(new_config.keys()) - valid_keys
            
            if invalid_keys:
                logger.warning(f"Invalid configuration keys ignored: {invalid_keys}")
            
            # 유효한 설정만 업데이트
            for key, value in new_config.items():
                if key in valid_keys:
                    old_value = self.config[key]
                    self.config[key] = value
                    logger.info(f"Configuration updated: {key} = {value} (was {old_value})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            return False
    
    def trigger_manual_recovery(self, component: str, failure_type: str = "manual_trigger") -> str:
        """수동 복구 트리거"""
        try:
            from dashboard.utils.failure_detector import FailureEvent, FailureType, FailureSeverity
            
            # 수동 장애 이벤트 생성
            manual_failure = FailureEvent(
                failure_type=getattr(FailureType, failure_type.upper(), FailureType.SERVER_UNRESPONSIVE),
                component=component,
                severity=FailureSeverity.MEDIUM,
                message=f"Manual recovery triggered for {component}",
                timestamp=datetime.now(),
                context={'manual_trigger': True, 'triggered_by': 'operator'}
            )
            
            # 복구 오케스트레이터에 전달
            session_id = asyncio.run(self.recovery_orchestrator.handle_failure(manual_failure))
            
            logger.info(f"Manual recovery triggered for {component}: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to trigger manual recovery: {e}")
            self.error_handler.handle_error(e,
                context={'component': component, 'failure_type': failure_type},
                user_message="수동 복구 실행 중 오류가 발생했습니다."
            )
            raise
    
    def get_comprehensive_report(self, days: int = 7) -> Dict[str, Any]:
        """종합 시스템 보고서 생성"""
        try:
            # 각 하위 시스템 보고서 수집
            system_status = self.get_system_status()
            failure_report = self.failure_analytics.get_failure_report(days)
            
            # 하위 시스템 통계들
            failure_stats = self.failure_detector.get_failure_statistics(days)
            recovery_stats = self.auto_recovery.get_recovery_statistics(days)
            orchestrator_stats = self.recovery_orchestrator.get_orchestrator_statistics(days)
            alert_stats = self.alert_manager.get_alert_statistics(days)
            
            # 종합 보고서 구성
            report = {
                'report_metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'period_days': days,
                    'system_version': '1.0.0',
                    'report_type': 'comprehensive_system_report'
                },
                'system_overview': system_status,
                'failure_analysis': failure_report,
                'subsystem_statistics': {
                    'failure_detection': failure_stats,
                    'auto_recovery': recovery_stats,
                    'orchestrator': orchestrator_stats,
                    'alerts': alert_stats
                },
                'key_metrics': {
                    'system_availability': self._calculate_availability(days),
                    'mttr_minutes': self._calculate_mttr(days),
                    'mtbf_hours': self._calculate_mtbf(days),
                    'recovery_success_rate': recovery_stats.get('success_rate', 0),
                    'alert_delivery_rate': self._calculate_alert_delivery_rate(alert_stats)
                },
                'recommendations': self._generate_system_recommendations(
                    failure_report, recovery_stats, orchestrator_stats
                )
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate comprehensive report: {e}")
            return {'error': str(e)}
    
    def _calculate_availability(self, days: int) -> float:
        """시스템 가용성 계산"""
        try:
            total_minutes = days * 24 * 60
            failure_stats = self.failure_detector.get_failure_statistics(days)
            total_failures = failure_stats.get('total_failures', 0)
            
            # 간단한 추정: 각 장애당 평균 5분 다운타임
            estimated_downtime_minutes = total_failures * 5
            
            availability = max(0, (total_minutes - estimated_downtime_minutes) / total_minutes * 100)
            return min(availability, 100)
            
        except Exception:
            return 99.0  # 기본값
    
    def _calculate_mttr(self, days: int) -> float:
        """평균 복구 시간 계산 (분)"""
        try:
            recovery_stats = self.auto_recovery.get_recovery_statistics(days)
            return recovery_stats.get('avg_execution_time', 15.0)  # 기본값 15분
        except Exception:
            return 15.0
    
    def _calculate_mtbf(self, days: int) -> float:
        """평균 장애 간격 계산 (시간)"""
        try:
            failure_stats = self.failure_detector.get_failure_statistics(days)
            total_failures = failure_stats.get('total_failures', 0)
            
            if total_failures > 0:
                total_hours = days * 24
                return total_hours / total_failures
            else:
                return days * 24  # 장애가 없으면 전체 기간
                
        except Exception:
            return 72.0  # 기본값 72시간
    
    def _calculate_alert_delivery_rate(self, alert_stats: Dict) -> float:
        """알림 전송 성공률 계산"""
        try:
            channel_stats = alert_stats.get('channel_statistics', [])
            if not channel_stats:
                return 100.0
            
            total_attempts = sum(stat.get('total_attempts', 0) for stat in channel_stats)
            successful_attempts = sum(stat.get('successful_attempts', 0) for stat in channel_stats)
            
            if total_attempts > 0:
                return (successful_attempts / total_attempts) * 100
            else:
                return 100.0
                
        except Exception:
            return 100.0
    
    def _generate_system_recommendations(
        self, 
        failure_report: Dict, 
        recovery_stats: Dict, 
        orchestrator_stats: Dict
    ) -> List[str]:
        """시스템 권장사항 생성"""
        recommendations = []
        
        try:
            # 복구 성공률 기반 권장사항
            success_rate = recovery_stats.get('success_rate', 0)
            if success_rate < 80:
                recommendations.append(f"복구 성공률이 {success_rate:.1f}%로 낮습니다. 복구 전략을 검토하세요.")
            
            # 에스컬레이션 비율 기반 권장사항
            escalations = orchestrator_stats.get('escalations', {})
            total_escalations = escalations.get('total', 0)
            if total_escalations > 5:
                recommendations.append(f"에스컬레이션이 {total_escalations}건 발생했습니다. 자동 복구 로직을 개선하세요.")
            
            # 장애 보고서의 권장사항 포함
            if 'comprehensive_recommendations' in failure_report:
                recommendations.extend(failure_report['comprehensive_recommendations'])
            
            # 기본 권장사항
            if not recommendations:
                recommendations.append("시스템이 안정적으로 운영되고 있습니다. 정기적인 모니터링을 지속하세요.")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate system recommendations: {e}")
            return ["권장사항 생성 중 오류가 발생했습니다."]


# 전역 통합 시스템 인스턴스
_failure_recovery_system = None


def get_failure_recovery_system() -> FailureRecoverySystem:
    """싱글톤 장애 복구 시스템 반환"""
    global _failure_recovery_system
    if _failure_recovery_system is None:
        _failure_recovery_system = FailureRecoverySystem()
    return _failure_recovery_system


# 편의 함수들
def start_failure_recovery_system():
    """장애 복구 시스템 시작"""
    system = get_failure_recovery_system()
    system.start_system()


def stop_failure_recovery_system():
    """장애 복구 시스템 중지"""
    system = get_failure_recovery_system()
    system.stop_system()


def get_system_status() -> Dict[str, Any]:
    """시스템 상태 조회"""
    system = get_failure_recovery_system()
    return system.get_system_status()


def trigger_manual_recovery(component: str, failure_type: str = "manual_trigger") -> str:
    """수동 복구 트리거"""
    system = get_failure_recovery_system()
    return system.trigger_manual_recovery(component, failure_type)