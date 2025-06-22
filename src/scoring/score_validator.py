"""
스코어 검증 및 보정 시스템

계산된 매력도 점수의 타당성을 검증하고 필요시 보정하는 모듈입니다.
이상치 탐지, 일관성 검증, 신뢰도 평가 등을 수행합니다.
"""

import logging
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..gemini_analyzer.models import ScoreDetails

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    confidence: float
    issues: List[str]
    recommendations: List[str]
    adjusted_score: Optional[ScoreDetails] = None


@dataclass
class ScoreStatistics:
    """점수 통계"""
    mean: float
    median: float
    std_dev: float
    min_score: float
    max_score: float
    outlier_threshold: float


class ScoreValidator:
    """스코어 검증 및 보정기"""
    
    def __init__(self):
        """스코어 검증기 초기화"""
        # 검증을 위한 기준값들
        self.score_history: List[int] = []
        self.component_history: Dict[str, List[float]] = {
            'sentiment': [],
            'endorsement': [],
            'influencer': []
        }
        
        # 이상치 탐지 임계값
        self.outlier_z_threshold = 2.5
        self.min_history_size = 10
        
        logger.info("스코어 검증 및 보정기 초기화 완료")
    
    def validate_score(
        self, 
        score_details: ScoreDetails,
        input_context: Optional[Dict] = None
    ) -> ValidationResult:
        """
        점수 검증 수행
        
        Args:
            score_details: 검증할 점수 정보
            input_context: 입력 컨텍스트 (텍스트 길이, 채널 정보 등)
            
        Returns:
            ValidationResult 검증 결과
        """
        try:
            issues = []
            recommendations = []
            confidence = 1.0
            
            # 1. 기본 범위 검증
            range_issues = self._validate_score_ranges(score_details)
            issues.extend(range_issues)
            
            # 2. 구성 요소 간 일관성 검증
            consistency_issues = self._validate_component_consistency(score_details)
            issues.extend(consistency_issues)
            
            # 3. 수학적 정확성 검증
            math_issues = self._validate_mathematical_accuracy(score_details)
            issues.extend(math_issues)
            
            # 4. 컨텍스트 기반 검증
            if input_context:
                context_issues = self._validate_with_context(score_details, input_context)
                issues.extend(context_issues)
            
            # 5. 이력 기반 이상치 탐지
            if len(self.score_history) >= self.min_history_size:
                outlier_issues = self._detect_outliers(score_details)
                issues.extend(outlier_issues)
            
            # 6. 신뢰도 계산
            confidence = self._calculate_validation_confidence(score_details, issues)
            
            # 7. 권장 사항 생성
            recommendations = self._generate_recommendations(score_details, issues)
            
            # 8. 필요시 점수 보정
            adjusted_score = self._adjust_score_if_needed(score_details, issues)
            
            is_valid = len([issue for issue in issues if 'critical' in issue.lower()]) == 0
            
            # 이력에 추가
            self._update_history(score_details)
            
            logger.debug(f"점수 검증 완료 - 유효성: {is_valid}, 신뢰도: {confidence:.3f}")
            
            return ValidationResult(
                is_valid=is_valid,
                confidence=confidence,
                issues=issues,
                recommendations=recommendations,
                adjusted_score=adjusted_score
            )
            
        except Exception as e:
            logger.error(f"점수 검증 실패: {str(e)}")
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                issues=[f"검증 프로세스 오류: {str(e)}"],
                recommendations=["점수를 재계산하세요."]
            )
    
    def _validate_score_ranges(self, score_details: ScoreDetails) -> List[str]:
        """점수 범위 검증"""
        issues = []
        
        # 총점 범위 검증 (0-100)
        if not (0 <= score_details.total <= 100):
            issues.append(f"CRITICAL: 총점 {score_details.total}이 범위(0-100)를 벗어남")
        
        # 구성 요소 범위 검증 (0.0-1.0)
        components = {
            'sentiment_score': score_details.sentiment_score,
            'endorsement_score': score_details.endorsement_score,
            'influencer_score': score_details.influencer_score
        }
        
        for component_name, value in components.items():
            if not (0.0 <= value <= 1.0):
                issues.append(f"CRITICAL: {component_name} {value}가 범위(0.0-1.0)를 벗어남")
        
        return issues
    
    def _validate_component_consistency(self, score_details: ScoreDetails) -> List[str]:
        """구성 요소 간 일관성 검증"""
        issues = []
        
        # 극단적 조합 검증
        components = [
            score_details.sentiment_score,
            score_details.endorsement_score,
            score_details.influencer_score
        ]
        
        # 모든 구성 요소가 매우 높은데 총점이 낮은 경우
        if all(c >= 0.8 for c in components) and score_details.total < 75:
            issues.append("WARNING: 구성 요소는 높지만 총점이 상대적으로 낮음")
        
        # 모든 구성 요소가 매우 낮은데 총점이 높은 경우
        if all(c <= 0.3 for c in components) and score_details.total > 40:
            issues.append("WARNING: 구성 요소는 낮지만 총점이 상대적으로 높음")
        
        # 구성 요소 간 극단적 차이
        component_range = max(components) - min(components)
        if component_range > 0.7:
            issues.append("INFO: 구성 요소 간 큰 차이 발견 (정상 범위일 수 있음)")
        
        return issues
    
    def _validate_mathematical_accuracy(self, score_details: ScoreDetails) -> List[str]:
        """수학적 정확성 검증"""
        issues = []
        
        # PRD 공식에 따른 계산 검증
        expected_total = int(round(
            (0.50 * score_details.sentiment_score +
             0.35 * score_details.endorsement_score +
             0.15 * score_details.influencer_score) * 100
        ))
        
        # 1점 오차 허용
        if abs(score_details.total - expected_total) > 1:
            issues.append(
                f"CRITICAL: 총점 계산 오류 - 실제: {score_details.total}, "
                f"예상: {expected_total}"
            )
        
        return issues
    
    def _validate_with_context(self, score_details: ScoreDetails, context: Dict) -> List[str]:
        """컨텍스트 기반 검증"""
        issues = []
        
        # 텍스트 길이와 감성 점수 일관성
        text_length = context.get('text_length', 0)
        if text_length < 10 and score_details.sentiment_score > 0.8:
            issues.append("WARNING: 짧은 텍스트에 비해 감성 점수가 높음")
        
        # 채널 규모와 인플루언서 점수 일관성
        subscriber_count = context.get('subscriber_count', 0)
        if subscriber_count < 1000 and score_details.influencer_score > 0.8:
            issues.append("INFO: 소규모 채널에 비해 인플루언서 점수가 높음")
        
        # 시연 레벨과 실사용 점수 일관성
        demonstration_level = context.get('demonstration_level', 0)
        if demonstration_level == 0 and score_details.endorsement_score > 0.7:
            issues.append("WARNING: 시연 없음에 비해 실사용 점수가 높음")
        
        return issues
    
    def _detect_outliers(self, score_details: ScoreDetails) -> List[str]:
        """이상치 탐지"""
        issues = []
        
        try:
            # 총점 이상치 탐지
            if len(self.score_history) >= self.min_history_size:
                z_score = self._calculate_z_score(score_details.total, self.score_history)
                if abs(z_score) > self.outlier_z_threshold:
                    issues.append(f"INFO: 총점 이상치 탐지 (Z-score: {z_score:.2f})")
            
            # 구성 요소별 이상치 탐지
            components = {
                'sentiment': score_details.sentiment_score,
                'endorsement': score_details.endorsement_score,
                'influencer': score_details.influencer_score
            }
            
            for component_name, value in components.items():
                history = self.component_history.get(component_name, [])
                if len(history) >= self.min_history_size:
                    z_score = self._calculate_z_score(value, history)
                    if abs(z_score) > self.outlier_z_threshold:
                        issues.append(
                            f"INFO: {component_name} 점수 이상치 탐지 "
                            f"(Z-score: {z_score:.2f})"
                        )
        
        except Exception as e:
            logger.warning(f"이상치 탐지 중 오류: {str(e)}")
        
        return issues
    
    def _calculate_z_score(self, value: float, history: List[float]) -> float:
        """Z-score 계산"""
        if len(history) < 2:
            return 0.0
        
        mean = statistics.mean(history)
        std_dev = statistics.stdev(history)
        
        if std_dev == 0:
            return 0.0
        
        return (value - mean) / std_dev
    
    def _calculate_validation_confidence(
        self, 
        score_details: ScoreDetails, 
        issues: List[str]
    ) -> float:
        """검증 신뢰도 계산"""
        confidence = 1.0
        
        # 이슈 심각도별 신뢰도 감소
        for issue in issues:
            if 'CRITICAL' in issue:
                confidence -= 0.3
            elif 'WARNING' in issue:
                confidence -= 0.15
            elif 'INFO' in issue:
                confidence -= 0.05
        
        # 점수 안정성 기반 신뢰도 조정
        components = [
            score_details.sentiment_score,
            score_details.endorsement_score,
            score_details.influencer_score
        ]
        
        # 극단값이 많으면 신뢰도 감소
        extreme_count = sum(1 for c in components if c < 0.1 or c > 0.9)
        confidence -= extreme_count * 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _generate_recommendations(
        self, 
        score_details: ScoreDetails, 
        issues: List[str]
    ) -> List[str]:
        """권장 사항 생성"""
        recommendations = []
        
        # 이슈 기반 권장 사항
        if any('CRITICAL' in issue for issue in issues):
            recommendations.append("점수를 재계산하거나 입력 데이터를 확인하세요.")
        
        if any('mathematical' in issue.lower() for issue in issues):
            recommendations.append("수학적 계산 로직을 점검하세요.")
        
        # 점수 기반 권장 사항
        if score_details.total < 30:
            recommendations.append("낮은 점수: 입력 데이터의 품질을 확인하세요.")
        elif score_details.total > 95:
            recommendations.append("매우 높은 점수: 과도한 평가가 아닌지 확인하세요.")
        
        # 구성 요소별 권장 사항
        if score_details.sentiment_score < 0.3:
            recommendations.append("감성 강도가 낮습니다. 텍스트 분석을 재검토하세요.")
        
        if score_details.endorsement_score < 0.3:
            recommendations.append("실사용 인증이 부족합니다. 사용 패턴을 재확인하세요.")
        
        if score_details.influencer_score < 0.3:
            recommendations.append("인플루언서 신뢰도가 낮습니다. 채널 정보를 확인하세요.")
        
        return recommendations or ["점수가 정상 범위에 있습니다."]
    
    def _adjust_score_if_needed(
        self, 
        score_details: ScoreDetails, 
        issues: List[str]
    ) -> Optional[ScoreDetails]:
        """필요시 점수 보정"""
        # CRITICAL 이슈가 있는 경우에만 보정
        critical_issues = [issue for issue in issues if 'CRITICAL' in issue]
        if not critical_issues:
            return None
        
        try:
            # 범위 보정
            adjusted_sentiment = max(0.0, min(1.0, score_details.sentiment_score))
            adjusted_endorsement = max(0.0, min(1.0, score_details.endorsement_score))
            adjusted_influencer = max(0.0, min(1.0, score_details.influencer_score))
            
            # 총점 재계산
            adjusted_total = int(round(
                (0.50 * adjusted_sentiment +
                 0.35 * adjusted_endorsement +
                 0.15 * adjusted_influencer) * 100
            ))
            adjusted_total = max(0, min(100, adjusted_total))
            
            return ScoreDetails(
                total=adjusted_total,
                sentiment_score=adjusted_sentiment,
                endorsement_score=adjusted_endorsement,
                influencer_score=adjusted_influencer
            )
            
        except Exception as e:
            logger.error(f"점수 보정 실패: {str(e)}")
            return None
    
    def _update_history(self, score_details: ScoreDetails):
        """점수 이력 업데이트"""
        try:
            # 총점 이력 업데이트
            self.score_history.append(score_details.total)
            if len(self.score_history) > 100:  # 최대 100개까지 보관
                self.score_history.pop(0)
            
            # 구성 요소별 이력 업데이트
            components = {
                'sentiment': score_details.sentiment_score,
                'endorsement': score_details.endorsement_score,
                'influencer': score_details.influencer_score
            }
            
            for component_name, value in components.items():
                self.component_history[component_name].append(value)
                if len(self.component_history[component_name]) > 100:
                    self.component_history[component_name].pop(0)
        
        except Exception as e:
            logger.warning(f"이력 업데이트 실패: {str(e)}")
    
    def get_score_statistics(self) -> Optional[ScoreStatistics]:
        """점수 통계 반환"""
        if len(self.score_history) < self.min_history_size:
            return None
        
        try:
            return ScoreStatistics(
                mean=statistics.mean(self.score_history),
                median=statistics.median(self.score_history),
                std_dev=statistics.stdev(self.score_history),
                min_score=min(self.score_history),
                max_score=max(self.score_history),
                outlier_threshold=self.outlier_z_threshold
            )
        except Exception as e:
            logger.error(f"통계 계산 실패: {str(e)}")
            return None
    
    def reset_history(self):
        """이력 초기화"""
        self.score_history.clear()
        for key in self.component_history:
            self.component_history[key].clear()
        logger.info("점수 이력이 초기화되었습니다.")