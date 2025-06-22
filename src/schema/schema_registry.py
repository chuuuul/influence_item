"""
스키마 버전 관리

JSON 스키마의 버전 관리와 호환성을 처리합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class SchemaVersion:
    """스키마 버전 정보"""
    version: str
    release_date: str
    description: str
    breaking_changes: List[str]
    deprecated_fields: List[str]
    new_fields: List[str]
    migration_notes: str = ""


class SchemaRegistry:
    """스키마 레지스트리"""
    
    def __init__(self):
        self.versions = self._init_schema_versions()
        self.current_version = "1.0"
        
    def _init_schema_versions(self) -> Dict[str, SchemaVersion]:
        """스키마 버전 초기화"""
        return {
            "1.0": SchemaVersion(
                version="1.0",
                release_date="2025-06-23",
                description="PRD 명세 기반 초기 JSON 스키마",
                breaking_changes=[],
                deprecated_fields=[],
                new_fields=[
                    "source_info.*",
                    "candidate_info.*", 
                    "monetization_info.*",
                    "status_info.*"
                ],
                migration_notes="PRD section 3.3 명세에 따른 완전한 스키마 구현"
            )
        }
        
    def get_version_info(self, version: str) -> Optional[SchemaVersion]:
        """버전 정보 조회"""
        return self.versions.get(version)
        
    def get_current_version(self) -> str:
        """현재 버전 반환"""
        return self.current_version
        
    def get_latest_version(self) -> str:
        """최신 버전 반환"""
        # 버전 번호 기준 정렬 (추후 semantic versioning 적용)
        sorted_versions = sorted(self.versions.keys())
        return sorted_versions[-1]
        
    def is_compatible(self, source_version: str, target_version: str) -> bool:
        """버전 호환성 검사"""
        # 현재는 동일 버전만 호환
        # 추후 breaking change 분석 로직 추가 예정
        return source_version == target_version
        
    def get_migration_path(
        self, 
        from_version: str, 
        to_version: str
    ) -> List[Tuple[str, str]]:
        """마이그레이션 경로 반환"""
        # 현재는 직접 마이그레이션만 지원
        # 추후 단계별 마이그레이션 경로 지원 예정
        if from_version == to_version:
            return []
        elif self.is_compatible(from_version, to_version):
            return [(from_version, to_version)]
        else:
            return []  # 호환되지 않음
            
    def migrate_data(
        self, 
        data: Dict[str, Any], 
        from_version: str, 
        to_version: str
    ) -> Dict[str, Any]:
        """데이터 마이그레이션"""
        
        if from_version == to_version:
            return data
            
        # 현재는 1.0 버전만 지원하므로 마이그레이션 불필요
        if from_version != "1.0" or to_version != "1.0":
            raise ValueError(f"Unsupported migration: {from_version} -> {to_version}")
            
        # 스키마 버전 업데이트
        migrated_data = data.copy()
        migrated_data["schema_version"] = to_version
        migrated_data["migrated_at"] = datetime.now().isoformat()
        migrated_data["migration_from"] = from_version
        
        return migrated_data
        
    def validate_version_compatibility(
        self, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """버전 호환성 검증"""
        result = {
            "is_compatible": True,
            "data_version": None,
            "current_version": self.current_version,
            "requires_migration": False,
            "warnings": [],
            "errors": []
        }
        
        # 데이터에서 버전 정보 추출
        data_version = data.get("schema_version", "unknown")
        result["data_version"] = data_version
        
        if data_version == "unknown":
            result["warnings"].append("스키마 버전 정보가 없습니다")
            result["requires_migration"] = True
            
        elif data_version not in self.versions:
            result["is_compatible"] = False
            result["errors"].append(f"지원되지 않는 스키마 버전: {data_version}")
            
        elif data_version != self.current_version:
            if self.is_compatible(data_version, self.current_version):
                result["requires_migration"] = True
                result["warnings"].append(
                    f"스키마 버전이 다릅니다: {data_version} -> {self.current_version}"
                )
            else:
                result["is_compatible"] = False
                result["errors"].append(
                    f"호환되지 않는 스키마 버전: {data_version}"
                )
                
        return result
        
    def get_schema_changelog(self) -> List[Dict[str, Any]]:
        """스키마 변경 이력 반환"""
        changelog = []
        
        for version, info in sorted(self.versions.items()):
            entry = {
                "version": version,
                "release_date": info.release_date,
                "description": info.description,
                "changes": {
                    "breaking_changes": info.breaking_changes,
                    "deprecated_fields": info.deprecated_fields,
                    "new_fields": info.new_fields
                },
                "migration_notes": info.migration_notes
            }
            changelog.append(entry)
            
        return changelog
        
    def generate_compatibility_matrix(self) -> Dict[str, Dict[str, bool]]:
        """호환성 매트릭스 생성"""
        matrix = {}
        
        for source_version in self.versions.keys():
            matrix[source_version] = {}
            for target_version in self.versions.keys():
                matrix[source_version][target_version] = self.is_compatible(
                    source_version, target_version
                )
                
        return matrix
        
    def get_version_summary(self) -> Dict[str, Any]:
        """버전 요약 정보"""
        return {
            "total_versions": len(self.versions),
            "current_version": self.current_version,
            "latest_version": self.get_latest_version(),
            "available_versions": list(self.versions.keys()),
            "registry_updated_at": datetime.now().isoformat()
        }
        
    def export_schema_definitions(self) -> Dict[str, Any]:
        """스키마 정의 내보내기"""
        # 현재 버전의 JSON Schema 정의 생성
        # (실제로는 Pydantic 모델에서 자동 생성 가능)
        
        from .models import ProductRecommendationCandidate
        
        try:
            # Pydantic 모델에서 JSON Schema 생성
            json_schema = ProductRecommendationCandidate.schema()
            
            return {
                "schema_version": self.current_version,
                "generated_at": datetime.now().isoformat(),
                "json_schema": json_schema,
                "examples": self._get_schema_examples()
            }
            
        except Exception as e:
            logger.error(f"Failed to export schema definitions: {e}")
            return {
                "error": f"Failed to generate schema: {str(e)}"
            }
            
    def _get_schema_examples(self) -> List[Dict[str, Any]]:
        """스키마 예시 데이터 생성"""
        examples = [
            {
                "name": "high_score_candidate",
                "description": "고득점 후보 예시",
                "data": {
                    "source_info": {
                        "celebrity_name": "강민경",
                        "channel_name": "걍밍경",
                        "video_title": "파리 출장 다녀왔습니다 VLOG",
                        "video_url": "https://www.youtube.com/watch?v=example123",
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
                            "사복 장인 강민경의 찐 애정템! 아비에무아 숄더백"
                        ],
                        "recommended_hashtags": [
                            "#강민경", "#걍밍경", "#강민경패션", "#아비에무아", "#숄더백추천"
                        ]
                    },
                    "monetization_info": {
                        "is_coupang_product": True,
                        "coupang_url_ai": "https://link.coupang.com/example123",
                        "coupang_url_manual": None
                    },
                    "status_info": {
                        "current_status": "needs_review",
                        "is_ppl": False,
                        "ppl_confidence": 0.1,
                        "last_updated": None
                    },
                    "schema_version": "1.0",
                    "created_at": None,
                    "updated_at": None
                }
            }
        ]
        
        return examples