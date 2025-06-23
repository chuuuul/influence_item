"""
Cost Optimization Engine
비용 최적화 분석 엔진

월말 예상 비용 예측 및 비용 최적화 권장사항 생성
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.metrics import mean_absolute_error

from src.api.usage_tracker import APIUsageTracker, get_tracker

# 로깅 설정
logger = logging.getLogger(__name__)


@dataclass
class CostPrediction:
    """비용 예측 결과"""
    predicted_monthly_cost: float
    confidence_score: float
    prediction_method: str
    daily_trend: List[float]
    api_breakdown: Dict[str, float]
    risk_level: str
    warning_message: Optional[str] = None


@dataclass
class OptimizationRecommendation:
    """최적화 권장사항"""
    category: str
    priority: str  # high, medium, low
    title: str
    description: str
    potential_savings: float
    implementation_effort: str  # easy, medium, hard
    action_items: List[str]


class CostOptimizer:
    """비용 최적화 및 예측 엔진"""
    
    def __init__(self, monthly_budget: float = 15000.0):
        """
        Args:
            monthly_budget: 월 예산 (원)
        """
        self.monthly_budget = monthly_budget
        self.usage_tracker = get_tracker()
        
        # 최적화 규칙 등록
        self.optimization_rules = [
            self._check_api_usage_patterns,
            self._check_resource_utilization,
            self._check_request_efficiency,
            self._check_caching_opportunities,
            self._check_rate_limiting_optimization,
            self._check_time_based_optimization
        ]
        
        logger.info("비용 최적화 엔진 초기화 완료")
    
    async def predict_monthly_cost(self, method: str = "auto") -> CostPrediction:
        """
        월말 예상 비용 예측
        
        Args:
            method: 예측 방법 ("linear", "polynomial", "seasonal", "auto")
        """
        try:
            # 현재 월 데이터 수집
            current_day = datetime.now().day
            days_in_month = pd.Timestamp.now().days_in_month
            
            # 일별 사용량 데이터 가져오기
            daily_data = await self._get_daily_usage_data(days=current_day)
            
            if len(daily_data) < 3:
                # 데이터가 부족한 경우 단순 선형 예측
                return await self._simple_linear_prediction(daily_data, days_in_month)
            
            # 방법별 예측 수행
            if method == "auto":
                predictions = []
                predictions.append(await self._linear_prediction(daily_data, days_in_month))
                predictions.append(await self._polynomial_prediction(daily_data, days_in_month))
                predictions.append(await self._seasonal_prediction(daily_data, days_in_month))
                
                # 가장 신뢰도 높은 예측 선택
                best_prediction = max(predictions, key=lambda p: p.confidence_score)
                return best_prediction
            
            elif method == "linear":
                return await self._linear_prediction(daily_data, days_in_month)
            elif method == "polynomial":
                return await self._polynomial_prediction(daily_data, days_in_month)
            elif method == "seasonal":
                return await self._seasonal_prediction(daily_data, days_in_month)
            else:
                raise ValueError(f"알 수 없는 예측 방법: {method}")
                
        except Exception as e:
            logger.error(f"비용 예측 오류: {e}")
            return await self._fallback_prediction()
    
    async def _get_daily_usage_data(self, days: int) -> pd.DataFrame:
        """일별 사용량 데이터 수집"""
        summary = self.usage_tracker.get_usage_summary(days=days)
        
        daily_costs = []
        daily_usage = summary.get('daily_usage', {})
        
        for i in range(1, days + 1):
            date_str = (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d')
            
            day_cost = 0.0
            day_calls = 0
            api_breakdown = {}
            
            if date_str in daily_usage:
                for api_name, api_data in daily_usage[date_str].items():
                    cost = api_data.get('cost', 0.0)
                    calls = api_data.get('calls', 0)
                    
                    day_cost += cost
                    day_calls += calls
                    api_breakdown[api_name] = cost
            
            daily_costs.append({
                'date': date_str,
                'day': i,
                'cost': day_cost,
                'calls': day_calls,
                'api_breakdown': api_breakdown
            })
        
        return pd.DataFrame(daily_costs)
    
    async def _simple_linear_prediction(self, daily_data: pd.DataFrame, days_in_month: int) -> CostPrediction:
        """단순 선형 예측 (데이터 부족시)"""
        if len(daily_data) == 0:
            predicted_cost = 0.0
        else:
            avg_daily_cost = daily_data['cost'].mean()
            predicted_cost = avg_daily_cost * days_in_month
        
        risk_level = "high" if predicted_cost > self.monthly_budget else "medium"
        
        return CostPrediction(
            predicted_monthly_cost=predicted_cost,
            confidence_score=0.3,  # 낮은 신뢰도
            prediction_method="simple_linear",
            daily_trend=[predicted_cost / days_in_month] * days_in_month,
            api_breakdown={"total": predicted_cost},
            risk_level=risk_level,
            warning_message="데이터 부족으로 낮은 신뢰도 예측"
        )
    
    async def _linear_prediction(self, daily_data: pd.DataFrame, days_in_month: int) -> CostPrediction:
        """선형 회귀 예측"""
        if len(daily_data) < 2:
            return await self._simple_linear_prediction(daily_data, days_in_month)
        
        X = daily_data['day'].values.reshape(-1, 1)
        y = daily_data['cost'].values
        
        # 선형 회귀 모델
        model = LinearRegression()
        model.fit(X, y)
        
        # 전체 월 예측
        all_days = np.arange(1, days_in_month + 1).reshape(-1, 1)
        daily_predictions = model.predict(all_days)
        
        # 음수 값 보정
        daily_predictions = np.maximum(daily_predictions, 0)
        
        predicted_cost = np.sum(daily_predictions)
        
        # 신뢰도 계산 (R² 스코어 기반)
        confidence_score = max(0.1, model.score(X, y))
        
        # API별 예측
        api_breakdown = await self._predict_api_breakdown(daily_data, predicted_cost)
        
        risk_level = self._assess_risk_level(predicted_cost)
        
        return CostPrediction(
            predicted_monthly_cost=predicted_cost,
            confidence_score=confidence_score,
            prediction_method="linear_regression",
            daily_trend=daily_predictions.tolist(),
            api_breakdown=api_breakdown,
            risk_level=risk_level
        )
    
    async def _polynomial_prediction(self, daily_data: pd.DataFrame, days_in_month: int) -> CostPrediction:
        """다항식 회귀 예측 (비선형 트렌드 감지)"""
        if len(daily_data) < 4:
            return await self._linear_prediction(daily_data, days_in_month)
        
        X = daily_data['day'].values.reshape(-1, 1)
        y = daily_data['cost'].values
        
        # 2차 다항식 특성 생성
        poly_features = PolynomialFeatures(degree=2)
        X_poly = poly_features.fit_transform(X)
        
        # 다항식 회귀 모델
        model = LinearRegression()
        model.fit(X_poly, y)
        
        # 전체 월 예측
        all_days = np.arange(1, days_in_month + 1).reshape(-1, 1)
        all_days_poly = poly_features.transform(all_days)
        daily_predictions = model.predict(all_days_poly)
        
        # 음수 값 보정
        daily_predictions = np.maximum(daily_predictions, 0)
        
        predicted_cost = np.sum(daily_predictions)
        
        # 신뢰도 계산
        confidence_score = max(0.1, model.score(X_poly, y))
        
        # API별 예측
        api_breakdown = await self._predict_api_breakdown(daily_data, predicted_cost)
        
        risk_level = self._assess_risk_level(predicted_cost)
        
        return CostPrediction(
            predicted_monthly_cost=predicted_cost,
            confidence_score=confidence_score,
            prediction_method="polynomial_regression",
            daily_trend=daily_predictions.tolist(),
            api_breakdown=api_breakdown,
            risk_level=risk_level
        )
    
    async def _seasonal_prediction(self, daily_data: pd.DataFrame, days_in_month: int) -> CostPrediction:
        """계절성/주기성을 고려한 예측"""
        if len(daily_data) < 7:
            return await self._linear_prediction(daily_data, days_in_month)
        
        # 주별 패턴 분석
        daily_data['weekday'] = pd.to_datetime(daily_data['date']).dt.dayofweek
        weekday_avg = daily_data.groupby('weekday')['cost'].mean()
        
        # 현재까지의 트렌드 계산
        X = daily_data['day'].values.reshape(-1, 1)
        y = daily_data['cost'].values
        
        trend_model = LinearRegression()
        trend_model.fit(X, y)
        
        # 전체 월 예측 (트렌드 + 주기성)
        daily_predictions = []
        for day in range(1, days_in_month + 1):
            date = datetime(datetime.now().year, datetime.now().month, day)
            weekday = date.weekday()
            
            # 트렌드 예측
            trend_cost = trend_model.predict([[day]])[0]
            
            # 주별 패턴 적용
            if weekday in weekday_avg.index:
                weekday_factor = weekday_avg[weekday] / daily_data['cost'].mean() if daily_data['cost'].mean() > 0 else 1
                seasonal_cost = trend_cost * weekday_factor
            else:
                seasonal_cost = trend_cost
            
            daily_predictions.append(max(0, seasonal_cost))
        
        predicted_cost = sum(daily_predictions)
        
        # 신뢰도 계산
        confidence_score = max(0.2, trend_model.score(X, y) * 0.8)  # 계절성 예측은 약간 낮은 신뢰도
        
        # API별 예측
        api_breakdown = await self._predict_api_breakdown(daily_data, predicted_cost)
        
        risk_level = self._assess_risk_level(predicted_cost)
        
        return CostPrediction(
            predicted_monthly_cost=predicted_cost,
            confidence_score=confidence_score,
            prediction_method="seasonal_regression",
            daily_trend=daily_predictions,
            api_breakdown=api_breakdown,
            risk_level=risk_level
        )
    
    async def _predict_api_breakdown(self, daily_data: pd.DataFrame, total_predicted: float) -> Dict[str, float]:
        """API별 비용 예측 분해"""
        api_totals = {}
        
        # 현재까지의 API별 비용 비율 계산
        for _, row in daily_data.iterrows():
            for api_name, cost in row['api_breakdown'].items():
                if api_name not in api_totals:
                    api_totals[api_name] = 0.0
                api_totals[api_name] += cost
        
        total_current = sum(api_totals.values())
        
        if total_current == 0:
            return {"unknown": total_predicted}
        
        # 비율에 따라 예측 비용 분배
        api_breakdown = {}
        for api_name, cost in api_totals.items():
            ratio = cost / total_current
            api_breakdown[api_name] = total_predicted * ratio
        
        return api_breakdown
    
    def _assess_risk_level(self, predicted_cost: float) -> str:
        """위험 수준 평가"""
        usage_rate = predicted_cost / self.monthly_budget
        
        if usage_rate >= 1.0:
            return "critical"
        elif usage_rate >= 0.9:
            return "high"
        elif usage_rate >= 0.7:
            return "medium"
        else:
            return "low"
    
    async def _fallback_prediction(self) -> CostPrediction:
        """예측 실패시 폴백"""
        return CostPrediction(
            predicted_monthly_cost=0.0,
            confidence_score=0.0,
            prediction_method="fallback",
            daily_trend=[],
            api_breakdown={},
            risk_level="unknown",
            warning_message="예측 데이터를 가져올 수 없습니다"
        )
    
    async def generate_optimization_recommendations(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """비용 최적화 권장사항 생성"""
        recommendations = []
        
        # 각 최적화 규칙 실행
        for rule in self.optimization_rules:
            try:
                rule_recommendations = await rule(prediction)
                recommendations.extend(rule_recommendations)
            except Exception as e:
                logger.error(f"최적화 규칙 실행 오류: {rule.__name__} - {e}")
        
        # 우선순위별 정렬
        priority_order = {"high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 4))
        
        return recommendations
    
    async def _check_api_usage_patterns(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """API 사용 패턴 분석"""
        recommendations = []
        
        # Gemini API 사용량 체크
        gemini_cost = prediction.api_breakdown.get('gemini', 0)
        if gemini_cost > self.monthly_budget * 0.6:  # 60% 이상
            recommendations.append(OptimizationRecommendation(
                category="API Usage",
                priority="high",
                title="Gemini API 사용량 최적화",
                description=f"Gemini API 비용이 예산의 {(gemini_cost/self.monthly_budget)*100:.1f}%를 차지합니다.",
                potential_savings=gemini_cost * 0.2,  # 20% 절약 가능
                implementation_effort="medium",
                action_items=[
                    "프롬프트 길이 최적화",
                    "응답 토큰 수 제한 설정",
                    "배치 처리로 API 호출 횟수 감소",
                    "캐싱을 통한 중복 요청 방지"
                ]
            ))
        
        # 전체 API 호출 빈도 체크
        if prediction.predicted_monthly_cost > self.monthly_budget * 0.8:
            recommendations.append(OptimizationRecommendation(
                category="API Usage",
                priority="medium",
                title="전체 API 호출 최적화",
                description="API 호출 빈도가 높아 비용 절감이 필요합니다.",
                potential_savings=prediction.predicted_monthly_cost * 0.15,
                implementation_effort="easy",
                action_items=[
                    "불필요한 API 호출 제거",
                    "API 호출 전 데이터 검증 강화",
                    "에러 발생시 즉시 재시도 대신 지연 재시도"
                ]
            ))
        
        return recommendations
    
    async def _check_resource_utilization(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """리소스 사용률 분석"""
        recommendations = []
        
        # 현재 사용량이 매우 낮은 경우
        current_usage_rate = prediction.predicted_monthly_cost / self.monthly_budget
        
        if current_usage_rate < 0.3:  # 30% 미만 사용
            recommendations.append(OptimizationRecommendation(
                category="Resource Utilization",
                priority="low",
                title="리소스 활용도 개선",
                description="현재 예산 대비 사용률이 낮아 추가 기능 개발 여유가 있습니다.",
                potential_savings=0.0,  # 절약이 아닌 활용 권장
                implementation_effort="medium",
                action_items=[
                    "추가 AI 모델 실험",
                    "더 정밀한 분석 알고리즘 적용",
                    "배치 크기 증가로 처리량 향상"
                ]
            ))
        
        return recommendations
    
    async def _check_request_efficiency(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """요청 효율성 체크"""
        recommendations = []
        
        # 일별 사용량 데이터 분석
        daily_data = await self._get_daily_usage_data(days=7)
        
        if len(daily_data) > 0:
            # 요청당 평균 비용 계산
            total_calls = daily_data['calls'].sum()
            total_cost = daily_data['cost'].sum()
            
            if total_calls > 0:
                cost_per_call = total_cost / total_calls
                
                # 임계값 대비 높은 경우
                if cost_per_call > 0.5:  # 호출당 0.5원 이상
                    recommendations.append(OptimizationRecommendation(
                        category="Request Efficiency",
                        priority="medium",
                        title="API 호출 효율성 개선",
                        description=f"API 호출당 평균 비용이 ₩{cost_per_call:.3f}로 높습니다.",
                        potential_savings=total_cost * 0.25,
                        implementation_effort="medium",
                        action_items=[
                            "대용량 요청을 작은 단위로 분할",
                            "응답 크기 최적화",
                            "불필요한 메타데이터 제거"
                        ]
                    ))
        
        return recommendations
    
    async def _check_caching_opportunities(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """캐싱 기회 분석"""
        recommendations = []
        
        # 반복 요청 패턴 분석 (실제 구현에서는 더 정교한 분석 필요)
        if prediction.predicted_monthly_cost > self.monthly_budget * 0.5:
            recommendations.append(OptimizationRecommendation(
                category="Caching",
                priority="medium",
                title="응답 캐싱 시스템 도입",
                description="반복적인 API 요청에 대한 캐싱으로 비용을 절감할 수 있습니다.",
                potential_savings=prediction.predicted_monthly_cost * 0.3,
                implementation_effort="hard",
                action_items=[
                    "Redis 캐시 서버 구축",
                    "API 응답 캐싱 정책 수립",
                    "캐시 만료 시간 최적화",
                    "캐시 히트율 모니터링"
                ]
            ))
        
        return recommendations
    
    async def _check_rate_limiting_optimization(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """Rate Limiting 최적화"""
        recommendations = []
        
        # API별 rate limit 효율성 체크
        from src.api.api_limiter import get_api_limiter
        limiter = get_api_limiter()
        
        gemini_status = limiter.get_api_status('gemini')
        
        if gemini_status['rate_limit_info']:
            rate_info = gemini_status['rate_limit_info']
            utilization = rate_info['calls_today'] / rate_info['limits']['per_day']
            
            if utilization > 0.8:  # 80% 이상 사용
                recommendations.append(OptimizationRecommendation(
                    category="Rate Limiting",
                    priority="high",
                    title="API Rate Limit 최적화",
                    description="API 사용률이 높아 rate limit 최적화가 필요합니다.",
                    potential_savings=prediction.predicted_monthly_cost * 0.1,
                    implementation_effort="easy",
                    action_items=[
                        "요청 간격 조정",
                        "배치 처리 도입",
                        "우선순위 기반 요청 큐잉"
                    ]
                ))
        
        return recommendations
    
    async def _check_time_based_optimization(self, prediction: CostPrediction) -> List[OptimizationRecommendation]:
        """시간 기반 최적화"""
        recommendations = []
        
        # 시간대별 사용 패턴 분석 (실제로는 더 정교한 분석 필요)
        if prediction.predicted_monthly_cost > self.monthly_budget * 0.7:
            recommendations.append(OptimizationRecommendation(
                category="Time-based Optimization",
                priority="low",
                title="시간대별 워크로드 분산",
                description="피크 시간대 사용량 분산으로 비용을 최적화할 수 있습니다.",
                potential_savings=prediction.predicted_monthly_cost * 0.1,
                implementation_effort="medium",
                action_items=[
                    "비피크 시간대 배치 작업 스케줄링",
                    "우선순위가 낮은 작업의 시간 분산",
                    "실시간 처리 vs 배치 처리 비율 조정"
                ]
            ))
        
        return recommendations


# 전역 비용 최적화 엔진 인스턴스
_global_cost_optimizer = None

def get_cost_optimizer() -> CostOptimizer:
    """전역 비용 최적화 엔진 인스턴스를 반환"""
    global _global_cost_optimizer
    if _global_cost_optimizer is None:
        _global_cost_optimizer = CostOptimizer()
    return _global_cost_optimizer