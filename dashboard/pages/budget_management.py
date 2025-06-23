"""
Budget Management Dashboard
예산 관리 대시보드

실시간 예산 모니터링, 임계값 알림, 비용 예측 및 최적화 권장사항을 제공하는 대시보드
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
from datetime import datetime, timedelta
import json

from src.api.budget_controller import get_budget_controller, BudgetThreshold
from src.api.api_limiter import get_api_limiter
from src.api.service_controller import get_service_controller, ServicePriority
from src.api.cost_optimizer import get_cost_optimizer
from src.api.usage_tracker import get_tracker

# 페이지 설정
st.set_page_config(
    page_title="예산 관리",
    page_icon="💰",
    layout="wide"
)

st.title("💰 예산 관리 대시보드")
st.markdown("실시간 예산 모니터링 및 비용 제어 시스템")

# 세션 상태 초기화
if 'budget_data_cache' not in st.session_state:
    st.session_state.budget_data_cache = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = None

# 컨트롤러 인스턴스
budget_controller = get_budget_controller()
api_limiter = get_api_limiter()
service_controller = get_service_controller()
cost_optimizer = get_cost_optimizer()
usage_tracker = get_tracker()

@st.cache_data(ttl=60)  # 1분 캐시
def get_budget_status():
    """예산 상태 조회 (캐시됨)"""
    return asyncio.run(budget_controller.check_budget_status())

@st.cache_data(ttl=300)  # 5분 캐시
def get_cost_prediction():
    """비용 예측 조회 (캐시됨)"""
    return asyncio.run(cost_optimizer.predict_monthly_cost())

@st.cache_data(ttl=300)  # 5분 캐시
def get_optimization_recommendations(prediction_data):
    """최적화 권장사항 조회 (캐시됨)"""
    # prediction_data를 다시 객체로 변환
    from src.api.cost_optimizer import CostPrediction
    prediction = CostPrediction(**prediction_data)
    return asyncio.run(cost_optimizer.generate_optimization_recommendations(prediction))

# 자동 새로고침 토글
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    auto_refresh = st.checkbox("자동 새로고침 (30초)", value=True)
with col2:
    if st.button("🔄 수동 새로고침"):
        st.cache_data.clear()
        st.rerun()
with col3:
    emergency_mode = st.button("🚨 긴급 모드", type="secondary")

# 긴급 모드 처리
if emergency_mode:
    api_limiter.set_emergency_bypass(True)
    st.success("긴급 우회 모드가 활성화되었습니다!")
    st.rerun()

# 자동 새로고침
if auto_refresh:
    if (st.session_state.last_update is None or 
        (datetime.now() - st.session_state.last_update).total_seconds() > 30):
        st.session_state.last_update = datetime.now()
        st.rerun()

try:
    # 예산 상태 조회
    budget_status = get_budget_status()
    
    # 메인 지표 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="현재 사용률",
            value=f"{budget_status.usage_rate:.1%}",
            delta=f"₩{budget_status.current_spend:,.0f} / ₩{budget_status.total_budget:,.0f}"
        )
    
    with col2:
        st.metric(
            label="월말 예상 비용",
            value=f"₩{budget_status.predicted_monthly_spend:,.0f}",
            delta=f"₩{budget_status.predicted_monthly_spend - budget_status.total_budget:,.0f}" if budget_status.predicted_monthly_spend > budget_status.total_budget else None
        )
    
    with col3:
        st.metric(
            label="남은 일수",
            value=f"{budget_status.days_remaining}일",
            delta=f"일평균: ₩{budget_status.daily_average:,.0f}"
        )
    
    with col4:
        # 임계값 상태
        if budget_status.threshold_status:
            threshold_color = {
                BudgetThreshold.WARNING_70: "🟡",
                BudgetThreshold.ALERT_80: "🟠", 
                BudgetThreshold.CRITICAL_90: "🔴",
                BudgetThreshold.EMERGENCY_95: "🚨",
                BudgetThreshold.STOP_100: "⛔"
            }
            status_text = f"{threshold_color.get(budget_status.threshold_status, '🟢')} {budget_status.threshold_status.name}"
        else:
            status_text = "🟢 정상"
        
        st.metric(
            label="임계값 상태",
            value=status_text
        )
    
    # 예산 사용률 게이지 차트
    st.subheader("📊 예산 사용률")
    
    # 게이지 차트 생성
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = budget_status.usage_rate * 100,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "예산 사용률 (%)"},
        delta = {'reference': 80},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 70], 'color': "lightgray"},
                {'range': [70, 80], 'color': "yellow"},
                {'range': [80, 90], 'color': "orange"},
                {'range': [90, 95], 'color': "red"},
                {'range': [95, 100], 'color': "darkred"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 95
            }
        }
    ))
    
    fig_gauge.update_layout(height=300)
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    # 탭으로 구분된 상세 정보
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 비용 예측", "🔧 최적화 권장사항", "🚦 서비스 상태", "📊 API 사용량", "📋 알림 이력"
    ])
    
    with tab1:
        st.subheader("💡 월말 비용 예측")
        
        # 비용 예측 조회
        prediction = get_cost_prediction()
        prediction_data = prediction.__dict__  # 직렬화를 위해 딕셔너리로 변환
        
        # 예측 정보 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="예측 월말 비용",
                value=f"₩{prediction.predicted_monthly_cost:,.0f}",
                delta=f"신뢰도: {prediction.confidence_score:.1%}"
            )
        
        with col2:
            st.metric(
                label="예측 방법",
                value=prediction.prediction_method.replace('_', ' ').title(),
                delta=f"위험도: {prediction.risk_level.upper()}"
            )
        
        with col3:
            if prediction.predicted_monthly_cost > budget_status.total_budget:
                over_amount = prediction.predicted_monthly_cost - budget_status.total_budget
                st.error(f"⚠️ 예산 초과 예상: ₩{over_amount:,.0f}")
            else:
                remaining = budget_status.total_budget - prediction.predicted_monthly_cost
                st.success(f"✅ 예산 내 운영: ₩{remaining:,.0f} 여유")
        
        # 일별 트렌드 차트
        if prediction.daily_trend:
            st.subheader("📈 일별 예상 비용 트렌드")
            
            days = list(range(1, len(prediction.daily_trend) + 1))
            df_trend = pd.DataFrame({
                'Day': days,
                'Predicted_Cost': prediction.daily_trend,
                'Cumulative': pd.Series(prediction.daily_trend).cumsum()
            })
            
            fig_trend = make_subplots(
                rows=2, cols=1,
                subplot_titles=('일별 예상 비용', '누적 비용'),
                vertical_spacing=0.1
            )
            
            # 일별 비용
            fig_trend.add_trace(
                go.Scatter(x=df_trend['Day'], y=df_trend['Predicted_Cost'], 
                          mode='lines+markers', name='일별 비용'),
                row=1, col=1
            )
            
            # 누적 비용
            fig_trend.add_trace(
                go.Scatter(x=df_trend['Day'], y=df_trend['Cumulative'], 
                          mode='lines', name='누적 비용', fill='tonexty'),
                row=2, col=1
            )
            
            # 예산 라인
            fig_trend.add_hline(y=budget_status.total_budget, line_dash="dash", 
                               line_color="red", annotation_text="월 예산 한도",
                               row=2, col=1)
            
            fig_trend.update_layout(height=500, showlegend=False)
            fig_trend.update_xaxes(title_text="일", row=2, col=1)
            fig_trend.update_yaxes(title_text="비용 (원)", row=1, col=1)
            fig_trend.update_yaxes(title_text="누적 비용 (원)", row=2, col=1)
            
            st.plotly_chart(fig_trend, use_container_width=True)
        
        # API별 예상 비용
        if prediction.api_breakdown:
            st.subheader("🔍 API별 예상 비용")
            
            api_df = pd.DataFrame([
                {'API': api_name, 'Cost': cost}
                for api_name, cost in prediction.api_breakdown.items()
            ])
            
            fig_api = px.pie(api_df, values='Cost', names='API', 
                           title="API별 비용 분배")
            st.plotly_chart(fig_api, use_container_width=True)
            
            # 상세 테이블
            api_df['Percentage'] = (api_df['Cost'] / api_df['Cost'].sum() * 100).round(1)
            api_df['Cost'] = api_df['Cost'].apply(lambda x: f"₩{x:,.0f}")
            api_df['Percentage'] = api_df['Percentage'].apply(lambda x: f"{x}%")
            
            st.dataframe(api_df, use_container_width=True)
    
    with tab2:
        st.subheader("🔧 비용 최적화 권장사항")
        
        # 최적화 권장사항 조회
        try:
            recommendations = get_optimization_recommendations(prediction_data)
            
            if recommendations:
                for i, rec in enumerate(recommendations):
                    # 우선순위별 색상
                    priority_colors = {
                        "high": "🔴",
                        "medium": "🟡", 
                        "low": "🟢"
                    }
                    
                    priority_icon = priority_colors.get(rec.priority, "⚪")
                    
                    with st.expander(f"{priority_icon} [{rec.category}] {rec.title}"):
                        st.write(f"**설명:** {rec.description}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("예상 절약액", f"₩{rec.potential_savings:,.0f}")
                        with col2:
                            st.metric("구현 난이도", rec.implementation_effort)
                        
                        st.write("**액션 아이템:**")
                        for action in rec.action_items:
                            st.write(f"• {action}")
            else:
                st.info("현재 추가 최적화 권장사항이 없습니다.")
        
        except Exception as e:
            st.error(f"최적화 권장사항 로드 실패: {e}")
    
    with tab3:
        st.subheader("🚦 서비스 상태 관리")
        
        # 서비스 상태 조회
        all_services = service_controller.get_all_services_status()
        
        # 우선순위별 그룹화
        priority_groups = {
            'essential': [],
            'important': [],
            'optional': []
        }
        
        for service_name, service_info in all_services.items():
            priority = service_info['priority']
            priority_groups[priority].append((service_name, service_info))
        
        # 우선순위별 표시
        for priority, services in priority_groups.items():
            if services:
                priority_icons = {
                    'essential': '🔥',
                    'important': '⚡',
                    'optional': '🔧'
                }
                
                st.write(f"### {priority_icons[priority]} {priority.title()} 서비스")
                
                for service_name, service_info in services:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
                    
                    with col1:
                        status_icons = {
                            'running': '🟢',
                            'stopped': '🔴',
                            'stopping': '🟡',
                            'starting': '🟡',
                            'error': '⚠️'
                        }
                        
                        icon = status_icons.get(service_info['status'], '⚪')
                        st.write(f"{icon} **{service_name}**")
                        st.caption(service_info['description'])
                    
                    with col2:
                        st.write(f"**상태:** {service_info['status']}")
                    
                    with col3:
                        if service_info['error_message']:
                            st.error("에러 발생")
                        elif service_info['is_stopped']:
                            st.warning("중단됨")
                        else:
                            st.success("정상")
                    
                    with col4:
                        if service_info['is_stopped']:
                            if st.button(f"시작", key=f"start_{service_name}"):
                                asyncio.run(service_controller._start_service(service_name))
                                st.rerun()
                        else:
                            if st.button(f"중단", key=f"stop_{service_name}"):
                                asyncio.run(service_controller._stop_service(service_name, "manual_stop"))
                                st.rerun()
        
        # 전체 제어 버튼
        st.write("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🚨 긴급 중단 (필수 서비스만 유지)"):
                asyncio.run(service_controller.emergency_stop_all_non_essential())
                st.warning("긴급 중단이 실행되었습니다!")
                st.rerun()
        
        with col2:
            if st.button("♻️ 모든 서비스 복구"):
                asyncio.run(service_controller.restore_all_services())
                st.success("모든 서비스 복구가 시작되었습니다!")
                st.rerun()
        
        with col3:
            if st.button("🔄 상태 새로고침"):
                st.rerun()
    
    with tab4:
        st.subheader("📊 API 사용량 및 제한 상태")
        
        # API 상태 조회
        api_status = api_limiter.get_all_api_status()
        
        # API 상태 표시
        for api_name, status in api_status.items():
            with st.expander(f"🔌 {api_name.upper()} API"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # 제한 상태
                    if status['is_limited']:
                        st.error("🚫 제한됨")
                    elif status['total_block']:
                        st.error("🚫 전체 차단")
                    elif status['emergency_bypass']:
                        st.warning("🚨 긴급 우회")
                    else:
                        st.success("✅ 정상")
                
                with col2:
                    # 회로 차단기 상태
                    circuit_icons = {
                        'closed': '🟢',
                        'open': '🔴',
                        'half_open': '🟡'
                    }
                    circuit_icon = circuit_icons.get(status['circuit_state'], '⚪')
                    st.write(f"**회로 상태:** {circuit_icon} {status['circuit_state']}")
                
                with col3:
                    # 실패/성공 카운트
                    st.write(f"**실패:** {status['failure_count']}")
                    st.write(f"**성공:** {status['success_count']}")
                
                # Rate Limit 정보
                if status['rate_limit_info']:
                    rate_info = status['rate_limit_info']
                    
                    st.write("**Rate Limit 사용량:**")
                    
                    # 분당 사용률
                    minute_usage = rate_info['calls_last_minute'] / rate_info['limits']['per_minute']
                    st.progress(minute_usage, text=f"분당: {rate_info['calls_last_minute']}/{rate_info['limits']['per_minute']}")
                    
                    # 시간당 사용률
                    hour_usage = rate_info['calls_last_hour'] / rate_info['limits']['per_hour']
                    st.progress(hour_usage, text=f"시간당: {rate_info['calls_last_hour']}/{rate_info['limits']['per_hour']}")
                    
                    # 일당 사용률
                    day_usage = rate_info['calls_today'] / rate_info['limits']['per_day']
                    st.progress(day_usage, text=f"일당: {rate_info['calls_today']}/{rate_info['limits']['per_day']}")
        
        # API 제한 제어
        st.write("---")
        st.write("**API 제한 제어**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_api = st.selectbox("API 선택", ['gemini', 'coupang', 'whisper'])
            
            if st.button(f"{selected_api} API 제한"):
                api_limiter.limit_api_calls(selected_api)
                st.warning(f"{selected_api} API가 제한되었습니다!")
                st.rerun()
        
        with col2:
            if st.button("모든 API 제한 해제"):
                api_limiter.remove_api_limit()
                st.success("모든 API 제한이 해제되었습니다!")
                st.rerun()
    
    with tab5:
        st.subheader("📋 알림 이력")
        
        # 알림 이력 조회
        alert_history = budget_controller.get_alert_history(days=7)
        
        if alert_history:
            # 알림 이력 테이블
            df_alerts = pd.DataFrame(alert_history)
            
            # 시간 형식 변환
            df_alerts['timestamp'] = pd.to_datetime(df_alerts['timestamp'])
            df_alerts['date'] = df_alerts['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
            
            # 임계값별 색상 매핑
            def get_threshold_color(threshold):
                colors = {
                    'WARNING_70': '🟡',
                    'ALERT_80': '🟠',
                    'CRITICAL_90': '🔴',
                    'EMERGENCY_95': '🚨',
                    'STOP_100': '⛔'
                }
                return colors.get(threshold, '⚪')
            
            df_alerts['threshold_icon'] = df_alerts['threshold'].apply(get_threshold_color)
            df_alerts['usage_rate_pct'] = (df_alerts['usage_rate'] * 100).round(1)
            df_alerts['current_spend_fmt'] = df_alerts['current_spend'].apply(lambda x: f"₩{x:,.0f}")
            df_alerts['predicted_spend_fmt'] = df_alerts['predicted_spend'].apply(lambda x: f"₩{x:,.0f}")
            
            # 표시할 컬럼 선택
            display_df = df_alerts[[
                'date', 'threshold_icon', 'threshold', 'usage_rate_pct', 
                'current_spend_fmt', 'predicted_spend_fmt', 'message'
            ]].copy()
            
            display_df.columns = [
                '시간', '🚨', '임계값', '사용률(%)', '현재 비용', '예상 비용', '메시지'
            ]
            
            st.dataframe(display_df, use_container_width=True)
            
            # 알림 통계
            st.write("### 📈 알림 통계 (최근 7일)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("총 알림 수", len(alert_history))
            
            with col2:
                critical_alerts = len([a for a in alert_history if a['threshold'] in ['EMERGENCY_95', 'STOP_100']])
                st.metric("중요 알림", critical_alerts)
            
            with col3:
                if alert_history:
                    latest_alert = alert_history[0]
                    hours_ago = (datetime.now() - datetime.fromisoformat(latest_alert['timestamp'])).total_seconds() / 3600
                    st.metric("마지막 알림", f"{hours_ago:.1f}시간 전")
        
        else:
            st.info("최근 7일간 알림 이력이 없습니다.")

except Exception as e:
    st.error(f"대시보드 로드 중 오류가 발생했습니다: {e}")
    st.write("상세 오류 정보:")
    st.exception(e)

# 푸터
st.write("---")
st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """메인 함수 - 다른 모듈에서 import하여 사용"""
    # 위의 모든 코드가 이미 실행되므로 별도 작업 불필요
    pass

if __name__ == "__main__":
    main()