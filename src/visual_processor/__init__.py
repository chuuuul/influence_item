"""
Visual Processor Package

EasyOCR 기반 텍스트 인식, YOLO 객체 탐지, 이미지 전처리 기능을 제공하는 패키지입니다.
"""

from .ocr_processor import OCRProcessor
from .object_detector import ObjectDetector
from .image_preprocessor import ImagePreprocessor

__all__ = [
    'OCRProcessor',
    'ObjectDetector', 
    'ImagePreprocessor'
]

__version__ = '1.0.0'