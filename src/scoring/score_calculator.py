"""
매력도 점수 계산기

감성 강도, 실사용 인증 강도, 인플루언서 신뢰도를 종합하여
PRD 명세에 따른 최종 매력도 점수를 계산합니다.

공식: 총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from ..gemini_analyzer.models import ScoreDetails
from .sentiment_analyzer import SentimentAnalyzer
from .endorsement_analyzer import EndorsementAnalyzer
from .influencer_analyzer import InfluencerAnalyzer, ChannelMetrics

logger = logging.getLogger(__name__)


@dataclass
class ScoringComponents:
    """스코어링 구성 요소"""
    sentiment_score: float
    endorsement_score: float
    influencer_score: float
    total_score: int


@dataclass
class ScoringInput:
    """스코어링 입력 데이터"""
    transcript_text: str
    usage_patterns: list
    demonstration_level: int
    channel_metrics: ChannelMetrics
    tone_indicators: Optional[Dict] = None
    reputation_score: Optional[float] = None


class ScoreCalculator:
    """매력도 점수 계산기"""
    
    # PRD 명세 가중치
    SENTIMENT_WEIGHT = 0.50
    ENDORSEMENT_WEIGHT = 0.35
    INFLUENCER_WEIGHT = 0.15
    
    def __init__(self):
        """점수 계산기 초기화"""
        self.sentiment_analyzer = SentimentAnalyzer()
        self.endorsement_analyzer = EndorsementAnalyzer()
        self.influencer_analyzer = InfluencerAnalyzer()
        logger.info("매력도 점수 계산기 초기화 완료")
    
    def calculate_attractiveness_score(self, scoring_input: ScoringInput) -> ScoreDetails:
        """
        매력도 점수 계산
        
        Args:
            scoring_input: 스코어링 입력 데이터
            
        Returns:
            ScoreDetails 객체 (total, sentiment_score, endorsement_score, influencer_score)
        """
        try:
            # 1. 감성 강도 분석 (0.0-1.0)
            sentiment_score = self.sentiment_analyzer.analyze_sentiment_intensity(
                scoring_input.transcript_text,
                scoring_input.tone_indicators
            )
            
            # 2. 실사용 인증 강도 분석 (0.0-1.0)
            endorsement_score = self.endorsement_analyzer.analyze_usage_authenticity(
                scoring_input.usage_patterns,
                scoring_input.demonstration_level
            )
            
            # 3. 인플루언서 신뢰도 분석 (0.0-1.0)
            influencer_score = self.influencer_analyzer.calculate_influencer_credibility(
                scoring_input.channel_metrics,
                scoring_input.reputation_score
            )
            
            # 4. 가중 평균 계산 및 0-100점 변환
            total_score = self._calculate_weighted_score(
                sentiment_score, endorsement_score, influencer_score
            )
            
            score_details = ScoreDetails(
                total=total_score,
                sentiment_score=sentiment_score,
                endorsement_score=endorsement_score,
                influencer_score=influencer_score
            )
            
            logger.info(f"매력도 점수 계산 완료 - 총점: {total_score}")
            return score_details
            
        except Exception as e:
            logger.error(f"매력도 점수 계산 실패: {str(e)}")
            # 오류 시 기본값 반환
            return ScoreDetails(
                total=50,
                sentiment_score=0.5,
                endorsement_score=0.5,
                influencer_score=0.5
            )
    
    def _calculate_weighted_score(
        self, 
        sentiment_score: float, 
        endorsement_score: float, 
        influencer_score: float
    ) -> int:
        """
        PRD 명세에 따른 가중 평균 계산
        
        Args:
            sentiment_score: 감성 강도 점수 (0.0-1.0)
            endorsement_score: 실사용 인증 강도 점수 (0.0-1.0)
            influencer_score: 인플루언서 신뢰도 점수 (0.0-1.0)
            
        Returns:
            총점 (0-100)
        """
        # PRD 명세 공식 적용
        weighted_sum = (
            self.SENTIMENT_WEIGHT * sentiment_score +
            self.ENDORSEMENT_WEIGHT * endorsement_score +
            self.INFLUENCER_WEIGHT * influencer_score
        )
        
        # 0-100점 범위로 변환
        total_score = int(round(weighted_sum * 100))
        
        # 범위 제한
        return max(0, min(100, total_score))
    
    def get_score_breakdown(self, scoring_input: ScoringInput) -> Dict[str, any]:
        """점수 계산 세부 내역 반환"""
        try:
            # 각 구성 요소별 상세 분석
            sentiment_breakdown = self.sentiment_analyzer.get_sentiment_breakdown(
                scoring_input.transcript_text
            )
            
            endorsement_breakdown = self.endorsement_analyzer.get_endorsement_breakdown(
                scoring_input.usage_patterns,
                scoring_input.demonstration_level
            )
            
            influencer_breakdown = self.influencer_analyzer.get_credibility_breakdown(
                scoring_input.channel_metrics,
                scoring_input.reputation_score
            )
            
            # 최종 점수 계산
            score_details = self.calculate_attractiveness_score(scoring_input)
            
            return {
                "final_score": {
                    "total": score_details.total,
                    "sentiment_score": score_details.sentiment_score,
                    "endorsement_score": score_details.endorsement_score,
                    "influencer_score": score_details.influencer_score,
                    "weights": {
                        "sentiment_weight": self.SENTIMENT_WEIGHT,
                        "endorsement_weight": self.ENDORSEMENT_WEIGHT,
                        "influencer_weight": self.INFLUENCER_WEIGHT
                    }
                },
                "sentiment_analysis": sentiment_breakdown,
                "endorsement_analysis": endorsement_breakdown,
                "influencer_analysis": influencer_breakdown
            }
            
        except Exception as e:
            logger.error(f"점수 세부 내역 생성 실패: {str(e)}")
            return {"error": f"분석 실패: {str(e)}"}
    
    def calculate_score_confidence(self, scoring_input: ScoringInput) -> float:
        """점수 신뢰도 계산"""
        try:
            confidence_factors = []
            
            # 1. 텍스트 길이 기반 신뢰도
            text_length = len(scoring_input.transcript_text.split())
            if text_length >= 50:
                confidence_factors.append(1.0)
            elif text_length >= 20:
                confidence_factors.append(0.8)
            elif text_length >= 10:
                confidence_factors.append(0.6)
            else:
                confidence_factors.append(0.3)
            
            # 2. 채널 지표 완성도
            channel_completeness = self._assess_channel_data_completeness(
                scoring_input.channel_metrics
            )
            confidence_factors.append(channel_completeness)
            
            # 3. 사용 패턴 데이터 품질
            usage_quality = min(1.0, len(scoring_input.usage_patterns) / 5)
            confidence_factors.append(usage_quality)
            
            # 4. 시연 레벨 신뢰도
            demo_confidence = scoring_input.demonstration_level / 3.0
            confidence_factors.append(demo_confidence)
            
            # 평균 신뢰도 계산
            confidence = sum(confidence_factors) / len(confidence_factors)
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.error(f"점수 신뢰도 계산 실패: {str(e)}")
            return 0.5
    
    def _assess_channel_data_completeness(self, channel_metrics: ChannelMetrics) -> float:
        """채널 데이터 완성도 평가"""
        completeness_score = 0.0
        total_fields = 6
        
        # 필수 필드들 확인
        if channel_metrics.subscriber_count > 0:
            completeness_score += 1
        if channel_metrics.video_view_count > 0:
            completeness_score += 1
        if channel_metrics.video_count > 0:
            completeness_score += 1
        if channel_metrics.channel_age_months > 0:
            completeness_score += 1
        if channel_metrics.engagement_rate is not None:
            completeness_score += 1
        if channel_metrics.verified_status is not None:
            completeness_score += 1
        
        return completeness_score / total_fields
    
    def get_score_interpretation(self, total_score: int) -> Dict[str, str]:
        """점수 해석 및 분류"""
        if total_score >= 90:
            grade = "S"
            interpretation = "극도로 매력적인 콘텐츠"
            action = "즉시 제작 권장"
        elif total_score >= 80:
            grade = "A"
            interpretation = "매우 매력적인 콘텐츠"
            action = "우선 제작 대상"
        elif total_score >= 70:
            grade = "B"
            interpretation = "매력적인 콘텐츠"
            action = "제작 권장"
        elif total_score >= 60:
            grade = "C"
            interpretation = "보통 수준의 콘텐츠"
            action = "검토 후 제작"
        elif total_score >= 50:
            grade = "D"
            interpretation = "낮은 매력도 콘텐츠"
            action = "제작 보류"
        else:
            grade = "F"
            interpretation = "매력도 부족 콘텐츠"
            action = "제작 비권장"
        
        return {
            "grade": grade,
            "interpretation": interpretation,
            "recommended_action": action
        }
    
    def classify_by_thresholds(self, total_score: int) -> Dict[str, str]:
        """
        임계값 기반 자동 분류
        
        Args:
            total_score: 총점 (0-100)
            
        Returns:
            분류 결과 (우선순위, 상태, 액션)
        """
        # 임계값 기준
        HIGH_THRESHOLD = 80      # 높은 매력도
        MEDIUM_THRESHOLD = 60    # 중간 매력도
        LOW_THRESHOLD = 40       # 낮은 매력도
        
        if total_score >= HIGH_THRESHOLD:
            return {
                "priority": "high",
                "status": "approved",
                "action": "immediate_production",
                "category": "premium_content",
                "confidence": "high"
            }
        elif total_score >= MEDIUM_THRESHOLD:
            return {
                "priority": "medium",
                "status": "needs_review",
                "action": "review_for_production",
                "category": "quality_content",
                "confidence": "medium"
            }
        elif total_score >= LOW_THRESHOLD:
            return {
                "priority": "low",
                "status": "conditional",
                "action": "consider_with_conditions",
                "category": "acceptable_content",
                "confidence": "low"
            }
        else:
            return {
                "priority": "reject",
                "status": "rejected",
                "action": "do_not_produce",
                "category": "poor_content",
                "confidence": "high"
            }
    
    def get_production_recommendation(self, score_details: ScoreDetails) -> Dict[str, any]:
        """제작 권장사항 생성"""
        classification = self.classify_by_thresholds(score_details.total)
        
        # 구성 요소별 강점/약점 분석
        strengths = []
        weaknesses = []
        
        if score_details.sentiment_score >= 0.7:
            strengths.append("강한 감성적 호응")
        elif score_details.sentiment_score <= 0.3:
            weaknesses.append("감성적 어필 부족")
        
        if score_details.endorsement_score >= 0.7:
            strengths.append("확실한 실사용 인증")
        elif score_details.endorsement_score <= 0.3:
            weaknesses.append("사용 경험 부족")
        
        if score_details.influencer_score >= 0.7:
            strengths.append("높은 인플루언서 신뢰도")
        elif score_details.influencer_score <= 0.3:
            weaknesses.append("낮은 채널 신뢰도")
        
        # 개선 제안사항
        improvement_suggestions = []
        if score_details.sentiment_score < 0.5:
            improvement_suggestions.append("더 감정적이고 열정적인 표현 필요")
        if score_details.endorsement_score < 0.5:
            improvement_suggestions.append("구체적인 사용법이나 효과 설명 추가")
        if score_details.influencer_score < 0.5:
            improvement_suggestions.append("채널 신뢰도 개선 또는 보완 검증 필요")
        
        return {
            "classification": classification,
            "score_breakdown": {
                "total": score_details.total,
                "sentiment": score_details.sentiment_score,
                "endorsement": score_details.endorsement_score,
                "influencer": score_details.influencer_score
            },
            "analysis": {
                "strengths": strengths,
                "weaknesses": weaknesses,
                "improvement_suggestions": improvement_suggestions
            },
            "recommendation": self._generate_detailed_recommendation(
                score_details, classification
            )
        }
    
    def _generate_detailed_recommendation(
        self, 
        score_details: ScoreDetails, 
        classification: Dict[str, str]
    ) -> str:
        """상세 권장사항 텍스트 생성"""
        score = score_details.total
        priority = classification["priority"]
        
        if priority == "high":
            return (
                f"매력도 점수 {score}점으로 매우 우수한 콘텐츠입니다. "
                f"즉시 제작을 권장하며, 높은 참여도와 수익성을 기대할 수 있습니다."
            )
        elif priority == "medium":
            return (
                f"매력도 점수 {score}점으로 양질의 콘텐츠입니다. "
                f"제작 전 세부 검토를 통해 완성도를 높이면 좋은 성과를 기대할 수 있습니다."
            )
        elif priority == "low":
            return (
                f"매력도 점수 {score}점으로 조건부 제작을 고려해볼 수 있습니다. "
                f"다른 요소들(트렌드, 시기 등)을 종합적으로 검토 후 결정하세요."
            )
        else:
            return (
                f"매력도 점수 {score}점으로 현재 상태로는 제작을 권장하지 않습니다. "
                f"더 매력적인 콘텐츠를 찾거나 기존 콘텐츠를 개선해보세요."
            )
    
    def batch_calculate_scores(self, scoring_inputs: list) -> list:
        """배치 점수 계산"""
        results = []
        
        for i, scoring_input in enumerate(scoring_inputs):
            try:
                score_details = self.calculate_attractiveness_score(scoring_input)
                classification = self.classify_by_thresholds(score_details.total)
                
                results.append({
                    "index": i,
                    "score_details": score_details,
                    "classification": classification,
                    "success": True
                })
                
            except Exception as e:
                logger.error(f"배치 계산 중 오류 발생 (인덱스 {i}): {str(e)}")
                results.append({
                    "index": i,
                    "error": str(e),
                    "success": False
                })
        
        return results