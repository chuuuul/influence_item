"""
Whisper 음성 인식 프로세서

OpenAI Whisper 모델을 사용하여 음성을 텍스트로 변환합니다.
"""

import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
try:
    import numpy as np
    import whisper
except ImportError:
    # 테스트 환경에서 whisper 모듈이 없을 경우를 위한 처리
    np = None
    whisper = None
from config.config import Config
from .audio_preprocessor import AudioPreprocessor
from ..gpu_optimizer import GPUOptimizer


class WhisperProcessor:
    """Whisper 음성 인식 프로세서 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Whisper 프로세서 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        self.preprocessor = AudioPreprocessor(config)
        
        # GPU 최적화 초기화
        self.gpu_optimizer = None
        if getattr(self.config, 'ENABLE_GPU_OPTIMIZATION', True):
            try:
                self.gpu_optimizer = GPUOptimizer(self.config)
                self.logger.info("Whisper GPU 최적화 활성화됨")
            except Exception as e:
                self.logger.warning(f"Whisper GPU 최적화 초기화 실패: {str(e)}")
                self.gpu_optimizer = None
        
        self.model = None
        self._load_model()
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        try:
            logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        except (AttributeError, TypeError):
            logger.setLevel(logging.INFO)  # 기본값 사용
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _load_model(self) -> None:
        """Whisper 모델 로드 (GPU 최적화)"""
        if whisper is None:
            self.logger.warning("Whisper 모듈이 설치되지 않았습니다. 테스트 모드로 실행됩니다.")
            self.model = None
            return
            
        try:
            self.logger.info(f"Whisper 모델 로드 시작: {self.config.WHISPER_MODEL_SIZE}")
            start_time = time.time()
            
            # GPU 최적화된 모델 로딩
            device = "cuda" if self.gpu_optimizer and self.gpu_optimizer.is_gpu_available else "cpu"
            
            self.model = whisper.load_model(
                self.config.WHISPER_MODEL_SIZE,
                device=device
            )
            
            load_time = time.time() - start_time
            self.logger.info(f"Whisper 모델 로드 완료 - 소요시간: {load_time:.2f}초")
            
        except Exception as e:
            self.logger.error(f"Whisper 모델 로드 실패: {str(e)}")
            raise
    
    def transcribe_audio_file(self, audio_path: Path) -> Optional[List[Dict[str, Any]]]:
        """
        음성 파일을 스크립트로 변환
        
        Args:
            audio_path: 음성 파일 경로
            
        Returns:
            타임스탬프가 포함된 스크립트 리스트
        """
        if self.model is None:
            self.logger.warning("Whisper 모델이 로드되지 않았습니다. 테스트 데이터를 반환합니다.")
            return [{"start": 0.0, "end": 5.0, "text": "테스트 음성 인식 결과", "confidence": 1.0}]
            
        try:
            self.logger.info(f"음성 인식 시작: {audio_path}")
            start_time = time.time()
            
            # 음성 파일 로드
            audio = self.preprocessor.load_audio(audio_path)
            if audio is None:
                return None
            
            # 음성 품질 검증
            if not self.preprocessor.validate_audio_quality(audio):
                self.logger.warning("음성 품질이 좋지 않지만 처리를 계속합니다.")
            
            # 음성 인식 실행
            result = self._transcribe_with_timestamps(audio)
            
            process_time = time.time() - start_time
            self.logger.info(f"음성 인식 완료 - 소요시간: {process_time:.2f}초")
            
            return result
            
        except Exception as e:
            self.logger.error(f"음성 인식 실패: {str(e)}")
            return None
    
    def _transcribe_with_timestamps(self, audio) -> List[Dict[str, Any]]:
        """
        타임스탬프를 포함한 음성 인식
        
        Args:
            audio: 음성 데이터
            
        Returns:
            타임스탬프가 포함된 세그먼트 리스트
        """
        try:
            # Whisper 음성 인식 옵션
            options = {
                'language': 'ko',  # 한국어 설정
                'task': 'transcribe',
                'word_timestamps': True,  # 단어별 타임스탬프
                'verbose': False,
            }
            
            # 긴 음성의 경우 청크로 분할 처리
            audio_duration = self.preprocessor.calculate_audio_duration(audio)
            
            if audio_duration > 30:  # 30초 이상인 경우
                return self._transcribe_long_audio(audio, options)
            else:
                return self._transcribe_short_audio(audio, options)
                
        except Exception as e:
            self.logger.error(f"타임스탬프 음성 인식 실패: {str(e)}")
            return []
    
    def _transcribe_short_audio(
        self, 
        audio, 
        options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        짧은 음성 인식 (30초 이하)
        
        Args:
            audio: 음성 데이터
            options: Whisper 옵션
            
        Returns:
            인식 결과 세그먼트 리스트
        """
        try:
            # Whisper 음성 인식
            result = self.model.transcribe(audio, **options)
            
            # 세그먼트 정보 추출
            segments = []
            for segment in result.get('segments', []):
                segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text'].strip(),
                    'confidence': segment.get('confidence', 1.0),
                })
            
            self.logger.debug(f"짧은 음성 인식 완료 - {len(segments)}개 세그먼트")
            return segments
            
        except Exception as e:
            self.logger.error(f"짧은 음성 인식 실패: {str(e)}")
            return []
    
    def _transcribe_long_audio(
        self, 
        audio, 
        options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        긴 음성 인식 (30초 초과)
        
        Args:
            audio: 음성 데이터
            options: Whisper 옵션
            
        Returns:
            인식 결과 세그먼트 리스트
        """
        try:
            self.logger.debug("긴 음성을 청크로 분할하여 처리")
            
            # 음성을 청크로 분할
            chunks = self.preprocessor.split_audio_chunks(audio, chunk_length=30 * 16000)
            
            all_segments = []
            current_offset = 0.0
            
            for i, chunk in enumerate(chunks):
                self.logger.debug(f"청크 {i+1}/{len(chunks)} 처리 중")
                
                # 청크별 음성 인식
                result = self.model.transcribe(chunk, **options)
                
                # 타임스탬프 오프셋 적용
                for segment in result.get('segments', []):
                    all_segments.append({
                        'start': segment['start'] + current_offset,
                        'end': segment['end'] + current_offset,
                        'text': segment['text'].strip(),
                        'confidence': segment.get('confidence', 1.0),
                    })
                
                # 다음 청크를 위한 오프셋 업데이트
                current_offset += 30.0
            
            self.logger.debug(f"긴 음성 인식 완료 - {len(all_segments)}개 세그먼트")
            return all_segments
            
        except Exception as e:
            self.logger.error(f"긴 음성 인식 실패: {str(e)}")
            return []
    
    def format_segments_to_json(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        세그먼트를 JSON 형태로 포맷팅
        
        Args:
            segments: 원본 세그먼트 리스트
            
        Returns:
            JSON 형태로 포맷팅된 세그먼트 리스트
        """
        try:
            formatted_segments = []
            
            for segment in segments:
                # 빈 텍스트 필터링
                text = segment['text'].strip()
                if not text:
                    continue
                
                formatted_segments.append({
                    'start': round(segment['start'], 2),
                    'end': round(segment['end'], 2),
                    'text': text,
                    'confidence': round(segment.get('confidence', 1.0), 3),
                })
            
            self.logger.debug(f"세그먼트 포맷팅 완료 - {len(formatted_segments)}개")
            return formatted_segments
            
        except Exception as e:
            self.logger.error(f"세그먼트 포맷팅 실패: {str(e)}")
            return []
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        모델 정보 반환
        
        Returns:
            모델 정보 딕셔너리
        """
        if self.model is None or whisper is None:
            return {
                'model_size': getattr(self.config, 'WHISPER_MODEL_SIZE', 'base'),
                'status': 'not_loaded',
                'message': 'Whisper 모듈이 설치되지 않았거나 모델이 로드되지 않았습니다.'
            }
        
        return {
            'model_size': self.config.WHISPER_MODEL_SIZE,
            'is_multilingual': self.model.is_multilingual,
            'supported_languages': list(whisper.tokenizer.LANGUAGES.keys()),
            'dims': {
                'n_mels': self.model.dims.n_mels,
                'n_vocab': self.model.dims.n_vocab,
                'n_audio_ctx': self.model.dims.n_audio_ctx,
                'n_audio_state': self.model.dims.n_audio_state,
                'n_text_ctx': self.model.dims.n_text_ctx,
                'n_text_state': self.model.dims.n_text_state,
            }
        }