---
sprint_id: S01
milestone_id: M01
sprint_name: Core AI Engine
status: planned
priority: critical
start_date: 2025-06-22
target_completion: 2025-06-29
progress_percentage: 0
estimated_effort_days: 7
actual_effort_days: 0
total_tasks: 5
completed_tasks: 0
---

# S01 - Core AI Engine

## 스프린트 개요

AI 2-Pass 파이프라인의 핵심 엔진을 구축하는 첫 번째 스프린트입니다. Whisper 음성 인식과 Gemini 텍스트 분석을 결합하여 YouTube 영상에서 제품 추천 구간을 자동으로 탐지하는 기본 시스템을 완성합니다.

## 스프린트 목표

1. **Whisper 음성 인식 파이프라인 구축**
2. **Gemini 1차 분석 (후보 구간 탐지) 구현**
3. **Gemini 2차 분석 (상세 정보 추출) 구현**
4. **기본 JSON 스키마 데이터 출력**
5. **통합 테스트 환경 구성**

## 성공 기준

- [ ] YouTube 영상 URL 입력 → 제품 추천 구간 JSON 출력까지 완전 자동화
- [ ] 테스트 영상 5개에서 정확한 제품 정보 추출 확인
- [ ] 프롬프트 엔지니어링을 통한 80% 이상 정확도 달성
- [ ] 모든 API 호출 에러 핸들링 완료
- [ ] 실행 시간 영상 1개당 3분 이내 처리

## 주요 태스크

### T01_S01 - Whisper 음성 인식 모듈 구현
- **파일**: `T01_S01_Whisper_Audio_Recognition.md`
- **목표**: YouTube 영상을 타임스탬프 포함 스크립트로 변환
- **기술**: OpenAI Whisper `small` 모델
- **산출물**: 음성 인식 파이프라인 모듈
- **복잡도**: Medium

### T02_S01 - Gemini 1차 분석 프롬프트 엔지니어링
- **파일**: `T02_S01_Gemini_First_Pass_Analysis.md`
- **목표**: 스크립트에서 제품 추천 후보 구간 탐지
- **기술**: Google Gemini 2.5 Flash API
- **산출물**: 정교한 프롬프트 및 분석 모듈
- **복잡도**: Medium

### T03_S01 - Gemini 2차 분석 종합 정보 추출
- **파일**: `T03_S01_Gemini_Second_Pass_Extraction.md`
- **목표**: 후보 구간의 상세 제품 정보 추출
- **기술**: Google Gemini 2.5 Flash API
- **산출물**: 구조화된 제품 정보 JSON 출력
- **복잡도**: Medium

### T04_S01 - 통합 파이프라인 구축
- **파일**: `T04_S01_Integrated_Pipeline.md`
- **목표**: 전체 워크플로우 연결 및 에러 핸들링
- **기술**: Python 비동기 처리
- **산출물**: 완전 자동화된 분석 시스템
- **복잡도**: Medium

### T05_S01 - 테스트 케이스 검증
- **파일**: `T05_S01_Test_Case_Validation.md`
- **목표**: 다양한 YouTube 영상으로 시스템 검증
- **기술**: 단위 테스트 + 통합 테스트
- **산출물**: 테스트 스위트 및 검증 리포트
- **복잡도**: Medium

## 기술 구현 세부사항

### 1. Whisper 음성 인식
```python
# 예상 구조
class WhisperProcessor:
    def __init__(self):
        self.model = whisper.load_model("small")
    
    def process_video(self, video_url):
        # YouTube 영상 다운로드 및 음성 추출
        # Whisper 모델로 타임스탬프 포함 스크립트 생성
        return transcription_with_timestamps
```

### 2. Gemini 1차 분석 프롬프트
```
핵심 패턴:
- 지칭 패턴: "제가 요즘 진짜 잘 쓰는 게..."
- 묘사 패턴: "딱 열면 향이 확 나는데..."
- 경험 공유: "이거 쓰고 나서 피부가 완전 달라졌어요"
- 소유 표현: "이건 제 파우치에 항상 들어있는 거예요"
```

### 3. JSON 스키마 출력
```json
{
  "source_info": {
    "video_url": "string",
    "celebrity_name": "string",
    "channel_name": "string"
  },
  "candidates": [
    {
      "start_time": "number",
      "end_time": "number", 
      "product_name": "string",
      "confidence_score": "number"
    }
  ]
}
```

## 품질 기준

### 코드 품질
- [ ] 모든 함수에 타입 힌트 추가
- [ ] 에러 핸들링 완료
- [ ] 로깅 시스템 구현
- [ ] 코드 문서화 완료

### 테스트 품질
- [ ] 단위 테스트 커버리지 80% 이상
- [ ] 통합 테스트 시나리오 완료
- [ ] 에러 케이스 테스트 포함
- [ ] 성능 테스트 완료

## 리스크 관리

### 주요 리스크
1. **Whisper 모델 정확도**: 한국어 음성 인식 성능
2. **Gemini API 응답 시간**: 대용량 스크립트 처리
3. **프롬프트 엔지니어링**: 정확한 구간 탐지

### 완화 방안
- Whisper 모델 파라미터 최적화
- Gemini API 호출 최적화 및 재시도 로직
- 다양한 프롬프트 패턴 테스트

## 완료 조건

- [ ] 모든 태스크 100% 완료
- [ ] 테스트 케이스 5개 모두 통과
- [ ] 코드 리뷰 완료
- [ ] 문서화 완료
- [ ] 다음 스프린트(S02) 준비 완료

## 다음 스프린트 연계

S01 완료 후 S02(시각 분석 및 통합)에서 OCR과 객체 인식을 추가하여 분석 정확도를 높입니다.