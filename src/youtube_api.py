"""
YouTube API 연동 모듈
PRD v1.0 - 채널/영상 수집 및 메타데이터 추출
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import time
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import yt_dlp
from pathlib import Path

logger = logging.getLogger(__name__)


class YouTubeAPIManager:
    """YouTube API 관리자"""
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: YouTube Data API v3 키
        """
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            logger.warning("YouTube API 키가 설정되지 않았습니다. 환경변수 YOUTUBE_API_KEY를 설정하세요.")
            
        self.youtube = None
        if self.api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
                logger.info("YouTube API 클라이언트 초기화 완료")
            except Exception as e:
                logger.error(f"YouTube API 클라이언트 초기화 실패: {e}")
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """YouTube URL에서 비디오 ID 추출"""
        try:
            if 'youtube.com/watch?v=' in url:
                return url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in url:
                return url.split('youtu.be/')[1].split('?')[0]
            elif len(url) == 11:  # 직접 비디오 ID인 경우
                return url
            return None
        except Exception:
            return None
    
    def extract_channel_id(self, url: str) -> Optional[str]:
        """YouTube 채널 URL에서 채널 ID 추출"""
        try:
            if 'youtube.com/channel/' in url:
                return url.split('channel/')[1].split('/')[0]
            elif 'youtube.com/c/' in url or 'youtube.com/@' in url:
                # 커스텀 URL은 검색으로 채널 ID 찾기
                return self._get_channel_id_by_username(url)
            return None
        except Exception:
            return None
    
    def _get_channel_id_by_username(self, url: str) -> Optional[str]:
        """커스텀 URL에서 채널 ID 찾기"""
        if not self.youtube:
            return None
            
        try:
            # URL에서 사용자명 추출
            if 'youtube.com/c/' in url:
                username = url.split('/c/')[1].split('/')[0]
            elif 'youtube.com/@' in url:
                username = url.split('/@')[1].split('/')[0]
            else:
                return None
            
            # 검색으로 채널 찾기
            search_response = self.youtube.search().list(
                q=username,
                type='channel',
                part='snippet',
                maxResults=5
            ).execute()
            
            for item in search_response.get('items', []):
                if item['snippet']['title'].lower().replace(' ', '') == username.lower():
                    return item['snippet']['channelId']
                    
            return None
        except Exception as e:
            logger.error(f"채널 ID 검색 실패: {e}")
            return None
    
    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """채널 정보 조회"""
        if not self.youtube:
            logger.error("YouTube API 클라이언트가 초기화되지 않았습니다.")
            return None
            
        try:
            response = self.youtube.channels().list(
                part='snippet,statistics,brandingSettings',
                id=channel_id
            ).execute()
            
            if not response.get('items'):
                return None
                
            channel = response['items'][0]
            
            return {
                'channel_id': channel_id,
                'title': channel['snippet']['title'],
                'description': channel['snippet']['description'],
                'thumbnail_url': channel['snippet']['thumbnails'].get('high', {}).get('url'),
                'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
                'video_count': int(channel['statistics'].get('videoCount', 0)),
                'view_count': int(channel['statistics'].get('viewCount', 0)),
                'country': channel['snippet'].get('country'),
                'published_at': channel['snippet']['publishedAt'],
                'custom_url': channel['snippet'].get('customUrl'),
                'keywords': channel.get('brandingSettings', {}).get('channel', {}).get('keywords', '').split(', ')
            }
            
        except HttpError as e:
            logger.error(f"채널 정보 조회 실패 (HTTP {e.resp.status}): {e}")
            return None
        except Exception as e:
            logger.error(f"채널 정보 조회 실패: {e}")
            return None
    
    def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 50,
        published_after: datetime = None,
        published_before: datetime = None
    ) -> List[Dict[str, Any]]:
        """채널의 영상 목록 조회"""
        if not self.youtube:
            logger.error("YouTube API 클라이언트가 초기화되지 않았습니다.")
            return []
            
        videos = []
        
        try:
            # 채널의 업로드 플레이리스트 ID 가져오기
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            if not channel_response.get('items'):
                logger.warning(f"채널을 찾을 수 없습니다: {channel_id}")
                return []
                
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # 플레이리스트에서 영상 목록 가져오기
            next_page_token = None
            collected_count = 0
            
            while collected_count < max_results:
                playlist_response = self.youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=uploads_playlist_id,
                    maxResults=min(50, max_results - collected_count),
                    pageToken=next_page_token
                ).execute()
                
                video_ids = []
                for item in playlist_response.get('items', []):
                    published_at = datetime.fromisoformat(
                        item['snippet']['publishedAt'].replace('Z', '+00:00')
                    ).replace(tzinfo=None)
                    
                    # 날짜 필터링
                    if published_after and published_at < published_after:
                        continue
                    if published_before and published_at > published_before:
                        continue
                        
                    video_ids.append(item['contentDetails']['videoId'])
                
                if not video_ids:
                    break
                
                # 영상 상세 정보 가져오기
                video_details = self._get_video_details(video_ids)
                videos.extend(video_details)
                collected_count += len(video_details)
                
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token or collected_count >= max_results:
                    break
                    
                # API 호출 제한 준수
                time.sleep(0.1)
            
            logger.info(f"채널 {channel_id}에서 {len(videos)}개 영상 수집 완료")
            return videos[:max_results]
            
        except HttpError as e:
            logger.error(f"채널 영상 조회 실패 (HTTP {e.resp.status}): {e}")
            return []
        except Exception as e:
            logger.error(f"채널 영상 조회 실패: {e}")
            return []
    
    def _get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """영상 상세 정보 가져오기"""
        if not video_ids:
            return []
            
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            videos = []
            for item in response.get('items', []):
                # 영상 길이 파싱
                duration = self._parse_duration(item['contentDetails']['duration'])
                
                # Shorts 제외 (PRD 요구사항)
                if duration and duration < 60:  # 60초 미만은 Shorts로 간주
                    continue
                
                video_data = {
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'thumbnail_url': item['snippet']['thumbnails'].get('high', {}).get('url'),
                    'duration_seconds': duration,
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'like_count': int(item['statistics'].get('likeCount', 0)),
                    'comment_count': int(item['statistics'].get('commentCount', 0)),
                    'tags': item['snippet'].get('tags', []),
                    'category_id': item['snippet'].get('categoryId'),
                    'default_language': item['snippet'].get('defaultLanguage'),
                    'url': f"https://www.youtube.com/watch?v={item['id']}"
                }
                videos.append(video_data)
                
            return videos
            
        except Exception as e:
            logger.error(f"영상 상세 정보 조회 실패: {e}")
            return []
    
    def _parse_duration(self, duration_str: str) -> Optional[int]:
        """ISO 8601 duration을 초 단위로 변환"""
        try:
            # PT1H2M3S 형식을 초로 변환
            import re
            
            if not duration_str.startswith('PT'):
                return None
                
            # 시간, 분, 초 추출
            hours = re.search(r'(\d+)H', duration_str)
            minutes = re.search(r'(\d+)M', duration_str)
            seconds = re.search(r'(\d+)S', duration_str)
            
            total_seconds = 0
            if hours:
                total_seconds += int(hours.group(1)) * 3600
            if minutes:
                total_seconds += int(minutes.group(1)) * 60
            if seconds:
                total_seconds += int(seconds.group(1))
                
            return total_seconds
            
        except Exception:
            return None
    
    def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """단일 영상 정보 조회"""
        if not self.youtube:
            logger.error("YouTube API 클라이언트가 초기화되지 않았습니다.")
            return None
            
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return None
                
            item = response['items'][0]
            duration = self._parse_duration(item['contentDetails']['duration'])
            
            return {
                'video_id': video_id,
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'published_at': item['snippet']['publishedAt'],
                'channel_id': item['snippet']['channelId'],
                'channel_title': item['snippet']['channelTitle'],
                'thumbnail_url': item['snippet']['thumbnails'].get('high', {}).get('url'),
                'duration_seconds': duration,
                'view_count': int(item['statistics'].get('viewCount', 0)),
                'like_count': int(item['statistics'].get('likeCount', 0)),
                'comment_count': int(item['statistics'].get('commentCount', 0)),
                'tags': item['snippet'].get('tags', []),
                'category_id': item['snippet'].get('categoryId'),
                'default_language': item['snippet'].get('defaultLanguage'),
                'url': f"https://www.youtube.com/watch?v={video_id}"
            }
            
        except HttpError as e:
            logger.error(f"영상 정보 조회 실패 (HTTP {e.resp.status}): {e}")
            return None
        except Exception as e:
            logger.error(f"영상 정보 조회 실패: {e}")
            return None
    
    def search_channels(
        self,
        query: str,
        max_results: int = 20,
        celebrity_keywords: List[str] = None
    ) -> List[Dict[str, Any]]:
        """채널 검색 (신규 채널 탐색용)"""
        if not self.youtube:
            logger.error("YouTube API 클라이언트가 초기화되지 않았습니다.")
            return []
            
        channels = []
        celebrity_keywords = celebrity_keywords or []
        
        try:
            search_response = self.youtube.search().list(
                q=query,
                type='channel',
                part='snippet',
                maxResults=max_results,
                order='relevance'
            ).execute()
            
            channel_ids = [item['id']['channelId'] for item in search_response.get('items', [])]
            
            if not channel_ids:
                return []
            
            # 채널 상세 정보 가져오기
            channels_response = self.youtube.channels().list(
                part='snippet,statistics,brandingSettings',
                id=','.join(channel_ids)
            ).execute()
            
            for item in channels_response.get('items', []):
                channel_data = {
                    'channel_id': item['id'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'thumbnail_url': item['snippet']['thumbnails'].get('high', {}).get('url'),
                    'subscriber_count': int(item['statistics'].get('subscriberCount', 0)),
                    'video_count': int(item['statistics'].get('videoCount', 0)),
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'published_at': item['snippet']['publishedAt'],
                    'custom_url': item['snippet'].get('customUrl'),
                    'keywords': item.get('brandingSettings', {}).get('channel', {}).get('keywords', '').split(', '),
                    'relevance_score': self._calculate_relevance_score(item, celebrity_keywords, query)
                }
                channels.append(channel_data)
            
            # 관련성 점수로 정렬
            channels.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            logger.info(f"'{query}' 검색으로 {len(channels)}개 채널 발견")
            return channels
            
        except HttpError as e:
            logger.error(f"채널 검색 실패 (HTTP {e.resp.status}): {e}")
            return []
        except Exception as e:
            logger.error(f"채널 검색 실패: {e}")
            return []
    
    def _calculate_relevance_score(
        self,
        channel: Dict[str, Any],
        celebrity_keywords: List[str],
        query: str
    ) -> float:
        """채널 관련성 점수 계산 (PRD의 정밀 매칭 알고리즘)"""
        score = 0.0
        
        title = channel['snippet']['title'].lower()
        description = channel['snippet']['description'].lower()
        
        # 1. 제목 일치도 (가중치 40%)
        if query.lower() in title:
            score += 40
        elif any(keyword.lower() in title for keyword in celebrity_keywords):
            score += 30
        
        # 2. 설명 일치도 (가중치 20%)
        if query.lower() in description:
            score += 20
        elif any(keyword.lower() in description for keyword in celebrity_keywords):
            score += 15
        
        # 3. 구독자 수 (가중치 20%, 로그 스케일)
        subscriber_count = int(channel['statistics'].get('subscriberCount', 0))
        if subscriber_count > 0:
            import math
            score += min(20, math.log10(subscriber_count) * 3)
        
        # 4. 영상 수 (가중치 10%)
        video_count = int(channel['statistics'].get('videoCount', 0))
        if video_count > 10:
            score += min(10, video_count / 10)
        
        # 5. 커스텀 URL 존재 (가중치 10%)
        if channel['snippet'].get('customUrl'):
            score += 10
        
        return round(score, 2)


class YouTubeDownloader:
    """YouTube 영상 다운로드 및 메타데이터 추출"""
    
    def __init__(self, download_dir: str = "downloads"):
        """
        Args:
            download_dir: 다운로드 디렉토리
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        # yt-dlp 설정
        self.ydl_opts = {
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'format': 'bestaudio[ext=mp3]/best[height<=720]',  # 음성 우선, 최대 720p
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['ko', 'en'],
            'ignoreerrors': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192K',
        }
    
    def download_audio(self, video_url: str) -> Optional[Dict[str, Any]]:
        """영상에서 오디오 추출"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # 메타데이터만 먼저 추출
                info = ydl.extract_info(video_url, download=False)
                
                if not info:
                    return None
                
                video_id = info.get('id')
                duration = info.get('duration', 0)
                
                # Shorts 제외 (PRD 요구사항)
                if duration < 60:
                    logger.info(f"Shorts 영상 제외: {video_id} (길이: {duration}초)")
                    return None
                
                # 오디오 다운로드
                audio_file = self.download_dir / f"{video_id}.mp3"
                if not audio_file.exists():
                    ydl.download([video_url])
                
                # 자막 파일 경로
                subtitle_files = {
                    'ko': self.download_dir / f"{video_id}.ko.vtt",
                    'en': self.download_dir / f"{video_id}.en.vtt",
                    'auto_ko': self.download_dir / f"{video_id}.ko.vtt",
                    'auto_en': self.download_dir / f"{video_id}.en.vtt"
                }
                
                return {
                    'video_id': video_id,
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'duration': duration,
                    'uploader': info.get('uploader'),
                    'upload_date': info.get('upload_date'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'audio_file': str(audio_file) if audio_file.exists() else None,
                    'subtitle_files': {
                        lang: str(path) for lang, path in subtitle_files.items() 
                        if path.exists()
                    },
                    'thumbnail': info.get('thumbnail'),
                    'tags': info.get('tags', []),
                    'categories': info.get('categories', [])
                }
                
        except Exception as e:
            logger.error(f"영상 다운로드 실패 ({video_url}): {e}")
            return None
    
    def extract_video_segments(
        self,
        video_url: str,
        start_time: int,
        end_time: int,
        output_path: str = None
    ) -> Optional[str]:
        """특정 구간 영상 추출"""
        try:
            video_id = video_url.split('v=')[-1].split('&')[0]
            
            if not output_path:
                output_path = str(self.download_dir / f"{video_id}_{start_time}_{end_time}.mp4")
            
            # ffmpeg를 사용한 구간 추출 (별도 구현 필요)
            # 현재는 전체 영상 정보만 반환
            
            opts = {
                'outtmpl': output_path,
                'format': 'best[height<=720]',
                'external_downloader': 'ffmpeg',
                'external_downloader_args': [
                    '-ss', str(start_time),
                    '-t', str(end_time - start_time)
                ]
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([video_url])
                
            return output_path if Path(output_path).exists() else None
            
        except Exception as e:
            logger.error(f"영상 구간 추출 실패: {e}")
            return None


def create_youtube_manager() -> YouTubeAPIManager:
    """YouTube API 매니저 생성"""
    return YouTubeAPIManager()


def create_youtube_downloader(download_dir: str = "downloads") -> YouTubeDownloader:
    """YouTube 다운로더 생성"""
    return YouTubeDownloader(download_dir)


if __name__ == "__main__":
    # 테스트 코드
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # API 키가 없으면 경고만 출력하고 종료
    if not os.getenv('YOUTUBE_API_KEY'):
        print("YouTube API 키가 설정되지 않았습니다.")
        print("환경변수 YOUTUBE_API_KEY를 설정해주세요.")
        sys.exit(1)
    
    # YouTube API 테스트
    yt_manager = create_youtube_manager()
    
    # 채널 검색 테스트
    channels = yt_manager.search_channels("강민경", max_results=5)
    print(f"검색 결과: {len(channels)}개 채널")
    
    for channel in channels:
        print(f"- {channel['title']} (구독자: {channel['subscriber_count']:,}명)")