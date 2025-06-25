"""
PPL 분류 및 라벨링 시스템

PPL 확률 결과를 바탕으로 콘텐츠를 분류하고 
적절한 라벨을 부여하는 모듈입니다.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import Counter, defaultdict
import pickle
import os
from datetime import datetime, timedelta
import json

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
    """고도화된 PPL 분류 및 라벨링 시스템 (95% 정확도 목표)"""
    
    def __init__(self):
        """PPL 분류기 초기화"""
        self.logger = logging.getLogger(__name__)
        
        # ML 기반 동적 임계값 (성능 기반 자동 조정)
        self.classification_thresholds = {
            PPLCategory.HIGH_PPL: 0.75,    # 정확도 향상을 위한 조정
            PPLCategory.MEDIUM_PPL: 0.55,  # 정밀도 개선
            PPLCategory.LOW_PPL: 0.25,     # False Negative 최소화
            PPLCategory.ORGANIC: 0.0
        }
        
        # ML 모델 상태
        self.ml_model = None
        self.feature_weights = None
        self.performance_history = []
        self.adaptive_thresholds = self.classification_thresholds.copy()
        
        # 컨텍스트 분석 강화를 위한 데이터
        self.context_patterns = self._initialize_context_patterns()
        self.linguistic_features = self._initialize_linguistic_features()
        
        # 학습 데이터 저장소
        self.training_data = {
            'features': [],
            'labels': [],
            'feedback': []
        }
        
        # 위험도 레벨 매핑 (정밀화된 분류)
        self.risk_levels = {
            PPLCategory.HIGH_PPL: "HIGH",
            PPLCategory.MEDIUM_PPL: "MEDIUM",
            PPLCategory.LOW_PPL: "LOW",
            PPLCategory.ORGANIC: "NONE",
            PPLCategory.UNKNOWN: "UNKNOWN"
        }
        
        # 개선된 권장 액션 (비즈니스 로직 정밀화)
        self.recommended_actions = {
            PPLCategory.HIGH_PPL: "AUTOMATIC_FILTER",      # 자동 필터링
            PPLCategory.MEDIUM_PPL: "ADVANCED_REVIEW",     # 고급 검토
            PPLCategory.LOW_PPL: "CONDITIONAL_PROCEED",    # 조건부 진행
            PPLCategory.ORGANIC: "AUTOMATIC_APPROVE",      # 자동 승인
            PPLCategory.UNKNOWN: "EXPERT_REVIEW"           # 전문가 검토
        }

    def classify(
        self,
        probability_score: float,
        component_scores: Dict[str, float],
        context_indicators: List[str],
        confidence: float = 0.5,
        text_content: str = "",
        additional_features: Dict[str, Any] = None
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
            self.logger.info(f"고급 PPL 분류 시작 - 확률: {probability_score:.3f}")
            
            # 고급 특성 추출
            advanced_features = self._extract_advanced_features(
                text_content, component_scores, context_indicators
            )
            
            # ML 기반 분류 (가능한 경우)
            if self.ml_model is not None:
                ml_category, ml_confidence = self._ml_classify(advanced_features)
                # ML 결과와 기존 결과 결합
                category = self._combine_classifications(probability_score, ml_category)
                confidence = max(confidence, ml_confidence)
            else:
                # 개선된 휴리스틱 분류
                category = self._advanced_determine_category(
                    probability_score, advanced_features, context_indicators
                )
            
            # 동적 신뢰도 레벨 결정
            confidence_level = self._advanced_determine_confidence_level(
                category, confidence, component_scores, advanced_features
            )
            
            # 위험도 및 권장 액션 결정
            risk_level = self.risk_levels[category]
            recommended_action = self.recommended_actions[category]
            
            # 필터링 결정 (HIGH_PPL과 MEDIUM_PPL 모두 PPL로 판정)
            filtering_decision = (category in [PPLCategory.HIGH_PPL, PPLCategory.MEDIUM_PPL])
            
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

    def _initialize_context_patterns(self) -> Dict[str, List[str]]:
        """컨텍스트 패턴 초기화 (정확도 향상)"""
        return {
            'commercial_intent': [
                '구매링크', '할인코드', '쿠폰번호', '특가이벤트', '한정판매',
                '선착순', '마감임박', '지금바로', '놓치면안되는', '기회',
                '최저가', '파격할인', '무료배송', '당일발송'
            ],
            'brand_relationship': [
                '브랜드파트너', '앰버서더', '공식협력', '후원업체', '제공업체',
                '협업브랜드', '파트너십', '공식인증', '브랜드멤버'
            ],
            'disclosure_patterns': [
                '#광고표시', '#유료광고', '#협찬표기', '#제공받음',
                'paid partnership', 'sponsored content', 'ad', 'promotion'
            ],
            'soft_ppl': [
                '개인적으로추천', '정말좋아해서', '자주사용하는', '애정템',
                '필수템', '인생템', '리피트', '재구매예정'
            ]
        }
    
    def _initialize_linguistic_features(self) -> Dict[str, Any]:
        """언어학적 특성 초기화"""
        return {
            'persuasive_words': ['강추', '무조건', '진짜', '정말로', '완전', '엄청'],
            'urgency_indicators': ['지금', '당장', '빨리', '서둘러', '마감', '마지막'],
            'emotion_amplifiers': ['대박', '미쳤다', '완전', '진짜', '엄청', '너무'],
            'credibility_markers': ['솔직히', '정직하게', '진심으로', '사실은']
        }
    
    def _extract_advanced_features(
        self, 
        text_content: str, 
        component_scores: Dict[str, float],
        context_indicators: List[str]
    ) -> Dict[str, float]:
        """고급 특성 추출 (ML 기반 정확도 향상)"""
        features = {}
        
        if not text_content:
            return {'default_features': 1.0}
        
        text_lower = text_content.lower()
        
        # 1. 컨텍스트 패턴 점수
        for pattern_type, patterns in self.context_patterns.items():
            count = sum(1 for pattern in patterns if pattern.lower() in text_lower)
            features[f'context_{pattern_type}'] = min(count / len(patterns), 1.0)
        
        # 2. 언어학적 특성
        for feature_type, words in self.linguistic_features.items():
            count = sum(1 for word in words if word in text_lower)
            features[f'linguistic_{feature_type}'] = min(count / len(words), 1.0)
        
        # 3. 텍스트 복잡도 분석
        sentences = text_content.split('.')
        avg_sentence_length = np.mean([len(s.split()) for s in sentences if s.strip()])
        features['text_complexity'] = min(avg_sentence_length / 20, 1.0)
        
        # 4. 감정 극성 분석 (간단한 휴리스틱)
        positive_words = ['좋다', '추천', '만족', '완벽', '최고', '훌륭']
        negative_words = ['아쉽다', '별로', '실망', '부족', '나쁘다']
        
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count + neg_count > 0:
            features['sentiment_polarity'] = pos_count / (pos_count + neg_count)
        else:
            features['sentiment_polarity'] = 0.5
        
        # 5. 기존 컴포넌트 점수 통합
        features.update({f'component_{k}': v for k, v in component_scores.items()})
        
        return features
    
    def _ml_classify(self, features: Dict[str, float]) -> Tuple[PPLCategory, float]:
        """ML 모델 기반 분류 (향후 구현 예정)"""
        # 현재는 플레이스홀더, 실제 ML 모델 연동 시 구현
        confidence = 0.8
        
        # 특성 기반 가중치 계산
        commercial_score = features.get('context_commercial_intent', 0)
        brand_score = features.get('context_brand_relationship', 0)
        disclosure_score = features.get('context_disclosure_patterns', 0)
        
        combined_score = (commercial_score * 0.4 + brand_score * 0.3 + disclosure_score * 0.3)
        
        if combined_score > 0.7:
            return PPLCategory.HIGH_PPL, confidence
        elif combined_score > 0.4:
            return PPLCategory.MEDIUM_PPL, confidence * 0.8
        elif combined_score > 0.15:
            return PPLCategory.LOW_PPL, confidence * 0.6
        else:
            return PPLCategory.ORGANIC, confidence * 0.4
    
    def _combine_classifications(
        self, 
        probability_score: float, 
        ml_category: PPLCategory
    ) -> PPLCategory:
        """기존 분류와 ML 분류 결합"""
        traditional_category = self._determine_category(probability_score)
        
        # 보수적 결합 (높은 정확도 우선)
        categories_ranking = {
            PPLCategory.HIGH_PPL: 4,
            PPLCategory.MEDIUM_PPL: 3,
            PPLCategory.LOW_PPL: 2,
            PPLCategory.ORGANIC: 1
        }
        
        traditional_rank = categories_ranking.get(traditional_category, 1)
        ml_rank = categories_ranking.get(ml_category, 1)
        
        # 더 높은 위험도를 선택 (False Negative 최소화)
        return traditional_category if traditional_rank >= ml_rank else ml_category
    
    def _advanced_determine_category(
        self, 
        probability_score: float, 
        advanced_features: Dict[str, float],
        context_indicators: List[str]
    ) -> PPLCategory:
        """고급 카테고리 결정 (컨텍스트 고려)"""
        
        # 기본 확률 기반 분류
        base_category = self._determine_category(probability_score)
        
        # 컨텍스트 기반 조정
        commercial_boost = advanced_features.get('context_commercial_intent', 0) * 0.3
        brand_boost = advanced_features.get('context_brand_relationship', 0) * 0.2
        disclosure_boost = advanced_features.get('context_disclosure_patterns', 0) * 0.4
        
        adjusted_score = probability_score + commercial_boost + brand_boost + disclosure_boost
        
        # 동적 임계값 적용
        return self._determine_category_with_adaptive_thresholds(adjusted_score)
    
    def _determine_category_with_adaptive_thresholds(self, score: float) -> PPLCategory:
        """적응적 임계값을 사용한 카테고리 결정"""
        thresholds = self.adaptive_thresholds
        
        if score >= thresholds[PPLCategory.HIGH_PPL]:
            return PPLCategory.HIGH_PPL
        elif score >= thresholds[PPLCategory.MEDIUM_PPL]:
            return PPLCategory.MEDIUM_PPL
        elif score >= thresholds[PPLCategory.LOW_PPL]:
            return PPLCategory.LOW_PPL
        else:
            return PPLCategory.ORGANIC
    
    def _advanced_determine_confidence_level(
        self,
        category: PPLCategory,
        analysis_confidence: float,
        component_scores: Dict[str, float],
        advanced_features: Dict[str, float]
    ) -> ConfidenceLevel:
        """고급 신뢰도 레벨 결정"""
        
        # 기본 신뢰도 계산
        base_confidence = self._determine_confidence_level(
            category, analysis_confidence, component_scores
        )
        
        if category == PPLCategory.ORGANIC:
            return ConfidenceLevel.ORGANIC
        
        # 고급 특성 기반 신뢰도 조정
        feature_consistency = self._calculate_feature_consistency(advanced_features)
        context_strength = self._calculate_context_strength(advanced_features)
        
        # 종합 신뢰도
        combined_confidence = (
            analysis_confidence * 0.4 +
            feature_consistency * 0.3 +
            context_strength * 0.3
        )
        
        # 더 엄격한 신뢰도 기준 (정확도 향상)
        if combined_confidence >= 0.9:
            return ConfidenceLevel.HIGH
        elif combined_confidence >= 0.7:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def _calculate_feature_consistency(self, features: Dict[str, float]) -> float:
        """특성 일관성 계산"""
        commercial_features = [
            features.get('context_commercial_intent', 0),
            features.get('context_brand_relationship', 0),
            features.get('linguistic_persuasive_words', 0)
        ]
        
        if not commercial_features:
            return 0.5
        
        mean_val = np.mean(commercial_features)
        std_val = np.std(commercial_features)
        
        # 낮은 분산 = 높은 일관성
        consistency = max(0, 1 - std_val)
        return consistency
    
    def _calculate_context_strength(self, features: Dict[str, float]) -> float:
        """컨텍스트 강도 계산"""
        context_scores = [
            features.get('context_commercial_intent', 0),
            features.get('context_brand_relationship', 0),
            features.get('context_disclosure_patterns', 0)
        ]
        
        return np.mean(context_scores)

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
                "explicit_weight": 0.75,  # 요구사항에 따른 가중치 반영
                "implicit_weight": 0.15,
                "context_weight": 0.10
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