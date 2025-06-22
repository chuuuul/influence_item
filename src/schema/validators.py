"""
데이터 검증 규칙

스키마 데이터의 유효성을 검증하고 비즈니스 규칙을 적용합니다.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import re
import logging

from .models import ProductRecommendationCandidate, ValidationError

logger = logging.getLogger(__name__)


class ValidationRule:
    """개별 검증 규칙"""
    
    def __init__(self, name: str, description: str, severity: str = "error"):
        self.name = name
        self.description = description
        self.severity = severity  # error, warning, info
        
    def validate(self, candidate: ProductRecommendationCandidate) -> Tuple[bool, str]:
        """
        검증 실행
        
        Returns:
            (is_valid, message)
        """
        raise NotImplementedError


class BusinessLogicValidator(ValidationRule):
    """비즈니스 로직 검증"""
    
    def __init__(self):
        super().__init__(
            "business_logic",
            "비즈니스 로직 일관성 검증",
            "error"
        )
        
    def validate(self, candidate: ProductRecommendationCandidate) -> Tuple[bool, str]:
        """비즈니스 규칙 검증"""
        errors = []
        
        # 1. PPL 후보는 낮은 매력도 점수를 가져야 함
        if candidate.status_info.is_ppl:
            if candidate.candidate_info.score_details.total > 70:
                errors.append("PPL 후보의 매력도 점수가 너무 높음")
                
        # 2. 고득점 후보는 수익화 가능해야 함
        if candidate.candidate_info.score_details.total >= 80:
            if not candidate.monetization_info.is_coupang_product:
                errors.append("고득점 후보가 수익화 불가능함")
                
        # 3. 클립 길이 적정성 검증
        duration = (
            candidate.candidate_info.clip_end_time - 
            candidate.candidate_info.clip_start_time
        )
        if duration < 10:
            errors.append("클립이 너무 짧음 (10초 미만)")
        elif duration > 180:
            errors.append("클립이 너무 긺 (180초 초과)")
            
        # 4. 타겟 오디언스와 가격대 일관성
        target_audience = candidate.candidate_info.target_audience
        price_point = candidate.candidate_info.price_point
        
        if "10대" in str(target_audience) and price_point == "럭셔리":
            errors.append("10대 타겟에 럭셔리 가격대는 부적절함")
            
        return len(errors) == 0, "; ".join(errors)


class ContentQualityValidator(ValidationRule):
    """콘텐츠 품질 검증"""
    
    def __init__(self):
        super().__init__(
            "content_quality",
            "콘텐츠 품질 검증",
            "warning"
        )
        
    def validate(self, candidate: ProductRecommendationCandidate) -> Tuple[bool, str]:
        """콘텐츠 품질 검증"""
        warnings = []
        
        # 1. 제품명 품질 검증
        product_name = candidate.candidate_info.product_name_ai
        if len(product_name) < 5:
            warnings.append("제품명이 너무 짧음")
        elif len(product_name) > 100:
            warnings.append("제품명이 너무 긺")
            
        # 2. 훅 문장 품질
        hook = candidate.candidate_info.hook_sentence
        if not hook.endswith('?') and not hook.endswith('!'):
            warnings.append("훅 문장이 의문문이나 감탄문이 아님")
            
        # 3. 해시태그 품질
        hashtags = candidate.candidate_info.recommended_hashtags
        if len(hashtags) < 3:
            warnings.append("해시태그가 너무 적음 (3개 미만)")
        elif len(hashtags) > 15:
            warnings.append("해시태그가 너무 많음 (15개 초과)")
            
        # 4. 카테고리 깊이
        category_depth = len(candidate.candidate_info.category_path)
        if category_depth < 2:
            warnings.append("카테고리가 너무 얕음")
        elif category_depth > 5:
            warnings.append("카테고리가 너무 깊음")
            
        return len(warnings) == 0, "; ".join(warnings)


class TechnicalValidator(ValidationRule):
    """기술적 검증"""
    
    def __init__(self):
        super().__init__(
            "technical",
            "기술적 요구사항 검증",
            "error"
        )
        
    def validate(self, candidate: ProductRecommendationCandidate) -> Tuple[bool, str]:
        """기술적 검증"""
        errors = []
        
        # 1. URL 접근 가능성 (기본 형식 검증)
        video_url = candidate.source_info.video_url
        if not video_url.startswith('https://www.youtube.com/watch?v='):
            errors.append("잘못된 YouTube URL 형식")
            
        # 2. 날짜 유효성
        try:
            upload_date = datetime.strptime(
                candidate.source_info.upload_date, 
                '%Y-%m-%d'
            )
            if upload_date > datetime.now():
                errors.append("미래 날짜는 허용되지 않음")
            elif upload_date < datetime.now() - timedelta(days=3650):  # 10년 전
                errors.append("너무 오래된 영상")
        except ValueError:
            errors.append("잘못된 날짜 형식")
            
        # 3. 필수 필드 존재성 재확인
        required_fields = [
            candidate.source_info.celebrity_name,
            candidate.candidate_info.product_name_ai,
            candidate.candidate_info.hook_sentence,
            candidate.candidate_info.summary_for_caption
        ]
        
        for i, field in enumerate(required_fields):
            if not field or not field.strip():
                field_names = [
                    "celebrity_name", "product_name_ai", 
                    "hook_sentence", "summary_for_caption"
                ]
                errors.append(f"필수 필드 누락: {field_names[i]}")
                
        return len(errors) == 0, "; ".join(errors)


class SchemaValidator:
    """통합 스키마 검증기"""
    
    def __init__(self):
        self.validators = [
            BusinessLogicValidator(),
            ContentQualityValidator(),
            TechnicalValidator()
        ]
        
    def validate(
        self, 
        candidate: ProductRecommendationCandidate,
        strict: bool = False
    ) -> Dict[str, Any]:
        """
        후보 데이터 검증
        
        Args:
            candidate: 검증할 후보 데이터
            strict: 엄격 모드 (warning도 오류로 처리)
            
        Returns:
            검증 결과 딕셔너리
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "info": [],
            "validation_summary": {}
        }
        
        # 1. Pydantic 모델 검증
        try:
            candidate.dict()  # 기본 검증 실행
        except Exception as e:
            result["is_valid"] = False
            result["errors"].append(f"모델 검증 오류: {str(e)}")
            
        # 2. 커스텀 검증 규칙 실행
        for validator in self.validators:
            try:
                is_valid, message = validator.validate(candidate)
                
                if not is_valid and message:
                    if validator.severity == "error":
                        result["errors"].append(f"{validator.name}: {message}")
                        result["is_valid"] = False
                    elif validator.severity == "warning":
                        result["warnings"].append(f"{validator.name}: {message}")
                        if strict:
                            result["is_valid"] = False
                    else:  # info
                        result["info"].append(f"{validator.name}: {message}")
                        
                result["validation_summary"][validator.name] = {
                    "passed": is_valid,
                    "severity": validator.severity,
                    "message": message if not is_valid else "OK"
                }
                
            except Exception as e:
                logger.error(f"Validator {validator.name} failed: {e}")
                result["errors"].append(f"검증기 오류 ({validator.name}): {str(e)}")
                result["is_valid"] = False
                
        # 3. 종합 평가
        result["total_errors"] = len(result["errors"])
        result["total_warnings"] = len(result["warnings"])
        result["validation_score"] = self._calculate_validation_score(result)
        
        return result
        
    def _calculate_validation_score(self, result: Dict[str, Any]) -> float:
        """검증 점수 계산 (0-100)"""
        errors = result["total_errors"]
        warnings = result["total_warnings"]
        
        # 기본 점수 100에서 차감
        score = 100.0
        score -= errors * 20  # 오류당 20점 차감
        score -= warnings * 5  # 경고당 5점 차감
        
        return max(0.0, score)
        
    def validate_batch(
        self, 
        candidates: List[ProductRecommendationCandidate],
        strict: bool = False
    ) -> Dict[str, Any]:
        """배치 검증"""
        batch_result = {
            "total_candidates": len(candidates),
            "valid_candidates": 0,
            "invalid_candidates": 0,
            "results": [],
            "summary": {
                "total_errors": 0,
                "total_warnings": 0,
                "average_score": 0.0
            }
        }
        
        total_score = 0.0
        
        for i, candidate in enumerate(candidates):
            result = self.validate(candidate, strict)
            result["candidate_index"] = i
            
            if result["is_valid"]:
                batch_result["valid_candidates"] += 1
            else:
                batch_result["invalid_candidates"] += 1
                
            batch_result["results"].append(result)
            batch_result["summary"]["total_errors"] += result["total_errors"]
            batch_result["summary"]["total_warnings"] += result["total_warnings"]
            total_score += result["validation_score"]
            
        if candidates:
            batch_result["summary"]["average_score"] = total_score / len(candidates)
            
        return batch_result
        
    def get_validation_report(self, result: Dict[str, Any]) -> str:
        """검증 결과 리포트 생성"""
        lines = []
        lines.append("=== 스키마 검증 결과 ===")
        lines.append(f"전체 상태: {'✅ 통과' if result['is_valid'] else '❌ 실패'}")
        lines.append(f"검증 점수: {result['validation_score']:.1f}/100")
        lines.append("")
        
        if result["errors"]:
            lines.append("🔴 오류:")
            for error in result["errors"]:
                lines.append(f"  - {error}")
            lines.append("")
            
        if result["warnings"]:
            lines.append("🟡 경고:")
            for warning in result["warnings"]:
                lines.append(f"  - {warning}")
            lines.append("")
            
        if result["info"]:
            lines.append("ℹ️ 정보:")
            for info in result["info"]:
                lines.append(f"  - {info}")
            lines.append("")
            
        lines.append("=== 검증기별 결과 ===")
        for name, summary in result["validation_summary"].items():
            status = "✅" if summary["passed"] else "❌"
            lines.append(f"{status} {name}: {summary['message']}")
            
        return "\n".join(lines)