"""
T05_S01_M02: 상세 뷰 구조 및 T07_S01_M02: AI 콘텐츠 표시 통합
YouTube 임베드 플레이어 및 AI 생성 콘텐츠 복사 기능
"""

import streamlit as st
import pandas as pd
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import sys
from pathlib import Path
from .ai_content_display import render_ai_content_display_component
from .product_image_gallery import ProductImageGallery
from .external_search import ExternalSearchComponent

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dashboard.components.workflow_state_manager import render_workflow_state_component
    from dashboard.utils.database_manager import get_database_manager
except ImportError:
    render_workflow_state_component = None
    get_database_manager = None

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

def create_youtube_embed_url(video_id, start_time=0, auto_play=True):
    """
    T06_S01_M02: Enhanced YouTube Embed URL Generation
    YouTube 임베드 URL 생성 (향상된 파라미터 지원)
    """
    if not video_id:
        return None
    
    # 기본 임베드 파라미터
    params = {
        'start': max(0, int(start_time)),  # 음수 방지
        'rel': 0,  # 관련 영상 표시 안함
        'showinfo': 0,  # 제목 정보 숨김 (legacy)
        'modestbranding': 1,  # YouTube 로고 최소화
        'iv_load_policy': 3,  # 주석 숨김
        'enablejsapi': 1,  # JavaScript API 활성화
        'origin': 'https://localhost',  # 보안 강화
    }
    
    # 자동재생 설정 (모바일에서는 제한될 수 있음)
    if auto_play:
        params['autoplay'] = 1
    
    # URL 파라미터 생성
    param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    embed_url = f"https://www.youtube.com/embed/{video_id}?{param_string}"
    
    return embed_url

def render_youtube_player(video_url, timestamp="00:00", width=640, height=360, auto_play=True):
    """
    T06_S01_M02: Enhanced YouTube Player with Error Handling
    YouTube 플레이어 렌더링 (에러 처리 및 로딩 상태 관리 포함)
    """
    if not video_url:
        st.warning("⚠️ YouTube URL이 제공되지 않았습니다.")
        return False
    
    # 플레이어 로딩 상태 표시
    with st.spinner("🎬 YouTube 플레이어를 로드하는 중..."):
        video_id = extract_youtube_id(video_url)
        
        if not video_id:
            st.error("❌ 올바른 YouTube URL이 아닙니다.")
            st.info(f"입력된 URL: {video_url}")
            return False
        
        try:
            start_seconds = timestamp_to_seconds(timestamp)
            embed_url = create_youtube_embed_url(video_id, start_seconds, auto_play)
            
            # 플레이어 컨트롤 정보 표시
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**🎯 재생 시작 시점**: {timestamp}")
            with col2:
                if st.button("🔄 새로고침", key="player_refresh"):
                    st.rerun()
            with col3:
                # 전체 영상 링크
                full_url = f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}s"
                st.markdown(f"[🔗 새 탭에서 열기]({full_url})")
            
            # 반응형 YouTube 플레이어 임베드
            st.markdown(f"""
            <div class="youtube-player-container" style="
                position: relative; 
                width: 100%; 
                height: 0; 
                padding-bottom: 56.25%;
                margin: 10px 0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            ">
                <iframe 
                    src="{embed_url}" 
                    style="
                        position: absolute; 
                        top: 0; 
                        left: 0; 
                        width: 100%; 
                        height: 100%;
                        border: none;
                    "
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                    allowfullscreen
                    loading="lazy">
                </iframe>
            </div>
            
            <style>
                @media (max-width: 768px) {{
                    .youtube-player-container {{
                        padding-bottom: 75%; /* 모바일에서 더 높은 비율 */
                    }}
                }}
            </style>
            """, unsafe_allow_html=True)
            
            return True
            
        except Exception as e:
            st.error(f"❌ YouTube 플레이어 로딩 중 오류가 발생했습니다: {str(e)}")
            
            # 대체 링크 제공
            st.info("대신 YouTube에서 직접 시청하세요:")
            backup_url = f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}s"
            st.markdown(f"[🎬 YouTube에서 시청하기]({backup_url})")
            
            return False

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

def render_timeline_navigator(candidate_data, video_url=None):
    """
    T06_S01_M02: Enhanced Timeline Navigator with Timestamp Auto-Play
    타임라인 네비게이터 렌더링 (타임스탬프 자동 재생 지원)
    """
    st.markdown("### ⏰ 타임라인 네비게이터")
    
    # PRD JSON 스키마에서 타임스탬프 정보 추출
    candidate_info = candidate_data.get('candidate_info', {}) if candidate_data else {}
    clip_start = candidate_info.get('clip_start_time', 0)
    clip_end = candidate_info.get('clip_end_time', 0)
    
    # 타임라인 이벤트 생성 (실제 데이터 기반 + 샘플)
    timeline_events = []
    
    # 실제 제품 언급 구간이 있는 경우
    if clip_start > 0:
        start_min, start_sec = divmod(clip_start, 60)
        timeline_events.append({
            "time": f"{start_min:02d}:{start_sec:02d}",
            "seconds": clip_start,
            "event": "제품 언급 시작",
            "type": "mention"
        })
        
        if clip_end > clip_start:
            end_min, end_sec = divmod(clip_end, 60)
            timeline_events.append({
                "time": f"{end_min:02d}:{end_sec:02d}",
                "seconds": clip_end, 
                "event": "제품 언급 종료",
                "type": "info"
            })
    
    # 추가 샘플 이벤트 (실제 구현에서는 AI 분석 결과 사용)
    if not timeline_events:
        timeline_events = [
            {"time": "01:23", "seconds": 83, "event": "제품 첫 언급", "type": "mention"},
            {"time": "02:45", "seconds": 165, "event": "제품 사용 시연", "type": "usage"},
            {"time": "04:12", "seconds": 252, "event": "상세 리뷰 시작", "type": "review"},
            {"time": "06:30", "seconds": 390, "event": "추천 발언", "type": "recommendation"},
            {"time": "07:15", "seconds": 435, "event": "제품 정보 표시", "type": "info"}
        ]
    
    if not timeline_events:
        st.info("📭 타임라인 이벤트가 없습니다.")
        return
    
    st.markdown("🎯 **클릭하여 해당 시점으로 이동:**")
    
    # 이벤트 개수에 따라 동적 컬럼 생성
    num_events = len(timeline_events)
    if num_events <= 5:
        cols = st.columns(num_events)
    else:
        # 너무 많으면 두 줄로 분할
        cols1 = st.columns(min(5, num_events))
        if num_events > 5:
            cols2 = st.columns(num_events - 5)
            cols = list(cols1) + list(cols2)
        else:
            cols = cols1
    
    for i, event in enumerate(timeline_events):
        if i < len(cols):
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
                button_text = f"{icon} {event['time']}"
                
                if st.button(button_text, key=f"timeline_{i}", use_container_width=True):
                    # 세션 상태에 타임스탬프 저장
                    st.session_state['current_timestamp'] = event['time']
                    st.session_state['current_timestamp_seconds'] = event['seconds']
                    
                    st.success(f"🎬 {event['time']} 시점으로 이동: {event['event']}")
                    
                    # YouTube 플레이어가 있으면 새로고침하여 해당 시점에서 재생
                    if video_url:
                        st.info("⏳ 플레이어를 새로운 시점으로 업데이트하는 중...")
                        # 페이지 새로고침으로 새 타임스탬프 반영
                        st.rerun()
                
                # 이벤트 설명
                st.caption(event['event'])
    
    # 현재 선택된 타임스탬프 표시
    if 'current_timestamp' in st.session_state:
        current_time = st.session_state['current_timestamp']
        st.info(f"🎯 **현재 선택된 시점**: {current_time}")
        
        # 타임스탬프 직접 입력 옵션
        with st.expander("🎛️ 타임스탬프 직접 설정"):
            col1, col2 = st.columns([3, 1])
            with col1:
                manual_timestamp = st.text_input(
                    "시간 입력 (MM:SS 또는 HH:MM:SS)",
                    value=current_time,
                    help="예: 02:30 또는 1:02:30"
                )
            with col2:
                if st.button("▶️ 재생", use_container_width=True):
                    st.session_state['current_timestamp'] = manual_timestamp
                    st.session_state['current_timestamp_seconds'] = timestamp_to_seconds(manual_timestamp)
                    st.rerun()

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

def render_ai_generated_content(candidate_data):
    """
    T07_S01_M02: AI 생성 콘텐츠 표시 
    PRD SPEC-DASH-03 요구사항에 따라 AI 콘텐츠를 복사 기능과 함께 제공
    """
    try:
        # PRD JSON 스키마 기반 AI 콘텐츠 컴포넌트 사용
        render_ai_content_display_component(candidate_data)
    except Exception as e:
        st.error(f"AI 콘텐츠 컴포넌트 로드 오류: {e}")
        
        # 폴백: 기본 콘텐츠 표시
        st.markdown("### 🤖 AI 생성 콘텐츠 (폴백 모드)")
        st.warning("고급 AI 콘텐츠 기능을 일시적으로 사용할 수 없습니다.")
        
        # 기본 정보 표시
        if 'candidate_info' in candidate_data:
            candidate_info = candidate_data['candidate_info']
            
            if candidate_info.get('recommended_titles'):
                st.markdown("**추천 제목:**")
                for title in candidate_info['recommended_titles']:
                    st.markdown(f"• {title}")
            
            if candidate_info.get('recommended_hashtags'):
                st.markdown("**해시태그:**")
                hashtag_text = " ".join(candidate_info['recommended_hashtags'])
                st.code(hashtag_text)
            
            if candidate_info.get('summary_for_caption'):
                st.markdown("**캡션:**")
                st.text_area("", value=candidate_info['summary_for_caption'], disabled=True)

def render_detail_view_enhanced(candidate_data):
    """
    T05_S01_M02: Enhanced Detail View with PRD JSON Schema Support
    PRD Section 3.3 JSON 스키마 구조를 완전히 지원하는 상세 뷰
    """
    
    # 데이터 없음 상태 처리
    if not candidate_data:
        st.error("⚠️ 선택된 후보 데이터가 없습니다.")
        st.info("목록 페이지로 돌아가서 후보를 선택해주세요.")
        if st.button("🔙 목록으로 돌아가기", type="primary"):
            st.session_state.current_page = 'monetizable_candidates'
            st.rerun()
        return
    
    # JSON 스키마 구조 파싱
    source_info = candidate_data.get('source_info', {})
    candidate_info = candidate_data.get('candidate_info', {})
    monetization_info = candidate_data.get('monetization_info', {})
    status_info = candidate_data.get('status_info', {})
    
    # 레거시 데이터 지원 (기존 구조와 호환)
    if not source_info and '채널명' in candidate_data:
        source_info = {
            'celebrity_name': candidate_data.get('채널명', ''),
            'channel_name': candidate_data.get('채널명', ''),
            'video_title': candidate_data.get('영상_제목', ''),
            'video_url': candidate_data.get('youtube_url', ''),
            'upload_date': candidate_data.get('업로드_날짜', '')
        }
        candidate_info = {
            'product_name_ai': candidate_data.get('제품명', ''),
            'category_path': [candidate_data.get('카테고리', '')],
            'clip_start_time': 0,
            'clip_end_time': 0,
            'score_details': {
                'total': candidate_data.get('매력도_점수', 0),
                'sentiment_score': candidate_data.get('감성_강도', 0),
                'endorsement_score': candidate_data.get('실사용_인증', 0),
                'influencer_score': candidate_data.get('인플루언서_신뢰도', 0)
            }
        }
        status_info = {
            'current_status': candidate_data.get('상태', 'needs_review'),
            'is_ppl': False,
            'ppl_confidence': 0.1
        }
    
    # 상단 네비게이션
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if st.button("🔙 뒤로 가기", use_container_width=True):
            st.session_state.current_page = 'monetizable_candidates'
            st.rerun()
    
    with col3:
        # 새로고침 버튼
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()
    
    # 제품 정보 헤더
    product_name = candidate_info.get('product_name_ai', 'Unknown Product')
    channel_name = source_info.get('channel_name', 'Unknown Channel')
    total_score = candidate_info.get('score_details', {}).get('total', 0)
    
    st.markdown(f"# 🎯 {product_name}")
    
    # 헤더 메타 정보
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📺 채널", channel_name)
    with col2:
        categories = candidate_info.get('category_path', ['Unknown'])
        st.metric("🏷️ 카테고리", ' > '.join(categories))
    with col3:
        st.metric("⭐ 매력도 점수", f"{total_score:.1f}점")
    with col4:
        current_status = status_info.get('current_status', 'needs_review')
        status_colors = {
            'needs_review': '🟡',
            'approved': '🟢', 
            'rejected': '🔴',
            'published': '🎉'
        }
        st.metric("📊 상태", f"{status_colors.get(current_status, '⚪')} {current_status}")


def render_source_info_section(source_info):
    """영상 정보 섹션 렌더링"""
    st.markdown("### 📺 영상 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**연예인**: {source_info.get('celebrity_name', 'N/A')}")
        st.markdown(f"**채널명**: {source_info.get('channel_name', 'N/A')}")
        st.markdown(f"**영상 제목**: {source_info.get('video_title', 'N/A')}")
    
    with col2:
        st.markdown(f"**업로드 날짜**: {source_info.get('upload_date', 'N/A')}")
        video_url = source_info.get('video_url', '')
        if video_url:
            st.markdown(f"**YouTube URL**: [링크]({video_url})")
        else:
            st.markdown("**YouTube URL**: N/A")


def render_product_info_section(candidate_info):
    """제품 정보 섹션 렌더링"""
    st.markdown("### 🛍️ 제품 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**AI 인식 제품명**: {candidate_info.get('product_name_ai', 'N/A')}")
        st.markdown(f"**수동 수정 제품명**: {candidate_info.get('product_name_manual', 'N/A') or '없음'}")
        
        # 카테고리 경로
        category_path = candidate_info.get('category_path', [])
        if category_path:
            st.markdown(f"**카테고리**: {' > '.join(category_path)}")
        else:
            st.markdown("**카테고리**: N/A")
    
    with col2:
        # 타임스탬프 정보
        start_time = candidate_info.get('clip_start_time', 0)
        end_time = candidate_info.get('clip_end_time', 0)
        if start_time or end_time:
            start_min, start_sec = divmod(start_time, 60)
            end_min, end_sec = divmod(end_time, 60)
            st.markdown(f"**타임스탬프**: {start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}")
        else:
            st.markdown("**타임스탬프**: N/A")
        
        # 제품 특징
        features = candidate_info.get('features', [])
        if features:
            st.markdown("**제품 특징**:")
            for feature in features:
                st.markdown(f"- {feature}")
        else:
            st.markdown("**제품 특징**: 없음")


def render_product_image_gallery_section(candidate_data):
    """제품 이미지 갤러리 섹션 렌더링"""
    st.markdown("### 🖼️ 제품 이미지 갤러리")
    
    # 이미지 데이터 추출 시도
    product_images = []
    
    # 1. candidate_data에서 직접 이미지 정보 확인
    if 'selected_product_images' in candidate_data:
        product_images = candidate_data['selected_product_images']
    elif 'all_product_images' in candidate_data:
        product_images = candidate_data['all_product_images']
    
    # 2. 분석 결과에서 추출 시도
    analysis_results = candidate_data.get('analysis_results', {})
    if not product_images and 'frame_analysis' in analysis_results:
        frame_analysis = analysis_results['frame_analysis']
        if hasattr(frame_analysis, 'selected_product_images'):
            product_images = frame_analysis.selected_product_images
        elif hasattr(frame_analysis, 'all_product_images'):
            product_images = frame_analysis.all_product_images
    
    # 3. 샘플 데이터 (개발/테스트용)
    if not product_images:
        st.info("현재 이 후보에 대해 추출된 제품 이미지가 없습니다.")
        
        # 개발용 샘플 데이터
        with st.expander("📋 샘플 이미지 데이터 (개발용)", expanded=False):
            if st.button("샘플 이미지 데이터 로드"):
                # 실제 이미지 파일 없이 메타데이터만 시뮬레이션
                sample_images = []
                for i in range(4):
                    sample_image = {
                        "hash": f"sample_hash_{i}",
                        "timestamp": 85.2 + i * 15,
                        "composite_score": 0.65 + (i * 0.08),
                        "object_confidence": 0.45 + (i * 0.1),
                        "quality_scores": {
                            "sharpness": 0.7 + (i * 0.05),
                            "size": 0.8 + (i * 0.02),
                            "brightness": 0.6 + (i * 0.03),
                            "contrast": 0.75 + (i * 0.01)
                        },
                        "image_dimensions": {
                            "width": 1280 + i * 64,
                            "height": 720 + i * 36
                        },
                        "file_paths": {
                            "original": f"temp/product_images/sample_{i}.jpg",
                            "thumbnail_150": f"temp/product_images/thumbnails_150/sample_{i}_150.jpg",
                            "thumbnail_300": f"temp/product_images/thumbnails_300/sample_{i}_300.jpg"
                        },
                        "file_sizes": {
                            "original": 180000 + i * 25000,
                            "thumbnail_150": 12000 + i * 1500,
                            "thumbnail_300": 35000 + i * 4000
                        },
                        "timeframe_info": {
                            "start_time": 80.0,
                            "end_time": 120.0,
                            "confidence_score": 0.85,
                            "reason": "제품 사용 시연 구간"
                        }
                    }
                    sample_images.append(sample_image)
                
                st.session_state[f'sample_images_{id(candidate_data)}'] = sample_images
                st.success("샘플 이미지 데이터가 로드되었습니다!")
                st.rerun()
        
        # 세션에서 샘플 데이터 확인
        sample_key = f'sample_images_{id(candidate_data)}'
        if sample_key in st.session_state:
            product_images = st.session_state[sample_key]
    
    # 4. 갤러리 표시
    if product_images:
        try:
            gallery = ProductImageGallery()
            
            # 갤러리 표시 옵션
            col1, col2, col3 = st.columns(3)
            with col1:
                columns = st.selectbox("열 개수", [2, 3, 4], index=1, key="gallery_columns")
            with col2:
                show_metadata = st.checkbox("메타데이터 표시", value=True, key="show_metadata")
            with col3:
                show_selection = st.checkbox("선택 기능", value=True, key="show_selection")
            
            # 갤러리 렌더링
            selected_images = gallery.display_gallery(
                product_images=product_images,
                key_prefix=f"detail_gallery_{id(candidate_data)}",
                columns=columns,
                show_selection=show_selection,
                show_metadata=show_metadata
            )
            
            # 선택된 이미지 정보 표시
            if show_selection and selected_images:
                st.markdown("---")
                st.markdown("### 📊 선택된 이미지 정보")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    avg_quality = sum(img.get("composite_score", 0) for img in selected_images) / len(selected_images)
                    st.metric("평균 품질 점수", f"{avg_quality:.3f}")
                
                with col2:
                    avg_confidence = sum(img.get("object_confidence", 0) for img in selected_images) / len(selected_images)
                    st.metric("평균 객체 신뢰도", f"{avg_confidence:.3f}")
                
                with col3:
                    total_size = sum(img.get("file_sizes", {}).get("original", 0) for img in selected_images)
                    st.metric("총 파일 크기", f"{total_size // 1024} KB")
                
                # JSON 내보내기
                if st.button("📤 선택된 이미지 정보 JSON 내보내기"):
                    export_data = gallery.export_selected_images_info(selected_images)
                    st.json(export_data)
                    st.success("선택된 이미지 정보를 JSON 형태로 내보냈습니다.")
            
            # 이미지 추출 통계
            st.markdown("---")
            st.markdown("### 📈 이미지 추출 통계")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("총 이미지 수", len(product_images))
            
            with col2:
                if product_images:
                    max_quality = max(img.get("composite_score", 0) for img in product_images)
                    st.metric("최고 품질 점수", f"{max_quality:.3f}")
            
            with col3:
                if product_images:
                    time_range = max(img.get("timestamp", 0) for img in product_images) - min(img.get("timestamp", 0) for img in product_images)
                    st.metric("시간 범위", f"{time_range:.1f}초")
            
            with col4:
                if product_images and product_images[0].get("timeframe_info"):
                    timeframe_confidence = product_images[0]["timeframe_info"].get("confidence_score", 0)
                    st.metric("구간 신뢰도", f"{timeframe_confidence:.3f}")
                
        except Exception as e:
            st.error(f"이미지 갤러리 렌더링 중 오류가 발생했습니다: {str(e)}")
            st.exception(e)
    
    else:
        st.info("🔍 제품 이미지를 추출하려면 AI 분석 파이프라인에서 이미지 추출 옵션을 활성화해야 합니다.")
        
        # 도움말
        with st.expander("💡 제품 이미지 추출 방법", expanded=False):
            st.markdown("""
            제품 이미지는 다음과 같은 과정을 통해 자동으로 추출됩니다:
            
            1. **타겟 시간대 분석**: AI가 제품 언급 구간을 식별
            2. **프레임 추출**: 해당 구간에서 고품질 프레임들을 추출
            3. **품질 평가**: 선명도, 해상도, 객체 탐지 신뢰도 기반으로 점수 계산
            4. **이미지 선별**: 최고 품질의 이미지 3-5개를 자동 선별
            5. **썸네일 생성**: 다양한 크기의 썸네일 자동 생성
            
            **주요 평가 기준**:
            - **선명도 (40%)**: Laplacian variance 기반 blur 측정
            - **해상도 (30%)**: 이미지 크기 및 화질
            - **객체 탐지 신뢰도 (30%)**: YOLO 모델의 제품 인식 정확도
            """)


def render_external_search_section(candidate_data):
    """
    T03_S02_M02: 외부 검색 연동 기능 섹션 렌더링
    PRD SPEC-DASH-04의 반자동 보조 검색 기능 구현
    """
    try:
        # 외부 검색 컴포넌트 초기화
        search_component = ExternalSearchComponent()
        
        # 후보 ID 추출
        candidate_id = candidate_data.get('id') or f"candidate_{hash(str(candidate_data))}"
        
        # 검색 섹션 렌더링
        search_event = search_component.render_search_section(
            candidate_data, 
            key_prefix=f"detail_search_{candidate_id}"
        )
        
        # 검색 이벤트 처리
        if search_event:
            # 검색 이벤트 데이터베이스에 저장
            try:
                search_event['session_key'] = f"detail_search_{candidate_id}"
                
                if get_database_manager:
                    db_manager = get_database_manager()
                    success = db_manager.save_search_event(candidate_id, search_event)
                    
                    if success:
                        st.info("🔍 검색 이력이 저장되었습니다.")
                    else:
                        st.warning("⚠️ 검색 이력 저장에 실패했습니다.")
                        
            except Exception as e:
                st.error(f"검색 이벤트 저장 중 오류: {str(e)}")
        
        # 검색 이력 표시 (접힌 상태로)
        with st.expander("📊 이 제품의 검색 이력", expanded=False):
            if get_database_manager:
                try:
                    db_manager = get_database_manager()
                    search_history = db_manager.get_search_history(candidate_id, limit=10)
                    
                    if search_history:
                        st.markdown("**최근 검색 기록**")
                        
                        for i, search in enumerate(search_history):
                            engine_icons = {'google': '🔍', 'naver': '🟢'}
                            type_icons = {'text': '📝', 'image': '🖼️', 'shopping': '🛍️'}
                            
                            engine_icon = engine_icons.get(search['search_engine'], '🔍')
                            type_icon = type_icons.get(search['search_type'], '📝')
                            
                            timestamp = search['timestamp']
                            if isinstance(timestamp, str):
                                try:
                                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    timestamp_str = timestamp.strftime('%m-%d %H:%M')
                                except:
                                    timestamp_str = timestamp[:16]
                            else:
                                timestamp_str = str(timestamp)[:16]
                            
                            st.markdown(f"**{i+1}.** {engine_icon} {type_icon} `{search['query']}` - {timestamp_str}")
                        
                        # 검색 통계
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            google_count = sum(1 for s in search_history if s['search_engine'] == 'google')
                            st.metric("Google 검색", google_count)
                        
                        with col2:
                            naver_count = sum(1 for s in search_history if s['search_engine'] == 'naver')
                            st.metric("네이버 검색", naver_count)
                        
                        with col3:
                            image_count = sum(1 for s in search_history if s['search_type'] == 'image')
                            st.metric("이미지 검색", image_count)
                    
                    else:
                        st.info("📭 이 제품에 대한 검색 이력이 없습니다.")
                        
                except Exception as e:
                    st.error(f"검색 이력 조회 중 오류: {str(e)}")
            else:
                st.warning("데이터베이스 연결을 사용할 수 없습니다.")
        
        # 글로벌 검색 통계 (관리자용)
        with st.expander("📈 전체 검색 통계 (관리자용)", expanded=False):
            if get_database_manager:
                try:
                    db_manager = get_database_manager()
                    search_stats = db_manager.get_search_statistics()
                    
                    if search_stats:
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("총 검색 수", search_stats.get('total_searches', 0))
                            st.metric("최근 24시간", search_stats.get('recent_searches_24h', 0))
                        
                        with col2:
                            engine_dist = search_stats.get('engine_distribution', {})
                            st.markdown("**검색 엔진별 사용량**")
                            for engine, count in engine_dist.items():
                                st.markdown(f"- {engine}: {count}회")
                        
                        with col3:
                            type_dist = search_stats.get('type_distribution', {})
                            st.markdown("**검색 타입별 사용량**")
                            for search_type, count in type_dist.items():
                                st.markdown(f"- {search_type}: {count}회")
                        
                        # 인기 검색어
                        popular_queries = db_manager.get_popular_search_queries(5)
                        if popular_queries:
                            st.markdown("**인기 검색어 TOP 5**")
                            for i, query_info in enumerate(popular_queries):
                                st.markdown(f"{i+1}. `{query_info['query']}` ({query_info['search_count']}회)")
                    
                except Exception as e:
                    st.error(f"검색 통계 조회 중 오류: {str(e)}")
        
    except Exception as e:
        st.error(f"외부 검색 컴포넌트 로딩 중 오류가 발생했습니다: {str(e)}")
        
        # 폴백: 기본 검색 링크 제공
        st.markdown("### 🔎 외부 검색 (기본 모드)")
        st.warning("고급 검색 기능을 일시적으로 사용할 수 없습니다.")
        
        candidate_info = candidate_data.get('candidate_info', {})
        product_name = candidate_info.get('product_name_ai', '')
        
        if product_name:
            from urllib.parse import quote_plus
            encoded_query = quote_plus(product_name)
            
            col1, col2 = st.columns(2)
            
            with col1:
                google_url = f"https://www.google.com/search?q={encoded_query}&hl=ko&gl=KR"
                st.markdown(f"[🔍 Google에서 검색]({google_url})")
                
                google_image_url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&hl=ko&gl=KR"
                st.markdown(f"[🖼️ Google 이미지 검색]({google_image_url})")
            
            with col2:
                naver_url = f"https://search.naver.com/search.naver?query={encoded_query}"
                st.markdown(f"[🟢 네이버에서 검색]({naver_url})")
                
                naver_image_url = f"https://search.naver.com/search.naver?where=image&query={encoded_query}"
                st.markdown(f"[🖼️ 네이버 이미지 검색]({naver_image_url})")
        else:
            st.info("제품 정보가 없어 검색 링크를 생성할 수 없습니다.")


def render_ai_analysis_section(candidate_info):
    """AI 분석 결과 섹션 렌더링"""
    st.markdown("### 🤖 AI 분석 결과")
    
    score_details = candidate_info.get('score_details', {})
    
    # 점수 표시
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_score = score_details.get('total', 0)
        st.metric("총점", f"{total_score}점", help="전체 매력도 점수")
    
    with col2:
        sentiment_score = score_details.get('sentiment_score', 0)
        st.metric("감성 강도", f"{sentiment_score:.2f}", help="감정적 호소력")
    
    with col3:
        endorsement_score = score_details.get('endorsement_score', 0) 
        st.metric("실사용 인증", f"{endorsement_score:.2f}", help="실제 사용 증거")
    
    with col4:
        influencer_score = score_details.get('influencer_score', 0)
        st.metric("인플루언서 신뢰도", f"{influencer_score:.2f}", help="신뢰도 점수")
    
    # 진행률 바
    st.markdown("**점수 상세 분석**")
    col1, col2 = st.columns(2)
    
    with col1:
        st.progress(sentiment_score, text=f"감성 강도: {sentiment_score:.2f}")
        st.progress(endorsement_score, text=f"실사용 인증: {endorsement_score:.2f}")
    
    with col2:
        st.progress(influencer_score, text=f"인플루언서 신뢰도: {influencer_score:.2f}")
        st.progress(total_score/100, text=f"총점: {total_score:.0f}/100")
    
    # AI 생성 콘텐츠
    hook_sentence = candidate_info.get('hook_sentence', '')
    summary = candidate_info.get('summary_for_caption', '')
    
    if hook_sentence:
        st.markdown("**🎯 후크 문장**")
        st.info(hook_sentence)
    
    if summary:
        st.markdown("**📝 캡션용 요약**")
        st.text_area("", value=summary, height=100, disabled=True)
    
    # 추천 제목들
    recommended_titles = candidate_info.get('recommended_titles', [])
    if recommended_titles:
        st.markdown("**💡 추천 제목들**")
        for i, title in enumerate(recommended_titles, 1):
            st.markdown(f"{i}. {title}")
    
    # 추천 해시태그
    recommended_hashtags = candidate_info.get('recommended_hashtags', [])
    if recommended_hashtags:
        st.markdown("**🏷️ 추천 해시태그**")
        hashtag_text = " ".join(recommended_hashtags)
        st.text_area("", value=hashtag_text, height=60, disabled=True, 
                    help="복사하여 사용하세요")


def render_detail_view_enhanced(candidate_data):
    """
    T05_S01_M02: Enhanced Detail View with PRD JSON Schema Support
    PRD Section 3.3 JSON 스키마 구조를 완전히 지원하는 상세 뷰
    """
    
    # 데이터 없음 상태 처리
    if not candidate_data:
        st.error("⚠️ 선택된 후보 데이터가 없습니다.")
        st.info("목록 페이지로 돌아가서 후보를 선택해주세요.")
        if st.button("🔙 목록으로 돌아가기", type="primary"):
            st.session_state.current_page = 'monetizable_candidates'
            st.rerun()
        return
    
    # JSON 스키마 구조 파싱
    source_info = candidate_data.get('source_info', {})
    candidate_info = candidate_data.get('candidate_info', {})
    monetization_info = candidate_data.get('monetization_info', {})
    status_info = candidate_data.get('status_info', {})
    
    # 레거시 데이터 지원 (기존 구조와 호환)
    if not source_info and '채널명' in candidate_data:
        source_info = {
            'celebrity_name': candidate_data.get('채널명', ''),
            'channel_name': candidate_data.get('채널명', ''),
            'video_title': candidate_data.get('영상_제목', ''),
            'video_url': candidate_data.get('youtube_url', ''),
            'upload_date': candidate_data.get('업로드_날짜', '')
        }
        candidate_info = {
            'product_name_ai': candidate_data.get('제품명', ''),
            'category_path': [candidate_data.get('카테고리', '')],
            'clip_start_time': 0,
            'clip_end_time': 0,
            'score_details': {
                'total': candidate_data.get('매력도_점수', 0),
                'sentiment_score': candidate_data.get('감성_강도', 0),
                'endorsement_score': candidate_data.get('실사용_인증', 0),
                'influencer_score': candidate_data.get('인플루언서_신뢰도', 0)
            },
            'hook_sentence': f"이것만은 꼭 써보세요! {candidate_data.get('제품명', '')}",
            'summary_for_caption': f"{candidate_data.get('채널명', '')}님이 추천하는 {candidate_data.get('제품명', '')}! 실제 사용 후기를 확인해보세요.",
            'recommended_titles': [
                f"{candidate_data.get('채널명', '')}이 추천하는 {candidate_data.get('제품명', '')}",
                f"이것 하나로 달라진 {candidate_data.get('채널명', '')}의 루틴",
                f"솔직 후기! {candidate_data.get('제품명', '')} 써본 결과"
            ],
            'recommended_hashtags': [
                f"#{candidate_data.get('채널명', '').replace(' ', '')}",
                f"#{candidate_data.get('카테고리', '')}",
                "#추천템", "#솔직후기"
            ]
        }
        monetization_info = {
            'is_coupang_product': True,
            'coupang_url_ai': candidate_data.get('쿠팡_링크', '')
        }
        status_info = {
            'current_status': candidate_data.get('상태', 'needs_review'),
            'is_ppl': False,
            'ppl_confidence': 0.1
        }
    
    # 상단 네비게이션
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if st.button("🔙 뒤로 가기", use_container_width=True):
            st.session_state.current_page = 'monetizable_candidates'
            st.rerun()
    
    with col3:
        # 새로고침 버튼
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()
    
    # 제품 정보 헤더
    product_name = candidate_info.get('product_name_ai', 'Unknown Product')
    channel_name = source_info.get('channel_name', 'Unknown Channel')
    total_score = candidate_info.get('score_details', {}).get('total', 0)
    
    st.markdown(f"# 🎯 {product_name}")
    
    # 헤더 메타 정보
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📺 채널", channel_name)
    with col2:
        categories = candidate_info.get('category_path', ['Unknown'])
        st.metric("🏷️ 카테고리", ' > '.join(categories))
    with col3:
        st.metric("⭐ 매력도 점수", f"{total_score:.1f}점")
    with col4:
        current_status = status_info.get('current_status', 'needs_review')
        status_colors = {
            'needs_review': '🟡',
            'approved': '🟢', 
            'rejected': '🔴',
            'published': '🎉'
        }
        st.metric("📊 상태", f"{status_colors.get(current_status, '⚪')} {current_status}")
    
    # 메인 콘텐츠 탭 (T03_S02_M02: 외부 검색 탭 추가)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📺 영상 정보", "🛍️ 제품 정보", "🤖 AI 분석", "🖼️ 제품 이미지", "💰 수익화 정보", "🔎 외부 검색"])
    
    with tab1:
        render_source_info_section(source_info)
        
        # YouTube 플레이어 (있는 경우)
        video_url = source_info.get('video_url', '')
        if video_url:
            st.markdown("---")
            st.markdown("### 🎬 영상 미리보기")
            
            # 현재 선택된 타임스탬프 우선 사용, 없으면 기본 시작 시간
            if 'current_timestamp' in st.session_state:
                current_timestamp = st.session_state['current_timestamp']
            else:
                start_time = candidate_info.get('clip_start_time', 0)
                start_min, start_sec = divmod(start_time, 60)
                current_timestamp = f"{start_min:02d}:{start_sec:02d}"
            
            # YouTube 플레이어 렌더링
            player_loaded = render_youtube_player(video_url, current_timestamp)
            
            if player_loaded:
                st.markdown("---")
                # 타임라인 네비게이터 추가
                render_timeline_navigator(candidate_data, video_url)
            else:
                st.warning("🎬 플레이어 로딩에 실패했지만 타임라인 네비게이터는 사용할 수 있습니다.")
                render_timeline_navigator(candidate_data, video_url)
    
    with tab2:
        render_product_info_section(candidate_info)
    
    with tab3:
        render_ai_analysis_section(candidate_info)
    
    with tab4:
        render_product_image_gallery_section(candidate_data)
    
    with tab5:
        st.markdown("### 💰 수익화 정보")
        
        is_coupang_product = monetization_info.get('is_coupang_product', False)
        coupang_url = monetization_info.get('coupang_url_ai', '')
        
        col1, col2 = st.columns(2)
        
        with col1:
            if is_coupang_product:
                st.success("✅ 쿠팡 파트너스 제품 발견")
            else:
                st.warning("⚠️ 쿠팡 파트너스 제품 미발견")
        
        with col2:
            if coupang_url:
                st.markdown(f"**🛒 쿠팡 링크**: [바로가기]({coupang_url})")
            else:
                st.info("쿠팡 링크가 없습니다.")
        
        # PPL 정보
        is_ppl = status_info.get('is_ppl', False)
        ppl_confidence = status_info.get('ppl_confidence', 0)
        
        st.markdown("**PPL 분석 결과**")
        if is_ppl:
            st.error(f"🚨 PPL 가능성 높음 (확률: {ppl_confidence:.1%})")
        else:
            st.success(f"✅ 자연스러운 추천 (PPL 확률: {ppl_confidence:.1%})")
    
    with tab6:
        # T03_S02_M02: 외부 검색 연동 기능
        render_external_search_section(candidate_data)
    
    # T07_S01_M02: AI 생성 콘텐츠 표시 섹션
    st.markdown("---")
    render_ai_generated_content(candidate_data)
    
    # T08_S01_M02: 워크플로우 상태 관리 시스템 통합
    st.markdown("---")
    st.markdown("## 🎛️ 워크플로우 상태 관리")
    
    # 후보 ID 추출
    candidate_id = candidate_data.get('id') or f"candidate_{hash(str(candidate_data))}"
    
    # 워크플로우 상태 관리 컴포넌트 렌더링
    if render_workflow_state_component:
        try:
            status_changed = render_workflow_state_component(
                candidate_id=candidate_id,
                candidate_data=candidate_data,
                show_history=True,
                show_rules=True
            )
            
            # 상태가 변경되었다면 데이터베이스에 저장
            if status_changed and get_database_manager:
                db_manager = get_database_manager()
                success = db_manager.save_candidate(candidate_data)
                if success:
                    st.success("✅ 변경사항이 데이터베이스에 저장되었습니다.")
                else:
                    st.warning("⚠️ 데이터베이스 저장 중 오류가 발생했습니다.")
                    
        except Exception as e:
            st.error(f"워크플로우 상태 관리 중 오류가 발생했습니다: {str(e)}")
            
            # 폴백: 기본 액션 버튼
            st.markdown("**기본 액션 버튼 (폴백 모드)**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("✅ 승인", use_container_width=True, type="primary"):
                    st.success("후보가 승인되었습니다!")
                    st.balloons()
            
            with col2:
                if st.button("❌ 반려", use_container_width=True):
                    st.error("후보가 반려되었습니다.")
            
            with col3:
                if st.button("✏️ 수정", use_container_width=True):
                    st.info("수정 모드로 전환합니다.")
            
            with col4:
                if st.button("🚀 업로드 완료", use_container_width=True):
                    st.success("업로드 완료로 표시되었습니다!")
    else:
        # 모듈 import 실패 시 기본 버튼
        st.warning("⚠️ 워크플로우 상태 관리 모듈을 로드할 수 없습니다. 기본 버튼을 사용합니다.")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ 승인", use_container_width=True, type="primary"):
                st.success("후보가 승인되었습니다!")
                st.balloons()
        
        with col2:
            if st.button("❌ 반려", use_container_width=True):
                st.error("후보가 반려되었습니다.")
        
        with col3:
            if st.button("✏️ 수정", use_container_width=True):
                st.info("수정 모드로 전환합니다.")
        
        with col4:
            if st.button("🚀 업로드 완료", use_container_width=True):
                st.success("업로드 완료로 표시되었습니다!")


def render_detail_view(product_data):
    """기존 호환성을 위한 래퍼 함수"""
    render_detail_view_enhanced(product_data)

# numpy import 추가
import numpy as np

def test_detail_view():
    """T05_S01_M02: Enhanced Detail View Test"""
    st.title("🧪 Enhanced Detail View Component Test")
    
    # PRD JSON 스키마 구조 테스트 데이터
    prd_schema_data = {
        "source_info": {
            "celebrity_name": "홍지윤",
            "channel_name": "홍지윤 Yoon",
            "video_title": "[일상VLOG] 스킨케어 추천 | 솔직 후기",
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "upload_date": "2025-06-22"
        },
        "candidate_info": {
            "product_name_ai": "히알루론산 세럼 - 프리미엄",
            "product_name_manual": None,
            "clip_start_time": 263,  # 4:23
            "clip_end_time": 375,    # 6:15
            "category_path": ["스킨케어", "세럼", "히알루론산"],
            "features": ["높은 수분 보습", "빠른 흡수", "끈적임 없음", "민감성 피부 적합"],
            "score_details": {
                "total": 85.3,
                "sentiment_score": 0.87,
                "endorsement_score": 0.92,
                "influencer_score": 0.89
            },
            "hook_sentence": "이것만은 꼭 써보세요! 세럼 하나로 달라지는 피부",
            "summary_for_caption": "홍지윤님이 추천하는 히알루론산 세럼! 실제 사용 후기를 확인해보세요. 높은 보습력과 빠른 흡수력이 특징입니다.",
            "target_audience": ["20대 후반 여성", "30대 직장인", "건성 피부"],
            "price_point": "중간",
            "endorsement_type": "습관적 사용",
            "recommended_titles": [
                "홍지윤이 매일 쓰는 세럼의 정체는?",
                "이것 하나로 달라진 홍지윤의 스킨케어 루틴",
                "솔직 후기! 히알루론산 세럼 써본 결과"
            ],
            "recommended_hashtags": [
                "#홍지윤", "#스킨케어", "#히알루론산세럼", "#보습세럼", "#추천템", "#솔직후기"
            ]
        },
        "monetization_info": {
            "is_coupang_product": True,
            "coupang_url_ai": "https://link.coupang.com/a/sample",
            "coupang_url_manual": None
        },
        "status_info": {
            "current_status": "needs_review",
            "is_ppl": False,
            "ppl_confidence": 0.1
        }
    }
    
    # 레거시 데이터 구조 테스트
    legacy_data = {
        "id": "PROD_002", 
        "제품명": "비타민C 크림 - 럭셔리",
        "채널명": "아이유IU",
        "영상_제목": "[GRWM] 아이유의 아침 루틴",
        "카테고리": "스킨케어",
        "매력도_점수": 78.5,
        "감성_강도": 0.82,
        "실사용_인증": 0.88,
        "인플루언서_신뢰도": 0.94,
        "상태": "승인됨",
        "업로드_날짜": "2025-06-20",
        "조회수": "89,320",
        "영상_길이": "08:45", 
        "타임스탬프": "02:15 - 03:30",
        "예상_가격": "32,000원",
        "youtube_url": "https://www.youtube.com/watch?v=sample2"
    }
    
    # 테스트 데이터 선택
    test_option = st.selectbox(
        "테스트 데이터 선택",
        ["PRD JSON 스키마 구조", "레거시 데이터 구조", "데이터 없음 상태"]
    )
    
    if test_option == "PRD JSON 스키마 구조":
        render_detail_view_enhanced(prd_schema_data)
    elif test_option == "레거시 데이터 구조":
        render_detail_view_enhanced(legacy_data)
    else:
        render_detail_view_enhanced(None)


if __name__ == "__main__":
    test_detail_view()