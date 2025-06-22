"""
JSON 스키마 문서 및 예시 생성

PRD 명세에 따른 완전한 JSON 스키마 문서화와 예시를 제공합니다.
"""

from typing import Dict, Any, List
import json
from datetime import datetime

from .models import ProductRecommendationCandidate, SourceInfo, CandidateInfo, MonetizationInfo, StatusInfo, ScoreDetails


class SchemaDocumentationGenerator:
    """스키마 문서 생성기"""
    
    @staticmethod
    def generate_json_schema() -> Dict[str, Any]:
        """JSON 스키마 정의 생성"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Product Recommendation Candidate Schema",
            "description": "연예인 추천 아이템 자동화 릴스 시스템의 제품 후보 데이터 스키마 (PRD v1.0 명세)",
            "type": "object",
            "required": ["source_info", "candidate_info", "monetization_info", "status_info"],
            "properties": {
                "source_info": {
                    "type": "object",
                    "description": "영상 소스 정보",
                    "required": ["celebrity_name", "channel_name", "video_title", "video_url", "upload_date"],
                    "properties": {
                        "celebrity_name": {
                            "type": "string",
                            "description": "연예인 이름",
                            "minLength": 1,
                            "example": "강민경"
                        },
                        "channel_name": {
                            "type": "string",
                            "description": "채널 이름",
                            "minLength": 1,
                            "example": "걍밍경"
                        },
                        "video_title": {
                            "type": "string",
                            "description": "영상 제목",
                            "minLength": 1,
                            "example": "파리 출장 다녀왔습니다 VLOG"
                        },
                        "video_url": {
                            "type": "string",
                            "format": "uri",
                            "pattern": "^https://www\\.youtube\\.com/watch\\?v=[\\w-]+$",
                            "description": "YouTube 영상 URL",
                            "example": "https://www.youtube.com/watch?v=example123"
                        },
                        "upload_date": {
                            "type": "string",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                            "description": "업로드 날짜 (YYYY-MM-DD)",
                            "example": "2025-06-22"
                        }
                    }
                },
                "candidate_info": {
                    "type": "object",
                    "description": "후보 제품 정보",
                    "required": [
                        "product_name_ai", "clip_start_time", "clip_end_time", 
                        "category_path", "score_details", "hook_sentence", 
                        "summary_for_caption", "price_point", "endorsement_type"
                    ],
                    "properties": {
                        "product_name_ai": {
                            "type": "string",
                            "description": "AI가 추출한 제품명",
                            "minLength": 1,
                            "example": "아비에무아 숄더백 (베이지)"
                        },
                        "product_name_manual": {
                            "type": ["string", "null"],
                            "description": "수동 수정 제품명",
                            "example": None
                        },
                        "clip_start_time": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "클립 시작 시간 (초)",
                            "example": 315
                        },
                        "clip_end_time": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "클립 종료 시간 (초)",
                            "example": 340
                        },
                        "category_path": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "카테고리 경로",
                            "example": ["패션잡화", "여성가방", "숄더백"]
                        },
                        "features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "제품 특징",
                            "example": ["수납이 넉넉해요", "가죽이 부드러워요"]
                        },
                        "score_details": {
                            "type": "object",
                            "description": "매력도 점수 세부사항 (PRD 공식: 0.50*감성 + 0.35*실사용 + 0.15*신뢰도)",
                            "required": ["total", "sentiment_score", "endorsement_score", "influencer_score"],
                            "properties": {
                                "total": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 100,
                                    "description": "총점 (0-100)",
                                    "example": 88
                                },
                                "sentiment_score": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                    "description": "감성 강도 (0.0-1.0)",
                                    "example": 0.9
                                },
                                "endorsement_score": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                    "description": "실사용 인증 강도 (0.0-1.0)",
                                    "example": 0.85
                                },
                                "influencer_score": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                    "description": "인플루언서 신뢰도 (0.0-1.0)",
                                    "example": 0.9
                                }
                            }
                        },
                        "hook_sentence": {
                            "type": "string",
                            "description": "관심 유발 훅 문장",
                            "minLength": 1,
                            "example": "강민경이 '이것만 쓴다'고 말한 바로 그 숄더백?"
                        },
                        "summary_for_caption": {
                            "type": "string",
                            "description": "캡션용 요약",
                            "minLength": 1,
                            "example": "사복 장인 강민경 님의 데일리백 정보! 넉넉한 수납과 부드러운 가죽이 특징인 아비에무아 숄더백이라고 해요."
                        },
                        "target_audience": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "타겟 오디언스",
                            "example": ["20대 후반 여성", "30대 직장인", "미니멀룩 선호자"]
                        },
                        "price_point": {
                            "type": "string",
                            "enum": ["저가", "일반", "프리미엄", "럭셔리"],
                            "description": "가격대",
                            "example": "프리미엄"
                        },
                        "endorsement_type": {
                            "type": "string",
                            "enum": ["명시적 추천", "자연스러운 언급", "습관적 사용", "비교 리뷰", "튜토리얼 시연"],
                            "description": "추천 유형",
                            "example": "습관적 사용"
                        },
                        "recommended_titles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 5,
                            "description": "추천 제목",
                            "example": [
                                "요즘 강민경이 매일 드는 '그 가방' 정보 (바로가기)",
                                "사복 장인 강민경의 찐 애정템! 아비에무아 숄더백"
                            ]
                        },
                        "recommended_hashtags": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "pattern": "^#.+"
                            },
                            "maxItems": 20,
                            "description": "추천 해시태그",
                            "example": ["#강민경", "#걍밍경", "#강민경패션", "#아비에무아", "#숄더백추천"]
                        }
                    }
                },
                "monetization_info": {
                    "type": "object",
                    "description": "수익화 정보",
                    "required": ["is_coupang_product"],
                    "properties": {
                        "is_coupang_product": {
                            "type": "boolean",
                            "description": "쿠팡 파트너스 제품 여부",
                            "example": True
                        },
                        "coupang_url_ai": {
                            "type": ["string", "null"],
                            "format": "uri",
                            "pattern": "^https://link\\.coupang\\.com/.+",
                            "description": "AI 생성 쿠팡 링크",
                            "example": "https://link.coupang.com/a/example"
                        },
                        "coupang_url_manual": {
                            "type": ["string", "null"],
                            "format": "uri",
                            "pattern": "^https://link\\.coupang\\.com/.+",
                            "description": "수동 설정 쿠팡 링크",
                            "example": None
                        }
                    }
                },
                "status_info": {
                    "type": "object",
                    "description": "상태 정보",
                    "required": ["current_status", "is_ppl", "ppl_confidence"],
                    "properties": {
                        "current_status": {
                            "type": "string",
                            "enum": [
                                "pending", "processing", "analysis_complete", "needs_review",
                                "high_ppl_risk", "ppl_review_required", "filtered_no_coupang",
                                "low_score_filtered", "approved", "rejected", "under_revision",
                                "published", "archived", "error"
                            ],
                            "description": "현재 상태",
                            "example": "needs_review"
                        },
                        "is_ppl": {
                            "type": "boolean",
                            "description": "PPL(유료광고) 여부",
                            "example": False
                        },
                        "ppl_confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "PPL 확률 (0.0-1.0)",
                            "example": 0.1
                        },
                        "last_updated": {
                            "type": ["string", "null"],
                            "format": "date-time",
                            "description": "마지막 업데이트 시간 (ISO 형식)",
                            "example": "2025-06-23T04:30:00Z"
                        }
                    }
                },
                "schema_version": {
                    "type": "string",
                    "description": "스키마 버전",
                    "default": "1.0",
                    "example": "1.0"
                },
                "created_at": {
                    "type": ["string", "null"],
                    "format": "date-time",
                    "description": "생성 시간",
                    "example": "2025-06-23T04:30:00Z"
                },
                "updated_at": {
                    "type": ["string", "null"],
                    "format": "date-time",
                    "description": "수정 시간",
                    "example": "2025-06-23T04:30:00Z"
                }
            }
        }
    
    @staticmethod
    def generate_example_data() -> Dict[str, Any]:
        """완전한 예시 데이터 생성"""
        return {
            "source_info": {
                "celebrity_name": "강민경",
                "channel_name": "걍밍경",
                "video_title": "파리 출장 다녀왔습니다 VLOG",
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "upload_date": "2025-06-22"
            },
            "candidate_info": {
                "product_name_ai": "아비에무아 숄더백 (베이지)",
                "product_name_manual": None,
                "clip_start_time": 315,
                "clip_end_time": 340,
                "category_path": ["패션잡화", "여성가방", "숄더백"],
                "features": ["수납이 넉넉해요", "가죽이 부드러워요", "어떤 옷에나 잘 어울려요"],
                "score_details": {
                    "total": 88,
                    "sentiment_score": 0.9,
                    "endorsement_score": 0.85,
                    "influencer_score": 0.9
                },
                "hook_sentence": "강민경이 '이것만 쓴다'고 말한 바로 그 숄더백?",
                "summary_for_caption": "사복 장인 강민경 님의 데일리백 정보! 넉넉한 수납과 부드러운 가죽이 특징인 아비에무아 숄더백이라고 해요. 어떤 옷에나 잘 어울려서 매일 손이 가는 찐 애정템이라고 하네요.",
                "target_audience": ["20대 후반 여성", "30대 직장인", "미니멀룩 선호자"],
                "price_point": "프리미엄",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "요즘 강민경이 매일 드는 '그 가방' 정보 (바로가기)",
                    "사복 장인 강민경의 찐 애정템! 아비에무아 숄더백",
                    "여름 데일리백 고민 끝! 강민경 PICK 가방 추천"
                ],
                "recommended_hashtags": [
                    "#강민경", "#걍밍경", "#강민경패션", "#아비에무아",
                    "#숄더백추천", "#여름가방", "#데일리백", "#연예인패션"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/a/bTZBP",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "needs_review",
                "is_ppl": False,
                "ppl_confidence": 0.1,
                "last_updated": "2025-06-23T04:30:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-23T04:30:00Z",
            "updated_at": "2025-06-23T04:30:00Z"
        }
    
    @staticmethod
    def generate_additional_examples() -> List[Dict[str, Any]]:
        """다양한 케이스의 추가 예시들"""
        examples = []
        
        # 예시 1: PPL 후보
        examples.append({
            "source_info": {
                "celebrity_name": "아이유",
                "channel_name": "IU Official",
                "video_title": "데일리 스킨케어 루틴 공개! (협찬)",
                "video_url": "https://www.youtube.com/watch?v=example1",
                "upload_date": "2025-06-20"
            },
            "candidate_info": {
                "product_name_ai": "라네즈 워터뱅크 하이드로 에센스",
                "product_name_manual": None,
                "clip_start_time": 180,
                "clip_end_time": 220,
                "category_path": ["뷰티", "스킨케어", "에센스"],
                "features": ["촉촉한 보습", "빠른 흡수"],
                "score_details": {
                    "total": 45,
                    "sentiment_score": 0.6,
                    "endorsement_score": 0.4,
                    "influencer_score": 0.8
                },
                "hook_sentence": "아이유의 광고지만 진짜 쓸까?",
                "summary_for_caption": "아이유 님이 협찬 영상에서 소개한 라네즈 에센스입니다.",
                "target_audience": ["20대 여성", "스킨케어 관심층"],
                "price_point": "일반",
                "endorsement_type": "명시적 추천",
                "recommended_titles": ["아이유 협찬템! 라네즈 에센스 솔직 후기"],
                "recommended_hashtags": ["#아이유", "#라네즈", "#협찬", "#스킨케어"]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/a/example1",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "high_ppl_risk",
                "is_ppl": True,
                "ppl_confidence": 0.9,
                "last_updated": "2025-06-23T04:30:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-23T04:30:00Z",
            "updated_at": "2025-06-23T04:30:00Z"
        })
        
        # 예시 2: 수익화 불가능한 제품
        examples.append({
            "source_info": {
                "celebrity_name": "박서준",
                "channel_name": "박서준TV",
                "video_title": "일본 여행 VLOG",
                "video_url": "https://www.youtube.com/watch?v=example2",
                "upload_date": "2025-06-18"
            },
            "candidate_info": {
                "product_name_ai": "도쿄역 한정판 키타로 라면",
                "product_name_manual": None,
                "clip_start_time": 450,
                "clip_end_time": 480,
                "category_path": ["식품", "라면", "한정판"],
                "features": ["도쿄역 한정", "특별한 맛"],
                "score_details": {
                    "total": 75,
                    "sentiment_score": 0.8,
                    "endorsement_score": 0.7,
                    "influencer_score": 0.8
                },
                "hook_sentence": "박서준이 극찬한 도쿄역 한정 라면!",
                "summary_for_caption": "박서준 님이 일본 여행에서 발견한 도쿄역 한정판 키타로 라면입니다.",
                "target_audience": ["20-30대 남성", "일본 여행 계획자"],
                "price_point": "일반",
                "endorsement_type": "자연스러운 언급",
                "recommended_titles": ["박서준 극찬! 도쿄역 한정 라면 찾아가기"],
                "recommended_hashtags": ["#박서준", "#도쿄여행", "#한정판", "#라면"]
            },
            "monetization_info": {
                "is_coupang_product": False,
                "coupang_url_ai": None,
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "filtered_no_coupang",
                "is_ppl": False,
                "ppl_confidence": 0.05,
                "last_updated": "2025-06-23T04:30:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-23T04:30:00Z",
            "updated_at": "2025-06-23T04:30:00Z"
        })
        
        return examples
    
    @staticmethod
    def generate_documentation_markdown() -> str:
        """마크다운 형식의 스키마 문서 생성"""
        schema = SchemaDocumentationGenerator.generate_json_schema()
        example = SchemaDocumentationGenerator.generate_example_data()
        
        md = """# 제품 추천 후보 JSON 스키마 문서

## 개요

연예인 추천 아이템 자동화 릴스 시스템의 핵심 데이터 구조입니다.
PRD v1.0 명세에 정의된 완전한 JSON 스키마를 구현합니다.

## 스키마 버전

- **현재 버전**: 1.0
- **스키마 ID**: `product-recommendation-candidate-schema-v1.0`
- **PRD 호환성**: PRD v1.0 100% 호환

## 데이터 구조

### 1. source_info (소스 정보)
영상의 기본 메타데이터를 포함합니다.

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| celebrity_name | string | ✅ | 연예인 이름 | "강민경" |
| channel_name | string | ✅ | 채널 이름 | "걍밍경" |
| video_title | string | ✅ | 영상 제목 | "파리 출장 다녀왔습니다 VLOG" |
| video_url | string | ✅ | YouTube URL | "https://www.youtube.com/watch?v=..." |
| upload_date | string | ✅ | 업로드 날짜 (YYYY-MM-DD) | "2025-06-22" |

### 2. candidate_info (후보 정보)
제품 후보의 상세 정보를 포함합니다.

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| product_name_ai | string | ✅ | AI 추출 제품명 | "아비에무아 숄더백 (베이지)" |
| product_name_manual | string/null | ❌ | 수동 수정 제품명 | null |
| clip_start_time | integer | ✅ | 시작 시간 (초) | 315 |
| clip_end_time | integer | ✅ | 종료 시간 (초) | 340 |
| category_path | array[string] | ✅ | 카테고리 경로 | ["패션잡화", "여성가방"] |
| features | array[string] | ❌ | 제품 특징 | ["수납이 넉넉해요"] |
| score_details | object | ✅ | 매력도 점수 | 아래 상세 참조 |
| hook_sentence | string | ✅ | 훅 문장 | "강민경이 쓰는 그 가방?" |
| summary_for_caption | string | ✅ | 캡션용 요약 | "강민경의 데일리백..." |
| target_audience | array[string] | ❌ | 타겟 오디언스 | ["20대 후반 여성"] |
| price_point | enum | ✅ | 가격대 | "프리미엄" |
| endorsement_type | enum | ✅ | 추천 유형 | "습관적 사용" |

#### score_details (매력도 점수)
PRD 공식: `총점 = (0.50 × 감성 강도) + (0.35 × 실사용 인증) + (0.15 × 인플루언서 신뢰도)`

| 필드 | 타입 | 범위 | 설명 |
|------|------|------|------|
| total | integer | 0-100 | 총점 |
| sentiment_score | float | 0.0-1.0 | 감성 강도 |
| endorsement_score | float | 0.0-1.0 | 실사용 인증 강도 |
| influencer_score | float | 0.0-1.0 | 인플루언서 신뢰도 |

### 3. monetization_info (수익화 정보)
쿠팡 파트너스 연동 정보를 포함합니다.

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| is_coupang_product | boolean | ✅ | 쿠팡 제품 여부 |
| coupang_url_ai | string/null | ❌ | AI 생성 쿠팡 링크 |
| coupang_url_manual | string/null | ❌ | 수동 설정 쿠팡 링크 |

### 4. status_info (상태 정보)
워크플로우 상태와 PPL 분석 결과를 포함합니다.

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| current_status | enum | ✅ | 현재 상태 |
| is_ppl | boolean | ✅ | PPL 여부 |
| ppl_confidence | float | ✅ | PPL 확률 (0.0-1.0) |
| last_updated | string/null | ❌ | 마지막 업데이트 시간 |

## 상태 코드 (current_status)

| 상태 | 설명 | 대시보드 표시 |
|------|------|---------------|
| `needs_review` | 검토 필요 | 🔍 검토 대기 |
| `approved` | 승인됨 | ✅ 승인 완료 |
| `rejected` | 반려됨 | ❌ 반려 |
| `filtered_no_coupang` | 수익화 불가 | 💰 수익화 필터링 |
| `published` | 업로드 완료 | 🚀 발행됨 |

## 검증 규칙

### 필수 검증
- 모든 required 필드 존재성
- URL 형식 검증 (YouTube, Coupang)
- 날짜 형식 검증 (YYYY-MM-DD, ISO datetime)
- 점수 범위 검증 (0.0-1.0, 0-100)

### 비즈니스 로직 검증
- PPL 후보는 매력도 점수 70 이하
- 고득점 후보(80+)는 수익화 가능해야 함
- 클립 길이 10-180초 범위
- 타겟 오디언스와 가격대 일관성

### 콘텐츠 품질 검증
- 제품명 길이 5-100자
- 훅 문장은 물음표(?) 또는 느낌표(!) 종료
- 해시태그 3-15개 범위
- 카테고리 깊이 2-5단계

## 예시 데이터

```json
""" + json.dumps(example, indent=2, ensure_ascii=False) + """
```

## API 응답 형식

실제 API에서는 다음과 같은 래퍼 형식으로 반환됩니다:

```json
{
  "success": true,
  "data": {
    // 위의 스키마 데이터
  },
  "schema_version": "1.0",
  "timestamp": "2025-06-23T04:30:00Z"
}
```

## 변경 이력

### v1.0 (2025-06-23)
- 초기 스키마 정의
- PRD v1.0 명세 완전 구현
- 매력도 스코어링 공식 적용
- PPL 필터링 로직 구현
- 쿠팡 파트너스 연동 지원

## 관련 문서

- [PRD v1.0](../PRD.md)
- [API 명세서](./api_specification.md)
- [데이터 검증 가이드](./validation_guide.md)
"""
        return md
    
    @staticmethod
    def save_documentation(output_dir: str = "docs/"):
        """문서 파일들을 저장"""
        import os
        from pathlib import Path
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # JSON 스키마 저장
        schema = SchemaDocumentationGenerator.generate_json_schema()
        with open(Path(output_dir) / "schema.json", "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        
        # 예시 데이터 저장
        example = SchemaDocumentationGenerator.generate_example_data()
        with open(Path(output_dir) / "example.json", "w", encoding="utf-8") as f:
            json.dump(example, f, indent=2, ensure_ascii=False)
        
        # 추가 예시들 저장
        additional_examples = SchemaDocumentationGenerator.generate_additional_examples()
        with open(Path(output_dir) / "additional_examples.json", "w", encoding="utf-8") as f:
            json.dump(additional_examples, f, indent=2, ensure_ascii=False)
        
        # 마크다운 문서 저장
        markdown = SchemaDocumentationGenerator.generate_documentation_markdown()
        with open(Path(output_dir) / "schema_documentation.md", "w", encoding="utf-8") as f:
            f.write(markdown)
        
        print(f"스키마 문서가 {output_dir}에 저장되었습니다:")
        print("- schema.json: JSON 스키마 정의")
        print("- example.json: 기본 예시 데이터")
        print("- additional_examples.json: 추가 예시들")
        print("- schema_documentation.md: 완전한 문서")


if __name__ == "__main__":
    # 문서 생성 테스트
    generator = SchemaDocumentationGenerator()
    
    # 스키마 생성
    schema = generator.generate_json_schema()
    print("JSON 스키마 생성 완료")
    
    # 예시 데이터 생성
    example = generator.generate_example_data()
    print("예시 데이터 생성 완료")
    
    # 문서 저장
    generator.save_documentation("../docs/schema/")
    print("문서 저장 완료")