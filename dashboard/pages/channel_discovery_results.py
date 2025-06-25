"""
채널 탐색 결과 관리 대시보드

Google Sheets 통합 및 Slack 알림이 포함된 채널 탐색 결과 관리 인터페이스
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
    from src.integrations.slack_integration import SlackIntegration
    from dashboard.utils.env_loader import load_env_file
    INTEGRATIONS_AVAILABLE = True
    # 환경변수 로드
    load_env_file()
except ImportError as e:
    st.error(f"통합 모듈 로드 실패: {str(e)}")
    INTEGRATIONS_AVAILABLE = False


def display_discovery_statistics():
    """채널 탐색 통계 표시"""
    st.subheader("📊 채널 탐색 통계")
    
    if not INTEGRATIONS_AVAILABLE:
        st.error("통합 모듈이 사용 불가능합니다.")
        return
    
    try:
        sheets = GoogleSheetsIntegration()
        stats = sheets.get_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 탐색 결과", stats['total_discoveries'])
        
        with col2:
            st.metric("고유 채널", stats['unique_channels'])
        
        with col3:
            st.metric("평균 점수", f"{stats['average_score']:.1f}")
        
        with col4:
            st.metric("고득점 후보", stats['high_score_candidates'])
        
        # 추가 통계
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("인증된 채널", stats['verified_count'])
        
        with col2:
            last_discovery = stats['last_discovery']
            if last_discovery:
                st.metric("최근 탐색", last_discovery.split()[0])  # 날짜만 표시
            else:
                st.metric("최근 탐색", "없음")
        
    except Exception as e:
        st.error(f"통계 조회 실패: {str(e)}")


def display_recent_discoveries():
    """최근 탐색 결과 표시"""
    st.subheader("🔍 최근 탐색 결과")
    
    if not INTEGRATIONS_AVAILABLE:
        st.error("통합 모듈이 사용 불가능합니다.")
        return
    
    try:
        sheets = GoogleSheetsIntegration()
        
        # 조회 옵션
        col1, col2 = st.columns(2)
        
        with col1:
            limit = st.slider("조회할 결과 수", min_value=10, max_value=100, value=20)
        
        with col2:
            min_score = st.slider("최소 점수", min_value=0, max_value=100, value=50)
        
        # 데이터 조회
        discoveries = sheets.get_latest_discoveries(limit=limit)
        
        if not discoveries:
            st.info("탐색 결과가 없습니다.")
            return
        
        # 점수 필터링
        filtered_discoveries = [
            d for d in discoveries 
            if float(d.get('총점수', 0)) >= min_score
        ]
        
        if not filtered_discoveries:
            st.warning(f"점수 {min_score}점 이상의 결과가 없습니다.")
            return
        
        st.info(f"{len(filtered_discoveries)}개 결과 표시 (전체 {len(discoveries)}개 중)")
        
        # 데이터프레임 생성
        df = pd.DataFrame(filtered_discoveries)
        
        # 주요 컬럼만 표시
        display_columns = ['발견일시', '채널명', '구독자수', '총점수', '인증여부', '국가']
        available_columns = [col for col in display_columns if col in df.columns]
        
        if available_columns:
            df_display = df[available_columns].copy()
            
            # 구독자수 포맷팅
            if '구독자수' in df_display.columns:
                df_display['구독자수'] = df_display['구독자수'].apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) and str(x).isdigit() else x
                )
            
            # 점수 포맷팅
            if '총점수' in df_display.columns:
                df_display['총점수'] = df_display['총점수'].apply(
                    lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x).replace('.', '').isdigit() else x
                )
            
            st.dataframe(df_display, use_container_width=True)
            
            # 점수 분포 차트
            if len(filtered_discoveries) > 1 and '총점수' in df.columns:
                scores = [float(d.get('총점수', 0)) for d in filtered_discoveries]
                fig = px.histogram(
                    x=scores,
                    title="점수 분포",
                    labels={'x': '총점수', 'y': '개수'},
                    nbins=20
                )
                st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"최근 탐색 결과 조회 실패: {str(e)}")


def display_manual_trigger():
    """수동 채널 탐색 실행"""
    st.subheader("🚀 수동 채널 탐색")
    
    with st.form("manual_discovery_form"):
        st.write("탐색 파라미터 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            keywords = st.text_area(
                "검색 키워드 (줄바꿈으로 구분)",
                value="아이유\n뷰티\n패션\n메이크업",
                height=100
            )
            
            days_back = st.slider("검색 기간 (일)", min_value=1, max_value=30, value=7)
        
        with col2:
            max_candidates = st.slider("최대 후보 수", min_value=10, max_value=100, value=20)
            min_score = st.slider("최소 점수", min_value=0, max_value=100, value=40)
        
        submitted = st.form_submit_button("🔍 탐색 시작", use_container_width=True)
        
        if submitted:
            # 키워드 파싱
            keyword_list = [kw.strip() for kw in keywords.split('\n') if kw.strip()]
            
            if not keyword_list:
                st.error("최소 1개 이상의 키워드를 입력하세요.")
                return
            
            # API 호출
            import requests
            import os
            
            api_url = os.getenv('CHANNEL_DISCOVERY_API_URL', 'http://localhost:5001')
            
            payload = {
                "keywords": keyword_list,
                "days_back": days_back,
                "max_candidates": max_candidates,
                "min_score": min_score
            }
            
            with st.spinner("채널 탐색 실행 중..."):
                try:
                    response = requests.post(
                        f"{api_url}/discover",
                        json=payload,
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        candidates = result.get('candidates', [])
                        
                        st.success(f"탐색 완료! {len(candidates)}개 후보 발견")
                        
                        # 결과 통계
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("실행 시간", f"{result.get('execution_time_seconds', 0):.1f}초")
                        
                        with col2:
                            high_score = len([c for c in candidates if c.get('total_score', 0) >= 70])
                            st.metric("고득점 후보", high_score)
                        
                        with col3:
                            verified = len([c for c in candidates if c.get('verified', False)])
                            st.metric("인증된 채널", verified)
                        
                        # Google Sheets 저장
                        if candidates and INTEGRATIONS_AVAILABLE:
                            try:
                                sheets = GoogleSheetsIntegration()
                                session_info = {
                                    'session_id': result.get('session_id', 'manual'),
                                    'execution_time': result.get('execution_time_seconds', 0)
                                }
                                
                                if sheets.save_channel_discovery_results(candidates, session_info):
                                    st.success("✅ Google Sheets에 결과 저장 완료")
                                else:
                                    st.warning("⚠️ Google Sheets 저장 실패")
                                
                                # Slack 알림
                                try:
                                    slack = SlackIntegration()
                                    if slack.send_channel_discovery_results(candidates, session_info):
                                        st.success("✅ Slack 알림 전송 완료")
                                    else:
                                        st.warning("⚠️ Slack 알림 전송 실패")
                                except Exception as slack_error:
                                    st.warning(f"⚠️ Slack 알림 실패: {str(slack_error)}")
                                
                            except Exception as save_error:
                                st.error(f"❌ 결과 저장 실패: {str(save_error)}")
                        
                        # 결과 표시
                        if candidates:
                            st.write("**상위 후보들:**")
                            for i, candidate in enumerate(candidates[:5], 1):
                                name = candidate.get('channel_name', 'Unknown')
                                score = candidate.get('total_score', 0)
                                subscribers = candidate.get('subscriber_count', 0)
                                verified = "✓" if candidate.get('verified', False) else "✗"
                                url = candidate.get('channel_url', '')
                                
                                if url:
                                    st.write(f"{i}. [{name}]({url}) - {score:.1f}점, {subscribers:,}명 {verified}")
                                else:
                                    st.write(f"{i}. {name} - {score:.1f}점, {subscribers:,}명 {verified}")
                    
                    else:
                        st.error(f"API 요청 실패: {response.status_code}")
                        st.text(response.text)
                
                except requests.exceptions.RequestException as e:
                    st.error(f"API 연결 실패: {str(e)}")
                    st.info("API 서버가 실행 중인지 확인하세요.")


def display_data_management():
    """데이터 관리"""
    st.subheader("🗄️ 데이터 관리")
    
    if not INTEGRATIONS_AVAILABLE:
        st.error("통합 모듈이 사용 불가능합니다.")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 통계 새로고침", use_container_width=True):
            with st.spinner("통계 업데이트 중..."):
                try:
                    sheets = GoogleSheetsIntegration()
                    stats = sheets.get_statistics()
                    st.success("통계 업데이트 완료")
                    st.json(stats)
                except Exception as e:
                    st.error(f"통계 업데이트 실패: {str(e)}")
    
    with col2:
        days_to_keep = st.number_input("보관 기간 (일)", min_value=1, max_value=365, value=30)
        if st.button("🧹 오래된 데이터 정리", use_container_width=True):
            with st.spinner("데이터 정리 중..."):
                try:
                    sheets = GoogleSheetsIntegration()
                    removed_count = sheets.cleanup_old_data(days_to_keep)
                    st.success(f"{removed_count}개 오래된 레코드 정리 완료")
                except Exception as e:
                    st.error(f"데이터 정리 실패: {str(e)}")
    
    with col3:
        if st.button("🔔 테스트 알림", use_container_width=True):
            with st.spinner("테스트 알림 전송 중..."):
                try:
                    slack = SlackIntegration()
                    test_message = f"🧪 대시보드 테스트 알림\n\n시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    if slack.send_simple_message("대시보드 테스트", test_message):
                        st.success("테스트 알림 전송 성공")
                    else:
                        st.error("테스트 알림 전송 실패")
                except Exception as e:
                    st.error(f"테스트 알림 실패: {str(e)}")


def main():
    """메인 함수"""
    st.title("🔍 채널 탐색 결과 관리")
    st.markdown("Google Sheets 통합 및 Slack 알림이 포함된 채널 탐색 결과 관리")
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["통계 대시보드", "최근 결과", "수동 탐색", "데이터 관리"]
    )
    
    if menu == "통계 대시보드":
        display_discovery_statistics()
        st.divider()
        
        # 간단한 차트 추가
        if INTEGRATIONS_AVAILABLE:
            try:
                sheets = GoogleSheetsIntegration()
                discoveries = sheets.get_latest_discoveries(limit=50)
                
                if discoveries and len(discoveries) > 1:
                    # 일별 탐색 건수
                    daily_counts = {}
                    for discovery in discoveries:
                        date_str = discovery.get('발견일시', '').split()[0]  # 날짜만 추출
                        if date_str:
                            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
                    
                    if daily_counts:
                        fig = px.bar(
                            x=list(daily_counts.keys()),
                            y=list(daily_counts.values()),
                            title="일별 채널 탐색 건수",
                            labels={'x': '날짜', 'y': '건수'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
            
            except Exception as e:
                st.warning(f"차트 생성 실패: {str(e)}")
    
    elif menu == "최근 결과":
        display_recent_discoveries()
    
    elif menu == "수동 탐색":
        display_manual_trigger()
    
    elif menu == "데이터 관리":
        display_data_management()


if __name__ == "__main__":
    main()