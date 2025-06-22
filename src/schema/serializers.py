"""
JSON 직렬화/역직렬화

스키마 데이터의 JSON 변환을 처리합니다.
"""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging

from .models import ProductRecommendationCandidate, ValidationError

logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """커스텀 JSON 인코더"""
    
    def default(self, obj):
        """특수 객체 직렬화"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'value'):  # Enum 객체
            return obj.value
        elif hasattr(obj, 'dict'):  # Pydantic 모델
            return obj.dict()
        return super().default(obj)


class JSONSerializer:
    """JSON 직렬화기"""
    
    def __init__(self, pretty: bool = False, ensure_ascii: bool = False):
        """
        Args:
            pretty: 읽기 쉬운 형식으로 출력
            ensure_ascii: ASCII 인코딩 강제
        """
        self.pretty = pretty
        self.ensure_ascii = ensure_ascii
        
    def serialize(
        self, 
        candidate: ProductRecommendationCandidate,
        include_metadata: bool = True
    ) -> str:
        """
        후보 데이터를 JSON 문자열로 직렬화
        
        Args:
            candidate: 직렬화할 후보 데이터
            include_metadata: 메타데이터 포함 여부
            
        Returns:
            JSON 문자열
        """
        try:
            # 기본 데이터 추출
            data = candidate.dict()
            
            # 메타데이터 추가
            if include_metadata:
                data["serialized_at"] = datetime.now().isoformat()
                data["serializer_version"] = "1.0"
                
            # JSON 직렬화
            json_str = json.dumps(
                data,
                cls=JSONEncoder,
                indent=2 if self.pretty else None,
                ensure_ascii=self.ensure_ascii,
                sort_keys=True
            )
            
            return json_str
            
        except Exception as e:
            logger.error(f"JSON serialization failed: {e}")
            raise ValidationError(f"Failed to serialize data: {str(e)}")
            
    def serialize_batch(
        self, 
        candidates: List[ProductRecommendationCandidate],
        include_metadata: bool = True
    ) -> str:
        """
        여러 후보를 배치로 직렬화
        
        Args:
            candidates: 후보 데이터 목록
            include_metadata: 메타데이터 포함 여부
            
        Returns:
            JSON 문자열
        """
        try:
            batch_data = {
                "candidates": [candidate.dict() for candidate in candidates],
                "total_count": len(candidates)
            }
            
            if include_metadata:
                batch_data.update({
                    "batch_serialized_at": datetime.now().isoformat(),
                    "serializer_version": "1.0",
                    "batch_id": f"batch_{int(datetime.now().timestamp())}"
                })
                
            json_str = json.dumps(
                batch_data,
                cls=JSONEncoder,
                indent=2 if self.pretty else None,
                ensure_ascii=self.ensure_ascii,
                sort_keys=True
            )
            
            return json_str
            
        except Exception as e:
            logger.error(f"Batch JSON serialization failed: {e}")
            raise ValidationError(f"Failed to serialize batch data: {str(e)}")
            
    def to_api_response(
        self, 
        candidate: ProductRecommendationCandidate,
        success: bool = True,
        message: str = "",
        extra_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        API 응답 형식으로 직렬화
        
        Args:
            candidate: 후보 데이터
            success: 성공 여부
            message: 응답 메시지
            extra_data: 추가 데이터
            
        Returns:
            API 응답 JSON 문자열
        """
        try:
            response_data = {
                "success": success,
                "message": message,
                "data": candidate.dict() if candidate else None,
                "timestamp": datetime.now().isoformat(),
                "schema_version": candidate.schema_version if candidate else "1.0"
            }
            
            if extra_data:
                response_data.update(extra_data)
                
            return json.dumps(
                response_data,
                cls=JSONEncoder,
                indent=2 if self.pretty else None,
                ensure_ascii=self.ensure_ascii
            )
            
        except Exception as e:
            logger.error(f"API response serialization failed: {e}")
            raise ValidationError(f"Failed to serialize API response: {str(e)}")


class JSONDeserializer:
    """JSON 역직렬화기"""
    
    def __init__(self, strict: bool = True):
        """
        Args:
            strict: 엄격 모드 (잘못된 필드 허용 안함)
        """
        self.strict = strict
        
    def deserialize(self, json_str: str) -> ProductRecommendationCandidate:
        """
        JSON 문자열을 후보 데이터로 역직렬화
        
        Args:
            json_str: JSON 문자열
            
        Returns:
            ProductRecommendationCandidate 객체
        """
        try:
            # JSON 파싱
            data = json.loads(json_str)
            
            # 메타데이터 제거
            data.pop("serialized_at", None)
            data.pop("serializer_version", None)
            
            # Pydantic 모델 생성
            candidate = ProductRecommendationCandidate(**data)
            
            return candidate
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            raise ValidationError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise ValidationError(f"Failed to deserialize data: {str(e)}")
            
    def deserialize_batch(self, json_str: str) -> List[ProductRecommendationCandidate]:
        """
        배치 JSON을 후보 데이터 목록으로 역직렬화
        
        Args:
            json_str: 배치 JSON 문자열
            
        Returns:
            ProductRecommendationCandidate 객체 목록
        """
        try:
            # JSON 파싱
            batch_data = json.loads(json_str)
            
            # 후보 데이터 추출
            candidates_data = batch_data.get("candidates", [])
            
            # 각 후보를 Pydantic 모델로 변환
            candidates = []
            for i, candidate_data in enumerate(candidates_data):
                try:
                    candidate = ProductRecommendationCandidate(**candidate_data)
                    candidates.append(candidate)
                except Exception as e:
                    logger.error(f"Failed to deserialize candidate {i}: {e}")
                    if self.strict:
                        raise ValidationError(f"Failed to deserialize candidate {i}: {str(e)}")
                    # non-strict 모드에서는 건너뛰기
                    
            return candidates
            
        except json.JSONDecodeError as e:
            logger.error(f"Batch JSON parsing failed: {e}")
            raise ValidationError(f"Invalid batch JSON format: {str(e)}")
        except Exception as e:
            logger.error(f"Batch deserialization failed: {e}")
            raise ValidationError(f"Failed to deserialize batch data: {str(e)}")
            
    def from_dict(self, data: Dict[str, Any]) -> ProductRecommendationCandidate:
        """
        딕셔너리에서 후보 데이터 생성
        
        Args:
            data: 딕셔너리 데이터
            
        Returns:
            ProductRecommendationCandidate 객체
        """
        try:
            return ProductRecommendationCandidate(**data)
        except Exception as e:
            logger.error(f"Failed to create candidate from dict: {e}")
            raise ValidationError(f"Failed to create candidate from dict: {str(e)}")
            
    def validate_json_structure(self, json_str: str) -> Dict[str, Any]:
        """
        JSON 구조 유효성 사전 검증
        
        Args:
            json_str: JSON 문자열
            
        Returns:
            검증 결과
        """
        result = {
            "is_valid": True,
            "errors": [],
            "parsed_data": None
        }
        
        try:
            # JSON 파싱 검증
            data = json.loads(json_str)
            result["parsed_data"] = data
            
            # 필수 최상위 필드 확인
            required_top_fields = ["source_info", "candidate_info", "monetization_info", "status_info"]
            for field in required_top_fields:
                if field not in data:
                    result["errors"].append(f"Missing required field: {field}")
                    result["is_valid"] = False
                    
            # 각 섹션의 필수 필드 확인
            if "source_info" in data:
                required_source_fields = ["celebrity_name", "channel_name", "video_title", "video_url", "upload_date"]
                for field in required_source_fields:
                    if field not in data["source_info"]:
                        result["errors"].append(f"Missing source_info field: {field}")
                        result["is_valid"] = False
                        
            if "candidate_info" in data:
                required_candidate_fields = ["product_name_ai", "clip_start_time", "clip_end_time", "score_details"]
                for field in required_candidate_fields:
                    if field not in data["candidate_info"]:
                        result["errors"].append(f"Missing candidate_info field: {field}")
                        result["is_valid"] = False
                        
            # 점수 구조 확인
            if "candidate_info" in data and "score_details" in data["candidate_info"]:
                score_details = data["candidate_info"]["score_details"]
                required_score_fields = ["total", "sentiment_score", "endorsement_score", "influencer_score"]
                for field in required_score_fields:
                    if field not in score_details:
                        result["errors"].append(f"Missing score_details field: {field}")
                        result["is_valid"] = False
                        
        except json.JSONDecodeError as e:
            result["is_valid"] = False
            result["errors"].append(f"Invalid JSON syntax: {str(e)}")
        except Exception as e:
            result["is_valid"] = False
            result["errors"].append(f"Structure validation error: {str(e)}")
            
        return result