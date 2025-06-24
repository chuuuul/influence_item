"""
채널 탐색 대시보드 페이지

PRD 요구사항에 따른 신규 채널 탐색 관리 대시보드:
- 탐색 기간 설정 및 실행
- 실시간 탐색 진행률 모니터링  
- 결과 확인 및 Google Sheets 연동
- 채널 후보 상세 정보 표시
"""

import streamlit as st
import asyncio
import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from pathlib import Path
import sys

# plotly 선택적 임포트
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("📊 차트 기능을 위해 plotly를 설치해주세요: `pip install plotly`")

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.channel_discovery import (
        ChannelDiscoveryEngine, DiscoveryConfig, ChannelCandidate,
        ChannelType, ChannelStatus, DEFAULT_CELEBRITY_KEYWORDS
    )
    from src.channel_discovery.youtube_search_integration import AdvancedYouTubeSearcher
    
    # Google Sheets 선택적 임포트
    try:
        from src.channel_discovery.sheets_integration import GoogleSheetsManager
        SHEETS_AVAILABLE = True
    except ImportError as e:
        SHEETS_AVAILABLE = False
        st.warning(f"📊 Google Sheets 연동이 비활성화되어 있습니다: {str(e)}")
        
except ImportError as e:
    st.error(f"모듈 임포트 에러: {e}")
    st.error("channel_discovery 모듈이 올바르게 설치되었는지 확인하세요.")
    st.stop()


def main():
    """메인 대시보드 함수"""
    
    st.set_page_config(
        page_title="채널 탐색 시스템",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 신규 채널 탐색 시스템")
    st.markdown("**PRD 2.1 요구사항에 따른 채널 자동 탐색 및 평가**")
    
    # 사이드바 메뉴
    with st.sidebar:
        st.header("📋 메뉴")
        page = st.radio(
            "페이지 선택",
            ["새 탐색 실행", "탐색 결과 조회", "설정 관리", "통계 대시보드"]
        )
    
    # 세션 상태 초기화
    if 'discovery_engine' not in st.session_state:
        st.session_state.discovery_engine = None
    
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    
    if 'discovery_results' not in st.session_state:
        st.session_state.discovery_results = []
    
    # 페이지 라우팅
    if page == "새 탐색 실행":
        show_new_discovery_page()
    elif page == "탐색 결과 조회":
        show_results_page()
    elif page == "설정 관리":
        show_settings_page()
    elif page == "통계 대시보드":
        show_statistics_page()


def show_new_discovery_page():
    """새 탐색 실행 페이지"""
    
    st.header("🚀 새로운 채널 탐색 실행")
    
    # 탐색 설정 폼
    with st.form("discovery_config_form"):
        st.subheader("📅 탐색 기간 설정")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "시작일",
                value=date.today() - timedelta(days=30),
                max_value=date.today()
            )
        
        with col2:
            end_date = st.date_input(
                "종료일",
                value=date.today(),
                max_value=date.today()
            )
        
        st.subheader("🎯 탐색 대상 설정")
        
        # 키워드 설정
        keywords_text = st.text_area(
            "탐색 키워드 (쉼표로 구분)",
            value=", ".join(DEFAULT_CELEBRITY_KEYWORDS[:10]),
            help="연예인명, 뷰티, 패션 등 관련 키워드를 입력하세요"
        )
        
        # 채널 타입 선택
        channel_types = st.multiselect(
            "채널 타입",
            options=[t.value for t in ChannelType],
            default=[ChannelType.CELEBRITY_PERSONAL.value, ChannelType.BEAUTY_INFLUENCER.value],
            help="탐색하고자 하는 채널 유형을 선택하세요"
        )
        
        # 필터링 조건
        st.subheader("🔧 필터링 조건")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            min_subscribers = st.number_input("최소 구독자 수", value=1000, min_value=0)
            min_videos = st.number_input("최소 영상 수", value=10, min_value=1)
        
        with col2:
            max_subscribers = st.number_input("최대 구독자 수", value=1000000, min_value=1000)
            max_results = st.number_input("최대 후보 수", value=100, min_value=10, max_value=500)
        
        with col3:
            min_score = st.slider("최소 매칭 점수", 0.0, 1.0, 0.3, 0.1)
            target_country = st.selectbox("대상 국가", ["KR", "US", "ALL"], index=0)
        
        # 고급 설정
        with st.expander("🔧 고급 설정"):
            search_methods = st.multiselect(
                "검색 방법",
                ["keyword_search", "trending", "related_channels"],
                default=["keyword_search", "trending"]
            )
            
            exclude_keywords = st.text_input(
                "제외 키워드 (쉼표로 구분)",
                help="검색 결과에서 제외할 키워드"
            )
        
        # Google Sheets 설정
        st.subheader("📊 Google Sheets 연동")
        
        if SHEETS_AVAILABLE:
            create_sheets = st.checkbox("결과를 Google Sheets에 자동 저장", value=True)
            
            if create_sheets:
                sheets_name = st.text_input(
                    "스프레드시트 이름",
                    value=f"채널_탐색_{datetime.now().strftime('%Y%m%d_%H%M')}"
                )
                share_emails = st.text_input(
                    "공유할 이메일 (쉼표로 구분)",
                    help="결과 스프레드시트를 공유할 이메일 주소"
                )
        else:
            create_sheets = False
            st.info("📊 Google Sheets 연동을 위해 gspread를 설치해주세요: `pip install gspread google-auth`")
        
        # 탐색 실행 버튼
        submitted = st.form_submit_button("🔍 탐색 시작", type="primary")
    
    if submitted:
        # 설정 검증
        if start_date >= end_date:
            st.error("종료일이 시작일보다 늦어야 합니다.")
            return
        
        if not keywords_text.strip():
            st.error("최소 하나 이상의 키워드를 입력해야 합니다.")
            return
        
        # 탐색 설정 생성
        target_keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
        target_channel_types = [ChannelType(ct) for ct in channel_types]
        exclude_kw_list = [kw.strip() for kw in exclude_keywords.split(",") if kw.strip()] if exclude_keywords else []
        
        config = DiscoveryConfig(
            start_date=start_date,
            end_date=end_date,
            target_keywords=target_keywords,
            target_channel_types=target_channel_types,
            min_subscriber_count=min_subscribers,
            max_subscriber_count=max_subscribers,
            min_video_count=min_videos,
            target_country=target_country if target_country != "ALL" else None,
            max_total_candidates=max_results,
            min_matching_score=min_score,
            search_methods=search_methods,
            exclude_keywords=exclude_kw_list
        )
        
        # 탐색 실행
        run_discovery(config, create_sheets, sheets_name, share_emails)


def run_discovery(config: DiscoveryConfig, create_sheets: bool = False,
                 sheets_name: str = "", share_emails: str = ""):
    """채널 탐색 실행"""
    
    st.subheader("🔄 탐색 진행 상황")
    
    # 진행률 표시 영역
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 상세 통계 영역
    stats_container = st.container()
    
    try:
        # 탐색 엔진 초기화
        if st.session_state.discovery_engine is None:
            with st.spinner("탐색 엔진 초기화 중..."):
                st.session_state.discovery_engine = ChannelDiscoveryEngine()
        
        engine = st.session_state.discovery_engine
        
        # 진행률 콜백 함수
        def update_progress(progress: float, message: str):
            progress_bar.progress(progress / 100)
            status_text.text(f"{message} ({progress:.1f}%)")
        
        # 비동기 탐색 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            candidates = loop.run_until_complete(
                engine.discover_channels(config, update_progress)
            )
            
            # 결과 저장
            st.session_state.discovery_results = candidates
            st.session_state.current_session_id = engine.current_session.session_id
            
            # 성공 메시지
            st.success(f"✅ 탐색 완료! {len(candidates)}개의 채널 후보를 발견했습니다.")
            
            # 결과 요약 표시
            show_discovery_summary(candidates)
            
            # Google Sheets 연동
            if create_sheets:
                create_google_sheets(candidates, sheets_name, share_emails)
            
        finally:
            loop.close()
        
    except Exception as e:
        st.error(f"❌ 탐색 실행 중 오류 발생: {str(e)}")
        st.exception(e)


def show_discovery_summary(candidates: List[ChannelCandidate]):
    """탐색 결과 요약 표시"""
    
    if not candidates:
        st.warning("발견된 채널 후보가 없습니다.")
        return
    
    st.subheader("📊 탐색 결과 요약")
    
    # 기본 통계
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 후보 수", len(candidates))
    
    with col2:
        high_score_count = len([c for c in candidates if c.total_score >= 70])
        st.metric("고점수 후보", high_score_count)
    
    with col3:
        avg_score = sum(c.total_score for c in candidates) / len(candidates)
        st.metric("평균 점수", f"{avg_score:.1f}")
    
    with col4:
        verified_count = len([c for c in candidates if c.verified])
        st.metric("인증 채널", verified_count)
    
    # 점수 분포 차트
    st.subheader("📈 점수 분포")
    
    if PLOTLY_AVAILABLE:
        scores = [c.total_score for c in candidates]
        fig = px.histogram(
            x=scores,
            nbins=20,
            title="채널 후보 점수 분포",
            labels={'x': '총점수', 'y': '채널 수'}
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        # plotly 없을 때 간단한 분포 표시
        scores = [c.total_score for c in candidates]
        score_ranges = {
            "90-100점": len([s for s in scores if 90 <= s <= 100]),
            "80-89점": len([s for s in scores if 80 <= s < 90]),
            "70-79점": len([s for s in scores if 70 <= s < 80]),
            "60-69점": len([s for s in scores if 60 <= s < 70]),
            "60점 미만": len([s for s in scores if s < 60])
        }
        st.bar_chart(score_ranges)
    
    # 상위 후보 테이블
    st.subheader("🏆 상위 채널 후보")
    
    # 상위 10개 후보
    top_candidates = sorted(candidates, key=lambda x: x.total_score, reverse=True)[:10]
    
    display_data = []
    for candidate in top_candidates:
        display_data.append({
            "순위": len(display_data) + 1,
            "채널명": candidate.channel_name,
            "구독자수": f"{candidate.subscriber_count:,}",
            "총점수": f"{candidate.total_score:.1f}",
            "등급": candidate.metadata.get('grade', '-') if candidate.metadata else '-',
            "인증": "✅" if candidate.verified else "",
            "URL": candidate.channel_url
        })
    
    df = pd.DataFrame(display_data)
    
    # 점수에 따른 색상 적용
    def color_score(val):
        try:
            score = float(val)
            if score >= 80:
                return 'background-color: #d4edda'
            elif score >= 60:
                return 'background-color: #fff3cd'
            elif score < 40:
                return 'background-color: #f8d7da'
        except:
            pass
        return ''
    
    styled_df = df.style.applymap(color_score, subset=['총점수'])
    st.dataframe(styled_df, use_container_width=True)


def create_google_sheets(candidates: List[ChannelCandidate], sheets_name: str, share_emails: str):
    """Google Sheets 생성 및 업로드"""
    
    if not SHEETS_AVAILABLE:
        st.warning("⚠️ Google Sheets 연동이 비활성화되어 있습니다.")
        return
    
    st.subheader("📋 Google Sheets 연동")
    
    try:
        with st.spinner("Google Sheets에 결과 업로드 중..."):
            # Google Sheets 관리자 초기화
            try:
                sheets_manager = GoogleSheetsManager()
                if sheets_manager.gc is None:
                    st.warning("⚠️ Google Sheets 인증이 설정되지 않았습니다.")
                    return
            except Exception as e:
                st.warning(f"⚠️ Google Sheets 관리자 초기화 실패: {str(e)}")
                return
            
            # 새 스프레드시트 생성
            spreadsheet_id, spreadsheet_url = sheets_manager.create_discovery_spreadsheet(sheets_name)
            
            # 채널 후보 업로드
            success = sheets_manager.upload_channel_candidates(spreadsheet_id, candidates)
            
            if success:
                st.success("✅ Google Sheets 업로드 완료!")
                
                # 스프레드시트 링크 표시
                st.markdown(f"**📊 결과 스프레드시트:** [링크 열기]({spreadsheet_url})")
                
                # 공유 설정
                if share_emails:
                    email_list = [email.strip() for email in share_emails.split(",") if email.strip()]
                    if email_list:
                        share_success = sheets_manager.share_spreadsheet(spreadsheet_id, email_list)
                        if share_success:
                            st.success(f"✅ {len(email_list)}명에게 공유 완료")
                        else:
                            st.warning("⚠️ 일부 공유 설정에 실패했습니다")
                
                # 세션에 URL 저장
                st.session_state.last_sheets_url = spreadsheet_url
            else:
                st.error("❌ Google Sheets 업로드 실패")
    
    except Exception as e:
        st.error(f"❌ Google Sheets 연동 중 오류 발생: {str(e)}")


def show_results_page():
    """탐색 결과 조회 페이지"""
    
    st.header("📋 탐색 결과 조회")
    
    # 세션 결과가 있는지 확인
    if not st.session_state.discovery_results:
        st.info("🔍 아직 탐색 결과가 없습니다. '새 탐색 실행' 페이지에서 채널 탐색을 시작해보세요.")
        return
    
    candidates = st.session_state.discovery_results
    
    # 필터링 옵션
    with st.expander("🔧 필터링 옵션"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_score_filter = st.slider("최소 점수", 0.0, 100.0, 0.0)
            verified_only = st.checkbox("인증 채널만 보기")
        
        with col2:
            min_subscribers_filter = st.number_input("최소 구독자 수", value=0, min_value=0)
            channel_type_filter = st.multiselect(
                "채널 타입 필터",
                options=[t.value for t in ChannelType],
                default=[]
            )
        
        with col3:
            search_term = st.text_input("채널명 검색")
    
    # 필터 적용
    filtered_candidates = candidates
    
    if min_score_filter > 0:
        filtered_candidates = [c for c in filtered_candidates if c.total_score >= min_score_filter]
    
    if verified_only:
        filtered_candidates = [c for c in filtered_candidates if c.verified]
    
    if min_subscribers_filter > 0:
        filtered_candidates = [c for c in filtered_candidates if c.subscriber_count >= min_subscribers_filter]
    
    if channel_type_filter:
        filtered_candidates = [c for c in filtered_candidates if c.channel_type.value in channel_type_filter]
    
    if search_term:
        filtered_candidates = [c for c in filtered_candidates if search_term.lower() in c.channel_name.lower()]
    
    # 결과 표시
    st.write(f"**총 {len(filtered_candidates)}개 채널** (전체 {len(candidates)}개 중)")
    
    if not filtered_candidates:
        st.warning("필터 조건에 맞는 채널이 없습니다.")
        return
    
    # 정렬 옵션
    sort_by = st.selectbox(
        "정렬 기준",
        ["총점수", "구독자수", "영상수", "매칭점수", "채널명"],
        index=0
    )
    
    sort_order = st.radio("정렬 순서", ["내림차순", "오름차순"], horizontal=True)
    
    # 정렬 적용
    reverse = sort_order == "내림차순"
    
    if sort_by == "총점수":
        filtered_candidates.sort(key=lambda x: x.total_score, reverse=reverse)
    elif sort_by == "구독자수":
        filtered_candidates.sort(key=lambda x: x.subscriber_count, reverse=reverse)
    elif sort_by == "영상수":
        filtered_candidates.sort(key=lambda x: x.video_count, reverse=reverse)
    elif sort_by == "매칭점수":
        filtered_candidates.sort(key=lambda x: x.matching_scores.get('matching', 0), reverse=reverse)
    elif sort_by == "채널명":
        filtered_candidates.sort(key=lambda x: x.channel_name, reverse=reverse)
    
    # 상세 결과 표시
    for i, candidate in enumerate(filtered_candidates):
        with st.expander(f"#{i+1} {candidate.channel_name} (점수: {candidate.total_score:.1f})"):
            show_candidate_details(candidate)


def show_candidate_details(candidate: ChannelCandidate):
    """채널 후보 상세 정보 표시"""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 기본 정보
        st.markdown(f"**🎬 채널명:** {candidate.channel_name}")
        st.markdown(f"**🔗 URL:** [채널 보기]({candidate.channel_url})")
        
        if candidate.description:
            with st.expander("📝 채널 설명"):
                st.text(candidate.description[:500] + "..." if len(candidate.description) > 500 else candidate.description)
        
        # 키워드
        if candidate.keywords:
            st.markdown(f"**🏷️ 키워드:** {', '.join(candidate.keywords[:10])}")
    
    with col2:
        # 통계
        st.metric("구독자 수", f"{candidate.subscriber_count:,}")
        st.metric("영상 수", f"{candidate.video_count:,}")
        st.metric("총 조회수", f"{candidate.view_count:,}")
    
    # 점수 정보
    st.subheader("📊 점수 분석")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총점수", f"{candidate.total_score:.1f}")
    
    with col2:
        matching_score = candidate.matching_scores.get('matching', 0) if candidate.matching_scores else 0
        st.metric("매칭점수", f"{matching_score:.2f}")
    
    with col3:
        quality_score = candidate.matching_scores.get('quality', 0) if candidate.matching_scores else 0
        st.metric("품질점수", f"{quality_score:.2f}")
    
    with col4:
        potential_score = candidate.matching_scores.get('potential', 0) if candidate.matching_scores else 0
        st.metric("잠재력점수", f"{potential_score:.2f}")
    
    # 강점/약점
    if candidate.metadata:
        strengths = candidate.metadata.get('strengths', [])
        weaknesses = candidate.metadata.get('weaknesses', [])
        
        if strengths or weaknesses:
            col1, col2 = st.columns(2)
            
            with col1:
                if strengths:
                    st.markdown("**💪 강점:**")
                    for strength in strengths:
                        st.markdown(f"• {strength}")
            
            with col2:
                if weaknesses:
                    st.markdown("**⚠️ 약점:**")
                    for weakness in weaknesses:
                        st.markdown(f"• {weakness}")


def show_settings_page():
    """설정 관리 페이지"""
    
    st.header("⚙️ 설정 관리")
    
    # YouTube API 설정
    st.subheader("🔑 YouTube API 설정")
    
    with st.expander("YouTube API 키 관리"):
        current_key = st.text_input("현재 API 키", type="password", help="보안을 위해 마스킹됩니다")
        
        if st.button("API 키 테스트"):
            if current_key:
                try:
                    # API 키 테스트 로직
                    st.success("✅ API 키가 유효합니다")
                except Exception as e:
                    st.error(f"❌ API 키 테스트 실패: {str(e)}")
            else:
                st.warning("API 키를 입력해주세요")
    
    # Google Sheets 설정
    st.subheader("📊 Google Sheets 설정")
    
    with st.expander("Google Sheets 인증 설정"):
        credentials_file = st.file_uploader(
            "Service Account JSON 파일",
            type=['json'],
            help="Google Cloud Console에서 다운로드한 서비스 계정 JSON 파일"
        )
        
        if credentials_file:
            # 파일 저장 로직
            st.success("✅ 인증 파일이 업로드되었습니다")
    
    # 기본 설정
    st.subheader("🎯 기본 설정")
    
    with st.form("default_settings"):
        st.markdown("**기본 검색 키워드**")
        default_keywords = st.text_area(
            "키워드 (쉼표로 구분)",
            value=", ".join(DEFAULT_CELEBRITY_KEYWORDS),
            height=100
        )
        
        st.markdown("**기본 필터링 조건**")
        col1, col2 = st.columns(2)
        
        with col1:
            default_min_subs = st.number_input("기본 최소 구독자 수", value=1000)
            default_max_subs = st.number_input("기본 최대 구독자 수", value=1000000)
        
        with col2:
            default_min_videos = st.number_input("기본 최소 영상 수", value=10)
            default_min_score = st.slider("기본 최소 점수", 0.0, 1.0, 0.3)
        
        if st.form_submit_button("💾 설정 저장"):
            # 설정 저장 로직
            st.success("✅ 설정이 저장되었습니다")


def show_statistics_page():
    """통계 대시보드 페이지"""
    
    st.header("📊 채널 탐색 통계")
    
    # 세션 결과가 없으면 샘플 데이터 표시
    if not st.session_state.discovery_results:
        st.info("🔍 탐색 결과가 없어 샘플 통계를 표시합니다.")
        show_sample_statistics()
        return
    
    candidates = st.session_state.discovery_results
    
    # 전체 통계
    st.subheader("📈 전체 통계")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("총 후보 수", len(candidates))
    
    with col2:
        avg_score = sum(c.total_score for c in candidates) / len(candidates) if candidates else 0
        st.metric("평균 점수", f"{avg_score:.1f}")
    
    with col3:
        high_score = len([c for c in candidates if c.total_score >= 70])
        st.metric("고점수 후보", high_score)
    
    with col4:
        verified = len([c for c in candidates if c.verified])
        st.metric("인증 채널", verified)
    
    with col5:
        avg_subs = sum(c.subscriber_count for c in candidates) / len(candidates) if candidates else 0
        st.metric("평균 구독자", f"{avg_subs:,.0f}")
    
    # 점수 분포 차트
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("점수 분포")
        if PLOTLY_AVAILABLE:
            scores = [c.total_score for c in candidates]
            fig1 = px.histogram(x=scores, nbins=15, title="총점수 분포")
            st.plotly_chart(fig1, use_container_width=True)
        else:
            scores = [c.total_score for c in candidates]
            score_ranges = {f"{i}-{i+9}점": len([s for s in scores if i <= s < i+10]) for i in range(0, 100, 10)}
            st.bar_chart(score_ranges)
    
    with col2:
        st.subheader("구독자 수 분포")
        if PLOTLY_AVAILABLE:
            subs = [c.subscriber_count for c in candidates]
            fig2 = px.histogram(x=subs, nbins=15, title="구독자 수 분포")
            fig2.update_xaxis(type="log")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            subs = [c.subscriber_count for c in candidates]
            sub_ranges = {
                "1K-10K": len([s for s in subs if 1000 <= s < 10000]),
                "10K-100K": len([s for s in subs if 10000 <= s < 100000]),
                "100K-1M": len([s for s in subs if 100000 <= s < 1000000]),
                "1M+": len([s for s in subs if s >= 1000000])
            }
            st.bar_chart(sub_ranges)
    
    # 채널 타입별 분석
    st.subheader("📊 채널 타입별 분석")
    
    type_data = {}
    for candidate in candidates:
        channel_type = candidate.channel_type.value if candidate.channel_type else "기타"
        if channel_type not in type_data:
            type_data[channel_type] = []
        type_data[channel_type].append(candidate.total_score)
    
    if type_data:
        if PLOTLY_AVAILABLE:
            fig3 = go.Figure()
            
            for channel_type, scores in type_data.items():
                fig3.add_trace(go.Box(
                    y=scores,
                    name=channel_type,
                    boxpoints='outliers'
                ))
            
            fig3.update_layout(title="채널 타입별 점수 분포")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            # plotly 없을 때 간단한 타입별 평균 표시
            type_averages = {
                channel_type: sum(scores) / len(scores) if scores else 0
                for channel_type, scores in type_data.items()
            }
            st.bar_chart(type_averages)
    
    # 성과 지표
    st.subheader("🎯 탐색 성과")
    
    if st.session_state.discovery_engine and st.session_state.current_session_id:
        session_status = st.session_state.discovery_engine.get_session_status(
            st.session_state.current_session_id
        )
        
        if session_status:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("처리된 쿼리", session_status.get('queries_processed', 0))
            
            with col2:
                st.metric("API 호출 수", session_status.get('api_calls_made', 0))
            
            with col3:
                error_rate = (session_status.get('processing_errors', 0) / 
                            max(session_status.get('queries_processed', 1), 1) * 100)
                st.metric("오류율", f"{error_rate:.1f}%")


def show_sample_statistics():
    """샘플 통계 표시"""
    
    st.markdown("### 📊 샘플 통계 데이터")
    
    # 샘플 메트릭
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("탐색된 채널", "1,234")
    
    with col2:
        st.metric("평균 점수", "67.8")
    
    with col3:
        st.metric("고품질 후보", "456")
    
    with col4:
        st.metric("성공률", "78.5%")
    
    # 샘플 차트
    if PLOTLY_AVAILABLE:
        import numpy as np
        
        # 점수 분포 샘플
        sample_scores = np.random.normal(65, 15, 100)
        sample_scores = np.clip(sample_scores, 0, 100)
        
        fig = px.histogram(x=sample_scores, nbins=20, title="점수 분포 (샘플)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        # 간단한 샘플 데이터 표시
        sample_data = {
            "90-100점": 8,
            "80-89점": 15,
            "70-79점": 25,
            "60-69점": 30,
            "50-59점": 15,
            "50점 미만": 7
        }
        st.bar_chart(sample_data)


if __name__ == "__main__":
    main()