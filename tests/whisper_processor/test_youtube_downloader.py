"""
YouTube 다운로더 단위 테스트
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.whisper_processor.youtube_downloader import YouTubeDownloader
from config import Config


class TestYouTubeDownloader:
    """YouTubeDownloader 테스트 클래스"""
    
    @pytest.fixture
    def mock_config(self):
        """테스트용 설정 모의객체"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = "INFO"
        config.get_temp_dir.return_value = Path("/tmp/test")
        return config
    
    @pytest.fixture
    def downloader(self, mock_config):
        """YouTubeDownloader 인스턴스"""
        return YouTubeDownloader(mock_config)
    
    @patch('src.whisper_processor.youtube_downloader.yt_dlp')
    @patch('tempfile.NamedTemporaryFile')
    def test_download_audio_success(self, mock_tempfile, mock_yt_dlp, downloader):
        """음성 다운로드 성공 테스트"""
        # 임시 파일 모의
        mock_file = Mock()
        mock_file.name = "/tmp/test/temp_audio"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # yt-dlp 모의
        mock_ydl_instance = Mock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        # 생성된 파일 존재 모의
        expected_path = Path("/tmp/test/temp_audio.wav")
        with patch('pathlib.Path.exists', return_value=True):
            result = downloader.download_audio("https://youtube.com/watch?v=test")
        
        assert result == expected_path
        mock_ydl_instance.download.assert_called_once_with(["https://youtube.com/watch?v=test"])
    
    @patch('src.whisper_processor.youtube_downloader.yt_dlp')
    def test_get_video_info_success(self, mock_yt_dlp, downloader):
        """영상 정보 추출 성공 테스트"""
        # yt-dlp 반환 데이터 모의
        mock_info = {
            'id': 'test_id',
            'title': '테스트 영상',
            'description': '테스트 설명',
            'duration': 300,
            'upload_date': '20240622',
            'uploader': '테스트 채널',
            'channel': '테스트 채널',
            'view_count': 1000,
            'like_count': 100,
        }
        
        mock_ydl_instance = Mock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        result = downloader.get_video_info("https://youtube.com/watch?v=test")
        
        assert result['id'] == 'test_id'
        assert result['title'] == '테스트 영상'
        assert result['duration'] == 300
        assert result['url'] == "https://youtube.com/watch?v=test"
        mock_ydl_instance.extract_info.assert_called_once_with(
            "https://youtube.com/watch?v=test", download=False
        )
    
    @patch('src.whisper_processor.youtube_downloader.yt_dlp')
    def test_download_audio_failure(self, mock_yt_dlp, downloader):
        """음성 다운로드 실패 테스트"""
        # yt-dlp 예외 발생
        mock_ydl_instance = Mock()
        mock_ydl_instance.download.side_effect = Exception("다운로드 실패")
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        result = downloader.download_audio("https://youtube.com/watch?v=invalid")
        
        assert result is None
    
    @patch('src.whisper_processor.youtube_downloader.yt_dlp')
    def test_get_video_info_failure(self, mock_yt_dlp, downloader):
        """영상 정보 추출 실패 테스트"""
        # yt-dlp 예외 발생
        mock_ydl_instance = Mock()
        mock_ydl_instance.extract_info.side_effect = Exception("정보 추출 실패")
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        result = downloader.get_video_info("https://youtube.com/watch?v=invalid")
        
        assert result is None
    
    def test_context_manager(self, downloader):
        """컨텍스트 매니저 테스트"""
        with patch.object(downloader, 'cleanup_temp_files') as mock_cleanup:
            with downloader:
                pass  # 컨텍스트 내에서 작업
            
            mock_cleanup.assert_called_once()
    
    def test_cleanup_temp_files(self, downloader):
        """임시 파일 정리 테스트"""
        # 임시 디렉토리 모의
        mock_temp_dir = Mock()
        mock_wav_files = [Mock(), Mock()]
        mock_temp_dir.glob.return_value = mock_wav_files
        downloader.temp_dir = mock_temp_dir
        
        downloader.cleanup_temp_files()
        
        mock_temp_dir.glob.assert_called_once_with('*.wav')
        for mock_file in mock_wav_files:
            mock_file.unlink.assert_called_once()