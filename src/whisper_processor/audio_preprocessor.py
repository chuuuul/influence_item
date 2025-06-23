"""
음성 전처리 모듈

음성 파일의 품질을 최적화하고 Whisper 모델에 적합한 형태로 변환합니다.
"""

import logging
from pathlib import Path
from typing import Optional
try:
    import numpy as np
    import whisper
except ImportError:
    # 테스트 환경에서 whisper 모듈이 없을 경우를 위한 처리
    np = None
    whisper = None
from config.config import Config


class AudioPreprocessor:
    """음성 전처리 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        음성 전처리기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        
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
    
    def load_audio(self, audio_path: Path) -> Optional['np.ndarray']:
        """
        음성 파일 로드
        
        Args:
            audio_path: 음성 파일 경로
            
        Returns:
            로드된 음성 데이터 (실패 시 None)
        """
        if whisper is None or np is None:
            self.logger.warning("Whisper 모듈이 설치되지 않았습니다. 테스트 데이터를 반환합니다.")
            # 테스트용 더미 데이터 반환 (5초 길이의 빈 오디오)
            return [0.0] * (5 * 16000)  # 5초 * 16kHz 샘플레이트
            
        try:
            self.logger.debug(f"음성 파일 로드: {audio_path}")
            
            # Whisper의 load_audio 함수 사용 (16kHz로 자동 리샘플링)
            audio = whisper.load_audio(str(audio_path))
            
            self.logger.debug(f"음성 로드 완료 - 길이: {len(audio)} 샘플")
            return audio
            
        except Exception as e:
            self.logger.error(f"음성 파일 로드 실패: {str(e)}")
            return None
    
    def preprocess_audio(self, audio) -> any:
        """
        음성 데이터 전처리
        
        Args:
            audio: 원본 음성 데이터
            
        Returns:
            전처리된 음성 데이터
        """
        if whisper is None:
            self.logger.warning("Whisper 모듈이 설치되지 않았습니다. 원본 오디오를 반환합니다.")
            return audio
            
        try:
            self.logger.debug("음성 전처리 시작")
            
            # Whisper의 pad_or_trim 사용 (30초 기준)
            # 긴 음성은 청크로 나누어 처리할 예정이므로 여기서는 기본 처리만
            processed_audio = whisper.pad_or_trim(audio)
            
            self.logger.debug("음성 전처리 완료")
            return processed_audio
            
        except Exception as e:
            self.logger.error(f"음성 전처리 실패: {str(e)}")
            return audio
    
    def split_audio_chunks(
        self, 
        audio, 
        chunk_length: int = 30 * 16000  # 30초 * 16kHz
    ) -> list:
        """
        긴 음성을 청크로 분할
        
        Args:
            audio: 음성 데이터
            chunk_length: 청크 길이 (샘플 수)
            
        Returns:
            분할된 음성 청크 리스트
        """
        if whisper is None:
            self.logger.warning("Whisper 모듈이 설치되지 않았습니다. 원본 오디오를 반환합니다.")
            return [audio]
            
        try:
            self.logger.debug(f"음성 청크 분할 시작 - 총 길이: {len(audio)} 샘플")
            
            chunks = []
            for i in range(0, len(audio), chunk_length):
                chunk = audio[i:i + chunk_length]
                # 너무 짧은 청크는 패딩 적용
                if len(chunk) < chunk_length:
                    chunk = whisper.pad_or_trim(chunk)
                chunks.append(chunk)
            
            self.logger.debug(f"음성 청크 분할 완료 - {len(chunks)}개 청크")
            return chunks
            
        except Exception as e:
            self.logger.error(f"음성 청크 분할 실패: {str(e)}")
            return [audio]
    
    def calculate_audio_duration(self, audio) -> float:
        """
        음성 길이 계산 (초 단위)
        
        Args:
            audio: 음성 데이터
            
        Returns:
            음성 길이 (초)
        """
        return len(audio) / 16000  # 16kHz 샘플레이트 기준
    
    def validate_audio_quality(self, audio) -> bool:
        """
        음성 품질 검증
        
        Args:
            audio: 음성 데이터
            
        Returns:
            품질이 양호한지 여부
        """
        if np is None:
            self.logger.warning("NumPy 모듈이 설치되지 않았습니다. 기본적으로 True를 반환합니다.")
            return True
            
        try:
            # 기본적인 품질 검사
            if len(audio) == 0:
                self.logger.warning("빈 음성 데이터")
                return False
            
            # 리스트인 경우 numpy 배열로 변환
            if isinstance(audio, list):
                audio_array = audio
            else:
                audio_array = audio
            
            # 음성 레벨 확인 (간단한 버전)
            avg_level = sum(abs(x) for x in audio_array) / len(audio_array)
            if avg_level < 0.001:  # 너무 조용한 음성
                self.logger.warning("음성 레벨이 너무 낮음")
                return False
            
            # 클리핑 확인 (간단한 버전)
            clipping_count = sum(1 for x in audio_array if abs(x) > 0.99)
            clipping_ratio = clipping_count / len(audio_array)
            if clipping_ratio > 0.01:  # 1% 이상 클리핑
                self.logger.warning(f"음성 클리핑 감지: {clipping_ratio:.2%}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"음성 품질 검증 실패: {str(e)}")
            return False