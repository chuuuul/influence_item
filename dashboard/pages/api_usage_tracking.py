"""
API Usage and Cost Tracking Dashboard Page

PRD 섹션 6.2에 명시된 API 비용 구조를 실시간으로 모니터링하는 대시보드
- Google Gemini 2.5 Flash API 사용량 추적
- Coupang Partners API 호출 횟수 모니터링 
- 월간 비용 예측 및 예산 관리
- 실시간 사용량 차트 및 통계
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# 프로젝트 루트 경로를 Python path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

try:
    from src.api.usage_tracker import get_tracker, APIUsageTracker
except ImportError:
    st.error("API Usage Tracker 모듈을 불러올 수 없습니다. 경로를 확인하세요.")
    st.stop()


def format_currency(amount: float) -> str:
    """원화 형식으로 포맷팅"""
    return f"₩{amount:,.0f}"


def format_number(number: int) -> str:
    """숫자 천단위 구분자 포맷팅"""
    return f"{number:,}"


def create_usage_metrics():
    """상단 메트릭 카드들 생성"""
    tracker = get_tracker()
    
    # 30일 요약 데이터
    summary = tracker.get_usage_summary(days=30)
    projection = tracker.get_monthly_projection()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "월간 예상 비용",
            format_currency(projection['projected_monthly_cost']),
            delta=f"예산 대비 {(projection['projected_monthly_cost'] - 15000):+,.0f}원" if projection['projected_monthly_cost'] > 0 else None,
            delta_color="inverse" if projection['projected_monthly_cost'] > 15000 else "normal"
        )
    
    with col2:
        st.metric(
            "30일 총 호출",
            format_number(summary['total_calls']),
            delta=f"일평균 {summary['total_calls'] // 30}"
        )
    
    with col3:
        st.metric(
            "30일 총 비용",
            format_currency(summary['total_cost_krw']),
            delta=f"일평균 ₩{summary['total_cost_krw'] / 30:.2f}"
        )
    
    with col4:
        budget_usage = (projection['projected_monthly_cost'] / 15000) * 100
        st.metric(
            "예산 사용률",
            f"{budget_usage:.1f}%",
            delta=f"{budget_usage - 100:+.1f}%p" if budget_usage > 100 else f"{100 - budget_usage:.1f}%p 여유",
            delta_color="inverse" if budget_usage > 100 else "normal"
        )


def create_api_breakdown_chart(summary):
    """API별 사용량 분석 차트"""
    if not summary['api_breakdown']:
        st.info("아직 API 사용 데이터가 없습니다.")
        return
    
    df = pd.DataFrame(summary['api_breakdown'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("API별 비용 분포")
        fig_cost = px.pie(
            df, 
            values='total_cost', 
            names='api_name',
            title="30일 API 비용 분포",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_cost.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_cost, use_container_width=True)
    
    with col2:
        st.subheader("API별 호출 횟수")
        fig_calls = px.bar(
            df, 
            x='api_name', 
            y='total_calls',
            title="30일 API 호출 횟수",
            color='total_calls',
            color_continuous_scale='Blues'
        )
        fig_calls.update_layout(showlegend=False)
        st.plotly_chart(fig_calls, use_container_width=True)


def create_daily_usage_trend(summary):
    """일별 사용량 트렌드 차트"""
    st.subheader("일별 사용량 추이")
    
    if not summary['daily_usage']:
        st.info("일별 사용량 데이터가 없습니다.")
        return
    
    # 일별 데이터를 DataFrame으로 변환
    daily_data = []
    for date, apis in summary['daily_usage'].items():
        total_cost = sum(api_data['cost'] for api_data in apis.values())
        total_calls = sum(api_data['calls'] for api_data in apis.values())
        
        daily_data.append({
            'date': date,
            'total_cost': total_cost,
            'total_calls': total_calls
        })
        
        # API별 세부 데이터
        for api_name, api_data in apis.items():
            daily_data.append({
                'date': date,
                'api_name': api_name,
                'cost': api_data['cost'],
                'calls': api_data['calls']
            })
    
    if not daily_data:
        st.info("표시할 데이터가 없습니다.")
        return
    
    # 전체 일별 트렌드
    df_daily_total = pd.DataFrame([d for d in daily_data if 'total_cost' in d])
    df_daily_total['date'] = pd.to_datetime(df_daily_total['date'])
    df_daily_total = df_daily_total.sort_values('date')
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_cost_trend = px.line(
            df_daily_total,
            x='date',
            y='total_cost',
            title="일별 총 비용 추이",
            markers=True
        )
        fig_cost_trend.update_traces(line_color='#FF6B6B')
        fig_cost_trend.update_layout(yaxis_title="비용 (₩)")
        st.plotly_chart(fig_cost_trend, use_container_width=True)
    
    with col2:
        fig_calls_trend = px.line(
            df_daily_total,
            x='date',
            y='total_calls',
            title="일별 총 호출 수 추이",
            markers=True
        )
        fig_calls_trend.update_traces(line_color='#4ECDC4')
        fig_calls_trend.update_layout(yaxis_title="호출 수")
        st.plotly_chart(fig_calls_trend, use_container_width=True)


def create_detailed_table(summary):
    """상세 API 사용량 테이블"""
    st.subheader("API별 상세 사용량")
    
    if not summary['api_breakdown']:
        st.info("상세 데이터가 없습니다.")
        return
    
    df = pd.DataFrame(summary['api_breakdown'])
    
    # 컬럼 형식 변경
    df['total_cost_formatted'] = df['total_cost'].apply(format_currency)
    df['total_calls_formatted'] = df['total_calls'].apply(format_number)
    df['total_tokens_formatted'] = df['total_tokens'].apply(format_number)
    df['avg_response_time'] = df['avg_response_time'].round(2)
    df['error_rate'] = (df['error_count'] / df['total_calls'] * 100).round(2)
    
    # 표시할 컬럼 선택
    display_columns = {
        'api_name': 'API 이름',
        'total_calls_formatted': '총 호출 수',
        'total_tokens_formatted': '총 토큰 수',
        'total_cost_formatted': '총 비용',
        'avg_response_time': '평균 응답시간 (ms)',
        'error_count': '에러 수',
        'error_rate': '에러율 (%)'
    }
    
    df_display = df[list(display_columns.keys())].rename(columns=display_columns)
    
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )


def create_budget_analysis():
    """예산 분석 섹션"""
    st.subheader("예산 분석")
    
    tracker = get_tracker()
    projection = tracker.get_monthly_projection()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 예산 대비 현재 상태 게이지 차트
        current_usage = projection['projected_monthly_cost']
        budget = 15000
        usage_percentage = min((current_usage / budget) * 100, 150)  # 최대 150%까지 표시
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = usage_percentage,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "월간 예산 사용률 (%)"},
            delta = {'reference': 100, 'suffix': "%"},
            gauge = {
                'axis': {'range': [None, 150]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "yellow"},
                    {'range': [80, 100], 'color': "orange"},
                    {'range': [100, 150], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ))
        
        fig_gauge.update_layout(height=300)
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col2:
        st.write("**예산 정보**")
        st.write(f"• 월 예산: {format_currency(budget)}")
        st.write(f"• 예상 사용: {format_currency(current_usage)}")
        st.write(f"• 잔여 예산: {format_currency(max(0, budget - current_usage))}")
        
        if projection['warning']:
            st.error(f"⚠️ {projection['warning']}")
        else:
            st.success("✅ 예산 내에서 운영 중")
        
        # PRD 기준 정보
        st.write("**PRD 기준 비용**")
        st.write("• Gemini API: ~₩700/월")
        st.write("• Coupang API: 무료")
        st.write("• Whisper: 무료 (오픈소스)")


def create_real_time_monitoring():
    """실시간 모니터링 섹션"""
    st.subheader("실시간 모니터링")
    
    # 자동 새로고침 옵션
    auto_refresh = st.checkbox("자동 새로고침 (30초)", value=False)
    
    if auto_refresh:
        # 30초마다 자동 새로고침
        st.rerun()
    
    # 최근 24시간 데이터
    tracker = get_tracker()
    recent_summary = tracker.get_usage_summary(days=1)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "오늘 호출 수",
            format_number(recent_summary['total_calls']),
            delta=f"어제 대비 데이터 필요"  # TODO: 전날 비교 데이터 추가
        )
    
    with col2:
        st.metric(
            "오늘 비용",
            format_currency(recent_summary['total_cost_krw']),
            delta=f"일평균 대비"
        )
    
    with col3:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.metric(
            "마지막 업데이트",
            current_time,
            delta="실시간"
        )


def main():
    """메인 대시보드 함수"""
    st.set_page_config(
        page_title="API 사용량 추적",
        page_icon="💰",
        layout="wide"
    )
    
    st.title("💰 API 사용량 및 비용 추적")
    st.markdown("---")
    
    # 필터 옵션
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("**PRD 기반 API 비용 모니터링 대시보드**")
    with col2:
        period = st.selectbox(
            "조회 기간",
            options=[7, 14, 30, 60, 90],
            index=2,  # 기본값: 30일
            format_func=lambda x: f"{x}일"
        )
    with col3:
        if st.button("🔄 새로고침", type="primary"):
            st.rerun()
    
    # 메트릭 카드
    create_usage_metrics()
    
    st.markdown("---")
    
    # 추적기 초기화 및 데이터 로드
    try:
        tracker = get_tracker()
        summary = tracker.get_usage_summary(days=period)
        
        # 차트 섹션
        create_api_breakdown_chart(summary)
        
        st.markdown("---")
        
        # 트렌드 분석
        create_daily_usage_trend(summary)
        
        st.markdown("---")
        
        # 예산 분석
        create_budget_analysis()
        
        st.markdown("---")
        
        # 상세 테이블
        create_detailed_table(summary)
        
        st.markdown("---")
        
        # 실시간 모니터링
        create_real_time_monitoring()
        
        # 푸터 정보
        st.markdown("---")
        st.caption(f"데이터 기준: {summary['generated_at']} | 조회 기간: {period}일")
        
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.info("API 사용량 데이터베이스가 초기화되지 않았을 수 있습니다.")
        
        if st.button("데이터베이스 초기화"):
            try:
                tracker = APIUsageTracker()
                st.success("데이터베이스가 초기화되었습니다. 페이지를 새로고침하세요.")
            except Exception as init_error:
                st.error(f"초기화 실패: {init_error}")


if __name__ == "__main__":
    main()