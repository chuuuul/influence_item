"""
연예인 추천 아이템 자동화 릴스 시스템 - 관리 대시보드
PRD v1.0 기반 Streamlit 대시보드
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 페이지 모듈 및 데이터베이스 import
try:
    from dashboard.views.monetizable_candidates import render_monetizable_candidates
    from dashboard.views.filtered_products import render_filtered_products
    from dashboard.views.channel_discovery import render_channel_discovery
    from dashboard.views.channel_discovery_results import render_channel_discovery_results
    from dashboard.views.video_collection import render_video_collection
    from dashboard.views.google_sheets_management import render_google_sheets_management
    from dashboard.utils.database_manager import get_database_manager
except ImportError as e:
    print(f"Import error: {e}")
    render_monetizable_candidates = None
    render_filtered_products = None
    render_channel_discovery = None
    render_channel_discovery_results = None
    render_video_collection = None
    render_google_sheets_management = None
    get_database_manager = None

# 페이지 설정
st.set_page_config(
    page_title="연예인 추천 아이템 대시보드",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    /* 자동 생성된 페이지 네비게이션 숨기기 */
    [data-testid="stSidebarNav"] {display: none;}
    
    /* 사이드바 스타일 개선 */
    .css-1d391kg {padding-top: 1rem;}
    
    /* 메트릭 카드 스타일 */
    [data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #e0e2e6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* 버튼 스타일 개선 */
    .stButton > button {
        width: 100%;
        text-align: left;
        background-color: transparent;
        border: none;
        padding: 0.5rem 1rem;
        margin: 0.2rem 0;
        border-radius: 5px;
        transition: background-color 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #f0f2f6;
    }
    
    /* 선택된 메뉴 강조 */
    .selected-menu {
        background-color: #e0e2e6 !important;
        font-weight: bold;
    }
    
    /* 데이터프레임 스타일 */
    .dataframe {
        font-size: 14px;
    }
    
    /* 헤더 스타일 */
    h1 {
        color: #1f2937;
        font-weight: 700;
    }
    
    h2, h3 {
        color: #374151;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # 헤더
    st.title("🎬 연예인 추천 아이템 자동화 시스템")
    st.markdown("**PRD v1.0** - 유튜브 영상에서 제품을 자동 탐지하고 Instagram Reels 콘텐츠 후보 생성")
    
    # 실제 데이터베이스에서 통계 가져오기
    if get_database_manager:
        try:
            db = get_database_manager()
            stats = db.get_status_statistics()
            
            # 시스템 상태 대시보드
            st.markdown("### 📊 시스템 현황")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total = stats.get('total_candidates', 0)
                st.metric("총 후보 수", f"{total:,}", help="전체 분석된 후보 수")
                
            with col2:
                needs_review = stats.get('status_distribution', {}).get('needs_review', 0)
                approved = stats.get('status_distribution', {}).get('approved', 0)
                st.metric("수익화 가능 후보", f"{approved}", f"+{needs_review} 검토중", help="승인된 수익화 가능 제품")
                
            with col3:
                st.metric("월 예상 비용", "₩14,900", "정상", help="PRD 예상 비용 내 운영중")
                
            with col4:
                recent_changes = stats.get('recent_changes_24h', 0)
                status_text = "✅ 정상" if total > 0 else "⚠️ 대기중"
                st.metric("시스템 상태", status_text, f"{recent_changes} 오늘 변경", help="24시간 내 상태 변경 수")
                
        except Exception as e:
            st.error(f"데이터베이스 연결 오류: {e}")
            # 기본값 표시
            st.markdown("### 📊 시스템 현황")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("총 후보 수", "0", help="데이터베이스 연결 필요")
            with col2:
                st.metric("수익화 가능 후보", "0", help="데이터베이스 연결 필요")
            with col3:
                st.metric("월 예상 비용", "₩14,900", "정상", help="PRD 예상 비용 내 운영중")
            with col4:
                st.metric("시스템 상태", "⚠️ 연결 필요", "데이터베이스", help="데이터베이스 연결 필요")
    else:
        st.error("데이터베이스 모듈을 가져올 수 없습니다.")
    
    st.markdown("---")
    
    # 사이드바 메뉴
    with st.sidebar:
        st.markdown("## 📋 메뉴")
        
        # 후보 관리
        st.markdown("### 🎯 후보 관리")
        if st.button("수익화 가능 후보", key="menu_monetizable", use_container_width=True):
            st.session_state.current_page = "monetizable_candidates"
        if st.button("수익화 필터링 목록", key="menu_filtered", use_container_width=True):
            st.session_state.current_page = "filtered_products"
        
        # 채널 관리
        st.markdown("### 📺 채널 관리")
        if st.button("신규 채널 탐색", key="menu_discovery", use_container_width=True):
            st.session_state.current_page = "channel_discovery"
        if st.button("탐색 결과 관리", key="menu_results", use_container_width=True):
            st.session_state.current_page = "channel_discovery_results"
        if st.button("Google Sheets 연동", key="menu_sheets", use_container_width=True):
            st.session_state.current_page = "google_sheets_management"
        
        # 영상 관리
        st.markdown("### 🎥 영상 관리")
        if st.button("영상 수집 설정", key="menu_video", use_container_width=True):
            st.session_state.current_page = "video_collection"
        
        # 시스템 정보
        st.markdown("---")
        st.markdown("### ℹ️ 시스템 정보")
        st.info("""
        **워크플로우**
        1. 채널/영상 수집
        2. AI 2-Pass 분석
        3. PPL 필터링
        4. 수익화 검증
        5. 매력도 스코어링
        6. 운영자 검토
        """)
    
    # 현재 페이지 가져오기
    current_page = st.session_state.get('current_page', 'monetizable_candidates')
    
    # 메인 콘텐츠 영역
    main_container = st.container()
    
    with main_container:
        # 페이지 렌더링
        if current_page == "monetizable_candidates":
            if render_monetizable_candidates:
                render_monetizable_candidates()
            else:
                st.header("🎯 수익화 가능 후보")
                st.info("AI 2-Pass 분석을 통해 발견된 제품 추천 후보들")
                
                # 실제 데이터베이스에서 데이터 가져오기
                if get_database_manager:
                    try:
                        db = get_database_manager()
                        
                        # 필터 UI
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            search = st.text_input("🔍 검색", placeholder="연예인, 제품명, 영상 제목...", key="search_candidates")
                        with col2:
                            status_filter = st.selectbox("상태", ["전체", "needs_review", "approved", "rejected", "filtered_no_coupang"], key="status_filter")
                        with col3:
                            limit = st.selectbox("표시 개수", [10, 25, 50, 100], index=1, key="limit_filter")
                        
                        # 상태 필터 적용
                        filter_status = None if status_filter == "전체" else status_filter
                        candidates = db.get_candidates_by_status(status=filter_status, limit=limit)
                        
                        if candidates:
                            # 데이터프레임 생성
                            df_data = []
                            for candidate in candidates:
                                source_info = candidate.get('source_info', {})
                                candidate_info = candidate.get('candidate_info', {})
                                status_info = candidate.get('status_info', {})
                                
                                # 검색 필터 적용
                                if search:
                                    search_text = f"{source_info.get('celebrity_name', '')} {candidate_info.get('product_name_ai', '')} {source_info.get('video_title', '')}".lower()
                                    if search.lower() not in search_text:
                                        continue
                                
                                df_data.append({
                                    "ID": candidate['id'][:12] + "...",
                                    "연예인": source_info.get('celebrity_name', 'N/A'),
                                    "제품명": candidate_info.get('product_name_ai', 'N/A'),
                                    "영상 제목": source_info.get('video_title', 'N/A')[:30] + "...",
                                    "매력도 점수": candidate_info.get('score_details', {}).get('total', 0),
                                    "상태": status_info.get('current_status', 'unknown'),
                                    "생성일": candidate.get('created_at', '')[:10] if candidate.get('created_at') else 'N/A',
                                    "AI 생성 훅": candidate_info.get('hook_sentence', 'N/A')[:50] + "..."
                                })
                            
                            if df_data:
                                df = pd.DataFrame(df_data)
                                
                                # 데이터 표시
                                st.dataframe(
                                    df,
                                    use_container_width=True,
                                    column_config={
                                        "매력도 점수": st.column_config.ProgressColumn(
                                            "매력도 점수",
                                            help="AI가 산출한 매력도 점수",
                                            format="%d",
                                            min_value=0,
                                            max_value=100,
                                        ),
                                        "상태": st.column_config.SelectboxColumn(
                                            "상태",
                                            options=["needs_review", "approved", "rejected", "filtered_no_coupang"],
                                            help="현재 검토 상태"
                                        )
                                    }
                                )
                                
                                st.info(f"총 {len(df_data)}개의 후보를 표시하고 있습니다.")
                            else:
                                st.warning("검색 조건에 맞는 후보가 없습니다.")
                        else:
                            st.warning("등록된 후보가 없습니다. AI 분석 파이프라인을 실행하여 후보를 생성해주세요.")
                            
                    except Exception as e:
                        st.error(f"데이터 로딩 오류: {e}")
                        st.info("데이터베이스가 초기화되지 않았거나 연결에 문제가 있습니다.")
                else:
                    st.error("데이터베이스 연결을 설정할 수 없습니다.")
                
        elif current_page == "filtered_products" and render_filtered_products:
            render_filtered_products()
        elif current_page == "channel_discovery" and render_channel_discovery:
            render_channel_discovery()
        elif current_page == "channel_discovery_results" and render_channel_discovery_results:
            render_channel_discovery_results()
        elif current_page == "google_sheets_management" and render_google_sheets_management:
            render_google_sheets_management()
        elif current_page == "video_collection" and render_video_collection:
            render_video_collection()
        else:
            st.error("페이지를 찾을 수 없습니다.")
    
    # 푸터
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col2:
        st.caption("© 2025 연예인 추천 아이템 자동화 시스템")
    with col3:
        st.caption("PRD v1.0 | Python 3.11 | Streamlit")

if __name__ == "__main__":
    main()