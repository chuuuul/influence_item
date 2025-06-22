---
task_id: T07_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Low
last_updated: 2025-06-22T20:30:00Z
---

# Task: AI Generated Content Display Component

## Description
PRD SPEC-DASH-03 요구사항에 따라 AI가 생성한 모든 콘텐츠 정보(추천 제목, 해시태그, 캡션 등)를 '복사하기' 버튼과 함께 제공하는 컴포넌트를 구현합니다.

## Goal / Objectives
- AI 생성 콘텐츠의 효율적인 표시 및 복사 기능 제공
- 인스타그램 릴스 제작에 필요한 모든 요소를 원클릭으로 복사
- 사용자 친화적인 콘텐츠 관리 인터페이스 완성

## Acceptance Criteria
- [ ] AI 생성 제목 목록 표시 및 개별 복사 기능
- [ ] AI 생성 해시태그 표시 및 전체 복사 기능
- [ ] AI 생성 캡션/요약 표시 및 복사 기능
- [ ] 후크 문장 표시 및 복사 기능
- [ ] 복사 성공 시 시각적 피드백 제공
- [ ] 모바일 환경에서도 복사 기능 정상 작동

## Subtasks
- [ ] AI 생성 콘텐츠 표시 레이아웃 설계
- [ ] 개별 제목 복사 버튼 구현
- [ ] 해시태그 전체 복사 기능 구현
- [ ] 캡션/요약 복사 기능 구현
- [ ] 복사 성공 피드백 UI 구현
- [ ] 빈 데이터 상태 처리
- [ ] 모바일 터치 인터페이스 최적화

## Technical Guidance

### Key Interfaces & Integration Points
- **Data Source**: JSON 스키마의 `candidate_info` 섹션
  - `recommended_titles`: AI 생성 제목 목록
  - `recommended_hashtags`: AI 생성 해시태그 목록
  - `summary_for_caption`: 캡션용 요약
  - `hook_sentence`: 후크 문장
- **Copy Functionality**: Streamlit 의 복사 기능 또는 JavaScript 클립보드 API
- **UI Components**: `st.button()`, `st.text_area()`, `st.code()` 활용

### Existing Patterns to Follow
- **Component Structure**: 기존 `dashboard/components/ai_content_display.py` 참조
- **Data Formatting**: JSON 배열을 사용자 친화적 형태로 변환
- **Button Styling**: 기존 CSS 클래스 및 스타일 패턴 활용
- **Feedback Messages**: `st.success()`, `st.info()` 를 활용한 사용자 피드백

### Database Models & API Contracts
- **Required Fields**:
  - `candidate_info.recommended_titles`: List[str]
  - `candidate_info.recommended_hashtags`: List[str]
  - `candidate_info.summary_for_caption`: str
  - `candidate_info.hook_sentence`: str
- **Optional Fields**: 
  - `candidate_info.target_audience`: 타겟 오디언스 정보
  - `candidate_info.price_point`: 가격대 정보

## Implementation Notes

### Step-by-Step Approach
1. AI 생성 콘텐츠 표시 레이아웃 설계 (카드 또는 탭 구조)
2. 제목 목록 표시 및 개별 복사 버튼 구현
3. 해시태그 표시 및 전체 복사 기능 구현
4. 캡션 및 후크 문장 복사 기능 구현
5. 복사 성공 피드백 UI 구현
6. 데이터 검증 및 예외 처리

### Architectural Decisions
- 카드 기반 레이아웃으로 콘텐츠 그룹핑
- 개별 복사와 전체 복사 옵션 모두 제공
- 클립보드 API 활용으로 브라우저 호환성 확보

### Testing Approach
- 다양한 콘텐츠 길이 및 형태로 표시 테스트
- 모든 복사 기능 동작 확인
- 다양한 브라우저에서 클립보드 API 테스트
- 모바일 환경에서 터치 동작 테스트

### Performance Considerations
- 대량 텍스트 렌더링 최적화
- 클립보드 동작 시 UI 블로킹 방지
- 반복 복사 동작 시 성능 유지

## Output Log
*(This section is populated as work progresses on the task)*