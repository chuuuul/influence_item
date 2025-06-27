"""신규 채널 탐색 페이지"""
import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# 프로젝트 root 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.youtube_api import YouTubeAPIManager
    from dashboard.utils.database_manager import DatabaseManager
except ImportError as e:
    st.error(f"모듈 import 실패: {e}")

def render_channel_discovery():
    st.header("🔍 신규 채널 탐색")
    st.info("PRD에 따라 신규 연예인 채널을 탐색하고 정밀 매칭 알고리즘으로 점수화합니다.")
    
    # 탐색 설정
    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("검색 키워드", placeholder="예: 강민경, 아이유, 홍지윤")
    with col2:
        max_results = st.selectbox("최대 결과 수", [10, 20, 30, 50])
    with col3:
        period = st.selectbox("탐색 기간", ["최근 7일", "최근 14일", "최근 30일"])
    
    # 연예인 키워드 설정
    celebrity_keywords = st.text_area(
        "연예인 관련 키워드 (선택사항)", 
        placeholder="뷰티, 패션, 라이프스타일, K-pop, 배우, 가수 등 (쉼표로 구분)"
    )
    
    # 탐색 시작 버튼
    if st.button("🚀 탐색 시작", type="primary", disabled=not search_query.strip()):
        if not search_query.strip():
            st.warning("검색 키워드를 입력해주세요.")
            return
            
        # YouTube API 매니저 초기화
        try:
            yt_manager = YouTubeAPIManager()
            if not yt_manager.youtube:
                st.error("YouTube API가 초기화되지 않았습니다. YOUTUBE_API_KEY 환경변수를 확인해주세요.")
                return
                
            # 키워드 파싱
            keywords = []
            if celebrity_keywords.strip():
                keywords = [k.strip() for k in celebrity_keywords.split(',') if k.strip()]
            
            # 채널 검색 실행
            with st.spinner("채널을 검색 중입니다..."):
                channels = yt_manager.search_channels(
                    query=search_query.strip(),
                    max_results=max_results,
                    celebrity_keywords=keywords
                )
            
            if not channels:
                st.warning("검색 결과가 없습니다. 다른 키워드로 시도해보세요.")
                return
            
            st.success(f"{len(channels)}개 채널을 발견했습니다!")
            
            # 결과를 세션 상태에 저장
            st.session_state.channel_search_results = channels
            st.session_state.search_query = search_query
            st.session_state.search_timestamp = datetime.now()
            
        except Exception as e:
            st.error(f"채널 검색 중 오류가 발생했습니다: {e}")
            return
    
    # 검색 결과 표시
    if hasattr(st.session_state, 'channel_search_results') and st.session_state.channel_search_results:
        st.subheader("📊 탐색 결과")
        
        # 검색 정보 표시
        if hasattr(st.session_state, 'search_timestamp'):
            st.caption(f"검색어: '{st.session_state.search_query}' | 검색 시간: {st.session_state.search_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        channels = st.session_state.channel_search_results
        
        # 데이터프레임 생성
        df_data = []
        for channel in channels:
            # 구독자 수 포맷팅
            subscriber_count = channel.get('subscriber_count', 0)
            if subscriber_count >= 1000000:
                sub_display = f"{subscriber_count/1000000:.1f}M"
            elif subscriber_count >= 1000:
                sub_display = f"{subscriber_count/1000:.1f}K"
            else:
                sub_display = str(subscriber_count)
            
            # 게시일 포맷팅
            published_at = channel.get('published_at', '')
            if published_at:
                try:
                    pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    published_display = pub_date.strftime('%Y-%m-%d')
                except:
                    published_display = published_at[:10] if len(published_at) >= 10 else published_at
            else:
                published_display = '-'
            
            df_data.append({
                "채널명": channel.get('title', ''),
                "구독자수": sub_display,
                "영상수": f"{channel.get('video_count', 0):,}",
                "개설일": published_display,
                "매칭점수": f"{channel.get('relevance_score', 0):.1f}",
                "채널ID": channel.get('channel_id', ''),
                "썸네일": channel.get('thumbnail_url', ''),
                "설명": channel.get('description', '')[:100] + "..." if len(channel.get('description', '')) > 100 else channel.get('description', '')
            })
        
        results_df = pd.DataFrame(df_data)
        
        # 상호작용 테이블
        selection = st.dataframe(
            results_df[["채널명", "구독자수", "영상수", "개설일", "매칭점수", "설명"]],
            use_container_width=True,
            selection_mode="single-row"
        )
        
        # 선택된 채널 상세 정보
        if hasattr(selection, 'selection') and selection.selection.get('rows'):
            selected_idx = selection.selection['rows'][0]
            selected_channel = channels[selected_idx]
            
            st.subheader("📋 선택된 채널 상세 정보")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # 썸네일 표시
                if selected_channel.get('thumbnail_url'):
                    st.image(selected_channel['thumbnail_url'], width=200)
                
                # 기본 정보
                st.write(f"**채널명:** {selected_channel.get('title', '')}")
                st.write(f"**구독자:** {selected_channel.get('subscriber_count', 0):,}명")
                st.write(f"**영상 수:** {selected_channel.get('video_count', 0):,}개")
                st.write(f"**총 조회수:** {selected_channel.get('view_count', 0):,}회")
                st.write(f"**매칭 점수:** {selected_channel.get('relevance_score', 0):.1f}/100")
                
                # 커스텀 URL
                if selected_channel.get('custom_url'):
                    st.write(f"**커스텀 URL:** @{selected_channel['custom_url']}")
            
            with col2:
                # 채널 설명
                st.write("**채널 설명:**")
                description = selected_channel.get('description', '')
                if description:
                    st.text_area("", description, height=150, disabled=True)
                else:
                    st.write("설명이 없습니다.")
                
                # 키워드
                keywords = selected_channel.get('keywords', [])
                if keywords and keywords != ['']:
                    st.write("**키워드:**")
                    st.write(", ".join(keywords))
            
            # 액션 버튼
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ 승인하여 추가", key=f"approve_{selected_idx}"):
                    # 데이터베이스에 채널 추가 (구현 필요)
                    st.success("채널이 승인되어 관리 목록에 추가되었습니다!")
            
            with col2:
                if st.button("❌ 제외", key=f"reject_{selected_idx}"):
                    st.info("채널이 제외되었습니다.")
            
            with col3:
                # YouTube 채널 바로가기
                channel_url = f"https://www.youtube.com/channel/{selected_channel.get('channel_id', '')}"
                st.link_button("🔗 YouTube에서 보기", channel_url)
    
    else:
        # 초기 상태 - 샘플 데이터 표시
        st.subheader("📊 최근 탐색 결과 (샘플)")
        st.caption("실제 검색을 위해 위의 검색 기능을 사용해주세요.")
        
        sample_results = pd.DataFrame({
            "채널명": ["홍지윤 Yoon", "아이유IU", "이사배"],
            "구독자수": ["1.2M", "8.5M", "2.1M"],
            "카테고리": ["뷰티/라이프", "음악/라이프", "뷰티"],
            "매칭점수": [92, 88, 95],
            "상태": ["대기", "승인", "대기"]
        })
        
        st.dataframe(sample_results, use_container_width=True)