"""
Whisper 프로세서 단위 테스트
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.whisper_processor.whisper_processor import WhisperProcessor
from config.config import Config


class TestWhisperProcessor:
    """WhisperProcessor 테스트 클래스"""
    
    @pytest.fixture
    def mock_config(self):
        """테스트용 설정 모의객체"""
        config = Mock(spec=Config)
        config.WHISPER_MODEL_SIZE = "small"
        config.LOG_LEVEL = "INFO"
        config.get_temp_dir.return_value = Path("/tmp/test")
        return config
    
    @pytest.fixture
    def mock_whisper_model(self):
        """Whisper 모델 모의객체"""
        model = Mock()
        model.is_multilingual = True
        model.dims = Mock()
        model.dims.n_mels = 80
        model.dims.n_vocab = 51865
        model.dims.n_audio_ctx = 1500
        model.dims.n_audio_state = 512
        model.dims.n_text_ctx = 448
        model.dims.n_text_state = 512
        
        # transcribe 메서드 모의
        model.transcribe.return_value = {
            'segments': [
                {
                    'start': 0.0,
                    'end': 5.0,
                    'text': '안녕하세요.',
                    'confidence': 0.95
                },
                {
                    'start': 5.0,
                    'end': 10.0,
                    'text': '테스트 음성입니다.',
                    'confidence': 0.92
                }
            ]
        }
        return model
    
    @patch('src.whisper_processor.whisper_processor.whisper')
    def test_whisper_processor_init(self, mock_whisper, mock_config, mock_whisper_model):
        """WhisperProcessor 초기화 테스트"""
        mock_whisper.load_model.return_value = mock_whisper_model
        
        processor = WhisperProcessor(mock_config)
        
        assert processor.config == mock_config
        assert processor.model == mock_whisper_model
        mock_whisper.load_model.assert_called_once_with("small")
    
    @patch('src.whisper_processor.whisper_processor.whisper')
    def test_transcribe_short_audio(self, mock_whisper, mock_config, mock_whisper_model):
        """짧은 음성 인식 테스트"""
        mock_whisper.load_model.return_value = mock_whisper_model
        
        processor = WhisperProcessor(mock_config)
        
        # 짧은 음성 데이터 (5초)
        audio = np.random.random(5 * 16000).astype(np.float32)
        
        result = processor._transcribe_short_audio(audio, {'language': 'ko'})
        
        assert len(result) == 2
        assert result[0]['start'] == 0.0
        assert result[0]['end'] == 5.0
        assert result[0]['text'] == '안녕하세요.'
        assert result[0]['confidence'] == 0.95
    
    @patch('src.whisper_processor.whisper_processor.whisper')
    def test_format_segments_to_json(self, mock_whisper, mock_config, mock_whisper_model):
        """세그먼트 JSON 포맷팅 테스트"""
        mock_whisper.load_model.return_value = mock_whisper_model
        
        processor = WhisperProcessor(mock_config)
        
        segments = [
            {
                'start': 0.123456,
                'end': 5.789123,
                'text': '  안녕하세요.  ',
                'confidence': 0.956789
            },
            {
                'start': 5.789123,
                'end': 10.456789,
                'text': '',  # 빈 텍스트
                'confidence': 0.8
            }
        ]
        
        result = processor.format_segments_to_json(segments)
        
        # 빈 텍스트 세그먼트는 필터링됨
        assert len(result) == 1
        assert result[0]['start'] == 0.12  # 반올림
        assert result[0]['end'] == 5.79   # 반올림
        assert result[0]['text'] == '안녕하세요.'  # 공백 제거
        assert result[0]['confidence'] == 0.957  # 반올림
    
    @patch('src.whisper_processor.whisper_processor.whisper')
    def test_get_model_info(self, mock_whisper, mock_config, mock_whisper_model):
        """모델 정보 반환 테스트"""
        mock_whisper.load_model.return_value = mock_whisper_model
        
        processor = WhisperProcessor(mock_config)
        
        info = processor.get_model_info()
        
        assert info['model_size'] == "small"
        assert info['is_multilingual'] == True
        assert 'supported_languages' in info
        assert 'dims' in info
        assert info['dims']['n_mels'] == 80
    
    @patch('src.whisper_processor.whisper_processor.whisper')
    def test_transcribe_with_timestamps_long_audio(self, mock_whisper, mock_config, mock_whisper_model):
        """긴 음성 타임스탬프 인식 테스트"""
        mock_whisper.load_model.return_value = mock_whisper_model
        
        processor = WhisperProcessor(mock_config)
        
        # 35초 음성 (30초 초과)
        audio = np.random.random(35 * 16000).astype(np.float32)
        
        with patch.object(processor, '_transcribe_long_audio') as mock_long_transcribe:
            mock_long_transcribe.return_value = [
                {'start': 0.0, 'end': 5.0, 'text': '첫 번째 청크', 'confidence': 0.9},
                {'start': 30.0, 'end': 35.0, 'text': '두 번째 청크', 'confidence': 0.9}
            ]
            
            result = processor._transcribe_with_timestamps(audio)
            
            mock_long_transcribe.assert_called_once()
            assert len(result) == 2
            assert result[1]['start'] == 30.0  # 오프셋 적용 확인
    
    @patch('src.whisper_processor.whisper_processor.whisper')
    def test_model_load_failure(self, mock_whisper, mock_config):
        """모델 로드 실패 테스트"""
        mock_whisper.load_model.side_effect = Exception("모델 로드 실패")
        
        with pytest.raises(Exception) as exc_info:
            WhisperProcessor(mock_config)
        
        assert "모델 로드 실패" in str(exc_info.value)