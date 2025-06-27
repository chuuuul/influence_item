"""
비디오 플레이어 컴포넌트 - PRD SPEC-DASH-02 구현

대시보드에서 분석 결과의 특정 구간을 바로 재생할 수 있는 
Streamlit 네이티브 st.video 기반 컴포넌트를 제공합니다.

리뷰어 지적사항 해결:
- 복잡한 커스텀 의존성 제거
- Streamlit 네이티브 기능 활용
- 안정성 및 성능 최적화
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

# 중앙화된 경로 관리 시스템 import
try:
    from config.path_config import get_path_manager
    pm = get_path_manager()
except ImportError:
    # fallback
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config.path_config import get_path_manager
    pm = get_path_manager()


class StreamlitVideoPlayer:
    """Streamlit 네이티브 기반 비디오 플레이어"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """YouTube URL에서 비디오 ID 추출"""
        try:
            if 'youtu.be/' in url:
                return url.split('youtu.be/')[1].split('?')[0]
            elif 'youtube.com/watch' in url:
                return parse_qs(urlparse(url).query)['v'][0]
            elif 'youtube.com/embed/' in url:
                return url.split('embed/')[1].split('?')[0]
            return None
        except Exception:
            return None
    
    def create_youtube_url_with_timestamp(self, video_url: str, start_time: float) -> str:
        """타임스탬프가 포함된 YouTube URL 생성"""
        try:
            video_id = self.extract_video_id(video_url)
            if not video_id:
                return video_url
            
            # 초를 시:분:초 형식으로 변환
            start_seconds = int(start_time)
            return f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}s"
        except Exception:
            return video_url
    
    def validate_youtube_url(self, url: str) -> bool:
        """YouTube URL 유효성 검사"""
        return bool(self.extract_video_id(url))


def render_video_player_component(
    video_url: str,
    segments_data: List[Dict[str, Any]],
    title: str = "분석 결과 영상 재생"
) -> None:
    """
    PRD SPEC-DASH-02: 타임스탬프 자동 재생
    
    Streamlit 네이티브 st.video를 활용한 안정적인 비디오 플레이어
    
    Args:
        video_url: YouTube URL
        segments_data: 분석 결과 구간 데이터
        title: 컴포넌트 제목
    """
    try:
        player = StreamlitVideoPlayer()
        
        st.markdown(f"### 🎬 {title}")
        
        if not video_url:
            st.warning("YouTube URL이 필요합니다.")
            return
        
        if not segments_data:
            st.info("재생할 구간 데이터가 없습니다.")
            return
        
        # YouTube URL 유효성 검사
        if not player.validate_youtube_url(video_url):
            st.error("유효하지 않은 YouTube URL입니다.")
            return
        
        # 플레이어 설정
        with st.expander("🔧 플레이어 설정", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                auto_play = st.checkbox("자동 재생", value=False, key="video_autoplay", 
                                       help="브라우저 정책에 따라 자동 재생이 제한될 수 있습니다.")
                loop_video = st.checkbox("반복 재생", value=False, key="video_loop")
            
            with col2:
                muted = st.checkbox("음소거", value=False, key="video_muted",
                                  help="자동 재생을 위해서는 음소거가 필요할 수 있습니다.")
                show_full_video = st.checkbox("전체 영상 보기", value=False, key="show_full_video")
        
        # 구간 데이터 처리 및 검증
        valid_segments = []
        for i, segment_data in enumerate(segments_data):
            try:
                start_time = float(segment_data.get('start_time', 0))
                end_time = float(segment_data.get('end_time', start_time + 30))
                
                # 유효성 검사
                if start_time < 0 or end_time <= start_time:
                    continue
                
                segment = {
                    'index': i + 1,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'title': segment_data.get('title', f'구간 {i+1}'),
                    'description': segment_data.get('description', '분석된 제품 소개 구간'),
                    'confidence_score': float(segment_data.get('confidence_score', 0.5)),
                    'product_name': segment_data.get('product_name', '미지정'),
                    'category': segment_data.get('category', '기타')
                }
                
                valid_segments.append(segment)
                
            except Exception as e:
                st.warning(f"구간 {i+1} 데이터 처리 중 오류: {str(e)}")
                continue
        
        if not valid_segments:
            st.error("유효한 재생 구간이 없습니다.")
            return
        
        # 구간 선택 UI
        st.markdown("### 🎯 재생할 구간 선택")
        
        # 구간 목록을 데이터프레임으로 표시
        segment_df = pd.DataFrame([
            {
                '구간': segment['index'],
                '제품명': segment['product_name'],
                '시작 시간': _format_time(segment['start_time']),
                '종료 시간': _format_time(segment['end_time']),
                '구간 길이': _format_time(segment['duration']),
                '신뢰도': f"{segment['confidence_score']:.1%}",
                '설명': segment['description'][:50] + ("..." if len(segment['description']) > 50 else "")
            }
            for segment in valid_segments
        ])
        
        # 구간 선택
        event = st.dataframe(
            segment_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="segment_selection"
        )
        
        # 선택된 구간 처리
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_segment = valid_segments[selected_idx]
            
            st.markdown("---")
            st.markdown(f"### 🎥 재생 중: {selected_segment['title']}")
            
            # 구간 정보 표시
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("시작 시간", _format_time(selected_segment['start_time']))
            
            with col2:
                st.metric("종료 시간", _format_time(selected_segment['end_time']))
            
            with col3:
                st.metric("구간 길이", _format_time(selected_segment['duration']))
            
            with col4:
                st.metric("신뢰도", f"{selected_segment['confidence_score']:.1%}")
            
            # 제품 정보
            if selected_segment['product_name'] != '미지정':
                st.info(f"**제품명:** {selected_segment['product_name']}")
            
            if selected_segment['description']:
                st.write(f"**설명:** {selected_segment['description']}")
            
            # === 핵심: Streamlit 네이티브 st.video 사용 ===
            if show_full_video:
                # 전체 영상 재생
                st.video(video_url, autoplay=auto_play, loop=loop_video, muted=muted)
            else:
                # 구간별 재생 - start_time 지원
                try:
                    st.video(
                        video_url, 
                        start_time=int(selected_segment['start_time']),
                        autoplay=auto_play,
                        loop=loop_video,
                        muted=muted
                    )
                except Exception as e:
                    st.warning(f"구간 재생 중 오류: {str(e)}")
                    st.video(video_url, autoplay=auto_play, loop=loop_video, muted=muted)
            
            # 직접 링크 제공
            timestamp_url = player.create_youtube_url_with_timestamp(
                video_url, 
                selected_segment['start_time']
            )
            
            st.markdown(f"""
            <div style="text-align: center; margin: 15px 0;">
                <a href="{timestamp_url}" target="_blank" style="
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #ff0000;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 16px;
                    transition: background-color 0.3s;
                " onmouseover="this.style.backgroundColor='#cc0000'" onmouseout="this.style.backgroundColor='#ff0000'">
                    🎬 YouTube에서 {_format_time(selected_segment['start_time'])}부터 직접 보기
                </a>
            </div>
            """, unsafe_allow_html=True)
            
        else:
            st.info("👆 위 표에서 재생할 구간을 선택해주세요.")
        
        # 전체 구간 요약
        st.markdown("---")
        if st.button("📊 전체 구간 요약 보기", type="secondary"):
            st.markdown("#### 📋 분석된 모든 구간 요약")
            
            total_duration = sum(segment['duration'] for segment in valid_segments)
            avg_confidence = sum(segment['confidence_score'] for segment in valid_segments) / len(valid_segments)
            unique_products = len(set(segment['product_name'] for segment in valid_segments if segment['product_name'] != '미지정'))
            
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            
            with summary_col1:
                st.metric("총 구간 수", len(valid_segments))
            
            with summary_col2:
                st.metric("총 분석 시간", _format_time(total_duration))
            
            with summary_col3:
                st.metric("평균 신뢰도", f"{avg_confidence:.1%}")
            
            with summary_col4:
                st.metric("발견된 제품 수", unique_products)
            
            # 상위 구간들 표시 (신뢰도 기준)
            top_segments = sorted(valid_segments, key=lambda x: x['confidence_score'], reverse=True)[:3]
            
            st.markdown("#### 🏆 신뢰도 상위 3개 구간")
            for i, segment in enumerate(top_segments, 1):
                with st.container():
                    st.markdown(f"""
                    **{i}위: {segment['title']}** (신뢰도: {segment['confidence_score']:.1%})
                    - 시간: {_format_time(segment['start_time'])} ~ {_format_time(segment['end_time'])}
                    - 제품: {segment['product_name']}
                    - 설명: {segment['description']}
                    """)
        
    except Exception as e:
        st.error(f"비디오 플레이어 컴포넌트 오류: {str(e)}")
        pm.logger.error(f"Video player component error: {str(e)}", exc_info=True)


def render_segment_comparison_player(
    video_url: str,
    segments_list: List[List[Dict[str, Any]]],
    titles: List[str]
) -> None:
    """
    여러 분석 결과의 구간을 비교하여 재생하는 컴포넌트 (Streamlit 네이티브)
    
    Args:
        video_url: YouTube URL
        segments_list: 각 분석 결과의 구간 데이터 리스트
        titles: 각 분석 결과의 제목
    """
    st.markdown("### 🔄 구간 비교 재생")
    
    if len(segments_list) != len(titles):
        st.error("구간 데이터와 제목의 개수가 일치하지 않습니다.")
        return
    
    # 탭으로 각 분석 결과 구분
    tabs = st.tabs(titles)
    
    for i, (tab, segments_data, title) in enumerate(zip(tabs, segments_list, titles)):
        with tab:
            render_video_player_component(
                video_url, 
                segments_data, 
                title=f"{title} 구간"
            )


def render_video_analysis_summary(
    video_url: str,
    analysis_results: Dict[str, Any]
) -> None:
    """
    비디오 분석 결과 요약 및 주요 구간 플레이어 (Streamlit 네이티브)
    
    Args:
        video_url: YouTube URL
        analysis_results: 전체 분석 결과
    """
    st.markdown("### 📊 분석 결과 요약")
    
    try:
        # 주요 통계
        col1, col2, col3, col4 = st.columns(4)
        
        segments_data = analysis_results.get('segments', [])
        total_segments = len(segments_data)
        
        with col1:
            st.metric("총 구간 수", total_segments)
        
        with col2:
            avg_confidence = sum(s.get('confidence_score', 0) for s in segments_data) / max(total_segments, 1)
            st.metric("평균 신뢰도", f"{avg_confidence:.1%}")
        
        with col3:
            total_duration = sum(
                s.get('end_time', 0) - s.get('start_time', 0) 
                for s in segments_data
            )
            st.metric("총 분석 구간", _format_time(total_duration))
        
        with col4:
            unique_products = len(set(
                s.get('product_name', '미지정') 
                for s in segments_data 
                if s.get('product_name')
            ))
            st.metric("발견된 제품 수", unique_products)
        
        # 신뢰도 높은 상위 구간만 표시
        if segments_data:
            high_confidence_segments = sorted(
                segments_data,
                key=lambda x: x.get('confidence_score', 0),
                reverse=True
            )[:5]  # 상위 5개만
            
            st.markdown("#### 🏆 신뢰도 높은 주요 구간")
            render_video_player_component(
                video_url,
                high_confidence_segments,
                title="주요 제품 소개 구간"
            )
    
    except Exception as e:
        st.error(f"분석 결과 요약 표시 오류: {str(e)}")


def _format_time(seconds: float) -> str:
    """시간을 MM:SS 또는 HH:MM:SS 형식으로 포맷팅"""
    if seconds < 0:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def create_sample_segments_data() -> List[Dict[str, Any]]:
    """테스트용 샘플 데이터 생성"""
    return [
        {
            "start_time": 120.5,
            "end_time": 145.8,
            "title": "테스트 제품 소개",
            "description": "샘플 제품에 대한 상세한 설명입니다.",
            "confidence_score": 0.85,
            "product_name": "샘플 제품",
            "category": "뷰티"
        },
        {
            "start_time": 200.2,
            "end_time": 230.7,
            "title": "두 번째 제품 리뷰",
            "description": "또 다른 제품에 대한 사용 후기입니다.",
            "confidence_score": 0.72,
            "product_name": "테스트 아이템",
            "category": "패션"
        }
    ]


def render_video_player_test_page():
    """
    비디오 플레이어 테스트 페이지 - PRD SPEC-DASH-02 검증
    """
    st.title("🎬 비디오 플레이어 컴포넌트 테스트")
    st.markdown("**PRD SPEC-DASH-02: 타임스탬프 자동 재생** 기능 테스트")
    
    st.markdown("---")
    
    # 테스트 설정
    with st.expander("🧪 테스트 설정", expanded=True):
        st.markdown("#### YouTube URL 입력")
        test_video_url = st.text_input(
            "테스트할 YouTube URL",
            value="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            help="유효한 YouTube URL을 입력하세요"
        )
        
        st.markdown("#### 테스트 모드 선택")
        test_mode = st.radio(
            "테스트 모드",
            ["샘플 데이터 사용", "커스텀 데이터 입력"],
            help="샘플 데이터로 빠른 테스트 또는 직접 데이터 입력"
        )
    
    if test_mode == "샘플 데이터 사용":
        # 샘플 데이터 사용
        sample_data = create_sample_segments_data()
        
        st.markdown("#### 📋 사용중인 샘플 데이터")
        st.json(sample_data)
        
        if st.button("🎬 샘플 데이터로 테스트 시작", type="primary"):
            st.markdown("---")
            render_video_player_component(
                test_video_url,
                sample_data,
                "테스트 비디오 플레이어"
            )
    
    else:
        # 커스텀 데이터 입력
        st.markdown("#### ✏️ 커스텀 구간 데이터 입력")
        
        with st.form("custom_segment_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                start_time = st.number_input("시작 시간 (초)", min_value=0.0, value=60.0, step=1.0)
                product_name = st.text_input("제품명", value="테스트 제품")
                confidence = st.slider("신뢰도", 0.0, 1.0, 0.8, 0.01)
            
            with col2:
                end_time = st.number_input("종료 시간 (초)", min_value=0.0, value=90.0, step=1.0)
                category = st.selectbox("카테고리", ["뷰티", "패션", "라이프스타일", "기타"])
                description = st.text_area("설명", value="커스텀 제품 설명")
            
            submitted = st.form_submit_button("🎬 커스텀 데이터로 테스트", type="primary")
            
            if submitted:
                if end_time <= start_time:
                    st.error("종료 시간은 시작 시간보다 커야 합니다.")
                else:
                    custom_data = [{
                        "start_time": start_time,
                        "end_time": end_time,
                        "title": f"커스텀 구간 ({_format_time(start_time)} ~ {_format_time(end_time)})",
                        "description": description,
                        "confidence_score": confidence,
                        "product_name": product_name,
                        "category": category
                    }]
                    
                    st.markdown("---")
                    render_video_player_component(
                        test_video_url,
                        custom_data,
                        "커스텀 테스트 비디오 플레이어"
                    )
    
    # 기능 설명
    st.markdown("---")
    st.markdown("### 📖 기능 설명")
    st.markdown("""
    **PRD SPEC-DASH-02 구현 내용:**
    
    ✅ **타임스탬프 자동 재생**: 선택한 구간에서 영상이 바로 재생됩니다.
    
    ✅ **Streamlit 네이티브**: `st.video`의 `start_time` 파라미터를 활용하여 안정성을 보장합니다.
    
    ✅ **YouTube 직접 링크**: 타임스탬프가 포함된 YouTube 링크를 제공합니다.
    
    ✅ **구간 정보 표시**: 선택한 구간의 상세 정보를 시각적으로 표시합니다.
    
    ✅ **오류 처리**: 잘못된 데이터나 URL에 대한 적절한 오류 처리를 수행합니다.
    """)
    
    st.markdown("### 🔧 기술적 개선사항")
    st.markdown("""
    - **의존성 제거**: 복잡한 커스텀 컴포넌트 대신 Streamlit 네이티브 기능 사용
    - **성능 최적화**: 불필요한 JavaScript 및 iframe 사용 최소화
    - **안정성 향상**: Streamlit의 검증된 비디오 플레이어 활용
    - **중앙화된 경로 관리**: 새로운 경로 관리 시스템 적용
    """)


if __name__ == "__main__":
    render_video_player_test_page()