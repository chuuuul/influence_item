"""
T03A_S03_M03: 스케일링 결정 알고리즘
메트릭과 예측 정보를 기반으로 자동 스케일링 결정을 내리는 엔진
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import sqlite3

logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """스케일링 행동"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"
    URGENT_SCALE_UP = "urgent_scale_up"


class ScalingReason(Enum):
    """스케일링 이유"""
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_QUEUE = "high_queue"
    HIGH_RESPONSE_TIME = "high_response_time"
    PREDICTED_LOAD_INCREASE = "predicted_load_increase"
    LOW_UTILIZATION = "low_utilization"
    COST_OPTIMIZATION = "cost_optimization"
    THRESHOLD_BREACH = "threshold_breach"
    PATTERN_BASED = "pattern_based"


@dataclass
class ScalingThresholds:
    """스케일링 임계값"""
    # 스케일 업 임계값
    cpu_scale_up: float = 75.0
    memory_scale_up: float = 80.0
    queue_scale_up: int = 10
    response_time_scale_up: float = 3000.0  # ms
    
    # 긴급 스케일 업 임계값
    cpu_urgent: float = 90.0
    memory_urgent: float = 95.0
    queue_urgent: int = 25
    response_time_urgent: float = 5000.0  # ms
    
    # 스케일 다운 임계값
    cpu_scale_down: float = 30.0
    memory_scale_down: float = 40.0
    queue_scale_down: int = 2
    response_time_scale_down: float = 1000.0  # ms
    
    # 예측 기반 임계값
    predicted_load_multiplier: float = 1.5
    confidence_threshold: float = 0.7
    
    # 시간 기반 설정
    scale_up_cooldown_minutes: int = 10  # 스케일 업 후 대기 시간
    scale_down_cooldown_minutes: int = 30  # 스케일 다운 후 대기 시간
    sustained_breach_minutes: int = 5  # 지속적 임계값 위반 시간


@dataclass
class ScalingDecision:
    """스케일링 결정"""
    action: ScalingAction
    reasons: List[ScalingReason]
    confidence: float
    urgency: int  # 1-10 (10이 가장 긴급)
    recommended_instances: int
    current_metrics: Dict[str, Any]
    predicted_metrics: Optional[Dict[str, Any]]
    cost_impact: Optional[float]
    decision_time: datetime
    cooldown_until: Optional[datetime]


class ScalingDecisionEngine:
    """스케일링 결정 엔진"""
    
    def __init__(self, thresholds: Optional[ScalingThresholds] = None, 
                 db_path: str = "scaling_decisions.db"):
        """
        Args:
            thresholds: 스케일링 임계값 설정
            db_path: 결정 이력 저장 데이터베이스 경로
        """
        self.thresholds = thresholds or ScalingThresholds()
        self.db_path = db_path
        
        # 비용 계산 (시간당)
        self.instance_costs = {
            'cpu_small': 0.02,   # $0.02/hour
            'cpu_medium': 0.04,  # $0.04/hour
            'cpu_large': 0.08,   # $0.08/hour
            'gpu_small': 0.50,   # $0.50/hour
            'gpu_medium': 1.00,  # $1.00/hour
            'gpu_large': 2.00    # $2.00/hour
        }
        
        self._init_database()
    
    def _init_database(self):
        """결정 이력 데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scaling_decisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        decision_time DATETIME NOT NULL,
                        action TEXT NOT NULL,
                        reasons TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        urgency INTEGER NOT NULL,
                        recommended_instances INTEGER NOT NULL,
                        current_metrics TEXT NOT NULL,
                        predicted_metrics TEXT,
                        cost_impact REAL,
                        cooldown_until DATETIME,
                        executed BOOLEAN DEFAULT FALSE,
                        execution_time DATETIME,
                        execution_result TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scaling_decisions_time 
                    ON scaling_decisions(decision_time)
                ''')
                
                conn.commit()
                logger.info("Scaling decisions database initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize scaling decisions database: {e}")
            raise
    
    def make_scaling_decision(self, current_metrics: Dict[str, Any], 
                            predicted_metrics: Optional[Dict[str, Any]] = None,
                            current_instance_count: int = 1) -> ScalingDecision:
        """스케일링 결정 생성"""
        try:
            decision_time = datetime.now()
            reasons = []
            urgency = 1
            confidence = 0.0
            action = ScalingAction.MAINTAIN
            
            # 쿨다운 확인
            if self._is_in_cooldown(decision_time):
                logger.info("Currently in cooldown period, maintaining current state")
                return self._create_maintain_decision(current_metrics, decision_time)
            
            # 1. 긴급 상황 확인
            urgent_action, urgent_reasons, urgent_urgency = self._check_urgent_conditions(current_metrics)
            if urgent_action != ScalingAction.MAINTAIN:
                action = urgent_action
                reasons.extend(urgent_reasons)
                urgency = urgent_urgency
                confidence = 0.95
            
            # 2. 현재 메트릭 기반 결정
            if action == ScalingAction.MAINTAIN:
                current_action, current_reasons, current_confidence = self._analyze_current_metrics(current_metrics)
                if current_action != ScalingAction.MAINTAIN:
                    action = current_action
                    reasons.extend(current_reasons)
                    confidence = max(confidence, current_confidence)
                    urgency = max(urgency, 5)
            
            # 3. 예측 기반 결정
            if predicted_metrics and action == ScalingAction.MAINTAIN:
                pred_action, pred_reasons, pred_confidence = self._analyze_predicted_metrics(predicted_metrics, current_metrics)
                if pred_action != ScalingAction.MAINTAIN:
                    action = pred_action
                    reasons.extend(pred_reasons)
                    confidence = max(confidence, pred_confidence)
                    urgency = max(urgency, 3)
            
            # 4. 패턴 기반 결정
            if action == ScalingAction.MAINTAIN:
                pattern_action, pattern_reasons, pattern_confidence = self._analyze_patterns(decision_time)
                if pattern_action != ScalingAction.MAINTAIN:
                    action = pattern_action
                    reasons.extend(pattern_reasons)
                    confidence = max(confidence, pattern_confidence)
                    urgency = max(urgency, 2)
            
            # 5. 권장 인스턴스 수 계산
            recommended_instances = self._calculate_recommended_instances(
                action, current_metrics, predicted_metrics, current_instance_count
            )
            
            # 6. 비용 영향 계산
            cost_impact = self._calculate_cost_impact(current_instance_count, recommended_instances)
            
            # 7. 쿨다운 시간 설정
            cooldown_until = self._calculate_cooldown_time(action, decision_time)
            
            # 결정 생성
            decision = ScalingDecision(
                action=action,
                reasons=reasons,
                confidence=confidence,
                urgency=urgency,
                recommended_instances=recommended_instances,
                current_metrics=current_metrics,
                predicted_metrics=predicted_metrics,
                cost_impact=cost_impact,
                decision_time=decision_time,
                cooldown_until=cooldown_until
            )
            
            # 결정 저장
            self._save_decision(decision)
            
            logger.info(f"Scaling decision made: {action.value} with confidence {confidence:.2f}")
            return decision
            
        except Exception as e:
            logger.error(f"Failed to make scaling decision: {e}")
            return self._create_maintain_decision(current_metrics, datetime.now())
    
    def _check_urgent_conditions(self, metrics: Dict[str, Any]) -> Tuple[ScalingAction, List[ScalingReason], int]:
        """긴급 상황 확인"""
        reasons = []
        
        cpu_percent = metrics.get('cpu_percent', 0)
        memory_percent = metrics.get('memory_percent', 0)
        queue_length = metrics.get('processing_queue_length', 0)
        response_time = metrics.get('avg_response_time', 0)
        
        # 긴급 스케일 업 조건 확인
        if cpu_percent >= self.thresholds.cpu_urgent:
            reasons.append(ScalingReason.HIGH_CPU)
        
        if memory_percent >= self.thresholds.memory_urgent:
            reasons.append(ScalingReason.HIGH_MEMORY)
        
        if queue_length >= self.thresholds.queue_urgent:
            reasons.append(ScalingReason.HIGH_QUEUE)
        
        if response_time >= self.thresholds.response_time_urgent:
            reasons.append(ScalingReason.HIGH_RESPONSE_TIME)
        
        if reasons:
            return ScalingAction.URGENT_SCALE_UP, reasons, 10
        
        return ScalingAction.MAINTAIN, [], 1
    
    def _analyze_current_metrics(self, metrics: Dict[str, Any]) -> Tuple[ScalingAction, List[ScalingReason], float]:
        """현재 메트릭 분석"""
        reasons = []
        scale_up_score = 0
        scale_down_score = 0
        
        cpu_percent = metrics.get('cpu_percent', 0)
        memory_percent = metrics.get('memory_percent', 0)
        queue_length = metrics.get('processing_queue_length', 0)
        response_time = metrics.get('avg_response_time', 0)
        success_rate = metrics.get('success_rate', 100)
        
        # 스케일 업 조건
        if cpu_percent >= self.thresholds.cpu_scale_up:
            reasons.append(ScalingReason.HIGH_CPU)
            scale_up_score += (cpu_percent - self.thresholds.cpu_scale_up) / 25.0  # 정규화
        
        if memory_percent >= self.thresholds.memory_scale_up:
            reasons.append(ScalingReason.HIGH_MEMORY)
            scale_up_score += (memory_percent - self.thresholds.memory_scale_up) / 20.0
        
        if queue_length >= self.thresholds.queue_scale_up:
            reasons.append(ScalingReason.HIGH_QUEUE)
            scale_up_score += min(queue_length / self.thresholds.queue_scale_up, 2.0)
        
        if response_time >= self.thresholds.response_time_scale_up:
            reasons.append(ScalingReason.HIGH_RESPONSE_TIME)
            scale_up_score += min(response_time / self.thresholds.response_time_scale_up, 2.0)
        
        # 스케일 다운 조건
        scale_down_conditions = 0
        if cpu_percent <= self.thresholds.cpu_scale_down:
            scale_down_conditions += 1
        if memory_percent <= self.thresholds.memory_scale_down:
            scale_down_conditions += 1
        if queue_length <= self.thresholds.queue_scale_down:
            scale_down_conditions += 1
        if response_time <= self.thresholds.response_time_scale_down:
            scale_down_conditions += 1
        
        if scale_down_conditions >= 3:  # 3개 이상 조건 만족시 스케일 다운
            reasons.append(ScalingReason.LOW_UTILIZATION)
            scale_down_score = scale_down_conditions / 4.0
        
        # 결정
        if scale_up_score > 0:
            confidence = min(scale_up_score / 2.0, 1.0)
            if scale_up_score >= 1.5:
                return ScalingAction.SCALE_UP, reasons, confidence
        
        if scale_down_score > 0.75 and not reasons:
            return ScalingAction.SCALE_DOWN, [ScalingReason.LOW_UTILIZATION], scale_down_score
        
        return ScalingAction.MAINTAIN, [], 0.5
    
    def _analyze_predicted_metrics(self, predicted: Dict[str, Any], 
                                 current: Dict[str, Any]) -> Tuple[ScalingAction, List[ScalingReason], float]:
        """예측 메트릭 분석"""
        try:
            predicted_load = predicted.get('prediction', 0)
            current_load = current.get('processing_queue_length', 0)
            
            # 예측 로드가 현재보다 상당히 증가할 것으로 예상되는 경우
            if predicted_load > current_load * self.thresholds.predicted_load_multiplier:
                confidence = min(predicted_load / (current_load * self.thresholds.predicted_load_multiplier), 1.0)
                if confidence >= self.thresholds.confidence_threshold:
                    return ScalingAction.SCALE_UP, [ScalingReason.PREDICTED_LOAD_INCREASE], confidence
            
            # 예측 로드가 현재보다 상당히 감소할 것으로 예상되는 경우
            elif predicted_load < current_load * 0.5 and current_load > 5:
                confidence = min((current_load - predicted_load) / current_load, 1.0)
                return ScalingAction.SCALE_DOWN, [ScalingReason.COST_OPTIMIZATION], confidence
            
            return ScalingAction.MAINTAIN, [], 0.5
            
        except Exception as e:
            logger.error(f"Failed to analyze predicted metrics: {e}")
            return ScalingAction.MAINTAIN, [], 0.0
    
    def _analyze_patterns(self, decision_time: datetime) -> Tuple[ScalingAction, List[ScalingReason], float]:
        """패턴 기반 분석"""
        try:
            # 시간대별 패턴 확인
            hour = decision_time.hour
            day_of_week = decision_time.weekday()
            
            # 업무시간 시작 전 (오전 8-9시, 평일)
            if day_of_week < 5 and 8 <= hour < 9:
                return ScalingAction.SCALE_UP, [ScalingReason.PATTERN_BASED], 0.6
            
            # 심야 시간 (오후 10시 - 오전 6시)
            if hour >= 22 or hour < 6:
                return ScalingAction.SCALE_DOWN, [ScalingReason.PATTERN_BASED], 0.5
            
            # 주말 저녁 (금요일 오후, 주말)
            if (day_of_week == 4 and hour >= 17) or day_of_week >= 5:
                return ScalingAction.SCALE_DOWN, [ScalingReason.PATTERN_BASED], 0.4
            
            return ScalingAction.MAINTAIN, [], 0.3
            
        except Exception as e:
            logger.error(f"Failed to analyze patterns: {e}")
            return ScalingAction.MAINTAIN, [], 0.0
    
    def _calculate_recommended_instances(self, action: ScalingAction, current_metrics: Dict[str, Any],
                                       predicted_metrics: Optional[Dict[str, Any]], 
                                       current_count: int) -> int:
        """권장 인스턴스 수 계산"""
        try:
            if action == ScalingAction.MAINTAIN:
                return current_count
            
            elif action == ScalingAction.URGENT_SCALE_UP:
                # 긴급한 경우 2배로 증가
                return min(current_count * 2, 10)  # 최대 10개 제한
            
            elif action == ScalingAction.SCALE_UP:
                # 현재 부하에 따라 증가량 결정
                queue_length = current_metrics.get('processing_queue_length', 0)
                cpu_percent = current_metrics.get('cpu_percent', 0)
                
                if queue_length > 20 or cpu_percent > 85:
                    return min(current_count + 2, 8)
                else:
                    return min(current_count + 1, 6)
            
            elif action == ScalingAction.SCALE_DOWN:
                # 최소 1개는 유지
                return max(current_count - 1, 1)
            
            return current_count
            
        except Exception as e:
            logger.error(f"Failed to calculate recommended instances: {e}")
            return current_count
    
    def _calculate_cost_impact(self, current_count: int, recommended_count: int) -> float:
        """비용 영향 계산 (시간당 USD)"""
        try:
            instance_cost = self.instance_costs.get('cpu_medium', 0.04)  # 기본값
            
            current_cost = current_count * instance_cost
            new_cost = recommended_count * instance_cost
            
            return new_cost - current_cost
            
        except Exception as e:
            logger.error(f"Failed to calculate cost impact: {e}")
            return 0.0
    
    def _calculate_cooldown_time(self, action: ScalingAction, decision_time: datetime) -> Optional[datetime]:
        """쿨다운 시간 계산"""
        try:
            if action == ScalingAction.SCALE_UP or action == ScalingAction.URGENT_SCALE_UP:
                return decision_time + timedelta(minutes=self.thresholds.scale_up_cooldown_minutes)
            elif action == ScalingAction.SCALE_DOWN:
                return decision_time + timedelta(minutes=self.thresholds.scale_down_cooldown_minutes)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to calculate cooldown time: {e}")
            return None
    
    def _is_in_cooldown(self, current_time: datetime) -> bool:
        """쿨다운 상태 확인"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT cooldown_until FROM scaling_decisions 
                    WHERE cooldown_until IS NOT NULL 
                    AND cooldown_until > ? 
                    ORDER BY decision_time DESC 
                    LIMIT 1
                ''', (current_time,))
                
                result = cursor.fetchone()
                return result is not None
                
        except Exception as e:
            logger.error(f"Failed to check cooldown status: {e}")
            return False
    
    def _create_maintain_decision(self, current_metrics: Dict[str, Any], decision_time: datetime) -> ScalingDecision:
        """유지 결정 생성"""
        return ScalingDecision(
            action=ScalingAction.MAINTAIN,
            reasons=[],
            confidence=1.0,
            urgency=1,
            recommended_instances=1,  # 현재 상태 유지
            current_metrics=current_metrics,
            predicted_metrics=None,
            cost_impact=0.0,
            decision_time=decision_time,
            cooldown_until=None
        )
    
    def _save_decision(self, decision: ScalingDecision):
        """결정 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO scaling_decisions (
                        decision_time, action, reasons, confidence, urgency,
                        recommended_instances, current_metrics, predicted_metrics,
                        cost_impact, cooldown_until
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    decision.decision_time,
                    decision.action.value,
                    json.dumps([r.value for r in decision.reasons]),
                    decision.confidence,
                    decision.urgency,
                    decision.recommended_instances,
                    json.dumps(decision.current_metrics),
                    json.dumps(decision.predicted_metrics) if decision.predicted_metrics else None,
                    decision.cost_impact,
                    decision.cooldown_until
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save scaling decision: {e}")
    
    def get_decision_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """결정 이력 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM scaling_decisions 
                    WHERE decision_time >= ? 
                    ORDER BY decision_time DESC
                ''', (cutoff_time,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    row_dict = dict(zip(columns, row))
                    # JSON 필드 파싱
                    if row_dict['reasons']:
                        row_dict['reasons'] = json.loads(row_dict['reasons'])
                    if row_dict['current_metrics']:
                        row_dict['current_metrics'] = json.loads(row_dict['current_metrics'])
                    if row_dict['predicted_metrics']:
                        row_dict['predicted_metrics'] = json.loads(row_dict['predicted_metrics'])
                    
                    results.append(row_dict)
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get decision history: {e}")
            return []
    
    def update_thresholds(self, new_thresholds: Dict[str, Any]):
        """임계값 업데이트"""
        try:
            for key, value in new_thresholds.items():
                if hasattr(self.thresholds, key):
                    setattr(self.thresholds, key, value)
                    logger.info(f"Updated threshold {key} to {value}")
                else:
                    logger.warning(f"Unknown threshold parameter: {key}")
                    
        except Exception as e:
            logger.error(f"Failed to update thresholds: {e}")
    
    def get_current_thresholds(self) -> Dict[str, Any]:
        """현재 임계값 조회"""
        try:
            return {
                'cpu_scale_up': self.thresholds.cpu_scale_up,
                'memory_scale_up': self.thresholds.memory_scale_up,
                'queue_scale_up': self.thresholds.queue_scale_up,
                'response_time_scale_up': self.thresholds.response_time_scale_up,
                'cpu_urgent': self.thresholds.cpu_urgent,
                'memory_urgent': self.thresholds.memory_urgent,
                'queue_urgent': self.thresholds.queue_urgent,
                'response_time_urgent': self.thresholds.response_time_urgent,
                'cpu_scale_down': self.thresholds.cpu_scale_down,
                'memory_scale_down': self.thresholds.memory_scale_down,
                'queue_scale_down': self.thresholds.queue_scale_down,
                'response_time_scale_down': self.thresholds.response_time_scale_down,
                'predicted_load_multiplier': self.thresholds.predicted_load_multiplier,
                'confidence_threshold': self.thresholds.confidence_threshold,
                'scale_up_cooldown_minutes': self.thresholds.scale_up_cooldown_minutes,
                'scale_down_cooldown_minutes': self.thresholds.scale_down_cooldown_minutes
            }
            
        except Exception as e:
            logger.error(f"Failed to get current thresholds: {e}")
            return {}