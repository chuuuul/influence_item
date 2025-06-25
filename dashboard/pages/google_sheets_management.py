"""
Google Sheets 관리 대시보드

PRD 2.1 요구사항에 따른 Google Sheets 연동 관리 인터페이스:
- 연결 상태 확인
- 채널 목록 실시간 동기화
- 신규 채널 후보 검토
- 승인/제외 처리 상태 모니터링
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from src.integrations.google_sheets_integration import GoogleSheetsIntegration
    from dashboard.utils.env_loader import load_env_file
    SHEETS_AVAILABLE = True
    # 환경변수 로드
    load_env_file()
except ImportError as e:
    st.error(f"Google Sheets 연동 모듈 로드 실패: {str(e)}")
    SHEETS_AVAILABLE = False


def display_connection_status():
    """연결 상태 표시"""
    st.subheader("🔗 Google Sheets 연결 상태")
    
    if not SHEETS_AVAILABLE:
        st.error("Google Sheets 연동 모듈이 사용 불가능합니다.")
        return None
    
    try:
        # Google Sheets 통합 초기화
        sheets_integration = GoogleSheetsIntegration()
        
        # 연결 검증
        with st.spinner("연결 상태 확인 중..."):
            info = sheets_integration.get_spreadsheet_info()
        
        # 결과 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success("✅ 인증 성공")
        
        with col2:
            st.success("✅ 스프레드시트 접근")
            st.caption(f"제목: {info['title']}")
        
        with col3:
            st.success("✅ 읽기/쓰기 권한")
        
        # 워크시트 정보
        st.write("**접근 가능한 시트:**")
        for sheet_name in info['sheets']:
            st.write(f"- {sheet_name}")
        
        # 스프레드시트 링크
        st.markdown(f"🔗 [Google Sheets에서 보기]({info['url']})")
        
        return sheets_integration
        
    except Exception as e:
        st.error(f"연결 확인 중 오류: {str(e)}")
        st.info("환경변수 GOOGLE_SHEETS_SPREADSHEET_ID와 인증 파일을 확인하세요.")
        return None


def sheets_configuration():
    """Google Sheets 설정"""
    st.subheader("⚙️ Google Sheets 설정")
    
    with st.form("sheets_config_form"):
        st.write("스프레드시트 설정")
        
        spreadsheet_id = st.text_input(
            "스프레드시트 ID",
            value=st.session_state.get('spreadsheet_id', ''),
            help="Google Sheets URL에서 `/d/SPREADSHEET_ID/edit` 부분의 ID"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            channels_sheet = st.text_input(
                "승인된 채널 시트명",
                value="승인된 채널"
            )
        
        with col2:
            candidates_sheet = st.text_input(
                "후보 채널 시트명", 
                value="후보 채널"
            )
        
        credentials_path = st.text_input(
            "인증 파일 경로",
            value="credentials/google_sheets_credentials.json"
        )
        
        submitted = st.form_submit_button("설정 저장")
        
        if submitted and spreadsheet_id:
            try:
                config = SheetsConfig(
                    spreadsheet_id=spreadsheet_id,
                    channels_sheet_name=channels_sheet,
                    candidates_sheet_name=candidates_sheet,
                    credentials_path=credentials_path
                )
                
                st.session_state.sheets_config = config
                st.session_state.spreadsheet_id = spreadsheet_id
                st.success("설정이 저장되었습니다!")
                st.rerun()
                
            except Exception as e:
                st.error(f"설정 저장 실패: {str(e)}")


def display_sync_dashboard(sheets_integration):
    """동기화 대시보드"""
    st.subheader("🔄 동기화 대시보드")
    
    try:
        # 동기화 통계
        stats = sheets_integration.get_sync_statistics(days=7)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 동기화", stats['total_syncs'])
        
        with col2:
            st.metric("성공한 동기화", stats['successful_syncs'])
        
        with col3:
            success_rate = (stats['successful_syncs'] / stats['total_syncs'] * 100) if stats['total_syncs'] > 0 else 0
            st.metric("성공률", f"{success_rate:.1f}%")
        
        with col4:
            st.metric("최근 오류", len(stats['recent_errors']))
        
        # 동기화 유형별 통계
        if stats['sync_breakdown']:
            st.write("**동기화 유형별 통계 (최근 7일)**")
            
            breakdown_data = []
            for sync_type, statuses in stats['sync_breakdown'].items():
                for status, data in statuses.items():
                    breakdown_data.append({
                        '동기화 유형': sync_type,
                        '상태': status,
                        '횟수': data['count'],
                        '처리된 레코드': data['processed'],
                        '동기화된 레코드': data['synced']
                    })
            
            if breakdown_data:
                df = pd.DataFrame(breakdown_data)
                st.dataframe(df, use_container_width=True)
                
                # 차트
                fig = px.bar(df, x='동기화 유형', y='횟수', color='상태', 
                           title="동기화 유형별 실행 횟수")
                st.plotly_chart(fig, use_container_width=True)
        
        # 최근 오류
        if stats['recent_errors']:
            st.write("**최근 오류**")
            error_df = pd.DataFrame(stats['recent_errors'])
            st.dataframe(error_df, use_container_width=True)
        
    except Exception as e:
        st.error(f"동기화 통계 로드 실패: {str(e)}")


def display_candidates_management(sheets_integration):
    """채널 후보 관리"""
    st.subheader("📋 채널 후보 관리")
    
    try:
        # 채널 후보 조회
        candidates = sheets_integration.get_channel_candidates()
        
        if not candidates:
            st.info("등록된 채널 후보가 없습니다.")
            return
        
        # 상태별 필터링
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pending_count = len([c for c in candidates if c['review_status'] == 'pending'])
            st.metric("검토 대기", pending_count)
        
        with col2:
            approved_count = len([c for c in candidates if c['review_status'] == 'approved'])
            st.metric("승인됨", approved_count)
        
        with col3:
            rejected_count = len([c for c in candidates if c['review_status'] == 'rejected'])
            st.metric("거부됨", rejected_count)
        
        # 필터 옵션
        status_filter = st.selectbox(
            "상태별 필터",
            options=['전체', 'pending', 'approved', 'rejected'],
            format_func=lambda x: {
                '전체': '전체', 'pending': '검토 대기', 
                'approved': '승인됨', 'rejected': '거부됨'
            }[x]
        )
        
        # 데이터 필터링
        if status_filter != '전체':
            filtered_candidates = [c for c in candidates if c['review_status'] == status_filter]
        else:
            filtered_candidates = candidates
        
        # 데이터프레임 생성
        if filtered_candidates:
            df = pd.DataFrame(filtered_candidates)
            
            # 컬럼 한글화
            df_display = df[['channel_name', 'channel_type', 'discovery_score', 
                           'discovery_reason', 'review_status', 'reviewed_by', 'notes']].copy()
            df_display.columns = ['채널명', '채널유형', '발견점수', '발견사유', '검토상태', '검토자', '비고']
            
            # 채널유형 한글화
            df_display['채널유형'] = df_display['채널유형'].map({
                'personal': '개인채널',
                'media': '미디어채널'
            })
            
            # 검토상태 한글화
            df_display['검토상태'] = df_display['검토상태'].map({
                'pending': '검토 대기',
                'approved': '승인됨', 
                'rejected': '거부됨'
            })
            
            st.dataframe(df_display, use_container_width=True)
            
            # 점수 분포 차트
            if len(filtered_candidates) > 1:
                fig = px.histogram(df, x='discovery_score', 
                                 title="채널 후보 발견 점수 분포",
                                 labels={'discovery_score': '발견 점수', 'count': '개수'})
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"'{status_filter}' 상태의 채널 후보가 없습니다.")
        
    except Exception as e:
        st.error(f"채널 후보 로드 실패: {str(e)}")


def display_sync_controls(sheets_integration):
    """동기화 제어"""
    st.subheader("🎛️ 동기화 제어")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 전체 동기화", use_container_width=True):
            with st.spinner("전체 동기화 실행 중..."):
                try:
                    results = sheets_integration.full_sync()
                    
                    success_count = sum(results.values())
                    if success_count >= 2:
                        st.success(f"전체 동기화 성공: {success_count}/3")
                    else:
                        st.warning(f"부분 동기화: {success_count}/3")
                    
                    st.json(results)
                    
                except Exception as e:
                    st.error(f"전체 동기화 실패: {str(e)}")
    
    with col2:
        if st.button("📤 후보 업로드", use_container_width=True):
            with st.spinner("채널 후보 업로드 중..."):
                try:
                    result = sheets_integration.sync_channel_candidates_to_sheets()
                    if result:
                        st.success("채널 후보 업로드 성공")
                    else:
                        st.error("채널 후보 업로드 실패")
                        
                except Exception as e:
                    st.error(f"후보 업로드 실패: {str(e)}")
    
    with col3:
        if st.button("📥 검토 다운로드", use_container_width=True):
            with st.spinner("검토 결과 다운로드 중..."):
                try:
                    result = sheets_integration.sync_reviews_from_sheets()
                    if result:
                        st.success("검토 결과 동기화 성공")
                    else:
                        st.error("검토 결과 동기화 실패")
                        
                except Exception as e:
                    st.error(f"검토 다운로드 실패: {str(e)}")
    
    # 실시간 동기화 설정
    st.write("**실시간 동기화 설정**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        sync_interval = st.slider("동기화 간격 (분)", min_value=1, max_value=60, value=5)
    
    with col2:
        if st.button("🚀 실시간 동기화 시작"):
            with st.spinner("실시간 동기화 실행 중..."):
                try:
                    result = sheets_integration.real_time_sync(sync_interval_minutes=sync_interval)
                    if result:
                        st.success("실시간 동기화 성공")
                    else:
                        st.warning("실시간 동기화 부분 실패")
                        
                except Exception as e:
                    st.error(f"실시간 동기화 실패: {str(e)}")


def display_changes_monitor(sheets_integration):
    """변경사항 모니터링"""
    st.subheader("👀 변경사항 모니터링")
    
    try:
        with st.spinner("변경사항 확인 중..."):
            changes = sheets_integration.monitor_sheets_changes()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("새로운 승인", len(changes['new_approvals']))
        
        with col2:
            st.metric("새로운 거부", len(changes['new_rejections']))
        
        with col3:
            st.metric("검토 대기", changes['pending_reviews'])
        
        # 새로운 승인
        if changes['new_approvals']:
            st.write("**새로운 승인**")
            approvals_df = pd.DataFrame(changes['new_approvals'])
            approvals_df.columns = ['채널ID', '채널명', '비고', '검토자']
            st.dataframe(approvals_df, use_container_width=True)
        
        # 새로운 거부
        if changes['new_rejections']:
            st.write("**새로운 거부**")
            rejections_df = pd.DataFrame(changes['new_rejections'])
            rejections_df.columns = ['채널ID', '채널명', '비고', '검토자']
            st.dataframe(rejections_df, use_container_width=True)
        
        # 마지막 업데이트 시간
        st.caption(f"마지막 확인: {changes['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        st.error(f"변경사항 모니터링 실패: {str(e)}")


def main():
    """메인 함수"""
    st.title("📊 Google Sheets 연동 관리")
    st.markdown("PRD 2.1 요구사항에 따른 채널 목록 및 후보 관리")
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["연결 설정", "동기화 대시보드", "채널 후보 관리", "동기화 제어", "변경사항 모니터링"]
    )
    
    # 설정 메뉴
    if menu == "연결 설정":
        sheets_configuration()
        st.divider()
        display_connection_status()
    
    else:
        # 다른 메뉴는 연결이 필요
        if 'sheets_config' not in st.session_state:
            st.warning("먼저 Google Sheets 설정을 완료하세요.")
            st.stop()
        
        try:
            sheets_integration = SheetsIntegration(st.session_state.sheets_config)
            
            if menu == "동기화 대시보드":
                display_sync_dashboard(sheets_integration)
            
            elif menu == "채널 후보 관리":
                display_candidates_management(sheets_integration)
            
            elif menu == "동기화 제어":
                display_sync_controls(sheets_integration)
            
            elif menu == "변경사항 모니터링":
                display_changes_monitor(sheets_integration)
        
        except Exception as e:
            st.error(f"Google Sheets 연동 초기화 실패: {str(e)}")
            st.info("설정을 다시 확인하고 인증 파일이 올바른지 확인하세요.")


if __name__ == "__main__":
    main()