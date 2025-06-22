"""
Whisper 프로세서 통합 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from pathlib import Path

from src.whisper_processor import WhisperProcessor, YouTubeDownloader
from config import Config


class TestWhisperProcessorIntegration:
    """Whisper 프로세서 통합 테스트"""
    
    @pytest.fixture
    def mock_config(self):
        """테스트용 설정"""
        config = Mock(spec=Config)
        config.WHISPER_MODEL_SIZE = "small"
        config.LOG_LEVEL = "INFO"
        config.get_temp_dir.return_value = Path("/tmp/test")
        return config
    
    @pytest.mark.integration
    @patch('src.whisper_processor.whisper_processor.whisper')
    @patch('src.whisper_processor.youtube_downloader.yt_dlp')
    def test_full_pipeline_mock(self, mock_yt_dlp, mock_whisper, mock_config):
        """전체 파이프라인 통합 테스트 (모의객체 사용)"""
        # Whisper 모델 모의
        mock_model = Mock()
        mock_model.is_multilingual = True
        mock_model.transcribe.return_value = {
            'segments': [
                {
                    'start': 0.0,
                    'end': 5.0,
                    'text': '안녕하세요, 오늘 제품을 소개해드릴게요.',
                    'confidence': 0.95
                }
            ]
        }
        mock_whisper.load_model.return_value = mock_model
        
        # YouTube 다운로더 모의
        mock_audio_path = Path("/tmp/test/audio.wav")
        mock_ydl_instance = Mock()
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
        
        # 테스트 실행
        with patch.object(Path, 'exists', return_value=True):
            # YouTube 다운로더
            downloader = YouTubeDownloader(mock_config)
            audio_path = downloader.download_audio("https://youtube.com/watch?v=test")
            
            # Whisper 프로세서
            processor = WhisperProcessor(mock_config)
            
            # 음성 인식 (모의 처리)
            with patch.object(processor.preprocessor, 'load_audio') as mock_load_audio:
                import numpy as np
                # 실제 오디오 배열 형태의 Mock 데이터 생성
                mock_load_audio.return_value = np.zeros(16000)  # 1초간의 무음 데이터
                
                with patch.object(processor.preprocessor, 'validate_audio_quality', return_value=True):
                    # Whisper 모델의 transcribe 메서드도 모킹
                    mock_transcribe_result = {
                        'segments': [
                            {
                                'start': 0.0,
                                'end': 5.0,
                                'text': '안녕하세요, 오늘 제품을 소개해드릴게요.',
                                'confidence': 0.95
                            }
                        ]
                    }
                    with patch.object(processor.model, 'transcribe', return_value=mock_transcribe_result):
                        result = processor.transcribe_audio_file(audio_path)
        
        # 결과 검증
        assert result is not None
        assert len(result) == 1
        assert result[0]['text'] == '안녕하세요, 오늘 제품을 소개해드릴게요.'
        assert result[0]['start'] == 0.0
        assert result[0]['end'] == 5.0
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_performance_benchmark(self, mock_config):
        """성능 벤치마크 테스트"""
        import time
        import numpy as np
        
        # 모의 Whisper 모델 (빠른 처리를 위해)
        with patch('src.whisper_processor.whisper_processor.whisper') as mock_whisper:
            mock_model = Mock()
            mock_model.is_multilingual = True
            mock_model.transcribe.return_value = {
                'segments': [
                    {
                        'start': 0.0,
                        'end': 10.0,
                        'text': '성능 테스트용 텍스트',
                        'confidence': 0.9
                    }
                ]
            }
            mock_whisper.load_model.return_value = mock_model
            
            processor = WhisperProcessor(mock_config)
            
            # 10분 길이의 모의 음성 데이터
            audio_duration = 10 * 60  # 10분
            mock_audio = np.random.random(audio_duration * 16000).astype(np.float32)
            
            # 성능 측정
            start_time = time.time()
            
            with patch.object(processor.preprocessor, 'load_audio', return_value=mock_audio):
                with patch.object(processor.preprocessor, 'validate_audio_quality', return_value=True):
                    # 실제 처리 시간을 시뮬레이션
                    time.sleep(0.5)  # 0.5초 처리 시간 시뮬레이션
                    
                    result = processor._transcribe_with_timestamps(mock_audio)
            
            processing_time = time.time() - start_time
            
            # 성능 요구사항 검증
            assert processing_time < 5.0  # 10분 영상이 5초 이내 처리 (모의 환경)
            assert result is not None
            
    @pytest.mark.integration
    def test_error_handling_integration(self, mock_config):
        """에러 핸들링 통합 테스트"""
        # 네트워크 오류 시뮬레이션
        with patch('src.whisper_processor.youtube_downloader.yt_dlp') as mock_yt_dlp:
            mock_ydl_instance = Mock()
            mock_ydl_instance.download.side_effect = Exception("네트워크 오류")
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
            
            downloader = YouTubeDownloader(mock_config)
            result = downloader.download_audio("https://youtube.com/watch?v=invalid")
            
            # 네트워크 오류 시 None 반환 확인
            assert result is None
        
        # Whisper 모델 로드 실패 시뮬레이션
        with patch('src.whisper_processor.whisper_processor.whisper') as mock_whisper:
            mock_whisper.load_model.side_effect = Exception("모델 로드 실패")
            
            with pytest.raises(Exception) as exc_info:
                WhisperProcessor(mock_config)
            
            assert "모델 로드 실패" in str(exc_info.value)
    
    @pytest.mark.integration
    def test_memory_usage(self, mock_config):
        """메모리 사용량 테스트"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Whisper 프로세서 초기화 (모의)
        with patch('src.whisper_processor.whisper_processor.whisper') as mock_whisper:
            mock_model = Mock()
            mock_whisper.load_model.return_value = mock_model
            
            processor = WhisperProcessor(mock_config)
            
            # 여러 번의 처리 시뮬레이션
            for _ in range(5):
                with patch.object(processor.preprocessor, 'load_audio') as mock_load_audio:
                    mock_load_audio.return_value = Mock()
                    
                    with patch.object(processor.preprocessor, 'validate_audio_quality', return_value=True):
                        processor._transcribe_with_timestamps(Mock())
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # 메모리 증가량이 2GB 이하인지 확인
        assert memory_increase < 2048  # 2GB
        
    def test_concurrent_processing(self, mock_config):
        """동시 처리 테스트"""
        import concurrent.futures
        
        # 여러 YouTube 다운로더 동시 실행
        with patch('src.whisper_processor.youtube_downloader.yt_dlp') as mock_yt_dlp:
            mock_ydl_instance = Mock()
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
            
            urls = [
                "https://youtube.com/watch?v=test1",
                "https://youtube.com/watch?v=test2",
                "https://youtube.com/watch?v=test3",
            ]
            
            def download_audio(url):
                downloader = YouTubeDownloader(mock_config)
                return downloader.get_video_info(url)
            
            # 동시 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(download_audio, url) for url in urls]
                results = [future.result() for future in futures]
            
            # 모든 요청이 처리되었는지 확인
            assert len(results) == 3
            assert mock_ydl_instance.extract_info.call_count == 3