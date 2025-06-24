"""
비디오 수집 관리 대시보드

PRD 2.2 요구사항:
- 운영자가 관리 대시보드에서 채널 및 분석 기간을 선택하여 과거 영상 수집
- RSS 피드 자동 수집 모니터링
- Google Sheets 채널 목록 동기화 관리
"""

import streamlit as st
import pandas as pd
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 환경변수 로드 (YouTube API 키 포함)
from dashboard.utils.env_loader import ensure_youtube_api_key

from src.rss_automation.rss_collector import RSSCollector, ChannelInfo
from src.rss_automation.historical_scraper import HistoricalScraper, ScrapingConfig
from src.rss_automation.content_filter import ContentFilter
from src.rss_automation.sheets_integration import SheetsIntegration, SheetsConfig, ChannelCandidate


def init_page():
    """페이지 초기 설정"""
    st.set_page_config(
        page_title="비디오 수집 관리",
        page_icon="📺",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("📺 비디오 수집 관리")
    
    # YouTube API 키 확인
    try:
        api_key = ensure_youtube_api_key()
        st.success(f"✅ YouTube API 키 로드 완료: {api_key[:10]}...")
    except Exception as e:
        st.error(f"❌ YouTube API 키 오류: {str(e)}")
        st.info("💡 .env 파일에 YOUTUBE_API_KEY를 설정하세요.")
        st.stop()
    
    st.markdown("---")


@st.cache_resource
def get_rss_collector():
    """RSS 수집기 인스턴스 캐시"""
    return RSSCollector()


@st.cache_resource
def get_historical_scraper():
    """과거 영상 수집기 인스턴스 캐시"""
    return HistoricalScraper()


@st.cache_resource
def get_content_filter():
    """컨텐츠 필터 인스턴스 캐시"""
    return ContentFilter()


@st.cache_resource
def get_sheets_integration():
    """Google Sheets 연동 인스턴스 캐시"""
    try:
        # 기본 설정 (실제 운영시에는 환경변수나 설정파일 사용)
        config = SheetsConfig(
            spreadsheet_id=st.secrets.get("GOOGLE_SHEETS_ID", ""),
            channels_sheet_name="승인된 채널",
            candidates_sheet_name="후보 채널"
        )
        return SheetsIntegration(config)
    except Exception as e:
        st.error(f"Google Sheets 연동 초기화 실패: {str(e)}")
        return None


def display_collection_overview():
    """수집 현황 개요"""
    st.subheader("📊 수집 현황 개요")
    
    try:
        collector = get_rss_collector()
        filter_system = get_content_filter()
        
        # 통계 데이터 조회
        collection_stats = collector.get_collection_statistics(days=7)
        filter_stats = filter_system.get_filter_statistics(days=7)
        
        # 메트릭 표시
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="총 수집 실행",
                value=collection_stats.get('total_executions', 0),
                delta=f"{collection_stats.get('successful_executions', 0)}회 성공"
            )
        
        with col2:
            st.metric(
                label="수집된 비디오",
                value=collection_stats.get('total_collected', 0),
                delta=f"최근 7일"
            )
        
        with col3:
            st.metric(
                label="필터링된 비디오",
                value=collection_stats.get('total_filtered', 0) + filter_stats.get('total_filtered', 0),
                delta=f"필터링률 {((filter_stats.get('total_filtered', 0) / max(collection_stats.get('total_collected', 1), 1)) * 100):.1f}%"
            )
        
        with col4:
            st.metric(
                label="오류 발생",
                value=collection_stats.get('total_errors', 0),
                delta="오류" if collection_stats.get('total_errors', 0) > 0 else "정상"
            )
        
        # 일별 수집 통계 차트
        if collection_stats.get('daily_stats'):
            df_daily = pd.DataFrame(collection_stats['daily_stats'])
            df_daily['date'] = pd.to_datetime(df_daily['date'])
            
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('일별 수집 현황', '일별 필터링 현황'),
                vertical_spacing=0.1
            )
            
            # 수집 현황
            fig.add_trace(
                go.Bar(x=df_daily['date'], y=df_daily['collected'], name='수집', marker_color='lightblue'),
                row=1, col=1
            )
            
            # 필터링 현황
            fig.add_trace(
                go.Bar(x=df_daily['date'], y=df_daily['filtered'], name='필터링', marker_color='lightcoral'),
                row=2, col=1
            )
            
            fig.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"수집 현황 조회 실패: {str(e)}")


def display_rss_collection_management():
    """RSS 수집 관리"""
    st.subheader("🔄 RSS 자동 수집 관리")
    
    try:
        collector = get_rss_collector()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**활성 채널 목록**")
            channels = collector.get_active_channels()
            
            if channels:
                channel_data = []
                for channel in channels:
                    channel_data.append({
                        '채널ID': channel.channel_id,
                        '채널명': channel.channel_name,
                        '채널유형': '개인채널' if channel.channel_type == 'personal' else '미디어채널',
                        'RSS URL': channel.rss_url,
                        '상태': '활성' if channel.is_active else '비활성'
                    })
                
                df_channels = pd.DataFrame(channel_data)
                st.dataframe(df_channels, use_container_width=True)
            else:
                st.info("등록된 활성 채널이 없습니다.")
        
        with col2:
            st.write("**수집 작업 실행**")
            
            if st.button("🚀 즉시 RSS 수집 실행", type="primary"):
                with st.spinner("RSS 피드 수집 중..."):
                    try:
                        # asyncio 이벤트 루프 처리
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        result = loop.run_until_complete(collector.collect_daily_videos())
                        
                        if result.success:
                            st.success(f"""
                            ✅ RSS 수집 완료!
                            - 수집된 비디오: {result.collected_count}개
                            - 필터링된 비디오: {result.filtered_count}개
                            - 실행 시간: {result.execution_time:.2f}초
                            """)
                        else:
                            st.error(f"RSS 수집 실패: {', '.join(result.errors)}")
                            
                    except Exception as e:
                        st.error(f"RSS 수집 실행 중 오류: {str(e)}")
            
            # 새 채널 추가
            st.write("**새 채널 추가**")
            with st.form("add_channel_form"):
                new_channel_id = st.text_input("채널 ID")
                new_channel_name = st.text_input("채널명")
                new_channel_type = st.selectbox("채널 유형", ["personal", "media"])
                new_rss_url = st.text_input("RSS URL")
                
                if st.form_submit_button("채널 추가"):
                    if all([new_channel_id, new_channel_name, new_rss_url]):
                        channel_info = ChannelInfo(
                            channel_id=new_channel_id,
                            channel_name=new_channel_name,
                            channel_type=new_channel_type,
                            rss_url=new_rss_url
                        )
                        
                        if collector.add_channel(channel_info):
                            st.success("채널이 성공적으로 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("채널 추가에 실패했습니다.")
                    else:
                        st.error("모든 필드를 입력해주세요.")
        
    except Exception as e:
        st.error(f"RSS 수집 관리 오류: {str(e)}")


def display_historical_scraping():
    """과거 영상 스크래핑"""
    st.subheader("⏰ 과거 영상 수집")
    
    try:
        scraper = get_historical_scraper()
        collector = get_rss_collector()
        
        # 스크래핑 설정
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**스크래핑 작업 설정**")
            
            # 채널 선택
            channels = collector.get_active_channels()
            if not channels:
                st.warning("등록된 채널이 없습니다. 먼저 채널을 추가해주세요.")
                return
            
            channel_options = {f"{ch.channel_name} ({ch.channel_id})": ch for ch in channels}
            selected_channel_display = st.selectbox("채널 선택", list(channel_options.keys()))
            selected_channel = channel_options[selected_channel_display]
            
            # 날짜 범위 선택
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("시작 날짜", value=datetime.now().date() - timedelta(days=30))
            with col_date2:
                end_date = st.date_input("종료 날짜", value=datetime.now().date())
            
            # 스크래핑 설정
            with st.expander("고급 설정"):
                headless = st.checkbox("헤드리스 모드", value=True)
                max_videos = st.number_input("최대 비디오 수", min_value=10, max_value=1000, value=500)
                scroll_delay = st.slider("스크롤 지연 시간 (초)", min_value=1.0, max_value=5.0, value=2.0)
            
            # 스크래핑 실행
            if st.button("🎬 과거 영상 수집 시작", type="primary"):
                if start_date <= end_date:
                    config = ScrapingConfig(
                        headless=headless,
                        max_videos_per_channel=max_videos,
                        scroll_delay=scroll_delay
                    )
                    
                    scraper_with_config = HistoricalScraper(config=config)
                    
                    with st.spinner(f"{selected_channel.channel_name} 채널의 과거 영상 수집 중..."):
                        try:
                            # asyncio 이벤트 루프 처리
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            result = loop.run_until_complete(
                                scraper_with_config.scrape_channel_videos(
                                    selected_channel.channel_id,
                                    selected_channel.channel_name,
                                    datetime.combine(start_date, datetime.min.time()),
                                    datetime.combine(end_date, datetime.max.time())
                                )
                            )
                            
                            if result.success:
                                st.success(f"""
                                ✅ 과거 영상 수집 완료!
                                - 발견된 비디오: {result.total_found}개
                                - 수집된 비디오: {result.collected_count}개
                                - 필터링된 비디오: {result.filtered_count}개
                                - 실행 시간: {result.execution_time:.2f}초
                                """)
                            else:
                                st.error(f"과거 영상 수집 실패: {', '.join(result.errors)}")
                                
                        except Exception as e:
                            st.error(f"과거 영상 수집 중 오류: {str(e)}")
                else:
                    st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
        
        with col2:
            st.write("**최근 스크래핑 작업**")
            
            # 최근 스크래핑 작업 목록
            recent_jobs = scraper.get_scraping_jobs(limit=10)
            
            if recent_jobs:
                for job in recent_jobs:
                    status_emoji = {
                        'completed': '✅',
                        'running': '🔄',
                        'failed': '❌',
                        'pending': '⏳'
                    }.get(job['status'], '❓')
                    
                    with st.expander(f"{status_emoji} {job['channel_name']} ({job['created_at'][:10]})"):
                        st.write(f"**작업 ID:** {job['job_id']}")
                        st.write(f"**기간:** {job['start_date']} ~ {job['end_date']}")
                        st.write(f"**상태:** {job['status']}")
                        
                        if job['status'] == 'completed':
                            col_stat1, col_stat2 = st.columns(2)
                            with col_stat1:
                                st.metric("수집", job['collected_count'])
                            with col_stat2:
                                st.metric("필터링", job['filtered_count'])
                        
                        # 수집된 비디오 보기
                        if st.button(f"비디오 목록 보기", key=f"view_{job['job_id']}"):
                            videos = scraper.get_scraped_videos(job['job_id'])
                            if videos:
                                st.dataframe(pd.DataFrame(videos))
                            else:
                                st.info("수집된 비디오가 없습니다.")
            else:
                st.info("최근 스크래핑 작업이 없습니다.")
        
    except Exception as e:
        st.error(f"과거 영상 수집 오류: {str(e)}")


def display_sheets_integration():
    """Google Sheets 연동 관리"""
    st.subheader("📊 Google Sheets 연동 관리")
    
    try:
        sheets = get_sheets_integration()
        if not sheets:
            st.error("Google Sheets 연동이 설정되지 않았습니다.")
            return
        
        # 동기화 작업
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**동기화 작업**")
            
            sync_col1, sync_col2, sync_col3, sync_col4 = st.columns(4)
            
            with sync_col1:
                if st.button("📤 승인된 채널 → Sheets"):
                    with st.spinner("승인된 채널을 Sheets로 동기화 중..."):
                        if sheets.sync_approved_channels_to_sheets():
                            st.success("승인된 채널 동기화 완료!")
                        else:
                            st.error("승인된 채널 동기화 실패")
            
            with sync_col2:
                if st.button("📤 후보 채널 → Sheets"):
                    with st.spinner("후보 채널을 Sheets로 동기화 중..."):
                        if sheets.sync_channel_candidates_to_sheets():
                            st.success("후보 채널 동기화 완료!")
                        else:
                            st.error("후보 채널 동기화 실패")
            
            with sync_col3:
                if st.button("📥 검토 결과 ← Sheets"):
                    with st.spinner("검토 결과를 Sheets에서 동기화 중..."):
                        if sheets.sync_reviews_from_sheets():
                            st.success("검토 결과 동기화 완료!")
                        else:
                            st.error("검토 결과 동기화 실패")
            
            with sync_col4:
                if st.button("🔄 전체 동기화", type="primary"):
                    with st.spinner("전체 동기화 중..."):
                        results = sheets.full_sync()
                        success_count = sum(results.values())
                        
                        if success_count == 3:
                            st.success("전체 동기화 완료!")
                        elif success_count > 0:
                            st.warning(f"부분 동기화 완료 ({success_count}/3)")
                        else:
                            st.error("전체 동기화 실패")
        
        with col2:
            st.write("**동기화 통계**")
            sync_stats = sheets.get_sync_statistics(days=7)
            
            st.metric("총 동기화", sync_stats.get('total_syncs', 0))
            st.metric("성공률", f"{(sync_stats.get('successful_syncs', 0) / max(sync_stats.get('total_syncs', 1), 1) * 100):.1f}%")
        
        # 채널 후보 관리
        st.write("**채널 후보 관리**")
        
        # 새 채널 후보 추가
        with st.expander("새 채널 후보 추가"):
            with st.form("add_candidate_form"):
                cand_channel_id = st.text_input("채널 ID")
                cand_channel_name = st.text_input("채널명")
                cand_channel_type = st.selectbox("채널 유형", ["personal", "media"])
                cand_rss_url = st.text_input("RSS URL")
                cand_score = st.slider("발견 점수", min_value=0.0, max_value=1.0, value=0.8)
                cand_reason = st.text_area("발견 사유")
                
                if st.form_submit_button("후보 추가"):
                    if all([cand_channel_id, cand_channel_name, cand_rss_url, cand_reason]):
                        candidate = ChannelCandidate(
                            channel_id=cand_channel_id,
                            channel_name=cand_channel_name,
                            channel_type=cand_channel_type,
                            rss_url=cand_rss_url,
                            discovery_score=cand_score,
                            discovery_reason=cand_reason,
                            discovered_at=datetime.now()
                        )
                        
                        if sheets.add_channel_candidate(candidate):
                            st.success("채널 후보가 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("채널 후보 추가에 실패했습니다.")
                    else:
                        st.error("모든 필수 필드를 입력해주세요.")
        
        # 채널 후보 목록
        candidates = sheets.get_channel_candidates()
        if candidates:
            # 상태별 필터링
            status_filter = st.selectbox("상태 필터", ["전체", "pending", "approved", "rejected"])
            
            if status_filter != "전체":
                candidates = [c for c in candidates if c['review_status'] == status_filter]
            
            # 데이터프레임 생성
            candidate_data = []
            for candidate in candidates:
                candidate_data.append({
                    '채널ID': candidate['channel_id'],
                    '채널명': candidate['channel_name'],
                    '채널유형': '개인채널' if candidate['channel_type'] == 'personal' else '미디어채널',
                    '발견점수': candidate['discovery_score'],
                    '발견사유': candidate['discovery_reason'][:50] + '...' if len(candidate['discovery_reason']) > 50 else candidate['discovery_reason'],
                    '상태': candidate['review_status'],
                    '발견일시': candidate['discovered_at'][:10] if candidate['discovered_at'] else '',
                    'Sheets동기화': '✅' if candidate['sheets_synced'] else '❌'
                })
            
            df_candidates = pd.DataFrame(candidate_data)
            st.dataframe(df_candidates, use_container_width=True)
        else:
            st.info("등록된 채널 후보가 없습니다.")
        
    except Exception as e:
        st.error(f"Google Sheets 연동 오류: {str(e)}")


def display_filter_management():
    """필터링 관리"""
    st.subheader("🔍 컨텐츠 필터링 관리")
    
    try:
        filter_system = get_content_filter()
        
        # 필터링 통계
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("**필터링 통계**")
            filter_stats = filter_system.get_filter_statistics(days=7)
            
            # 필터 유형별 통계 차트
            if filter_stats.get('filter_breakdown'):
                breakdown_data = []
                for filter_type, results in filter_stats['filter_breakdown'].items():
                    for result, count in results.items():
                        breakdown_data.append({
                            '필터유형': filter_type,
                            '결과': result,
                            '개수': count
                        })
                
                if breakdown_data:
                    df_breakdown = pd.DataFrame(breakdown_data)
                    fig = px.bar(
                        df_breakdown, 
                        x='필터유형', 
                        y='개수', 
                        color='결과',
                        title="필터 유형별 처리 결과"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # 연예인별 매칭 통계
            if filter_stats.get('celebrity_matches'):
                st.write("**연예인별 매칭 통계 (Top 10)**")
                celebrity_data = [
                    {'연예인': reason, '매칭횟수': count}
                    for reason, count in list(filter_stats['celebrity_matches'].items())[:10]
                ]
                
                if celebrity_data:
                    df_celebrity = pd.DataFrame(celebrity_data)
                    fig = px.bar(
                        df_celebrity,
                        x='매칭횟수',
                        y='연예인',
                        orientation='h',
                        title="연예인별 매칭 횟수"
                    )
                    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("**필터 관리**")
            
            # 새 연예인 추가
            with st.expander("연예인 추가"):
                with st.form("add_celebrity_form"):
                    celeb_name = st.text_input("연예인 이름")
                    celeb_aliases = st.text_input("별명/예명 (쉼표로 구분)")
                    celeb_group = st.text_input("그룹명 (선택사항)")
                    
                    if st.form_submit_button("연예인 추가"):
                        if celeb_name:
                            aliases = [alias.strip() for alias in celeb_aliases.split(',') if alias.strip()]
                            
                            if filter_system.add_celebrity(celeb_name, aliases, celeb_group):
                                st.success(f"연예인 '{celeb_name}' 추가 완료!")
                            else:
                                st.error("연예인 추가 실패")
                        else:
                            st.error("연예인 이름을 입력해주세요.")
            
            # 새 필터 패턴 추가
            with st.expander("필터 패턴 추가"):
                with st.form("add_pattern_form"):
                    pattern_type = st.selectbox("패턴 유형", ["shorts_indicator", "ppl_keyword"])
                    pattern_text = st.text_input("패턴 (정규식)")
                    pattern_desc = st.text_input("설명")
                    
                    if st.form_submit_button("패턴 추가"):
                        if pattern_text:
                            if filter_system.add_filter_pattern(pattern_type, pattern_text, pattern_desc):
                                st.success("필터 패턴 추가 완료!")
                            else:
                                st.error("필터 패턴 추가 실패")
                        else:
                            st.error("패턴을 입력해주세요.")
            
            # 테스트 필터링
            st.write("**필터링 테스트**")
            test_title = st.text_input("테스트할 영상 제목")
            test_description = st.text_area("테스트할 영상 설명", height=100)
            test_channel_type = st.selectbox("채널 유형", ["personal", "media"])
            
            if st.button("🧪 필터링 테스트"):
                if test_title:
                    result = filter_system.comprehensive_filter(
                        test_title, test_description, test_channel_type
                    )
                    
                    if result.passed:
                        st.success(f"✅ 통과: {result.reason}")
                    else:
                        st.error(f"❌ 차단: {result.reason}")
                    
                    st.info(f"신뢰도: {result.confidence:.2f}")
                    
                    if result.matched_names:
                        st.write(f"매칭된 항목: {', '.join(result.matched_names)}")
                else:
                    st.error("테스트할 제목을 입력해주세요.")
        
    except Exception as e:
        st.error(f"필터링 관리 오류: {str(e)}")


def main():
    """메인 함수"""
    init_page()
    
    # 사이드바 메뉴
    with st.sidebar:
        st.title("📺 비디오 수집 관리")
        
        menu_options = [
            "📊 수집 현황",
            "🔄 RSS 자동 수집",
            "⏰ 과거 영상 수집",
            "📊 Google Sheets 연동",
            "🔍 필터링 관리"
        ]
        
        selected_menu = st.radio("메뉴 선택", menu_options)
        
        st.markdown("---")
        st.markdown("### 💡 도움말")
        st.markdown("""
        **RSS 자동 수집**: 승인된 채널의 RSS 피드를 통해 새로운 비디오를 자동으로 수집합니다.
        
        **과거 영상 수집**: Playwright를 사용하여 지정된 기간의 과거 영상을 스크래핑합니다.
        
        **Google Sheets 연동**: 채널 목록과 후보 채널을 Google Sheets와 동기화합니다.
        
        **필터링 관리**: 연예인 이름 필터링과 PPL 콘텐츠 필터링을 관리합니다.
        """)
    
    # 선택된 메뉴에 따라 페이지 표시
    if selected_menu == "📊 수집 현황":
        display_collection_overview()
    elif selected_menu == "🔄 RSS 자동 수집":
        display_rss_collection_management()
    elif selected_menu == "⏰ 과거 영상 수집":
        display_historical_scraping()
    elif selected_menu == "📊 Google Sheets 연동":
        display_sheets_integration()
    elif selected_menu == "🔍 필터링 관리":
        display_filter_management()


if __name__ == "__main__":
    main()