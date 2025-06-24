"""
RSS 피드 자동 수집기

PRD 2.2 요구사항:
- 승인된 채널 목록의 RSS 피드를 통해 매일 자동 수집
- 미디어 채널은 영상 제목에 등록된 연예인 이름 포함된 경우만 수집
- YouTube 쇼츠는 분석 대상에서 명시적으로 제외
"""

import feedparser
import sqlite3
import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
import re
import time

# VideoInfo 모델 제거됨 - 직접 딕셔너리 사용
from ..youtube_api.youtube_client import YouTubeAPIClient
from .content_filter import ContentFilter


@dataclass
class ChannelInfo:
    """채널 정보"""
    channel_id: str
    channel_name: str
    channel_type: str  # 'personal' 또는 'media'
    rss_url: str
    is_active: bool = True


@dataclass
class CollectionResult:
    """수집 결과"""
    success: bool
    collected_count: int
    filtered_count: int
    error_count: int
    errors: List[str]
    execution_time: float


class RSSCollector:
    """RSS 피드 자동 수집기"""
    
    def __init__(self, db_path: str = "influence_item.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.youtube_client = YouTubeAPIClient()
        self.content_filter = ContentFilter()
        self._setup_database()
    
    def _setup_database(self) -> None:
        """데이터베이스 테이블 설정"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # RSS 수집 채널 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rss_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT NOT NULL,
                    channel_type TEXT NOT NULL CHECK (channel_type IN ('personal', 'media')),
                    rss_url TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_collected_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # RSS 수집 로그 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rss_collection_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    video_title TEXT,
                    video_url TEXT,
                    published_date TIMESTAMP,
                    collection_status TEXT NOT NULL CHECK (collection_status IN ('collected', 'filtered', 'error')),
                    filter_reason TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_id) REFERENCES rss_channels (channel_id)
                )
            """)
            
            # RSS 수집 실행 로그 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rss_execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT UNIQUE NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    total_channels INTEGER DEFAULT 0,
                    total_collected INTEGER DEFAULT 0,
                    total_filtered INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    execution_status TEXT DEFAULT 'running' CHECK (execution_status IN ('running', 'completed', 'failed')),
                    error_message TEXT
                )
            """)
            
            conn.commit()
    
    def add_channel(self, channel_info: ChannelInfo) -> bool:
        """채널 추가"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO rss_channels 
                    (channel_id, channel_name, channel_type, rss_url, is_active, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    channel_info.channel_id,
                    channel_info.channel_name,
                    channel_info.channel_type,
                    channel_info.rss_url,
                    channel_info.is_active
                ))
                conn.commit()
                self.logger.info(f"채널 추가됨: {channel_info.channel_name} ({channel_info.channel_id})")
                return True
        except Exception as e:
            self.logger.error(f"채널 추가 실패: {str(e)}")
            return False
    
    def get_active_channels(self) -> List[ChannelInfo]:
        """활성 채널 목록 조회"""
        channels = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT channel_id, channel_name, channel_type, rss_url, is_active
                    FROM rss_channels 
                    WHERE is_active = TRUE
                    ORDER BY channel_name
                """)
                
                for row in cursor.fetchall():
                    channels.append(ChannelInfo(
                        channel_id=row[0],
                        channel_name=row[1],
                        channel_type=row[2],
                        rss_url=row[3],
                        is_active=row[4]
                    ))
        except Exception as e:
            self.logger.error(f"활성 채널 조회 실패: {str(e)}")
        
        return channels
    
    def _extract_video_id_from_url(self, url: str) -> Optional[str]:
        """YouTube URL에서 비디오 ID 추출"""
        try:
            # YouTube URL 패턴들
            patterns = [
                r'youtube\.com/watch\?v=([^&]+)',
                r'youtu\.be/([^?]+)',
                r'youtube\.com/embed/([^?]+)',
                r'youtube\.com/v/([^?]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            self.logger.error(f"비디오 ID 추출 실패: {str(e)}")
            return None
    
    def _is_youtube_shorts(self, video_id: str) -> bool:
        """YouTube 쇼츠 여부 확인"""
        try:
            # YouTube API를 통해 비디오 정보 조회
            video_info = self.youtube_client.get_video_details(video_id)
            if not video_info:
                return False
            
            # 길이가 60초 이하인 세로형 비디오는 쇼츠로 간주
            duration = video_info.get('duration_seconds', 0)
            if duration <= 60:
                # 추가로 비디오 해상도나 기타 메타데이터로 쇼츠 판별 가능
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"쇼츠 여부 확인 실패 {video_id}: {str(e)}")
            return False
    
    def _is_duplicate_video(self, video_id: str) -> bool:
        """중복 비디오 확인"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM rss_collection_logs 
                    WHERE video_id = ? AND collection_status = 'collected'
                """, (video_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            self.logger.error(f"중복 확인 실패: {str(e)}")
            return False
    
    def _collect_from_rss_feed(self, channel: ChannelInfo) -> List[Dict[str, Any]]:
        """RSS 피드에서 비디오 수집"""
        collected_videos = []
        
        try:
            self.logger.info(f"RSS 피드 수집 시작: {channel.channel_name}")
            
            # RSS 피드 파싱
            feed = feedparser.parse(channel.rss_url)
            
            if feed.bozo:
                self.logger.warning(f"RSS 피드 파싱 경고: {channel.channel_name} - {feed.bozo_exception}")
            
            # 최근 7일 이내의 비디오만 수집
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for entry in feed.entries:
                try:
                    # 비디오 URL에서 ID 추출
                    video_id = self._extract_video_id_from_url(entry.link)
                    if not video_id:
                        continue
                    
                    # 중복 확인
                    if self._is_duplicate_video(video_id):
                        continue
                    
                    # 게시 날짜 확인
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_date = datetime(*entry.published_parsed[:6])
                        if published_date < cutoff_date:
                            continue
                    
                    # 쇼츠 제외
                    if self._is_youtube_shorts(video_id):
                        self._log_collection_result(
                            channel.channel_id, video_id, entry.title, entry.link,
                            published_date, 'filtered', 'YouTube Shorts 제외'
                        )
                        continue
                    
                    # 미디어 채널의 경우 연예인 이름 필터링
                    if channel.channel_type == 'media':
                        if not self.content_filter.has_celebrity_name(entry.title):
                            self._log_collection_result(
                                channel.channel_id, video_id, entry.title, entry.link,
                                published_date, 'filtered', '연예인 이름 미포함'
                            )
                            continue
                    
                    video_data = {
                        'video_id': video_id,
                        'title': entry.title,
                        'url': entry.link,
                        'channel_id': channel.channel_id,
                        'channel_name': channel.channel_name,
                        'published_date': published_date,
                        'description': getattr(entry, 'summary', ''),
                        'thumbnail_url': self._extract_thumbnail_url(entry)
                    }
                    
                    collected_videos.append(video_data)
                    
                    # 수집 로그 기록
                    self._log_collection_result(
                        channel.channel_id, video_id, entry.title, entry.link,
                        published_date, 'collected', None
                    )
                    
                except Exception as e:
                    self.logger.error(f"비디오 처리 실패 {channel.channel_name}: {str(e)}")
                    continue
            
            self.logger.info(f"RSS 피드 수집 완료: {channel.channel_name}, 수집된 비디오: {len(collected_videos)}개")
            
        except Exception as e:
            self.logger.error(f"RSS 피드 수집 실패 {channel.channel_name}: {str(e)}")
        
        return collected_videos
    
    def _extract_thumbnail_url(self, entry: Any) -> Optional[str]:
        """RSS 엔트리에서 썸네일 URL 추출"""
        try:
            # RSS 피드에서 썸네일 추출
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0]['url']
            
            # YouTube 기본 썸네일 생성
            video_id = self._extract_video_id_from_url(entry.link)
            if video_id:
                return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            
            return None
        except Exception:
            return None
    
    def _log_collection_result(self, channel_id: str, video_id: str, title: str, 
                             url: str, published_date: Optional[datetime], 
                             status: str, filter_reason: Optional[str]) -> None:
        """수집 결과 로그 기록"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rss_collection_logs 
                    (channel_id, video_id, video_title, video_url, published_date, 
                     collection_status, filter_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    channel_id, video_id, title, url, published_date, status, filter_reason
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"수집 로그 기록 실패: {str(e)}")
    
    def _save_collected_videos(self, videos: List[Dict[str, Any]]) -> int:
        """수집된 비디오를 데이터베이스에 저장"""
        saved_count = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for video in videos:
                    try:
                        # videos 테이블에 저장 (기존 테이블 구조 활용)
                        cursor.execute("""
                            INSERT OR IGNORE INTO videos 
                            (video_id, title, channel_name, channel_id, url, 
                             upload_date, description, thumbnail_url, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'collected')
                        """, (
                            video['video_id'],
                            video['title'],
                            video['channel_name'],
                            video['channel_id'],
                            video['url'],
                            video['published_date'],
                            video['description'],
                            video['thumbnail_url']
                        ))
                        
                        if cursor.rowcount > 0:
                            saved_count += 1
                            
                    except Exception as e:
                        self.logger.error(f"비디오 저장 실패 {video['video_id']}: {str(e)}")
                        continue
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"비디오 저장 중 오류: {str(e)}")
        
        return saved_count
    
    def _update_channel_last_collected(self, channel_id: str) -> None:
        """채널 마지막 수집 시간 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rss_channels 
                    SET last_collected_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                """, (channel_id,))
                conn.commit()
        except Exception as e:
            self.logger.error(f"채널 수집 시간 업데이트 실패: {str(e)}")
    
    async def collect_daily_videos(self) -> CollectionResult:
        """일일 비디오 수집 실행"""
        start_time = time.time()
        execution_id = f"rss_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        result = CollectionResult(
            success=False,
            collected_count=0,
            filtered_count=0,
            error_count=0,
            errors=[],
            execution_time=0.0
        )
        
        try:
            self.logger.info(f"RSS 일일 수집 시작: {execution_id}")
            
            # 실행 로그 시작 기록
            self._log_execution_start(execution_id)
            
            # 활성 채널 목록 조회
            channels = self.get_active_channels()
            if not channels:
                self.logger.warning("활성 채널이 없습니다.")
                return result
            
            all_collected_videos = []
            total_filtered = 0
            total_errors = 0
            
            # 각 채널에서 비디오 수집
            for channel in channels:
                try:
                    collected_videos = self._collect_from_rss_feed(channel)
                    all_collected_videos.extend(collected_videos)
                    
                    # 채널별 통계 계산
                    channel_filtered = self._count_filtered_videos(channel.channel_id, execution_id)
                    total_filtered += channel_filtered
                    
                    # 채널 마지막 수집 시간 업데이트
                    self._update_channel_last_collected(channel.channel_id)
                    
                except Exception as e:
                    error_msg = f"채널 {channel.channel_name} 수집 실패: {str(e)}"
                    self.logger.error(error_msg)
                    result.errors.append(error_msg)
                    total_errors += 1
            
            # 수집된 비디오 저장
            saved_count = self._save_collected_videos(all_collected_videos)
            
            # 결과 설정
            result.success = True
            result.collected_count = saved_count
            result.filtered_count = total_filtered
            result.error_count = total_errors
            result.execution_time = time.time() - start_time
            
            # 실행 로그 완료 기록
            self._log_execution_complete(execution_id, len(channels), saved_count, 
                                       total_filtered, total_errors, None)
            
            self.logger.info(
                f"RSS 일일 수집 완료: 수집 {saved_count}개, 필터링 {total_filtered}개, "
                f"오류 {total_errors}개, 실행시간 {result.execution_time:.2f}초"
            )
            
        except Exception as e:
            error_msg = f"RSS 일일 수집 실패: {str(e)}"
            self.logger.error(error_msg)
            result.errors.append(error_msg)
            result.execution_time = time.time() - start_time
            
            # 실행 로그 실패 기록
            self._log_execution_complete(execution_id, len(channels) if 'channels' in locals() else 0, 
                                       0, 0, 1, error_msg)
        
        return result
    
    def _count_filtered_videos(self, channel_id: str, execution_id: str) -> int:
        """특정 채널의 필터링된 비디오 수 계산"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM rss_collection_logs 
                    WHERE channel_id = ? AND collection_status = 'filtered'
                    AND DATE(collected_at) = DATE('now')
                """, (channel_id,))
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def _log_execution_start(self, execution_id: str) -> None:
        """실행 시작 로그 기록"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rss_execution_logs (execution_id, started_at)
                    VALUES (?, CURRENT_TIMESTAMP)
                """, (execution_id,))
                conn.commit()
        except Exception as e:
            self.logger.error(f"실행 시작 로그 기록 실패: {str(e)}")
    
    def _log_execution_complete(self, execution_id: str, total_channels: int, 
                              collected: int, filtered: int, errors: int, 
                              error_message: Optional[str]) -> None:
        """실행 완료 로그 기록"""
        try:
            status = 'completed' if error_message is None else 'failed'
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rss_execution_logs 
                    SET completed_at = CURRENT_TIMESTAMP,
                        total_channels = ?,
                        total_collected = ?,
                        total_filtered = ?,
                        total_errors = ?,
                        execution_status = ?,
                        error_message = ?
                    WHERE execution_id = ?
                """, (total_channels, collected, filtered, errors, status, error_message, execution_id))
                conn.commit()
        except Exception as e:
            self.logger.error(f"실행 완료 로그 기록 실패: {str(e)}")
    
    def get_collection_statistics(self, days: int = 7) -> Dict[str, Any]:
        """수집 통계 조회"""
        stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'total_collected': 0,
            'total_filtered': 0,
            'total_errors': 0,
            'avg_execution_time': 0.0,
            'daily_stats': []
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 실행 통계
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_executions,
                        SUM(CASE WHEN execution_status = 'completed' THEN 1 ELSE 0 END) as successful,
                        SUM(total_collected) as collected,
                        SUM(total_filtered) as filtered,
                        SUM(total_errors) as errors
                    FROM rss_execution_logs
                    WHERE DATE(started_at) >= DATE('now', '-{} days')
                """.format(days))
                
                row = cursor.fetchone()
                if row:
                    stats.update({
                        'total_executions': row[0] or 0,
                        'successful_executions': row[1] or 0,
                        'total_collected': row[2] or 0,
                        'total_filtered': row[3] or 0,
                        'total_errors': row[4] or 0
                    })
                
                # 일별 통계
                cursor.execute("""
                    SELECT 
                        DATE(started_at) as date,
                        COUNT(*) as executions,
                        SUM(total_collected) as collected,
                        SUM(total_filtered) as filtered,
                        SUM(total_errors) as errors
                    FROM rss_execution_logs
                    WHERE DATE(started_at) >= DATE('now', '-{} days')
                    GROUP BY DATE(started_at)
                    ORDER BY date DESC
                """.format(days))
                
                daily_stats = []
                for row in cursor.fetchall():
                    daily_stats.append({
                        'date': row[0],
                        'executions': row[1],
                        'collected': row[2] or 0,
                        'filtered': row[3] or 0,
                        'errors': row[4] or 0
                    })
                
                stats['daily_stats'] = daily_stats
                
        except Exception as e:
            self.logger.error(f"통계 조회 실패: {str(e)}")
        
        return stats