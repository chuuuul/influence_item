---
task_id: T10_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Medium
last_updated: 2025-06-22T20:30:00Z
---

# Task: Dashboard Integration Testing & UI/UX Validation

## Description
S01_M02 스프린트의 최종 단계로, 구현된 모든 대시보드 기능들의 통합 테스트를 수행하고 UI/UX를 검증합니다. 실제 운영자가 15분 내에 기본 워크플로우를 수행할 수 있는지 확인하고 성능 최적화를 진행합니다.

## Goal / Objectives
- 전체 대시보드 기능의 end-to-end 통합 테스트 수행
- 실제 운영 시나리오에서 사용성 검증
- 성능 최적화 및 버그 수정
- 운영 준비 완료 상태로 품질 보장

## Acceptance Criteria
- [ ] 100개 이상 후보 데이터로 모든 기능 정상 동작 확인
- [ ] 실제 운영자가 15분 내 기본 워크플로우 완수 가능
- [ ] 모든 상태 전환 버튼 정상 동작 및 데이터 정합성 유지
- [ ] YouTube 타임스탬프 재생 정확도 ±2초 이내
- [ ] 페이지 로딩 시간 2초 이내 (100개 후보 기준)
- [ ] 에러 상황에서 적절한 사용자 피드백 제공
- [ ] 모바일/태블릿 환경에서 기본 기능 정상 동작

## Subtasks
- [ ] 테스트 데이터 준비 (100개+ 후보 샘플)
- [ ] 기능별 단위 테스트 수행
- [ ] 통합 워크플로우 테스트 시나리오 실행
- [ ] 성능 측정 및 최적화 포인트 식별
- [ ] UI/UX 사용성 테스트 수행
- [ ] 브라우저 호환성 테스트
- [ ] 모바일 반응형 테스트
- [ ] 에러 처리 시나리오 테스트
- [ ] 테스트 결과 문서화 및 버그 수정

## Technical Guidance

### Key Interfaces & Integration Points
- **End-to-End Testing**: 데이터 로딩 → 정렬/필터링 → 상세보기 → 상태변경 전체 플로우
- **Performance Testing**: `time.time()` 또는 Streamlit 성능 모니터링
- **Data Validation**: 실제 JSON 스키마 데이터로 모든 컴포넌트 테스트
- **Screenshot Capture**: Playwright 또는 Selenium으로 테스트 스크린샷 저장

### Existing Patterns to Follow
- **Test Data**: 기존 `tests/` 디렉토리의 테스트 패턴 활용
- **Error Logging**: 기존 `influence_item.log` 패턴으로 오류 기록
- **Performance Monitoring**: 각 컴포넌트별 렌더링 시간 측정
- **Screenshot Storage**: 기존 `screenshots/` 디렉토리 활용

### Database Models & API Contracts
- **Test Dataset**: 다양한 상태의 후보 데이터 (needs_review, approved, filtered_no_coupang 등)
- **Data Integrity**: 상태 변경 후 데이터베이스 정합성 검증
- **Schema Validation**: PRD JSON 스키마 완전 준수 확인

## Implementation Notes

### Step-by-Step Approach
1. **테스트 환경 구성**: 100개+ 다양한 상태의 테스트 데이터 준비
2. **기능별 단위 테스트**: 정렬, 필터링, 상세보기, 상태변경 개별 테스트
3. **통합 워크플로우 테스트**: 실제 운영 시나리오 기반 전체 플로우 테스트
4. **성능 측정**: 페이지 로딩, 데이터 처리, 상태 변경 시간 측정
5. **사용성 테스트**: 실제 사용자 관점에서 15분 워크플로우 수행
6. **버그 수정 및 최적화**: 발견된 이슈 수정 및 성능 개선
7. **최종 검증**: 모든 요구사항 충족 확인

### Architectural Decisions
- 실제 운영 환경과 동일한 조건에서 테스트 수행
- 사용자 중심의 워크플로우 기반 테스트 시나리오 설계
- 성능 측정과 사용성 테스트 병행

### Testing Scenarios

#### Core Workflow Test (15분 제한)
1. **데이터 조회**: 후보 목록 로딩 및 표시 (30초)
2. **정렬/필터링**: 매력도 순 정렬, 키워드 검색 (1분)
3. **상세 검토**: 상위 5개 후보 상세보기 및 YouTube 재생 (10분)
4. **상태 관리**: 승인 2개, 반려 1개, 수정 1개, 필터링 복원 1개 (3분)
5. **결과 확인**: 변경 내용 반영 확인 (30초)

#### Performance Benchmarks
- **페이지 로딩**: 100개 후보 < 2초
- **정렬 동작**: 1000개 후보 < 1초
- **상세 뷰 전환**: < 0.5초
- **상태 변경**: < 1초
- **YouTube 재생**: 클릭 후 3초 이내 재생 시작

### Testing Tools & Methods
- **Automated Testing**: Pytest 기반 기능 테스트
- **Performance Testing**: `@st.cache_data` 효과 측정
- **Screenshot Testing**: 주요 페이지 스크린샷 저장
- **Manual Testing**: 실제 사용자 시나리오 기반 수동 테스트

## Output Log
*(This section is populated as work progresses on the task)*