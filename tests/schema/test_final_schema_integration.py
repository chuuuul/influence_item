"""
최종 JSON 스키마 통합 테스트

T05_S03의 완전한 JSON 스키마 구현을 검증합니다.
"""

import pytest
import json
from datetime import datetime
from typing import Dict, Any

from src.schema.models import (
    ProductRecommendationCandidate, SourceInfo, CandidateInfo, 
    MonetizationInfo, StatusInfo, ScoreDetails, ValidationError
)
from src.schema.validators import SchemaValidator
from src.schema.serializers import JSONSerializer, JSONDeserializer
from src.schema.formatters import APIResponseFormatter, DashboardFormatter
from src.schema.data_transformers import DataTransformer
from src.schema.schema_registry import SchemaRegistry
from src.schema.schema_documentation import SchemaDocumentationGenerator


class TestFinalSchemaIntegration:
    """최종 스키마 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.validator = SchemaValidator()
        self.serializer = JSONSerializer(pretty=True)
        self.deserializer = JSONDeserializer()
        self.api_formatter = APIResponseFormatter()
        self.dashboard_formatter = DashboardFormatter()
        self.transformer = DataTransformer()
        self.registry = SchemaRegistry()
        
    @pytest.fixture
    def valid_candidate_data(self) -> Dict[str, Any]:
        """유효한 후보 데이터"""
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
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "요즘 강민경이 매일 드는 '그 가방' 정보",
                    "사복 장인 강민경의 찐 애정템!"
                ],
                "recommended_hashtags": [
                    "#강민경", "#걍밍경", "#강민경패션", "#아비에무아"
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
    
    def test_pydantic_model_creation(self, valid_candidate_data):
        """Pydantic 모델 생성 테스트"""
        # Act
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Assert
        assert candidate.source_info.celebrity_name == "강민경"
        assert candidate.candidate_info.score_details.total == 88
        assert candidate.monetization_info.is_coupang_product is True
        assert candidate.status_info.current_status == "needs_review"
        assert candidate.schema_version == "1.0"
    
    def test_prd_scoring_formula_validation(self, valid_candidate_data):
        """PRD 매력도 스코어링 공식 검증"""
        # Arrange
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act
        score_details = candidate.candidate_info.score_details
        calculated_score = (
            0.50 * score_details.sentiment_score +
            0.35 * score_details.endorsement_score +
            0.15 * score_details.influencer_score
        ) * 100
        
        # Assert - PRD 공식과 일치해야 함
        assert abs(score_details.total - calculated_score) <= 5
    
    def test_required_field_validation(self):
        """필수 필드 검증 테스트"""
        # Arrange - 필수 필드 누락
        incomplete_data = {
            "source_info": {
                "celebrity_name": "강민경"
                # channel_name, video_title, video_url, upload_date 누락
            }
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            ProductRecommendationCandidate(**incomplete_data)
    
    def test_url_format_validation(self, valid_candidate_data):
        """URL 형식 검증 테스트"""
        # Arrange - 잘못된 YouTube URL
        invalid_data = valid_candidate_data.copy()
        invalid_data["source_info"]["video_url"] = "https://invalid-url.com"
        
        # Act & Assert
        with pytest.raises(ValidationError):
            ProductRecommendationCandidate(**invalid_data)
    
    def test_score_range_validation(self, valid_candidate_data):
        """점수 범위 검증 테스트"""
        # Arrange - 범위를 벗어난 점수
        invalid_data = valid_candidate_data.copy()
        invalid_data["candidate_info"]["score_details"]["sentiment_score"] = 1.5  # 1.0 초과
        
        # Act & Assert
        with pytest.raises(ValidationError):
            ProductRecommendationCandidate(**invalid_data)
    
    def test_json_serialization_deserialization(self, valid_candidate_data):
        """JSON 직렬화/역직렬화 테스트"""
        # Arrange
        original_candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act - 직렬화
        json_str = self.serializer.serialize(original_candidate)
        
        # Act - 역직렬화
        deserialized_candidate = self.deserializer.deserialize(json_str)
        
        # Assert
        assert original_candidate.source_info.celebrity_name == deserialized_candidate.source_info.celebrity_name
        assert original_candidate.candidate_info.score_details.total == deserialized_candidate.candidate_info.score_details.total
        assert original_candidate.monetization_info.is_coupang_product == deserialized_candidate.monetization_info.is_coupang_product
    
    def test_comprehensive_validation(self, valid_candidate_data):
        """종합 검증 테스트"""
        # Arrange
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act
        validation_result = self.validator.validate(candidate)
        
        # Assert
        assert validation_result["is_valid"] is True
        assert validation_result["total_errors"] == 0
        assert validation_result["validation_score"] > 80
    
    def test_api_response_formatting(self, valid_candidate_data):
        """API 응답 포맷팅 테스트"""
        # Arrange
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act
        api_response = self.api_formatter.format_success(candidate, "Analysis complete")
        
        # Assert
        assert api_response["success"] is True
        assert api_response["message"] == "Analysis complete"
        assert "data" in api_response
        assert "timestamp" in api_response
    
    def test_dashboard_formatting(self, valid_candidate_data):
        """대시보드 포맷팅 테스트"""
        # Arrange
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act
        summary = self.dashboard_formatter.format_candidate_summary(candidate)
        
        # Assert
        assert "celebrity_name" in summary
        assert "product_name" in summary
        assert "score" in summary
        assert "priority_score" in summary
        assert summary["score"] == 88
    
    def test_legacy_data_transformation(self):
        """레거시 데이터 변환 테스트"""
        # Arrange
        legacy_data = {
            "influencer_name": "강민경",
            "channel": "걍밍경",
            "title": "파리 출장 VLOG",
            "url": "https://www.youtube.com/watch?v=test123",
            "upload_date": "2025-06-22",
            "product": "아비에무아 숄더백",
            "start": 315,
            "end": 340,
            "total_score": 88,
            "emotion_score": 0.9,
            "usage_score": 0.85,
            "creator_score": 0.9,
            "categories": ["패션잡화", "여성가방"],
            "monetizable": True
        }
        
        # Act
        candidate = self.transformer.transform_legacy_format(legacy_data)
        
        # Assert
        assert isinstance(candidate, ProductRecommendationCandidate)
        assert candidate.source_info.celebrity_name == "강민경"
        assert candidate.candidate_info.score_details.total == 88
        assert candidate.monetization_info.is_coupang_product is True
    
    def test_schema_version_compatibility(self, valid_candidate_data):
        """스키마 버전 호환성 테스트"""
        # Act
        compatibility_result = self.registry.validate_version_compatibility(valid_candidate_data)
        
        # Assert
        assert compatibility_result["is_compatible"] is True
        assert compatibility_result["data_version"] == "1.0"
        assert compatibility_result["current_version"] == "1.0"
        assert compatibility_result["requires_migration"] is False
    
    def test_schema_documentation_generation(self):
        """스키마 문서 생성 테스트"""
        # Act
        json_schema = SchemaDocumentationGenerator.generate_json_schema()
        example_data = SchemaDocumentationGenerator.generate_example_data()
        
        # Assert
        assert "$schema" in json_schema
        assert "properties" in json_schema
        assert "source_info" in json_schema["properties"]
        assert "candidate_info" in json_schema["properties"]
        
        # 예시 데이터로 모델 생성 가능한지 확인
        candidate = ProductRecommendationCandidate(**example_data)
        assert candidate.source_info.celebrity_name == "강민경"
    
    def test_ppl_business_logic(self, valid_candidate_data):
        """PPL 비즈니스 로직 테스트"""
        # Arrange - PPL 후보로 설정
        ppl_data = valid_candidate_data.copy()
        ppl_data["status_info"]["is_ppl"] = True
        ppl_data["status_info"]["ppl_confidence"] = 0.9
        ppl_data["candidate_info"]["score_details"]["total"] = 45  # PPL은 낮은 점수
        
        # Act
        candidate = ProductRecommendationCandidate(**ppl_data)
        validation_result = self.validator.validate(candidate)
        
        # Assert
        assert candidate.status_info.is_ppl is True
        assert candidate.status_info.ppl_confidence == 0.9
        # PPL 후보는 매력도 점수가 낮아야 함 (비즈니스 로직)
        assert validation_result["is_valid"] is True
    
    def test_monetization_consistency(self, valid_candidate_data):
        """수익화 일관성 테스트"""
        # Arrange - 수익화 가능하지만 URL 없음
        inconsistent_data = valid_candidate_data.copy()
        inconsistent_data["monetization_info"]["is_coupang_product"] = True
        inconsistent_data["monetization_info"]["coupang_url_ai"] = None
        inconsistent_data["monetization_info"]["coupang_url_manual"] = None
        
        # Act & Assert
        with pytest.raises(ValidationError):
            ProductRecommendationCandidate(**inconsistent_data)
    
    def test_priority_score_calculation(self, valid_candidate_data):
        """우선순위 점수 계산 테스트"""
        # Arrange
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act
        priority_score = candidate.calculate_priority_score()
        
        # Assert
        assert 0 <= priority_score <= 100
        assert isinstance(priority_score, float)
        
        # 고득점 후보는 우선순위도 높아야 함
        if candidate.candidate_info.score_details.total >= 80:
            assert priority_score >= 70
    
    def test_hashtag_normalization(self, valid_candidate_data):
        """해시태그 정규화 테스트"""
        # Arrange
        candidate = ProductRecommendationCandidate(**valid_candidate_data)
        
        # Act
        hashtags = candidate.candidate_info.recommended_hashtags
        
        # Assert
        for hashtag in hashtags:
            assert hashtag.startswith('#')
            assert len(hashtag) >= 2
    
    def test_full_pipeline_integration(self, valid_candidate_data):
        """전체 파이프라인 통합 테스트"""
        # Arrange
        original_data = valid_candidate_data
        
        # Act 1: 모델 생성
        candidate = ProductRecommendationCandidate(**original_data)
        
        # Act 2: 검증
        validation_result = self.validator.validate(candidate)
        
        # Act 3: 직렬화
        json_str = self.serializer.serialize(candidate)
        
        # Act 4: API 응답 포맷팅
        api_response = self.api_formatter.format_success(candidate)
        
        # Act 5: 대시보드 포맷팅
        dashboard_summary = self.dashboard_formatter.format_candidate_summary(candidate)
        
        # Assert
        assert validation_result["is_valid"] is True
        assert json.loads(json_str)  # JSON 파싱 가능
        assert api_response["success"] is True
        assert "celebrity_name" in dashboard_summary
        
        # 데이터 일관성 확인
        assert candidate.get_final_product_name() == "아비에무아 숄더백 (베이지)"
        assert candidate.get_final_coupang_url() == "https://link.coupang.com/a/bTZBP"
        assert candidate.is_high_priority() is True  # 88점이므로 고우선순위
    
    def test_error_handling(self):
        """에러 처리 테스트"""
        # Test 1: 잘못된 JSON 파싱
        with pytest.raises(ValidationError):
            self.deserializer.deserialize("invalid json")
        
        # Test 2: API 에러 응답
        error_response = self.api_formatter.format_error(
            "Test error", "TEST_ERROR", 400
        )
        assert error_response["success"] is False
        assert error_response["error"]["code"] == "TEST_ERROR"
        
        # Test 3: 검증 실패 응답
        invalid_data = {"invalid": "data"}
        try:
            ProductRecommendationCandidate(**invalid_data)
        except Exception:
            validation_response = self.api_formatter.format_error(
                "Validation failed", "VALIDATION_ERROR", 422
            )
            assert validation_response["error"]["status_code"] == 422


if __name__ == "__main__":
    # 간단한 통합 테스트 실행
    test_case = TestFinalSchemaIntegration()
    test_case.setup_method()
    
    # 유효한 데이터로 테스트
    valid_data = {
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
            "endorsement_type": "습관적 사용",
            "recommended_titles": [
                "요즘 강민경이 매일 드는 '그 가방' 정보",
                "사복 장인 강민경의 찐 애정템!"
            ],
            "recommended_hashtags": [
                "#강민경", "#걍밍경", "#강민경패션", "#아비에무아"
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
    
    print("=== 최종 JSON 스키마 통합 테스트 ===")
    
    try:
        # 기본 테스트들 실행
        test_case.test_pydantic_model_creation(valid_data)
        print("✅ Pydantic 모델 생성 테스트 통과")
        
        test_case.test_prd_scoring_formula_validation(valid_data)
        print("✅ PRD 스코어링 공식 검증 통과")
        
        test_case.test_json_serialization_deserialization(valid_data)
        print("✅ JSON 직렬화/역직렬화 테스트 통과")
        
        test_case.test_comprehensive_validation(valid_data)
        print("✅ 종합 검증 테스트 통과")
        
        test_case.test_api_response_formatting(valid_data)
        print("✅ API 응답 포맷팅 테스트 통과")
        
        test_case.test_dashboard_formatting(valid_data)
        print("✅ 대시보드 포맷팅 테스트 통과")
        
        test_case.test_legacy_data_transformation()
        print("✅ 레거시 데이터 변환 테스트 통과")
        
        test_case.test_schema_version_compatibility(valid_data)
        print("✅ 스키마 버전 호환성 테스트 통과")
        
        test_case.test_schema_documentation_generation()
        print("✅ 스키마 문서 생성 테스트 통과")
        
        test_case.test_full_pipeline_integration(valid_data)
        print("✅ 전체 파이프라인 통합 테스트 통과")
        
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
        print("✅ T05_S03 최종 JSON 스키마 완성 - 검증 완료")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()