"""
타임스탬프 자동 재생 모듈

대시보드에서 분석 결과의 특정 시간대를 바로 재생할 수 있는 기능을 제공합니다.
YouTube 영상의 특정 구간으로 자동 이동하고 재생하는 기능을 구현합니다.
"""

import logging
import re
import urllib.parse
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from config.config import Config


@dataclass
class PlaybackSegment:
    """재생 구간 정보"""
    start_time: float
    end_time: float
    title: str
    description: str
    confidence_score: float
    product_name: Optional[str] = None
    category: Optional[str] = None
    thumbnail_url: Optional[str] = None


@dataclass
class VideoPlayerConfig:
    """비디오 플레이어 설정"""
    auto_play: bool = True
    show_controls: bool = True
    loop_segment: bool = False
    quality: str = "hd720"  # hd720, hd1080, medium, small
    volume: int = 80  # 0-100
    speed: float = 1.0  # 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0
    language: str = "ko"
    captions: bool = True


class TimestampVideoPlayer:
    """타임스탬프 기반 비디오 플레이어"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        타임스탬프 비디오 플레이어 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # 기본 플레이어 설정
        self.player_config = VideoPlayerConfig()
        
        # YouTube 정규식 패턴
        self.youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]+)'
        ]
        
        self.logger.info("타임스탬프 비디오 플레이어 초기화 완료")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        
        try:
            if hasattr(self.config, 'LOG_LEVEL') and isinstance(self.config.LOG_LEVEL, str):
                level_str = self.config.LOG_LEVEL.upper()
                logger.setLevel(getattr(logging, level_str, logging.INFO))
            else:
                logger.setLevel(logging.INFO)
        except (AttributeError, TypeError):
            logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def extract_video_id(self, video_url: str) -> Optional[str]:
        """YouTube URL에서 비디오 ID 추출"""
        if not video_url:
            return None
        
        for pattern in self.youtube_patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        
        self.logger.warning(f"유효하지 않은 YouTube URL: {video_url}")
        return None
    
    def create_timestamped_url(
        self, 
        video_url: str, 
        start_time: float, 
        end_time: Optional[float] = None,
        auto_play: bool = True
    ) -> str:
        """
        타임스탬프가 포함된 YouTube URL 생성
        
        Args:
            video_url: 원본 YouTube URL
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초, 선택적)
            auto_play: 자동 재생 여부
            
        Returns:
            타임스탬프가 포함된 YouTube URL
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return video_url
        
        try:
            # 기본 URL 구성
            base_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # 파라미터 구성
            params = {}
            
            # 시작 시간 설정 (초 단위)
            if start_time > 0:
                params['t'] = f"{int(start_time)}s"
            
            # 종료 시간은 YouTube 기본 기능으로는 지원되지 않음
            # 대신 커스텀 플레이어나 JavaScript로 구현 필요
            
            # 자동 재생 설정 (embed 모드에서만 작동)
            if auto_play:
                params['autoplay'] = '1'
            
            # URL 구성
            if params:
                query_string = urllib.parse.urlencode(params)
                timestamped_url = f"{base_url}&{query_string}"
            else:
                timestamped_url = base_url
            
            self.logger.debug(f"타임스탬프 URL 생성: {timestamped_url}")
            return timestamped_url
            
        except Exception as e:
            self.logger.error(f"타임스탬프 URL 생성 실패: {str(e)}")
            return video_url
    
    def create_embed_url(
        self, 
        video_url: str, 
        start_time: float, 
        end_time: Optional[float] = None,
        player_config: Optional[VideoPlayerConfig] = None
    ) -> str:
        """
        임베드용 YouTube URL 생성 (더 많은 제어 옵션)
        
        Args:
            video_url: 원본 YouTube URL
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초, 선택적)
            player_config: 플레이어 설정
            
        Returns:
            임베드용 YouTube URL
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return video_url
        
        config = player_config or self.player_config
        
        try:
            # 임베드 기본 URL
            base_url = f"https://www.youtube.com/embed/{video_id}"
            
            # 파라미터 구성
            params = {}
            
            # 시작 시간
            if start_time > 0:
                params['start'] = str(int(start_time))
            
            # 종료 시간
            if end_time and end_time > start_time:
                params['end'] = str(int(end_time))
            
            # 자동 재생
            if config.auto_play:
                params['autoplay'] = '1'
            
            # 컨트롤 표시
            if not config.show_controls:
                params['controls'] = '0'
            
            # 루프 재생
            if config.loop_segment:
                params['loop'] = '1'
                params['playlist'] = video_id  # 루프에 필요
            
            # 자막
            if config.captions:
                params['cc_load_policy'] = '1'
                if config.language != 'en':
                    params['cc_lang_pref'] = config.language
            
            # 품질 설정 (사용자가 변경 가능하므로 힌트만 제공)
            if hasattr(config, 'quality') and config.quality:
                params['vq'] = config.quality
            
            # 기타 설정
            params['rel'] = '0'  # 관련 동영상 표시 안함
            params['modestbranding'] = '1'  # YouTube 브랜딩 최소화
            params['iv_load_policy'] = '3'  # 주석 표시 안함
            
            # URL 구성
            if params:
                query_string = urllib.parse.urlencode(params)
                embed_url = f"{base_url}?{query_string}"
            else:
                embed_url = base_url
            
            self.logger.debug(f"임베드 URL 생성: {embed_url}")
            return embed_url
            
        except Exception as e:
            self.logger.error(f"임베드 URL 생성 실패: {str(e)}")
            return f"https://www.youtube.com/embed/{video_id}"
    
    def create_iframe_html(
        self, 
        video_url: str, 
        segment: PlaybackSegment,
        width: int = 560,
        height: int = 315,
        player_config: Optional[VideoPlayerConfig] = None
    ) -> str:
        """
        재생용 iframe HTML 코드 생성
        
        Args:
            video_url: YouTube URL
            segment: 재생 구간 정보
            width: iframe 너비
            height: iframe 높이
            player_config: 플레이어 설정
            
        Returns:
            iframe HTML 코드
        """
        embed_url = self.create_embed_url(
            video_url, 
            segment.start_time, 
            segment.end_time,
            player_config
        )
        
        # 구간 정보를 HTML에 포함
        segment_info = {
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'title': segment.title,
            'description': segment.description,
            'confidence_score': segment.confidence_score,
            'product_name': segment.product_name,
            'category': segment.category
        }
        
        iframe_html = f'''
        <div class="video-player-container" data-segment='{json.dumps(segment_info)}'>
            <div class="video-info">
                <h4>{segment.title}</h4>
                <p>{segment.description}</p>
                <div class="segment-details">
                    <span class="time-range">{self._format_time(segment.start_time)} - {self._format_time(segment.end_time)}</span>
                    <span class="confidence">신뢰도: {segment.confidence_score:.1%}</span>
                    {f'<span class="product">제품: {segment.product_name}</span>' if segment.product_name else ''}
                </div>
            </div>
            <iframe 
                width="{width}" 
                height="{height}" 
                src="{embed_url}" 
                title="YouTube video player" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen>
            </iframe>
        </div>
        '''
        
        return iframe_html
    
    def create_playlist_from_segments(
        self, 
        video_url: str, 
        segments: List[PlaybackSegment],
        player_config: Optional[VideoPlayerConfig] = None
    ) -> Dict[str, Any]:
        """
        여러 구간으로 플레이리스트 생성
        
        Args:
            video_url: YouTube URL
            segments: 재생 구간 리스트
            player_config: 플레이어 설정
            
        Returns:
            플레이리스트 정보
        """
        video_id = self.extract_video_id(video_url)
        if not video_id or not segments:
            return {}
        
        try:
            playlist_items = []
            
            for i, segment in enumerate(segments):
                embed_url = self.create_embed_url(
                    video_url, 
                    segment.start_time, 
                    segment.end_time,
                    player_config
                )
                
                item = {
                    'id': f"segment_{i}",
                    'title': segment.title,
                    'description': segment.description,
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'duration': segment.end_time - segment.start_time,
                    'confidence_score': segment.confidence_score,
                    'product_name': segment.product_name,
                    'category': segment.category,
                    'embed_url': embed_url,
                    'thumbnail_url': segment.thumbnail_url or f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                }
                playlist_items.append(item)
            
            # 신뢰도 순으로 정렬
            playlist_items.sort(key=lambda x: x['confidence_score'], reverse=True)
            
            playlist = {
                'video_id': video_id,
                'video_url': video_url,
                'total_segments': len(segments),
                'total_duration': sum(segment.end_time - segment.start_time for segment in segments),
                'items': playlist_items,
                'created_at': datetime.now().isoformat(),
                'player_config': {
                    'auto_play': player_config.auto_play if player_config else self.player_config.auto_play,
                    'show_controls': player_config.show_controls if player_config else self.player_config.show_controls,
                    'loop_segment': player_config.loop_segment if player_config else self.player_config.loop_segment
                }
            }
            
            self.logger.info(f"플레이리스트 생성 완료: {len(segments)}개 구간")
            return playlist
            
        except Exception as e:
            self.logger.error(f"플레이리스트 생성 실패: {str(e)}")
            return {}
    
    def create_streamlit_video_component(
        self, 
        video_url: str, 
        segment: PlaybackSegment,
        player_config: Optional[VideoPlayerConfig] = None
    ) -> Dict[str, Any]:
        """
        Streamlit용 비디오 컴포넌트 데이터 생성
        
        Args:
            video_url: YouTube URL
            segment: 재생 구간
            player_config: 플레이어 설정
            
        Returns:
            Streamlit 컴포넌트용 데이터
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return {}
        
        embed_url = self.create_embed_url(
            video_url, 
            segment.start_time, 
            segment.end_time,
            player_config
        )
        
        component_data = {
            'video_id': video_id,
            'embed_url': embed_url,
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'title': segment.title,
            'description': segment.description,
            'confidence_score': segment.confidence_score,
            'product_name': segment.product_name,
            'category': segment.category,
            'formatted_time_range': f"{self._format_time(segment.start_time)} - {self._format_time(segment.end_time)}",
            'duration': segment.end_time - segment.start_time,
            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            'direct_link': self.create_timestamped_url(video_url, segment.start_time)
        }
        
        return component_data
    
    def _format_time(self, seconds: float) -> str:
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
    
    def generate_video_controls_javascript(self) -> str:
        """비디오 컨트롤용 JavaScript 코드 생성"""
        js_code = '''
        <script>
        class TimestampVideoPlayer {
            constructor() {
                this.players = new Map();
                this.currentSegment = null;
            }
            
            // YouTube API 로드
            loadYouTubeAPI() {
                if (window.YT) return Promise.resolve();
                
                return new Promise((resolve) => {
                    const tag = document.createElement('script');
                    tag.src = 'https://www.youtube.com/iframe_api';
                    const firstScriptTag = document.getElementsByTagName('script')[0];
                    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
                    
                    window.onYouTubeIframeAPIReady = () => resolve();
                });
            }
            
            // 플레이어 초기화
            initPlayer(containerId, videoId, startTime, endTime) {
                return this.loadYouTubeAPI().then(() => {
                    const player = new YT.Player(containerId, {
                        height: '315',
                        width: '560',
                        videoId: videoId,
                        playerVars: {
                            'start': Math.floor(startTime),
                            'end': Math.floor(endTime),
                            'autoplay': 1,
                            'controls': 1,
                            'rel': 0,
                            'modestbranding': 1
                        },
                        events: {
                            'onReady': (event) => this.onPlayerReady(event, startTime, endTime),
                            'onStateChange': (event) => this.onPlayerStateChange(event, startTime, endTime)
                        }
                    });
                    
                    this.players.set(containerId, {
                        player: player,
                        startTime: startTime,
                        endTime: endTime
                    });
                    
                    return player;
                });
            }
            
            // 플레이어 준비 완료
            onPlayerReady(event, startTime, endTime) {
                event.target.seekTo(startTime, true);
                event.target.playVideo();
            }
            
            // 플레이어 상태 변경
            onPlayerStateChange(event, startTime, endTime) {
                if (event.data === YT.PlayerState.PLAYING) {
                    // 종료 시간 체크
                    this.checkEndTime(event.target, endTime);
                }
            }
            
            // 종료 시간 체크
            checkEndTime(player, endTime) {
                const checkInterval = setInterval(() => {
                    const currentTime = player.getCurrentTime();
                    if (currentTime >= endTime) {
                        player.pauseVideo();
                        clearInterval(checkInterval);
                    }
                }, 500);
            }
            
            // 특정 구간으로 이동
            seekToSegment(containerId, startTime, endTime) {
                const playerData = this.players.get(containerId);
                if (playerData) {
                    playerData.player.seekTo(startTime, true);
                    playerData.player.playVideo();
                    this.checkEndTime(playerData.player, endTime);
                }
            }
            
            // 구간 루프 재생
            loopSegment(containerId, startTime, endTime) {
                const playerData = this.players.get(containerId);
                if (playerData) {
                    const loopPlay = () => {
                        playerData.player.seekTo(startTime, true);
                        playerData.player.playVideo();
                        setTimeout(() => {
                            if (playerData.player.getPlayerState() === YT.PlayerState.PLAYING) {
                                loopPlay();
                            }
                        }, (endTime - startTime) * 1000);
                    };
                    loopPlay();
                }
            }
        }
        
        // 전역 플레이어 인스턴스
        window.timestampPlayer = new TimestampVideoPlayer();
        
        // 유틸리티 함수들
        function playSegment(videoId, startTime, endTime, containerId) {
            window.timestampPlayer.initPlayer(containerId, videoId, startTime, endTime);
        }
        
        function seekToTime(containerId, startTime, endTime) {
            window.timestampPlayer.seekToSegment(containerId, startTime, endTime);
        }
        
        function loopSegment(containerId, startTime, endTime) {
            window.timestampPlayer.loopSegment(containerId, startTime, endTime);
        }
        
        // 시간 포맷팅
        function formatTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            
            if (hours > 0) {
                return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            } else {
                return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            }
        }
        </script>
        '''
        
        return js_code
    
    def generate_css_styles(self) -> str:
        """비디오 플레이어용 CSS 스타일 생성"""
        css_styles = '''
        <style>
        .video-player-container {
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #f9f9f9;
        }
        
        .video-info {
            margin-bottom: 15px;
        }
        
        .video-info h4 {
            margin: 0 0 8px 0;
            color: #333;
            font-size: 16px;
        }
        
        .video-info p {
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
        }
        
        .segment-details {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            font-size: 12px;
        }
        
        .segment-details span {
            padding: 4px 8px;
            border-radius: 4px;
            background-color: #fff;
            border: 1px solid #ccc;
        }
        
        .time-range {
            background-color: #e3f2fd !important;
            color: #1976d2;
        }
        
        .confidence {
            background-color: #f3e5f5 !important;
            color: #7b1fa2;
        }
        
        .product {
            background-color: #e8f5e8 !important;
            color: #388e3c;
        }
        
        .video-controls {
            margin-top: 10px;
            display: flex;
            gap: 10px;
        }
        
        .video-controls button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            background-color: #1976d2;
            color: white;
            cursor: pointer;
            font-size: 14px;
        }
        
        .video-controls button:hover {
            background-color: #1565c0;
        }
        
        .video-controls button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        
        .playlist-container {
            display: grid;
            gap: 20px;
            margin: 20px 0;
        }
        
        .playlist-item {
            display: flex;
            gap: 15px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #fff;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .playlist-item:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transform: translateY(-1px);
        }
        
        .playlist-thumbnail {
            width: 120px;
            height: 90px;
            border-radius: 4px;
            object-fit: cover;
        }
        
        .playlist-info {
            flex: 1;
        }
        
        .playlist-title {
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        
        .playlist-description {
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }
        
        .playlist-meta {
            display: flex;
            gap: 10px;
            font-size: 12px;
        }
        
        @media (max-width: 768px) {
            .video-player-container iframe {
                width: 100%;
                height: 250px;
            }
            
            .playlist-item {
                flex-direction: column;
            }
            
            .playlist-thumbnail {
                width: 100%;
                height: 180px;
            }
        }
        </style>
        '''
        
        return css_styles
    
    def get_player_config(self) -> VideoPlayerConfig:
        """현재 플레이어 설정 반환"""
        return self.player_config
    
    def set_player_config(self, config: VideoPlayerConfig) -> None:
        """플레이어 설정 업데이트"""
        self.player_config = config
        self.logger.info("플레이어 설정 업데이트 완료")
    
    def validate_segment(self, segment: PlaybackSegment) -> bool:
        """재생 구간 유효성 검증"""
        if segment.start_time < 0:
            return False
        
        if segment.end_time <= segment.start_time:
            return False
        
        if segment.end_time - segment.start_time > 600:  # 10분 초과
            self.logger.warning(f"구간이 너무 깁니다: {segment.end_time - segment.start_time}초")
        
        return True