"""
채널 후보 점수화 시스템

후보 채널을 다양한 지표로 평가하고 순위화:
- 매칭 점수 (관련성)
- 품질 점수 (채널 성과)
- 잠재력 점수 (성장성, 수익화 가능성)
- 종합 점수 계산 및 순위화
"""

import logging
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics

from .models import (
    ChannelCandidate, MatchingResult, ChannelMetrics, 
    ScoringWeights, ChannelType, ChannelStatus
)
from ..youtube_api.youtube_client import ChannelInfo


@dataclass
class ChannelScore:
    """채널 종합 점수"""
    channel_id: str
    
    # 개별 점수
    matching_score: float = 0.0      # 매칭 관련성 (0-1)
    quality_score: float = 0.0       # 채널 품질 (0-1)
    potential_score: float = 0.0     # 성장 잠재력 (0-1)
    monetization_score: float = 0.0  # 수익화 가능성 (0-1)
    
    # 종합 점수
    total_score: float = 0.0         # 최종 점수 (0-100)
    grade: str = "F"                 # 등급 (S, A, B, C, D, F)
    
    # 점수 세부사항
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    
    # 메타데이터
    calculated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0


class QualityAnalyzer:
    """채널 품질 분석기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_subscriber_score(self, subscriber_count: int) -> float:
        """구독자 수 기반 점수 (로그 스케일)"""
        if subscriber_count <= 0:
            return 0.0
        
        # 1K~10M 구독자를 0.1~1.0으로 매핑 (로그 스케일)
        log_subs = math.log10(subscriber_count)
        
        # 구간별 점수 매핑
        if log_subs < 3:  # < 1K
            return 0.05
        elif log_subs < 4:  # 1K~10K
            return 0.1 + (log_subs - 3) * 0.2  # 0.1~0.3
        elif log_subs < 5:  # 10K~100K
            return 0.3 + (log_subs - 4) * 0.3  # 0.3~0.6
        elif log_subs < 6:  # 100K~1M
            return 0.6 + (log_subs - 5) * 0.3  # 0.6~0.9
        else:  # > 1M
            return min(0.9 + (log_subs - 6) * 0.1, 1.0)
    
    def calculate_activity_score(self, video_count: int, channel_age_days: int) -> float:
        """활동성 점수 (영상 수 대비 채널 연령)"""
        if video_count <= 0 or channel_age_days <= 0:
            return 0.0
        
        # 월평균 업로드 수 계산
        months_active = max(channel_age_days / 30, 1)
        videos_per_month = video_count / months_active
        
        # 월 2~10개 영상이 최적
        if videos_per_month < 0.5:
            return 0.1  # 너무 적음
        elif videos_per_month < 2:
            return 0.3 + (videos_per_month - 0.5) * 0.4  # 0.3~0.9
        elif videos_per_month <= 10:
            return 0.9  # 최적 범위
        else:
            return max(0.9 - (videos_per_month - 10) * 0.05, 0.3)  # 너무 많음
    
    def calculate_engagement_score(self, channel_info: ChannelInfo) -> float:
        """참여도 점수 추정 (실제 데이터 필요 시 YouTube Analytics API 사용)"""
        # 현재는 기본 지표로 추정
        score = 0.5  # 기본 점수
        
        # 구독자 대비 조회수 비율
        if channel_info.subscriber_count > 0 and channel_info.view_count > 0:
            view_per_subscriber = channel_info.view_count / channel_info.subscriber_count
            
            # 구독자당 평균 조회수가 높을수록 참여도 높음
            if view_per_subscriber > 100:
                score += 0.3
            elif view_per_subscriber > 50:
                score += 0.2
            elif view_per_subscriber > 20:
                score += 0.1
        
        # 채널 인증 여부
        if channel_info.verified:
            score += 0.2
        
        return min(score, 1.0)
    
    def analyze_content_consistency(self, channel_info: ChannelInfo) -> Tuple[float, List[str]]:
        """콘텐츠 일관성 분석"""
        score = 0.5
        insights = []
        
        # 키워드 기반 일관성 분석
        if channel_info.keywords:
            # 키워드가 있으면 콘텐츠 방향성이 있다고 판단
            score += 0.2
            insights.append(f"키워드 설정: {len(channel_info.keywords)}개")
        
        # 설명 길이 기반 전문성 판단
        if channel_info.description:
            desc_length = len(channel_info.description)
            if desc_length > 500:
                score += 0.2
                insights.append("상세한 채널 설명")
            elif desc_length > 100:
                score += 0.1
                insights.append("기본적인 채널 설명")
        
        # 채널명 전문성 분석
        name_lower = channel_info.channel_name.lower()
        professional_keywords = ['official', '공식', 'studio', '스튜디오', 'tv', 'media']
        
        for keyword in professional_keywords:
            if keyword in name_lower:
                score += 0.1
                insights.append(f"전문성 지표: {keyword}")
                break
        
        return min(score, 1.0), insights


class PotentialAnalyzer:
    """성장 잠재력 분석기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_growth_potential(self, channel_info: ChannelInfo) -> Tuple[float, Dict[str, float]]:
        """성장 잠재력 점수 계산"""
        metrics = {}
        
        # 구독자 규모별 성장 잠재력
        sub_count = channel_info.subscriber_count
        if sub_count < 10000:
            growth_stage_score = 0.8  # 초기 단계, 높은 성장 가능성
            metrics['growth_stage'] = growth_stage_score
        elif sub_count < 100000:
            growth_stage_score = 0.9  # 성장 단계, 최고 잠재력
            metrics['growth_stage'] = growth_stage_score
        elif sub_count < 1000000:
            growth_stage_score = 0.6  # 성숙 단계
            metrics['growth_stage'] = growth_stage_score
        else:
            growth_stage_score = 0.3  # 대형 채널, 성장률 둔화
            metrics['growth_stage'] = growth_stage_score
        
        # 채널 연령 대비 성과
        if channel_info.published_at:
            try:
                published_date = datetime.fromisoformat(channel_info.published_at.replace('Z', '+00:00'))
                channel_age_days = (datetime.now().replace(tzinfo=None) - published_date.replace(tzinfo=None)).days
                
                if channel_age_days > 0:
                    # 일당 구독자 증가율
                    daily_growth = sub_count / channel_age_days
                    
                    if daily_growth > 10:
                        age_performance_score = 0.9
                    elif daily_growth > 5:
                        age_performance_score = 0.7
                    elif daily_growth > 1:
                        age_performance_score = 0.5
                    else:
                        age_performance_score = 0.3
                    
                    metrics['age_performance'] = age_performance_score
                else:
                    metrics['age_performance'] = 0.5
            except:
                metrics['age_performance'] = 0.5
        else:
            metrics['age_performance'] = 0.5
        
        # 콘텐츠 생산성
        video_per_month = 0
        if channel_info.published_at and channel_info.video_count > 0:
            try:
                published_date = datetime.fromisoformat(channel_info.published_at.replace('Z', '+00:00'))
                months_active = max((datetime.now().replace(tzinfo=None) - published_date.replace(tzinfo=None)).days / 30, 1)
                video_per_month = channel_info.video_count / months_active
            except:
                pass
        
        if video_per_month > 4:
            productivity_score = 0.9
        elif video_per_month > 2:
            productivity_score = 0.7
        elif video_per_month > 1:
            productivity_score = 0.5
        else:
            productivity_score = 0.3
        
        metrics['productivity'] = productivity_score
        
        # 종합 점수
        total_potential = (
            growth_stage_score * 0.4 +
            metrics['age_performance'] * 0.35 +
            productivity_score * 0.25
        )
        
        return total_potential, metrics
    
    def calculate_trend_alignment(self, channel_info: ChannelInfo, current_trends: List[str] = None) -> float:
        """트렌드 정렬성 분석"""
        if not current_trends:
            current_trends = [
                '뷰티', '패션', '라이프스타일', 'vlog', '먹방',
                '리뷰', '언박싱', 'asmr', '운동', '요리',
                '여행', '게임', '음악', '댄스', '코미디'
            ]
        
        score = 0.0
        
        # 채널명에서 트렌드 키워드 매칭
        name_lower = channel_info.channel_name.lower()
        name_matches = sum(1 for trend in current_trends if trend.lower() in name_lower)
        score += min(name_matches * 0.1, 0.3)
        
        # 설명에서 트렌드 키워드 매칭
        if channel_info.description:
            desc_lower = channel_info.description.lower()
            desc_matches = sum(1 for trend in current_trends if trend.lower() in desc_lower)
            score += min(desc_matches * 0.05, 0.4)
        
        # 키워드에서 트렌드 매칭
        if channel_info.keywords:
            keyword_text = ' '.join(channel_info.keywords).lower()
            keyword_matches = sum(1 for trend in current_trends if trend.lower() in keyword_text)
            score += min(keyword_matches * 0.1, 0.3)
        
        return min(score, 1.0)


class MonetizationAnalyzer:
    """수익화 가능성 분석기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 수익화 친화적 키워드
        self.monetization_keywords = [
            '리뷰', '추천', '사용후기', '픽', '언박싱',
            '쇼핑', '구매', '할인', '세일', '브랜드',
            '제품', '아이템', '필수템', '애정템',
            '뷰티', '화장품', '패션', '옷', '가방',
            '액세서리', '신발', '시계', '향수'
        ]
    
    def calculate_product_affinity(self, channel_info: ChannelInfo) -> Tuple[float, List[str]]:
        """제품 친화성 분석"""
        score = 0.0
        found_keywords = []
        
        text_to_analyze = f"{channel_info.channel_name} {channel_info.description}"
        if channel_info.keywords:
            text_to_analyze += " " + " ".join(channel_info.keywords)
        
        text_lower = text_to_analyze.lower()
        
        for keyword in self.monetization_keywords:
            if keyword in text_lower:
                score += 0.1
                found_keywords.append(keyword)
        
        # 정규화
        score = min(score, 1.0)
        
        return score, found_keywords
    
    def calculate_audience_commercial_value(self, channel_info: ChannelInfo) -> float:
        """오디언스 상업적 가치 분석"""
        score = 0.5  # 기본 점수
        
        # 구독자 규모별 상업적 가치
        sub_count = channel_info.subscriber_count
        if 10000 <= sub_count <= 500000:
            # 중간 규모가 마케팅 효율이 좋음
            score += 0.3
        elif 1000 <= sub_count < 10000:
            score += 0.2
        elif sub_count > 500000:
            score += 0.1
        
        # 국가별 가치 (한국 타겟)
        if channel_info.country == 'KR':
            score += 0.2
        
        return min(score, 1.0)
    
    def analyze_brand_safety(self, channel_info: ChannelInfo) -> Tuple[float, List[str]]:
        """브랜드 안전성 분석"""
        score = 0.8  # 기본 안전 점수
        issues = []
        
        # 위험 키워드 검사
        risk_keywords = [
            '논란', '스캔들', '사건', '문제', '비판',
            '욕설', '선정적', '폭력', '혐오', '차별'
        ]
        
        text_to_check = f"{channel_info.channel_name} {channel_info.description}"
        text_lower = text_to_check.lower()
        
        for risk_keyword in risk_keywords:
            if risk_keyword in text_lower:
                score -= 0.1
                issues.append(f"위험 키워드 발견: {risk_keyword}")
        
        # 인증 채널은 안전성 높음
        if channel_info.verified:
            score += 0.1
        
        return max(score, 0.0), issues


class ChannelScorer:
    """채널 종합 점수 계산기"""
    
    def __init__(self, scoring_weights: Optional[ScoringWeights] = None):
        self.logger = logging.getLogger(__name__)
        self.weights = scoring_weights or ScoringWeights()
        self.weights.normalize()  # 가중치 정규화
        
        self.quality_analyzer = QualityAnalyzer()
        self.potential_analyzer = PotentialAnalyzer()
        self.monetization_analyzer = MonetizationAnalyzer()
    
    def calculate_channel_score(self, channel_candidate: ChannelCandidate, 
                              matching_result: MatchingResult,
                              channel_info: ChannelInfo) -> ChannelScore:
        """채널 종합 점수 계산"""
        
        # 1. 매칭 점수 (매칭 결과에서 가져옴)
        matching_score = matching_result.total_score
        
        # 2. 품질 점수 계산
        quality_breakdown = self._calculate_quality_score(channel_info)
        quality_score = quality_breakdown['total']
        
        # 3. 잠재력 점수 계산
        potential_score, potential_metrics = self.potential_analyzer.calculate_growth_potential(channel_info)
        
        # 4. 수익화 점수 계산
        monetization_breakdown = self._calculate_monetization_score(channel_info)
        monetization_score = monetization_breakdown['total']
        
        # 5. 종합 점수 계산 (0-100 스케일)
        total_score = (
            matching_score * 40 +        # 매칭 관련성 40%
            quality_score * 30 +         # 채널 품질 30%
            potential_score * 20 +       # 성장 잠재력 20%
            monetization_score * 10      # 수익화 가능성 10%
        )
        
        # 6. 등급 계산
        grade = self._calculate_grade(total_score)
        
        # 7. 강점/약점 분석
        strengths, weaknesses = self._analyze_strengths_weaknesses(
            matching_score, quality_score, potential_score, monetization_score,
            quality_breakdown, monetization_breakdown
        )
        
        # 8. 신뢰도 계산
        confidence = self._calculate_confidence(channel_info, matching_result)
        
        return ChannelScore(
            channel_id=channel_candidate.channel_id,
            matching_score=matching_score,
            quality_score=quality_score,
            potential_score=potential_score,
            monetization_score=monetization_score,
            total_score=total_score,
            grade=grade,
            score_breakdown={
                'matching': matching_score,
                'quality': quality_breakdown,
                'potential': potential_metrics,
                'monetization': monetization_breakdown
            },
            strengths=strengths,
            weaknesses=weaknesses,
            confidence=confidence
        )
    
    def _calculate_quality_score(self, channel_info: ChannelInfo) -> Dict[str, float]:
        """품질 점수 세부 계산"""
        
        # 구독자 점수
        subscriber_score = self.quality_analyzer.calculate_subscriber_score(
            channel_info.subscriber_count
        )
        
        # 활동성 점수
        channel_age_days = 365  # 기본값 (실제로는 published_at에서 계산)
        if channel_info.published_at:
            try:
                published_date = datetime.fromisoformat(channel_info.published_at.replace('Z', '+00:00'))
                channel_age_days = (datetime.now().replace(tzinfo=None) - published_date.replace(tzinfo=None)).days
            except:
                pass
        
        activity_score = self.quality_analyzer.calculate_activity_score(
            channel_info.video_count, channel_age_days
        )
        
        # 참여도 점수
        engagement_score = self.quality_analyzer.calculate_engagement_score(channel_info)
        
        # 일관성 점수
        consistency_score, consistency_insights = self.quality_analyzer.analyze_content_consistency(channel_info)
        
        # 종합 품질 점수
        total_quality = (
            subscriber_score * self.weights.subscriber_count_weight +
            activity_score * 0.25 +
            engagement_score * self.weights.engagement_rate_weight +
            consistency_score * self.weights.content_consistency_weight
        )
        
        return {
            'total': total_quality,
            'subscriber_score': subscriber_score,
            'activity_score': activity_score,
            'engagement_score': engagement_score,
            'consistency_score': consistency_score,
            'consistency_insights': consistency_insights
        }
    
    def _calculate_monetization_score(self, channel_info: ChannelInfo) -> Dict[str, float]:
        """수익화 점수 세부 계산"""
        
        # 제품 친화성
        product_affinity, found_keywords = self.monetization_analyzer.calculate_product_affinity(channel_info)
        
        # 오디언스 상업적 가치
        audience_value = self.monetization_analyzer.calculate_audience_commercial_value(channel_info)
        
        # 브랜드 안전성
        brand_safety, safety_issues = self.monetization_analyzer.analyze_brand_safety(channel_info)
        
        # 종합 수익화 점수
        total_monetization = (
            product_affinity * 0.4 +
            audience_value * 0.35 +
            brand_safety * 0.25
        )
        
        return {
            'total': total_monetization,
            'product_affinity': product_affinity,
            'audience_value': audience_value,
            'brand_safety': brand_safety,
            'found_keywords': found_keywords,
            'safety_issues': safety_issues
        }
    
    def _calculate_grade(self, total_score: float) -> str:
        """점수에 따른 등급 계산"""
        if total_score >= 90:
            return "S"
        elif total_score >= 80:
            return "A"
        elif total_score >= 70:
            return "B"
        elif total_score >= 60:
            return "C"
        elif total_score >= 50:
            return "D"
        else:
            return "F"
    
    def _analyze_strengths_weaknesses(self, matching_score: float, quality_score: float,
                                    potential_score: float, monetization_score: float,
                                    quality_breakdown: Dict, monetization_breakdown: Dict) -> Tuple[List[str], List[str]]:
        """강점과 약점 분석"""
        strengths = []
        weaknesses = []
        
        # 개별 점수 기준 분석
        if matching_score > 0.8:
            strengths.append("타겟 키워드와 높은 관련성")
        elif matching_score < 0.4:
            weaknesses.append("타겟과 관련성 부족")
        
        if quality_score > 0.7:
            strengths.append("높은 채널 품질")
        elif quality_score < 0.4:
            weaknesses.append("채널 품질 개선 필요")
        
        if potential_score > 0.7:
            strengths.append("높은 성장 잠재력")
        elif potential_score < 0.4:
            weaknesses.append("성장 잠재력 제한적")
        
        if monetization_score > 0.7:
            strengths.append("수익화 친화적")
        elif monetization_score < 0.4:
            weaknesses.append("수익화 어려움")
        
        # 세부 분석
        if quality_breakdown.get('subscriber_score', 0) > 0.8:
            strengths.append("대규모 구독자 기반")
        
        if quality_breakdown.get('consistency_score', 0) > 0.8:
            strengths.append("일관된 콘텐츠")
        
        if len(monetization_breakdown.get('found_keywords', [])) > 3:
            strengths.append("제품 리뷰 친화적")
        
        if monetization_breakdown.get('brand_safety', 1.0) < 0.6:
            weaknesses.append("브랜드 안전성 우려")
        
        return strengths, weaknesses
    
    def _calculate_confidence(self, channel_info: ChannelInfo, matching_result: MatchingResult) -> float:
        """점수 신뢰도 계산"""
        confidence_factors = []
        
        # 채널 정보 완성도
        if channel_info.description:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.3)
        
        if channel_info.keywords:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.5)
        
        # 구독자 수 (신뢰도 지표)
        if channel_info.subscriber_count > 10000:
            confidence_factors.append(0.9)
        elif channel_info.subscriber_count > 1000:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.4)
        
        # 매칭 결과 신뢰도
        confidence_factors.append(matching_result.confidence)
        
        return statistics.mean(confidence_factors)
    
    def batch_score_channels(self, candidates: List[ChannelCandidate],
                           matching_results: List[MatchingResult],
                           channel_infos: List[ChannelInfo]) -> List[ChannelScore]:
        """여러 채널 배치 점수 계산"""
        
        if not (len(candidates) == len(matching_results) == len(channel_infos)):
            raise ValueError("입력 리스트들의 길이가 일치하지 않습니다")
        
        scores = []
        
        self.logger.info(f"배치 점수 계산 시작: {len(candidates)}개 채널")
        
        for i, (candidate, matching_result, channel_info) in enumerate(zip(candidates, matching_results, channel_infos)):
            try:
                score = self.calculate_channel_score(candidate, matching_result, channel_info)
                scores.append(score)
                
                if (i + 1) % 10 == 0:
                    self.logger.info(f"점수 계산 진행률: {i + 1}/{len(candidates)}")
                    
            except Exception as e:
                self.logger.error(f"점수 계산 실패 {candidate.channel_id}: {str(e)}")
                continue
        
        # 총 점수 순으로 정렬
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        self.logger.info(f"배치 점수 계산 완료: {len(scores)}개 결과")
        return scores
    
    def get_score_distribution(self, scores: List[ChannelScore]) -> Dict[str, any]:
        """점수 분포 통계"""
        if not scores:
            return {}
        
        total_scores = [score.total_score for score in scores]
        
        return {
            'count': len(scores),
            'mean': statistics.mean(total_scores),
            'median': statistics.median(total_scores),
            'std_dev': statistics.stdev(total_scores) if len(total_scores) > 1 else 0,
            'min': min(total_scores),
            'max': max(total_scores),
            'grade_distribution': {
                grade: len([s for s in scores if s.grade == grade])
                for grade in ['S', 'A', 'B', 'C', 'D', 'F']
            },
            'high_potential_count': len([s for s in scores if s.total_score >= 70]),
            'recommended_count': len([s for s in scores if s.total_score >= 60])
        }