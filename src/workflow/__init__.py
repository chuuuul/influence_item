"""
워크플로우 모듈

이 모듈은 PPL 분석, 수익화 검증, 매력도 스코어링 결과를 종합하여
제품 추천 후보를 자동으로 분류하고 적절한 상태로 라우팅하는
워크플로우 시스템을 제공합니다.

태스크 T04_S03 명세에 따른 핵심 컴포넌트:
- FilterEngine: 필터링 규칙 엔진
- WorkflowManager: 워크플로우 실행 관리  
- PriorityCalculator: 우선순위 계산 (PRD 매력도 공식 적용)
- StateRouter: 상태 라우팅 로직
- AuditLogger: 워크플로우 감사 로그
"""

from .filter_engine import FilterEngine, FilterRule
from .workflow_manager import WorkflowManager
from .priority_calculator import PriorityCalculator
from .state_router import StateRouter, StateTransition
from .audit_logger import AuditLogger

__all__ = [
    'FilterEngine',
    'FilterRule', 
    'WorkflowManager',
    'PriorityCalculator',
    'StateRouter',
    'StateTransition',
    'AuditLogger'
]