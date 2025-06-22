"""
우선순위 계산기

매력도 점수, PPL 위험도, 수익화 가능성 등을 종합하여
후보의 검토 우선순위를 계산합니다.
"""

from typing import Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """우선순위 레벨"""
    URGENT = "urgent"      # 90-100점: 즉시 검토
    HIGH = "high"          # 70-89점: 높은 우선순위
    MEDIUM = "medium"      # 50-69점: 중간 우선순위  
    LOW = "low"            # 30-49점: 낮은 우선순위
    MINIMAL = "minimal"    # 0-29점: 최소 우선순위


@dataclass
class PriorityScore:
    """우선순위 점수 결과"""
    total_score: float
    level: PriorityLevel
    factors: Dict[str, float]
    reasoning: str
    estimated_review_time: int  # 예상 검토 시간 (분)


class PriorityCalculator:
    """우선순위 계산기"""
    
    def __init__(self):
        # PRD 명세에 따른 매력도 스코어링 공식 (section 7)
        # 총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
        self.attractiveness_weights = {
            "sentiment_score": 0.50,      # 감성 강도 (50%)
            "endorsement_score": 0.35,    # 실사용 인증 강도 (35%)
            "influencer_score": 0.15      # 인플루언서 신뢰도 (15%)
        }
        
        # 우선순위 계산을 위한 보조 가중치
        self.priority_weights = {
            "attractiveness": 0.7,     # 매력도 점수 (70%)
            "ppl_safety": 0.2,         # PPL 안전성 (20%)
            "urgency": 0.1            # 시급성 (10%)
        }
        
        # 연예인 등급별 가중치
        self.celebrity_tiers = {
            "A급": 1.0,     # 대형 연예인
            "B급": 0.8,     # 중견 연예인
            "C급": 0.6,     # 신인/소규모
            "기타": 0.4     # 일반인/기타
        }
        
    def calculate_priority(self, candidate_data: Dict[str, Any]) -> PriorityScore:
        """
        후보 데이터를 기반으로 우선순위를 계산합니다.
        PRD 명세에 따른 매력도 스코어링 공식을 적용합니다.
        
        Args:
            candidate_data: 후보 데이터
            
        Returns:
            PriorityScore 객체
        """
        factors = {}
        reasoning_parts = []
        
        # 1. PRD 매력도 스코어링 공식 적용 (70%)
        attractiveness_score = self._calculate_prd_attractiveness_score(candidate_data)
        factors["attractiveness"] = attractiveness_score
        reasoning_parts.append(f"매력도: {attractiveness_score:.1f}")
        
        # 2. PPL 안전성 (20%)
        ppl_safety_score = self._calculate_ppl_safety_factor(candidate_data)
        factors["ppl_safety"] = ppl_safety_score
        reasoning_parts.append(f"PPL안전성: {ppl_safety_score:.1f}")
        
        # 3. 시급성 (10%)
        urgency_score = self._calculate_urgency_factor(candidate_data)
        factors["urgency"] = urgency_score
        reasoning_parts.append(f"시급성: {urgency_score:.1f}")
        
        # 총점 계산 (우선순위 가중평균)
        total_score = sum(
            factors[factor] * self.priority_weights[factor]
            for factor in factors
        )
        
        # 우선순위 레벨 결정
        priority_level = self._determine_priority_level(total_score)
        
        # 예상 검토 시간 계산
        estimated_time = self._estimate_review_time(priority_level, factors)
        
        reasoning = f"총점 {total_score:.1f} ({', '.join(reasoning_parts)})"
        
        return PriorityScore(
            total_score=total_score,
            level=priority_level,
            factors=factors,
            reasoning=reasoning,
            estimated_review_time=estimated_time
        )
        
    def _calculate_prd_attractiveness_score(self, data: Dict[str, Any]) -> float:
        """
        PRD 명세에 따른 매력도 스코어링 공식 적용
        총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
        """
        score_details = data.get("candidate_info", {}).get("score_details", {})
        
        # PRD 공식의 각 구성 요소 추출
        sentiment_score = score_details.get("sentiment_score", 0.0)      # 감성 강도
        endorsement_score = score_details.get("endorsement_score", 0.0)  # 실사용 인증 강도
        influencer_score = score_details.get("influencer_score", 0.0)    # 인플루언서 신뢰도
        
        # PRD 공식 적용
        prd_score = (
            self.attractiveness_weights["sentiment_score"] * sentiment_score +
            self.attractiveness_weights["endorsement_score"] * endorsement_score +
            self.attractiveness_weights["influencer_score"] * influencer_score
        )
        
        # 0-100 범위로 정규화
        return min(100.0, max(0.0, prd_score * 100))
        
    def _calculate_attractiveness_factor(self, data: Dict[str, Any]) -> float:
        """매력도 점수 팩터 계산"""
        score_details = data.get("candidate_info", {}).get("score_details", {})
        total_score = score_details.get("total", 0)
        
        # 100점 만점을 100점 만점으로 정규화
        return min(total_score, 100.0)
        
    def _calculate_monetization_factor(self, data: Dict[str, Any]) -> float:
        """수익화 가능성 팩터 계산"""
        monetization_info = data.get("monetization_info", {})
        
        if not monetization_info.get("is_coupang_product", False):
            return 0.0  # 수익화 불가능
            
        # 쿠팡 URL 품질 평가
        coupang_url = monetization_info.get("coupang_url_ai", "")
        if coupang_url and "coupang.com" in coupang_url:
            return 100.0  # 완전한 수익화 가능
        else:
            return 50.0   # 부분적 수익화 가능
            
    def _calculate_ppl_safety_factor(self, data: Dict[str, Any]) -> float:
        """PPL 안전성 팩터 계산 (PPL 확률이 낮을수록 높은 점수)"""
        status_info = data.get("status_info", {})
        ppl_confidence = status_info.get("ppl_confidence", 0)
        
        # PPL 확률을 안전성 점수로 변환 (역비례)
        safety_score = (1.0 - ppl_confidence) * 100
        return max(0.0, min(safety_score, 100.0))
        
    def _calculate_celebrity_factor(self, data: Dict[str, Any]) -> float:
        """연예인 등급 팩터 계산"""
        source_info = data.get("source_info", {})
        celebrity_name = source_info.get("celebrity_name", "")
        
        # 간단한 연예인 등급 판정 (실제로는 더 정교한 로직 필요)
        if not celebrity_name:
            return self.celebrity_tiers["기타"] * 100
            
        # 채널 구독자 수 기반 등급 판정 (임시)
        # 실제로는 외부 API나 데이터베이스 조회 필요
        channel_name = source_info.get("channel_name", "")
        
        # 임시 등급 판정 로직
        if any(keyword in celebrity_name for keyword in ["아이유", "태연", "수지"]):
            return self.celebrity_tiers["A급"] * 100
        elif any(keyword in channel_name.lower() for keyword in ["official", "엔터"]):
            return self.celebrity_tiers["B급"] * 100
        else:
            return self.celebrity_tiers["C급"] * 100
            
    def _calculate_urgency_factor(self, data: Dict[str, Any]) -> float:
        """시급성 팩터 계산"""
        from datetime import datetime, timedelta
        
        source_info = data.get("source_info", {})
        upload_date_str = source_info.get("upload_date", "")
        
        try:
            upload_date = datetime.fromisoformat(upload_date_str.replace("Z", "+00:00"))
            days_ago = (datetime.now().astimezone() - upload_date).days
            
            # 최신 영상일수록 높은 시급성
            if days_ago <= 1:
                return 100.0  # 1일 이내
            elif days_ago <= 3:
                return 80.0   # 3일 이내
            elif days_ago <= 7:
                return 60.0   # 1주 이내
            elif days_ago <= 30:
                return 40.0   # 1달 이내
            else:
                return 20.0   # 1달 이상
                
        except (ValueError, TypeError):
            return 50.0  # 기본값
            
    def _determine_priority_level(self, total_score: float) -> PriorityLevel:
        """총점을 기반으로 우선순위 레벨 결정"""
        if total_score >= 90:
            return PriorityLevel.URGENT
        elif total_score >= 70:
            return PriorityLevel.HIGH
        elif total_score >= 50:
            return PriorityLevel.MEDIUM
        elif total_score >= 30:
            return PriorityLevel.LOW
        else:
            return PriorityLevel.MINIMAL
            
    def _estimate_review_time(self, level: PriorityLevel, factors: Dict[str, float]) -> int:
        """우선순위 레벨과 팩터를 기반으로 예상 검토 시간 계산 (분)"""
        base_times = {
            PriorityLevel.URGENT: 5,    # 5분
            PriorityLevel.HIGH: 8,      # 8분
            PriorityLevel.MEDIUM: 12,   # 12분
            PriorityLevel.LOW: 20,      # 20분
            PriorityLevel.MINIMAL: 30   # 30분
        }
        
        base_time = base_times.get(level, 15)
        
        # PPL 위험도가 높으면 검토 시간 증가
        ppl_safety = factors.get("ppl_safety", 100)
        if ppl_safety < 50:  # PPL 위험도 높음
            base_time += 10
            
        # 수익화 불가능하면 검토 시간 증가
        monetization = factors.get("monetization", 100)
        if monetization == 0:
            base_time += 15
            
        return base_time
        
    def sort_candidates_by_priority(
        self, 
        candidates: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], PriorityScore]]:
        """
        후보 목록을 우선순위별로 정렬합니다.
        
        Args:
            candidates: 후보 데이터 목록
            
        Returns:
            (후보, 우선순위점수) 튜플의 정렬된 목록
        """
        candidate_priorities = []
        
        for candidate in candidates:
            priority_score = self.calculate_priority(candidate)
            candidate_priorities.append((candidate, priority_score))
            
        # 우선순위 점수 내림차순 정렬
        candidate_priorities.sort(key=lambda x: x[1].total_score, reverse=True)
        
        return candidate_priorities
        
    def get_priority_statistics(self, priorities: List[PriorityScore]) -> Dict[str, Any]:
        """우선순위 통계 정보 생성"""
        if not priorities:
            return {}
            
        level_counts = {}
        total_estimated_time = 0
        
        for priority in priorities:
            level = priority.level.value
            level_counts[level] = level_counts.get(level, 0) + 1
            total_estimated_time += priority.estimated_review_time
            
        avg_score = sum(p.total_score for p in priorities) / len(priorities)
        
        return {
            "total_candidates": len(priorities),
            "average_score": avg_score,
            "level_distribution": level_counts,
            "total_estimated_review_time_minutes": total_estimated_time,
            "total_estimated_review_time_hours": total_estimated_time / 60
        }