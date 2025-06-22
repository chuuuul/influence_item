"""
PPL 분류 및 라벨링 시스템

PPL 확률 결과를 바탕으로 콘텐츠를 분류하고 
적절한 라벨을 부여하는 모듈입니다.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PPLCategory(Enum):
    """PPL 카테고리 정의"""
    HIGH_PPL = "high_ppl_likely"
    MEDIUM_PPL = "medium_ppl_possible"
    LOW_PPL = "low_ppl_unlikely"
    ORGANIC = "no_ppl_organic"
    UNKNOWN = "unknown_error"


class ConfidenceLevel(Enum):
    """신뢰도 레벨 정의"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ORGANIC = "organic"


@dataclass
class PPLClassificationResult:
    """PPL 분류 결과"""
    category: PPLCategory
    confidence_level: ConfidenceLevel
    probability_score: float
    risk_level: str
    recommended_action: str
    filtering_decision: bool
    labels: List[str]
    metadata: Dict[str, Any]


class PPLClassifier:
    """PPL 확률 기반 분류 및 라벨링 시스템"""
    
    def __init__(self):
        """PPL 분류기 초기화"""
        self.logger = logging.getLogger(__name__)
        
        # 분류 임계값 설정
        self.classification_thresholds = {
            PPLCategory.HIGH_PPL: 0.8,
            PPLCategory.MEDIUM_PPL: 0.5,
            PPLCategory.LOW_PPL: 0.2,
            PPLCategory.ORGANIC: 0.0
        }
        
        # 위험도 레벨 매핑
        self.risk_levels = {
            PPLCategory.HIGH_PPL: "HIGH",
            PPLCategory.MEDIUM_PPL: "MEDIUM",
            PPLCategory.LOW_PPL: "LOW",
            PPLCategory.ORGANIC: "NONE",
            PPLCategory.UNKNOWN: "UNKNOWN"
        }
        
        # 권장 액션 매핑
        self.recommended_actions = {
            PPLCategory.HIGH_PPL: "FILTER_OUT",
            PPLCategory.MEDIUM_PPL: "MANUAL_REVIEW",
            PPLCategory.LOW_PPL: "PROCEED_WITH_CAUTION",
            PPLCategory.ORGANIC: "PROCEED",
            PPLCategory.UNKNOWN: "MANUAL_REVIEW"
        }

    def classify(
        self,
        probability_score: float,
        component_scores: Dict[str, float],
        context_indicators: List[str],
        confidence: float = 0.5
    ) -> PPLClassificationResult:
        """
        PPL 확률과 관련 정보를 바탕으로 콘텐츠 분류
        
        Args:
            probability_score: PPL 최종 확률 (0.0-1.0)
            component_scores: 컴포넌트별 점수
            context_indicators: 컨텍스트에서 발견된 지표들
            confidence: 분석 신뢰도
            
        Returns:
            PPLClassificationResult: 분류 결과
        """
        try:
            self.logger.info(f"PPL 분류 시작 - 확률: {probability_score:.3f}")
            
            # 기본 카테고리 분류
            category = self._determine_category(probability_score)
            
            # 신뢰도 레벨 결정
            confidence_level = self._determine_confidence_level(
                category, confidence, component_scores
            )
            
            # 위험도 및 권장 액션 결정
            risk_level = self.risk_levels[category]
            recommended_action = self.recommended_actions[category]
            
            # 필터링 결정 (HIGH_PPL만 필터링)
            filtering_decision = (category == PPLCategory.HIGH_PPL)
            
            # 라벨 생성
            labels = self._generate_labels(
                category, confidence_level, context_indicators, component_scores
            )
            
            # 메타데이터 생성
            metadata = self._generate_metadata(
                probability_score, component_scores, context_indicators, confidence
            )
            
            result = PPLClassificationResult(
                category=category,
                confidence_level=confidence_level,
                probability_score=probability_score,
                risk_level=risk_level,
                recommended_action=recommended_action,
                filtering_decision=filtering_decision,
                labels=labels,
                metadata=metadata
            )
            
            self.logger.info(
                f"PPL 분류 완료 - 카테고리: {category.value}, "
                f"신뢰도: {confidence_level.value}, 필터링: {filtering_decision}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"PPL 분류 오류: {str(e)}")
            return self._get_error_classification(str(e))

    def _determine_category(self, probability_score: float) -> PPLCategory:
        """
        확률 점수를 바탕으로 PPL 카테고리 결정
        
        Args:
            probability_score: PPL 확률 점수
            
        Returns:
            PPLCategory: 결정된 카테고리
        """
        if probability_score >= self.classification_thresholds[PPLCategory.HIGH_PPL]:
            return PPLCategory.HIGH_PPL
        elif probability_score >= self.classification_thresholds[PPLCategory.MEDIUM_PPL]:
            return PPLCategory.MEDIUM_PPL
        elif probability_score >= self.classification_thresholds[PPLCategory.LOW_PPL]:
            return PPLCategory.LOW_PPL
        else:
            return PPLCategory.ORGANIC

    def _determine_confidence_level(
        self,
        category: PPLCategory,
        analysis_confidence: float,
        component_scores: Dict[str, float]
    ) -> ConfidenceLevel:
        """
        카테고리와 분석 신뢰도를 바탕으로 전체 신뢰도 레벨 결정
        
        Args:
            category: PPL 카테고리
            analysis_confidence: 분석 신뢰도
            component_scores: 컴포넌트별 점수
            
        Returns:
            ConfidenceLevel: 신뢰도 레벨
        """
        try:
            # 카테고리별 기본 신뢰도
            if category == PPLCategory.ORGANIC:
                return ConfidenceLevel.ORGANIC
            
            # 컴포넌트 점수의 일관성 확인
            explicit_score = component_scores.get('explicit_patterns', 0.0)
            implicit_score = component_scores.get('implicit_patterns', 0.0)
            context_score = component_scores.get('context_analysis', 0.0)
            
            # 점수들의 분산 계산 (일관성 지표)
            scores = [explicit_score, implicit_score, context_score]
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            consistency = 1.0 - variance  # 낮은 분산 = 높은 일관성
            
            # 종합 신뢰도 계산
            overall_confidence = (analysis_confidence + consistency) / 2
            
            # 신뢰도 레벨 결정
            if overall_confidence >= 0.8:
                return ConfidenceLevel.HIGH
            elif overall_confidence >= 0.5:
                return ConfidenceLevel.MEDIUM
            else:
                return ConfidenceLevel.LOW
                
        except Exception:
            return ConfidenceLevel.LOW

    def _generate_labels(
        self,
        category: PPLCategory,
        confidence_level: ConfidenceLevel,
        context_indicators: List[str],
        component_scores: Dict[str, float]
    ) -> List[str]:
        """
        분류 결과를 바탕으로 라벨 생성
        
        Args:
            category: PPL 카테고리
            confidence_level: 신뢰도 레벨
            context_indicators: 컨텍스트 지표들
            component_scores: 컴포넌트별 점수
            
        Returns:
            List[str]: 생성된 라벨들
        """
        labels = []
        
        # 기본 카테고리 라벨
        category_labels = {
            PPLCategory.HIGH_PPL: "PPL_LIKELY",
            PPLCategory.MEDIUM_PPL: "PPL_POSSIBLE",
            PPLCategory.LOW_PPL: "PPL_UNLIKELY",
            PPLCategory.ORGANIC: "ORGANIC_CONTENT",
            PPLCategory.UNKNOWN: "UNKNOWN"
        }
        labels.append(category_labels[category])
        
        # 신뢰도 라벨
        if confidence_level != ConfidenceLevel.ORGANIC:
            labels.append(f"CONFIDENCE_{confidence_level.value.upper()}")
        
        # 컴포넌트별 특성 라벨
        explicit_score = component_scores.get('explicit_patterns', 0.0)
        implicit_score = component_scores.get('implicit_patterns', 0.0)
        
        if explicit_score > 0.7:
            labels.append("EXPLICIT_PATTERNS_STRONG")
        elif explicit_score > 0.3:
            labels.append("EXPLICIT_PATTERNS_WEAK")
        
        if implicit_score > 0.6:
            labels.append("IMPLICIT_SIGNALS_DETECTED")
        
        # 컨텍스트 지표 기반 라벨
        commercial_keywords = ["협찬", "광고", "할인", "이벤트", "제공"]
        found_commercial = [ind for ind in context_indicators if any(kw in ind for kw in commercial_keywords)]
        
        if found_commercial:
            labels.append("COMMERCIAL_LANGUAGE")
        
        # 브랜드 관련 라벨
        brand_keywords = ["브랜드", "공식", "파트너", "앰버서더"]
        found_brand = [ind for ind in context_indicators if any(kw in ind for kw in brand_keywords)]
        
        if found_brand:
            labels.append("BRAND_RELATIONSHIP")
        
        return labels

    def _generate_metadata(
        self,
        probability_score: float,
        component_scores: Dict[str, float],
        context_indicators: List[str],
        confidence: float
    ) -> Dict[str, Any]:
        """
        분류 관련 메타데이터 생성
        
        Args:
            probability_score: PPL 확률 점수
            component_scores: 컴포넌트별 점수
            context_indicators: 컨텍스트 지표들
            confidence: 분석 신뢰도
            
        Returns:
            Dict[str, Any]: 메타데이터
        """
        return {
            "probability_score": probability_score,
            "component_scores": component_scores,
            "context_indicators": context_indicators,
            "analysis_confidence": confidence,
            "classification_version": "1.0",
            "threshold_used": self.classification_thresholds,
            "score_breakdown": {
                "explicit_weight": 0.6,
                "implicit_weight": 0.25,
                "context_weight": 0.15
            }
        }

    def _get_error_classification(self, error_message: str) -> PPLClassificationResult:
        """
        오류 발생 시 기본 분류 결과 반환
        
        Args:
            error_message: 오류 메시지
            
        Returns:
            PPLClassificationResult: 오류 시 기본 결과
        """
        return PPLClassificationResult(
            category=PPLCategory.UNKNOWN,
            confidence_level=ConfidenceLevel.LOW,
            probability_score=0.5,
            risk_level="UNKNOWN",
            recommended_action="MANUAL_REVIEW",
            filtering_decision=False,
            labels=["ERROR", "REQUIRES_MANUAL_REVIEW"],
            metadata={"error": error_message}
        )

    def get_classification_summary(self, result: PPLClassificationResult) -> str:
        """
        분류 결과의 요약 문자열 생성
        
        Args:
            result: PPL 분류 결과
            
        Returns:
            str: 분류 결과 요약
        """
        return (
            f"카테고리: {result.category.value} | "
            f"확률: {result.probability_score:.3f} | "
            f"신뢰도: {result.confidence_level.value} | "
            f"위험도: {result.risk_level} | "
            f"필터링: {'예' if result.filtering_decision else '아니오'}"
        )

    def update_thresholds(self, new_thresholds: Dict[PPLCategory, float]):
        """
        분류 임계값 업데이트 (향후 성능 개선용)
        
        Args:
            new_thresholds: 새로운 임계값
        """
        # 임계값 유효성 검증
        sorted_categories = [PPLCategory.ORGANIC, PPLCategory.LOW_PPL, 
                           PPLCategory.MEDIUM_PPL, PPLCategory.HIGH_PPL]
        
        for i in range(len(sorted_categories) - 1):
            current_cat = sorted_categories[i]
            next_cat = sorted_categories[i + 1]
            
            if new_thresholds.get(current_cat, 0) >= new_thresholds.get(next_cat, 1):
                self.logger.warning("임계값 순서가 잘못됨. 업데이트 건너뜀")
                return
        
        self.classification_thresholds.update(new_thresholds)
        self.logger.info(f"분류 임계값 업데이트됨: {new_thresholds}")

    def get_filtering_stats(self, results: List[PPLClassificationResult]) -> Dict[str, Any]:
        """
        분류 결과들의 통계 정보 생성
        
        Args:
            results: PPL 분류 결과 리스트
            
        Returns:
            Dict[str, Any]: 통계 정보
        """
        if not results:
            return {"total": 0}
        
        total = len(results)
        filtered_count = sum(1 for r in results if r.filtering_decision)
        
        category_counts = {}
        for category in PPLCategory:
            category_counts[category.value] = sum(
                1 for r in results if r.category == category
            )
        
        return {
            "total": total,
            "filtered": filtered_count,
            "filter_rate": filtered_count / total,
            "category_distribution": category_counts,
            "average_probability": sum(r.probability_score for r in results) / total
        }