"""
PPL 판단 근거 생성기

PPL 분석 결과의 투명성을 위해 상세한 판단 근거와 
설명을 생성하는 모듈입니다.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .ppl_context_analyzer import ContextAnalysisResult
from .ppl_probability_calculator import PPLProbabilityResult
from .ppl_classifier import PPLClassificationResult, PPLCategory

logger = logging.getLogger(__name__)


@dataclass
class PPLReasoningReport:
    """PPL 판단 근거 리포트"""
    analysis_summary: str
    detailed_reasoning: str
    key_evidence: List[str]
    confidence_explanation: str
    decision_factors: Dict[str, Any]
    transparency_data: Dict[str, Any]
    generated_at: datetime


class PPLReasoningGenerator:
    """PPL 분석 결과의 판단 근거 생성기"""
    
    def __init__(self):
        """판단 근거 생성기 초기화"""
        self.logger = logging.getLogger(__name__)
        
        # 증거 유형별 가중치
        self.evidence_weights = {
            'explicit_pattern': 0.6,
            'implicit_pattern': 0.25,
            'context_analysis': 0.15
        }

    def generate_reasoning_report(
        self,
        pattern_analysis_result: Dict[str, Any],
        context_analysis_result: ContextAnalysisResult,
        probability_result: PPLProbabilityResult,
        classification_result: PPLClassificationResult,
        video_metadata: Optional[Dict[str, Any]] = None
    ) -> PPLReasoningReport:
        """
        종합적인 PPL 판단 근거 리포트 생성
        
        Args:
            pattern_analysis_result: 패턴 분석 결과
            context_analysis_result: 컨텍스트 분석 결과  
            probability_result: 확률 계산 결과
            classification_result: 분류 결과
            video_metadata: 영상 메타데이터 (옵션)
            
        Returns:
            PPLReasoningReport: 판단 근거 리포트
        """
        try:
            self.logger.info("PPL 판단 근거 리포트 생성 시작")
            
            # 분석 요약 생성
            analysis_summary = self._generate_analysis_summary(
                probability_result, classification_result
            )
            
            # 상세 판단 근거 생성
            detailed_reasoning = self._generate_detailed_reasoning(
                pattern_analysis_result, context_analysis_result, probability_result
            )
            
            # 핵심 증거 추출
            key_evidence = self._extract_key_evidence(
                pattern_analysis_result, context_analysis_result
            )
            
            # 신뢰도 설명 생성
            confidence_explanation = self._generate_confidence_explanation(
                context_analysis_result, probability_result, classification_result
            )
            
            # 결정 요인 정리
            decision_factors = self._compile_decision_factors(
                pattern_analysis_result, context_analysis_result, probability_result
            )
            
            # 투명성 데이터 생성
            transparency_data = self._generate_transparency_data(
                pattern_analysis_result, context_analysis_result, 
                probability_result, classification_result, video_metadata
            )
            
            report = PPLReasoningReport(
                analysis_summary=analysis_summary,
                detailed_reasoning=detailed_reasoning,
                key_evidence=key_evidence,
                confidence_explanation=confidence_explanation,
                decision_factors=decision_factors,
                transparency_data=transparency_data,
                generated_at=datetime.now()
            )
            
            self.logger.info("PPL 판단 근거 리포트 생성 완료")
            return report
            
        except Exception as e:
            self.logger.error(f"판단 근거 리포트 생성 오류: {str(e)}")
            return self._get_error_report(str(e))

    def _generate_analysis_summary(
        self,
        probability_result: PPLProbabilityResult,
        classification_result: PPLClassificationResult
    ) -> str:
        """
        분석 결과 요약 생성
        
        Args:
            probability_result: 확률 계산 결과
            classification_result: 분류 결과
            
        Returns:
            str: 분석 요약
        """
        category_descriptions = {
            PPLCategory.HIGH_PPL: "높은 확률의 PPL 콘텐츠",
            PPLCategory.MEDIUM_PPL: "중간 정도의 PPL 가능성",
            PPLCategory.LOW_PPL: "낮은 PPL 가능성",
            PPLCategory.ORGANIC: "유기적 콘텐츠",
            PPLCategory.UNKNOWN: "분석 불가"
        }
        
        category_desc = category_descriptions.get(
            classification_result.category, "분류 불명"
        )
        
        return (
            f"분석 결과: {category_desc} "
            f"(확률: {probability_result.final_probability:.1%}, "
            f"신뢰도: {classification_result.confidence_level.value})"
        )

    def _generate_detailed_reasoning(
        self,
        pattern_analysis_result: Dict[str, Any],
        context_analysis_result: ContextAnalysisResult,
        probability_result: PPLProbabilityResult
    ) -> str:
        """
        상세 판단 근거 생성
        
        Args:
            pattern_analysis_result: 패턴 분석 결과
            context_analysis_result: 컨텍스트 분석 결과
            probability_result: 확률 계산 결과
            
        Returns:
            str: 상세 판단 근거
        """
        reasoning_parts = []
        
        # 패턴 분석 근거
        explicit_score = probability_result.component_scores.get('explicit_patterns', 0.0)
        implicit_score = probability_result.component_scores.get('implicit_patterns', 0.0)
        
        if explicit_score > 0.5:
            reasoning_parts.append(
                f"명시적 PPL 패턴이 감지됨 (강도: {explicit_score:.1%}). "
                f"직접적인 상업적 언어나 광고성 표현이 발견됨."
            )
        elif explicit_score > 0.2:
            reasoning_parts.append(
                f"약한 명시적 패턴 감지됨 (강도: {explicit_score:.1%}). "
                f"일부 상업적 표현이 존재하나 강하지 않음."
            )
        else:
            reasoning_parts.append("명시적 PPL 패턴은 감지되지 않음.")
        
        if implicit_score > 0.4:
            reasoning_parts.append(
                f"암시적 상업적 신호 감지됨 (강도: {implicit_score:.1%}). "
                f"간접적인 상업적 의도나 편향이 존재함."
            )
        elif implicit_score > 0.2:
            reasoning_parts.append(
                f"미약한 암시적 신호 감지됨 (강도: {implicit_score:.1%})."
            )
        
        # 컨텍스트 분석 근거
        context_score = context_analysis_result.commercial_likelihood
        if context_score > 0.6:
            reasoning_parts.append(
                f"컨텍스트 분석에서 높은 상업적 가능성 확인됨 "
                f"(점수: {context_score:.1%}). {context_analysis_result.reasoning}"
            )
        elif context_score > 0.3:
            reasoning_parts.append(
                f"컨텍스트에서 중간 수준의 상업적 신호 감지됨 "
                f"(점수: {context_score:.1%})."
            )
        else:
            reasoning_parts.append("컨텍스트에서 유기적 콘텐츠 특성 확인됨.")
        
        # 종합 판단
        final_prob = probability_result.final_probability
        reasoning_parts.append(
            f"가중 평균 계산 결과 최종 PPL 확률 {final_prob:.1%} 도출. "
            f"이는 각 분석 요소의 가중치를 적용한 종합적 판단임."
        )
        
        return " ".join(reasoning_parts)

    def _extract_key_evidence(
        self,
        pattern_analysis_result: Dict[str, Any],
        context_analysis_result: ContextAnalysisResult
    ) -> List[str]:
        """
        핵심 증거 추출
        
        Args:
            pattern_analysis_result: 패턴 분석 결과
            context_analysis_result: 컨텍스트 분석 결과
            
        Returns:
            List[str]: 핵심 증거 목록
        """
        evidence_list = []
        
        # 패턴 분석에서 발견된 증거
        explicit_matches = pattern_analysis_result.get('explicit_matches', [])
        for match in explicit_matches[:3]:  # 상위 3개만
            if match.get('confidence', 0) > 0.5:
                evidence_list.append(
                    f"명시적 패턴: '{match.get('matched_text', '')}' "
                    f"(신뢰도: {match.get('confidence', 0):.1%})"
                )
        
        implicit_matches = pattern_analysis_result.get('implicit_matches', [])
        for match in implicit_matches[:2]:  # 상위 2개만
            if match.get('confidence', 0) > 0.4:
                evidence_list.append(
                    f"암시적 패턴: '{match.get('pattern_type', '')}' 유형 감지"
                )
        
        # 컨텍스트 분석에서 발견된 증거
        for indicator in context_analysis_result.key_indicators[:3]:
            evidence_list.append(f"컨텍스트 지표: {indicator}")
        
        # 증거가 없으면 기본 메시지
        if not evidence_list:
            evidence_list.append("특별한 상업적 증거가 발견되지 않음")
        
        return evidence_list

    def _generate_confidence_explanation(
        self,
        context_analysis_result: ContextAnalysisResult,
        probability_result: PPLProbabilityResult,
        classification_result: PPLClassificationResult
    ) -> str:
        """
        신뢰도 설명 생성
        
        Args:
            context_analysis_result: 컨텍스트 분석 결과
            probability_result: 확률 계산 결과
            classification_result: 분류 결과
            
        Returns:
            str: 신뢰도 설명
        """
        confidence_level = classification_result.confidence_level.value
        context_confidence = context_analysis_result.confidence
        
        explanations = {
            'high': f"높은 신뢰도 (컨텍스트 분석 확신도: {context_confidence:.1%}). "
                   f"여러 분석 요소가 일관된 결과를 보이며, 판단 근거가 명확함.",
            'medium': f"중간 신뢰도 (컨텍스트 분석 확신도: {context_confidence:.1%}). "
                     f"일부 분석 요소에서 불확실성이 존재하나 전반적 경향은 명확함.",
            'low': f"낮은 신뢰도 (컨텍스트 분석 확신도: {context_confidence:.1%}). "
                  f"분석 요소들 간 불일치가 있거나 증거가 불충분함.",
            'organic': "유기적 콘텐츠로 판단되어 신뢰도 평가가 적용되지 않음."
        }
        
        return explanations.get(confidence_level, "신뢰도 평가 불가")

    def _compile_decision_factors(
        self,
        pattern_analysis_result: Dict[str, Any],
        context_analysis_result: ContextAnalysisResult,
        probability_result: PPLProbabilityResult
    ) -> Dict[str, Any]:
        """
        결정 요인 정리
        
        Args:
            pattern_analysis_result: 패턴 분석 결과
            context_analysis_result: 컨텍스트 분석 결과
            probability_result: 확률 계산 결과
            
        Returns:
            Dict[str, Any]: 결정 요인
        """
        return {
            "pattern_analysis": {
                "explicit_matches_count": len(pattern_analysis_result.get('explicit_matches', [])),
                "implicit_matches_count": len(pattern_analysis_result.get('implicit_matches', [])),
                "highest_pattern_confidence": max(
                    [m.get('confidence', 0) for m in pattern_analysis_result.get('explicit_matches', [])],
                    default=0.0
                )
            },
            "context_analysis": {
                "commercial_likelihood": context_analysis_result.commercial_likelihood,
                "key_indicators_count": len(context_analysis_result.key_indicators),
                "analysis_confidence": context_analysis_result.confidence
            },
            "probability_calculation": {
                "component_scores": probability_result.component_scores,
                "final_probability": probability_result.final_probability,
                "classification": probability_result.classification
            },
            "weights_applied": self.evidence_weights
        }

    def _generate_transparency_data(
        self,
        pattern_analysis_result: Dict[str, Any],
        context_analysis_result: ContextAnalysisResult,
        probability_result: PPLProbabilityResult,
        classification_result: PPLClassificationResult,
        video_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        투명성 데이터 생성 (전체 분석 과정 기록)
        
        Args:
            pattern_analysis_result: 패턴 분석 결과
            context_analysis_result: 컨텍스트 분석 결과
            probability_result: 확률 계산 결과
            classification_result: 분류 결과
            video_metadata: 영상 메타데이터
            
        Returns:
            Dict[str, Any]: 투명성 데이터
        """
        return {
            "analysis_version": "T01B_S03_v1.0",
            "analysis_timestamp": datetime.now().isoformat(),
            "input_data": {
                "video_metadata": video_metadata,
                "pattern_analysis_input": pattern_analysis_result,
                "context_analysis_input": {
                    "commercial_likelihood": context_analysis_result.commercial_likelihood,
                    "reasoning": context_analysis_result.reasoning,
                    "key_indicators": context_analysis_result.key_indicators,
                    "confidence": context_analysis_result.confidence
                }
            },
            "processing_steps": {
                "1_pattern_analysis": "T01A_S03 모듈에서 수행",
                "2_context_analysis": "Gemini API를 통한 컨텍스트 분석",
                "3_probability_calculation": "가중 평균 기반 최종 확률 계산",
                "4_classification": "임계값 기반 카테고리 분류",
                "5_reasoning_generation": "투명성을 위한 근거 생성"
            },
            "algorithm_parameters": {
                "weights": probability_result.component_scores,
                "thresholds": classification_result.metadata.get("threshold_used", {}),
                "evidence_weights": self.evidence_weights
            },
            "output_data": {
                "final_probability": probability_result.final_probability,
                "classification": classification_result.category.value,
                "confidence_level": classification_result.confidence_level.value,
                "filtering_decision": classification_result.filtering_decision
            }
        }

    def _get_error_report(self, error_message: str) -> PPLReasoningReport:
        """
        오류 발생 시 기본 리포트 반환
        
        Args:
            error_message: 오류 메시지
            
        Returns:
            PPLReasoningReport: 오류 리포트
        """
        return PPLReasoningReport(
            analysis_summary=f"분석 중 오류 발생: {error_message}",
            detailed_reasoning="시스템 오류로 인해 정상적인 분석이 수행되지 않음.",
            key_evidence=["시스템 오류"],
            confidence_explanation="오류로 인해 신뢰도 평가 불가",
            decision_factors={"error": error_message},
            transparency_data={"error": True, "error_message": error_message},
            generated_at=datetime.now()
        )

    def export_report_as_text(self, report: PPLReasoningReport) -> str:
        """
        리포트를 텍스트 형태로 내보내기
        
        Args:
            report: PPL 판단 근거 리포트
            
        Returns:
            str: 텍스트 형태의 리포트
        """
        text_parts = [
            "=" * 60,
            "PPL 분석 판단 근거 리포트",
            "=" * 60,
            f"생성 시간: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "1. 분석 요약",
            "-" * 30,
            report.analysis_summary,
            "",
            "2. 상세 판단 근거",
            "-" * 30,
            report.detailed_reasoning,
            "",
            "3. 핵심 증거",
            "-" * 30,
            "\n".join(f"- {evidence}" for evidence in report.key_evidence),
            "",
            "4. 신뢰도 설명",
            "-" * 30,
            report.confidence_explanation,
            "",
            "5. 주요 결정 요인",
            "-" * 30,
            f"패턴 분석 매치: 명시적 {report.decision_factors['pattern_analysis']['explicit_matches_count']}개, "
            f"암시적 {report.decision_factors['pattern_analysis']['implicit_matches_count']}개",
            f"컨텍스트 상업성: {report.decision_factors['context_analysis']['commercial_likelihood']:.1%}",
            f"최종 확률: {report.decision_factors['probability_calculation']['final_probability']:.1%}",
            "",
            "=" * 60
        ]
        
        return "\n".join(text_parts)