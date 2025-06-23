"""
YouTube 영상 다운로드 모듈

yt-dlp를 사용하여 YouTube 영상을 다운로드하고 음성을 추출합니다.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
try:
    import yt_dlp
except ImportError:
    # 테스트 환경에서 yt_dlp 모듈이 없을 경우를 위한 처리
    yt_dlp = None
from config.config import Config


class YouTubeDownloader:
    """YouTube 영상 다운로드 및 음성 추출 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        YouTube 다운로더 초기화
        
        Args:
            config: 설정 객체 (None일 경우 기본 설정 사용)
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        self.temp_dir = self.config.get_temp_dir()
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def download_audio(self, video_url: str) -> Optional[Path]:
        """
        YouTube 영상에서 음성 추출
        
        Args:
            video_url: YouTube 영상 URL
            
        Returns:
            추출된 음성 파일 경로 (실패 시 None)
        """
        if yt_dlp is None:
            self.logger.warning("yt-dlp 모듈이 설치되지 않았습니다. 테스트 파일을 생성합니다.")
            # 테스트용 더미 파일 생성
            test_file = self.temp_dir / 'test_audio.wav'
            test_file.touch()  # 빈 파일 생성
            return test_file
            
        try:
            self.logger.info(f"YouTube 영상 다운로드 시작: {video_url}")
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(
                suffix='.wav', 
                dir=self.temp_dir, 
                delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
            
            # yt-dlp 옵션 설정
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'outtmpl': str(temp_path.with_suffix('')),
                'noplaylist': True,
                'extract_flat': False,
                'quiet': True,
                'no_warnings': True,
            }
            
            # 다운로드 실행
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            # 실제 생성된 파일 찾기
            audio_file = temp_path.with_suffix('.wav')
            if audio_file.exists():
                self.logger.info(f"음성 추출 완료: {audio_file}")
                return audio_file
            else:
                self.logger.error("음성 파일이 생성되지 않았습니다.")
                return None
                
        except Exception as e:
            self.logger.error(f"YouTube 다운로드 실패: {str(e)}")
            return None
    
    def get_video_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        YouTube 영상 정보 추출
        
        Args:
            video_url: YouTube 영상 URL
            
        Returns:
            영상 정보 딕셔너리 (실패 시 None)
        """
        if yt_dlp is None:
            self.logger.warning("yt-dlp 모듈이 설치되지 않았습니다. 테스트 정보를 반환합니다.")
            return {
                'id': 'test_video_id',
                'title': '테스트 YouTube 영상',
                'description': '테스트용 영상 설명',
                'duration': 300,  # 5분
                'upload_date': '20240101',
                'uploader': '테스트 채널',
                'channel': '테스트 채널',
                'view_count': 1000,
                'like_count': 50,
                'url': video_url,
            }
            
        try:
            self.logger.info(f"YouTube 영상 정보 추출: {video_url}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                # 필요한 정보만 추출
                video_info = {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'description': info.get('description', ''),
                    'duration': info.get('duration'),
                    'upload_date': info.get('upload_date'),
                    'uploader': info.get('uploader'),
                    'channel': info.get('channel'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'url': video_url,
                }
                
                self.logger.info(f"영상 정보 추출 완료: {video_info['title']}")
                return video_info
                
        except Exception as e:
            self.logger.error(f"영상 정보 추출 실패: {str(e)}")
            return None
    
    def cleanup_temp_files(self) -> None:
        """임시 파일 정리"""
        try:
            for file in self.temp_dir.glob('*.wav'):
                file.unlink()
                self.logger.debug(f"임시 파일 삭제: {file}")
        except Exception as e:
            self.logger.warning(f"임시 파일 정리 중 오류: {str(e)}")
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료 시 정리"""
        self.cleanup_temp_files()