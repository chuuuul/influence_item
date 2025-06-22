---
sprint_id: S03
milestone_id: M01
sprint_name: Filtering & Verification System
status: active
priority: critical
start_date: 2025-06-23
target_completion: 2025-06-30
progress_percentage: 0
estimated_effort_days: 7
actual_effort_days: 0
total_tasks: 6
completed_tasks: 0
---

# S03 - Filtering & Verification System

## 스프린트 개요

S01, S02에서 구축한 AI 분석 파이프라인에 PPL 필터링, 수익화 검증, 매력도 스코어링 시스템을 추가하여 비즈니스 가치가 높은 콘텐츠만을 선별하는 완전한 필터링 및 검증 시스템을 구축합니다.

## 스프린트 목표

1. **PPL 확률 분석 알고리즘 구현**
2. **쿠팡 파트너스 API 연동 및 수익화 검증**
3. **매력도 스코어링 시스템 개발**
4. **자동 필터링 워크플로우 구축**
5. **최종 JSON 스키마 완성 및 검증**

## 성공 기준

- [ ] PPL 콘텐츠를 90% 이상 정확도로 탐지 및 분리
- [ ] 쿠팡 파트너스 API 연동 완료 및 수익화 가능 제품 확인
- [ ] 매력도 스코어 공식 구현 및 검증
- [ ] 자동 필터링으로 운영자 검토 시간 70% 단축
- [ ] 완전한 JSON 스키마 기반 데이터 출력

## 주요 태스크

### T01A_S03 - PPL 패턴 분석 기초 모듈
- **파일**: `T01A_S03_PPL_Pattern_Analysis_Module.md`
- **목표**: 명시적/암시적 PPL 패턴 탐지 기초 모듈
- **기술**: 패턴 매칭, 정규식, 퍼지 매칭
- **산출물**: PPL 패턴 분석 모듈
- **복잡도**: Medium

### T01B_S03 - PPL 컨텍스트 분석 및 통합
- **파일**: `T01B_S03_PPL_Context_Analysis_Integration.md`
- **목표**: Gemini 기반 컨텍스트 분석 및 최종 PPL 확률 계산
- **기술**: Gemini API, 컨텍스트 분석, 통합 로직
- **산출물**: 통합 PPL 분석 시스템
- **복잡도**: Medium

### T02_S03 - 쿠팡 파트너스 API 연동
- **파일**: `T02_S03_Coupang_Partners_API_Integration.md`
- **목표**: 제품 검색 및 수익화 가능성 검증
- **기술**: REST API, 제품 매칭 알고리즘
- **산출물**: 쿠팡 API 연동 모듈
- **복잡도**: Medium

### T03_S03 - 매력도 스코어링 시스템
- **파일**: `T03_S03_Attractiveness_Scoring_System.md`
- **목표**: 감성 강도, 실사용 인증, 인플루언서 신뢰도 종합 점수
- **기술**: 가중 평균, 감성 분석, 신뢰도 계산
- **산출물**: 스코어링 엔진
- **복잡도**: Medium

### T04_S03 - 자동 필터링 워크플로우
- **파일**: `T04_S03_Automated_Filtering_Workflow.md`
- **목표**: 필터링 규칙 기반 자동 분류 시스템
- **기술**: 규칙 엔진, 워크플로우 관리
- **산출물**: 자동 필터링 시스템
- **복잡도**: Medium

### T05_S03 - 최종 JSON 스키마 완성
- **파일**: `T05_S03_Final_JSON_Schema_Completion.md`
- **목표**: PRD 명세 기준 완전한 JSON 스키마 출력
- **기술**: 데이터 검증, 스키마 완성
- **산출물**: 최종 데이터 구조
- **복잡도**: Medium

## 기술 구현 세부사항

### 1. PPL 확률 분석
```python
class PPLAnalyzer:
    def __init__(self):
        self.ppl_indicators = {
            'explicit_ad': ['협찬', '광고', '제공받은'],
            'payment_terms': ['유료광고', 'AD', 'SPONSORED'],
            'disclosure_patterns': ['#광고', '#협찬', '#제공']
        }
    
    def analyze_ppl_probability(self, content_data):
        # 영상 설명, 음성 스크립트 기반 PPL 확률 계산
        return ppl_probability_score
```

### 2. 쿠팡 파트너스 연동
```python
class CoupangPartnerAPI:
    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key
        
    def search_product(self, product_name):
        # 제품명으로 쿠팡 검색
        # 매칭 제품 및 파트너스 링크 반환
        return search_results
```

### 3. 매력도 스코어링
```python
def calculate_attractiveness_score(sentiment_score, endorsement_score, influencer_score):
    """
    총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
    """
    total_score = (
        0.50 * sentiment_score +
        0.35 * endorsement_score + 
        0.15 * influencer_score
    )
    return min(100, max(0, total_score * 100))
```

### 4. 최종 JSON 스키마
```json
{
  "source_info": {
    "celebrity_name": "강민경",
    "channel_name": "걍밍경", 
    "video_title": "파리 출장 다녀왔습니다 VLOG",
    "video_url": "https://www.youtube.com/watch?v=...",
    "upload_date": "2025-06-22"
  },
  "candidate_info": {
    "product_name_ai": "아비에무아 숄더백 (베이지)",
    "clip_start_time": 315,
    "clip_end_time": 340,
    "category_path": ["패션잡화", "여성가방", "숄더백"],
    "features": ["수납이 넉넉해요", "가죽이 부드러워요"],
    "score_details": {
      "total": 88,
      "sentiment_score": 0.9,
      "endorsement_score": 0.85,
      "influencer_score": 0.9
    },
    "hook_sentence": "강민경이 '이것만 쓴다'고 말한 바로 그 숄더백?",
    "summary_for_caption": "사복 장인 강민경 님의 데일리백 정보!",
    "target_audience": ["20대 후반 여성", "30대 직장인"],
    "price_point": "프리미엄",
    "endorsement_type": "습관적 사용"
  },
  "monetization_info": {
    "is_coupang_product": true,
    "coupang_url_ai": "https://link.coupang.com/..."
  },
  "status_info": {
    "current_status": "needs_review",
    "is_ppl": false,
    "ppl_confidence": 0.1
  }
}
```

## 품질 기준

### 정확도 기준
- [ ] PPL 탐지 정확도 > 90%
- [ ] 쿠팡 제품 매칭 정확도 > 85%
- [ ] 매력도 스코어 신뢰도 > 88%
- [ ] 자동 필터링 정확도 > 92%

### 성능 기준
- [ ] 제품당 검증 시간 < 30초
- [ ] API 호출 성공률 > 99%
- [ ] 데이터 일관성 100% 보장
- [ ] 에러 핸들링 완전 구현

## 리스크 관리

### 주요 리스크
1. **쿠팡 API 제한**: 호출 횟수 및 속도 제한
2. **PPL 탐지 복잡성**: 암시적 광고의 미묘한 표현
3. **제품 매칭 정확도**: 동일 제품의 다양한 표현 방식

### 완화 방안
- API 호출 최적화 및 캐싱 전략
- 다양한 PPL 패턴 학습 데이터 구축
- 퍼지 매칭 및 유사도 알고리즘 적용

## 완료 조건

- [ ] 모든 태스크 100% 완료
- [ ] PPL 필터링 테스트 케이스 통과
- [ ] 쿠팡 API 연동 검증 완료
- [ ] 매력도 스코어링 정확도 검증
- [ ] 최종 JSON 스키마 검증 완료
- [ ] M01 마일스톤 완료 준비

## 다음 마일스톤 연계

S03 완료로 M01(AI Pipeline Foundation) 마일스톤이 완료되며, M02(Management Dashboard) 마일스톤에서 Streamlit 기반 관리 대시보드 구축을 시작합니다.