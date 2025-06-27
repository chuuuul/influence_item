"""
비디오 플레이어 컴포넌트

대시보드에서 분석 결과의 특정 구간을 바로 재생할 수 있는 
Streamlit 컴포넌트를 제공합니다.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import json
import logging

from src.video_player.timestamp_player import (
    TimestampVideoPlayer, PlaybackSegment, VideoPlayerConfig
)


def render_video_player_component(
    video_url: str,
    segments_data: List[Dict[str, Any]],
    title: str = "분석 결과 영상 재생"
) -> None:
    """
    비디오 플레이어 컴포넌트 렌더링
    
    Args:
        video_url: YouTube URL
        segments_data: 분석 결과 구간 데이터
        title: 컴포넌트 제목
    """
    try:
        # 비디오 플레이어 초기화
        player = TimestampVideoPlayer()
        
        st.markdown(f"### 🎬 {title}")
        
        if not video_url:
            st.warning("YouTube URL이 필요합니다.")
            return
        
        if not segments_data:
            st.info("재생할 구간 데이터가 없습니다.")
            return
        
        # CSS 스타일 적용
        st.markdown(player.generate_css_styles(), unsafe_allow_html=True)
        
        # 플레이어 설정
        with st.expander("🔧 플레이어 설정"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                auto_play = st.checkbox("자동 재생", value=True, key="video_autoplay")
                show_controls = st.checkbox("컨트롤 표시", value=True, key="video_controls")
            
            with col2:
                loop_segment = st.checkbox("구간 반복", value=False, key="video_loop")
                quality = st.selectbox(
                    "화질", 
                    ["hd720", "hd1080", "medium", "small"],
                    index=0,
                    key="video_quality"
                )
            
            with col3:
                volume = st.slider("볼륨", 0, 100, 80, key="video_volume")
                speed = st.selectbox(
                    "재생 속도",
                    [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
                    index=3,
                    key="video_speed"
                )
        
        # 플레이어 설정 적용
        player_config = VideoPlayerConfig(
            auto_play=auto_play,
            show_controls=show_controls,
            loop_segment=loop_segment,
            quality=quality,
            volume=volume,
            speed=speed
        )
        
        # 구간 데이터를 PlaybackSegment로 변환
        segments = []
        for i, segment_data in enumerate(segments_data):
            try:
                segment = PlaybackSegment(
                    start_time=float(segment_data.get('start_time', 0)),
                    end_time=float(segment_data.get('end_time', 30)),
                    title=segment_data.get('title', f'구간 {i+1}'),
                    description=segment_data.get('description', '분석된 제품 소개 구간'),
                    confidence_score=float(segment_data.get('confidence_score', 0.5)),
                    product_name=segment_data.get('product_name'),
                    category=segment_data.get('category'),
                    thumbnail_url=segment_data.get('thumbnail_url')
                )
                
                if player.validate_segment(segment):
                    segments.append(segment)
                    
            except Exception as e:
                st.error(f"구간 {i+1} 데이터 처리 오류: {str(e)}")
                continue
        
        if not segments:
            st.error("유효한 재생 구간이 없습니다.")
            return
        
        # 구간 선택 UI
        st.markdown("### 🎯 재생할 구간 선택")
        
        # 구간 목록을 데이터프레임으로 표시
        segment_df = pd.DataFrame([
            {
                '구간': i + 1,
                '제품명': segment.product_name or '미지정',
                '시작 시간': _format_time(segment.start_time),
                '종료 시간': _format_time(segment.end_time),
                '구간 길이': _format_time(segment.end_time - segment.start_time),
                '신뢰도': f"{segment.confidence_score:.1%}",
                '설명': segment.description[:50] + "..." if len(segment.description) > 50 else segment.description
            }
            for i, segment in enumerate(segments)
        ])
        
        # 구간 선택
        selected_rows = st.dataframe(
            segment_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # 선택된 구간이 있으면 비디오 플레이어 표시
        if selected_rows.selection.rows:
            selected_idx = selected_rows.selection.rows[0]
            selected_segment = segments[selected_idx]
            
            st.markdown("---")
            st.markdown(f"### 🎥 재생 중: {selected_segment.title}")
            
            # 구간 정보 표시
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("시작 시간", _format_time(selected_segment.start_time))
            
            with col2:
                st.metric("종료 시간", _format_time(selected_segment.end_time))
            
            with col3:
                st.metric("구간 길이", _format_time(selected_segment.end_time - selected_segment.start_time))
            
            with col4:
                st.metric("신뢰도", f"{selected_segment.confidence_score:.1%}")
            
            # 제품 정보 (있는 경우)
            if selected_segment.product_name:
                st.info(f"**제품명:** {selected_segment.product_name}")
            
            if selected_segment.description:
                st.write(f"**설명:** {selected_segment.description}")
            
            # 비디오 플레이어 생성
            embed_url = player.create_embed_url(
                video_url,
                selected_segment.start_time,
                selected_segment.end_time,
                player_config
            )
            
            # iframe으로 비디오 표시
            st.markdown(f"""
            <div style="display: flex; justify-content: center; margin: 20px 0;">
                <iframe 
                    width="700" 
                    height="394" 
                    src="{embed_url}" 
                    title="YouTube video player" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen>
                </iframe>
            </div>
            """, unsafe_allow_html=True)
            
            # 직접 링크 제공
            direct_url = player.create_timestamped_url(
                video_url, 
                selected_segment.start_time
            )
            
            st.markdown(f"""
            <div style="text-align: center; margin: 10px 0;">
                <a href="{direct_url}" target="_blank" style="
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #ff0000;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                ">🎬 YouTube에서 직접 보기</a>
            </div>
            """, unsafe_allow_html=True)
            
        else:
            st.info("👆 위 표에서 재생할 구간을 선택해주세요.")
        
        # 전체 플레이리스트 생성 옵션
        st.markdown("---")
        if st.button("📋 전체 구간 플레이리스트 생성", type="secondary"):
            playlist = player.create_playlist_from_segments(
                video_url, 
                segments, 
                player_config
            )
            
            if playlist:
                st.success(f"플레이리스트 생성 완료! {len(segments)}개 구간")
                
                # 플레이리스트 정보 표시
                st.json(playlist)
                
                # 다운로드 링크 생성
                playlist_json = json.dumps(playlist, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📥 플레이리스트 다운로드 (JSON)",
                    data=playlist_json,
                    file_name=f"playlist_{player.extract_video_id(video_url)}.json",
                    mime="application/json"
                )
            else:
                st.error("플레이리스트 생성에 실패했습니다.")
        
        # JavaScript 컨트롤 추가
        st.markdown(player.generate_video_controls_javascript(), unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"비디오 플레이어 컴포넌트 오류: {str(e)}")
        logging.error(f"Video player component error: {str(e)}")


def render_segment_comparison_player(
    video_url: str,
    segments_list: List[List[Dict[str, Any]]],
    titles: List[str]
) -> None:
    """
    여러 분석 결과의 구간을 비교하여 재생하는 컴포넌트
    
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
    비디오 분석 결과 요약 및 주요 구간 플레이어
    
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
    """테스트용 빈 데이터 반환"""
    return []


# 테스트용 페이지 (개발 시에만 사용)
def render_video_player_test_page():
    """비디오 플레이어 테스트 페이지"""
    st.title("🎬 비디오 플레이어 컴포넌트")
    st.info("실제 분석 결과 데이터가 필요합니다. 메인 대시보드에서 영상을 분석하여 사용하세요.")


if __name__ == "__main__":
    render_video_player_test_page()