"""
출력 포맷터

다양한 출력 형식으로 스키마 데이터를 변환합니다.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import csv
import io
import logging

from .models import ProductRecommendationCandidate
from .serializers import JSONSerializer

logger = logging.getLogger(__name__)


class APIResponseFormatter:
    """API 응답 포맷터"""
    
    def __init__(self, include_debug: bool = False):
        """
        Args:
            include_debug: 디버그 정보 포함 여부
        """
        self.include_debug = include_debug
        self.json_serializer = JSONSerializer(pretty=True)
        
    def format_success(
        self,
        data: Union[ProductRecommendationCandidate, List[ProductRecommendationCandidate]],
        message: str = "Success",
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """성공 응답 포맷"""
        
        response = {
            "success": True,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": None
        }
        
        # 데이터 처리
        if isinstance(data, list):
            response["data"] = {
                "candidates": [candidate.dict() for candidate in data],
                "count": len(data)
            }
        elif isinstance(data, ProductRecommendationCandidate):
            response["data"] = data.dict()
        else:
            response["data"] = data
            
        # 추가 데이터
        if extra_data:
            response.update(extra_data)
            
        # 디버그 정보
        if self.include_debug:
            response["debug"] = {
                "formatter_version": "1.0",
                "processing_time_ms": 0,  # 실제로는 측정 필요
                "memory_usage_mb": 0      # 실제로는 측정 필요
            }
            
        return response
        
    def format_error(
        self,
        error_message: str,
        error_code: str = "GENERIC_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """오류 응답 포맷"""
        
        response = {
            "success": False,
            "error": {
                "code": error_code,
                "message": error_message,
                "status_code": status_code
            },
            "timestamp": datetime.now().isoformat(),
            "data": None
        }
        
        if details:
            response["error"]["details"] = details
            
        if self.include_debug:
            response["debug"] = {
                "stack_trace": None,  # 프로덕션에서는 제외
                "request_id": f"req_{int(datetime.now().timestamp())}"
            }
            
        return response
        
    def format_validation_result(
        self,
        validation_result: Dict[str, Any],
        candidate: Optional[ProductRecommendationCandidate] = None
    ) -> Dict[str, Any]:
        """검증 결과 포맷"""
        
        if validation_result["is_valid"]:
            return self.format_success(
                data=candidate,
                message="Validation passed",
                extra_data={
                    "validation": {
                        "score": validation_result["validation_score"],
                        "warnings": validation_result["warnings"]
                    }
                }
            )
        else:
            return self.format_error(
                error_message="Validation failed",
                error_code="VALIDATION_ERROR",
                status_code=422,
                details={
                    "errors": validation_result["errors"],
                    "warnings": validation_result["warnings"],
                    "validation_score": validation_result["validation_score"]
                }
            )


class DashboardFormatter:
    """대시보드용 포맷터"""
    
    def format_candidate_summary(
        self, 
        candidate: ProductRecommendationCandidate
    ) -> Dict[str, Any]:
        """후보 요약 정보 포맷"""
        
        return {
            "id": f"{candidate.source_info.video_url}#{candidate.candidate_info.clip_start_time}",
            "celebrity_name": candidate.source_info.celebrity_name,
            "product_name": candidate.get_final_product_name(),
            "score": candidate.candidate_info.score_details.total,
            "status": candidate.status_info.current_status,
            "is_monetizable": candidate.monetization_info.is_coupang_product,
            "ppl_risk": candidate.status_info.ppl_confidence,
            "upload_date": candidate.source_info.upload_date,
            "priority_score": candidate.calculate_priority_score(),
            "clip_duration": (
                candidate.candidate_info.clip_end_time - 
                candidate.candidate_info.clip_start_time
            ),
            "category": " > ".join(candidate.candidate_info.category_path),
            "price_point": candidate.candidate_info.price_point
        }
        
    def format_batch_summary(
        self, 
        candidates: List[ProductRecommendationCandidate]
    ) -> Dict[str, Any]:
        """배치 요약 정보 포맷"""
        
        if not candidates:
            return {
                "total_count": 0,
                "summary": {},
                "candidates": []
            }
            
        # 통계 계산
        total_count = len(candidates)
        avg_score = sum(c.candidate_info.score_details.total for c in candidates) / total_count
        monetizable_count = sum(1 for c in candidates if c.monetization_info.is_coupang_product)
        high_ppl_count = sum(1 for c in candidates if c.status_info.ppl_confidence > 0.7)
        
        # 상태별 분포
        status_distribution = {}
        for candidate in candidates:
            status = candidate.status_info.current_status
            status_distribution[status] = status_distribution.get(status, 0) + 1
            
        # 카테고리별 분포
        category_distribution = {}
        for candidate in candidates:
            category = candidate.candidate_info.category_path[0] if candidate.candidate_info.category_path else "기타"
            category_distribution[category] = category_distribution.get(category, 0) + 1
            
        return {
            "total_count": total_count,
            "summary": {
                "average_score": round(avg_score, 1),
                "monetizable_rate": round(monetizable_count / total_count * 100, 1),
                "high_ppl_rate": round(high_ppl_count / total_count * 100, 1),
                "status_distribution": status_distribution,
                "category_distribution": category_distribution
            },
            "candidates": [self.format_candidate_summary(c) for c in candidates]
        }


class ExportFormatter:
    """데이터 내보내기 포맷터"""
    
    def to_csv(
        self, 
        candidates: List[ProductRecommendationCandidate],
        include_metadata: bool = False
    ) -> str:
        """CSV 형식으로 내보내기"""
        
        output = io.StringIO()
        
        # 헤더 정의
        headers = [
            "celebrity_name", "channel_name", "video_title", "video_url", "upload_date",
            "product_name_ai", "product_name_manual", "clip_start_time", "clip_end_time",
            "total_score", "sentiment_score", "endorsement_score", "influencer_score",
            "hook_sentence", "summary_for_caption", "price_point", "endorsement_type",
            "is_coupang_product", "coupang_url_ai", "current_status", "is_ppl", "ppl_confidence"
        ]
        
        if include_metadata:
            headers.extend(["schema_version", "created_at", "updated_at"])
            
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        # 데이터 행 작성
        for candidate in candidates:
            row = {
                "celebrity_name": candidate.source_info.celebrity_name,
                "channel_name": candidate.source_info.channel_name,
                "video_title": candidate.source_info.video_title,
                "video_url": candidate.source_info.video_url,
                "upload_date": candidate.source_info.upload_date,
                "product_name_ai": candidate.candidate_info.product_name_ai,
                "product_name_manual": candidate.candidate_info.product_name_manual,
                "clip_start_time": candidate.candidate_info.clip_start_time,
                "clip_end_time": candidate.candidate_info.clip_end_time,
                "total_score": candidate.candidate_info.score_details.total,
                "sentiment_score": candidate.candidate_info.score_details.sentiment_score,
                "endorsement_score": candidate.candidate_info.score_details.endorsement_score,
                "influencer_score": candidate.candidate_info.score_details.influencer_score,
                "hook_sentence": candidate.candidate_info.hook_sentence,
                "summary_for_caption": candidate.candidate_info.summary_for_caption,
                "price_point": candidate.candidate_info.price_point,
                "endorsement_type": candidate.candidate_info.endorsement_type,
                "is_coupang_product": candidate.monetization_info.is_coupang_product,
                "coupang_url_ai": candidate.monetization_info.coupang_url_ai,
                "current_status": candidate.status_info.current_status,
                "is_ppl": candidate.status_info.is_ppl,
                "ppl_confidence": candidate.status_info.ppl_confidence
            }
            
            if include_metadata:
                row.update({
                    "schema_version": candidate.schema_version,
                    "created_at": candidate.created_at,
                    "updated_at": candidate.updated_at
                })
                
            writer.writerow(row)
            
        return output.getvalue()
        
    def to_excel_ready(
        self, 
        candidates: List[ProductRecommendationCandidate]
    ) -> Dict[str, Any]:
        """Excel 내보내기용 데이터 준비"""
        
        # 메인 데이터 시트
        main_sheet = []
        for candidate in candidates:
            row = {
                "연예인": candidate.source_info.celebrity_name,
                "채널": candidate.source_info.channel_name,
                "영상제목": candidate.source_info.video_title,
                "제품명": candidate.get_final_product_name(),
                "총점": candidate.candidate_info.score_details.total,
                "클립시간": f"{candidate.candidate_info.clip_start_time}-{candidate.candidate_info.clip_end_time}",
                "카테고리": " > ".join(candidate.candidate_info.category_path),
                "가격대": candidate.candidate_info.price_point,
                "상태": candidate.status_info.current_status,
                "수익화가능": "가능" if candidate.monetization_info.is_coupang_product else "불가능",
                "PPL위험도": f"{candidate.status_info.ppl_confidence:.1%}",
                "업로드일": candidate.source_info.upload_date
            }
            main_sheet.append(row)
            
        # 통계 시트
        dashboard_formatter = DashboardFormatter()
        summary = dashboard_formatter.format_batch_summary(candidates)
        
        stats_sheet = [
            {"항목": "전체 후보 수", "값": summary["total_count"]},
            {"항목": "평균 점수", "값": summary["summary"]["average_score"]},
            {"항목": "수익화 가능 비율", "값": f"{summary['summary']['monetizable_rate']}%"},
            {"항목": "PPL 위험 비율", "값": f"{summary['summary']['high_ppl_rate']}%"}
        ]
        
        return {
            "main_data": main_sheet,
            "statistics": stats_sheet,
            "export_info": {
                "exported_at": datetime.now().isoformat(),
                "total_records": len(candidates),
                "format_version": "1.0"
            }
        }


class ReportFormatter:
    """보고서 포맷터"""
    
    def generate_analysis_report(
        self, 
        candidates: List[ProductRecommendationCandidate]
    ) -> Dict[str, Any]:
        """분석 보고서 생성"""
        
        if not candidates:
            return {"error": "No candidates provided"}
            
        dashboard_formatter = DashboardFormatter()
        summary = dashboard_formatter.format_batch_summary(candidates)
        
        # 성능 분석
        high_score_candidates = [c for c in candidates if c.candidate_info.score_details.total >= 80]
        low_ppl_candidates = [c for c in candidates if c.status_info.ppl_confidence <= 0.3]
        monetizable_candidates = [c for c in candidates if c.monetization_info.is_coupang_product]
        
        # 추천 사항
        recommendations = []
        if len(high_score_candidates) / len(candidates) < 0.3:
            recommendations.append("고득점 후보 비율이 낮습니다. 분석 품질을 개선하세요.")
        if len(monetizable_candidates) / len(candidates) < 0.5:
            recommendations.append("수익화 가능 후보가 부족합니다. 제품 매칭 로직을 개선하세요.")
        if not recommendations:
            recommendations.append("전체적으로 양호한 품질의 후보들입니다.")
            
        return {
            "report_generated_at": datetime.now().isoformat(),
            "summary": summary["summary"],
            "analysis": {
                "total_candidates": len(candidates),
                "high_score_candidates": len(high_score_candidates),
                "low_ppl_candidates": len(low_ppl_candidates),
                "monetizable_candidates": len(monetizable_candidates),
                "quality_metrics": {
                    "high_score_rate": len(high_score_candidates) / len(candidates),
                    "low_ppl_rate": len(low_ppl_candidates) / len(candidates),
                    "monetization_rate": len(monetizable_candidates) / len(candidates)
                }
            },
            "recommendations": recommendations,
            "top_performers": [
                dashboard_formatter.format_candidate_summary(c) 
                for c in sorted(candidates, key=lambda x: x.candidate_info.score_details.total, reverse=True)[:5]
            ]
        }