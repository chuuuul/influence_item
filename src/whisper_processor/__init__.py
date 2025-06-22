"""
Whisper 음성 인식 모듈

YouTube 영상에서 음성을 추출하고 OpenAI Whisper 모델을 사용하여 
타임스탬프가 포함된 정확한 스크립트로 변환하는 모듈입니다.
"""

from .whisper_processor import WhisperProcessor
from .youtube_downloader import YouTubeDownloader

__all__ = ["WhisperProcessor", "YouTubeDownloader"]