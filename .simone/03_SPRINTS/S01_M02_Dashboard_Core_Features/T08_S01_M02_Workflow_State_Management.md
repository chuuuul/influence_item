---
task_id: T08_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Medium
last_updated: 2025-06-22T20:30:00Z
---

# Task: Workflow State Management System

## Description
PRD SPEC-DASH-05의 핵심인 상태 기반 워크플로우 관리 시스템을 구현합니다. 운영자가 후보에 대해 승인/반려/수정/업로드완료 버튼으로 상태를 변경하고, 상태 변경 이력을 추적하며, 데이터베이스 업데이트를 처리합니다.

## Goal / Objectives
- 직관적인 상태 관리 버튼 인터페이스 제공
- 상태 변경 시 실시간 데이터베이스 업데이트
- 상태 변경 이력 추적 및 로깅 시스템 구축
- 워크플로우 진행 상황 시각화

## Acceptance Criteria
- [ ] ✅ 승인, ❌ 반려, ✏️ 수정, 🚀 업로드완료 버튼 정상 동작
- [ ] 버튼 클릭 시 즉시 상태 변경 및 UI 업데이트
- [ ] 상태 변경 시 데이터베이스 자동 업데이트
- [ ] 상태 변경 이력 로그 기록 및 표시
- [ ] 현재 상태에 따른 버튼 활성화/비활성화
- [ ] 상태 변경 시 확인 대화상자 제공

## Subtasks
- [ ] 상태 관리 버튼 UI 컴포넌트 구현
- [ ] 상태 변경 로직 및 데이터 업데이트 구현
- [ ] 상태 이력 추적 시스템 구현
- [ ] 데이터베이스 연동 및 CRUD 작업
- [ ] 상태별 워크플로우 규칙 구현
- [ ] 에러 처리 및 롤백 메커니즘
- [ ] 상태 변경 확인 대화상자

## Technical Guidance

### Key Interfaces & Integration Points
- **State Management**: JSON 스키마의 `status_info.current_status` 필드
- **Database Operations**: SQLite 또는 향후 데이터베이스 연동
- **Logging**: 기존 `src/workflow/audit_logger.py` 활용
- **State Router**: 기존 `src/workflow/state_router.py` 활용
- **UI Components**: `st.button()`, `st.selectbox()`, `st.success()` 조합

### Existing Patterns to Follow
- **Workflow Management**: 기존 `src/workflow/workflow_manager.py` 패턴 참조
- **State Definition**: 
  - `needs_review`: 검토 대기
  - `approved`: 승인됨  
  - `rejected`: 반려됨
  - `filtered_no_coupang`: 수익화 불가
  - `published`: 업로드 완료
- **Error Handling**: try-catch 구문으로 데이터 오류 처리
- **Logging Pattern**: 타임스탬프와 사용자 액션 기록

### Database Models & API Contracts
- **State Fields**:
  - `status_info.current_status`: enum (상태값)
  - `status_info.updated_at`: timestamp (마지막 업데이트)
  - `status_info.updated_by`: string (변경자, 추후 다중 사용자 대비)
- **Audit Log Fields**:
  - `timestamp`: 변경 시각
  - `old_status`: 이전 상태
  - `new_status`: 새 상태
  - `reason`: 변경 사유 (선택사항)

## Implementation Notes

### Step-by-Step Approach
1. 상태 관리 버튼 UI 레이아웃 설계 및 구현
2. 상태 변경 로직 및 검증 규칙 구현
3. 데이터베이스 업데이트 함수 구현
4. 상태 이력 로깅 시스템 연동
5. 에러 처리 및 사용자 피드백 구현
6. 워크플로우 규칙 적용 (상태 전환 제약)

### Architectural Decisions
- 버튼 기반 직관적 상태 변경 인터페이스
- 즉시 반영(immediate update) 방식으로 사용자 경험 향상
- 로컬 상태와 데이터베이스 상태 동기화 보장

### Testing Approach
- 모든 상태 전환 조합 테스트
- 데이터베이스 오류 상황에서 롤백 테스트
- 동시 사용자 상태 변경 충돌 테스트 (추후)
- 대량 데이터에서 상태 변경 성능 테스트

### Performance Considerations
- 상태 변경 시 최소한의 데이터만 업데이트
- 배치 상태 변경 기능 준비 (선택사항)
- 캐싱으로 반복 조회 최적화

### Workflow Rules
- `needs_review` → `approved`, `rejected`, `filtered_no_coupang` 가능
- `approved` → `published`, `needs_review` (재검토) 가능
- `published` 상태는 최종 상태 (변경 불가)
- `rejected` → `needs_review` (재검토) 가능

## Output Log
*(This section is populated as work progresses on the task)*