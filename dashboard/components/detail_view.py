"""
S03-004: 상세 뷰 및 영상 재생 기능
YouTube 임베드 플레이어 및 타임스탬프 자동 재생
"""

import streamlit as st
import pandas as pd
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

def extract_youtube_id(url):
    """YouTube URL에서 비디오 ID 추출"""
    if not url:
        return None
    
    # YouTube URL 패턴들
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def timestamp_to_seconds(timestamp):
    """타임스탬프를 초로 변환 (MM:SS 또는 HH:MM:SS 형식)"""
    if not timestamp:
        return 0
    
    # 범위 형식 처리 (MM:SS - MM:SS)
    if " - " in timestamp:
        start_time = timestamp.split(" - ")[0]
        timestamp = start_time
    
    parts = timestamp.split(":")
    if len(parts) == 2:  # MM:SS
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:  # HH:MM:SS  
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    
    return 0

def create_youtube_embed_url(video_id, start_time=0):
    """YouTube 임베드 URL 생성"""
    if not video_id:
        return None
    
    embed_url = f"https://www.youtube.com/embed/{video_id}?start={start_time}&autoplay=1&rel=0&showinfo=0"
    return embed_url

def render_youtube_player(video_url, timestamp="00:00", width=640, height=360):
    """YouTube 플레이어 렌더링"""
    video_id = extract_youtube_id(video_url)
    
    if not video_id:
        st.error("올바른 YouTube URL이 아닙니다.")
        return
    
    start_seconds = timestamp_to_seconds(timestamp)
    embed_url = create_youtube_embed_url(video_id, start_seconds)
    
    # YouTube 플레이어 임베드
    st.markdown(f"""
    <div style="position: relative; width: 100%; height: 0; padding-bottom: 56.25%;">
        <iframe 
            src="{embed_url}" 
            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
            frameborder="0" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen>
        </iframe>
    </div>
    """, unsafe_allow_html=True)

def render_product_gallery(product_data):
    """제품 이미지 갤러리 렌더링"""
    st.markdown("### 🖼️ 제품 이미지")
    
    # 샘플 이미지 (실제로는 프레임 추출 결과)
    sample_images = [
        "https://via.placeholder.com/300x200/667eea/ffffff?text=Frame+1",
        "https://via.placeholder.com/300x200/764ba2/ffffff?text=Frame+2", 
        "https://via.placeholder.com/300x200/f093fb/ffffff?text=Frame+3",
        "https://via.placeholder.com/300x200/4facfe/ffffff?text=Frame+4"
    ]
    
    col1, col2, col3, col4 = st.columns(4)
    
    for i, img_url in enumerate(sample_images):
        with [col1, col2, col3, col4][i]:
            st.image(img_url, caption=f"프레임 {i+1}", use_container_width=True)
            if st.button(f"🔍 확대", key=f"zoom_{i}"):
                st.session_state[f'zoomed_image_{i}'] = img_url

def render_analysis_details(product_data):
    """분석 상세 정보 렌더링"""
    st.markdown("### 📊 분석 상세 정보")
    
    # 분석 지표들
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📈 매력도 분석")
        
        # 감성 강도
        sentiment_score = product_data.get('감성_강도', 0.8)
        st.progress(sentiment_score, text=f"감성 강도: {sentiment_score:.2f}")
        
        # 실사용 인증
        usage_score = product_data.get('실사용_인증', 0.7) 
        st.progress(usage_score, text=f"실사용 인증: {usage_score:.2f}")
        
        # 인플루언서 신뢰도
        trust_score = product_data.get('인플루언서_신뢰도', 0.9)
        st.progress(trust_score, text=f"신뢰도: {trust_score:.2f}")
        
        # 종합 점수
        total_score = product_data.get('매력도_점수', 75.0)
        st.metric("종합 매력도", f"{total_score:.1f}점", f"+{total_score-70:.1f}")
    
    with col2:
        st.markdown("#### 🔍 감지된 키워드")
        
        # 샘플 키워드들
        keywords = [
            "강력 추천", "완전 대박", "진짜 좋아요", "솔직 후기",
            "직접 써봤는데", "효과 확실", "매일 사용", "립스틱"
        ]
        
        for keyword in keywords:
            confidence = np.random.uniform(0.6, 0.95)
            st.markdown(f"- **{keyword}** ({confidence:.1%} 신뢰도)")
        
        st.markdown("#### 📝 AI 분석 요약")
        st.info("""
        **긍정적 요소**:
        - 직접 사용 경험 언급
        - 구체적인 효과 설명
        - 자연스러운 추천 톤
        
        **주의사항**:
        - PPL 가능성 낮음 (90% 확률로 자연스러운 추천)
        - 제품 정보 명확함
        """)

def render_timeline_navigator(product_data):
    """타임라인 네비게이터 렌더링"""
    st.markdown("### ⏰ 타임라인 네비게이터")
    
    # 샘플 타임라인 데이터
    timeline_events = [
        {"time": "01:23", "event": "제품 첫 언급", "type": "mention"},
        {"time": "02:45", "event": "제품 사용 시연", "type": "usage"},
        {"time": "04:12", "event": "상세 리뷰 시작", "type": "review"},
        {"time": "06:30", "event": "추천 발언", "type": "recommendation"},
        {"time": "07:15", "event": "제품 정보 표시", "type": "info"}
    ]
    
    st.markdown("클릭하여 해당 시점으로 이동:")
    
    cols = st.columns(len(timeline_events))
    
    for i, event in enumerate(timeline_events):
        with cols[i]:
            # 이벤트 타입별 아이콘
            icons = {
                "mention": "💬",
                "usage": "👋", 
                "review": "📝",
                "recommendation": "👍",
                "info": "ℹ️"
            }
            
            icon = icons.get(event['type'], '⏰')
            
            if st.button(f"{icon} {event['time']}", key=f"timeline_{i}", use_container_width=True):
                st.session_state['current_timestamp'] = event['time']
                st.success(f"🎬 {event['time']} 시점으로 이동: {event['event']}")
                st.rerun()
            
            st.caption(event['event'])

def render_action_buttons(product_data):
    """액션 버튼들 렌더링"""
    st.markdown("### 🎯 상태 관리")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("✅ 승인", use_container_width=True, type="primary"):
            st.success("제품이 승인되었습니다!")
            st.balloons()
    
    with col2:
        if st.button("❌ 반려", use_container_width=True):
            st.error("제품이 반려되었습니다.")
    
    with col3:
        if st.button("✏️ 수정", use_container_width=True):
            st.info("수정 모드로 전환되었습니다.")
    
    with col4:
        if st.button("📊 재분석", use_container_width=True):
            st.info("재분석을 시작합니다...")

def render_ai_generated_content(product_data):
    """AI 생성 콘텐츠 표시"""
    # 새로운 AI 콘텐츠 컴포넌트 사용
    try:
        from dashboard.components.ai_content_display import render_ai_content_display
        render_ai_content_display(product_data)
    except ImportError:
        st.error("AI 콘텐츠 컴포넌트를 로드할 수 없습니다.")
        
        # 폴백: 기본 콘텐츠 표시
        st.markdown("### 🤖 AI 생성 콘텐츠 (기본 모드)")
        st.info("고급 AI 콘텐츠 기능이 곧 제공됩니다.")

def render_detail_view(product_data):
    """제품 상세 뷰 렌더링"""
    
    # 뒤로 가기 버튼
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← 뒤로 가기", use_container_width=True):
            st.session_state.current_page = 'monetizable_candidates'
            st.rerun()
    
    # 헤더
    st.markdown(f"# 📱 {product_data.get('제품명', '제품명')}")
    st.markdown(f"**채널**: {product_data.get('채널명', '채널명')} | **카테고리**: {product_data.get('카테고리', '카테고리')} | **점수**: {product_data.get('매력도_점수', 0)}점")
    
    # 영상 재생 및 기본 정보
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🎬 영상 재생")
        
        # 현재 타임스탬프 가져오기
        current_timestamp = st.session_state.get('current_timestamp', product_data.get('타임스탬프', '00:00'))
        
        # YouTube 플레이어
        if product_data.get('youtube_url'):
            render_youtube_player(
                product_data['youtube_url'], 
                current_timestamp.split(' - ')[0] if ' - ' in current_timestamp else current_timestamp
            )
        else:
            st.info("YouTube URL이 없습니다.")
        
        # 타임라인 네비게이터
        render_timeline_navigator(product_data)
    
    with col2:
        st.markdown("### 📋 기본 정보")
        
        info_data = {
            "영상 제목": product_data.get('영상_제목', '-'),
            "업로드 날짜": product_data.get('업로드_날짜', '-'),
            "조회수": product_data.get('조회수', '-'),
            "영상 길이": product_data.get('영상_길이', '-'),
            "타임스탬프": product_data.get('타임스탬프', '-'),
            "예상 가격": product_data.get('예상_가격', '-'),
            "상태": product_data.get('상태', '-')
        }
        
        for key, value in info_data.items():
            st.markdown(f"**{key}**: {value}")
        
        # 쿠팡 링크 (있는 경우)
        if product_data.get('쿠팡_링크'):
            st.markdown(f"**🛒 쿠팡 링크**: [바로가기]({product_data['쿠팡_링크']})")
    
    # 추가 정보 탭
    tab1, tab2, tab3, tab4 = st.tabs(["📊 분석 상세", "🖼️ 이미지", "🤖 AI 콘텐츠", "📝 처리 이력"])
    
    with tab1:
        render_analysis_details(product_data)
    
    with tab2:
        render_product_gallery(product_data)
    
    with tab3:
        render_ai_generated_content(product_data)
    
    with tab4:
        st.markdown("### 📝 처리 이력")
        
        # 샘플 처리 이력
        history = [
            {"date": "2025-06-22 14:30", "action": "시스템 분석 완료", "user": "시스템", "details": "매력도 점수 75.2점 산출"},
            {"date": "2025-06-22 14:35", "action": "쿠팡 링크 연결", "user": "시스템", "details": "자동 검색 성공"},
            {"date": "2025-06-22 15:00", "action": "검토 대기 상태", "user": "시스템", "details": "운영자 검토 요청"},
        ]
        
        for entry in history:
            with st.expander(f"{entry['date']} - {entry['action']}"):
                st.markdown(f"**처리자**: {entry['user']}")
                st.markdown(f"**상세**: {entry['details']}")
    
    # 액션 버튼
    st.markdown("---")
    render_action_buttons(product_data)

# numpy import 추가
import numpy as np

if __name__ == "__main__":
    # 테스트용 샘플 데이터
    sample_product = {
        "id": "PROD_001",
        "제품명": "히알루론산 세럼 - 프리미엄",
        "채널명": "홍지윤 Yoon",
        "영상_제목": "[일상VLOG] 스킨케어 추천 | 솔직 후기",
        "카테고리": "스킨케어",
        "매력도_점수": 85.3,
        "감성_강도": 0.87,
        "실사용_인증": 0.92,
        "인플루언서_신뢰도": 0.89,
        "상태": "검토중",
        "업로드_날짜": "2025-06-22",
        "조회수": "125,450",
        "영상_길이": "12:34",
        "타임스탬프": "04:23 - 06:15",
        "예상_가격": "45,000원",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
    
    render_detail_view(sample_product)