---
task_id: T05_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Medium
last_updated: 2025-06-22T20:30:00Z
---

# Task: Detail View Page Structure & Product Information Display

## Description
후보 아이템 클릭 시 표시되는 상세 뷰 페이지의 기본 구조를 구현합니다. PRD 요구사항에 따라 제품 정보, 영상 정보, AI 분석 결과를 체계적으로 표시하고, Master-Detail 2-depth 구조를 완성합니다.

## Goal / Objectives
- 선택된 후보의 모든 상세 정보를 체계적으로 표시
- 사용자 친화적인 정보 레이아웃 및 구성
- 추후 YouTube 플레이어 및 상태 관리 기능 통합 준비

## Acceptance Criteria
- [ ] 후보 선택 시 상세 뷰 페이지로 정상 이동
- [ ] 제품 기본 정보 섹션 (이름, 카테고리, 특징) 표시
- [ ] 영상 정보 섹션 (채널명, 제목, 업로드 날짜) 표시
- [ ] AI 분석 결과 섹션 (매력도 점수, 후크 문장) 표시
- [ ] 뒤로 가기 버튼으로 목록 페이지 복귀 가능
- [ ] 반응형 레이아웃 (모바일/데스크톱 대응)

## Subtasks
- [ ] 상세 뷰 페이지 기본 레이아웃 설계
- [ ] 제품 정보 섹션 구현
- [ ] 영상 정보 섹션 구현
- [ ] AI 분석 결과 섹션 구현
- [ ] 네비게이션 버튼 (뒤로 가기) 구현
- [ ] 반응형 레이아웃 적용
- [ ] 데이터 없음 상태 처리

## Technical Guidance

### Key Interfaces & Integration Points
- **Data Source**: 세션 상태에 저장된 선택 후보 데이터
- **Navigation**: 목록 페이지와 상세 뷰 간 라우팅
- **Component Structure**: 기존 `dashboard/components/detail_view.py` 활용
- **Data Display**: 탭 또는 섹션 기반 정보 그룹핑

### Existing Patterns to Follow
- **Session State**: `st.session_state` 로 선택된 후보 데이터 관리
- **Layout Structure**: `st.columns()` 또는 `st.container()` 활용
- **Data Formatting**: JSON 데이터를 사용자 친화적 형태로 변환
- **Error Handling**: 데이터 누락 시 적절한 메시지 표시

### Database Models & API Contracts
- **Data Schema**: PRD Section 3.3 JSON 스키마 구조 준수
- **Required Sections**: 
  - `source_info`: celebrity_name, channel_name, video_title, upload_date
  - `candidate_info`: product_name_ai, category_path, features, score_details
  - `monetization_info`: is_coupang_product, coupang_url_ai
  - `status_info`: current_status, is_ppl, ppl_confidence

## Implementation Notes

### Step-by-Step Approach
1. 상세 뷰 페이지 기본 레이아웃 및 섹션 구조 설계
2. 각 정보 섹션별 컴포넌트 구현
3. 데이터 바인딩 및 표시 로직 구현
4. 네비게이션 버튼 및 페이지 전환 구현
5. 반응형 레이아웃 적용 및 테스트
6. 예외 상황 처리 (데이터 누락, 오류 등)

### Architectural Decisions
- 탭 기반 정보 그룹핑으로 가독성 향상
- 컴포넌트 기반 설계로 재사용성 극대화
- 세션 상태 기반 데이터 전달로 성능 최적화

### Testing Approach
- 다양한 데이터 형태의 후보로 표시 테스트
- 데이터 누락 상황에서 오류 처리 테스트
- 다양한 화면 크기에서 레이아웃 테스트
- 네비게이션 동작 테스트

### Performance Considerations
- 대용량 이미지 로딩 최적화 (추후 YouTube 썸네일)
- 불필요한 데이터 리렌더링 방지
- 빠른 페이지 전환을 위한 데이터 캐싱

## Output Log
*(This section is populated as work progresses on the task)*