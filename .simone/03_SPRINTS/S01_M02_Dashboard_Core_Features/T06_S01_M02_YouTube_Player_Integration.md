---
task_id: T06_S01_M02
sprint_sequence_id: S01_M02
status: open
complexity: Medium
last_updated: 2025-06-22T20:30:00Z
---

# Task: YouTube Embedded Player Integration & Timestamp Auto-Play

## Description
PRD SPEC-DASH-02 핵심 요구사항인 YouTube 타임스탬프 자동 재생 기능을 구현합니다. 제품 언급 구간 클릭 시 YouTube 임베드 플레이어에서 해당 시점부터 자동 재생되어 검토 효율을 극대화합니다.

## Goal / Objectives
- YouTube 임베드 플레이어 통합 및 Streamlit 환경 최적화
- 제품 언급 구간 클릭 시 해당 시점 자동 재생 기능
- 플레이어 상태 관리 및 에러 처리 체계 구축

## Acceptance Criteria
- [ ] YouTube 영상이 상세 뷰에서 정상 재생됨
- [ ] 타임스탬프 클릭 시 해당 시점에서 자동 재생 시작
- [ ] 플레이어 컨트롤 (재생/정지, 음량, 전체화면) 정상 동작
- [ ] 영상 로딩 실패 시 적절한 오류 메시지 표시
- [ ] 모바일 환경에서도 플레이어 정상 작동
- [ ] 타임스탬프 정확도 ±2초 이내

## Subtasks
- [ ] YouTube 임베드 URL 생성 로직 구현
- [ ] Streamlit 에서 YouTube 플레이어 통합
- [ ] 타임스탬프 자동 재생 기능 구현
- [ ] 플레이어 에러 처리 및 로딩 상태 관리
- [ ] 모바일 반응형 플레이어 최적화
- [ ] 타임스탬프 UI 개선 (클릭 가능 표시)

## Technical Guidance

### Key Interfaces & Integration Points
- **YouTube API**: 임베드 URL 형식 `https://www.youtube.com/embed/{video_id}?start={seconds}`
- **Streamlit Components**: `st.components.v1.html()` 또는 `st.video()` 활용
- **Data Source**: `candidate_info.clip_start_time`, `candidate_info.clip_end_time`
- **URL Parsing**: YouTube URL에서 video_id 추출 로직

### Existing Patterns to Follow
- **iframe Embedding**: HTML iframe 태그를 `st.components.v1.html()` 로 렌더링
- **Error Handling**: try-catch 구문으로 영상 로딩 오류 처리
- **Responsive Design**: CSS 미디어 쿼리로 반응형 플레이어
- **State Management**: 플레이어 상태를 세션 상태로 관리

### Database Models & API Contracts
- **Required Fields**: 
  - `source_info.video_url`: YouTube 영상 URL
  - `candidate_info.clip_start_time`: 제품 언급 시작 시간 (초)
  - `candidate_info.clip_end_time`: 제품 언급 종료 시간 (초)
- **URL Format**: YouTube 표준 URL 또는 youtu.be 단축 URL 지원

## Implementation Notes

### Step-by-Step Approach
1. YouTube URL 파싱 및 video_id 추출 함수 구현
2. 타임스탬프 포함 임베드 URL 생성 로직 구현
3. Streamlit 환경에서 YouTube 플레이어 임베드 테스트
4. 타임스탬프 클릭 이벤트 핸들링 구현
5. 에러 처리 및 로딩 상태 UI 구현
6. 모바일 환경 반응형 최적화

### Architectural Decisions
- iframe 기반 임베드 방식으로 YouTube API 제약 해결
- 클라이언트 사이드 JavaScript로 타임스탬프 제어
- Streamlit 컴포넌트 시스템 활용한 플레이어 통합

### Testing Approach
- 다양한 YouTube URL 형식으로 파싱 테스트
- 정확한 타임스탬프 재생 위치 확인
- 네트워크 오류 상황에서 에러 처리 테스트
- 다양한 디바이스에서 플레이어 동작 테스트

### Performance Considerations
- 플레이어 로딩 시간 최적화
- 다수 영상 동시 로딩 시 성능 고려
- 대역폭 제한 환경에서 사용성 보장

### Streamlit Constraints
- Streamlit의 iframe 보안 정책 고려
- 컴포넌트 리렌더링 최소화
- YouTube 자동재생 정책 제약 사항 해결

## Output Log
*(This section is populated as work progresses on the task)*