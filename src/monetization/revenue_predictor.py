"""
수익화 예측 및 검증 시스템

실제 수익성 데이터를 기반으로 인플루언서의 수익화 가능성을 예측하고,
협업 ROI를 계산하는 고도화된 시스템입니다.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import requests
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)


class MarketCategory(Enum):
    """시장 카테고리"""
    BEAUTY = "beauty"
    FASHION = "fashion"
    LIFESTYLE = "lifestyle"
    FOOD = "food"
    TECH = "tech"
    FITNESS = "fitness"
    PARENTING = "parenting"
    PET_CARE = "pet_care"
    HOME_DECOR = "home_decor"
    TRAVEL = "travel"


@dataclass
class ProductInfo:
    """제품 정보"""
    product_id: str
    name: str
    category: MarketCategory
    price: float
    commission_rate: float
    availability: bool
    stock_level: Optional[int] = None
    price_history: List[Dict] = field(default_factory=list)
    
    
@dataclass
class MarketData:
    """시장 데이터"""
    category: MarketCategory
    avg_conversion_rate: float
    seasonal_multipliers: Dict[str, float]
    competition_level: float
    price_sensitivity: float
    target_demographics: Dict[str, float]


@dataclass
class RevenueMetrics:
    """수익 지표"""
    predicted_revenue: float
    predicted_conversions: int
    roi_percentage: float
    payback_period_days: int
    confidence_score: float
    risk_factors: List[str]
    optimization_suggestions: List[str]


class MarketAnalyzer:
    """시장 분석기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.market_data = self._initialize_market_data()
        self.seasonal_trends = self._initialize_seasonal_trends()
    
    def _initialize_market_data(self) -> Dict[MarketCategory, MarketData]:
        """시장 데이터 초기화"""
        return {
            MarketCategory.BEAUTY: MarketData(
                category=MarketCategory.BEAUTY,
                avg_conversion_rate=0.035,  # 3.5%
                seasonal_multipliers={
                    'spring': 1.2, 'summer': 1.1, 'fall': 1.3, 'winter': 0.9
                },
                competition_level=0.8,
                price_sensitivity=0.6,
                target_demographics={'female_20s': 0.4, 'female_30s': 0.35, 'female_40s': 0.25}
            ),
            MarketCategory.FASHION: MarketData(
                category=MarketCategory.FASHION,
                avg_conversion_rate=0.025,  # 2.5%
                seasonal_multipliers={
                    'spring': 1.3, 'summer': 1.0, 'fall': 1.4, 'winter': 1.1
                },
                competition_level=0.9,
                price_sensitivity=0.7,
                target_demographics={'female_20s': 0.5, 'female_30s': 0.3, 'male_20s': 0.2}
            ),
            MarketCategory.TECH: MarketData(
                category=MarketCategory.TECH,
                avg_conversion_rate=0.015,  # 1.5%
                seasonal_multipliers={
                    'spring': 1.0, 'summer': 0.9, 'fall': 1.1, 'winter': 1.2
                },
                competition_level=0.7,
                price_sensitivity=0.8,
                target_demographics={'male_20s': 0.3, 'male_30s': 0.4, 'female_20s': 0.3}
            ),
            # 다른 카테고리들도 동일하게 초기화
        }
    
    def _initialize_seasonal_trends(self) -> Dict[str, float]:
        """계절별 트렌드 초기화"""
        current_month = datetime.now().month
        
        seasonal_map = {
            (12, 1, 2): 'winter',
            (3, 4, 5): 'spring', 
            (6, 7, 8): 'summer',
            (9, 10, 11): 'fall'
        }
        
        current_season = 'spring'  # 기본값
        for months, season in seasonal_map.items():
            if current_month in months:
                current_season = season
                break
        
        return {'current_season': current_season}
    
    def analyze_market_opportunity(
        self, 
        category: MarketCategory,
        channel_demographics: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """시장 기회 분석"""
        
        market_data = self.market_data.get(category)
        if not market_data:
            return {'error': f'Unknown category: {category}'}
        
        current_season = self.seasonal_trends['current_season']
        seasonal_multiplier = market_data.seasonal_multipliers.get(current_season, 1.0)
        
        # 타겟 인구 매칭 점수
        demographic_match = 1.0
        if channel_demographics:
            demographic_match = self._calculate_demographic_match(
                market_data.target_demographics, channel_demographics
            )
        
        # 기회 점수 계산
        opportunity_score = (
            market_data.avg_conversion_rate * 
            seasonal_multiplier * 
            demographic_match * 
            (2 - market_data.competition_level)  # 경쟁도 역산
        )
        
        return {
            'category': category.value,
            'base_conversion_rate': market_data.avg_conversion_rate,
            'seasonal_multiplier': seasonal_multiplier,
            'demographic_match_score': demographic_match,
            'competition_level': market_data.competition_level,
            'opportunity_score': opportunity_score,
            'market_insights': self._generate_market_insights(market_data, seasonal_multiplier)
        }
    
    def _calculate_demographic_match(
        self, 
        target_demographics: Dict[str, float],
        channel_demographics: Dict[str, float]
    ) -> float:
        """인구 통계학적 매칭 점수 계산"""
        
        match_score = 0.0
        total_weight = 0.0
        
        for demo, target_weight in target_demographics.items():
            channel_weight = channel_demographics.get(demo, 0.0)
            match_score += min(target_weight, channel_weight)
            total_weight += target_weight
        
        return match_score / total_weight if total_weight > 0 else 0.5
    
    def _generate_market_insights(
        self, 
        market_data: MarketData, 
        seasonal_multiplier: float
    ) -> List[str]:
        """시장 인사이트 생성"""
        insights = []
        
        if seasonal_multiplier > 1.2:
            insights.append("현재 성수기 - 높은 전환율 기대")
        elif seasonal_multiplier < 0.9:
            insights.append("현재 비수기 - 보수적 목표 설정 권장")
        
        if market_data.competition_level > 0.8:
            insights.append("고경쟁 시장 - 차별화 전략 필요")
        
        if market_data.price_sensitivity > 0.7:
            insights.append("가격 민감 시장 - 할인 혜택 강조 필요")
        
        return insights


class PriceTracker:
    """가격 추적 시스템"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_history = {}
        self.price_alerts = {}
    
    def track_product_price(self, product_id: str, current_price: float) -> Dict[str, Any]:
        """제품 가격 추적"""
        
        timestamp = datetime.now()
        
        if product_id not in self.price_history:
            self.price_history[product_id] = []
        
        # 가격 기록 저장
        price_record = {
            'timestamp': timestamp.isoformat(),
            'price': current_price
        }
        self.price_history[product_id].append(price_record)
        
        # 최근 30일 데이터만 유지
        cutoff_date = timestamp - timedelta(days=30)
        self.price_history[product_id] = [
            record for record in self.price_history[product_id]
            if datetime.fromisoformat(record['timestamp']) > cutoff_date
        ]
        
        # 가격 변동 분석
        price_analysis = self._analyze_price_trend(product_id)
        
        return {
            'product_id': product_id,
            'current_price': current_price,
            'price_trend': price_analysis['trend'],
            'volatility': price_analysis['volatility'],
            'recommendation': price_analysis['recommendation']
        }
    
    def _analyze_price_trend(self, product_id: str) -> Dict[str, Any]:
        """가격 트렌드 분석"""
        
        history = self.price_history.get(product_id, [])
        if len(history) < 2:
            return {'trend': 'insufficient_data', 'volatility': 0, 'recommendation': 'monitor'}
        
        prices = [record['price'] for record in history]
        
        # 트렌드 계산
        if len(prices) >= 7:  # 최소 7일 데이터
            recent_avg = np.mean(prices[-7:])
            older_avg = np.mean(prices[:-7]) if len(prices) > 7 else prices[0]
            
            trend_change = (recent_avg - older_avg) / older_avg * 100
            
            if trend_change > 5:
                trend = 'increasing'
            elif trend_change < -5:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        # 변동성 계산
        volatility = np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0
        
        # 추천사항
        if trend == 'decreasing':
            recommendation = 'wait_for_lower_price'
        elif trend == 'increasing' and volatility < 0.1:
            recommendation = 'buy_now'
        else:
            recommendation = 'monitor'
        
        return {
            'trend': trend,
            'volatility': volatility,
            'recommendation': recommendation
        }
    
    def set_price_alert(self, product_id: str, target_price: float, alert_type: str = 'below'):
        """가격 알림 설정"""
        
        self.price_alerts[product_id] = {
            'target_price': target_price,
            'alert_type': alert_type,  # 'below', 'above'
            'created_at': datetime.now().isoformat(),
            'active': True
        }
        
        self.logger.info(f"가격 알림 설정: {product_id} - {target_price} ({alert_type})")
    
    def check_price_alerts(self, product_id: str, current_price: float) -> List[Dict]:
        """가격 알림 확인"""
        
        alerts_triggered = []
        alert = self.price_alerts.get(product_id)
        
        if alert and alert['active']:
            should_trigger = False
            
            if alert['alert_type'] == 'below' and current_price <= alert['target_price']:
                should_trigger = True
            elif alert['alert_type'] == 'above' and current_price >= alert['target_price']:
                should_trigger = True
            
            if should_trigger:
                alerts_triggered.append({
                    'product_id': product_id,
                    'current_price': current_price,
                    'target_price': alert['target_price'],
                    'alert_type': alert['alert_type'],
                    'triggered_at': datetime.now().isoformat()
                })
                
                # 알림 비활성화 (중복 방지)
                alert['active'] = False
        
        return alerts_triggered


class StockMonitor:
    """재고 모니터링 시스템"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stock_data = {}
    
    def update_stock_level(self, product_id: str, stock_level: int) -> Dict[str, Any]:
        """재고 수준 업데이트"""
        
        timestamp = datetime.now()
        
        previous_level = self.stock_data.get(product_id, {}).get('current_level', 0)
        
        self.stock_data[product_id] = {
            'current_level': stock_level,
            'previous_level': previous_level,
            'last_updated': timestamp.isoformat(),
            'trend': self._calculate_stock_trend(previous_level, stock_level)
        }
        
        # 재고 부족 경고
        alert_level = self._get_stock_alert_level(stock_level)
        
        return {
            'product_id': product_id,
            'current_stock': stock_level,
            'stock_trend': self.stock_data[product_id]['trend'],
            'alert_level': alert_level,
            'recommendation': self._get_stock_recommendation(stock_level, alert_level)
        }
    
    def _calculate_stock_trend(self, previous: int, current: int) -> str:
        """재고 트렌드 계산"""
        if previous == 0:
            return 'new'
        
        change_ratio = (current - previous) / previous
        
        if change_ratio > 0.2:
            return 'increasing'
        elif change_ratio < -0.2:
            return 'decreasing'
        else:
            return 'stable'
    
    def _get_stock_alert_level(self, stock_level: int) -> str:
        """재고 경고 레벨"""
        if stock_level == 0:
            return 'out_of_stock'
        elif stock_level < 10:
            return 'critical'
        elif stock_level < 50:
            return 'low'
        else:
            return 'normal'
    
    def _get_stock_recommendation(self, stock_level: int, alert_level: str) -> str:
        """재고 기반 추천사항"""
        recommendations = {
            'out_of_stock': 'remove_from_promotion',
            'critical': 'limited_time_promotion',
            'low': 'moderate_promotion', 
            'normal': 'full_promotion'
        }
        
        return recommendations.get(alert_level, 'monitor')


class RevenuePredictor:
    """수익 예측 시스템"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.market_analyzer = MarketAnalyzer()
        self.price_tracker = PriceTracker()
        self.stock_monitor = StockMonitor()
        
        # 예측 모델 파라미터
        self.model_params = {
            'base_ctr': 0.05,  # 기본 클릭률
            'base_conversion': 0.02,  # 기본 전환율
            'influence_decay': 0.1,  # 영향력 감소율
            'market_volatility': 0.15  # 시장 변동성
        }
    
    def predict_revenue(
        self,
        channel_score: float,
        category: MarketCategory,
        product_price: float,
        commission_rate: float,
        estimated_reach: int,
        collaboration_cost: float = 0,
        channel_demographics: Dict[str, float] = None
    ) -> RevenueMetrics:
        """종합 수익 예측"""
        
        try:
            # 시장 기회 분석
            market_opportunity = self.market_analyzer.analyze_market_opportunity(
                category, channel_demographics
            )
            
            # 기본 전환율 계산
            base_conversion = market_opportunity.get('base_conversion_rate', 0.02)
            seasonal_multiplier = market_opportunity.get('seasonal_multiplier', 1.0)
            demographic_match = market_opportunity.get('demographic_match_score', 1.0)
            
            # 채널 점수 기반 전환율 조정
            score_multiplier = 1 + (channel_score - 50) / 100
            
            # 최종 전환율
            final_conversion_rate = (
                base_conversion * 
                seasonal_multiplier * 
                demographic_match * 
                score_multiplier
            )
            
            # 예상 전환수
            predicted_conversions = int(estimated_reach * final_conversion_rate)
            
            # 예상 수익
            predicted_revenue = predicted_conversions * product_price * commission_rate
            
            # ROI 계산
            roi_percentage = 0
            if collaboration_cost > 0:
                roi_percentage = ((predicted_revenue - collaboration_cost) / collaboration_cost) * 100
            
            # 회수 기간
            payback_period_days = 30  # 기본 30일
            if predicted_revenue > 0:
                daily_revenue = predicted_revenue / 30
                if daily_revenue > 0:
                    payback_period_days = min(collaboration_cost / daily_revenue, 365)
            
            # 신뢰도 점수
            confidence_score = self._calculate_confidence(
                channel_score, market_opportunity, estimated_reach
            )
            
            # 위험 요소 분석
            risk_factors = self._analyze_risk_factors(
                market_opportunity, product_price, predicted_conversions
            )
            
            # 최적화 제안
            optimization_suggestions = self._generate_optimization_suggestions(
                final_conversion_rate, roi_percentage, risk_factors
            )
            
            return RevenueMetrics(
                predicted_revenue=predicted_revenue,
                predicted_conversions=predicted_conversions,
                roi_percentage=roi_percentage,
                payback_period_days=int(payback_period_days),
                confidence_score=confidence_score,
                risk_factors=risk_factors,
                optimization_suggestions=optimization_suggestions
            )
            
        except Exception as e:
            self.logger.error(f"수익 예측 오류: {str(e)}")
            return self._get_default_metrics()
    
    def _calculate_confidence(
        self, 
        channel_score: float, 
        market_opportunity: Dict, 
        estimated_reach: int
    ) -> float:
        """예측 신뢰도 계산"""
        
        confidence_factors = []
        
        # 채널 점수 기반 신뢰도
        if channel_score >= 70:
            confidence_factors.append(0.9)
        elif channel_score >= 50:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)
        
        # 시장 데이터 품질
        if market_opportunity.get('demographic_match_score', 0) > 0.7:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.6)
        
        # 데이터 규모
        if estimated_reach > 10000:
            confidence_factors.append(0.8)
        elif estimated_reach > 1000:
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.4)
        
        return np.mean(confidence_factors)
    
    def _analyze_risk_factors(
        self, 
        market_opportunity: Dict, 
        product_price: float, 
        predicted_conversions: int
    ) -> List[str]:
        """위험 요소 분석"""
        
        risk_factors = []
        
        # 시장 경쟁도
        competition_level = market_opportunity.get('competition_level', 0.5)
        if competition_level > 0.8:
            risk_factors.append("고경쟁 시장으로 인한 전환율 하락 위험")
        
        # 가격 민감도
        if product_price > 100000:  # 10만원 이상 고가상품
            risk_factors.append("고가 상품으로 인한 구매 저항 위험")
        
        # 예상 전환수
        if predicted_conversions < 5:
            risk_factors.append("낮은 예상 전환수로 인한 수익 불확실성")
        
        # 계절적 요인
        seasonal_multiplier = market_opportunity.get('seasonal_multiplier', 1.0)
        if seasonal_multiplier < 0.9:
            risk_factors.append("비수기로 인한 성과 하락 위험")
        
        return risk_factors
    
    def _generate_optimization_suggestions(
        self, 
        conversion_rate: float, 
        roi_percentage: float, 
        risk_factors: List[str]
    ) -> List[str]:
        """최적화 제안 생성"""
        
        suggestions = []
        
        # 전환율 개선
        if conversion_rate < 0.02:
            suggestions.append("타겟팅 정확도 향상을 통한 전환율 개선")
            suggestions.append("콘텐츠 품질 향상으로 설득력 증대")
        
        # ROI 개선
        if roi_percentage < 100:
            suggestions.append("협업 비용 최적화 검토")
            suggestions.append("커미션율 협상을 통한 수익성 개선")
        
        # 위험 요소별 대응
        if "고경쟁 시장" in str(risk_factors):
            suggestions.append("차별화된 메시지로 경쟁 우위 확보")
        
        if "고가 상품" in str(risk_factors):
            suggestions.append("분할 결제나 할인 혜택으로 구매 장벽 완화")
        
        if "낮은 예상 전환수" in str(risk_factors):
            suggestions.append("도달 범위 확대를 통한 노출 증대")
        
        return suggestions
    
    def _get_default_metrics(self) -> RevenueMetrics:
        """기본 지표 반환 (오류 시)"""
        return RevenueMetrics(
            predicted_revenue=0.0,
            predicted_conversions=0,
            roi_percentage=0.0,
            payback_period_days=365,
            confidence_score=0.1,
            risk_factors=["예측 모델 오류"],
            optimization_suggestions=["데이터 품질 개선 필요"]
        )
    
    def batch_predict_revenue(
        self, 
        predictions_data: List[Dict[str, Any]]
    ) -> List[RevenueMetrics]:
        """배치 수익 예측"""
        
        results = []
        
        for data in predictions_data:
            try:
                metrics = self.predict_revenue(
                    channel_score=data.get('channel_score', 50),
                    category=MarketCategory(data.get('category', 'lifestyle')),
                    product_price=data.get('product_price', 50000),
                    commission_rate=data.get('commission_rate', 0.05),
                    estimated_reach=data.get('estimated_reach', 1000),
                    collaboration_cost=data.get('collaboration_cost', 0),
                    channel_demographics=data.get('channel_demographics')
                )
                results.append(metrics)
                
            except Exception as e:
                self.logger.error(f"배치 예측 오류: {str(e)}")
                results.append(self._get_default_metrics())
        
        return results
    
    def generate_revenue_report(
        self, 
        revenue_metrics: List[RevenueMetrics]
    ) -> Dict[str, Any]:
        """수익 리포트 생성"""
        
        if not revenue_metrics:
            return {'error': 'No data provided'}
        
        total_predicted_revenue = sum(m.predicted_revenue for m in revenue_metrics)
        total_predicted_conversions = sum(m.predicted_conversions for m in revenue_metrics)
        avg_roi = np.mean([m.roi_percentage for m in revenue_metrics])
        avg_confidence = np.mean([m.confidence_score for m in revenue_metrics])
        
        # 위험 요소 집계
        all_risk_factors = []
        for metrics in revenue_metrics:
            all_risk_factors.extend(metrics.risk_factors)
        
        risk_frequency = {}
        for risk in all_risk_factors:
            risk_frequency[risk] = risk_frequency.get(risk, 0) + 1
        
        # 상위 위험 요소
        top_risks = sorted(risk_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'summary': {
                'total_campaigns': len(revenue_metrics),
                'total_predicted_revenue': total_predicted_revenue,
                'total_predicted_conversions': total_predicted_conversions,
                'average_roi_percentage': avg_roi,
                'average_confidence_score': avg_confidence
            },
            'performance_distribution': {
                'high_roi_campaigns': len([m for m in revenue_metrics if m.roi_percentage > 200]),
                'medium_roi_campaigns': len([m for m in revenue_metrics if 100 <= m.roi_percentage <= 200]),
                'low_roi_campaigns': len([m for m in revenue_metrics if m.roi_percentage < 100])
            },
            'risk_analysis': {
                'top_risk_factors': top_risks,
                'high_risk_campaigns': len([m for m in revenue_metrics if len(m.risk_factors) > 2])
            },
            'recommendations': self._generate_portfolio_recommendations(revenue_metrics)
        }
    
    def _generate_portfolio_recommendations(self, metrics: List[RevenueMetrics]) -> List[str]:
        """포트폴리오 추천사항 생성"""
        
        recommendations = []
        
        # ROI 분포 분석
        high_roi_ratio = len([m for m in metrics if m.roi_percentage > 200]) / len(metrics)
        if high_roi_ratio < 0.3:
            recommendations.append("고수익 캠페인 비율 증대 필요")
        
        # 신뢰도 분석
        avg_confidence = np.mean([m.confidence_score for m in metrics])
        if avg_confidence < 0.7:
            recommendations.append("예측 정확도 향상을 위한 데이터 품질 개선")
        
        # 위험 분산
        high_risk_ratio = len([m for m in metrics if len(m.risk_factors) > 2]) / len(metrics)
        if high_risk_ratio > 0.5:
            recommendations.append("위험 분산을 위한 포트폴리오 다각화")
        
        return recommendations