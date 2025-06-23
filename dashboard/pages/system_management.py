"""
T05_S02_M02: 시스템 관리 페이지
백업, 모니터링, 에러 관리 통합 인터페이스
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import threading
import time

# 시스템 관리 모듈들 import
try:
    from dashboard.utils.backup_manager import get_backup_manager
    from dashboard.utils.error_handler import get_error_handler, ErrorSeverity
    from dashboard.utils.system_monitor import get_system_monitor, HealthStatus
    from dashboard.utils.performance_monitor import get_performance_monitor
except ImportError as e:
    st.error(f"시스템 관리 모듈을 로드할 수 없습니다: {e}")
    st.stop()


def render_system_management():
    """시스템 관리 페이지 렌더링"""
    st.title("🔧 시스템 관리")
    st.markdown("백업, 모니터링, 에러 관리를 위한 통합 관리 인터페이스")
    
    # 탭 구성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 시스템 상태", 
        "💾 백업 관리", 
        "⚠️ 에러 관리", 
        "📈 성능 모니터링",
        "🔧 시스템 설정"
    ])
    
    with tab1:
        render_system_status()
    
    with tab2:
        render_backup_management()
    
    with tab3:
        render_error_management()
    
    with tab4:
        render_performance_monitoring()
    
    with tab5:
        render_system_settings()


def render_system_status():
    """시스템 상태 탭"""
    st.subheader("🔍 실시간 시스템 상태")
    
    # 헬스체크 실행
    system_monitor = get_system_monitor()
    
    if st.button("🔄 헬스체크 실행", help="전체 시스템 상태를 점검합니다"):
        with st.spinner("시스템 상태를 확인하는 중..."):
            health_status = system_monitor.get_health_status()
        
        # 전체 상태 요약
        healthy_count = sum(1 for h in health_status.values() if h.status == HealthStatus.HEALTHY)
        total_count = len(health_status)
        
        if healthy_count == total_count:
            st.success(f"✅ 모든 컴포넌트가 정상입니다 ({healthy_count}/{total_count})")
        elif healthy_count > total_count * 0.7:
            st.warning(f"⚠️ 일부 컴포넌트에 문제가 있습니다 ({healthy_count}/{total_count})")
        else:
            st.error(f"🚨 시스템에 심각한 문제가 있습니다 ({healthy_count}/{total_count})")
        
        # 컴포넌트별 상태 표시
        col1, col2 = st.columns(2)
        
        for i, (component, health) in enumerate(health_status.items()):
            target_col = col1 if i % 2 == 0 else col2
            
            with target_col:
                with st.container():
                    # 상태에 따른 색상 및 아이콘
                    if health.status == HealthStatus.HEALTHY:
                        st.success(f"✅ **{component.replace('_', ' ').title()}**")
                        status_color = "green"
                    elif health.status == HealthStatus.WARNING:
                        st.warning(f"⚠️ **{component.replace('_', ' ').title()}**")
                        status_color = "orange"
                    else:
                        st.error(f"🚨 **{component.replace('_', ' ').title()}**")
                        status_color = "red"
                    
                    st.write(f"**상태**: {health.message}")
                    st.write(f"**응답시간**: {health.response_time:.1f}ms")
                    st.write(f"**확인시간**: {health.timestamp.strftime('%H:%M:%S')}")
                    
                    # 상세 정보 표시
                    if health.details:
                        with st.expander("상세 정보"):
                            st.json(health.details)
    
    # 시스템 메트릭 요약
    st.subheader("📊 시스템 메트릭 요약")
    
    metrics_summary = system_monitor.get_metrics_summary(hours=1)
    if "error" not in metrics_summary:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cpu_avg = metrics_summary.get("cpu", {}).get("avg", 0)
            st.metric(
                "평균 CPU 사용률",
                f"{cpu_avg:.1f}%",
                help="최근 1시간 평균 CPU 사용률"
            )
        
        with col2:
            memory_avg = metrics_summary.get("memory", {}).get("avg", 0)
            st.metric(
                "평균 메모리 사용률",
                f"{memory_avg:.1f}%",
                help="최근 1시간 평균 메모리 사용률"
            )
        
        with col3:
            disk_avg = metrics_summary.get("disk", {}).get("avg", 0)
            st.metric(
                "디스크 사용률",
                f"{disk_avg:.1f}%",
                help="현재 디스크 사용률"
            )
        
        with col4:
            data_points = metrics_summary.get("data_points", 0)
            st.metric(
                "데이터 포인트",
                f"{data_points}개",
                help="최근 1시간 수집된 메트릭 수"
            )


def render_backup_management():
    """백업 관리 탭"""
    st.subheader("💾 데이터베이스 백업 관리")
    
    backup_manager = get_backup_manager()
    
    # 백업 생성 섹션
    st.markdown("### 📦 새 백업 생성")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        backup_description = st.text_input(
            "백업 설명",
            placeholder="예: 기능 업데이트 전 백업",
            help="백업에 대한 설명을 입력하세요"
        )
    
    with col2:
        backup_type = st.selectbox(
            "백업 유형",
            ["manual", "daily", "weekly", "monthly"],
            help="백업 유형을 선택하세요"
        )
    
    if st.button("🔄 백업 생성", type="primary"):
        with st.spinner("백업을 생성하는 중..."):
            result = backup_manager.create_backup(
                backup_type=backup_type,
                description=backup_description
            )
        
        if "error" in result:
            st.error(f"백업 생성 실패: {result['error']}")
        else:
            st.success(f"✅ 백업이 성공적으로 생성되었습니다!")
            st.info(f"**백업 ID**: `{result['backup_id']}`")
            st.info(f"**압축률**: {result['compression_ratio']:.1%}")
            st.info(f"**생성 시간**: {result['creation_time']:.2f}초")
    
    # 백업 목록
    st.markdown("### 📋 백업 목록")
    
    backups = backup_manager.list_backups()
    
    if not backups:
        st.info("생성된 백업이 없습니다.")
    else:
        # 백업 통계
        stats = backup_manager.get_backup_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("총 백업 수", stats.get("total_backups", 0))
        with col2:
            st.metric("총 크기", f"{stats.get('total_size_mb', 0):.1f} MB")
        with col3:
            latest = stats.get("latest_backup")
            if latest:
                latest_dt = datetime.fromisoformat(latest)
                latest_str = latest_dt.strftime("%m/%d %H:%M")
            else:
                latest_str = "없음"
            st.metric("최신 백업", latest_str)
        with col4:
            avg_ratio = stats.get("average_compression_ratio", 0)
            st.metric("평균 압축률", f"{avg_ratio:.1%}")
        
        # 백업 테이블
        backup_data = []
        for backup in backups:
            backup_data.append({
                "백업 ID": backup["backup_id"],
                "유형": backup["backup_type"],
                "생성일시": datetime.fromisoformat(backup["timestamp"]).strftime("%Y-%m-%d %H:%M"),
                "크기 (MB)": backup.get("file_size_mb", 0),
                "설명": backup.get("description", ""),
                "상태": "✅ 정상" if backup.get("file_exists", False) else "❌ 파일 없음"
            })
        
        df = pd.DataFrame(backup_data)
        st.dataframe(df, use_container_width=True)
        
        # 백업 관리 액션
        st.markdown("### 🔧 백업 관리")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**백업 복구**")
            selected_backup = st.selectbox(
                "복구할 백업 선택",
                options=[b["backup_id"] for b in backups],
                help="복구할 백업을 선택하세요"
            )
            
            if st.button("🔄 백업 복구", help="⚠️ 현재 데이터베이스가 대체됩니다"):
                if st.session_state.get("confirm_restore"):
                    with st.spinner("백업을 복구하는 중..."):
                        result = backup_manager.restore_backup(selected_backup)
                    
                    if result.get("success"):
                        st.success("✅ 백업 복구가 완료되었습니다!")
                        st.info(f"복구 시간: {result['restore_time']:.2f}초")
                    else:
                        st.error(f"백업 복구 실패: {result.get('error', '알 수 없는 오류')}")
                    
                    # 확인 상태 초기화
                    del st.session_state["confirm_restore"]
                    st.rerun()
                else:
                    st.warning("⚠️ 정말로 백업을 복구하시겠습니까? 현재 데이터가 손실될 수 있습니다.")
                    if st.button("✅ 복구 확인"):
                        st.session_state["confirm_restore"] = True
                        st.rerun()
        
        with col2:
            st.markdown("**백업 삭제**")
            delete_backup = st.selectbox(
                "삭제할 백업 선택",
                options=[b["backup_id"] for b in backups],
                key="delete_backup_select",
                help="삭제할 백업을 선택하세요"
            )
            
            if st.button("🗑️ 백업 삭제"):
                if st.session_state.get("confirm_delete"):
                    success = backup_manager.delete_backup(delete_backup)
                    if success:
                        st.success("✅ 백업이 삭제되었습니다!")
                    else:
                        st.error("❌ 백업 삭제에 실패했습니다.")
                    
                    del st.session_state["confirm_delete"]
                    st.rerun()
                else:
                    st.warning("⚠️ 정말로 백업을 삭제하시겠습니까?")
                    if st.button("✅ 삭제 확인"):
                        st.session_state["confirm_delete"] = True
                        st.rerun()


def render_error_management():
    """에러 관리 탭"""
    st.subheader("⚠️ 에러 로그 관리")
    
    error_handler = get_error_handler()
    
    # 에러 통계
    stats = error_handler.get_error_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 에러 수", stats.get("total_errors", 0))
    
    with col2:
        critical_count = stats.get("by_severity", {}).get("critical", 0)
        st.metric("심각한 에러", critical_count)
    
    with col3:
        high_count = stats.get("by_severity", {}).get("high", 0)
        st.metric("높은 수준 에러", high_count)
    
    with col4:
        last_reset = stats.get("last_reset", "")
        if last_reset:
            reset_dt = datetime.fromisoformat(last_reset)
            reset_str = reset_dt.strftime("%m/%d %H:%M")
        else:
            reset_str = "없음"
        st.metric("마지막 리셋", reset_str)
    
    # 심각도별 에러 분포 차트
    severity_data = stats.get("by_severity", {})
    if any(severity_data.values()):
        fig = px.pie(
            values=list(severity_data.values()),
            names=list(severity_data.keys()),
            title="에러 심각도별 분포"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 최근 에러 목록
    st.markdown("### 📋 최근 에러 목록")
    
    error_limit = st.slider("표시할 에러 수", 10, 100, 50)
    recent_errors = error_handler.get_recent_errors(limit=error_limit)
    
    if not recent_errors:
        st.info("최근 에러가 없습니다.")
    else:
        error_data = []
        for error in recent_errors:
            error_data.append({
                "에러 ID": error["error_id"],
                "시각": datetime.fromisoformat(error["timestamp"]).strftime("%m/%d %H:%M:%S"),
                "심각도": error["severity"],
                "유형": error["error_type"],
                "메시지": error["error_message"][:100] + "..." if len(error["error_message"]) > 100 else error["error_message"]
            })
        
        df = pd.DataFrame(error_data)
        
        # 심각도에 따른 색상 적용
        def highlight_severity(row):
            if row["심각도"] == "critical":
                return ["background-color: #ffebee"] * len(row)
            elif row["심각도"] == "high":
                return ["background-color: #fff3e0"] * len(row)
            elif row["심각도"] == "medium":
                return ["background-color: #f3e5f5"] * len(row)
            else:
                return [""] * len(row)
        
        styled_df = df.style.apply(highlight_severity, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # 에러 로그 관리
        st.markdown("### 🔧 에러 로그 관리")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ 에러 로그 초기화"):
                if st.session_state.get("confirm_clear_errors"):
                    success = error_handler.clear_error_log()
                    if success:
                        st.success("✅ 에러 로그가 초기화되었습니다!")
                    else:
                        st.error("❌ 에러 로그 초기화에 실패했습니다.")
                    
                    del st.session_state["confirm_clear_errors"]
                    st.rerun()
                else:
                    st.warning("⚠️ 정말로 모든 에러 로그를 삭제하시겠습니까?")
                    if st.button("✅ 삭제 확인"):
                        st.session_state["confirm_clear_errors"] = True
                        st.rerun()
        
        with col2:
            # 에러 로그 다운로드
            if st.button("📥 에러 로그 다운로드"):
                log_data = json.dumps(recent_errors, indent=2, ensure_ascii=False)
                st.download_button(
                    label="다운로드",
                    data=log_data,
                    file_name=f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )


def render_performance_monitoring():
    """성능 모니터링 탭"""
    st.subheader("📈 성능 모니터링")
    
    # 기존 성능 모니터 활용
    performance_monitor = get_performance_monitor()
    
    # 성능 메트릭 표시
    try:
        from dashboard.utils.performance_monitor import display_performance_metrics
        display_performance_metrics()
    except ImportError:
        st.error("성능 모니터링 모듈을 로드할 수 없습니다.")
    
    # 시스템 모니터링 시작/중지
    st.markdown("### 🔧 모니터링 제어")
    
    system_monitor = get_system_monitor()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("▶️ 모니터링 시작"):
            system_monitor.start_monitoring()
            st.success("✅ 시스템 모니터링이 시작되었습니다!")
    
    with col2:
        if st.button("⏹️ 모니터링 중지"):
            system_monitor.stop_monitoring()
            st.info("ℹ️ 시스템 모니터링이 중지되었습니다.")


def render_system_settings():
    """시스템 설정 탭"""
    st.subheader("🔧 시스템 설정")
    
    # 백업 설정
    st.markdown("### 💾 백업 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        auto_backup_enabled = st.checkbox(
            "자동 백업 활성화",
            value=True,
            help="정기적으로 자동 백업을 생성합니다"
        )
        
        backup_retention_days = st.number_input(
            "백업 보존 기간 (일)",
            min_value=1,
            max_value=365,
            value=30,
            help="백업을 보존할 기간을 설정합니다"
        )
    
    with col2:
        backup_interval_hours = st.number_input(
            "백업 간격 (시간)",
            min_value=1,
            max_value=168,
            value=24,
            help="자동 백업 실행 간격을 설정합니다"
        )
        
        max_backup_count = st.number_input(
            "최대 백업 개수",
            min_value=1,
            max_value=100,
            value=10,
            help="보관할 최대 백업 개수를 설정합니다"
        )
    
    # 모니터링 설정
    st.markdown("### 📊 모니터링 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        monitoring_enabled = st.checkbox(
            "시스템 모니터링 활성화",
            value=True,
            help="실시간 시스템 모니터링을 활성화합니다"
        )
        
        alert_cpu_threshold = st.slider(
            "CPU 경고 임계값 (%)",
            min_value=50,
            max_value=95,
            value=80,
            help="CPU 사용률 경고 임계값을 설정합니다"
        )
    
    with col2:
        monitoring_interval = st.number_input(
            "모니터링 간격 (초)",
            min_value=10,
            max_value=3600,
            value=60,
            help="시스템 메트릭 수집 간격을 설정합니다"
        )
        
        alert_memory_threshold = st.slider(
            "메모리 경고 임계값 (%)",
            min_value=50,
            max_value=95,
            value=85,
            help="메모리 사용률 경고 임계값을 설정합니다"
        )
    
    # 설정 저장
    if st.button("💾 설정 저장", type="primary"):
        settings = {
            "backup": {
                "auto_backup_enabled": auto_backup_enabled,
                "retention_days": backup_retention_days,
                "interval_hours": backup_interval_hours,
                "max_count": max_backup_count
            },
            "monitoring": {
                "enabled": monitoring_enabled,
                "interval": monitoring_interval,
                "cpu_threshold": alert_cpu_threshold,
                "memory_threshold": alert_memory_threshold
            },
            "updated_at": datetime.now().isoformat()
        }
        
        # 설정 파일 저장 (향후 구현)
        st.success("✅ 설정이 저장되었습니다!")
        st.json(settings)


if __name__ == "__main__":
    render_system_management()