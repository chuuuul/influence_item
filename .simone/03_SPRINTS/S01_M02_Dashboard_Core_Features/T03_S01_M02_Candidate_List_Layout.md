---
task_id: T03_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Medium
last_updated: 2025-06-22T20:30:00Z
---

# Task: Monetizable Candidates List Page Basic Layout

## Description
수익화 가능 후보 목록 페이지의 기본 레이아웃을 구현합니다. PRD SPEC-DASH-01 요구사항에 따라 매력도 점수, 채널명, 영상 제목, 업로드 날짜 등 주요 정보를 표시하는 테이블 구조를 구성합니다.

## Goal / Objectives
- 수익화 가능 후보들의 핵심 정보를 한눈에 볼 수 있는 레이아웃 완성
- PRD JSON 스키마에 따른 데이터 표시 구조 구현
- 후속 정렬/필터링 기능을 위한 테이블 기반 구조 준비

## Acceptance Criteria
- [ ] 후보 목록이 테이블 형태로 깔끔하게 표시됨
- [ ] 매력도 점수, 채널명, 영상 제목, 업로드 날짜 컬럼 표시
- [ ] 각 행 클릭 시 상세 뷰로 이동 가능
- [ ] 빈 데이터 상태 처리 (No data available)
- [ ] 로딩 상태 표시 기능
- [ ] 모바일 환경에서도 가독성 유지

## Subtasks
- [ ] 기본 테이블 구조 설계 및 구현
- [ ] 컬럼 헤더 정의 (매력도 점수, 채널명, 영상 제목, 업로드 날짜)
- [ ] 행 클릭 이벤트 핸들링
- [ ] 빈 데이터 상태 UI 구현
- [ ] 로딩 스피너 구현
- [ ] 반응형 테이블 레이아웃 최적화

## Technical Guidance

### Key Interfaces & Integration Points
- **Data Source**: 향후 `src/schema/models.py`의 JSON 스키마 연동
- **Table Component**: `st.dataframe()` 또는 `st.table()` 활용
- **Navigation**: 행 클릭 시 상세 뷰 페이지로 라우팅
- **State Management**: 선택된 후보 정보 세션 상태 저장

### Existing Patterns to Follow
- **Data Display**: 기존 `dashboard/pages/monetizable_candidates.py` 패턴 참조
- **Event Handling**: Streamlit 의 `st.button()` 또는 `st.selectbox()` 활용
- **Responsive Design**: CSS 미디어 쿼리 활용
- **Error Handling**: try-except 구문으로 데이터 오류 처리

### Database Models & API Contracts
- **JSON Schema**: PRD Section 3.3의 최종 JSON 스키마 준수
- **Required Fields**: 
  - `source_info`: celebrity_name, channel_name, video_title, upload_date
  - `candidate_info`: product_name_ai, score_details.total
  - `status_info`: current_status

## Implementation Notes

### Step-by-Step Approach
1. 기본 테이블 레이아웃 구성 (컬럼 헤더 정의)
2. 샘플 데이터로 테이블 렌더링 테스트
3. 행 클릭 이벤트 핸들링 구현
4. 빈 데이터 상태 및 로딩 상태 UI 구현
5. 반응형 디자인 적용 및 테스트

### Architectural Decisions
- Streamlit의 네이티브 테이블 컴포넌트 활용
- 행 클릭 시 세션 상태 기반 페이지 전환
- CSS 그리드 레이아웃으로 반응형 구현

### Testing Approach
- 다양한 데이터 크기(빈 데이터, 소량, 대량)로 테스트
- 다양한 화면 크기에서 레이아웃 확인
- 클릭 이벤트 동작 확인

### Performance Considerations
- 대량 데이터 로딩 시 페이지네이션 준비
- 테이블 렌더링 성능 최적화
- 불필요한 데이터 로딩 최소화

## Output Log
*(This section is populated as work progresses on the task)*