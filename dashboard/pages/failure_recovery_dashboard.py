"""
T04_S03_M03: 장애 감지 및 자동 복구 시스템 - 관리 대시보드
장애 복구 시스템의 상태 모니터링 및 관리를 위한 Streamlit 대시보드
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# 시스템 모듈 임포트
from dashboard.utils.failure_recovery_system import get_failure_recovery_system
from dashboard.utils.failure_detector import get_failure_detector
from dashboard.utils.auto_recovery import get_auto_recovery
from dashboard.utils.recovery_orchestrator import get_recovery_orchestrator
from dashboard.utils.alert_manager import get_alert_manager
from dashboard.utils.failure_analytics import get_failure_analytics

def main():
    """장애 복구 시스템 대시보드 메인"""
    
    st.set_page_config(
        page_title="Failure Recovery Dashboard",
        page_icon="🔧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔧 장애 감지 및 자동 복구 시스템")
    st.markdown("---")
    
    # 사이드바 - 시스템 제어
    render_sidebar()
    
    # 메인 대시보드
    try:
        # 시스템 상태 확인
        system = get_failure_recovery_system()
        system_status = system.get_system_status()
        
        if not system_status.get('is_running', False):
            st.warning("⚠️ 장애 복구 시스템이 실행되지 않고 있습니다.")
            if st.button("🚀 시스템 시작", key="start_system"):
                with st.spinner("시스템을 시작하는 중..."):
                    system.start_system()
                    st.success("✅ 시스템이 시작되었습니다!")
                    st.experimental_rerun()
            return
        
        # 탭 구성
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 시스템 현황", "🔍 장애 감지", "🔄 복구 현황", 
            "📢 알림 현황", "📈 분석 보고서", "⚙️ 시스템 설정"
        ])
        
        with tab1:
            render_system_overview(system_status)
        
        with tab2:
            render_failure_detection()
        
        with tab3:
            render_recovery_status()
        
        with tab4:
            render_alert_status()
        
        with tab5:
            render_analytics_report()
        
        with tab6:
            render_system_configuration()
            
    except Exception as e:
        st.error(f"❌ 대시보드 로딩 중 오류가 발생했습니다: {e}")
        st.exception(e)


def render_sidebar():
    """사이드바 렌더링"""
    st.sidebar.title("🔧 시스템 제어")
    
    try:
        system = get_failure_recovery_system()
        system_status = system.get_system_status()
        
        # 시스템 상태 표시
        if system_status.get('is_running', False):
            st.sidebar.success("✅ 시스템 실행 중")
            uptime = system_status.get('uptime_hours', 0)
            st.sidebar.metric("운영 시간", f"{uptime:.1f}시간")
            
            # 시스템 중지 버튼
            if st.sidebar.button("🛑 시스템 중지", key="stop_system"):
                with st.spinner("시스템을 중지하는 중..."):
                    system.stop_system()
                    st.success("✅ 시스템이 중지되었습니다!")
                    st.experimental_rerun()
        else:
            st.sidebar.error("❌ 시스템 중지됨")
        
        st.sidebar.markdown("---")
        
        # 빠른 액션
        st.sidebar.subheader("🚀 빠른 액션")
        
        # 수동 복구 트리거
        with st.sidebar.form("manual_recovery"):
            st.write("**수동 복구 실행**")
            component = st.text_input("컴포넌트 이름", placeholder="예: api_server")
            failure_type = st.selectbox("장애 유형", [
                "manual_trigger", "api_error", "database_connection", 
                "server_unresponsive", "resource_exhausted"
            ])
            
            if st.form_submit_button("🔄 복구 실행"):
                if component:
                    try:
                        session_id = system.trigger_manual_recovery(component, failure_type)
                        st.success(f"✅ 복구 세션 시작: {session_id}")
                    except Exception as e:
                        st.error(f"❌ 복구 실행 실패: {e}")
                else:
                    st.error("컴포넌트 이름을 입력해주세요.")
        
        # 새로고침 버튼
        if st.sidebar.button("🔄 새로고침", key="refresh_dashboard"):
            st.experimental_rerun()
        
        # 자동 새로고침 설정
        auto_refresh = st.sidebar.checkbox("자동 새로고침 (30초)", value=False)
        if auto_refresh:
            time.sleep(30)
            st.experimental_rerun()
            
    except Exception as e:
        st.sidebar.error(f"❌ 사이드바 오류: {e}")


def render_system_overview(system_status: Dict[str, Any]):
    """시스템 현황 탭 렌더링"""
    
    st.header("📊 시스템 전체 현황")
    
    # 시스템 통계
    stats = system_status.get('statistics', {})
    
    # 메트릭 표시
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "총 장애 감지", 
            stats.get('total_failures_detected', 0),
            delta=None
        )
    
    with col2:
        st.metric(
            "복구 시도", 
            stats.get('total_recoveries_attempted', 0),
            delta=None
        )
    
    with col3:
        success_rate = stats.get('recovery_success_rate', 0) * 100
        st.metric(
            "복구 성공률", 
            f"{success_rate:.1f}%",
            delta=f"{success_rate - 80:.1f}%" if success_rate != 0 else None,
            delta_color="normal" if success_rate >= 80 else "inverse"
        )
    
    with col4:
        st.metric(
            "에스컬레이션", 
            stats.get('escalated_failures', 0),
            delta=None
        )
    
    with col5:
        st.metric(
            "발송 알림", 
            stats.get('alerts_sent', 0),
            delta=None
        )
    
    st.markdown("---")
    
    # 하위 시스템 상태
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔍 하위 시스템 상태")
        subsystems = system_status.get('subsystems', {})
        
        # 장애 감지기
        detector_status = subsystems.get('failure_detector', {})
        detector_color = "🟢" if detector_status.get('monitoring', False) else "🔴"
        st.write(f"{detector_color} **장애 감지기**: {'실행 중' if detector_status.get('monitoring') else '중지됨'}")
        st.write(f"   - 활성 모니터: {detector_status.get('enabled_monitors', 0)}/{detector_status.get('active_monitors', 0)}")
        
        # 복구 오케스트레이터
        orchestrator_status = subsystems.get('recovery_orchestrator', {})
        orchestrator_color = "🟢" if orchestrator_status.get('running', False) else "🔴"
        st.write(f"{orchestrator_color} **복구 오케스트레이터**: {'실행 중' if orchestrator_status.get('running') else '중지됨'}")
        st.write(f"   - 활성 세션: {orchestrator_status.get('active_sessions', 0)}")
        
        # 알림 관리자
        alert_status = subsystems.get('alert_manager', {})
        st.write(f"🟢 **알림 관리자**: 활성화됨")
        st.write(f"   - 활성 채널: {alert_status.get('enabled_channels', 0)}")
    
    with col2:
        st.subheader("📈 실시간 지표")
        
        # 일일 평균 지표
        failures_per_day = stats.get('failures_per_day', 0)
        recoveries_per_day = stats.get('recoveries_per_day', 0)
        
        # 간단한 차트
        metrics_data = pd.DataFrame({
            '지표': ['일일 장애', '일일 복구', '성공률'],
            '값': [failures_per_day, recoveries_per_day, success_rate]
        })
        
        fig = px.bar(
            metrics_data, 
            x='지표', 
            y='값',
            title="주요 지표 현황",
            color='지표'
        )
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    # 시스템 설정 표시
    st.subheader("⚙️ 현재 설정")
    config = system_status.get('configuration', {})
    config_df = pd.DataFrame([
        {"설정": "자동 복구", "값": "활성화" if config.get('enable_auto_recovery') else "비활성화"},
        {"설정": "알림", "값": "활성화" if config.get('enable_alerts') else "비활성화"},
        {"설정": "분석", "값": "활성화" if config.get('enable_analytics') else "비활성화"},
        {"설정": "헬스체크 간격", "값": f"{config.get('health_check_interval', 30)}초"},
        {"설정": "분석 간격", "값": f"{config.get('analytics_interval', 3600)}초"},
    ])
    st.dataframe(config_df, use_container_width=True, hide_index=True)


def render_failure_detection():
    """장애 감지 탭 렌더링"""
    
    st.header("🔍 장애 감지 현황")
    
    try:
        detector = get_failure_detector()
        
        # 최근 장애 통계
        col1, col2 = st.columns(2)
        
        with col1:
            # 기간 선택
            period = st.selectbox("분석 기간", [1, 7, 30], index=1, format_func=lambda x: f"{x}일")
            
        with col2:
            st.metric("모니터링 상태", "🟢 실행 중" if detector.is_monitoring else "🔴 중지됨")
        
        # 장애 통계 조회
        failure_stats = detector.get_failure_statistics(period)
        
        if failure_stats.get('total_failures', 0) > 0:
            # 장애 유형별 분포
            st.subheader("📊 장애 유형별 분포")
            breakdown = failure_stats.get('failure_breakdown', [])
            
            if breakdown:
                breakdown_df = pd.DataFrame(breakdown)
                
                # 파이 차트
                fig = px.pie(
                    breakdown_df, 
                    values='count', 
                    names='failure_type',
                    title=f"최근 {period}일 장애 유형 분포"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 상세 테이블
                st.subheader("📋 상세 통계")
                breakdown_df['평균 복구 시도'] = breakdown_df['avg_recovery_attempts']
                st.dataframe(
                    breakdown_df[['failure_type', 'severity', 'count', '평균 복구 시도']], 
                    use_container_width=True,
                    hide_index=True
                )
            
            # 컴포넌트별 상태
            st.subheader("🔧 컴포넌트별 상태")
            component_states = failure_stats.get('component_states', [])
            
            if component_states:
                components_df = pd.DataFrame(component_states)
                
                # 상태별 색상 매핑
                def status_color(status):
                    colors = {'healthy': '🟢', 'failed': '🔴', 'warning': '🟡'}
                    return colors.get(status, '⚪')
                
                components_df['상태'] = components_df['status'].apply(
                    lambda x: f"{status_color(x)} {x}"
                )
                
                st.dataframe(
                    components_df[['component', '상태', 'consecutive_failures', 'total_failures']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'component': '컴포넌트',
                        'consecutive_failures': '연속 실패',
                        'total_failures': '총 실패'
                    }
                )
        else:
            st.info(f"📅 최근 {period}일간 감지된 장애가 없습니다.")
        
        # 활성 모니터 목록
        st.subheader("📡 활성 모니터")
        monitors_info = []
        for name, config in detector.monitors.items():
            monitors_info.append({
                '모니터명': name,
                '상태': '🟢 활성' if config['enabled'] else '🔴 비활성',
                '간격': f"{config['interval']}초",
                '마지막 체크': config.get('last_check', 'N/A'),
                '연속 실패': config.get('consecutive_failures', 0)
            })
        
        if monitors_info:
            monitors_df = pd.DataFrame(monitors_info)
            st.dataframe(monitors_df, use_container_width=True, hide_index=True)
        else:
            st.warning("등록된 모니터가 없습니다.")
            
    except Exception as e:
        st.error(f"❌ 장애 감지 정보 조회 실패: {e}")


def render_recovery_status():
    """복구 현황 탭 렌더링"""
    
    st.header("🔄 자동 복구 현황")
    
    try:
        orchestrator = get_recovery_orchestrator()
        auto_recovery = get_auto_recovery()
        
        # 활성 복구 세션
        st.subheader("🔄 활성 복구 세션")
        active_sessions = orchestrator.get_active_sessions()
        
        if active_sessions:
            sessions_info = []
            for session in active_sessions:
                sessions_info.append({
                    '세션 ID': session['session_id'][:12] + '...',
                    '컴포넌트': session['failure_event']['component'],
                    '장애 유형': session['failure_event']['failure_type'],
                    '현재 단계': session['current_stage'],
                    '상태': session['status'],
                    '시도 횟수': session['total_attempts'],
                    '시작 시간': session['start_time'][:19].replace('T', ' ')
                })
            
            sessions_df = pd.DataFrame(sessions_info)
            st.dataframe(sessions_df, use_container_width=True, hide_index=True)
            
            # 세션 상세 정보
            if st.checkbox("세션 상세 정보 표시"):
                selected_session = st.selectbox(
                    "세션 선택", 
                    [s['session_id'] for s in active_sessions],
                    format_func=lambda x: x[:12] + '...'
                )
                
                if selected_session:
                    session_details = orchestrator.get_session_details(selected_session)
                    if session_details:
                        st.json(session_details)
        else:
            st.info("현재 활성 복구 세션이 없습니다.")
        
        # 복구 통계
        col1, col2 = st.columns(2)
        
        with col1:
            period = st.selectbox("통계 기간", [1, 7, 30], index=1, format_func=lambda x: f"{x}일", key="recovery_period")
        
        # 복구 통계 조회
        recovery_stats = auto_recovery.get_recovery_statistics(period)
        orchestrator_stats = orchestrator.get_orchestrator_statistics(period)
        
        with col2:
            st.metric(
                "복구 성공률", 
                f"{recovery_stats.get('success_rate', 0):.1f}%"
            )
        
        # 복구 액션별 성능
        st.subheader("📊 복구 액션별 성능")
        recovery_breakdown = recovery_stats.get('recovery_breakdown', [])
        
        if recovery_breakdown:
            recovery_df = pd.DataFrame(recovery_breakdown)
            
            # 성공률 계산
            recovery_df['성공률'] = recovery_df.apply(
                lambda row: (row['count'] if row['result'] == 'success' else 0), axis=1
            )
            
            # 액션별 집계
            action_stats = recovery_df.groupby('action').agg({
                'count': 'sum',
                'avg_execution_time': 'mean'
            }).reset_index()
            
            # 차트
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=('복구 액션별 시도 횟수', '평균 실행 시간'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            fig.add_trace(
                go.Bar(x=action_stats['action'], y=action_stats['count'], name='시도 횟수'),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Bar(x=action_stats['action'], y=action_stats['avg_execution_time'], name='실행 시간(초)'),
                row=1, col=2
            )
            
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # 상세 테이블
            st.dataframe(
                action_stats.rename(columns={
                    'action': '복구 액션',
                    'count': '총 시도',
                    'avg_execution_time': '평균 실행 시간(초)'
                }),
                use_container_width=True,
                hide_index=True
            )
        
        # 오케스트레이터 통계
        st.subheader("🎭 오케스트레이터 통계")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 세션", orchestrator_stats.get('current_stats', {}).get('total_sessions', 0))
        
        with col2:
            st.metric("성공 세션", orchestrator_stats.get('current_stats', {}).get('successful_sessions', 0))
        
        with col3:
            escalations = orchestrator_stats.get('escalations', {})
            st.metric("에스컬레이션", escalations.get('total', 0))
            
    except Exception as e:
        st.error(f"❌ 복구 현황 조회 실패: {e}")


def render_alert_status():
    """알림 현황 탭 렌더링"""
    
    st.header("📢 알림 시스템 현황")
    
    try:
        alert_manager = get_alert_manager()
        
        # 기간 선택
        period = st.selectbox("조회 기간", [1, 7, 30], index=1, format_func=lambda x: f"{x}일", key="alert_period")
        
        # 알림 통계 조회
        alert_stats = alert_manager.get_alert_statistics(period)
        
        # 전체 통계
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 알림", alert_stats.get('total_alerts', 0))
        
        with col2:
            # 채널별 평균 성공률 계산
            channel_stats = alert_stats.get('channel_statistics', [])
            avg_success_rate = 0
            if channel_stats:
                total_attempts = sum(stat.get('total_attempts', 0) for stat in channel_stats)
                successful_attempts = sum(stat.get('successful_attempts', 0) for stat in channel_stats)
                if total_attempts > 0:
                    avg_success_rate = (successful_attempts / total_attempts) * 100
            
            st.metric("전송 성공률", f"{avg_success_rate:.1f}%")
        
        with col3:
            # 채널 수
            active_channels = len([n for n in alert_manager.notifiers.values() 
                                 if getattr(n, 'enabled', True)])
            st.metric("활성 채널", active_channels)
        
        # 알림 유형별 분포
        st.subheader("📊 알림 유형별 분포")
        alert_breakdown = alert_stats.get('alert_breakdown', [])
        
        if alert_breakdown:
            breakdown_df = pd.DataFrame(alert_breakdown)
            
            # 우선순위별 분포
            fig = px.pie(
                breakdown_df, 
                values='count', 
                names='priority',
                title=f"최근 {period}일 알림 우선순위 분포"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 유형별 막대 차트
            fig2 = px.bar(
                breakdown_df, 
                x='alert_type', 
                y='count',
                color='priority',
                title=f"알림 유형별 발송 건수"
            )
            fig2.update_xaxes(tickangle=45)
            st.plotly_chart(fig2, use_container_width=True)
        
        # 채널별 성능
        st.subheader("📡 채널별 성능")
        
        if channel_stats:
            channels_df = pd.DataFrame(channel_stats)
            
            # 성능 메트릭
            channels_df['성공률'] = (channels_df['successful_attempts'] / channels_df['total_attempts'] * 100).round(1)
            channels_df['평균 응답시간'] = channels_df['avg_response_time_ms'].round(0)
            
            st.dataframe(
                channels_df[['channel', '성공률', 'total_attempts', 'successful_attempts', '평균 응답시간']].rename(columns={
                    'channel': '채널',
                    'total_attempts': '총 시도',
                    'successful_attempts': '성공'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # 응답 시간 차트
            fig = px.bar(
                channels_df, 
                x='channel', 
                y='avg_response_time_ms',
                title="채널별 평균 응답 시간 (ms)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("채널별 통계 데이터가 없습니다.")
        
        # 알림 설정 현황
        st.subheader("⚙️ 알림 채널 설정")
        
        channel_config = []
        for channel_name, notifier in alert_manager.notifiers.items():
            enabled = getattr(notifier, 'enabled', True)
            status = "🟢 활성화" if enabled else "🔴 비활성화"
            
            channel_config.append({
                '채널': channel_name.value,
                '상태': status,
                '설명': {
                    'slack': 'Slack 웹훅 알림',
                    'email': 'SMTP 이메일 알림',
                    'sms': 'SMS 알림 (향후 지원)',
                    'webhook': '사용자 정의 웹훅'
                }.get(channel_name.value, '알 수 없음')
            })
        
        config_df = pd.DataFrame(channel_config)
        st.dataframe(config_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"❌ 알림 현황 조회 실패: {e}")


def render_analytics_report():
    """분석 보고서 탭 렌더링"""
    
    st.header("📈 장애 분석 보고서")
    
    try:
        analytics = get_failure_analytics()
        system = get_failure_recovery_system()
        
        # 기간 선택
        period = st.selectbox("보고서 기간", [7, 14, 30, 90], index=0, format_func=lambda x: f"{x}일", key="analytics_period")
        
        # 종합 보고서 생성
        with st.spinner("분석 보고서를 생성하는 중..."):
            comprehensive_report = system.get_comprehensive_report(period)
        
        if 'error' in comprehensive_report:
            st.error(f"❌ 보고서 생성 실패: {comprehensive_report['error']}")
            return
        
        # 요약 정보
        st.subheader("📋 분석 요약")
        summary = comprehensive_report.get('summary', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 장애", summary.get('total_failures', 0))
        
        with col2:
            st.metric("일일 장애율", f"{summary.get('failure_rate_per_day', 0):.1f}")
        
        with col3:
            trend = summary.get('trend_direction', 'stable')
            trend_emoji = {'increasing': '📈', 'decreasing': '📉', 'stable': '➡️', 'volatile': '📊'}
            st.metric("트렌드", f"{trend_emoji.get(trend, '➡️')} {trend}")
        
        with col4:
            st.metric("감지된 패턴", summary.get('patterns_detected', 0))
        
        # 트렌드 분석
        st.subheader("📈 장애 트렌드 분석")
        trend_analysis = comprehensive_report.get('failure_analysis', {}).get('trend_analysis', {})
        
        if trend_analysis:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**분석 결과:**")
                st.write(f"- 분석 기간: {trend_analysis.get('analysis_period_days', 0)}일")
                st.write(f"- 총 장애: {trend_analysis.get('total_failures', 0)}건")
                st.write(f"- 트렌드: {trend_analysis.get('trend_direction', 'unknown')} ({trend_analysis.get('trend_percentage', 0):.1f}%)")
                st.write(f"- 주요 장애 유형: {trend_analysis.get('most_common_failure_type', 'N/A')}")
                st.write(f"- 최다 영향 컴포넌트: {trend_analysis.get('most_affected_component', 'N/A')}")
            
            with col2:
                # 심각도 분포
                severity_dist = trend_analysis.get('severity_distribution', {})
                if severity_dist:
                    severity_df = pd.DataFrame([
                        {'심각도': k, '건수': v} for k, v in severity_dist.items()
                    ])
                    
                    fig = px.pie(
                        severity_df, 
                        values='건수', 
                        names='심각도',
                        title="심각도별 분포"
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # 감지된 패턴
        st.subheader("🔍 감지된 장애 패턴")
        patterns = comprehensive_report.get('failure_analysis', {}).get('detected_patterns', [])
        
        if patterns:
            pattern_info = []
            for pattern in patterns:
                pattern_info.append({
                    '패턴 ID': pattern['pattern_id'],
                    '설명': pattern['description'],
                    '빈도': pattern['frequency'],
                    '신뢰도': f"{pattern['confidence_score']:.2f}",
                    '복구 성공률': f"{pattern['recovery_success_rate']:.1%}",
                    '평균 복구 시간': f"{pattern['avg_recovery_time_minutes']:.1f}분"
                })
            
            patterns_df = pd.DataFrame(pattern_info)
            st.dataframe(patterns_df, use_container_width=True, hide_index=True)
        else:
            st.info("감지된 패턴이 없습니다.")
        
        # 장애 예측
        st.subheader("🔮 장애 위험 예측")
        predictions = comprehensive_report.get('failure_analysis', {}).get('failure_predictions', [])
        
        if predictions:
            pred_info = []
            for pred in predictions:
                pred_info.append({
                    '컴포넌트': pred['component'],
                    '예상 장애 유형': pred['predicted_failure_type'],
                    '위험도': f"{pred['probability']:.1%}",
                    '예측 기간': pred['predicted_time_window'],
                    '신뢰도': f"{pred['confidence_level']:.2f}"
                })
            
            pred_df = pd.DataFrame(pred_info)
            
            # 위험도별 색상 적용
            def risk_color(risk_str):
                risk = float(risk_str.rstrip('%')) / 100
                if risk >= 0.7:
                    return '🔴 높음'
                elif risk >= 0.4:
                    return '🟡 보통'
                else:
                    return '🟢 낮음'
            
            pred_df['위험 수준'] = pred_df['위험도'].apply(risk_color)
            
            st.dataframe(pred_df, use_container_width=True, hide_index=True)
        else:
            st.info("예측된 장애 위험이 없습니다.")
        
        # 핵심 지표
        st.subheader("📊 핵심 성능 지표")
        key_metrics = comprehensive_report.get('key_metrics', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            availability = key_metrics.get('system_availability', 99.0)
            st.metric(
                "시스템 가용성", 
                f"{availability:.2f}%",
                delta=f"{availability - 99:.2f}%" if availability != 99 else None,
                delta_color="normal" if availability >= 99 else "inverse"
            )
        
        with col2:
            mttr = key_metrics.get('mttr_minutes', 15)
            st.metric("MTTR (분)", f"{mttr:.1f}")
        
        with col3:
            mtbf = key_metrics.get('mtbf_hours', 72)
            st.metric("MTBF (시간)", f"{mtbf:.1f}")
        
        with col4:
            alert_rate = key_metrics.get('alert_delivery_rate', 100)
            st.metric("알림 전송률", f"{alert_rate:.1f}%")
        
        # 권장사항
        st.subheader("💡 권장사항")
        recommendations = comprehensive_report.get('recommendations', [])
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                st.write(f"**{i}.** {rec}")
        else:
            st.info("현재 특별한 권장사항이 없습니다.")
        
        # 보고서 다운로드
        st.subheader("📥 보고서 다운로드")
        
        # JSON 다운로드
        report_json = json.dumps(comprehensive_report, ensure_ascii=False, indent=2)
        st.download_button(
            label="📄 JSON 형식 다운로드",
            data=report_json,
            file_name=f"failure_analysis_report_{period}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        
    except Exception as e:
        st.error(f"❌ 분석 보고서 생성 실패: {e}")
        st.exception(e)


def render_system_configuration():
    """시스템 설정 탭 렌더링"""
    
    st.header("⚙️ 시스템 설정")
    
    try:
        system = get_failure_recovery_system()
        current_status = system.get_system_status()
        current_config = current_status.get('configuration', {})
        
        st.subheader("🔧 현재 설정")
        
        # 설정 수정 폼
        with st.form("system_config"):
            st.write("**기본 기능 설정**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                enable_auto_recovery = st.checkbox(
                    "자동 복구 활성화", 
                    value=current_config.get('enable_auto_recovery', True)
                )
            
            with col2:
                enable_alerts = st.checkbox(
                    "알림 활성화", 
                    value=current_config.get('enable_alerts', True)
                )
            
            with col3:
                enable_analytics = st.checkbox(
                    "분석 활성화", 
                    value=current_config.get('enable_analytics', True)
                )
            
            st.write("**모니터링 간격 설정**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                health_check_interval = st.number_input(
                    "헬스체크 간격 (초)", 
                    min_value=10, 
                    max_value=300, 
                    value=current_config.get('health_check_interval', 30)
                )
            
            with col2:
                analytics_interval = st.number_input(
                    "분석 간격 (초)", 
                    min_value=300, 
                    max_value=86400, 
                    value=current_config.get('analytics_interval', 3600)
                )
            
            with col3:
                status_report_interval = st.number_input(
                    "상태 보고 간격 (초)", 
                    min_value=3600, 
                    max_value=604800, 
                    value=current_config.get('status_report_interval', 86400)
                )
            
            # 설정 저장 버튼
            if st.form_submit_button("💾 설정 저장", type="primary"):
                new_config = {
                    'enable_auto_recovery': enable_auto_recovery,
                    'enable_alerts': enable_alerts,
                    'enable_analytics': enable_analytics,
                    'health_check_interval': health_check_interval,
                    'analytics_interval': analytics_interval,
                    'status_report_interval': status_report_interval
                }
                
                try:
                    success = system.update_configuration(new_config)
                    if success:
                        st.success("✅ 설정이 저장되었습니다!")
                        st.experimental_rerun()
                    else:
                        st.error("❌ 설정 저장에 실패했습니다.")
                except Exception as e:
                    st.error(f"❌ 설정 저장 오류: {e}")
        
        st.markdown("---")
        
        # 시스템 액션
        st.subheader("🔧 시스템 관리")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 시스템 재시작", key="restart_system"):
                try:
                    with st.spinner("시스템을 재시작하는 중..."):
                        system.stop_system()
                        time.sleep(2)
                        system.start_system()
                    st.success("✅ 시스템이 재시작되었습니다!")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ 시스템 재시작 실패: {e}")
        
        with col2:
            if st.button("📊 즉시 분석 실행", key="run_analysis"):
                try:
                    with st.spinner("분석을 실행하는 중..."):
                        analytics = get_failure_analytics()
                        trend = analytics.analyze_failure_trends(7)
                        patterns = analytics.detect_failure_patterns(30)
                    st.success(f"✅ 분석 완료! 패턴 {len(patterns)}개 감지")
                except Exception as e:
                    st.error(f"❌ 분석 실행 실패: {e}")
        
        with col3:
            if st.button("🧹 로그 정리", key="cleanup_logs"):
                st.info("🔧 로그 정리 기능은 개발 중입니다.")
        
        # 고급 설정
        st.subheader("🔬 고급 설정")
        
        with st.expander("모니터 설정"):
            detector = get_failure_detector()
            
            st.write("**등록된 모니터:**")
            for name, config in detector.monitors.items():
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(f"**{name}**")
                
                with col2:
                    st.write(f"{config['interval']}초")
                
                with col3:
                    status = "🟢 활성" if config['enabled'] else "🔴 비활성"
                    st.write(status)
        
        with st.expander("알림 채널 설정"):
            alert_manager = get_alert_manager()
            
            st.write("**채널별 상태:**")
            for channel_name, notifier in alert_manager.notifiers.items():
                enabled = getattr(notifier, 'enabled', True)
                status = "🟢 활성화" if enabled else "🔴 비활성화"
                st.write(f"- **{channel_name.value}**: {status}")
        
        # 시스템 정보
        st.subheader("ℹ️ 시스템 정보")
        
        system_info = {
            "시스템 버전": "1.0.0",
            "시작 시간": current_status.get('start_time', 'N/A'),
            "운영 시간": f"{current_status.get('uptime_hours', 0):.1f}시간",
            "실행 상태": "🟢 실행 중" if current_status.get('is_running') else "🔴 중지됨"
        }
        
        info_df = pd.DataFrame([
            {"항목": k, "값": v} for k, v in system_info.items()
        ])
        
        st.dataframe(info_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"❌ 시스템 설정 조회 실패: {e}")


if __name__ == "__main__":
    main()