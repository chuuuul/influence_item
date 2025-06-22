---
task_id: T09_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Low
last_updated: 2025-06-22T20:30:00Z
---

# Task: Filtered Products Management Page & Manual Link Connection

## Description
PRD 요구사항에 따라 '수익화 필터링 목록' 탭을 구현하고, 쿠팡 파트너스에서 검색되지 않은 제품들에 대해 수동으로 링크를 연결하여 메인 수익화 목록으로 복원하는 기능을 제공합니다.

## Goal / Objectives
- 수익화 불가로 분류된 제품들의 관리 인터페이스 제공
- 수동 링크 연결 기능으로 제품 복원 워크플로우 구현
- 필터링 사유 표시 및 관리 효율성 향상

## Acceptance Criteria
- [ ] 수익화 필터링 목록 페이지 표시 (탭 형태)
- [ ] 필터링된 제품들의 기본 정보 테이블 표시
- [ ] 🔗 수동 링크 연결 버튼 제공
- [ ] 링크 입력 폼 및 검증 기능
- [ ] 링크 연결 성공 시 메인 목록으로 이동
- [ ] 필터링 사유 표시 (쿠팡 검색 실패, PPL 등)

## Subtasks
- [ ] 필터링된 제품 목록 표시 레이아웃 구현
- [ ] 수동 링크 연결 폼 UI 구현
- [ ] 링크 URL 검증 로직 구현
- [ ] 상태 변경 및 데이터 업데이트 기능
- [ ] 메인 목록 복원 워크플로우 구현
- [ ] 필터링 사유별 분류 표시

## Technical Guidance

### Key Interfaces & Integration Points
- **Data Source**: `status_info.current_status = "filtered_no_coupang"` 인 항목들
- **State Change**: `filtered_no_coupang` → `needs_review` 상태 전환
- **URL Validation**: 쿠팡 파트너스 URL 형식 검증
- **Database Update**: `monetization_info.coupang_url_manual` 필드 업데이트

### Existing Patterns to Follow
- **Table Display**: 기존 후보 목록과 동일한 테이블 구조 활용
- **Form Handling**: `st.form()` 과 `st.text_input()` 조합
- **State Management**: 기존 워크플로우 상태 관리 패턴 활용
- **URL Validation**: 정규식 패턴으로 쿠팡 URL 형식 검증

### Database Models & API Contracts
- **Filter Criteria**: `status_info.current_status == "filtered_no_coupang"`
- **Update Fields**:
  - `monetization_info.coupang_url_manual`: 수동 연결 URL
  - `monetization_info.is_coupang_product`: True 로 변경
  - `status_info.current_status`: `needs_review` 로 변경
- **Validation Rules**: 쿠팡 파트너스 도메인 확인

## Implementation Notes

### Step-by-Step Approach
1. 필터링된 제품 목록 조회 및 표시 기능 구현
2. 수동 링크 연결 폼 UI 및 유효성 검증 구현
3. 링크 연결 성공 시 상태 변경 로직 구현
4. 메인 목록 복원 및 사용자 피드백 구현
5. 필터링 사유별 분류 및 통계 표시
6. 에러 처리 및 롤백 메커니즘

### Architectural Decisions
- 탭 기반 페이지 분리로 사용자 경험 최적화
- 실시간 URL 검증으로 사용자 실수 방지
- 단계별 확인 프로세스로 데이터 정합성 보장

### Testing Approach
- 다양한 쿠팡 URL 형식으로 검증 테스트
- 잘못된 URL 입력 시 에러 처리 테스트
- 상태 변경 및 데이터 업데이트 정확성 테스트
- 복원된 제품이 메인 목록에 정상 표시되는지 확인

### Performance Considerations
- 필터링 목록 조회 시 인덱스 활용
- 대량 복원 작업 시 배치 처리 고려
- URL 검증 시 네트워크 지연 최소화

### URL Validation Rules
- 쿠팡 파트너스 도메인: `link.coupang.com` 또는 `coupa.ng`
- HTTPS 프로토콜 강제
- 파트너 ID 포함 여부 확인
- 악성 링크 차단을 위한 기본 검증

## Output Log
*(This section is populated as work progresses on the task)*