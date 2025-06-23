---
task_id: T03_S02_M02
sprint_sequence_id: S02
status: completed
complexity: Medium
last_updated: 2025-06-23T19:15:00Z
---

# Task: 외부 검색 연동 기능

## Description
PRD SPEC-DASH-04의 핵심 기능으로, 추출된 제품 이미지와 AI 분석 정보를 활용하여 Google/네이버 검색을 자동으로 연동하는 기능을 구현한다. 이미지 기반 역검색과 텍스트 기반 검색을 모두 지원하여 정확한 제품 모델 식별을 지원한다.

## Goal / Objectives
- Google/네이버 검색 링크 자동 생성 및 원클릭 연결
- 이미지 기반 역검색 지원 (Google Lens, 네이버 이미지 검색)
- 검색 결과를 활용한 제품 정보 보완 기능
- 외부 검색 결과의 대시보드 내 통합 표시

## Acceptance Criteria
- [x] Google 텍스트 검색 링크 자동 생성
- [x] 네이버 검색 링크 자동 생성
- [x] Google Lens 이미지 검색 링크 생성
- [x] 네이버 이미지 검색 연동
- [x] 검색 버튼 클릭 시 새 탭에서 외부 검색 실행
- [x] 검색 쿼리 최적화 (제품명, 브랜드명, 카테고리 조합)
- [x] 검색 결과 피드백 기능 (유용함/도움안됨)
- [x] 검색 이력 저장 및 관리

## Subtasks
- [x] 검색 쿼리 생성 알고리즘 구현
- [x] Google 검색 URL 빌더 개발
- [x] 네이버 검색 URL 빌더 개발
- [x] 이미지 업로드 및 검색 연동 시스템
- [x] 검색 버튼 UI 컴포넌트 개발
- [x] 검색 결과 피드백 시스템 구현
- [x] 검색 이력 데이터베이스 설계 및 구현
- [x] 검색 성능 분석 및 최적화

## Technical Guidance

### Key Integration Points
- **대시보드 연동**: `dashboard/components/detail_view.py`에 검색 버튼 추가
- **이미지 데이터**: T02에서 추출된 이미지 파일 활용
- **제품 정보**: JSON 스키마의 `candidate_info` 데이터 사용
- **데이터베이스**: 검색 이력 저장을 위한 SQLite 확장
- **상태 관리**: `dashboard/components/workflow_state_manager.py`와 연동

### Existing Patterns to Follow
- **URL 처리**: Python urllib.parse 모듈 활용
- **파일 처리**: 기존 이미지 파일 관리 패턴
- **사용자 인터페이스**: Streamlit의 버튼 및 링크 컴포넌트
- **데이터 저장**: 기존 database_manager.py 패턴

### Specific Imports and Modules
```python
import urllib.parse
import base64
import requests
from datetime import datetime
import streamlit as st
from dashboard.utils.database_manager import DatabaseManager
from pathlib import Path
```

## Implementation Notes

### Step-by-Step Implementation Approach
1. **검색 쿼리 최적화**: AI 추출 정보에서 핵심 검색어 생성
2. **URL 빌더 시스템**: 각 검색 엔진별 URL 생성 로직
3. **이미지 검색 연동**: 이미지 파일을 검색 엔진에 업로드하는 방식
4. **UI 통합**: 대시보드에 검색 버튼 그룹 추가
5. **피드백 시스템**: 검색 결과의 유용성 평가 및 학습

### Key Architectural Decisions
- **검색 엔진 선택**: Google, 네이버 우선 지원, 확장 가능한 구조
- **이미지 처리**: Base64 인코딩을 통한 이미지 데이터 전송
- **쿼리 생성 전략**: 제품명 + 브랜드명 + 카테고리 조합
- **결과 추적**: 클릭 이벤트 및 피드백 데이터 수집

### Testing Approach
- **기능 테스트**: 각 검색 엔진별 링크 생성 및 연결 검증
- **쿼리 테스트**: 다양한 제품 정보로 검색 쿼리 품질 평가
- **성능 테스트**: 이미지 업로드 및 검색 연동 속도 측정
- **사용성 테스트**: 실제 운영자 워크플로우에서의 효과성 검증

### Performance Considerations
- **검색 속도**: 비동기 방식으로 검색 링크 생성
- **이미지 크기**: 검색용 이미지 최적화 (용량 및 해상도)
- **캐싱**: 동일 제품에 대한 검색 결과 캐시
- **API 제한**: 검색 엔진 API 사용량 모니터링

## External Search Engines Integration

### Google Search
- **텍스트 검색**: `https://www.google.com/search?q={query}`
- **이미지 검색**: Google Lens API 또는 이미지 업로드 방식
- **검색 매개변수**: `hl=ko`, `gl=KR` 등 한국어 최적화

### Naver Search
- **텍스트 검색**: `https://search.naver.com/search.naver?query={query}`
- **이미지 검색**: `https://search.naver.com/search.naver?where=image&query={query}`
- **쇼핑 검색**: `https://search.shopping.naver.com/search/all?query={query}`

## Output Log

[2025-06-23 14:32]: T03_S02_M02 작업 시작 - 외부 검색 연동 기능 구현
[2025-06-23 14:35]: ✅ Subtask 1 완료 - 검색 쿼리 생성 알고리즘 구현 (dashboard/utils/search_query_builder.py)
  - 브랜드와 제품명 자동 분리 기능
  - Google/네이버 최적화된 쿼리 생성
  - 불용어 제거 및 정규화 알고리즘
  - 다양한 검색 전략 지원 (연예인+제품명, 카테고리+제품명, 특징 포함 등)

[2025-06-23 14:38]: ✅ Subtask 2 완료 - 검색 버튼 UI 컴포넌트 개발 (dashboard/components/external_search.py)
  - 텍스트 검색, 이미지 검색, 쇼핑 검색 지원
  - 추출된 제품 이미지 활용 역검색 기능
  - 수동 쿼리 입력 및 피드백 시스템
  - 새 탭에서 외부 검색 실행
  - 검색 결과 피드백 수집 기능

[2025-06-23 14:42]: ✅ Subtask 3 완료 - 검색 이력 데이터베이스 설계 및 구현
  - search_history 테이블 추가 (검색 엔진, 쿼리, 타입, URL, 타임스탬프)
  - search_feedback 테이블 추가 (피드백 타입, 코멘트)
  - 검색 통계 및 인기 쿼리 조회 기능
  - 인덱스 최적화로 성능 향상

[2025-06-23 14:45]: ✅ Subtask 4 완료 - detail_view.py에 검색 기능 통합
  - "🔎 외부 검색" 탭 추가
  - ExternalSearchComponent 통합
  - 검색 이벤트 자동 저장
  - 제품별 검색 이력 표시
  - 글로벌 검색 통계 (관리자용)
  - 폴백 모드 지원

[2025-06-23 14:47]: ✅ 모든 Acceptance Criteria 구현 완료:
  ✅ Google 텍스트 검색 링크 자동 생성
  ✅ 네이버 검색 링크 자동 생성  
  ✅ Google Lens 이미지 검색 링크 생성
  ✅ 네이버 이미지 검색 연동
  ✅ 검색 버튼 클릭 시 새 탭에서 외부 검색 실행
  ✅ 검색 쿼리 최적화 (제품명, 브랜드명, 카테고리 조합)
  ✅ 검색 결과 피드백 기능 (유용함/도움안됨)
  ✅ 검색 이력 저장 및 관리

[2025-06-23 14:48]: 🎯 핵심 기능 구현 완료
  - PRD SPEC-DASH-04 요구사항 완전 구현
  - 제품 이미지 기반 역검색 지원
  - 지능적 쿼리 최적화 알고리즘
  - 데이터베이스 기반 이력 관리
  - 사용자 피드백 수집 시스템