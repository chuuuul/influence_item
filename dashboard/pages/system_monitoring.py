"""
T01_S03_M03: 실시간 모니터링 대시보드
시스템 리소스, GPU, n8n 워크플로우, 데이터베이스, 네트워크 통합 모니터링
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import time
from datetime import datetime, timedelta
import logging

# 모니터링 모듈 임포트
from dashboard.utils.system_monitor import get_system_monitor, HealthStatus
from dashboard.utils.n8n_monitor import get_n8n_monitor
from dashboard.utils.database_performance_monitor import get_database_monitor
from dashboard.utils.network_monitor import get_network_monitor
from dashboard.utils.error_handler import handle_error

logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="시스템 모니터링",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def create_gauge_chart(value: float, title: str, max_value: float = 100, 
                      threshold_warning: float = 70, threshold_critical: float = 90,
                      unit: str = "%") -> go.Figure:
    """게이지 차트 생성"""
    # 색상 결정
    if value >= threshold_critical:
        color = "red"
    elif value >= threshold_warning:
        color = "orange"
    else:
        color = "green"
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        number = {'suffix': unit},
        gauge = {
            'axis': {'range': [None, max_value]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, threshold_warning], 'color': "lightgray"},
                {'range': [threshold_warning, threshold_critical], 'color': "yellow"},
                {'range': [threshold_critical, max_value], 'color': "lightcoral"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': threshold_critical
            }
        }
    ))
    
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def create_time_series_chart(data: list, title: str, y_label: str) -> go.Figure:
    """시계열 차트 생성"""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="데이터 없음", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title=title, height=300)
        return fig
    
    df = pd.DataFrame(data)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['value'],
        mode='lines+markers',
        name=y_label,
        line=dict(width=2)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="시간",
        yaxis_title=y_label,
        height=300,
        margin=dict(l=50, r=20, t=50, b=40)
    )
    
    return fig


def display_health_status(health_data: dict):
    """헬스 상태 표시"""
    if not health_data:
        st.error("헬스 상태 데이터를 가져올 수 없습니다.")
        return
    
    st.subheader("🏥 시스템 헬스 상태")
    
    # 헬스 상태별 색상 매핑
    status_colors = {
        HealthStatus.HEALTHY: "🟢",
        HealthStatus.WARNING: "🟡", 
        HealthStatus.CRITICAL: "🔴",
        HealthStatus.DOWN: "⚫"
    }
    
    # 헬스 상태를 열로 표시
    cols = st.columns(len(health_data))
    
    for idx, (component, health_check) in enumerate(health_data.items()):
        with cols[idx]:
            # 상태에 따른 색상
            if hasattr(health_check, 'status'):
                status = health_check.status
                if isinstance(status, str):
                    # 문자열인 경우 HealthStatus로 변환
                    status_map = {
                        'healthy': HealthStatus.HEALTHY,
                        'warning': HealthStatus.WARNING,
                        'critical': HealthStatus.CRITICAL,
                        'down': HealthStatus.DOWN
                    }
                    status = status_map.get(status.lower(), HealthStatus.CRITICAL)
            else:
                status = HealthStatus.CRITICAL
            
            status_icon = status_colors.get(status, "❓")
            
            st.metric(
                label=f"{status_icon} {component.title()}",
                value=status.value.title() if hasattr(status, 'value') else str(status),
                help=health_check.message if hasattr(health_check, 'message') else "상태 정보"
            )


def display_system_overview():
    """시스템 개요 표시"""
    st.header("🖥️ 시스템 리소스 모니터링")
    
    try:
        # 시스템 모니터 인스턴스 가져오기
        system_monitor = get_system_monitor()
        
        # 현재 시스템 메트릭 수집
        current_metrics = system_monitor._collect_system_metrics()
        
        if current_metrics:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                cpu_chart = create_gauge_chart(
                    current_metrics.cpu_percent,
                    "CPU 사용률",
                    max_value=100,
                    threshold_warning=70,
                    threshold_critical=90
                )
                st.plotly_chart(cpu_chart, use_container_width=True)
            
            with col2:
                memory_chart = create_gauge_chart(
                    current_metrics.memory_percent,
                    "메모리 사용률",
                    max_value=100,
                    threshold_warning=75,
                    threshold_critical=90
                )
                st.plotly_chart(memory_chart, use_container_width=True)
            
            with col3:
                disk_chart = create_gauge_chart(
                    current_metrics.disk_percent,
                    "디스크 사용률",
                    max_value=100,
                    threshold_warning=80,
                    threshold_critical=95
                )
                st.plotly_chart(disk_chart, use_container_width=True)
            
            with col4:
                # 업타임 표시
                uptime_hours = current_metrics.uptime / 3600
                st.metric(
                    "시스템 업타임",
                    f"{uptime_hours:.1f}시간",
                    help="시스템이 켜진 시간"
                )
                
                st.metric(
                    "네트워크 연결",
                    f"{current_metrics.active_connections}개",
                    help="활성 네트워크 연결 수"
                )
                
                st.metric(
                    "메모리 사용가능",
                    f"{current_metrics.memory_available / (1024**3):.1f}GB",
                    help="사용 가능한 메모리"
                )
                
                st.metric(
                    "디스크 여유공간",
                    f"{current_metrics.disk_free / (1024**3):.1f}GB",
                    help="사용 가능한 디스크 공간"
                )
        
        # GPU 정보 표시
        if current_metrics and current_metrics.gpu_metrics:
            st.subheader("🎮 GPU 모니터링")
            
            gpu_cols = st.columns(len(current_metrics.gpu_metrics))
            for idx, gpu_metric in enumerate(current_metrics.gpu_metrics):
                with gpu_cols[idx]:
                    st.markdown(f"**GPU {gpu_metric.gpu_id}: {gpu_metric.name}**")
                    
                    # GPU 로드 게이지
                    gpu_load_chart = create_gauge_chart(
                        gpu_metric.load,
                        f"GPU {gpu_metric.gpu_id} 로드",
                        max_value=100,
                        threshold_warning=80,
                        threshold_critical=95
                    )
                    st.plotly_chart(gpu_load_chart, use_container_width=True)
                    
                    # GPU 메모리 및 온도 정보
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric(
                            "메모리 사용률",
                            f"{gpu_metric.memory_util:.1f}%",
                            help=f"사용: {gpu_metric.memory_used}MB / 전체: {gpu_metric.memory_total}MB"
                        )
                    
                    with col_b:
                        temp_color = "🔴" if gpu_metric.temperature > 80 else "🟡" if gpu_metric.temperature > 70 else "🟢"
                        st.metric(
                            "온도",
                            f"{temp_color} {gpu_metric.temperature}°C",
                            help="GPU 온도"
                        )
        
        elif current_metrics:
            st.info("GPU 모니터링을 사용할 수 없습니다. (GPUtil이 설치되지 않았거나 GPU가 없습니다)")
        
        # 헬스 상태 표시
        health_data = system_monitor.get_health_status()
        display_health_status(health_data)
        
    except Exception as e:
        handle_error(e, "시스템 모니터링 데이터 수집 중 오류가 발생했습니다.")


def display_n8n_monitoring():
    """n8n 워크플로우 모니터링 표시"""
    st.header("⚙️ n8n 워크플로우 모니터링")
    
    try:
        # n8n 모니터 설정
        n8n_url = st.sidebar.text_input("n8n URL", value="http://localhost:5678")
        api_key = st.sidebar.text_input("API Key (선택사항)", value="", type="password")
        
        n8n_monitor = get_n8n_monitor(n8n_url, api_key)
        
        # 연결 상태 확인
        if n8n_monitor.check_connection():
            st.success("✅ n8n 서버에 연결됨")
            
            # 워크플로우 목록
            workflows = n8n_monitor.get_workflows()
            
            if workflows:
                st.subheader("📋 워크플로우 목록")
                
                # 워크플로우 테이블
                workflow_data = []
                for wf in workflows:
                    workflow_data.append({
                        "이름": wf.name,
                        "상태": "🟢 활성" if wf.status.value == "active" else "🔴 비활성",
                        "총 실행 수": wf.total_executions,
                        "성공률 (%)": f"{wf.success_rate:.1f}",
                        "평균 실행시간 (초)": f"{wf.avg_execution_time:.1f}",
                        "마지막 실행": wf.last_execution.strftime("%Y-%m-%d %H:%M") if wf.last_execution else "없음"
                    })
                
                workflow_df = pd.DataFrame(workflow_data)
                st.dataframe(workflow_df, use_container_width=True)
                
                # 실행 요약 통계
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 실행 통계 (최근 24시간)")
                    summary = n8n_monitor.get_workflow_execution_summary(24)
                    
                    summary_cols = st.columns(4)
                    with summary_cols[0]:
                        st.metric("총 실행", summary.get('total_executions', 0))
                    with summary_cols[1]:
                        st.metric("성공", summary.get('successful_executions', 0))
                    with summary_cols[2]:
                        st.metric("실패", summary.get('failed_executions', 0))
                    with summary_cols[3]:
                        st.metric("성공률", f"{summary.get('success_rate', 0):.1f}%")
                
                with col2:
                    st.subheader("🔄 최근 실행 내역")
                    recent_executions = n8n_monitor.get_recent_executions(10)
                    
                    if recent_executions:
                        exec_data = []
                        for exec_info in recent_executions:
                            status_icon = "✅" if exec_info.success else "❌"
                            exec_data.append({
                                "상태": f"{status_icon} {exec_info.status.value}",
                                "워크플로우": exec_info.workflow_name[:30] + "..." if len(exec_info.workflow_name) > 30 else exec_info.workflow_name,
                                "실행시간": f"{exec_info.execution_time:.1f}초" if exec_info.execution_time else "진행중",
                                "시작시간": exec_info.start_time.strftime("%H:%M:%S")
                            })
                        
                        exec_df = pd.DataFrame(exec_data)
                        st.dataframe(exec_df, use_container_width=True)
                    else:
                        st.info("최근 실행 내역이 없습니다.")
                
                # 워크플로우별 성능 차트
                if len(workflows) > 0:
                    st.subheader("📈 워크플로우 성능 분석")
                    
                    # 성공률 차트
                    success_rate_data = [(wf.name, wf.success_rate) for wf in workflows if wf.total_executions > 0]
                    if success_rate_data:
                        names, rates = zip(*success_rate_data)
                        
                        fig = px.bar(
                            x=list(names),
                            y=list(rates),
                            title="워크플로우별 성공률",
                            labels={'x': '워크플로우', 'y': '성공률 (%)'}
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("등록된 워크플로우가 없습니다.")
        
        else:
            st.error(f"❌ n8n 서버에 연결할 수 없습니다. ({n8n_url})")
            st.info("n8n 서버가 실행 중인지 확인하고 URL을 다시 입력해주세요.")
            
    except Exception as e:
        handle_error(e, "n8n 모니터링 중 오류가 발생했습니다.")


def display_database_monitoring():
    """데이터베이스 모니터링 표시"""
    st.header("🗄️ 데이터베이스 성능 모니터링")
    
    try:
        db_monitor = get_database_monitor()
        
        # 현재 데이터베이스 메트릭 수집
        current_metrics = db_monitor.collect_database_metrics()
        
        if current_metrics:
            # 기본 데이터베이스 정보
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "데이터베이스 크기",
                    f"{current_metrics.database_size_mb:.1f} MB",
                    help="데이터베이스 파일 크기"
                )
            
            with col2:
                st.metric(
                    "테이블 수",
                    current_metrics.table_count,
                    help="데이터베이스 내 테이블 개수"
                )
            
            with col3:
                st.metric(
                    "인덱스 수",
                    current_metrics.index_count,
                    help="데이터베이스 내 인덱스 개수"
                )
            
            with col4:
                response_color = "🔴" if current_metrics.query_execution_time > 100 else "🟡" if current_metrics.query_execution_time > 50 else "🟢"
                st.metric(
                    "쿼리 응답시간",
                    f"{response_color} {current_metrics.query_execution_time:.1f} ms",
                    help="테스트 쿼리 실행 시간"
                )
            
            # 성능 요약
            performance_summary = db_monitor.get_performance_summary(24)
            
            if 'error' not in performance_summary:
                st.subheader("📊 성능 분석 (최근 24시간)")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**데이터베이스 통계**")
                    db_stats = performance_summary.get('database_stats', {})
                    
                    stats_col1, stats_col2 = st.columns(2)
                    with stats_col1:
                        st.metric("평균 DB 크기", f"{db_stats.get('avg_size_mb', 0):.1f} MB")
                        st.metric("테이블 수", db_stats.get('table_count', 0))
                    
                    with stats_col2:
                        st.metric("인덱스 수", db_stats.get('index_count', 0))
                        st.metric("최대 테이블", db_stats.get('largest_table', 'unknown'))
                
                with col2:
                    st.markdown("**쿼리 성능**")
                    query_perf = performance_summary.get('query_performance', {})
                    
                    perf_col1, perf_col2 = st.columns(2)
                    with perf_col1:
                        st.metric("총 쿼리 수", query_perf.get('total_queries', 0))
                        st.metric("평균 실행시간", f"{query_perf.get('avg_execution_time', 0):.1f} ms")
                    
                    with perf_col2:
                        st.metric("슬로우 쿼리", query_perf.get('slow_queries_count', 0))
                        st.metric("캐시 히트율", f"{current_metrics.cache_hit_ratio:.1f}%")
                
                # 쿼리 타입별 성능 차트
                query_stats = query_perf.get('query_type_stats', {})
                if query_stats:
                    st.subheader("📈 쿼리 타입별 성능")
                    
                    # 쿼리 타입별 실행 시간 차트
                    query_types = list(query_stats.keys())
                    avg_times = [query_stats[qt]['avg_execution_time'] for qt in query_types]
                    query_counts = [query_stats[qt]['count'] for qt in query_types]
                    
                    fig = make_subplots(
                        rows=1, cols=2,
                        subplot_titles=('평균 실행시간', '쿼리 수'),
                        specs=[[{"secondary_y": False}, {"secondary_y": False}]]
                    )
                    
                    fig.add_trace(
                        go.Bar(x=query_types, y=avg_times, name="평균 실행시간 (ms)"),
                        row=1, col=1
                    )
                    
                    fig.add_trace(
                        go.Bar(x=query_types, y=query_counts, name="쿼리 수"),
                        row=1, col=2
                    )
                    
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                # 슬로우 쿼리 분석
                slow_query_analysis = performance_summary.get('slow_query_analysis', {})
                if slow_query_analysis:
                    st.subheader("🐌 슬로우 쿼리 분석")
                    
                    slow_data = []
                    for table, data in slow_query_analysis.items():
                        slow_data.append({
                            "테이블": table,
                            "슬로우 쿼리 수": data['count'],
                            "평균 시간 (ms)": f"{data['avg_time']:.1f}",
                            "최대 시간 (ms)": f"{data['max_time']:.1f}",
                            "쿼리 타입": ", ".join(data['query_types'])
                        })
                    
                    slow_df = pd.DataFrame(slow_data)
                    st.dataframe(slow_df, use_container_width=True)
        
        else:
            st.error("데이터베이스 메트릭을 수집할 수 없습니다.")
            
    except Exception as e:
        handle_error(e, "데이터베이스 모니터링 중 오류가 발생했습니다.")


def display_network_monitoring():
    """네트워크 모니터링 표시"""
    st.header("🌐 네트워크 및 API 모니터링")
    
    try:
        network_monitor = get_network_monitor()
        
        # 실시간 네트워크 상태
        real_time_stats = network_monitor.get_real_time_network_stats()
        
        if 'error' not in real_time_stats:
            st.subheader("📡 실시간 네트워크 상태")
            
            net_data = real_time_stats.get('network', {})
            api_data = real_time_stats.get('api', {})
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "활성 연결",
                    net_data.get('connections_established', 0),
                    help="현재 설정된 네트워크 연결 수"
                )
            
            with col2:
                st.metric(
                    "수신 속도",
                    f"{net_data.get('read_speed_mbps', 0):.2f} MB/s",
                    help="현재 네트워크 수신 속도"
                )
            
            with col3:
                st.metric(
                    "송신 속도",
                    f"{net_data.get('write_speed_mbps', 0):.2f} MB/s",
                    help="현재 네트워크 송신 속도"
                )
            
            with col4:
                success_rate = api_data.get('recent_success_rate', 100)
                rate_color = "🟢" if success_rate >= 95 else "🟡" if success_rate >= 80 else "🔴"
                st.metric(
                    "API 성공률",
                    f"{rate_color} {success_rate:.1f}%",
                    help="최근 5분간 API 호출 성공률"
                )
            
            # 네트워크 사용량 요약
            network_summary = network_monitor.get_network_summary(24)
            
            if 'error' not in network_summary:
                st.subheader("📊 네트워크 사용량 (최근 24시간)")
                
                traffic = network_summary.get('traffic_summary', {})
                connections = network_summary.get('connection_stats', {})
                speeds = network_summary.get('speed_stats', {})
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**데이터 트래픽**")
                    
                    traffic_col1, traffic_col2 = st.columns(2)
                    with traffic_col1:
                        st.metric("송신 데이터", f"{traffic.get('total_bytes_sent_mb', 0):.1f} MB")
                        st.metric("송신 패킷", f"{traffic.get('total_packets_sent', 0):,}")
                    
                    with traffic_col2:
                        st.metric("수신 데이터", f"{traffic.get('total_bytes_recv_mb', 0):.1f} MB")
                        st.metric("수신 패킷", f"{traffic.get('total_packets_recv', 0):,}")
                
                with col2:
                    st.markdown("**연결 통계**")
                    
                    conn_col1, conn_col2 = st.columns(2)
                    with conn_col1:
                        st.metric("현재 연결", connections.get('current_established', 0))
                        st.metric("평균 연결", f"{connections.get('avg_established', 0):.1f}")
                    
                    with conn_col2:
                        st.metric("최대 연결", connections.get('max_established', 0))
                        st.metric("리스닝 포트", connections.get('current_listening', 0))
            
            # API 모니터링
            api_summary = network_monitor.get_api_summary(24)
            
            if 'error' not in api_summary:
                st.subheader("🔌 API 모니터링 (최근 24시간)")
                
                overall_stats = api_summary.get('overall_stats', {})
                
                api_col1, api_col2, api_col3, api_col4 = st.columns(4)
                
                with api_col1:
                    st.metric("총 요청", overall_stats.get('total_requests', 0))
                
                with api_col2:
                    st.metric("성공 요청", overall_stats.get('successful_requests', 0))
                
                with api_col3:
                    st.metric("실패 요청", overall_stats.get('failed_requests', 0))
                
                with api_col4:
                    st.metric("평균 응답시간", f"{overall_stats.get('avg_response_time', 0):.1f} ms")
                
                # 엔드포인트별 통계
                endpoint_stats = api_summary.get('endpoint_stats', {})
                if endpoint_stats:
                    st.subheader("📊 엔드포인트별 성능")
                    
                    endpoint_data = []
                    for endpoint, stats in endpoint_stats.items():
                        endpoint_data.append({
                            "엔드포인트": endpoint,
                            "총 요청": stats['total_requests'],
                            "성공률 (%)": f"{stats['success_rate']:.1f}",
                            "평균 응답시간 (ms)": f"{stats['avg_response_time']:.1f}",
                            "최대 응답시간 (ms)": f"{stats['max_response_time']:.1f}",
                            "마지막 요청": stats['last_request'][:16] if isinstance(stats['last_request'], str) else "N/A"
                        })
                    
                    endpoint_df = pd.DataFrame(endpoint_data)
                    st.dataframe(endpoint_df, use_container_width=True)
                
                # 상태 코드 분포
                status_distribution = api_summary.get('status_code_distribution', {})
                if status_distribution:
                    st.subheader("📈 HTTP 상태 코드 분포")
                    
                    status_codes = list(status_distribution.keys())
                    status_counts = list(status_distribution.values())
                    
                    fig = px.pie(
                        values=status_counts,
                        names=status_codes,
                        title="HTTP 상태 코드 분포"
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.error("네트워크 통계를 가져올 수 없습니다.")
            
    except Exception as e:
        handle_error(e, "네트워크 모니터링 중 오류가 발생했습니다.")


def main():
    """메인 함수"""
    st.title("📊 실시간 시스템 모니터링 대시보드")
    st.markdown("---")
    
    # 사이드바 설정
    st.sidebar.title("⚙️ 모니터링 설정")
    
    # 자동 새로고침 설정
    auto_refresh = st.sidebar.checkbox("자동 새로고침 (30초)", value=True)
    if auto_refresh:
        time.sleep(30)
        st.rerun()
    
    # 새로고침 버튼
    if st.sidebar.button("🔄 수동 새로고침"):
        st.rerun()
    
    # 모니터링 섹션 선택
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 모니터링 섹션")
    
    show_system = st.sidebar.checkbox("시스템 리소스", value=True)
    show_n8n = st.sidebar.checkbox("n8n 워크플로우", value=True)
    show_database = st.sidebar.checkbox("데이터베이스", value=True)
    show_network = st.sidebar.checkbox("네트워크 & API", value=True)
    
    # 현재 시간 표시
    st.sidebar.markdown("---")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.sidebar.markdown(f"**마지막 업데이트:** {current_time}")
    
    # 모니터링 섹션 표시
    try:
        if show_system:
            display_system_overview()
            st.markdown("---")
        
        if show_n8n:
            display_n8n_monitoring()
            st.markdown("---")
        
        if show_database:
            display_database_monitoring()
            st.markdown("---")
        
        if show_network:
            display_network_monitoring()
            st.markdown("---")
        
        # 페이지 하단에 시스템 정보
        st.markdown("### 💡 시스템 정보")
        st.info(
            "이 대시보드는 실시간으로 시스템 리소스, GPU, n8n 워크플로우, "
            "데이터베이스 성능, 네트워크 및 API 상태를 모니터링합니다. "
            "문제 발생 시 자동으로 알림이 발송됩니다."
        )
        
    except Exception as e:
        handle_error(e, "모니터링 대시보드 로딩 중 오류가 발생했습니다.")


if __name__ == "__main__":
    main()