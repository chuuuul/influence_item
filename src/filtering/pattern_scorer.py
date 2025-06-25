"""
PPL 패턴 스코어링 모듈

패턴 매칭 결과를 기반으로 PPL 확률 점수를 계산합니다.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import logging

from .ppl_pattern_matcher import PatternMatch


@dataclass
class PPLScore:
    """PPL 스코어링 결과"""
    explicit_score: float  # 명시적 패턴 점수 (0.0-1.0)
    implicit_score: float  # 암시적 패턴 점수 (0.0-1.0)
    combined_score: float  # 종합 점수 (0.0-1.0)
    confidence: float     # 신뢰도 (0.0-1.0)
    evidence_count: int   # 증거 개수
    dominant_category: str  # 주요 카테고리
    reasoning: List[str]   # 판단 근거


class PatternScorer:
    """PPL 패턴 기반 스코어링 엔진"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """설정 파일 로드"""
        default_config_path = "config/ppl_patterns.json"
        try:
            with open(config_path or default_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"설정 파일을 찾을 수 없습니다: {config_path or default_config_path}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """기본 설정 반환"""
        return {
            "scoring_weights": {
                "explicit_patterns": {
                    "direct_disclosure": 0.85,     # 명시적 패턴 가중치 더 강화
                    "hashtag_disclosure": 0.80,    # 해시태그 패턴 강화
                    "description_patterns": 0.75   # 설명 패턴 강화
                },
                "implicit_patterns": {
                    "promotional_language": 0.45,  # 프로모션 언어 강화
                    "commercial_context": 0.50,    # 상업적 컨텍스트 강화
                    "purchase_guidance": 0.60,     # 구매 유도 강화
                    "timing_patterns": 0.65        # 타이밍 압박 강화
                }
            },
            "thresholds": {
                "high_ppl_probability": 0.65,     # 요구사항에 따른 임계값
                "medium_ppl_probability": 0.4,    # 요구사항에 따른 임계값
                "low_ppl_probability": 0.15       # 요구사항에 따른 임계값
            }
        }
    
    def calculate_ppl_score(self, explicit_matches: List[PatternMatch], 
                           implicit_matches: List[PatternMatch]) -> PPLScore:
        """PPL 점수 계산"""
        
        # 명시적 패턴 점수 계산
        explicit_score = self._calculate_explicit_score(explicit_matches)
        
        # 암시적 패턴 점수 계산
        implicit_score = self._calculate_implicit_score(implicit_matches)
        
        # 종합 점수 계산
        combined_score = self._calculate_combined_score(explicit_score, implicit_score)
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(explicit_matches, implicit_matches)
        
        # 증거 개수
        evidence_count = len(explicit_matches) + len(implicit_matches)
        
        # 주요 카테고리 결정
        dominant_category = self._determine_dominant_category(explicit_matches, implicit_matches)
        
        # 판단 근거 생성
        reasoning = self._generate_reasoning(explicit_matches, implicit_matches, 
                                           explicit_score, implicit_score)
        
        return PPLScore(
            explicit_score=explicit_score,
            implicit_score=implicit_score,
            combined_score=combined_score,
            confidence=confidence,
            evidence_count=evidence_count,
            dominant_category=dominant_category,
            reasoning=reasoning
        )
    
    def _calculate_explicit_score(self, matches: List[PatternMatch]) -> float:
        """명시적 패턴 점수 계산"""
        if not matches:
            return 0.0
        
        category_scores = {}
        weights = self.config.get("scoring_weights", {}).get("explicit_patterns", {})
        
        for match in matches:
            category = self._get_category_from_pattern(match.pattern.pattern)
            if category not in category_scores:
                category_scores[category] = []
            
            # 매칭 신뢰도와 패턴 가중치를 곱한 점수
            score = match.confidence * match.pattern.weight
            category_scores[category].append(score)
        
        # 카테고리별 최고 점수 선택 (중복 제거)
        total_score = 0.0
        for category, scores in category_scores.items():
            max_score = max(scores)
            weight = weights.get(category, 0.5)
            total_score += max_score * weight
        
        return min(1.0, total_score)
    
    def _calculate_implicit_score(self, matches: List[PatternMatch]) -> float:
        """암시적 패턴 점수 계산"""
        if not matches:
            return 0.0
        
        category_scores = {}
        weights = self.config.get("scoring_weights", {}).get("implicit_patterns", {})
        
        for match in matches:
            category = self._get_category_from_pattern(match.pattern.pattern)
            if category not in category_scores:
                category_scores[category] = []
            
            score = match.confidence * match.pattern.weight
            category_scores[category].append(score)
        
        # 암시적 패턴은 누적 효과 고려 (여러 증거의 조합) - 강화된 버전
        total_score = 0.0
        total_evidence_count = sum(len(scores) for scores in category_scores.values())
        
        for category, scores in category_scores.items():
            # 카테고리 내 점수들의 가중 평균
            avg_score = sum(scores) / len(scores)
            weight = weights.get(category, 0.3)
            
            # 카테고리별 증거 개수에 따른 보너스 (최대 1.3배)
            category_evidence_bonus = min(1.3, 1.0 + (len(scores) - 1) * 0.15)
            
            # 전체 증거 개수에 따른 추가 보너스 (복합적 증거)
            if total_evidence_count >= 4:  # 4개 이상의 증거
                global_evidence_bonus = 1.2
            elif total_evidence_count >= 3:  # 3개 이상의 증거  
                global_evidence_bonus = 1.1
            else:
                global_evidence_bonus = 1.0
            
            category_score = avg_score * weight * category_evidence_bonus * global_evidence_bonus
            total_score += category_score
        
        return min(1.0, total_score)
    
    def _calculate_combined_score(self, explicit_score: float, implicit_score: float) -> float:
        """종합 점수 계산 - 개선된 버전"""
        # 명시적 패턴이 강하면 높은 가중치
        if explicit_score > 0.6:
            return explicit_score * 0.85 + implicit_score * 0.15
        elif explicit_score > 0.3:
            # 중간 수준 명시적 패턴
            return explicit_score * 0.65 + implicit_score * 0.35
        else:
            # 명시적 패턴이 약하거나 없으면 암시적 패턴 중심
            # 암시적 패턴이 다수 있을 때 더 높은 점수
            if implicit_score > 0.4:
                # 암시적 패턴 강화 보너스
                implicit_bonus = min(1.0, implicit_score * 1.4)
                return explicit_score * 0.2 + implicit_bonus * 0.8
            else:
                return explicit_score * 0.3 + implicit_score * 0.7
    
    def _calculate_confidence(self, explicit_matches: List[PatternMatch], 
                            implicit_matches: List[PatternMatch]) -> float:
        """신뢰도 계산"""
        all_matches = explicit_matches + implicit_matches
        if not all_matches:
            return 0.0
        
        # 평균 매칭 신뢰도
        avg_confidence = sum(match.confidence for match in all_matches) / len(all_matches)
        
        # 증거 다양성 보너스
        categories = set(self._get_category_from_pattern(match.pattern.pattern) 
                        for match in all_matches)
        diversity_bonus = min(1.2, 1.0 + (len(categories) - 1) * 0.05)
        
        # 명시적 패턴 존재 시 신뢰도 증가
        explicit_bonus = 1.1 if explicit_matches else 1.0
        
        final_confidence = avg_confidence * diversity_bonus * explicit_bonus
        return min(1.0, final_confidence)
    
    def _determine_dominant_category(self, explicit_matches: List[PatternMatch], 
                                   implicit_matches: List[PatternMatch]) -> str:
        """주요 카테고리 결정"""
        all_matches = explicit_matches + implicit_matches
        if not all_matches:
            return "none"
        
        category_counts = {}
        for match in all_matches:
            category = self._get_category_from_pattern(match.pattern.pattern)
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return max(category_counts.items(), key=lambda x: x[1])[0]
    
    def _generate_reasoning(self, explicit_matches: List[PatternMatch], 
                          implicit_matches: List[PatternMatch],
                          explicit_score: float, implicit_score: float) -> List[str]:
        """판단 근거 생성"""
        reasoning = []
        
        if explicit_matches:
            reasoning.append(f"명시적 PPL 패턴 {len(explicit_matches)}개 발견 (점수: {explicit_score:.2f})")
            for match in explicit_matches[:3]:  # 상위 3개만 표시
                reasoning.append(f"- '{match.matched_text}' (신뢰도: {match.confidence:.2f})")
        
        if implicit_matches:
            reasoning.append(f"암시적 PPL 패턴 {len(implicit_matches)}개 발견 (점수: {implicit_score:.2f})")
            # 카테고리별 요약
            categories = {}
            for match in implicit_matches:
                category = self._get_category_from_pattern(match.pattern.pattern)
                if category not in categories:
                    categories[category] = []
                categories[category].append(match)
            
            for category, matches in categories.items():
                reasoning.append(f"- {category}: {len(matches)}개 패턴")
        
        if not explicit_matches and not implicit_matches:
            reasoning.append("PPL 관련 패턴이 발견되지 않음")
        
        return reasoning
    
    def _get_category_from_pattern(self, pattern_text: str) -> str:
        """패턴 텍스트에서 카테고리 추정"""
        # 실제로는 패턴 정의에서 가져와야 하지만, 간단한 휴리스틱 사용
        explicit_keywords = ['협찬', '광고', '제공받', 'sponsored', 'AD', '#광고', '#협찬']
        commercial_keywords = ['브랜드', '신제품', '런칭', '캠페인', '콜라보']
        promotional_keywords = ['특가', '할인', '이벤트', '쿠폰']
        guidance_keywords = ['구매', '링크', '설명란', '관심있으신']
        
        pattern_lower = pattern_text.lower()
        
        if any(keyword in pattern_lower for keyword in explicit_keywords):
            return 'explicit'
        elif any(keyword in pattern_lower for keyword in commercial_keywords):
            return 'commercial_context'
        elif any(keyword in pattern_lower for keyword in promotional_keywords):
            return 'promotional_language'
        elif any(keyword in pattern_lower for keyword in guidance_keywords):
            return 'purchase_guidance'
        else:
            return 'other'
    
    def classify_ppl_level(self, score: PPLScore) -> str:
        """PPL 확률 수준 분류"""
        thresholds = self.config.get("thresholds", {})
        
        if score.combined_score >= thresholds.get("high_ppl_probability", 0.8):
            return "high_ppl_likely"
        elif score.combined_score >= thresholds.get("medium_ppl_probability", 0.5):
            return "medium_ppl_possible"
        elif score.combined_score >= thresholds.get("low_ppl_probability", 0.2):
            return "low_ppl_unlikely"
        else:
            return "no_ppl_organic"
    
    def get_score_summary(self, score: PPLScore) -> Dict:
        """점수 요약 정보 반환"""
        return {
            "level": self.classify_ppl_level(score),
            "combined_score": round(score.combined_score, 3),
            "confidence": round(score.confidence, 3),
            "evidence_count": score.evidence_count,
            "dominant_category": score.dominant_category,
            "breakdown": {
                "explicit": round(score.explicit_score, 3),
                "implicit": round(score.implicit_score, 3)
            }
        }