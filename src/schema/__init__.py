"""
JSON 스키마 모듈

PRD 명세에 정의된 완전한 JSON 스키마를 구현하고,
모든 분석 단계 결과를 통합하여 구조화된 데이터 출력을 제공합니다.

주요 컴포넌트:
- models: 완전한 Pydantic 모델
- validators: 데이터 검증 규칙
- serializers: JSON 직렬화/역직렬화
- schema_registry: 스키마 버전 관리
- formatters: 출력 포맷터
"""

from .models import (
    SourceInfo,
    ScoreDetails,
    CandidateInfo,
    MonetizationInfo,
    StatusInfo,
    ProductRecommendationCandidate,
    ValidationError
)
from .validators import SchemaValidator
from .serializers import JSONSerializer, JSONDeserializer
from .schema_registry import SchemaRegistry
from .formatters import APIResponseFormatter

__all__ = [
    'SourceInfo',
    'ScoreDetails', 
    'CandidateInfo',
    'MonetizationInfo',
    'StatusInfo',
    'ProductRecommendationCandidate',
    'ValidationError',
    'SchemaValidator',
    'JSONSerializer',
    'JSONDeserializer',
    'SchemaRegistry',
    'APIResponseFormatter'
]