"""
워크플로우 상태 관리 시스템
T08_S01_M02: Workflow State Management

PRD SPEC-DASH-05의 상태 기반 워크플로우 관리 시스템 구현
"""

import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.workflow.state_router import StateRouter, CandidateStatus, StateTransition
    from src.workflow.audit_logger import AuditLogger, LogCategory, LogLevel
except ImportError:
    StateRouter = None
    CandidateStatus = None
    StateTransition = None
    AuditLogger = None
    LogCategory = None
    LogLevel = None

logger = logging.getLogger(__name__)


class WorkflowStateManager:
    """워크플로우 상태 관리자"""
    
    def __init__(self):
        """상태 관리자 초기화"""
        self.state_router = StateRouter() if StateRouter else None
        self.audit_logger = AuditLogger() if AuditLogger else None
        
        # 상태별 표시 정보
        self.status_config = {
            "needs_review": {
                "label": "검토 대기",
                "icon": "🔍",
                "color": "#ffc107",
                "bg_color": "#fff3cd",
                "description": "운영자 검토가 필요한 상태"
            },
            "approved": {
                "label": "승인됨",
                "icon": "✅",
                "color": "#28a745",
                "bg_color": "#d4edda",
                "description": "운영자가 승인한 상태"
            },
            "rejected": {
                "label": "반려됨",
                "icon": "❌",
                "color": "#dc3545",
                "bg_color": "#f8d7da",
                "description": "운영자가 반려한 상태"
            },
            "under_revision": {
                "label": "수정중",
                "icon": "✏️",
                "color": "#17a2b8",
                "bg_color": "#d1ecf1",
                "description": "수정 작업 중인 상태"
            },
            "published": {
                "label": "업로드 완료",
                "icon": "🚀",
                "color": "#6f42c1",
                "bg_color": "#e2d9f3",
                "description": "최종 업로드 완료된 상태"
            },
            "filtered_no_coupang": {
                "label": "수익화 불가",
                "icon": "🔗",
                "color": "#fd7e14",
                "bg_color": "#ffeaa7",
                "description": "쿠팡 파트너스 연동 불가"
            },
            "high_ppl_risk": {
                "label": "PPL 위험",
                "icon": "⚠️",
                "color": "#e83e8c",
                "bg_color": "#f8d7da",
                "description": "PPL 확률이 높은 상태"
            }
        }
        
        # 워크플로우 규칙 정의 (PRD SPEC-DASH-05 기준)
        self.workflow_rules = {
            "needs_review": ["approved", "rejected", "under_revision"],
            "approved": ["published", "under_revision"],
            "rejected": ["under_revision", "needs_review"],
            "under_revision": ["needs_review", "rejected"],
            "filtered_no_coupang": ["needs_review"],  # 수동 링크 연결 후
            "high_ppl_risk": ["needs_review"],  # 예외적 승인
            "published": []  # 최종 상태
        }
        
    def render_status_badge(self, status: str, show_description: bool = False) -> str:
        """상태 배지 HTML 렌더링"""
        config = self.status_config.get(status, {
            "label": status,
            "icon": "❓",
            "color": "#6c757d",
            "bg_color": "#f8f9fa",
            "description": "알 수 없는 상태"
        })
        
        badge_html = f"""
        <span style="
            display: inline-flex;
            align-items: center;
            padding: 0.4rem 0.8rem;
            background-color: {config['bg_color']};
            color: {config['color']};
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            border: 1px solid {config['color']}30;
            margin: 0.2rem;
        ">
            {config['icon']} {config['label']}
        </span>
        """
        
        if show_description:
            badge_html += f"""
            <div style="
                font-size: 0.75rem;
                color: #6c757d;
                margin-top: 0.25rem;
                font-style: italic;
            ">
                {config['description']}
            </div>
            """
            
        return badge_html
        
    def render_state_buttons(
        self,
        candidate_id: str,
        current_status: str,
        reason_required: bool = True
    ) -> Optional[Tuple[str, str]]:
        """
        상태 변경 버튼들을 렌더링하고 사용자 액션을 처리
        
        Args:
            candidate_id: 후보 ID
            current_status: 현재 상태
            reason_required: 변경 사유 입력 필수 여부
            
        Returns:
            (new_status, reason) 튜플 또는 None
        """
        available_actions = self.workflow_rules.get(current_status, [])
        
        if not available_actions:
            st.info(f"💡 현재 상태 '{self.status_config.get(current_status, {}).get('label', current_status)}'에서는 더 이상 변경할 수 없습니다.")
            return None
            
        st.markdown("### 🔄 상태 변경")
        
        # 현재 상태 표시
        st.markdown("**현재 상태:**")
        st.markdown(self.render_status_badge(current_status, show_description=True), unsafe_allow_html=True)
        
        # 사용 가능한 액션 버튼들
        st.markdown("**가능한 액션:**")
        
        # 버튼을 가로로 배치
        cols = st.columns(len(available_actions))
        selected_action = None
        
        for i, action in enumerate(available_actions):
            config = self.status_config.get(action, {})
            with cols[i]:
                if st.button(
                    f"{config.get('icon', '❓')} {config.get('label', action)}",
                    key=f"action_{candidate_id}_{action}",
                    help=config.get('description', ''),
                    use_container_width=True
                ):
                    selected_action = action
                    
        if selected_action:
            # 변경 사유 입력
            reason = ""
            if reason_required:
                st.markdown("---")
                reason = st.text_area(
                    "변경 사유를 입력하세요:",
                    key=f"reason_{candidate_id}_{selected_action}",
                    height=100,
                    placeholder="상태 변경 사유를 입력해주세요..."
                )
                
                if not reason.strip():
                    st.warning("⚠️ 변경 사유를 입력해주세요.")
                    return None
                    
            # 확인 대화상자
            st.markdown("---")
            st.warning(f"⚠️ 상태를 **'{self.status_config.get(selected_action, {}).get('label', selected_action)}'**로 변경하시겠습니까?")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 확인", key=f"confirm_{candidate_id}_{selected_action}", type="primary"):
                    return (selected_action, reason)
                    
            with col2:
                if st.button("❌ 취소", key=f"cancel_{candidate_id}_{selected_action}"):
                    st.rerun()
                    
        return None
        
    def apply_status_change(
        self,
        candidate_id: str,
        candidate_data: Dict[str, Any],
        new_status: str,
        reason: str,
        operator_id: str = "dashboard_user"
    ) -> bool:
        """
        상태 변경을 적용하고 데이터베이스 업데이트
        
        Args:
            candidate_id: 후보 ID
            candidate_data: 후보 데이터
            new_status: 새로운 상태
            reason: 변경 사유
            operator_id: 운영자 ID
            
        Returns:
            성공 여부
        """
        try:
            current_status = candidate_data.get("status_info", {}).get("current_status", "needs_review")
            
            # 상태 전환 유효성 검증
            if self.state_router:
                transition = self.state_router.apply_manual_transition(
                    candidate_data=candidate_data,
                    new_status=new_status,
                    reason=reason,
                    operator_id=operator_id
                )
                
                # 후보 데이터 업데이트
                candidate_data["status_info"]["current_status"] = new_status
                candidate_data["status_info"]["updated_at"] = datetime.now().isoformat()
                candidate_data["status_info"]["updated_by"] = operator_id
                candidate_data["status_info"]["last_reason"] = reason
                
                # 감사 로그 기록
                if self.audit_logger:
                    self.audit_logger.log_state_transition(
                        candidate_id=candidate_id,
                        from_status=current_status,
                        to_status=new_status,
                        reason=reason
                    )
                    
                    self.audit_logger.log(
                        category=LogCategory.WORKFLOW,
                        level=LogLevel.INFO,
                        candidate_id=candidate_id,
                        message=f"Manual status change by {operator_id}",
                        metadata={
                            "operator_id": operator_id,
                            "from_status": current_status,
                            "to_status": new_status,
                            "reason": reason,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                logger.info(f"Status change applied: {candidate_id} {current_status} -> {new_status}")
                return True
                
            else:
                # Fallback: 기본 상태 업데이트
                candidate_data["status_info"] = candidate_data.get("status_info", {})
                candidate_data["status_info"]["current_status"] = new_status
                candidate_data["status_info"]["updated_at"] = datetime.now().isoformat()
                candidate_data["status_info"]["updated_by"] = operator_id
                candidate_data["status_info"]["last_reason"] = reason
                
                logger.info(f"Basic status change applied: {candidate_id} -> {new_status}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply status change: {e}")
            st.error(f"상태 변경 중 오류가 발생했습니다: {str(e)}")
            
            # 롤백 처리 - 원래 상태로 복원
            try:
                original_status = candidate_data.get("status_info", {}).get("current_status", "needs_review")
                if "status_info" in candidate_data:
                    candidate_data["status_info"]["current_status"] = original_status
                    logger.info(f"Rollback completed for {candidate_id}: restored to {original_status}")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
                
            return False
            
    def render_status_history(self, candidate_id: str, limit: int = 10):
        """상태 변경 이력 표시"""
        if not self.audit_logger:
            st.info("🔍 상태 변경 이력을 확인하려면 감사 로그 시스템이 필요합니다.")
            return
            
        try:
            # 상태 관련 로그 조회
            logs = self.audit_logger.get_logs(
                candidate_id=candidate_id,
                category=LogCategory.STATE,
                limit=limit
            )
            
            if not logs:
                st.info("📝 상태 변경 이력이 없습니다.")
                return
                
            st.markdown("### 📋 상태 변경 이력")
            
            for log in logs:
                metadata = log.metadata
                from_status = metadata.get("from_status", "알 수 없음")
                to_status = metadata.get("to_status", "알 수 없음")
                reason = metadata.get("transition_reason", "사유 없음")
                
                # 시간 포맷팅
                time_str = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                # 이력 항목 렌더링
                st.markdown(f"""
                <div style="
                    padding: 1rem;
                    margin: 0.5rem 0;
                    border-left: 4px solid #667eea;
                    background: #f8f9fa;
                    border-radius: 8px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <strong>{self.render_status_badge(from_status)} → {self.render_status_badge(to_status)}</strong>
                        <span style="color: #6c757d; font-size: 0.875rem;">{time_str}</span>
                    </div>
                    <div style="color: #495057; font-size: 0.9rem;">
                        📝 {reason}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            logger.error(f"Failed to render status history: {e}")
            st.error(f"상태 이력 조회 중 오류가 발생했습니다: {str(e)}")
            
    def get_status_statistics(self) -> Dict[str, Any]:
        """상태별 통계 정보 반환"""
        if not self.audit_logger:
            return {}
            
        try:
            stats = self.audit_logger.get_statistics()
            return stats
        except Exception as e:
            logger.error(f"Failed to get status statistics: {e}")
            return {}
            
    def render_workflow_rules_info(self):
        """워크플로우 규칙 정보 표시"""
        with st.expander("📖 워크플로우 규칙 안내"):
            st.markdown("""
            ### 상태 전환 규칙 (PRD SPEC-DASH-05)
            
            - **검토 대기** → 승인됨, 반려됨, 수정중
            - **승인됨** → 업로드 완료, 수정중 (재검토)
            - **반려됨** → 수정중, 검토 대기 (재검토)
            - **수정중** → 검토 대기, 반려됨
            - **수익화 불가** → 검토 대기 (수동 링크 연결 후)
            - **PPL 위험** → 검토 대기 (예외적 승인)
            - **업로드 완료** → 최종 상태 (변경 불가)
            
            ### 주의사항
            - 모든 상태 변경은 사유 입력이 필요합니다
            - 변경 이력은 감사 로그에 기록됩니다
            - 잘못된 전환은 시스템에서 자동으로 차단됩니다
            """)


def render_workflow_state_component(
    candidate_id: str,
    candidate_data: Dict[str, Any],
    show_history: bool = True,
    show_rules: bool = True
) -> bool:
    """
    워크플로우 상태 관리 컴포넌트 렌더링
    
    Args:
        candidate_id: 후보 ID
        candidate_data: 후보 데이터
        show_history: 상태 이력 표시 여부
        show_rules: 워크플로우 규칙 표시 여부
        
    Returns:
        상태가 변경되었는지 여부
    """
    manager = WorkflowStateManager()
    current_status = candidate_data.get("status_info", {}).get("current_status", "needs_review")
    
    # 상태 변경 처리
    action_result = manager.render_state_buttons(candidate_id, current_status)
    
    if action_result:
        new_status, reason = action_result
        success = manager.apply_status_change(
            candidate_id=candidate_id,
            candidate_data=candidate_data,
            new_status=new_status,
            reason=reason
        )
        
        if success:
            st.success(f"✅ 상태가 성공적으로 변경되었습니다: {manager.status_config.get(new_status, {}).get('label', new_status)}")
            st.rerun()
        return success
        
    # 상태 이력 표시
    if show_history:
        manager.render_status_history(candidate_id)
        
    # 워크플로우 규칙 정보
    if show_rules:
        manager.render_workflow_rules_info()
        
    return False