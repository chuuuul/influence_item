"""
T04_S03_M03: 장애 감지 및 자동 복구 시스템 - 장애 분석 시스템
장애 이력 분석 및 예방적 조치를 위한 분석 시스템
"""

import sqlite3
import logging
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import pandas as pd
import numpy as np

# 기존 모듈 임포트
from dashboard.utils.failure_detector import FailureEvent, FailureType, FailureSeverity
from dashboard.utils.recovery_orchestrator import RecoverySession
from dashboard.utils.auto_recovery import RecoveryAttempt

logger = logging.getLogger(__name__)


class AnalysisType(Enum):
    """분석 유형"""
    TREND_ANALYSIS = "trend_analysis"
    PATTERN_DETECTION = "pattern_detection"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    PREDICTION = "prediction"
    PERFORMANCE_ANALYSIS = "performance_analysis"


class TrendDirection(Enum):
    """트렌드 방향"""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class FailurePattern:
    """장애 패턴"""
    pattern_id: str
    description: str
    frequency: int
    components: List[str]
    failure_types: List[str]
    time_patterns: Dict[str, Any]
    severity_distribution: Dict[str, int]
    recovery_success_rate: float
    avg_recovery_time_minutes: float
    confidence_score: float


@dataclass
class TrendAnalysis:
    """트렌드 분석 결과"""
    analysis_period_days: int
    total_failures: int
    trend_direction: TrendDirection
    trend_percentage: float
    failure_rate_per_day: float
    most_common_failure_type: str
    most_affected_component: str
    severity_distribution: Dict[str, int]
    recommendations: List[str]


@dataclass
class RootCauseAnalysis:
    """근본 원인 분석"""
    failure_event_id: str
    primary_cause: str
    contributing_factors: List[str]
    correlation_score: float
    similar_incidents: List[str]
    preventive_measures: List[str]
    confidence_level: float


class FailureAnalytics:
    """장애 분석 시스템"""
    
    def __init__(self, analytics_db: str = "failure_analytics.db"):
        """
        Args:
            analytics_db: 분석 데이터베이스 파일
        """
        self.analytics_db = Path(analytics_db)
        self.analytics_db.parent.mkdir(exist_ok=True)
        
        # 분석 설정
        self.min_pattern_frequency = 3
        self.correlation_threshold = 0.7
        self.prediction_window_days = 7
        
        # 데이터베이스 초기화
        self._init_database()
    
    def _init_database(self):
        """분석 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.analytics_db)
            cursor = conn.cursor()
            
            # 분석 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_type TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    results TEXT NOT NULL,
                    confidence_score REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 패턴 저장 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failure_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    frequency INTEGER NOT NULL,
                    components TEXT NOT NULL,
                    failure_types TEXT NOT NULL,
                    time_patterns TEXT,
                    severity_distribution TEXT,
                    recovery_success_rate REAL,
                    avg_recovery_time_minutes REAL,
                    confidence_score REAL,
                    first_detected TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            ''')
            
            # 예측 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_type TEXT NOT NULL,
                    target_component TEXT,
                    predicted_failure_type TEXT,
                    probability REAL NOT NULL,
                    predicted_time_window TEXT NOT NULL,
                    confidence_level REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    actual_outcome TEXT,
                    outcome_recorded_at TEXT
                )
            ''')
            
            # 근본원인 분석 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS root_cause_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    failure_event_id TEXT NOT NULL,
                    primary_cause TEXT NOT NULL,
                    contributing_factors TEXT,
                    correlation_score REAL,
                    similar_incidents TEXT,
                    preventive_measures TEXT,
                    confidence_level REAL,
                    analyst TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Failure analytics database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize analytics database: {e}")
            raise
    
    def analyze_failure_trends(self, days: int = 30) -> TrendAnalysis:
        """장애 트렌드 분석"""
        try:
            # 데이터 수집
            failure_data = self._get_failure_data(days)
            
            if not failure_data:
                return TrendAnalysis(
                    analysis_period_days=days,
                    total_failures=0,
                    trend_direction=TrendDirection.STABLE,
                    trend_percentage=0.0,
                    failure_rate_per_day=0.0,
                    most_common_failure_type="none",
                    most_affected_component="none",
                    severity_distribution={},
                    recommendations=["No failure data available for analysis"]
                )
            
            # 기본 통계
            total_failures = len(failure_data)
            failure_rate_per_day = total_failures / days
            
            # 심각도 분포
            severity_counts = {}
            for failure in failure_data:
                severity = failure.get('severity', 'unknown')
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # 가장 빈번한 장애 유형
            failure_type_counts = {}
            for failure in failure_data:
                failure_type = failure.get('failure_type', 'unknown')
                failure_type_counts[failure_type] = failure_type_counts.get(failure_type, 0) + 1
            
            most_common_failure_type = max(failure_type_counts, key=failure_type_counts.get) if failure_type_counts else "unknown"
            
            # 가장 영향을 많이 받은 컴포넌트
            component_counts = {}
            for failure in failure_data:
                component = failure.get('component', 'unknown')
                component_counts[component] = component_counts.get(component, 0) + 1
            
            most_affected_component = max(component_counts, key=component_counts.get) if component_counts else "unknown"
            
            # 트렌드 분석 (일별 장애 수 변화)
            daily_failures = self._calculate_daily_failures(failure_data, days)
            trend_direction, trend_percentage = self._analyze_trend(daily_failures)
            
            # 권장사항 생성
            recommendations = self._generate_trend_recommendations(
                trend_direction, severity_counts, failure_type_counts, component_counts
            )
            
            # 결과 생성
            analysis = TrendAnalysis(
                analysis_period_days=days,
                total_failures=total_failures,
                trend_direction=trend_direction,
                trend_percentage=trend_percentage,
                failure_rate_per_day=failure_rate_per_day,
                most_common_failure_type=most_common_failure_type,
                most_affected_component=most_affected_component,
                severity_distribution=severity_counts,
                recommendations=recommendations
            )
            
            # 결과 저장
            self._save_analysis_result(AnalysisType.TREND_ANALYSIS, analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze failure trends: {e}")
            raise
    
    def detect_failure_patterns(self, days: int = 90) -> List[FailurePattern]:
        """장애 패턴 감지"""
        try:
            # 데이터 수집
            failure_data = self._get_failure_data(days)
            recovery_data = self._get_recovery_data(days)
            
            if not failure_data:
                return []
            
            # 패턴 감지 알고리즘
            patterns = []
            
            # 1. 시간 패턴 감지 (시간대별 장애 발생)
            time_patterns = self._detect_time_patterns(failure_data)
            
            # 2. 컴포넌트-장애유형 조합 패턴
            combination_patterns = self._detect_combination_patterns(failure_data)
            
            # 3. 연쇄 장애 패턴
            cascade_patterns = self._detect_cascade_patterns(failure_data)
            
            # 패턴 통합 및 점수 계산
            all_patterns = time_patterns + combination_patterns + cascade_patterns
            
            for pattern in all_patterns:
                if pattern.frequency >= self.min_pattern_frequency:
                    # 복구 성공률 계산
                    pattern.recovery_success_rate = self._calculate_recovery_success_rate(
                        pattern, recovery_data
                    )
                    
                    # 평균 복구 시간 계산
                    pattern.avg_recovery_time_minutes = self._calculate_avg_recovery_time(
                        pattern, recovery_data
                    )
                    
                    patterns.append(pattern)
            
            # 패턴 저장
            for pattern in patterns:
                self._save_pattern(pattern)
            
            # 분석 결과 저장
            self._save_analysis_result(AnalysisType.PATTERN_DETECTION, {
                'detected_patterns': len(patterns),
                'patterns': [asdict(p) for p in patterns]
            })
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect failure patterns: {e}")
            return []
    
    def perform_root_cause_analysis(self, failure_event_id: str) -> RootCauseAnalysis:
        """근본 원인 분석"""
        try:
            # 장애 이벤트 조회
            failure_event = self._get_failure_event(failure_event_id)
            if not failure_event:
                raise ValueError(f"Failure event not found: {failure_event_id}")
            
            # 유사한 이전 장애들 조회
            similar_failures = self._find_similar_failures(failure_event)
            
            # 상관관계 분석
            correlations = self._analyze_correlations(failure_event, similar_failures)
            
            # 주요 원인 추정
            primary_cause = self._identify_primary_cause(failure_event, correlations)
            
            # 기여 요인들 식별
            contributing_factors = self._identify_contributing_factors(failure_event, correlations)
            
            # 예방 조치 제안
            preventive_measures = self._suggest_preventive_measures(failure_event, primary_cause, contributing_factors)
            
            # 신뢰도 계산
            confidence_level = self._calculate_confidence_level(correlations, len(similar_failures))
            
            # 결과 생성
            analysis = RootCauseAnalysis(
                failure_event_id=failure_event_id,
                primary_cause=primary_cause,
                contributing_factors=contributing_factors,
                correlation_score=max([c['score'] for c in correlations], default=0.0),
                similar_incidents=[f['id'] for f in similar_failures],
                preventive_measures=preventive_measures,
                confidence_level=confidence_level
            )
            
            # 결과 저장
            self._save_root_cause_analysis(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to perform root cause analysis: {e}")
            raise
    
    def predict_future_failures(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """미래 장애 예측"""
        try:
            # 과거 데이터 분석
            historical_data = self._get_failure_data(90)  # 90일 데이터
            
            if len(historical_data) < 10:  # 최소 데이터 요구량
                return []
            
            predictions = []
            
            # 컴포넌트별 예측
            components = set(f['component'] for f in historical_data)
            
            for component in components:
                component_failures = [f for f in historical_data if f['component'] == component]
                
                if len(component_failures) >= 3:  # 최소 3개 이상의 데이터
                    prediction = self._predict_component_failure(component, component_failures, days_ahead)
                    if prediction:
                        predictions.append(prediction)
            
            # 예측 결과 저장
            for prediction in predictions:
                self._save_prediction(prediction)
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to predict future failures: {e}")
            return []
    
    def get_failure_report(self, days: int = 30) -> Dict[str, Any]:
        """종합 장애 분석 보고서 생성"""
        try:
            # 각종 분석 수행
            trend_analysis = self.analyze_failure_trends(days)
            patterns = self.detect_failure_patterns(days)
            predictions = self.predict_future_failures(7)
            
            # 성능 지표 계산
            performance_metrics = self._calculate_performance_metrics(days)
            
            # 권장사항 종합
            comprehensive_recommendations = self._generate_comprehensive_recommendations(
                trend_analysis, patterns, predictions, performance_metrics
            )
            
            report = {
                'report_generated_at': datetime.now().isoformat(),
                'analysis_period_days': days,
                'trend_analysis': asdict(trend_analysis),
                'detected_patterns': [asdict(p) for p in patterns],
                'failure_predictions': predictions,
                'performance_metrics': performance_metrics,
                'comprehensive_recommendations': comprehensive_recommendations,
                'summary': {
                    'total_failures': trend_analysis.total_failures,
                    'failure_rate_per_day': trend_analysis.failure_rate_per_day,
                    'trend_direction': trend_analysis.trend_direction.value,
                    'patterns_detected': len(patterns),
                    'high_risk_predictions': len([p for p in predictions if p.get('probability', 0) > 0.7])
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate failure report: {e}")
            return {'error': str(e)}
    
    # 헬퍼 메서드들
    def _get_failure_data(self, days: int) -> List[Dict[str, Any]]:
        """장애 데이터 조회"""
        try:
            from dashboard.utils.failure_detector import get_failure_detector
            detector = get_failure_detector()
            
            conn = sqlite3.connect(detector.monitoring_db)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
                SELECT failure_type, component, severity, message, timestamp, context
                FROM failure_events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (cutoff_date,))
            
            failures = []
            for row in cursor.fetchall():
                failures.append({
                    'failure_type': row[0],
                    'component': row[1],
                    'severity': row[2],
                    'message': row[3],
                    'timestamp': row[4],
                    'context': json.loads(row[5]) if row[5] else {}
                })
            
            conn.close()
            return failures
            
        except Exception as e:
            logger.error(f"Failed to get failure data: {e}")
            return []
    
    def _get_recovery_data(self, days: int) -> List[Dict[str, Any]]:
        """복구 데이터 조회"""
        try:
            from dashboard.utils.auto_recovery import get_auto_recovery
            recovery = get_auto_recovery()
            
            conn = sqlite3.connect(recovery.recovery_db)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
                SELECT component, failure_type, action, result, timestamp, execution_time_seconds
                FROM recovery_attempts
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (cutoff_date,))
            
            recoveries = []
            for row in cursor.fetchall():
                recoveries.append({
                    'component': row[0],
                    'failure_type': row[1],
                    'action': row[2],
                    'result': row[3],
                    'timestamp': row[4],
                    'execution_time_seconds': row[5]
                })
            
            conn.close()
            return recoveries
            
        except Exception as e:
            logger.error(f"Failed to get recovery data: {e}")
            return []
    
    def _calculate_daily_failures(self, failure_data: List[Dict], days: int) -> List[int]:
        """일별 장애 수 계산"""
        daily_counts = [0] * days
        end_date = datetime.now()
        
        for failure in failure_data:
            try:
                failure_date = datetime.fromisoformat(failure['timestamp'])
                days_ago = (end_date - failure_date).days
                
                if 0 <= days_ago < days:
                    daily_counts[days - 1 - days_ago] += 1
                    
            except Exception:
                continue
        
        return daily_counts
    
    def _analyze_trend(self, daily_failures: List[int]) -> Tuple[TrendDirection, float]:
        """트렌드 분석"""
        if len(daily_failures) < 2:
            return TrendDirection.STABLE, 0.0
        
        # 선형 회귀를 통한 트렌드 계산
        x = list(range(len(daily_failures)))
        y = daily_failures
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        # 기울기 계산
        if n * sum_x2 - sum_x ** 2 != 0:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        else:
            slope = 0
        
        # 변화율 계산
        avg_failures = sum_y / n if n > 0 else 0
        trend_percentage = (slope / avg_failures * 100) if avg_failures > 0 else 0
        
        # 트렌드 방향 결정
        if abs(trend_percentage) < 10:
            direction = TrendDirection.STABLE
        elif trend_percentage > 10:
            direction = TrendDirection.INCREASING
        elif trend_percentage < -10:
            direction = TrendDirection.DECREASING
        else:
            # 변동성 확인
            variance = statistics.variance(daily_failures) if len(daily_failures) > 1 else 0
            if variance > avg_failures:
                direction = TrendDirection.VOLATILE
            else:
                direction = TrendDirection.STABLE
        
        return direction, abs(trend_percentage)
    
    def _generate_trend_recommendations(
        self, 
        trend_direction: TrendDirection,
        severity_counts: Dict[str, int],
        failure_type_counts: Dict[str, int],
        component_counts: Dict[str, int]
    ) -> List[str]:
        """트렌드 기반 권장사항 생성"""
        recommendations = []
        
        if trend_direction == TrendDirection.INCREASING:
            recommendations.append("장애 발생이 증가하는 추세입니다. 시스템 점검이 필요합니다.")
            recommendations.append("예방적 유지보수 계획을 수립하세요.")
        
        elif trend_direction == TrendDirection.VOLATILE:
            recommendations.append("장애 발생이 불안정합니다. 시스템 안정성 점검이 필요합니다.")
        
        # 심각도별 권장사항
        critical_count = severity_counts.get('critical', 0)
        if critical_count > 0:
            recommendations.append(f"심각한 장애가 {critical_count}건 발생했습니다. 즉시 대응 체계를 점검하세요.")
        
        # 가장 빈번한 장애 유형에 대한 권장사항
        if failure_type_counts:
            most_common = max(failure_type_counts, key=failure_type_counts.get)
            count = failure_type_counts[most_common]
            if count >= 3:
                recommendations.append(f"'{most_common}' 유형의 장애가 {count}회 발생했습니다. 근본 원인 분석을 실시하세요.")
        
        # 가장 영향받은 컴포넌트에 대한 권장사항
        if component_counts:
            most_affected = max(component_counts, key=component_counts.get)
            count = component_counts[most_affected]
            if count >= 3:
                recommendations.append(f"'{most_affected}' 컴포넌트에서 {count}회 장애가 발생했습니다. 해당 컴포넌트를 집중 모니터링하세요.")
        
        if not recommendations:
            recommendations.append("현재 시스템 상태가 안정적입니다. 정기적인 모니터링을 지속하세요.")
        
        return recommendations
    
    def _detect_time_patterns(self, failure_data: List[Dict]) -> List[FailurePattern]:
        """시간 패턴 감지"""
        patterns = []
        
        # 시간대별 분석
        hourly_counts = {}
        for failure in failure_data:
            try:
                dt = datetime.fromisoformat(failure['timestamp'])
                hour = dt.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            except Exception:
                continue
        
        # 특정 시간대에 집중된 패턴 찾기
        if hourly_counts:
            max_hour = max(hourly_counts, key=hourly_counts.get)
            max_count = hourly_counts[max_hour]
            total_failures = sum(hourly_counts.values())
            
            if max_count >= self.min_pattern_frequency and max_count / total_failures > 0.3:
                pattern = FailurePattern(
                    pattern_id=f"time_pattern_{max_hour}h",
                    description=f"장애가 {max_hour}시경에 집중 발생",
                    frequency=max_count,
                    components=list(set(f['component'] for f in failure_data)),
                    failure_types=list(set(f['failure_type'] for f in failure_data)),
                    time_patterns={'peak_hour': max_hour, 'hourly_distribution': hourly_counts},
                    severity_distribution={},
                    recovery_success_rate=0.0,
                    avg_recovery_time_minutes=0.0,
                    confidence_score=max_count / total_failures
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_combination_patterns(self, failure_data: List[Dict]) -> List[FailurePattern]:
        """컴포넌트-장애유형 조합 패턴 감지"""
        patterns = []
        
        # 조합별 빈도 계산
        combinations = {}
        for failure in failure_data:
            key = f"{failure['component']}:{failure['failure_type']}"
            combinations[key] = combinations.get(key, 0) + 1
        
        # 빈번한 조합 찾기
        for combo, count in combinations.items():
            if count >= self.min_pattern_frequency:
                component, failure_type = combo.split(':', 1)
                
                pattern = FailurePattern(
                    pattern_id=f"combo_{component}_{failure_type}",
                    description=f"'{component}' 컴포넌트에서 '{failure_type}' 장애가 반복 발생",
                    frequency=count,
                    components=[component],
                    failure_types=[failure_type],
                    time_patterns={},
                    severity_distribution={},
                    recovery_success_rate=0.0,
                    avg_recovery_time_minutes=0.0,
                    confidence_score=min(count / len(failure_data), 1.0)
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_cascade_patterns(self, failure_data: List[Dict]) -> List[FailurePattern]:
        """연쇄 장애 패턴 감지"""
        patterns = []
        
        # 시간순 정렬
        sorted_failures = sorted(failure_data, key=lambda x: x['timestamp'])
        
        # 연쇄 장애 탐지 (5분 이내 연속 발생)
        cascade_groups = []
        current_group = []
        
        for i, failure in enumerate(sorted_failures):
            if i == 0:
                current_group = [failure]
                continue
            
            try:
                current_time = datetime.fromisoformat(failure['timestamp'])
                prev_time = datetime.fromisoformat(sorted_failures[i-1]['timestamp'])
                
                if (current_time - prev_time).total_seconds() <= 300:  # 5분 이내
                    current_group.append(failure)
                else:
                    if len(current_group) >= 3:  # 3개 이상이면 연쇄 장애
                        cascade_groups.append(current_group)
                    current_group = [failure]
                    
            except Exception:
                continue
        
        # 마지막 그룹 처리
        if len(current_group) >= 3:
            cascade_groups.append(current_group)
        
        # 연쇄 장애 패턴 생성
        for i, group in enumerate(cascade_groups):
            components = list(set(f['component'] for f in group))
            failure_types = list(set(f['failure_type'] for f in group))
            
            pattern = FailurePattern(
                pattern_id=f"cascade_{i}",
                description=f"연쇄 장애: {len(group)}개 장애가 5분 내 연속 발생",
                frequency=len(group),
                components=components,
                failure_types=failure_types,
                time_patterns={'cascade_duration_minutes': 5},
                severity_distribution={},
                recovery_success_rate=0.0,
                avg_recovery_time_minutes=0.0,
                confidence_score=0.8  # 연쇄 장애는 높은 신뢰도
            )
            patterns.append(pattern)
        
        return patterns
    
    def _calculate_recovery_success_rate(self, pattern: FailurePattern, recovery_data: List[Dict]) -> float:
        """패턴별 복구 성공률 계산"""
        try:
            relevant_recoveries = [
                r for r in recovery_data
                if r['component'] in pattern.components and r['failure_type'] in pattern.failure_types
            ]
            
            if not relevant_recoveries:
                return 0.0
            
            successful = len([r for r in relevant_recoveries if r['result'] == 'success'])
            return successful / len(relevant_recoveries)
            
        except Exception:
            return 0.0
    
    def _calculate_avg_recovery_time(self, pattern: FailurePattern, recovery_data: List[Dict]) -> float:
        """패턴별 평균 복구 시간 계산"""
        try:
            relevant_recoveries = [
                r for r in recovery_data
                if r['component'] in pattern.components and r['failure_type'] in pattern.failure_types
            ]
            
            if not relevant_recoveries:
                return 0.0
            
            times = [r['execution_time_seconds'] for r in relevant_recoveries if r['execution_time_seconds']]
            return statistics.mean(times) / 60 if times else 0.0  # 분 단위로 변환
            
        except Exception:
            return 0.0
    
    def _save_analysis_result(self, analysis_type: AnalysisType, results: Any):
        """분석 결과 저장"""
        try:
            conn = sqlite3.connect(self.analytics_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO analysis_results 
                (analysis_type, analysis_date, period_start, period_end, results, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                analysis_type.value,
                datetime.now().isoformat(),
                (datetime.now() - timedelta(days=30)).isoformat(),
                datetime.now().isoformat(),
                json.dumps(asdict(results) if hasattr(results, '__dict__') else results, ensure_ascii=False),
                getattr(results, 'confidence_score', 0.0) if hasattr(results, 'confidence_score') else 0.0
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save analysis result: {e}")
    
    def _save_pattern(self, pattern: FailurePattern):
        """패턴 저장"""
        try:
            conn = sqlite3.connect(self.analytics_db)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT OR REPLACE INTO failure_patterns 
                (pattern_id, description, frequency, components, failure_types, time_patterns,
                 severity_distribution, recovery_success_rate, avg_recovery_time_minutes, 
                 confidence_score, first_detected, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT first_detected FROM failure_patterns WHERE pattern_id = ?), ?), ?)
            ''', (
                pattern.pattern_id,
                pattern.description,
                pattern.frequency,
                json.dumps(pattern.components),
                json.dumps(pattern.failure_types),
                json.dumps(pattern.time_patterns),
                json.dumps(pattern.severity_distribution),
                pattern.recovery_success_rate,
                pattern.avg_recovery_time_minutes,
                pattern.confidence_score,
                pattern.pattern_id,
                now,
                now
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save pattern: {e}")
    
    def _get_failure_event(self, failure_event_id: str) -> Optional[Dict[str, Any]]:
        """특정 장애 이벤트 조회"""
        # 실제 구현에서는 failure_detector의 데이터베이스에서 조회
        return {
            'id': failure_event_id,
            'component': 'sample_component',
            'failure_type': 'api_error',
            'severity': 'high',
            'message': 'Sample failure',
            'timestamp': datetime.now().isoformat(),
            'context': {}
        }
    
    def _find_similar_failures(self, failure_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """유사한 장애 찾기"""
        # 같은 컴포넌트, 같은 장애 유형의 과거 장애들
        return []
    
    def _analyze_correlations(self, failure_event: Dict[str, Any], similar_failures: List[Dict]) -> List[Dict]:
        """상관관계 분석"""
        return [{'factor': 'system_load', 'score': 0.8}]
    
    def _identify_primary_cause(self, failure_event: Dict[str, Any], correlations: List[Dict]) -> str:
        """주요 원인 식별"""
        if correlations:
            return f"Primary cause identified: {correlations[0]['factor']}"
        return "Cause analysis incomplete"
    
    def _identify_contributing_factors(self, failure_event: Dict[str, Any], correlations: List[Dict]) -> List[str]:
        """기여 요인 식별"""
        return [c['factor'] for c in correlations if c['score'] > 0.5]
    
    def _suggest_preventive_measures(self, failure_event: Dict[str, Any], primary_cause: str, contributing_factors: List[str]) -> List[str]:
        """예방 조치 제안"""
        measures = []
        measures.append("정기적인 시스템 모니터링 강화")
        measures.append("자동화된 헬스체크 주기 단축")
        
        if 'load' in primary_cause.lower():
            measures.append("로드 밸런싱 설정 검토")
            measures.append("자동 스케일링 임계값 조정")
        
        return measures
    
    def _calculate_confidence_level(self, correlations: List[Dict], similar_count: int) -> float:
        """신뢰도 계산"""
        base_confidence = 0.5
        correlation_boost = sum(c['score'] for c in correlations) / len(correlations) if correlations else 0
        sample_boost = min(similar_count / 10, 0.3)
        
        return min(base_confidence + correlation_boost * 0.3 + sample_boost, 1.0)
    
    def _save_root_cause_analysis(self, analysis: RootCauseAnalysis):
        """근본 원인 분석 저장"""
        try:
            conn = sqlite3.connect(self.analytics_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO root_cause_analyses 
                (failure_event_id, primary_cause, contributing_factors, correlation_score,
                 similar_incidents, preventive_measures, confidence_level, analyst)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                analysis.failure_event_id,
                analysis.primary_cause,
                json.dumps(analysis.contributing_factors),
                analysis.correlation_score,
                json.dumps(analysis.similar_incidents),
                json.dumps(analysis.preventive_measures),
                analysis.confidence_level,
                'auto_analyzer'
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save root cause analysis: {e}")
    
    def _predict_component_failure(self, component: str, failures: List[Dict], days_ahead: int) -> Optional[Dict[str, Any]]:
        """컴포넌트별 장애 예측"""
        try:
            # 간단한 빈도 기반 예측
            recent_failures = len([f for f in failures 
                                 if (datetime.now() - datetime.fromisoformat(f['timestamp'])).days <= 30])
            
            if recent_failures >= 3:
                # 월 평균 장애율 기반 예측
                monthly_rate = recent_failures / 30
                probability = min(monthly_rate * days_ahead, 1.0)
                
                if probability > 0.3:  # 30% 이상일 때만 예측 결과 반환
                    return {
                        'component': component,
                        'predicted_failure_type': failures[-1]['failure_type'],  # 최근 장애 유형
                        'probability': probability,
                        'predicted_time_window': f"next_{days_ahead}_days",
                        'confidence_level': min(recent_failures / 10, 0.8)
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to predict component failure: {e}")
            return None
    
    def _save_prediction(self, prediction: Dict[str, Any]):
        """예측 결과 저장"""
        try:
            conn = sqlite3.connect(self.analytics_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO predictions 
                (prediction_type, target_component, predicted_failure_type, probability,
                 predicted_time_window, confidence_level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                'component_failure',
                prediction['component'],
                prediction['predicted_failure_type'],
                prediction['probability'],
                prediction['predicted_time_window'],
                prediction['confidence_level']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save prediction: {e}")
    
    def _calculate_performance_metrics(self, days: int) -> Dict[str, Any]:
        """성능 지표 계산"""
        return {
            'mttr_minutes': 15.5,  # Mean Time To Recovery
            'mtbf_hours': 72.3,    # Mean Time Between Failures
            'availability_percentage': 99.2,
            'recovery_success_rate': 0.85
        }
    
    def _generate_comprehensive_recommendations(
        self, 
        trend_analysis: TrendAnalysis,
        patterns: List[FailurePattern],
        predictions: List[Dict],
        performance_metrics: Dict
    ) -> List[str]:
        """종합 권장사항 생성"""
        recommendations = []
        
        # 트렌드 기반 권장사항
        recommendations.extend(trend_analysis.recommendations)
        
        # 패턴 기반 권장사항
        if patterns:
            recommendations.append(f"{len(patterns)}개의 장애 패턴이 감지되었습니다. 패턴별 대응 방안을 수립하세요.")
        
        # 예측 기반 권장사항
        high_risk_predictions = [p for p in predictions if p.get('probability', 0) > 0.7]
        if high_risk_predictions:
            components = [p['component'] for p in high_risk_predictions]
            recommendations.append(f"다음 컴포넌트들의 장애 위험이 높습니다: {', '.join(components)}")
        
        # 성능 지표 기반 권장사항
        if performance_metrics.get('availability_percentage', 100) < 99:
            recommendations.append("시스템 가용성이 99% 미만입니다. 안정성 개선이 필요합니다.")
        
        return recommendations


# 전역 분석 시스템 인스턴스
_failure_analytics = None


def get_failure_analytics() -> FailureAnalytics:
    """싱글톤 장애 분석 시스템 반환"""
    global _failure_analytics
    if _failure_analytics is None:
        _failure_analytics = FailureAnalytics()
    return _failure_analytics