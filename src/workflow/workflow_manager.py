"""
워크플로우 관리자

전체 필터링 워크플로우를 실행하고 관리합니다.
필터링, 우선순위 계산, 상태 라우팅을 통합적으로 처리합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

from .filter_engine import FilterEngine, FilterAction
from .priority_calculator import PriorityCalculator, PriorityScore
from .state_router import StateRouter, StateTransition, CandidateStatus
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """워크플로우 실행 결과"""
    candidate_id: str
    success: bool
    filter_actions: List[FilterAction]
    priority_score: PriorityScore
    state_transition: StateTransition
    processing_time_ms: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        
        # Enum 값들을 문자열로 변환
        if self.priority_score:
            result["priority_score"]["level"] = self.priority_score.level.value
            
        if self.state_transition:
            result["state_transition"]["from_status"] = self.state_transition.from_status.value
            result["state_transition"]["to_status"] = self.state_transition.to_status.value
            result["state_transition"]["timestamp"] = self.state_transition.timestamp.isoformat()
            
        if self.filter_actions:
            for i, action in enumerate(result["filter_actions"]):
                if hasattr(action, "result"):
                    result["filter_actions"][i]["result"] = action.result.value
                    
        return result


@dataclass
class BatchWorkflowResult:
    """배치 워크플로우 실행 결과"""
    total_processed: int
    successful: int
    failed: int
    results: List[WorkflowResult]
    total_processing_time_ms: int
    statistics: Dict[str, Any]


class WorkflowManager:
    """워크플로우 관리자"""
    
    def __init__(
        self,
        filter_engine: Optional[FilterEngine] = None,
        priority_calculator: Optional[PriorityCalculator] = None,
        state_router: Optional[StateRouter] = None,
        audit_logger: Optional[AuditLogger] = None,
        max_workers: int = 4
    ):
        self.filter_engine = filter_engine or FilterEngine()
        self.priority_calculator = priority_calculator or PriorityCalculator()
        self.state_router = state_router or StateRouter()
        self.audit_logger = audit_logger or AuditLogger()
        self.max_workers = max_workers
        
        # 성능 통계
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "average_processing_time_ms": 0,
            "start_time": datetime.now()
        }
        
    def process_candidate(self, candidate_data: Dict[str, Any]) -> WorkflowResult:
        """
        단일 후보에 대해 전체 워크플로우를 실행합니다.
        
        Args:
            candidate_data: 후보 데이터
            
        Returns:
            WorkflowResult 객체
        """
        start_time = datetime.now()
        candidate_id = self._extract_candidate_id(candidate_data)
        
        try:
            # 1. 필터링 규칙 적용
            logger.debug(f"Processing candidate {candidate_id}: Applying filters")
            filter_actions = self.filter_engine.process_candidate(candidate_data)
            
            # 2. 우선순위 계산
            logger.debug(f"Processing candidate {candidate_id}: Calculating priority")
            priority_score = self.priority_calculator.calculate_priority(candidate_data)
            
            # 3. 상태 라우팅
            logger.debug(f"Processing candidate {candidate_id}: Routing state")
            state_transition = self.state_router.route_candidate(
                candidate_data, filter_actions, priority_score
            )
            
            # 4. 후보 데이터 업데이트
            self._update_candidate_data(candidate_data, filter_actions, priority_score, state_transition)
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            result = WorkflowResult(
                candidate_id=candidate_id,
                success=True,
                filter_actions=filter_actions,
                priority_score=priority_score,
                state_transition=state_transition,
                processing_time_ms=processing_time
            )
            
            # 5. 감사 로그 기록
            self.audit_logger.log_workflow_execution(result)
            
            # 6. 통계 업데이트
            self._update_stats(True, processing_time)
            
            logger.info(f"Successfully processed candidate {candidate_id}")
            return result
            
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            error_msg = f"Workflow processing failed: {str(e)}"
            logger.error(f"Failed to process candidate {candidate_id}: {error_msg}")
            
            result = WorkflowResult(
                candidate_id=candidate_id,
                success=False,
                filter_actions=[],
                priority_score=None,
                state_transition=None,
                processing_time_ms=processing_time,
                error_message=error_msg
            )
            
            # 감사 로그 기록 (실패)
            self.audit_logger.log_workflow_error(candidate_id, error_msg)
            
            # 통계 업데이트
            self._update_stats(False, processing_time)
            
            return result
            
    def process_candidates_batch(
        self,
        candidates: List[Dict[str, Any]],
        parallel: bool = True
    ) -> BatchWorkflowResult:
        """
        여러 후보를 배치로 처리합니다.
        
        Args:
            candidates: 후보 데이터 목록
            parallel: 병렬 처리 여부
            
        Returns:
            BatchWorkflowResult 객체
        """
        start_time = datetime.now()
        
        if parallel and len(candidates) > 1:
            results = self._process_parallel(candidates)
        else:
            results = self._process_sequential(candidates)
            
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 결과 집계
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        # 통계 생성
        statistics = self._generate_batch_statistics(results)
        
        return BatchWorkflowResult(
            total_processed=len(results),
            successful=successful,
            failed=failed,
            results=results,
            total_processing_time_ms=processing_time,
            statistics=statistics
        )
        
    def _process_parallel(self, candidates: List[Dict[str, Any]]) -> List[WorkflowResult]:
        """병렬 처리"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.process_candidate, candidate)
                for candidate in candidates
            ]
            
            results = []
            for future in futures:
                try:
                    result = future.result(timeout=300)  # 5분 타임아웃
                    results.append(result)
                except Exception as e:
                    error_result = WorkflowResult(
                        candidate_id="unknown",
                        success=False,
                        filter_actions=[],
                        priority_score=None,
                        state_transition=None,
                        processing_time_ms=0,
                        error_message=f"Parallel processing error: {str(e)}"
                    )
                    results.append(error_result)
                    
            return results
            
    def _process_sequential(self, candidates: List[Dict[str, Any]]) -> List[WorkflowResult]:
        """순차 처리"""
        return [self.process_candidate(candidate) for candidate in candidates]
        
    def _extract_candidate_id(self, candidate_data: Dict[str, Any]) -> str:
        """후보 데이터에서 ID 추출"""
        # 여러 가능한 ID 필드 시도
        for key in ["id", "candidate_id", "video_url", "clip_start_time"]:
            if key in candidate_data:
                return str(candidate_data[key])
                
        # 영상 URL과 시작 시간으로 고유 ID 생성
        source_info = candidate_data.get("source_info", {})
        candidate_info = candidate_data.get("candidate_info", {})
        
        video_url = source_info.get("video_url", "unknown")
        start_time = candidate_info.get("clip_start_time", 0)
        
        return f"{video_url}#{start_time}"
        
    def _update_candidate_data(
        self,
        candidate_data: Dict[str, Any],
        filter_actions: List[FilterAction],
        priority_score: PriorityScore,
        state_transition: StateTransition
    ):
        """후보 데이터 업데이트"""
        
        # 상태 정보 업데이트
        if "status_info" not in candidate_data:
            candidate_data["status_info"] = {}
            
        candidate_data["status_info"]["current_status"] = state_transition.to_status.value
        candidate_data["status_info"]["last_updated"] = datetime.now().isoformat()
        
        # 우선순위 정보 추가
        if "priority_info" not in candidate_data:
            candidate_data["priority_info"] = {}
            
        candidate_data["priority_info"].update({
            "priority_score": priority_score.total_score,
            "priority_level": priority_score.level.value,
            "estimated_review_time": priority_score.estimated_review_time,
            "priority_reasoning": priority_score.reasoning
        })
        
        # 필터링 이력 추가
        if "workflow_history" not in candidate_data:
            candidate_data["workflow_history"] = []
            
        workflow_entry = {
            "timestamp": datetime.now().isoformat(),
            "filter_actions": [
                {
                    "result": action.result.value,
                    "new_status": action.new_status,
                    "priority": action.priority,
                    "reason": action.reason
                }
                for action in filter_actions
            ],
            "state_transition": {
                "from": state_transition.from_status.value,
                "to": state_transition.to_status.value,
                "reason": state_transition.reason
            }
        }
        
        candidate_data["workflow_history"].append(workflow_entry)
        
    def _update_stats(self, success: bool, processing_time_ms: int):
        """통계 업데이트"""
        self.stats["total_processed"] += 1
        
        if success:
            self.stats["successful"] += 1
        else:
            self.stats["failed"] += 1
            
        # 평균 처리 시간 업데이트
        total = self.stats["total_processed"]
        current_avg = self.stats["average_processing_time_ms"]
        self.stats["average_processing_time_ms"] = (
            (current_avg * (total - 1) + processing_time_ms) / total
        )
        
    def _generate_batch_statistics(self, results: List[WorkflowResult]) -> Dict[str, Any]:
        """배치 처리 통계 생성"""
        if not results:
            return {}
            
        # 상태 분포
        status_distribution = {}
        priority_distribution = {}
        
        processing_times = []
        successful_results = [r for r in results if r.success]
        
        for result in successful_results:
            # 상태 분포
            status = result.state_transition.to_status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1
            
            # 우선순위 분포
            if result.priority_score:
                priority = result.priority_score.level.value
                priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
                
            # 처리 시간
            processing_times.append(result.processing_time_ms)
            
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return {
            "success_rate": len(successful_results) / len(results),
            "status_distribution": status_distribution,
            "priority_distribution": priority_distribution,
            "average_processing_time_ms": avg_processing_time,
            "min_processing_time_ms": min(processing_times) if processing_times else 0,
            "max_processing_time_ms": max(processing_times) if processing_times else 0
        }
        
    def get_workflow_statistics(self) -> Dict[str, Any]:
        """전체 워크플로우 통계 반환"""
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "processing_rate_per_minute": (
                self.stats["total_processed"] / (uptime / 60) if uptime > 0 else 0
            ),
            "success_rate": (
                self.stats["successful"] / self.stats["total_processed"] 
                if self.stats["total_processed"] > 0 else 0
            )
        }
        
    def reset_statistics(self):
        """통계 초기화"""
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "average_processing_time_ms": 0,
            "start_time": datetime.now()
        }
        
    def export_results(
        self,
        results: List[WorkflowResult],
        format: str = "json"
    ) -> str:
        """결과를 지정된 형식으로 내보내기"""
        
        if format.lower() == "json":
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_results": len(results),
                "results": [result.to_dict() for result in results]
            }
            return json.dumps(export_data, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")