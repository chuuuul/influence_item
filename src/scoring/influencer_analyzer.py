"""
인플루언서 신뢰도 분석 모듈

채널 구독자, 영상 조회수, 신뢰성 지표를 종합하여 
인플루언서 신뢰도를 계산합니다.
0.0-1.0 범위의 점수를 반환합니다.
"""

import logging
import math
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChannelMetrics:
    """채널 지표"""
    subscriber_count: int
    video_view_count: int
    video_count: int
    channel_age_months: int
    engagement_rate: Optional[float] = None
    verified_status: bool = False


@dataclass
class InfluencerCredibility:
    """인플루언서 신뢰도 구성 요소"""
    scale_score: float  # 규모 점수
    engagement_score: float  # 참여도 점수
    consistency_score: float  # 일관성 점수
    authenticity_score: float  # 진정성 점수


class InfluencerAnalyzer:
    """인플루언서 신뢰도 분석기"""
    
    def __init__(self):
        """인플루언서 신뢰도 분석기 초기화"""
        # 신뢰도 계산을 위한 기준값들
        self.subscriber_tiers = {
            1000: 0.1,      # 1K - 입문
            10000: 0.3,     # 10K - 신흥 
            100000: 0.6,    # 100K - 중견
            1000000: 0.85,  # 1M - 대형
            10000000: 1.0   # 10M+ - 메가
        }
        
        self.view_ratio_thresholds = {
            0.01: 0.2,   # 1% 미만 - 낮음
            0.05: 0.5,   # 5% 미만 - 보통
            0.10: 0.8,   # 10% 미만 - 높음
            0.20: 1.0    # 20% 이상 - 매우 높음
        }
        
        logger.info("인플루언서 신뢰도 분석기 초기화 완료")
    
    def calculate_influencer_credibility(
        self, 
        channel_metrics: ChannelMetrics, 
        reputation_score: Optional[float] = None
    ) -> float:
        """
        인플루언서 신뢰도 계산
        
        Args:
            channel_metrics: 채널 지표 정보
            reputation_score: 외부 평판 점수 (선택적)
            
        Returns:
            인플루언서 신뢰도 점수 (0.0-1.0)
        """
        try:
            # 개별 신뢰도 구성 요소 계산
            credibility = self._calculate_credibility_components(channel_metrics)
            
            # 외부 평판 점수가 있는 경우 반영
            if reputation_score is not None:
                reputation_weight = 0.15
                base_weight = 0.85
            else:
                reputation_score = 0.5  # 중립값
                reputation_weight = 0.0
                base_weight = 1.0
            
            # 가중 평균 계산
            final_score = (
                credibility.scale_score * 0.25 * base_weight +
                credibility.engagement_score * 0.35 * base_weight +
                credibility.consistency_score * 0.25 * base_weight +
                credibility.authenticity_score * 0.15 * base_weight +
                reputation_score * reputation_weight
            )
            
            # 0.0-1.0 범위로 정규화
            final_score = max(0.0, min(1.0, final_score))
            
            logger.debug(f"인플루언서 신뢰도 계산 완료 - 점수: {final_score:.3f}")
            return final_score
            
        except Exception as e:
            logger.error(f"인플루언서 신뢰도 계산 실패: {str(e)}")
            return 0.5  # 기본값 반환
    
    def _calculate_credibility_components(self, metrics: ChannelMetrics) -> InfluencerCredibility:
        """신뢰도 구성 요소 계산"""
        # 1. 규모 점수 (구독자 수 기반)
        scale_score = self._calculate_scale_score(metrics.subscriber_count)
        
        # 2. 참여도 점수 (조회수/구독자 비율)
        engagement_score = self._calculate_engagement_score(
            metrics.subscriber_count, 
            metrics.video_view_count,
            metrics.engagement_rate
        )
        
        # 3. 일관성 점수 (영상 개수, 채널 나이)
        consistency_score = self._calculate_consistency_score(
            metrics.video_count,
            metrics.channel_age_months
        )
        
        # 4. 진정성 점수 (인증 상태, 비율 등)
        authenticity_score = self._calculate_authenticity_score(metrics)
        
        return InfluencerCredibility(
            scale_score=scale_score,
            engagement_score=engagement_score,
            consistency_score=consistency_score,
            authenticity_score=authenticity_score
        )
    
    def _calculate_scale_score(self, subscriber_count: int) -> float:
        """규모 점수 계산 (구독자 수 기반)"""
        if subscriber_count <= 0:
            return 0.0
        
        # 로그 스케일로 정규화하여 급격한 차이 완화
        log_subscribers = math.log10(max(1, subscriber_count))
        
        # 구독자 구간별 점수 할당
        for threshold, score in sorted(self.subscriber_tiers.items()):
            if subscriber_count <= threshold:
                return score
        
        # 최고 구간을 넘는 경우
        return 1.0
    
    def _calculate_engagement_score(
        self, 
        subscriber_count: int, 
        video_view_count: int,
        engagement_rate: Optional[float] = None
    ) -> float:
        """참여도 점수 계산"""
        if subscriber_count <= 0:
            return 0.0
        
        # 기본적으로 조회수/구독자 비율 사용
        view_ratio = video_view_count / subscriber_count
        
        # 참여도 비율에 따른 점수 계산
        for threshold, score in sorted(self.view_ratio_thresholds.items()):
            if view_ratio <= threshold:
                return score
        
        # 외부 참여도 점수가 있는 경우 가중 평균
        if engagement_rate is not None:
            ratio_score = min(1.0, view_ratio * 10)  # 10% 기준 정규화
            return (ratio_score * 0.7 + engagement_rate * 0.3)
        
        return min(1.0, view_ratio * 10)
    
    def _calculate_consistency_score(
        self, 
        video_count: int, 
        channel_age_months: int
    ) -> float:
        """일관성 점수 계산"""
        if channel_age_months <= 0:
            return 0.0
        
        # 월평균 영상 업로드 수
        videos_per_month = video_count / channel_age_months
        
        # 적정 업로드 빈도 기준 (월 2-8개가 적정)
        if videos_per_month < 0.5:
            # 너무 적음
            consistency = videos_per_month * 2
        elif videos_per_month <= 8:
            # 적정 범위
            consistency = 0.8 + (videos_per_month / 8) * 0.2
        else:
            # 너무 많음 (품질 저하 우려)
            consistency = max(0.3, 1.0 - (videos_per_month - 8) * 0.05)
        
        # 채널 나이에 따른 신뢰도 보정
        age_factor = min(1.0, channel_age_months / 24)  # 2년 기준
        
        return consistency * (0.7 + 0.3 * age_factor)
    
    def _calculate_authenticity_score(self, metrics: ChannelMetrics) -> float:
        """진정성 점수 계산"""
        authenticity = 0.5  # 기본 점수
        
        # 인증 상태 반영
        if metrics.verified_status:
            authenticity += 0.2
        
        # 구독자 대비 영상 수 비율 (스팸 채널 감지)
        if metrics.subscriber_count > 0:
            video_subscriber_ratio = metrics.video_count / metrics.subscriber_count
            
            # 적정 비율 (1000명당 1-50개 영상이 정상)
            if 0.001 <= video_subscriber_ratio <= 0.05:
                authenticity += 0.2
            elif video_subscriber_ratio > 0.1:
                authenticity -= 0.3  # 스팸 의심
        
        # 채널 나이 대비 성장률 (급성장 의심 감지)
        if metrics.channel_age_months > 0:
            growth_rate = metrics.subscriber_count / metrics.channel_age_months
            
            # 월 평균 구독자 증가가 너무 빠르면 의심
            if growth_rate > 50000:  # 월 5만명 이상 증가
                authenticity -= 0.2
            elif growth_rate > 10000:  # 월 1만명 이상 증가
                authenticity -= 0.1
        
        return max(0.0, min(1.0, authenticity))
    
    def get_credibility_breakdown(
        self, 
        channel_metrics: ChannelMetrics, 
        reputation_score: Optional[float] = None
    ) -> Dict[str, float]:
        """신뢰도 분석 세부 내역 반환"""
        credibility = self._calculate_credibility_components(channel_metrics)
        total_credibility = self.calculate_influencer_credibility(
            channel_metrics, reputation_score
        )
        
        return {
            "scale_score": credibility.scale_score,
            "engagement_score": credibility.engagement_score,
            "consistency_score": credibility.consistency_score,
            "authenticity_score": credibility.authenticity_score,
            "reputation_score": reputation_score or 0.5,
            "total_credibility": total_credibility
        }
    
    def get_tier_classification(self, subscriber_count: int) -> str:
        """구독자 수에 따른 등급 분류"""
        if subscriber_count >= 10000000:
            return "메가 인플루언서"
        elif subscriber_count >= 1000000:
            return "대형 인플루언서"
        elif subscriber_count >= 100000:
            return "중견 인플루언서"
        elif subscriber_count >= 10000:
            return "신흥 인플루언서"
        elif subscriber_count >= 1000:
            return "마이크로 인플루언서"
        else:
            return "나노 인플루언서"
    
    def assess_channel_quality(self, metrics: ChannelMetrics) -> Dict[str, str]:
        """채널 품질 종합 평가"""
        credibility = self._calculate_credibility_components(metrics)
        
        def score_to_grade(score: float) -> str:
            if score >= 0.9:
                return "A+"
            elif score >= 0.8:
                return "A"
            elif score >= 0.7:
                return "B+"
            elif score >= 0.6:
                return "B"
            elif score >= 0.5:
                return "C+"
            elif score >= 0.4:
                return "C"
            else:
                return "D"
        
        return {
            "scale_grade": score_to_grade(credibility.scale_score),
            "engagement_grade": score_to_grade(credibility.engagement_score),
            "consistency_grade": score_to_grade(credibility.consistency_score),
            "authenticity_grade": score_to_grade(credibility.authenticity_score),
            "tier": self.get_tier_classification(metrics.subscriber_count)
        }