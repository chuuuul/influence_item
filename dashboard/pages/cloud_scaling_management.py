"""
클라우드 스케일링 관리 페이지
T03B_S03_M03: 클라우드 인스턴스 자동 스케일링 실행 시스템의 웹 인터페이스
"""

import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import logging

# 프로젝트 utils 임포트
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.utils.integrated_scaling_manager import get_scaling_manager, start_auto_scaling, stop_auto_scaling

logger = logging.getLogger(__name__)


async def render_cloud_scaling_page():
    """클라우드 스케일링 관리 페이지 렌더링"""
    
    st.title("🚀 클라우드 스케일링 관리")
    st.markdown("---")
    
    try:
        # 스케일링 관리자 초기화
        manager = await get_scaling_manager()
        
        # 사이드바 제어판
        with st.sidebar:
            st.header("⚙️ 제어판")
            
            # 자동 스케일링 토글
            auto_scaling_enabled = st.toggle(
                "자동 스케일링 활성화", 
                value=manager.enable_auto_scaling,
                help="자동 스케일링을 활성화/비활성화합니다"
            )
            
            if auto_scaling_enabled != manager.enable_auto_scaling:
                await manager.update_configuration({'enable_auto_scaling': auto_scaling_enabled})
                st.success("자동 스케일링 설정이 업데이트되었습니다")
                st.rerun()
            
            # 모니터링 상태
            st.subheader("📊 모니터링 상태")
            status = manager.get_status()
            
            if status['is_running']:
                st.success("🟢 모니터링 활성")
                if st.button("모니터링 중지", type="secondary"):
                    manager.stop_monitoring()
                    st.success("모니터링이 중지되었습니다")
                    st.rerun()
            else:
                st.error("🔴 모니터링 비활성")
                if st.button("모니터링 시작", type="primary"):
                    asyncio.create_task(manager.start_monitoring())
                    st.success("모니터링이 시작되었습니다")
                    st.rerun()
            
            # 설정 조정
            st.subheader("⚙️ 설정")
            
            new_cost_limit = st.number_input(
                "시간당 비용 한도 ($)",
                min_value=1.0,
                max_value=100.0,
                value=manager.cost_limit_per_hour,
                step=0.5,
                help="시간당 최대 허용 비용"
            )
            
            new_monitoring_interval = st.number_input(
                "모니터링 간격 (초)",
                min_value=30,
                max_value=600,
                value=manager.monitoring_interval,
                step=30,
                help="메트릭 수집 간격"
            )
            
            if st.button("설정 적용"):
                await manager.update_configuration({
                    'cost_limit_per_hour': new_cost_limit,
                    'monitoring_interval': new_monitoring_interval
                })
                st.success("설정이 적용되었습니다")
                st.rerun()
        
        # 메인 대시보드
        col1, col2, col3, col4 = st.columns(4)
        
        # 상세 메트릭 조회
        detailed_metrics = await manager.get_detailed_metrics()
        current_metrics = detailed_metrics.get('current_metrics', {})
        cost_estimate = detailed_metrics.get('cost_estimate', {})
        
        with col1:
            st.metric(
                "🖥️ 실행 중인 인스턴스",
                value=current_metrics.get('aws_instances_running', 0),
                delta=None
            )
        
        with col2:
            hourly_cost = cost_estimate.get('cost_per_hour', 0.0)
            st.metric(
                "💰 시간당 비용",
                value=f"${hourly_cost:.4f}",
                delta=f"${hourly_cost - manager.cost_limit_per_hour:.4f}" if hourly_cost > manager.cost_limit_per_hour else None,
                delta_color="inverse"
            )
        
        with col3:
            cpu_percent = current_metrics.get('cpu_percent', 0)
            st.metric(
                "🔥 CPU 사용률",
                value=f"{cpu_percent:.1f}%",
                delta=None
            )
        
        with col4:
            queue_length = current_metrics.get('processing_queue_length', 0)
            st.metric(
                "📋 처리 대기열",
                value=queue_length,
                delta=None
            )
        
        st.markdown("---")
        
        # 탭 구성
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 실시간 모니터링", 
            "🎯 스케일링 결정", 
            "📈 비용 추적", 
            "🔧 수동 제어", 
            "📋 이벤트 로그"
        ])
        
        with tab1:
            await render_monitoring_tab(detailed_metrics)
        
        with tab2:
            await render_scaling_decisions_tab(detailed_metrics)
        
        with tab3:
            await render_cost_tracking_tab(detailed_metrics)
        
        with tab4:
            await render_manual_control_tab(manager)
        
        with tab5:
            await render_event_log_tab(status)
        
    except Exception as e:
        st.error(f"페이지 로딩 중 오류가 발생했습니다: {e}")
        logger.error(f"Cloud scaling page error: {e}")


async def render_monitoring_tab(detailed_metrics):
    """실시간 모니터링 탭"""
    st.subheader("📊 실시간 시스템 메트릭")
    
    current_metrics = detailed_metrics.get('current_metrics', {})
    predictions = detailed_metrics.get('predictions', {})
    
    if not current_metrics:
        st.warning("메트릭 데이터를 가져올 수 없습니다")
        return
    
    # 메트릭 차트
    col1, col2 = st.columns(2)
    
    with col1:
        # CPU & 메모리 사용률
        fig_resource = go.Figure()
        
        fig_resource.add_trace(go.Indicator(
            mode="gauge+number",
            value=current_metrics.get('cpu_percent', 0),
            domain={'x': [0, 0.5], 'y': [0, 1]},
            title={'text': "CPU 사용률 (%)"},
            gauge={'axis': {'range': [None, 100]},
                   'bar': {'color': "darkblue"},
                   'steps': [
                       {'range': [0, 50], 'color': "lightgray"},
                       {'range': [50, 80], 'color': "yellow"},
                       {'range': [80, 100], 'color': "red"}],
                   'threshold': {'line': {'color': "red", 'width': 4},
                                'thickness': 0.75, 'value': 90}}
        ))
        
        fig_resource.add_trace(go.Indicator(
            mode="gauge+number",
            value=current_metrics.get('memory_percent', 0),
            domain={'x': [0.5, 1], 'y': [0, 1]},
            title={'text': "메모리 사용률 (%)"},
            gauge={'axis': {'range': [None, 100]},
                   'bar': {'color': "darkgreen"},
                   'steps': [
                       {'range': [0, 60], 'color': "lightgray"},
                       {'range': [60, 85], 'color': "yellow"},
                       {'range': [85, 100], 'color': "red"}],
                   'threshold': {'line': {'color': "red", 'width': 4},
                                'thickness': 0.75, 'value': 95}}
        ))
        
        fig_resource.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_resource, use_container_width=True)
    
    with col2:
        # 처리 대기열 및 응답 시간
        queue_data = {
            '메트릭': ['처리 대기열', '평균 응답시간 (ms)', '성공률 (%)'],
            '현재값': [
                current_metrics.get('processing_queue_length', 0),
                current_metrics.get('avg_response_time', 0),
                current_metrics.get('success_rate', 100)
            ]
        }
        
        if predictions:
            queue_data['예측값'] = [
                predictions.get('prediction', 0),
                predictions.get('predicted_response_time', 0),
                predictions.get('predicted_success_rate', 100)
            ]
        
        df_queue = pd.DataFrame(queue_data)
        
        fig_queue = px.bar(
            df_queue, 
            x='메트릭', 
            y=['현재값'] + (['예측값'] if predictions else []),
            title="처리 성능 메트릭",
            barmode='group'
        )
        fig_queue.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_queue, use_container_width=True)
    
    # 원시 메트릭 데이터
    with st.expander("🔍 상세 메트릭 데이터"):
        st.json(current_metrics)


async def render_scaling_decisions_tab(detailed_metrics):
    """스케일링 결정 탭"""
    st.subheader("🎯 스케일링 결정 이력")
    
    decision_history = detailed_metrics.get('decision_history', [])
    
    if not decision_history:
        st.info("스케일링 결정 이력이 없습니다")
        return
    
    # 결정 이력 테이블
    decisions_data = []
    for decision in decision_history:
        decisions_data.append({
            '시간': decision.get('decision_time', ''),
            '액션': decision.get('action', ''),
            '이유': ', '.join(decision.get('reasons', [])),
            '신뢰도': f"{decision.get('confidence', 0):.2f}",
            '긴급도': decision.get('urgency', 0),
            '권장 인스턴스': decision.get('recommended_instances', 0),
            '비용 영향': f"${decision.get('cost_impact', 0):.4f}"
        })
    
    df_decisions = pd.DataFrame(decisions_data)
    st.dataframe(df_decisions, use_container_width=True)
    
    # 결정 분포 차트
    if len(decisions_data) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            # 액션 분포
            action_counts = df_decisions['액션'].value_counts()
            fig_actions = px.pie(
                values=action_counts.values,
                names=action_counts.index,
                title="스케일링 액션 분포"
            )
            st.plotly_chart(fig_actions, use_container_width=True)
        
        with col2:
            # 신뢰도 히스토그램
            fig_confidence = px.histogram(
                df_decisions,
                x='신뢰도',
                title="결정 신뢰도 분포",
                nbins=10
            )
            st.plotly_chart(fig_confidence, use_container_width=True)


async def render_cost_tracking_tab(detailed_metrics):
    """비용 추적 탭"""
    st.subheader("📈 비용 추적 및 예측")
    
    cost_estimate = detailed_metrics.get('cost_estimate', {})
    
    if not cost_estimate:
        st.warning("비용 데이터를 가져올 수 없습니다")
        return
    
    # 비용 메트릭
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "시간당 비용",
            f"${cost_estimate.get('cost_per_hour', 0):.4f}",
            help="현재 실행 중인 인스턴스의 시간당 비용"
        )
    
    with col2:
        st.metric(
            "일일 비용",
            f"${cost_estimate.get('cost_per_day', 0):.2f}",
            help="현재 설정 기준 일일 예상 비용"
        )
    
    with col3:
        st.metric(
            "월간 비용",
            f"${cost_estimate.get('cost_per_month', 0):.2f}",
            help="현재 설정 기준 월간 예상 비용"
        )
    
    # 비용 시나리오 분석
    st.subheader("💡 비용 시나리오 분석")
    
    # 인스턴스 수에 따른 비용 시뮬레이션
    instances_range = list(range(1, 11))
    hourly_costs = [i * 0.0928 for i in instances_range]  # t3.large 기준
    daily_costs = [h * 24 for h in hourly_costs]
    monthly_costs = [d * 30 for d in daily_costs]
    
    cost_simulation = pd.DataFrame({
        '인스턴스 수': instances_range,
        '시간당 비용': hourly_costs,
        '일일 비용': daily_costs,
        '월간 비용': monthly_costs
    })
    
    fig_cost_sim = px.line(
        cost_simulation,
        x='인스턴스 수',
        y=['시간당 비용', '일일 비용', '월간 비용'],
        title="인스턴스 수에 따른 비용 변화",
        labels={'value': '비용 ($)', 'variable': '비용 유형'}
    )
    st.plotly_chart(fig_cost_sim, use_container_width=True)
    
    # 실행 이력별 비용
    execution_history = detailed_metrics.get('execution_history', [])
    if execution_history:
        st.subheader("💰 스케일링 실행별 비용 영향")
        
        exec_data = []
        for exec_item in execution_history:
            exec_data.append({
                '실행 시간': exec_item.get('execution_time', ''),
                '액션': exec_item.get('action', ''),
                '대상 인스턴스': exec_item.get('target_instances', 0),
                '비용 영향': f"${exec_item.get('cost_estimate', 0):.4f}",
                '상태': exec_item.get('status', '')
            })
        
        df_exec = pd.DataFrame(exec_data)
        st.dataframe(df_exec, use_container_width=True)


async def render_manual_control_tab(manager):
    """수동 제어 탭"""
    st.subheader("🔧 수동 스케일링 제어")
    
    # 현재 상태 표시
    detailed_metrics = await manager.get_detailed_metrics()
    current_instances = detailed_metrics.get('current_metrics', {}).get('aws_instances_running', 0)
    
    st.info(f"현재 실행 중인 인스턴스: **{current_instances}개**")
    
    # 수동 스케일링 폼
    with st.form("manual_scaling_form"):
        st.markdown("### 🎯 타겟 인스턴스 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            target_instances = st.number_input(
                "목표 인스턴스 수",
                min_value=1,
                max_value=10,
                value=current_instances,
                step=1,
                help="설정할 목표 인스턴스 수 (1-10개)"
            )
        
        with col2:
            reason = st.selectbox(
                "스케일링 이유",
                [
                    "Manual Override",
                    "Performance Testing",
                    "Traffic Spike Preparation",
                    "Cost Optimization",
                    "Maintenance",
                    "Emergency Response"
                ],
                help="수동 스케일링을 수행하는 이유"
            )
        
        # 예상 비용 계산
        cost_per_instance = 0.0928  # t3.large 시간당 비용
        estimated_hourly_cost = target_instances * cost_per_instance
        cost_difference = (target_instances - current_instances) * cost_per_instance
        
        st.markdown("### 💰 비용 영향 분석")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("예상 시간당 비용", f"${estimated_hourly_cost:.4f}")
        
        with col2:
            st.metric(
                "비용 변화", 
                f"${cost_difference:.4f}",
                delta=f"${cost_difference:.4f}"
            )
        
        with col3:
            st.metric("예상 일일 비용", f"${estimated_hourly_cost * 24:.2f}")
        
        # 안전 확인
        if estimated_hourly_cost > manager.cost_limit_per_hour:
            st.warning(f"⚠️ 예상 비용이 설정된 한도(${manager.cost_limit_per_hour:.4f}/시간)를 초과합니다!")
        
        # 실행 버튼
        submit_manual = st.form_submit_button(
            "🚀 수동 스케일링 실행",
            type="primary",
            help="설정된 타겟으로 수동 스케일링을 실행합니다"
        )
        
        if submit_manual:
            if target_instances == current_instances:
                st.info("현재와 동일한 인스턴스 수입니다. 변경이 필요하지 않습니다.")
            else:
                try:
                    with st.spinner("수동 스케일링을 실행 중입니다..."):
                        execution_result = await manager.manual_scale(
                            target_instances=target_instances,
                            reason=reason
                        )
                    
                    st.success(f"✅ 수동 스케일링이 성공적으로 실행되었습니다!")
                    st.info(f"실행 ID: {execution_result.execution_id}")
                    
                    # 3초 후 페이지 새로고침
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 수동 스케일링 실행 중 오류가 발생했습니다: {e}")
    
    # 빠른 액션 버튼들
    st.markdown("### ⚡ 빠른 액션")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("➕ 인스턴스 +1", help="인스턴스 1개 추가"):
            try:
                await manager.manual_scale(current_instances + 1, "Quick Scale Up")
                st.success("인스턴스가 1개 추가되었습니다")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")
    
    with col2:
        if current_instances > 1 and st.button("➖ 인스턴스 -1", help="인스턴스 1개 제거"):
            try:
                await manager.manual_scale(current_instances - 1, "Quick Scale Down")
                st.success("인스턴스가 1개 제거되었습니다")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")
    
    with col3:
        if st.button("🔄 최소 구성", help="최소 인스턴스로 설정 (1개)"):
            try:
                await manager.manual_scale(1, "Minimum Configuration")
                st.success("최소 구성으로 설정되었습니다")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")
    
    with col4:
        if st.button("⚡ 고성능 구성", help="고성능 구성으로 설정 (5개)"):
            try:
                await manager.manual_scale(5, "High Performance Configuration")
                st.success("고성능 구성으로 설정되었습니다")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")


async def render_event_log_tab(status):
    """이벤트 로그 탭"""
    st.subheader("📋 이벤트 로그")
    
    recent_events = status.get('recent_events', [])
    
    if not recent_events:
        st.info("최근 이벤트가 없습니다")
        return
    
    # 이벤트 필터
    col1, col2 = st.columns(2)
    
    with col1:
        event_types = list(set([event['event_type'] for event in recent_events]))
        selected_type = st.selectbox(
            "이벤트 타입 필터",
            ["전체"] + event_types,
            help="특정 타입의 이벤트만 표시"
        )
    
    with col2:
        show_details = st.checkbox("상세 정보 표시", value=False)
    
    # 이벤트 목록 표시
    filtered_events = recent_events
    if selected_type != "전체":
        filtered_events = [e for e in recent_events if e['event_type'] == selected_type]
    
    for event in reversed(filtered_events):  # 최신 순으로 표시
        timestamp = datetime.fromisoformat(event['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
        event_type = event['event_type']
        
        # 이벤트 타입에 따른 아이콘
        icon_map = {
            'decision_made': '🎯',
            'execution_started': '🚀',
            'execution_completed': '✅',
            'execution_failed': '❌',
            'manual_scaling': '🔧',
            'cost_limit_exceeded': '💰',
            'configuration_updated': '⚙️'
        }
        
        icon = icon_map.get(event_type, '📝')
        
        with st.container():
            st.markdown(f"**{icon} {event_type}** - {timestamp}")
            
            if show_details:
                st.json(event['details'])
            else:
                # 간단한 요약 표시
                details = event['details']
                if event_type == 'decision_made':
                    st.write(f"Action: {details.get('action', 'N/A')}, Confidence: {details.get('confidence', 0):.2f}")
                elif event_type in ['execution_started', 'execution_completed']:
                    st.write(f"Action: {details.get('action', 'N/A')}, Target: {details.get('target_instances', 'N/A')}")
                elif event_type == 'manual_scaling':
                    st.write(f"Target: {details.get('target_instances', 'N/A')}, Reason: {details.get('reason', 'N/A')}")
                else:
                    st.write(f"Details: {str(details)[:100]}...")
            
            st.markdown("---")


def render_page():
    """페이지 렌더링 (동기 버전)"""
    try:
        # 비동기 함수를 동기적으로 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(render_cloud_scaling_page())
    except Exception as e:
        st.error(f"페이지 렌더링 중 오류가 발생했습니다: {e}")
        logger.error(f"Page rendering error: {e}")


if __name__ == "__main__":
    render_page()