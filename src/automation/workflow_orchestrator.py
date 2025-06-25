"""
고도화된 워크플로우 자동화 시스템

95% 자동화율을 목표로 하는 지능형 워크플로우 오케스트레이터입니다.
운영자 개입을 최소화하고 품질 관리를 자동화합니다.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import queue
import threading

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """워크플로우 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AutomationLevel(Enum):
    """자동화 레벨"""
    FULL_AUTO = "full_auto"      # 완전 자동
    SEMI_AUTO = "semi_auto"      # 반자동 (중요 결정만 사람)
    MANUAL = "manual"            # 수동
    SUPERVISED = "supervised"    # 감독 하에 자동


class DecisionPoint(Enum):
    """의사결정 지점"""
    PPL_CLASSIFICATION = "ppl_classification"
    CHANNEL_APPROVAL = "channel_approval"
    CONTENT_QUALITY = "content_quality"
    REVENUE_THRESHOLD = "revenue_threshold"
    RISK_ASSESSMENT = "risk_assessment"


@dataclass
class WorkflowStep:
    """워크플로우 단계"""
    step_id: str
    name: str
    function: Callable
    parameters: Dict[str, Any]
    automation_level: AutomationLevel
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    dependencies: List[str] = field(default_factory=list)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    failure_handlers: List[Callable] = field(default_factory=list)


@dataclass
class WorkflowExecution:
    """워크플로우 실행 정보"""
    execution_id: str
    workflow_name: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    current_step: Optional[str] = None
    results: Dict[str, Any] = field(default_factory=dict)
    automation_rate: float = 0.0
    human_interventions: List[Dict] = field(default_factory=list)


class AutoDecisionEngine:
    """자동 의사결정 엔진"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.decision_rules = self._initialize_decision_rules()
        self.confidence_thresholds = self._initialize_confidence_thresholds()
        self.performance_history = []
    
    def _initialize_decision_rules(self) -> Dict[DecisionPoint, Dict]:
        """의사결정 규칙 초기화"""
        return {
            DecisionPoint.PPL_CLASSIFICATION: {
                'auto_approve_threshold': 0.95,    # 95% 이상 신뢰도면 자동 승인
                'auto_reject_threshold': 0.05,     # 5% 이하 신뢰도면 자동 거부
                'manual_review_range': (0.05, 0.95), # 중간 영역은 수동 검토
                'risk_factors_limit': 2             # 위험 요소 2개 이하만 자동 처리
            },
            DecisionPoint.CHANNEL_APPROVAL: {
                'auto_approve_score': 75,           # 75점 이상 자동 승인
                'auto_reject_score': 30,            # 30점 이하 자동 거부
                'required_metrics': ['quality_score', 'potential_score', 'monetization_score'],
                'minimum_confidence': 0.7
            },
            DecisionPoint.CONTENT_QUALITY: {
                'auto_approve_quality': 0.8,       # 품질 점수 0.8 이상
                'content_safety_required': True,   # 콘텐츠 안전성 필수
                'brand_alignment_minimum': 0.6     # 브랜드 정렬성 최소 0.6
            },
            DecisionPoint.REVENUE_THRESHOLD: {
                'minimum_roi': 150,                 # 최소 ROI 150%
                'minimum_revenue': 50000,           # 최소 예상 수익 5만원
                'payback_period_max': 60,           # 최대 회수 기간 60일
                'confidence_minimum': 0.6           # 예측 신뢰도 최소 0.6
            },
            DecisionPoint.RISK_ASSESSMENT: {
                'acceptable_risk_score': 0.3,      # 허용 위험 점수
                'critical_risk_factors': [         # 치명적 위험 요소
                    'brand_safety_violation',
                    'legal_compliance_issue',
                    'fake_engagement'
                ],
                'auto_mitigation_enabled': True     # 자동 위험 완화
            }
        }
    
    def _initialize_confidence_thresholds(self) -> Dict[AutomationLevel, float]:
        """자동화 레벨별 신뢰도 임계값"""
        return {
            AutomationLevel.FULL_AUTO: 0.95,     # 95% 이상 신뢰도 필요
            AutomationLevel.SEMI_AUTO: 0.8,      # 80% 이상 신뢰도 필요
            AutomationLevel.SUPERVISED: 0.6,     # 60% 이상 신뢰도 필요
            AutomationLevel.MANUAL: 0.0          # 신뢰도 무관
        }
    
    def make_decision(
        self, 
        decision_point: DecisionPoint,
        data: Dict[str, Any],
        automation_level: AutomationLevel = AutomationLevel.SEMI_AUTO
    ) -> Tuple[str, Dict[str, Any]]:
        """자동 의사결정"""
        
        try:
            rules = self.decision_rules.get(decision_point)
            if not rules:
                return "manual_review", {"reason": "No rules defined"}
            
            # 신뢰도 확인
            confidence = data.get('confidence', 0.0)
            required_confidence = self.confidence_thresholds.get(automation_level, 0.8)
            
            if confidence < required_confidence:
                return "manual_review", {
                    "reason": "Insufficient confidence",
                    "confidence": confidence,
                    "required": required_confidence
                }
            
            # 의사결정 지점별 로직
            if decision_point == DecisionPoint.PPL_CLASSIFICATION:
                return self._decide_ppl_classification(data, rules)
            
            elif decision_point == DecisionPoint.CHANNEL_APPROVAL:
                return self._decide_channel_approval(data, rules)
            
            elif decision_point == DecisionPoint.CONTENT_QUALITY:
                return self._decide_content_quality(data, rules)
            
            elif decision_point == DecisionPoint.REVENUE_THRESHOLD:
                return self._decide_revenue_threshold(data, rules)
            
            elif decision_point == DecisionPoint.RISK_ASSESSMENT:
                return self._decide_risk_assessment(data, rules)
            
            else:
                return "manual_review", {"reason": "Unknown decision point"}
                
        except Exception as e:
            self.logger.error(f"의사결정 오류: {str(e)}")
            return "manual_review", {"reason": f"Decision error: {str(e)}"}
    
    def _decide_ppl_classification(self, data: Dict, rules: Dict) -> Tuple[str, Dict]:
        """PPL 분류 의사결정"""
        
        probability = data.get('probability_score', 0.0)
        confidence = data.get('confidence', 0.0)
        risk_factors = data.get('risk_factors', [])
        
        # 자동 거부 조건
        if (probability <= rules['auto_reject_threshold'] and 
            confidence >= rules['auto_approve_threshold']):
            return "auto_approve_organic", {
                "reason": "High confidence organic content",
                "probability": probability,
                "confidence": confidence
            }
        
        # 자동 필터링 조건
        if (probability >= rules['auto_approve_threshold'] and
            len(risk_factors) <= rules['risk_factors_limit']):
            return "auto_filter_ppl", {
                "reason": "High confidence PPL detection",
                "probability": probability,
                "risk_factors": risk_factors
            }
        
        # 수동 검토 필요
        return "manual_review", {
            "reason": "Requires human judgment",
            "probability": probability,
            "confidence": confidence,
            "risk_factors": risk_factors
        }
    
    def _decide_channel_approval(self, data: Dict, rules: Dict) -> Tuple[str, Dict]:
        """채널 승인 의사결정"""
        
        total_score = data.get('total_score', 0)
        confidence = data.get('confidence', 0.0)
        
        # 필수 메트릭 확인
        missing_metrics = []
        for metric in rules['required_metrics']:
            if metric not in data:
                missing_metrics.append(metric)
        
        if missing_metrics:
            return "manual_review", {
                "reason": "Missing required metrics",
                "missing_metrics": missing_metrics
            }
        
        # 자동 승인 조건
        if (total_score >= rules['auto_approve_score'] and
            confidence >= rules['minimum_confidence']):
            return "auto_approve", {
                "reason": "High score and confidence",
                "total_score": total_score,
                "confidence": confidence
            }
        
        # 자동 거부 조건
        if total_score <= rules['auto_reject_score']:
            return "auto_reject", {
                "reason": "Score below threshold",
                "total_score": total_score,
                "threshold": rules['auto_reject_score']
            }
        
        # 수동 검토
        return "manual_review", {
            "reason": "Score in manual review range",
            "total_score": total_score
        }
    
    def _decide_content_quality(self, data: Dict, rules: Dict) -> Tuple[str, Dict]:
        """콘텐츠 품질 의사결정"""
        
        quality_score = data.get('quality_score', 0.0)
        safety_score = data.get('safety_score', 0.0)
        brand_alignment = data.get('brand_alignment', 0.0)
        
        # 품질 기준 확인
        quality_pass = quality_score >= rules['auto_approve_quality']
        safety_pass = safety_score >= 0.8 if rules['content_safety_required'] else True
        brand_pass = brand_alignment >= rules['brand_alignment_minimum']
        
        if quality_pass and safety_pass and brand_pass:
            return "auto_approve", {
                "reason": "All quality criteria met",
                "quality_score": quality_score,
                "safety_score": safety_score,
                "brand_alignment": brand_alignment
            }
        
        # 품질 이슈 상세 분석
        issues = []
        if not quality_pass:
            issues.append(f"Quality score {quality_score} below {rules['auto_approve_quality']}")
        if not safety_pass:
            issues.append(f"Safety concerns detected")
        if not brand_pass:
            issues.append(f"Brand alignment {brand_alignment} below {rules['brand_alignment_minimum']}")
        
        return "manual_review", {
            "reason": "Quality issues detected",
            "issues": issues
        }
    
    def _decide_revenue_threshold(self, data: Dict, rules: Dict) -> Tuple[str, Dict]:
        """수익 임계값 의사결정"""
        
        roi = data.get('roi_percentage', 0)
        revenue = data.get('predicted_revenue', 0)
        payback_period = data.get('payback_period_days', 365)
        confidence = data.get('confidence_score', 0.0)
        
        # 수익성 기준 확인
        roi_pass = roi >= rules['minimum_roi']
        revenue_pass = revenue >= rules['minimum_revenue']
        payback_pass = payback_period <= rules['payback_period_max']
        confidence_pass = confidence >= rules['confidence_minimum']
        
        if roi_pass and revenue_pass and payback_pass and confidence_pass:
            return "auto_approve", {
                "reason": "Revenue criteria met",
                "roi": roi,
                "revenue": revenue,
                "payback_period": payback_period
            }
        
        # 수익성 이슈 분석
        issues = []
        if not roi_pass:
            issues.append(f"ROI {roi}% below minimum {rules['minimum_roi']}%")
        if not revenue_pass:
            issues.append(f"Revenue {revenue} below minimum {rules['minimum_revenue']}")
        if not payback_pass:
            issues.append(f"Payback period {payback_period} days exceeds {rules['payback_period_max']}")
        if not confidence_pass:
            issues.append(f"Prediction confidence {confidence} below {rules['confidence_minimum']}")
        
        return "manual_review", {
            "reason": "Revenue criteria not met",
            "issues": issues
        }
    
    def _decide_risk_assessment(self, data: Dict, rules: Dict) -> Tuple[str, Dict]:
        """위험 평가 의사결정"""
        
        risk_score = data.get('risk_score', 0.5)
        risk_factors = data.get('risk_factors', [])
        
        # 치명적 위험 요소 확인
        critical_risks = [risk for risk in risk_factors 
                         if risk in rules['critical_risk_factors']]
        
        if critical_risks:
            return "auto_reject", {
                "reason": "Critical risk factors detected",
                "critical_risks": critical_risks
            }
        
        # 일반 위험 평가
        if risk_score <= rules['acceptable_risk_score']:
            return "auto_approve", {
                "reason": "Risk within acceptable limits",
                "risk_score": risk_score,
                "risk_factors": risk_factors
            }
        
        # 자동 위험 완화 가능한지 확인
        if rules['auto_mitigation_enabled']:
            mitigation_suggestions = self._generate_mitigation_suggestions(risk_factors)
            if mitigation_suggestions:
                return "auto_mitigate", {
                    "reason": "Risk can be automatically mitigated",
                    "risk_score": risk_score,
                    "mitigation_suggestions": mitigation_suggestions
                }
        
        return "manual_review", {
            "reason": "Risk requires human assessment",
            "risk_score": risk_score,
            "risk_factors": risk_factors
        }
    
    def _generate_mitigation_suggestions(self, risk_factors: List[str]) -> List[str]:
        """위험 완화 제안 생성"""
        
        mitigation_map = {
            'high_price_sensitivity': '할인 쿠폰 제공',
            'seasonal_decline': '시즌 종료 후 재실행 스케줄링',
            'low_engagement_rate': '콘텐츠 형식 다양화',
            'competitor_presence': '차별화 메시지 강화'
        }
        
        suggestions = []
        for risk in risk_factors:
            if risk in mitigation_map:
                suggestions.append(mitigation_map[risk])
        
        return suggestions
    
    def update_performance_feedback(
        self, 
        decision_point: DecisionPoint,
        predicted_outcome: str,
        actual_outcome: str,
        data: Dict[str, Any]
    ):
        """성능 피드백 업데이트"""
        
        feedback = {
            'timestamp': datetime.now().isoformat(),
            'decision_point': decision_point.value,
            'predicted_outcome': predicted_outcome,
            'actual_outcome': actual_outcome,
            'is_correct': predicted_outcome == actual_outcome,
            'data': data
        }
        
        self.performance_history.append(feedback)
        
        # 성능 기반 규칙 조정 (적응적 학습)
        if len(self.performance_history) >= 100:
            self._adjust_decision_rules()
    
    def _adjust_decision_rules(self):
        """의사결정 규칙 조정"""
        
        recent_performance = self.performance_history[-100:]
        
        # 의사결정 지점별 정확도 계산
        for decision_point in DecisionPoint:
            point_feedback = [f for f in recent_performance 
                            if f['decision_point'] == decision_point.value]
            
            if len(point_feedback) >= 10:
                accuracy = sum(1 for f in point_feedback if f['is_correct']) / len(point_feedback)
                
                # 정확도가 90% 미만이면 더 보수적으로 조정
                if accuracy < 0.9:
                    self._make_rules_more_conservative(decision_point)
                    self.logger.info(f"의사결정 규칙 조정: {decision_point.value} - 정확도 {accuracy:.2%}")
    
    def _make_rules_more_conservative(self, decision_point: DecisionPoint):
        """규칙을 더 보수적으로 조정"""
        
        rules = self.decision_rules.get(decision_point)
        if not rules:
            return
        
        if decision_point == DecisionPoint.PPL_CLASSIFICATION:
            rules['auto_approve_threshold'] = min(rules['auto_approve_threshold'] + 0.01, 0.99)
            rules['auto_reject_threshold'] = max(rules['auto_reject_threshold'] - 0.01, 0.01)
        
        elif decision_point == DecisionPoint.CHANNEL_APPROVAL:
            rules['auto_approve_score'] = min(rules['auto_approve_score'] + 2, 95)
            rules['minimum_confidence'] = min(rules['minimum_confidence'] + 0.05, 0.95)
        
        elif decision_point == DecisionPoint.REVENUE_THRESHOLD:
            rules['minimum_roi'] = min(rules['minimum_roi'] + 10, 300)
            rules['confidence_minimum'] = min(rules['confidence_minimum'] + 0.05, 0.9)


class WorkflowOrchestrator:
    """워크플로우 오케스트레이터"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.decision_engine = AutoDecisionEngine()
        self.active_executions = {}
        self.workflow_templates = self._initialize_workflow_templates()
        self.automation_metrics = {
            'total_decisions': 0,
            'automated_decisions': 0,
            'manual_interventions': 0,
            'automation_rate': 0.0
        }
        
        # 비동기 작업 큐
        self.task_queue = queue.Queue()
        self.worker_pool = ThreadPoolExecutor(max_workers=10)
        
        # 모니터링 스레드
        self._start_monitoring_thread()
    
    def _initialize_workflow_templates(self) -> Dict[str, List[WorkflowStep]]:
        """워크플로우 템플릿 초기화"""
        
        return {
            'channel_discovery_pipeline': [
                WorkflowStep(
                    step_id='rss_collection',
                    name='RSS 데이터 수집',
                    function=self._mock_rss_collection,
                    parameters={'sources': 'all'},
                    automation_level=AutomationLevel.FULL_AUTO
                ),
                WorkflowStep(
                    step_id='channel_discovery',
                    name='채널 발견',
                    function=self._mock_channel_discovery,
                    parameters={'search_terms': []},
                    automation_level=AutomationLevel.FULL_AUTO,
                    dependencies=['rss_collection']
                ),
                WorkflowStep(
                    step_id='ppl_filtering',
                    name='PPL 콘텐츠 필터링',
                    function=self._mock_ppl_filtering,
                    parameters={},
                    automation_level=AutomationLevel.SEMI_AUTO,
                    dependencies=['channel_discovery']
                ),
                WorkflowStep(
                    step_id='channel_scoring',
                    name='채널 점수 계산',
                    function=self._mock_channel_scoring,
                    parameters={},
                    automation_level=AutomationLevel.FULL_AUTO,
                    dependencies=['ppl_filtering']
                ),
                WorkflowStep(
                    step_id='revenue_prediction',
                    name='수익 예측',
                    function=self._mock_revenue_prediction,
                    parameters={},
                    automation_level=AutomationLevel.SEMI_AUTO,
                    dependencies=['channel_scoring']
                ),
                WorkflowStep(
                    step_id='final_approval',
                    name='최종 승인',
                    function=self._mock_final_approval,
                    parameters={},
                    automation_level=AutomationLevel.SUPERVISED,
                    dependencies=['revenue_prediction']
                )
            ]
        }
    
    def _start_monitoring_thread(self):
        """모니터링 스레드 시작"""
        
        def monitor_executions():
            while True:
                try:
                    # 실행 중인 워크플로우 모니터링
                    for execution_id, execution in list(self.active_executions.items()):
                        if execution.status == WorkflowStatus.RUNNING:
                            self._check_execution_health(execution)
                    
                    # 메트릭 업데이트
                    self._update_automation_metrics()
                    
                    time.sleep(30)  # 30초마다 체크
                    
                except Exception as e:
                    self.logger.error(f"모니터링 스레드 오류: {str(e)}")
        
        monitoring_thread = threading.Thread(target=monitor_executions, daemon=True)
        monitoring_thread.start()
    
    def execute_workflow(
        self, 
        workflow_name: str, 
        parameters: Dict[str, Any] = None,
        automation_level: AutomationLevel = AutomationLevel.SEMI_AUTO
    ) -> str:
        """워크플로우 실행"""
        
        try:
            # 실행 ID 생성
            execution_id = f"{workflow_name}_{int(time.time())}"
            
            # 워크플로우 템플릿 가져오기
            workflow_steps = self.workflow_templates.get(workflow_name)
            if not workflow_steps:
                raise ValueError(f"Unknown workflow: {workflow_name}")
            
            # 실행 정보 생성
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_name=workflow_name,
                status=WorkflowStatus.PENDING,
                started_at=datetime.now()
            )
            
            self.active_executions[execution_id] = execution
            
            # 비동기 실행 시작
            self.worker_pool.submit(
                self._execute_workflow_async, 
                execution_id, 
                workflow_steps, 
                parameters or {}, 
                automation_level
            )
            
            self.logger.info(f"워크플로우 실행 시작: {execution_id}")
            return execution_id
            
        except Exception as e:
            self.logger.error(f"워크플로우 실행 오류: {str(e)}")
            raise
    
    def _execute_workflow_async(
        self, 
        execution_id: str, 
        workflow_steps: List[WorkflowStep],
        parameters: Dict[str, Any],
        automation_level: AutomationLevel
    ):
        """비동기 워크플로우 실행"""
        
        execution = self.active_executions[execution_id]
        execution.status = WorkflowStatus.RUNNING
        
        try:
            # 의존성 그래프 기반 실행 순서 결정
            execution_order = self._resolve_dependencies(workflow_steps)
            
            for step_id in execution_order:
                step = next(s for s in workflow_steps if s.step_id == step_id)
                execution.current_step = step_id
                
                # 단계 실행
                step_result = self._execute_step(step, execution, parameters, automation_level)
                
                if step_result['success']:
                    execution.steps_completed.append(step_id)
                    execution.results[step_id] = step_result['data']
                else:
                    execution.steps_failed.append(step_id)
                    if step_result.get('critical_failure', False):
                        break
            
            # 실행 완료
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()
            
            # 자동화율 계산
            execution.automation_rate = self._calculate_automation_rate(execution)
            
            self.logger.info(
                f"워크플로우 완료: {execution_id} - "
                f"자동화율: {execution.automation_rate:.1%}"
            )
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.completed_at = datetime.now()
            self.logger.error(f"워크플로우 실행 실패: {execution_id} - {str(e)}")
    
    def _resolve_dependencies(self, steps: List[WorkflowStep]) -> List[str]:
        """의존성 해결하여 실행 순서 결정"""
        
        # 토폴로지 정렬 구현
        in_degree = {step.step_id: len(step.dependencies) for step in steps}
        queue_steps = [step.step_id for step in steps if in_degree[step.step_id] == 0]
        result = []
        
        while queue_steps:
            current = queue_steps.pop(0)
            result.append(current)
            
            # 의존성 제거
            for step in steps:
                if current in step.dependencies:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue_steps.append(step.step_id)
        
        return result
    
    def _execute_step(
        self, 
        step: WorkflowStep, 
        execution: WorkflowExecution,
        parameters: Dict[str, Any],
        automation_level: AutomationLevel
    ) -> Dict[str, Any]:
        """워크플로우 단계 실행"""
        
        try:
            self.logger.info(f"단계 실행: {step.step_id} - {step.name}")
            
            # 단계별 파라미터 준비
            step_params = {**parameters, **step.parameters}
            step_params['execution_context'] = {
                'execution_id': execution.execution_id,
                'previous_results': execution.results
            }
            
            # 함수 실행
            start_time = time.time()
            result = step.function(step_params)
            execution_time = time.time() - start_time
            
            # 성공 기준 확인
            if step.success_criteria:
                success = self._check_success_criteria(result, step.success_criteria)
            else:
                success = result.get('success', True)
            
            # 자동화 레벨에 따른 처리
            if not success and step.automation_level != AutomationLevel.FULL_AUTO:
                # 사람의 개입 필요
                intervention_result = self._request_human_intervention(
                    step, result, execution, automation_level
                )
                
                if intervention_result['approved']:
                    success = True
                    result.update(intervention_result['modifications'])
            
            return {
                'success': success,
                'data': result,
                'execution_time': execution_time,
                'automation_level': step.automation_level.value
            }
            
        except Exception as e:
            self.logger.error(f"단계 실행 오류 {step.step_id}: {str(e)}")
            
            # 재시도 로직
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                self.logger.info(f"단계 재시도: {step.step_id} ({step.retry_count}/{step.max_retries})")
                return self._execute_step(step, execution, parameters, automation_level)
            
            # 실패 핸들러 실행
            for handler in step.failure_handlers:
                try:
                    handler(step, str(e), execution)
                except Exception as handler_error:
                    self.logger.error(f"실패 핸들러 오류: {str(handler_error)}")
            
            return {
                'success': False,
                'error': str(e),
                'critical_failure': True
            }
    
    def _check_success_criteria(self, result: Dict, criteria: Dict) -> bool:
        """성공 기준 확인"""
        
        for key, expected_value in criteria.items():
            actual_value = result.get(key)
            
            if isinstance(expected_value, dict):
                # 범위 또는 조건 확인
                if 'min' in expected_value and actual_value < expected_value['min']:
                    return False
                if 'max' in expected_value and actual_value > expected_value['max']:
                    return False
            else:
                # 정확한 값 확인
                if actual_value != expected_value:
                    return False
        
        return True
    
    def _request_human_intervention(
        self, 
        step: WorkflowStep, 
        result: Dict,
        execution: WorkflowExecution,
        automation_level: AutomationLevel
    ) -> Dict[str, Any]:
        """사람의 개입 요청"""
        
        # 개입 기록
        intervention = {
            'timestamp': datetime.now().isoformat(),
            'step_id': step.step_id,
            'reason': result.get('intervention_reason', 'Step requires human review'),
            'data': result,
            'automation_level': automation_level.value
        }
        
        execution.human_interventions.append(intervention)
        self.automation_metrics['manual_interventions'] += 1
        
        # 실제 구현에서는 알림/대시보드 시스템과 연동
        self.logger.warning(
            f"사람 개입 필요: {step.step_id} - {intervention['reason']} "
            f"(실행 ID: {execution.execution_id})"
        )
        
        # 임시로 자동 승인 (실제로는 대기 상태)
        return {
            'approved': True,
            'modifications': {},
            'approver': 'system_auto_approval',
            'approval_time': datetime.now().isoformat()
        }
    
    def _calculate_automation_rate(self, execution: WorkflowExecution) -> float:
        """자동화율 계산"""
        
        total_steps = len(execution.steps_completed) + len(execution.steps_failed)
        if total_steps == 0:
            return 0.0
        
        manual_interventions = len(execution.human_interventions)
        automated_steps = total_steps - manual_interventions
        
        return automated_steps / total_steps
    
    def _update_automation_metrics(self):
        """자동화 메트릭 업데이트"""
        
        total_decisions = 0
        automated_decisions = 0
        
        for execution in self.active_executions.values():
            if execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                steps_count = len(execution.steps_completed) + len(execution.steps_failed)
                interventions_count = len(execution.human_interventions)
                
                total_decisions += steps_count
                automated_decisions += (steps_count - interventions_count)
        
        if total_decisions > 0:
            self.automation_metrics['automation_rate'] = automated_decisions / total_decisions
        
        self.automation_metrics['total_decisions'] = total_decisions
        self.automation_metrics['automated_decisions'] = automated_decisions
    
    def _check_execution_health(self, execution: WorkflowExecution):
        """실행 건강성 체크"""
        
        # 실행 시간 초과 체크
        running_time = datetime.now() - execution.started_at
        if running_time > timedelta(hours=2):  # 2시간 초과 시 경고
            self.logger.warning(f"장시간 실행 중인 워크플로우: {execution.execution_id}")
        
        # 오류 패턴 체크
        if len(execution.steps_failed) > len(execution.steps_completed):
            self.logger.warning(f"높은 실패율: {execution.execution_id}")
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """실행 상태 조회"""
        return self.active_executions.get(execution_id)
    
    def get_automation_metrics(self) -> Dict[str, Any]:
        """자동화 메트릭 조회"""
        return {
            **self.automation_metrics,
            'active_executions': len([e for e in self.active_executions.values() 
                                    if e.status == WorkflowStatus.RUNNING]),
            'success_rate': self._calculate_success_rate(),
            'average_execution_time': self._calculate_average_execution_time()
        }
    
    def _calculate_success_rate(self) -> float:
        """성공률 계산"""
        completed_executions = [e for e in self.active_executions.values() 
                              if e.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]]
        
        if not completed_executions:
            return 0.0
        
        successful = len([e for e in completed_executions if e.status == WorkflowStatus.COMPLETED])
        return successful / len(completed_executions)
    
    def _calculate_average_execution_time(self) -> float:
        """평균 실행 시간 계산 (분)"""
        completed_executions = [e for e in self.active_executions.values() 
                              if e.status == WorkflowStatus.COMPLETED and e.completed_at]
        
        if not completed_executions:
            return 0.0
        
        total_time = sum(
            (e.completed_at - e.started_at).total_seconds() 
            for e in completed_executions
        )
        
        return total_time / len(completed_executions) / 60  # 분 단위
    
    # Mock 함수들 (실제 구현에서는 실제 기능으로 대체)
    def _mock_rss_collection(self, params: Dict) -> Dict:
        """Mock RSS 수집"""
        time.sleep(1)  # 실행 시뮬레이션
        return {'success': True, 'channels_found': 25, 'data_quality': 0.9}
    
    def _mock_channel_discovery(self, params: Dict) -> Dict:
        """Mock 채널 발견"""
        time.sleep(2)
        return {'success': True, 'candidates_found': 15, 'filtering_applied': True}
    
    def _mock_ppl_filtering(self, params: Dict) -> Dict:
        """Mock PPL 필터링"""
        time.sleep(1)
        return {'success': True, 'ppl_detected': 8, 'organic_content': 7, 'confidence': 0.92}
    
    def _mock_channel_scoring(self, params: Dict) -> Dict:
        """Mock 채널 점수 계산"""
        time.sleep(1)
        return {'success': True, 'average_score': 67.5, 'high_potential': 5}
    
    def _mock_revenue_prediction(self, params: Dict) -> Dict:
        """Mock 수익 예측"""
        time.sleep(1)
        return {'success': True, 'predicted_roi': 185, 'confidence': 0.78}
    
    def _mock_final_approval(self, params: Dict) -> Dict:
        """Mock 최종 승인"""
        time.sleep(0.5)
        return {'success': True, 'approved_channels': 12, 'requires_review': 3}