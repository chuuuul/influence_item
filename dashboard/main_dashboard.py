"""
연예인 추천 아이템 자동화 시스템 - 관리 대시보드
S03-001: Streamlit 기반 관리 대시보드 기본 구조
"""

import streamlit as st
import sys
import os
import time
import psutil
import gc
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Any

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 페이지 모듈 import
try:
    from dashboard.pages.monetizable_candidates import render_monetizable_candidates
    from dashboard.pages.filtered_products import render_filtered_products
    from dashboard.pages.ai_content_generator import render_ai_content_generator
    from dashboard.components.detail_view import render_detail_view
    from dashboard.utils.performance_monitor import (
        get_performance_monitor, 
        optimize_streamlit_config,
        measure_page_load_time,
        check_performance_thresholds
    )
except ImportError:
    render_monetizable_candidates = None
    render_filtered_products = None
    render_ai_content_generator = None
    render_detail_view = None
    get_performance_monitor = None
    optimize_streamlit_config = None
    measure_page_load_time = None
    check_performance_thresholds = None

@st.cache_resource
def get_system_info() -> Dict[str, Any]:
    """시스템 정보 캐싱"""
    return {
        "version": "v1.0.0",
        "status": "🟢 정상 운영",
        "last_update": "방금 전"
    }

@st.cache_data(ttl=300)  # 5분 캐시
def get_dashboard_metrics() -> Dict[str, Any]:
    """대시보드 메트릭 캐싱"""
    # 실제로는 데이터베이스에서 가져와야 함
    return {
        "total_videos": 31,
        "monetizable_candidates": 23,
        "filtered_items": 8,
        "approved_items": 12,
        "today_videos": 5,
        "new_candidates": 3,
        "resolved_filtered": -2,
        "today_approved": 4
    }

@st.cache_data(ttl=60)  # 1분 캐시
def get_recent_activities() -> List[Dict[str, str]]:
    """최근 활동 데이터 캐싱"""
    return [
        {"time": "2분 전", "activity": "새로운 영상 분석 완료", "status": "completed"},
        {"time": "15분 전", "activity": "제품 후보 3개 승인됨", "status": "completed"},
        {"time": "32분 전", "activity": "영상 분석 시작", "status": "processing"},
        {"time": "1시간 전", "activity": "쿠팡 API 연동 확인", "status": "completed"},
    ]

@st.cache_data(ttl=300)  # 5분 캐시
def get_system_status() -> Dict[str, int]:
    """시스템 상태 정보 캐싱"""
    return {
        "분석 대기": 5,
        "처리 중": 2,
        "완료": 23,
        "오류": 1
    }

def initialize_app():
    """앱 초기 설정"""
    st.set_page_config(
        page_title="연예인 추천 아이템 관리 대시보드 v1.0",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': """
            # 연예인 추천 아이템 자동화 시스템
            
            YouTube 영상에서 연예인이 추천하는 제품을 AI로 자동 탐지하고,  
            Instagram Reels 콘텐츠 생성을 통한 쿠팡 파트너스 제휴 마케팅 시스템
            
            **Version**: v1.0.0  
            **Tech Stack**: Streamlit, Gemini AI, Whisper, YOLOv8
            
            **키보드 단축키**:
            - Alt + H: 홈 페이지
            - Alt + M: 수익화 가능 후보
            - Alt + F: 수익화 필터링 목록
            - Alt + A: AI 콘텐츠 생성
            """
        }
    )
    
    # 키보드 단축키 지원을 위한 JavaScript
    keyboard_shortcuts = """
    <script>
    document.addEventListener('keydown', function(e) {
        if (e.altKey) {
            switch(e.key) {
                case 'h':
                case 'H':
                    e.preventDefault();
                    // 홈 페이지로 이동
                    window.parent.postMessage({type: 'navigate', page: 'home'}, '*');
                    break;
                case 'm':
                case 'M':
                    e.preventDefault();
                    // 수익화 후보 페이지로 이동
                    window.parent.postMessage({type: 'navigate', page: 'monetizable_candidates'}, '*');
                    break;
                case 'f':
                case 'F':
                    e.preventDefault();
                    // 필터링 목록 페이지로 이동
                    window.parent.postMessage({type: 'navigate', page: 'filtered_products'}, '*');
                    break;
                case 'a':
                case 'A':
                    e.preventDefault();
                    // AI 콘텐츠 생성 페이지로 이동
                    window.parent.postMessage({type: 'navigate', page: 'ai_content_generator'}, '*');
                    break;
            }
        }
    });
    </script>
    """
    
    # JavaScript를 페이지에 삽입
    st.components.v1.html(keyboard_shortcuts, height=0)
    
    # 커스텀 CSS 스타일 (성능 최적화 및 반응형)
    st.markdown("""
    <style>
    /* 메인 앱 스타일 */
    .main .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }
    
    .main-header {
        padding: 2rem 0;
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .main-header p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin: 0;
    }
    
    /* 메트릭 카드 */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        border-left: 4px solid #667eea;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    
    /* 상태 배지 */
    .status-badge {
        padding: 0.4rem 0.8rem;
        border-radius: 25px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-pending { background-color: #fff3cd; color: #856404; }
    .status-processing { background-color: #d1ecf1; color: #0c5460; }
    .status-completed { background-color: #d4edda; color: #155724; }
    .status-failed { background-color: #f8d7da; color: #721c24; }
    
    /* 활동 카드 */
    .activity-card {
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 3px solid #667eea;
        background: #f8f9fa;
        border-radius: 8px;
        transition: background-color 0.2s ease;
    }
    
    .activity-card:hover {
        background: #e9ecef;
    }
    
    .activity-time {
        color: #6c757d;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2);
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
    }
    
    /* 사이드바 스타일 */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    /* 활성 메뉴 버튼 스타일 */
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border: 2px solid #667eea !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
    }
    
    .stButton > button[data-testid="baseButton-secondary"] {
        background: transparent !important;
        color: #495057 !important;
        border: 1px solid #dee2e6 !important;
        font-weight: 500 !important;
    }
    
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background: #f8f9fa !important;
        border-color: #667eea !important;
        color: #667eea !important;
    }
    
    /* 알림 박스 개선 */
    .stAlert {
        border-radius: 10px;
        border: none;
    }
    
    /* 푸터 스타일 */
    .footer {
        text-align: center;
        color: #6c757d;
        font-size: 0.9rem;
        margin-top: 3rem;
        padding: 2rem 0;
        border-top: 1px solid #dee2e6;
    }
    
    .footer a {
        color: #667eea;
        text-decoration: none;
        font-weight: 500;
    }
    
    .footer a:hover {
        text-decoration: underline;
    }
    
    /* 성능 최적화 */
    * {
        box-sizing: border-box;
    }
    
    .main .block-container {
        will-change: transform;
    }
    
    /* 이미지 최적화 */
    img {
        max-width: 100%;
        height: auto;
        loading: lazy;
    }
    
    /* 애니메이션 최적화 */
    .metric-card, .activity-card, .stButton > button {
        transform: translateZ(0);
        backface-visibility: hidden;
    }
    
    /* 반응형 디자인 - 태블릿 (768px - 1023px) */
    @media (min-width: 768px) and (max-width: 1023px) {
        .main .block-container {
            max-width: 95%;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        .main-header h1 {
            font-size: 2rem;
        }
        
        .main-header p {
            font-size: 1rem;
        }
        
        .sidebar .sidebar-content {
            padding: 0.75rem;
        }
    }
    
    /* 반응형 디자인 - 모바일 (768px 이하) */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 1.8rem;
        }
        
        .main-header p {
            font-size: 0.9rem;
        }
        
        .main .block-container {
            padding-top: 1rem;
        }
        
        .metric-card {
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .activity-card {
            padding: 0.75rem;
        }
    }
    
    /* 작은 모바일 디바이스 (480px 이하) */
    @media (max-width: 480px) {
        .main-header {
            padding: 1.5rem 1rem;
        }
        
        .main-header h1 {
            font-size: 1.5rem;
        }
        
        .sidebar .sidebar-content {
            padding: 0.5rem;
        }
        
        .stButton > button {
            font-size: 0.8rem;
            padding: 0.4rem 0.8rem;
        }
    }
    
    /* 데스크톱 (1024px 이상) */
    @media (min-width: 1024px) {
        .main .block-container {
            max-width: 1400px;
        }
        
        .sidebar .sidebar-content {
            padding: 1rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def render_breadcrumb():
    """브레드크럼 네비게이션 렌더링"""
    current_page = st.session_state.get('current_page', 'home')
    
    # 페이지별 브레드크럼 정의
    breadcrumb_map = {
        'home': [('🏠', '홈')],
        'monetizable_candidates': [('🏠', '홈'), ('💰', '수익화 가능 후보')],
        'filtered_products': [('🏠', '홈'), ('🔍', '수익화 필터링 목록')],
        'ai_content_generator': [('🏠', '홈'), ('🔧', '분석 도구'), ('🤖', 'AI 콘텐츠 생성')],
        'detail_view': [('🏠', '홈'), ('💰', '수익화 가능 후보'), ('📋', '상세 뷰')],
        'video_analysis': [('🏠', '홈'), ('🔧', '분석 도구'), ('📹', '영상 분석')],
        'statistics': [('🏠', '홈'), ('📊', '관리'), ('📈', '통계 및 리포트')],
        'settings': [('🏠', '홈'), ('📊', '관리'), ('⚙️', '시스템 설정')]
    }
    
    breadcrumb_items = breadcrumb_map.get(current_page, [('🏠', '홈')])
    
    # 브레드크럼 HTML 생성
    breadcrumb_html = '<div style="margin: 1rem 0; padding: 0.5rem 0; border-bottom: 1px solid #dee2e6;">'
    for i, (icon, name) in enumerate(breadcrumb_items):
        if i > 0:
            breadcrumb_html += ' <span style="color: #6c757d; margin: 0 0.5rem;">></span> '
        
        if i == len(breadcrumb_items) - 1:  # 현재 페이지
            breadcrumb_html += f'<span style="color: #667eea; font-weight: 600;">{icon} {name}</span>'
        else:
            breadcrumb_html += f'<span style="color: #6c757d;">{icon} {name}</span>'
    
    breadcrumb_html += '</div>'
    st.markdown(breadcrumb_html, unsafe_allow_html=True)

def render_header():
    """메인 헤더 렌더링"""
    st.markdown("""
    <div class="main-header">
        <h1>🎬 연예인 추천 아이템 관리 대시보드</h1>
        <p>YouTube 영상 분석을 통한 수익화 가능 제품 후보 관리 시스템</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """사이드바 네비게이션 렌더링"""
    st.sidebar.title("📊 대시보드 메뉴")
    
    # 메뉴 항목들을 그룹으로 분류 - PRD 명세에 따른 Master-Detail 구조
    menu_groups = {
        "📋 핵심 기능": {
            "🏠 홈": "home",
            "💰 수익화 가능 후보": "monetizable_candidates", 
            "🔍 수익화 필터링 목록": "filtered_products"
        },
        "🔧 분석 도구": {
            "🤖 AI 콘텐츠 생성": "ai_content_generator",
            "📹 영상 분석": "video_analysis"
        },
        "📊 관리 및 설정": {
            "📈 통계 및 리포트": "statistics",
            "⚙️ 시스템 설정": "settings"
        }
    }
    
    # 모든 메뉴 항목을 평면화
    all_menu_items = {}
    for group_items in menu_groups.values():
        all_menu_items.update(group_items)
    
    # 현재 선택된 페이지 확인
    current_page = st.session_state.get('current_page', 'home')
    current_menu_key = None
    for key, value in all_menu_items.items():
        if value == current_page:
            current_menu_key = key
            break
    
    # 메뉴 그룹별로 렌더링
    selected_page = None
    for group_name, group_items in menu_groups.items():
        st.sidebar.markdown(f"**{group_name}**")
        for menu_key, page_value in group_items.items():
            is_selected = (current_menu_key == menu_key)
            if st.sidebar.button(
                menu_key, 
                key=f"menu_{page_value}",
                use_container_width=True,
                type="primary" if is_selected else "secondary"
            ):
                selected_page = page_value
        st.sidebar.markdown("---")
    
    # 페이지 선택 처리 및 상태 유지
    if selected_page:
        st.session_state.current_page = selected_page
        # 페이지 전환 시 이전 상태 정리
        if 'selected_product' in st.session_state and selected_page != 'detail_view':
            del st.session_state.selected_product
        st.rerun()
    
    # 시스템 상태 정보 (캐시된 데이터 사용)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 시스템 상태")
    
    status_info = get_system_status()
    for status, count in status_info.items():
        st.sidebar.metric(status, count)
    
    # 시스템 정보 (캐시된 데이터 사용)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ 시스템 정보")
    system_info = get_system_info()
    st.sidebar.info(f"""
    - **버전**: {system_info["version"]}
    - **상태**: {system_info["status"]}
    - **마지막 업데이트**: {system_info["last_update"]}
    """)

def render_home_page():
    """홈 페이지 렌더링 (성능 최적화)"""
    st.markdown("## 📊 대시보드 개요")
    
    # 캐시된 메트릭 데이터 로드
    metrics = get_dashboard_metrics()
    
    # 메트릭 카드들 - 반응형 레이아웃
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📹 총 분석 영상", 
            value=str(metrics["total_videos"]), 
            delta=f"{metrics['today_videos']} (오늘)"
        )
    
    with col2:
        st.metric(
            label="💰 수익화 후보",
            value=str(metrics["monetizable_candidates"]),
            delta=f"{metrics['new_candidates']} (신규)"
        )
    
    with col3:
        st.metric(
            label="🔍 필터링 항목",
            value=str(metrics["filtered_items"]),
            delta=f"{metrics['resolved_filtered']} (해결)"
        )
    
    with col4:
        st.metric(
            label="✅ 승인 완료",
            value=str(metrics["approved_items"]),
            delta=f"{metrics['today_approved']} (오늘)"
        )
    
    # 최근 활동 및 알림
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 최근 활동")
        # 캐시된 활동 데이터 사용
        recent_activities = get_recent_activities()
        
        for activity in recent_activities:
            status_class = f"status-{activity['status']}"
            st.markdown(f"""
            <div class="activity-card">
                <div class="activity-time">{activity['time']}</div>
                <div style="margin-top: 0.25rem;">
                    {activity['activity']} 
                    <span class="status-badge {status_class}">
                        {activity['status'].upper()}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 🔔 알림 및 공지")
        st.info("💡 새로운 매력도 스코어링 알고리즘이 적용되었습니다.")
        st.warning("⚠️ GPU 서버 메모리 사용량이 높습니다. (82%)")
        st.success("✅ 데이터베이스 백업이 성공적으로 완료되었습니다.")
    
    # 빠른 액션 버튼들
    st.markdown("---")
    st.markdown("### 🚀 빠른 실행")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔍 새 영상 분석 시작", use_container_width=True):
            st.info("영상 분석 기능은 곧 구현됩니다.")
    
    with col2:
        if st.button("📊 통계 리포트 생성", use_container_width=True):
            st.info("리포트 생성 기능은 곧 구현됩니다.")
    
    with col3:
        if st.button("💾 데이터 백업", use_container_width=True):
            st.info("백업 기능은 곧 구현됩니다.")
    
    with col4:
        if st.button("⚙️ 시스템 점검", use_container_width=True):
            st.info("시스템 점검 기능은 곧 구현됩니다.")

def render_placeholder_page(page_name: str):
    """플레이스홀더 페이지 렌더링"""
    page_titles = {
        "filtered_products": "🔍 필터링된 제품 관리", 
        "video_analysis": "📹 영상 분석 도구",
        "statistics": "📈 통계 및 리포트",
        "settings": "⚙️ 시스템 설정"
    }
    
    title = page_titles.get(page_name, "페이지")
    st.markdown(f"## {title}")
    
    st.info(f"""
    🚧 **{title} 페이지는 현재 개발 중입니다.**
    
    이 페이지는 S03 스프린트의 다음 단계에서 구현될 예정입니다:
    - 데이터 테이블 표시
    - 필터링 및 정렬 기능
    - 상세 뷰 및 편집 기능
    - 워크플로우 관리
    """)
    
    # 개발 예정 기능 미리보기
    if page_name == "filtered_products":
        st.markdown("### 🎯 예정 기능")
        st.markdown("""
        - **필터링 사유 표시**: 자동 필터링 이유 설명
        - **수동 링크 연결**: 쿠팡 파트너스 링크 직접 입력
        - **복원 기능**: 메인 목록으로 다시 이동
        - **검색 도구**: 보조 검색 기능 제공
        """)

def main():
    """메인 애플리케이션 (성능 최적화)"""
    # 성능 모니터링 시작
    if measure_page_load_time:
        end_measurement = measure_page_load_time("main_dashboard")
    
    # 성능 최적화 설정
    if optimize_streamlit_config:
        optimize_streamlit_config()
    
    # 앱 초기화
    initialize_app()
    
    # 헤더 렌더링
    render_header()
    
    # 브레드크럼 네비게이션 렌더링
    render_breadcrumb()
    
    # 사이드바 렌더링
    render_sidebar()
    
    # 현재 페이지 렌더링
    current_page = st.session_state.get('current_page', 'home')
    
    if current_page == 'home':
        render_home_page()
    elif current_page == 'monetizable_candidates':
        if render_monetizable_candidates:
            render_monetizable_candidates()
        else:
            st.error("수익화 후보 페이지를 로드할 수 없습니다.")
    elif current_page == 'filtered_products':
        if render_filtered_products:
            render_filtered_products()
        else:
            st.error("필터링 제품 페이지를 로드할 수 없습니다.")
    elif current_page == 'ai_content_generator':
        if render_ai_content_generator:
            render_ai_content_generator()
        else:
            st.error("AI 콘텐츠 생성기 페이지를 로드할 수 없습니다.")
    elif current_page == 'detail_view':
        if render_detail_view and 'selected_product' in st.session_state:
            render_detail_view(st.session_state.selected_product)
        else:
            st.error("상세 뷰를 로드할 수 없거나 선택된 제품이 없습니다.")
            if st.button("← 뒤로 가기"):
                st.session_state.current_page = 'monetizable_candidates'
                st.rerun()
    else:
        render_placeholder_page(current_page)
    
    # 푸터
    st.markdown("""
    <div class="footer">
        © 2025 연예인 추천 아이템 자동화 시스템 v1.0<br>
        <small>Powered by Streamlit • Gemini AI • OpenAI Whisper • YOLOv8</small>
    </div>
    """, unsafe_allow_html=True)
    
    # 성능 측정 완료
    if measure_page_load_time and 'end_measurement' in locals():
        load_time = end_measurement()
        
        # 성능 경고 체크
        if check_performance_thresholds:
            thresholds = check_performance_thresholds()
            if not all(thresholds.values()):
                st.sidebar.warning("⚠️ 성능 최적화가 필요합니다.")
        
        # 개발 모드에서 성능 정보 표시
        if st.sidebar.checkbox("🔧 성능 정보 표시", help="개발/디버깅용"):
            st.sidebar.metric("페이지 로딩", f"{load_time:.1f}ms")

if __name__ == "__main__":
    main()