"""
필터링 규칙 엔진

PPL, 수익화, 매력도 기준에 따른 자동 필터링 규칙을 정의하고 실행합니다.
"""

from typing import List, Dict, Any, Callable, Optional
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class FilterResult(Enum):
    """필터링 결과 유형"""
    APPROVE = "approve"
    REJECT = "reject"
    REQUIRE_MANUAL = "require_manual"
    SKIP = "skip"


class FilterPriority(Enum):
    """필터 우선순위"""
    CRITICAL = 1  # 즉시 적용 (PPL 위험도)
    HIGH = 2      # 높은 우선순위 (수익화)
    MEDIUM = 3    # 중간 우선순위 (매력도)
    LOW = 4       # 낮은 우선순위 (기타)


@dataclass
class FilterAction:
    """필터 액션 정의"""
    result: FilterResult
    new_status: str
    priority: str
    reason: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class FilterRule:
    """개별 필터링 규칙"""
    
    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        action: FilterAction,
        priority: FilterPriority = FilterPriority.MEDIUM,
        description: str = ""
    ):
        self.name = name
        self.condition = condition
        self.action = action
        self.priority = priority
        self.description = description
        
    def evaluate(self, candidate_data: Dict[str, Any]) -> Optional[FilterAction]:
        """
        후보 데이터에 대해 규칙을 평가합니다.
        
        Args:
            candidate_data: 후보 데이터
            
        Returns:
            FilterAction 또는 None (조건 불충족)
        """
        try:
            if self.condition(candidate_data):
                logger.debug(f"Rule '{self.name}' triggered for candidate")
                return self.action
            return None
        except Exception as e:
            logger.error(f"Error evaluating rule '{self.name}': {e}")
            return None


class FilterEngine:
    """필터링 규칙 엔진"""
    
    def __init__(self):
        self.rules: List[FilterRule] = []
        self._init_default_rules()
        
    def _init_default_rules(self):
        """기본 필터링 규칙 초기화"""
        
        # PPL 위험도 필터링 (최우선)
        self.add_rule(FilterRule(
            name="high_ppl_risk",
            condition=lambda data: data.get("status_info", {}).get("ppl_confidence", 0) > 0.7,
            action=FilterAction(
                result=FilterResult.REJECT,
                new_status="high_ppl_risk",
                priority="low",
                reason="PPL(유료광고) 확률이 높음 (>70%)"
            ),
            priority=FilterPriority.CRITICAL,
            description="PPL 확률이 70% 이상인 경우 자동 분류"
        ))
        
        # 중간 PPL 위험도 (수동 검토 필요)
        self.add_rule(FilterRule(
            name="medium_ppl_risk",
            condition=lambda data: 0.3 < data.get("status_info", {}).get("ppl_confidence", 0) <= 0.7,
            action=FilterAction(
                result=FilterResult.REQUIRE_MANUAL,
                new_status="ppl_review_required",
                priority="medium",
                reason="PPL 확률이 중간 수준 (30-70%), 수동 검토 필요"
            ),
            priority=FilterPriority.HIGH,
            description="PPL 확률이 30-70%인 경우 수동 검토 요구"
        ))
        
        # 수익화 불가능 필터링
        self.add_rule(FilterRule(
            name="no_monetization",
            condition=lambda data: not data.get("monetization_info", {}).get("is_coupang_product", False),
            action=FilterAction(
                result=FilterResult.REJECT,
                new_status="filtered_no_coupang",
                priority="low",
                reason="쿠팡 파트너스 제품 없음, 수익화 불가"
            ),
            priority=FilterPriority.HIGH,
            description="쿠팡 파트너스에서 제품을 찾을 수 없는 경우"
        ))
        
        # 고매력도 후보 우선 처리
        self.add_rule(FilterRule(
            name="high_attractiveness",
            condition=lambda data: data.get("candidate_info", {}).get("score_details", {}).get("total", 0) >= 80,
            action=FilterAction(
                result=FilterResult.APPROVE,
                new_status="needs_review",
                priority="high",
                reason="매력도 점수 높음 (80점 이상)"
            ),
            priority=FilterPriority.MEDIUM,
            description="매력도 점수가 80점 이상인 고품질 후보"
        ))
        
        # 중간 매력도 후보
        self.add_rule(FilterRule(
            name="medium_attractiveness",
            condition=lambda data: 60 <= data.get("candidate_info", {}).get("score_details", {}).get("total", 0) < 80,
            action=FilterAction(
                result=FilterResult.APPROVE,
                new_status="needs_review",
                priority="medium",
                reason="매력도 점수 중간 (60-79점)"
            ),
            priority=FilterPriority.MEDIUM,
            description="매력도 점수가 60-79점인 중간 품질 후보"
        ))
        
        # 낮은 매력도 후보
        self.add_rule(FilterRule(
            name="low_attractiveness",
            condition=lambda data: data.get("candidate_info", {}).get("score_details", {}).get("total", 0) < 60,
            action=FilterAction(
                result=FilterResult.REJECT,
                new_status="low_score_filtered",
                priority="low",
                reason="매력도 점수 낮음 (60점 미만)"
            ),
            priority=FilterPriority.LOW,
            description="매력도 점수가 60점 미만인 저품질 후보"
        ))
        
    def add_rule(self, rule: FilterRule):
        """새로운 규칙 추가"""
        self.rules.append(rule)
        # 우선순위별로 정렬
        self.rules.sort(key=lambda r: r.priority.value)
        
    def remove_rule(self, rule_name: str) -> bool:
        """규칙 제거"""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                return True
        return False
        
    def process_candidate(self, candidate_data: Dict[str, Any]) -> List[FilterAction]:
        """
        후보에 대해 모든 규칙을 평가합니다.
        
        Args:
            candidate_data: 후보 데이터
            
        Returns:
            적용된 FilterAction 목록
        """
        applied_actions = []
        
        for rule in self.rules:
            action = rule.evaluate(candidate_data)
            if action:
                applied_actions.append(action)
                logger.info(f"Applied rule '{rule.name}': {action.reason}")
                
                # CRITICAL 우선순위 규칙이 적용되면 즉시 중단
                if rule.priority == FilterPriority.CRITICAL:
                    break
                    
                # REJECT 결과가 나오면 후속 규칙 건너뛰기
                if action.result == FilterResult.REJECT:
                    break
                    
        return applied_actions
        
    def get_final_decision(self, actions: List[FilterAction]) -> FilterAction:
        """
        여러 액션 중 최종 결정을 선택합니다.
        
        Args:
            actions: 적용된 액션 목록
            
        Returns:
            최종 FilterAction
        """
        if not actions:
            # 기본 액션: 검토 필요
            return FilterAction(
                result=FilterResult.APPROVE,
                new_status="needs_review",
                priority="medium",
                reason="기본 규칙: 수동 검토 필요"
            )
            
        # 첫 번째 액션이 가장 높은 우선순위
        return actions[0]
        
    def get_rules_summary(self) -> List[Dict[str, Any]]:
        """활성 규칙 요약 정보 반환"""
        return [
            {
                "name": rule.name,
                "priority": rule.priority.name,
                "description": rule.description,
                "action_result": rule.action.result.value,
                "action_status": rule.action.new_status
            }
            for rule in self.rules
        ]