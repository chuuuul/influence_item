"""
통합 PPL 분석기

패턴 분석, 컨텍스트 분석, 확률 계산, 분류 및 판단 근거 생성을 
통합하여 제공하는 메인 PPL 분석 모듈입니다.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# PPL 분석 모듈들
from .ppl_pattern_matcher import PPLPatternMatcher
from .pattern_scorer import PatternScorer
from .ppl_context_analyzer import PPLContextAnalyzer, ContextAnalysisResult
from .ppl_probability_calculator import PPLProbabilityCalculator, PPLProbabilityResult
from .ppl_classifier import PPLClassifier, PPLClassificationResult
from .ppl_reasoning_generator import PPLReasoningGenerator, PPLReasoningReport

# Gemini 분석기 모듈
from ..gemini_analyzer.state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class PPLAnalysisInput:
    """PPL 분석 입력 데이터"""
    video_title: str
    video_description: str
    transcript_excerpt: str
    video_metadata: Optional[Dict[str, Any]] = None


@dataclass
class PPLAnalysisResult:
    """PPL 분석 최종 결과"""
    # 핵심 결과
    is_ppl: bool
    ppl_probability: float
    confidence_level: str
    
    # 상세 분석 결과
    pattern_analysis: Dict[str, Any]
    context_analysis: ContextAnalysisResult
    probability_calculation: PPLProbabilityResult
    classification: PPLClassificationResult
    reasoning_report: PPLReasoningReport
    
    # 메타데이터
    analysis_duration: float
    analysis_timestamp: datetime


class IntegratedPPLAnalyzer:
    """통합 PPL 분석기"""
    
    def __init__(self, state_manager: StateManager):
        """
        통합 PPL 분석기 초기화
        
        Args:
            state_manager: Gemini API 호출을 위한 상태 관리자
        """
        self.state_manager = state_manager
        self.logger = logging.getLogger(__name__)
        
        # 개별 분석 모듈 초기화
        self.pattern_matcher = PPLPatternMatcher()
        self.pattern_scorer = PatternScorer()
        self.context_analyzer = PPLContextAnalyzer(state_manager)
        self.probability_calculator = PPLProbabilityCalculator()
        self.classifier = PPLClassifier()
        self.reasoning_generator = PPLReasoningGenerator()
        
        self.logger.info("통합 PPL 분석기 초기화 완료")

    async def analyze_ppl(
        self,
        analysis_input: PPLAnalysisInput
    ) -> PPLAnalysisResult:
        """
        종합적인 PPL 분석 수행
        
        Args:
            analysis_input: PPL 분석 입력 데이터
            
        Returns:
            PPLAnalysisResult: 종합 PPL 분석 결과
        """
        start_time = datetime.now()
        
        try:
            self.logger.info("PPL 종합 분석 시작")
            
            # 1단계: 패턴 분석 (T01A 모듈)
            pattern_analysis_result = await self._run_pattern_analysis(
                analysis_input.transcript_excerpt
            )
            
            # 2단계: 컨텍스트 분석 (Gemini API)
            context_analysis_result = await self.context_analyzer.analyze_context(
                video_title=analysis_input.video_title,
                video_description=analysis_input.video_description,
                transcript_excerpt=analysis_input.transcript_excerpt,
                pattern_analysis_result=pattern_analysis_result
            )
            
            # 3단계: 확률 계산 (통합)
            probability_result = self.probability_calculator.calculate_final_probability(
                pattern_analysis_result, context_analysis_result
            )
            
            # 4단계: 분류 및 라벨링
            classification_result = self.classifier.classify(
                probability_score=probability_result.final_probability,
                component_scores=probability_result.component_scores,
                context_indicators=context_analysis_result.key_indicators,
                confidence=context_analysis_result.confidence
            )
            
            # 5단계: 판단 근거 생성
            reasoning_report = self.reasoning_generator.generate_reasoning_report(
                pattern_analysis_result=pattern_analysis_result,
                context_analysis_result=context_analysis_result,
                probability_result=probability_result,
                classification_result=classification_result,
                video_metadata=analysis_input.video_metadata
            )
            
            # 최종 결과 생성
            end_time = datetime.now()
            analysis_duration = (end_time - start_time).total_seconds()
            
            final_result = PPLAnalysisResult(
                is_ppl=classification_result.filtering_decision,
                ppl_probability=probability_result.final_probability,
                confidence_level=classification_result.confidence_level.value,
                pattern_analysis=pattern_analysis_result,
                context_analysis=context_analysis_result,
                probability_calculation=probability_result,
                classification=classification_result,
                reasoning_report=reasoning_report,
                analysis_duration=analysis_duration,
                analysis_timestamp=end_time
            )
            
            self.logger.info(
                f"PPL 종합 분석 완료 - 소요시간: {analysis_duration:.2f}초, "
                f"PPL 판정: {final_result.is_ppl}, 확률: {final_result.ppl_probability:.3f}"
            )
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"PPL 종합 분석 오류: {str(e)}")
            return self._get_error_result(str(e), start_time)

    async def _run_pattern_analysis(self, transcript_excerpt: str) -> Dict[str, Any]:
        """
        패턴 분석 실행 (T01A 모듈 통합)
        
        Args:
            transcript_excerpt: 분석할 음성 스크립트 구간
            
        Returns:
            Dict[str, Any]: 패턴 분석 결과
        """
        try:
            # PPL 패턴 매칭 (T01A 실제 인터페이스 사용)
            explicit_matches = self.pattern_matcher.analyze_explicit_patterns(transcript_excerpt)
            implicit_matches = self.pattern_matcher.analyze_implicit_patterns(transcript_excerpt)
            
            # 매치 결과를 임시 객체로 만들어 점수 계산에 전달
            from dataclasses import dataclass
            from typing import List
            
            @dataclass
            class TempMatchResult:
                explicit_matches: List
                implicit_matches: List
                statistics: Dict = None
                
                def __post_init__(self):
                    if self.statistics is None:
                        self.statistics = {
                            "total_explicit": len(self.explicit_matches),
                            "total_implicit": len(self.implicit_matches)
                        }
            
            temp_matches = TempMatchResult(
                explicit_matches=explicit_matches,
                implicit_matches=implicit_matches
            )
            
            # 패턴 점수 계산
            pattern_scores = self.pattern_scorer.calculate_ppl_score(explicit_matches, implicit_matches)
            
            # 결과 통합
            pattern_analysis_result = {
                "explicit_matches": [
                    {
                        "matched_text": match.matched_text,
                        "pattern_name": match.pattern.name if hasattr(match.pattern, 'name') else "unknown",
                        "confidence": match.confidence,
                        "start_pos": match.start_position,
                        "end_pos": match.end_position
                    }
                    for match in explicit_matches
                ],
                "implicit_matches": [
                    {
                        "pattern_type": match.pattern.name if hasattr(match.pattern, 'name') else "unknown",
                        "confidence": match.confidence,
                        "context": match.matched_text[:50] + "..." if len(match.matched_text) > 50 else match.matched_text
                    }
                    for match in implicit_matches
                ],
                "pattern_scores": {
                    "explicit_score": pattern_scores.explicit_score,
                    "implicit_score": pattern_scores.implicit_score,
                    "confidence": pattern_scores.confidence,
                    "total_score": pattern_scores.combined_score
                },
                "statistics": temp_matches.statistics
            }
            
            return pattern_analysis_result
            
        except Exception as e:
            self.logger.error(f"패턴 분석 오류: {str(e)}")
            return {
                "explicit_matches": [],
                "implicit_matches": [],
                "pattern_scores": {
                    "explicit_score": 0.0,
                    "implicit_score": 0.0,
                    "confidence": 0.0,
                    "total_score": 0.0
                },
                "statistics": {},
                "error": str(e)
            }

    def _get_error_result(
        self, 
        error_message: str, 
        start_time: datetime
    ) -> PPLAnalysisResult:
        """
        오류 발생 시 기본 결과 반환
        
        Args:
            error_message: 오류 메시지
            start_time: 분석 시작 시간
            
        Returns:
            PPLAnalysisResult: 오류 시 기본 결과
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 기본 오류 결과 생성
        error_context = ContextAnalysisResult(
            commercial_likelihood=0.5,
            reasoning=f"분석 오류: {error_message}",
            key_indicators=[],
            confidence=0.0,
            raw_response={}
        )
        
        error_probability = PPLProbabilityResult(
            final_probability=0.5,
            classification="unknown_error",
            confidence_level="low",
            component_scores={"error": True},
            reasoning_summary=f"오류로 인한 기본값: {error_message}"
        )
        
        error_classification = PPLClassificationResult(
            category=self.classifier.PPLCategory.UNKNOWN,
            confidence_level=self.classifier.ConfidenceLevel.LOW,
            probability_score=0.5,
            risk_level="UNKNOWN",
            recommended_action="MANUAL_REVIEW",
            filtering_decision=False,
            labels=["ERROR", "MANUAL_REVIEW_REQUIRED"],
            metadata={"error": error_message}
        )
        
        error_reasoning = self.reasoning_generator._get_error_report(error_message)
        
        return PPLAnalysisResult(
            is_ppl=False,
            ppl_probability=0.5,
            confidence_level="low",
            pattern_analysis={"error": error_message},
            context_analysis=error_context,
            probability_calculation=error_probability,
            classification=error_classification,
            reasoning_report=error_reasoning,
            analysis_duration=duration,
            analysis_timestamp=end_time
        )

    def get_analysis_summary(self, result: PPLAnalysisResult) -> str:
        """
        분석 결과 요약 문자열 생성
        
        Args:
            result: PPL 분석 결과
            
        Returns:
            str: 분석 결과 요약
        """
        return (
            f"PPL 분석 결과: {'PPL 감지' if result.is_ppl else 'PPL 미감지'} | "
            f"확률: {result.ppl_probability:.1%} | "
            f"신뢰도: {result.confidence_level} | "
            f"분석시간: {result.analysis_duration:.2f}초"
        )

    async def batch_analyze(
        self, 
        analysis_inputs: List[PPLAnalysisInput],
        max_concurrent: int = 3
    ) -> List[PPLAnalysisResult]:
        """
        배치 PPL 분석 수행
        
        Args:
            analysis_inputs: PPL 분석 입력 데이터 리스트
            max_concurrent: 최대 동시 실행 수
            
        Returns:
            List[PPLAnalysisResult]: PPL 분석 결과 리스트
        """
        self.logger.info(f"배치 PPL 분석 시작 - {len(analysis_inputs)}개 항목")
        
        # 세마포어를 사용한 동시 실행 제어
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(input_data):
            async with semaphore:
                return await self.analyze_ppl(input_data)
        
        # 모든 분석 작업을 동시에 실행
        tasks = [analyze_with_semaphore(input_data) for input_data in analysis_inputs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"배치 분석 중 오류 (항목 {i}): {str(result)}")
                error_result = self._get_error_result(
                    str(result), datetime.now()
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        self.logger.info(f"배치 PPL 분석 완료 - {len(processed_results)}개 결과")
        return processed_results

    def get_batch_statistics(self, results: List[PPLAnalysisResult]) -> Dict[str, Any]:
        """
        배치 분석 결과 통계 생성
        
        Args:
            results: PPL 분석 결과 리스트
            
        Returns:
            Dict[str, Any]: 배치 분석 통계
        """
        if not results:
            return {"total": 0}
        
        total_count = len(results)
        ppl_detected = sum(1 for r in results if r.is_ppl)
        avg_probability = sum(r.ppl_probability for r in results) / total_count
        avg_duration = sum(r.analysis_duration for r in results) / total_count
        
        confidence_distribution = {}
        for result in results:
            conf_level = result.confidence_level
            confidence_distribution[conf_level] = confidence_distribution.get(conf_level, 0) + 1
        
        return {
            "total_analyzed": total_count,
            "ppl_detected": ppl_detected,
            "ppl_rate": ppl_detected / total_count,
            "average_probability": avg_probability,
            "average_duration": avg_duration,
            "confidence_distribution": confidence_distribution,
            "successful_analyses": sum(1 for r in results if not hasattr(r.pattern_analysis, 'error'))
        }

    def export_results_summary(
        self, 
        results: List[PPLAnalysisResult],
        include_detailed: bool = False
    ) -> str:
        """
        분석 결과 요약을 텍스트로 내보내기
        
        Args:
            results: PPL 분석 결과 리스트
            include_detailed: 상세 정보 포함 여부
            
        Returns:
            str: 텍스트 형태의 결과 요약
        """
        if not results:
            return "분석 결과가 없습니다."
        
        stats = self.get_batch_statistics(results)
        
        summary_parts = [
            "=" * 60,
            "PPL 분석 결과 요약",
            "=" * 60,
            f"총 분석 항목: {stats['total_analyzed']}개",
            f"PPL 감지: {stats['ppl_detected']}개 ({stats['ppl_rate']:.1%})",
            f"평균 확률: {stats['average_probability']:.1%}",
            f"평균 분석 시간: {stats['average_duration']:.2f}초",
            "",
            "신뢰도 분포:",
        ]
        
        for conf_level, count in stats['confidence_distribution'].items():
            summary_parts.append(f"  - {conf_level}: {count}개")
        
        if include_detailed:
            summary_parts.extend([
                "",
                "상세 분석 결과:",
                "-" * 40
            ])
            
            for i, result in enumerate(results, 1):
                summary_parts.append(f"{i}. {self.get_analysis_summary(result)}")
        
        summary_parts.append("=" * 60)
        
        return "\n".join(summary_parts)