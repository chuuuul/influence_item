"""
상태 라우팅 로직

필터링 결과와 우선순위에 따라 후보의 상태를 적절히 전환하고
워크플로우를 라우팅합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import logging

from .filter_engine import FilterAction, FilterResult
from .priority_calculator import PriorityScore, PriorityLevel

logger = logging.getLogger(__name__)


class CandidateStatus(Enum):
    """후보 상태 정의"""
    # 초기 상태
    PENDING = "pending"                    # 대기중
    
    # 분석 단계
    PROCESSING = "processing"              # 분석중
    ANALYSIS_COMPLETE = "analysis_complete"  # 분석 완료
    
    # 필터링 결과
    NEEDS_REVIEW = "needs_review"          # 검토 필요
    HIGH_PL_RISK = "high_ppl_risk"        # PPL 위험도 높음
    PPL_REVIEW_REQUIRED = "ppl_review_required"  # PPL 수동 검토 필요
    FILTERED_NO_COUPANG = "filtered_no_coupang"  # 수익화 불가
    LOW_SCORE_FILTERED = "low_score_filtered"    # 낮은 점수로 필터링
    
    # 운영자 액션
    APPROVED = "approved"                  # 승인됨
    REJECTED = "rejected"                  # 반려됨
    UNDER_REVISION = "under_revision"      # 수정중
    
    # 최종 상태
    PUBLISHED = "published"                # 발행됨
    ARCHIVED = "archived"                  # 아카이브됨
    ERROR = "error"                        # 오류


@dataclass
class StateTransition:
    """상태 전환 정보"""
    from_status: CandidateStatus
    to_status: CandidateStatus
    reason: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class StateRouter:
    """상태 라우팅 관리자"""
    
    def __init__(self):
        # 허용되는 상태 전환 규칙
        self.allowed_transitions = self._init_transition_rules()
        
    def _init_transition_rules(self) -> Dict[CandidateStatus, List[CandidateStatus]]:
        """허용되는 상태 전환 규칙 초기화"""
        return {
            CandidateStatus.PENDING: [
                CandidateStatus.PROCESSING,
                CandidateStatus.ERROR
            ],
            CandidateStatus.PROCESSING: [
                CandidateStatus.ANALYSIS_COMPLETE,
                CandidateStatus.ERROR
            ],
            CandidateStatus.ANALYSIS_COMPLETE: [
                CandidateStatus.NEEDS_REVIEW,
                CandidateStatus.HIGH_PL_RISK,
                CandidateStatus.PPL_REVIEW_REQUIRED,
                CandidateStatus.FILTERED_NO_COUPANG,
                CandidateStatus.LOW_SCORE_FILTERED,
                CandidateStatus.ERROR
            ],
            CandidateStatus.NEEDS_REVIEW: [
                CandidateStatus.APPROVED,
                CandidateStatus.REJECTED,
                CandidateStatus.UNDER_REVISION
            ],
            CandidateStatus.PPL_REVIEW_REQUIRED: [
                CandidateStatus.APPROVED,
                CandidateStatus.REJECTED,
                CandidateStatus.HIGH_PL_RISK
            ],
            CandidateStatus.FILTERED_NO_COUPANG: [
                CandidateStatus.NEEDS_REVIEW,  # 수동 링크 연결 후
                CandidateStatus.ARCHIVED
            ],
            CandidateStatus.HIGH_PL_RISK: [
                CandidateStatus.ARCHIVED,
                CandidateStatus.NEEDS_REVIEW  # 예외적 승인
            ],
            CandidateStatus.LOW_SCORE_FILTERED: [
                CandidateStatus.ARCHIVED,
                CandidateStatus.NEEDS_REVIEW  # 재검토
            ],
            CandidateStatus.APPROVED: [
                CandidateStatus.PUBLISHED,
                CandidateStatus.UNDER_REVISION
            ],
            CandidateStatus.REJECTED: [
                CandidateStatus.ARCHIVED,
                CandidateStatus.UNDER_REVISION  # 재작업
            ],
            CandidateStatus.UNDER_REVISION: [
                CandidateStatus.NEEDS_REVIEW,
                CandidateStatus.REJECTED
            ],
            CandidateStatus.PUBLISHED: [
                CandidateStatus.ARCHIVED
            ],
            CandidateStatus.ERROR: [
                CandidateStatus.PENDING,  # 재시도
                CandidateStatus.ARCHIVED
            ]
        }
        
    def route_candidate(
        self,
        candidate_data: Dict[str, Any],
        filter_actions: List[FilterAction],
        priority_score: PriorityScore
    ) -> StateTransition:
        """
        필터링 결과와 우선순위를 기반으로 후보 상태를 라우팅합니다.
        
        Args:
            candidate_data: 후보 데이터
            filter_actions: 적용된 필터 액션 목록
            priority_score: 우선순위 점수
            
        Returns:
            StateTransition 객체
        """
        current_status = self._get_current_status(candidate_data)
        
        # 필터링 액션이 없으면 기본 라우팅
        if not filter_actions:
            new_status = CandidateStatus.NEEDS_REVIEW
            reason = "필터링 규칙 없음, 기본 검토 대상"
        else:
            # 첫 번째 (최우선) 액션 기반 라우팅
            primary_action = filter_actions[0]
            new_status, reason = self._map_action_to_status(primary_action, priority_score)
            
        # 상태 전환 유효성 검증
        if not self._is_transition_allowed(current_status, new_status):
            logger.warning(f"Invalid transition from {current_status} to {new_status}")
            new_status = CandidateStatus.ERROR
            reason = f"허용되지 않는 상태 전환: {current_status.value} -> {new_status.value}"
            
        # 메타데이터 생성
        metadata = {
            "filter_actions": [
                {
                    "result": action.result.value,
                    "reason": action.reason,
                    "priority": action.priority
                }
                for action in filter_actions
            ],
            "priority_score": {
                "total": priority_score.total_score,
                "level": priority_score.level.value,
                "estimated_time": priority_score.estimated_review_time
            },
            "routing_decision": {
                "primary_action": filter_actions[0].reason if filter_actions else None,
                "routing_reason": reason
            }
        }
        
        return StateTransition(
            from_status=current_status,
            to_status=new_status,
            reason=reason,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
    def _get_current_status(self, candidate_data: Dict[str, Any]) -> CandidateStatus:
        """후보 데이터에서 현재 상태 추출"""
        status_str = candidate_data.get("status_info", {}).get("current_status", "pending")
        
        try:
            return CandidateStatus(status_str)
        except ValueError:
            logger.warning(f"Unknown status: {status_str}, defaulting to PENDING")
            return CandidateStatus.PENDING
            
    def _map_action_to_status(
        self,
        action: FilterAction,
        priority_score: PriorityScore
    ) -> Tuple[CandidateStatus, str]:
        """필터 액션을 후보 상태로 매핑"""
        
        if action.result == FilterResult.REJECT:
            if action.new_status == "high_ppl_risk":
                return CandidateStatus.HIGH_PL_RISK, action.reason
            elif action.new_status == "filtered_no_coupang":
                return CandidateStatus.FILTERED_NO_COUPANG, action.reason
            elif action.new_status == "low_score_filtered":
                return CandidateStatus.LOW_SCORE_FILTERED, action.reason
            else:
                return CandidateStatus.REJECTED, action.reason
                
        elif action.result == FilterResult.REQUIRE_MANUAL:
            if action.new_status == "ppl_review_required":
                return CandidateStatus.PPL_REVIEW_REQUIRED, action.reason
            else:
                return CandidateStatus.NEEDS_REVIEW, action.reason
                
        elif action.result == FilterResult.APPROVE:
            # 우선순위에 따른 세부 상태 결정
            if priority_score.level in [PriorityLevel.URGENT, PriorityLevel.HIGH]:
                return CandidateStatus.NEEDS_REVIEW, f"{action.reason} (고우선순위)"
            else:
                return CandidateStatus.NEEDS_REVIEW, action.reason
                
        else:  # SKIP or unknown
            return CandidateStatus.NEEDS_REVIEW, "기본 검토 대상"
            
    def _is_transition_allowed(
        self,
        from_status: CandidateStatus,
        to_status: CandidateStatus
    ) -> bool:
        """상태 전환이 허용되는지 확인"""
        allowed = self.allowed_transitions.get(from_status, [])
        return to_status in allowed
        
    def apply_manual_transition(
        self,
        candidate_data: Dict[str, Any],
        new_status: str,
        reason: str,
        operator_id: str = "system"
    ) -> StateTransition:
        """
        운영자에 의한 수동 상태 전환을 적용합니다.
        
        Args:
            candidate_data: 후보 데이터
            new_status: 새로운 상태
            reason: 전환 사유
            operator_id: 운영자 ID
            
        Returns:
            StateTransition 객체
        """
        current_status = self._get_current_status(candidate_data)
        
        try:
            target_status = CandidateStatus(new_status)
        except ValueError:
            raise ValueError(f"Invalid status: {new_status}")
            
        if not self._is_transition_allowed(current_status, target_status):
            raise ValueError(f"Transition not allowed: {current_status.value} -> {new_status}")
            
        metadata = {
            "operator_id": operator_id,
            "manual_transition": True,
            "operator_reason": reason
        }
        
        return StateTransition(
            from_status=current_status,
            to_status=target_status,
            reason=f"운영자 수동 전환: {reason}",
            timestamp=datetime.now(),
            metadata=metadata
        )
        
    def get_available_transitions(self, current_status: str) -> List[str]:
        """현재 상태에서 가능한 전환 상태 목록 반환"""
        try:
            status = CandidateStatus(current_status)
            allowed = self.allowed_transitions.get(status, [])
            return [s.value for s in allowed]
        except ValueError:
            return []
            
    def get_transition_statistics(
        self,
        transitions: List[StateTransition]
    ) -> Dict[str, Any]:
        """상태 전환 통계 생성"""
        if not transitions:
            return {}
            
        status_counts = {}
        transition_counts = {}
        
        for transition in transitions:
            # 목적 상태 카운트
            to_status = transition.to_status.value
            status_counts[to_status] = status_counts.get(to_status, 0) + 1
            
            # 전환 패턴 카운트
            pattern = f"{transition.from_status.value} -> {transition.to_status.value}"
            transition_counts[pattern] = transition_counts.get(pattern, 0) + 1
            
        return {
            "total_transitions": len(transitions),
            "status_distribution": status_counts,
            "transition_patterns": transition_counts,
            "most_common_target": max(status_counts.items(), key=lambda x: x[1])[0] if status_counts else None
        }