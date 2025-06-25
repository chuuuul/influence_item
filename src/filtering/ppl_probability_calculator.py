"""
PPL 확률 계산기

패턴 분석과 컨텍스트 분석 결과를 통합하여 
최종 PPL 확률을 계산하는 모듈입니다.
"""

import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass

from .ppl_context_analyzer import ContextAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class PPLProbabilityResult:
    """PPL 확률 계산 결과"""
    final_probability: float
    classification: str
    confidence_level: str
    component_scores: Dict[str, float]
    reasoning_summary: str


class PPLProbabilityCalculator:
    """패턴 분석과 컨텍스트 분석을 통합한 PPL 확률 계산기"""
    
    def __init__(self):
        """PPL 확률 계산기 초기화"""
        self.logger = logging.getLogger(__name__)
        
        # 가중치 설정 (총합 1.0) - 요구사항에 따른 최적화
        self.weights = {
            'explicit_patterns': 0.75,   # 명시적 패턴 가중치 강화 (0.6 -> 0.75)
            'implicit_patterns': 0.15,   # 암시적 패턴 가중치 감소 (0.25 -> 0.15)  
            'context_analysis': 0.10     # 컨텍스트 분석 가중치 감소 (0.15 -> 0.10)
        }
        
        # 확률 임계값 설정 - 정확도 개선을 위한 재조정
        self.thresholds = {
            'high_ppl': 0.65,     # 높은 PPL 가능성 (0.8 -> 0.65)
            'medium_ppl': 0.4,    # 중간 PPL 가능성 (0.5 -> 0.4)
            'low_ppl': 0.15       # 낮은 PPL 가능성 (0.2 -> 0.15)
        }

    def calculate_final_probability(
        self,
        pattern_analysis_result: Dict[str, Any],
        context_analysis_result: ContextAnalysisResult
    ) -> PPLProbabilityResult:
        """
        패턴 분석과 컨텍스트 분석 결과를 통합하여 최종 PPL 확률 계산
        
        Args:
            pattern_analysis_result: 패턴 분석 결과 (T01A에서 생성)
            context_analysis_result: 컨텍스트 분석 결과
            
        Returns:
            PPLProbabilityResult: 최종 PPL 확률 계산 결과
        """
        try:
            self.logger.info("PPL 최종 확률 계산 시작")
            
            # 패턴 분석 결과에서 점수 추출
            explicit_score = self._extract_pattern_score(
                pattern_analysis_result, 'explicit'
            )
            implicit_score = self._extract_pattern_score(
                pattern_analysis_result, 'implicit'
            )
            
            # 컨텍스트 분석 점수
            context_score = context_analysis_result.commercial_likelihood
            
            # 가중 평균으로 최종 확률 계산
            final_probability = (
                self.weights['explicit_patterns'] * explicit_score +
                self.weights['implicit_patterns'] * implicit_score +
                self.weights['context_analysis'] * context_score
            )
            
            # 확률 정규화 (0.0-1.0 범위)
            final_probability = max(0.0, min(1.0, final_probability))
            
            # 분류 및 신뢰도 계산
            classification, confidence_level = self._classify_ppl_result(final_probability)
            
            # 컴포넌트 점수 정리
            component_scores = {
                'explicit_patterns': explicit_score,
                'implicit_patterns': implicit_score,
                'context_analysis': context_score,
                'weighted_final': final_probability
            }
            
            # 판단 근거 요약 생성
            reasoning_summary = self._generate_reasoning_summary(
                component_scores, context_analysis_result, classification
            )
            
            result = PPLProbabilityResult(
                final_probability=final_probability,
                classification=classification,
                confidence_level=confidence_level,
                component_scores=component_scores,
                reasoning_summary=reasoning_summary
            )
            
            self.logger.info(
                f"PPL 확률 계산 완료 - 최종 확률: {final_probability:.3f}, "
                f"분류: {classification}, 신뢰도: {confidence_level}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"PPL 확률 계산 오류: {str(e)}")
            # 오류 시 중립적 결과 반환
            return self._get_neutral_result(str(e))

    def _extract_pattern_score(
        self, 
        pattern_result: Dict[str, Any], 
        pattern_type: str
    ) -> float:
        """
        패턴 분석 결과에서 특정 유형의 점수 추출 - 개선된 버전
        
        Args:
            pattern_result: 패턴 분석 결과
            pattern_type: 'explicit' 또는 'implicit'
            
        Returns:
            float: 추출된 점수 (0.0-1.0)
        """
        try:
            # 먼저 pattern_scores에서 직접 추출 시도 (개선된 방식)
            pattern_scores = pattern_result.get('pattern_scores', {})
            if pattern_scores:
                if pattern_type == 'explicit':
                    score = pattern_scores.get('explicit_score', 0.0)
                    return min(1.0, max(0.0, score))
                elif pattern_type == 'implicit':
                    score = pattern_scores.get('implicit_score', 0.0)
                    return min(1.0, max(0.0, score))
            
            # 기존 방식으로 폴백
            if pattern_type == 'explicit':
                # 명시적 패턴 점수 추출
                explicit_matches = pattern_result.get('explicit_matches', [])
                if explicit_matches:
                    # 가장 높은 confidence를 가진 매치의 점수 사용
                    confidences = []
                    for match in explicit_matches:
                        if isinstance(match, dict):
                            confidences.append(match.get('confidence', 0.0))
                        else:
                            # PPLPatternMatch 객체인 경우
                            confidences.append(getattr(match, 'confidence', 0.0))
                    
                    if confidences:
                        # 명시적 패턴의 경우 최고 신뢰도 사용 (명확한 증거 우선)
                        max_confidence = max(confidences)
                        return min(1.0, max_confidence)
                return 0.0
                
            elif pattern_type == 'implicit':
                # 암시적 패턴 점수 추출
                implicit_matches = pattern_result.get('implicit_matches', [])
                if implicit_matches:
                    confidences = []
                    for match in implicit_matches:
                        if isinstance(match, dict):
                            confidences.append(match.get('confidence', 0.0))
                        else:
                            # PPLPatternMatch 객체인 경우
                            confidences.append(getattr(match, 'confidence', 0.0))
                    
                    if confidences:
                        # 암시적 패턴의 경우 누적 효과 고려 (여러 약한 증거의 조합)
                        avg_confidence = sum(confidences) / len(confidences)
                        # 다중 증거 보너스 (최대 1.3배)
                        evidence_bonus = min(1.3, 1.0 + (len(confidences) - 1) * 0.1)
                        return min(1.0, avg_confidence * evidence_bonus)
                return 0.0
                
        except (KeyError, TypeError, ValueError) as e:
            self.logger.warning(f"패턴 점수 추출 실패 ({pattern_type}): {str(e)}")
            return 0.0

    def _classify_ppl_result(self, probability: float) -> Tuple[str, str]:
        """
        PPL 확률을 기준으로 분류 및 신뢰도 레벨 결정
        
        Args:
            probability: PPL 확률 (0.0-1.0)
            
        Returns:
            Tuple[str, str]: (분류, 신뢰도 레벨)
        """
        if probability >= self.thresholds['high_ppl']:
            return "high_ppl_likely", "high"
        elif probability >= self.thresholds['medium_ppl']:
            return "medium_ppl_possible", "medium"
        elif probability >= self.thresholds['low_ppl']:
            return "low_ppl_unlikely", "low"
        else:
            return "no_ppl_organic", "organic"

    def _generate_reasoning_summary(
        self,
        component_scores: Dict[str, float],
        context_result: ContextAnalysisResult,
        classification: str
    ) -> str:
        """
        분석 결과를 바탕으로 판단 근거 요약 생성
        
        Args:
            component_scores: 컴포넌트별 점수
            context_result: 컨텍스트 분석 결과
            classification: PPL 분류 결과
            
        Returns:
            str: 판단 근거 요약
        """
        try:
            # 주요 지표 확인
            explicit_score = component_scores['explicit_patterns']
            implicit_score = component_scores['implicit_patterns']
            context_score = component_scores['context_analysis']
            
            summary_parts = []
            
            # 명시적 패턴 분석
            if explicit_score > 0.7:
                summary_parts.append(f"명시적 PPL 패턴 강하게 감지됨 (점수: {explicit_score:.2f})")
            elif explicit_score > 0.3:
                summary_parts.append(f"명시적 PPL 패턴 부분적 감지됨 (점수: {explicit_score:.2f})")
            else:
                summary_parts.append("명시적 PPL 패턴 미감지")
            
            # 암시적 패턴 분석
            if implicit_score > 0.5:
                summary_parts.append(f"암시적 상업적 신호 감지됨 (점수: {implicit_score:.2f})")
            elif implicit_score > 0.2:
                summary_parts.append(f"약한 상업적 신호 감지됨 (점수: {implicit_score:.2f})")
            
            # 컨텍스트 분석 결과
            if context_score > 0.6:
                summary_parts.append(f"컨텍스트 상업성 높음 (점수: {context_score:.2f})")
            elif context_score > 0.3:
                summary_parts.append(f"컨텍스트 상업성 보통 (점수: {context_score:.2f})")
            
            # 주요 지표 추가
            if context_result.key_indicators:
                summary_parts.append(f"주요 지표: {', '.join(context_result.key_indicators[:3])}")
            
            # 최종 판단
            classification_text = {
                "high_ppl_likely": "높은 PPL 가능성",
                "medium_ppl_possible": "중간 PPL 가능성", 
                "low_ppl_unlikely": "낮은 PPL 가능성",
                "no_ppl_organic": "유기적 콘텐츠 가능성"
            }.get(classification, "분류 불명")
            
            summary_parts.append(f"최종 판단: {classification_text}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            return f"판단 근거 생성 중 오류: {str(e)}"

    def _get_neutral_result(self, error_message: str) -> PPLProbabilityResult:
        """
        오류 발생 시 중립적 결과 반환
        
        Args:
            error_message: 오류 메시지
            
        Returns:
            PPLProbabilityResult: 중립적 결과
        """
        return PPLProbabilityResult(
            final_probability=0.5,
            classification="unknown_error",
            confidence_level="low",
            component_scores={
                'explicit_patterns': 0.0,
                'implicit_patterns': 0.0,
                'context_analysis': 0.0,
                'weighted_final': 0.5
            },
            reasoning_summary=f"분석 중 오류 발생: {error_message}"
        )

    def update_weights(self, new_weights: Dict[str, float]):
        """
        가중치 업데이트 (향후 성능 개선용)
        
        Args:
            new_weights: 새로운 가중치 딕셔너리
        """
        if abs(sum(new_weights.values()) - 1.0) < 0.01:  # 총합이 1.0에 근사
            self.weights.update(new_weights)
            self.logger.info(f"가중치 업데이트됨: {new_weights}")
        else:
            self.logger.warning("가중치 총합이 1.0이 아님. 업데이트 건너뜀")

    def get_threshold_info(self) -> Dict[str, float]:
        """
        현재 임계값 정보 반환
        
        Returns:
            Dict[str, float]: 임계값 정보
        """
        return self.thresholds.copy()

    def get_weight_info(self) -> Dict[str, float]:
        """
        현재 가중치 정보 반환
        
        Returns:
            Dict[str, float]: 가중치 정보
        """
        return self.weights.copy()