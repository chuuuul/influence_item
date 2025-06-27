"""
시각 분석 모듈 - OCR 및 객체 인식
PRD v1.0 - AI 2-Pass 파이프라인의 시각 분석 컴포넌트
"""

import os
import cv2
import numpy as np
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import tempfile
import time
import json
from datetime import datetime

# OCR 및 객체 인식 imports
import easyocr
import torch
from PIL import Image
import subprocess

logger = logging.getLogger(__name__)


class OCRProcessor:
    """EasyOCR 기반 텍스트 인식 처리기"""
    
    def __init__(self, languages: List[str] = None, gpu: bool = True):
        """
        Args:
            languages: 지원할 언어 목록 (기본: ['ko', 'en'])
            gpu: GPU 사용 여부
        """
        self.languages = languages or ['ko', 'en']
        self.gpu = gpu and torch.cuda.is_available()
        self.reader = None
        self._init_reader()
    
    def _init_reader(self):
        """EasyOCR 리더 초기화"""
        try:
            logger.info(f"EasyOCR 초기화 중... (언어: {self.languages}, GPU: {self.gpu})")
            self.reader = easyocr.Reader(
                self.languages,
                gpu=self.gpu,
                verbose=False
            )
            logger.info("EasyOCR 초기화 완료")
        except Exception as e:
            logger.error(f"EasyOCR 초기화 실패: {e}")
            # GPU 실패시 CPU로 재시도
            if self.gpu:
                logger.info("GPU 실패, CPU로 재시도...")
                try:
                    self.reader = easyocr.Reader(
                        self.languages,
                        gpu=False,
                        verbose=False
                    )
                    self.gpu = False
                    logger.info("EasyOCR CPU 모드로 초기화 완료")
                except Exception as e2:
                    logger.error(f"EasyOCR CPU 초기화도 실패: {e2}")
    
    def extract_text_from_image(self, image_path: str) -> List[Dict[str, Any]]:
        """
        이미지에서 텍스트 추출
        
        Args:
            image_path: 이미지 파일 경로
            
        Returns:
            텍스트 인식 결과 리스트
        """
        if not self.reader:
            logger.error("EasyOCR이 초기화되지 않았습니다.")
            return []
        
        try:
            # 이미지 읽기 및 전처리
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"이미지를 읽을 수 없습니다: {image_path}")
                return []
            
            # OCR 실행
            results = self.reader.readtext(image, detail=1)
            
            # 결과 정리
            ocr_results = []
            for bbox, text, confidence in results:
                if confidence > 0.5:  # 신뢰도 임계값
                    ocr_results.append({
                        'text': text.strip(),
                        'confidence': round(confidence, 3),
                        'bbox': {
                            'x1': int(bbox[0][0]),
                            'y1': int(bbox[0][1]),
                            'x2': int(bbox[2][0]),
                            'y2': int(bbox[2][1])
                        },
                        'center': {
                            'x': int((bbox[0][0] + bbox[2][0]) / 2),
                            'y': int((bbox[0][1] + bbox[2][1]) / 2)
                        }
                    })
            
            logger.info(f"OCR 완료: {len(ocr_results)}개 텍스트 영역 발견")
            return ocr_results
            
        except Exception as e:
            logger.error(f"OCR 처리 실패: {e}")
            return []
    
    def extract_text_from_frames(
        self,
        frame_paths: List[str],
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        여러 프레임에서 텍스트 추출 및 병합
        
        Args:
            frame_paths: 프레임 이미지 경로 리스트
            min_confidence: 최소 신뢰도
            
        Returns:
            통합된 텍스트 결과
        """
        all_texts = []
        text_frequency = {}
        
        for frame_path in frame_paths:
            frame_results = self.extract_text_from_image(frame_path)
            
            for result in frame_results:
                if result['confidence'] >= min_confidence:
                    text = result['text']
                    if text in text_frequency:
                        text_frequency[text]['count'] += 1
                        text_frequency[text]['avg_confidence'] = (
                            text_frequency[text]['avg_confidence'] + result['confidence']
                        ) / 2
                    else:
                        text_frequency[text] = {
                            'count': 1,
                            'avg_confidence': result['confidence'],
                            'bbox': result['bbox'],
                            'center': result['center']
                        }
        
        # 빈도와 신뢰도 기반으로 정렬
        sorted_texts = sorted(
            text_frequency.items(),
            key=lambda x: (x[1]['count'], x[1]['avg_confidence']),
            reverse=True
        )
        
        # 결과 정리
        for text, info in sorted_texts:
            all_texts.append({
                'text': text,
                'frequency': info['count'],
                'avg_confidence': round(info['avg_confidence'], 3),
                'bbox': info['bbox'],
                'center': info['center']
            })
        
        return all_texts


class VideoFrameExtractor:
    """비디오에서 프레임 추출"""
    
    @staticmethod
    def extract_frames_from_video(
        video_path: str,
        start_time: float,
        end_time: float,
        frame_interval: float = 1.0,
        output_dir: str = None
    ) -> List[str]:
        """
        비디오에서 특정 구간의 프레임 추출
        
        Args:
            video_path: 비디오 파일 경로
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초)
            frame_interval: 프레임 추출 간격 (초)
            output_dir: 출력 디렉토리
            
        Returns:
            추출된 프레임 파일 경로 리스트
        """
        if not output_dir:
            output_dir = tempfile.mkdtemp()
        else:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        frame_paths = []
        
        try:
            # OpenCV로 비디오 열기
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"비디오를 열 수 없습니다: {video_path}")
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            start_frame = int(start_time * fps)
            end_frame = int(end_time * fps)
            interval_frames = int(frame_interval * fps)
            
            # 시작 프레임으로 이동
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            frame_count = start_frame
            while frame_count <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 지정된 간격마다 프레임 저장
                if (frame_count - start_frame) % interval_frames == 0:
                    timestamp = frame_count / fps
                    frame_filename = f"frame_{timestamp:.1f}s.jpg"
                    frame_path = os.path.join(output_dir, frame_filename)
                    
                    cv2.imwrite(frame_path, frame)
                    frame_paths.append(frame_path)
                    
                    logger.debug(f"프레임 저장: {frame_path}")
                
                frame_count += 1
            
            cap.release()
            logger.info(f"프레임 추출 완료: {len(frame_paths)}개")
            
        except Exception as e:
            logger.error(f"프레임 추출 실패: {e}")
        
        return frame_paths
    
    @staticmethod
    def download_youtube_segment(
        video_url: str,
        start_time: float,
        end_time: float,
        output_path: str = None
    ) -> Optional[str]:
        """
        YouTube 영상의 특정 구간 다운로드 (yt-dlp + ffmpeg 사용)
        
        Args:
            video_url: YouTube 영상 URL
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초)
            output_path: 출력 파일 경로
            
        Returns:
            다운로드된 파일 경로
        """
        if not output_path:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"segment_{start_time}_{end_time}.mp4")
        
        try:
            # yt-dlp와 ffmpeg를 사용한 구간 다운로드
            cmd = [
                'yt-dlp',
                '--external-downloader', 'ffmpeg',
                '--external-downloader-args',
                f'-ss {start_time} -t {end_time - start_time}',
                '-f', 'best[height<=720]',
                '-o', output_path,
                video_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"YouTube 구간 다운로드 완료: {output_path}")
                return output_path
            else:
                logger.error(f"YouTube 다운로드 실패: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"YouTube 다운로드 오류: {e}")
            return None


class VisualAnalyzer:
    """통합 시각 분석기"""
    
    def __init__(self, languages: List[str] = None, gpu: bool = True):
        """
        Args:
            languages: OCR 지원 언어
            gpu: GPU 사용 여부
        """
        self.ocr = OCRProcessor(languages, gpu)
        self.frame_extractor = VideoFrameExtractor()
    
    def analyze_video_segment(
        self,
        video_source: str,
        start_time: float,
        end_time: float,
        is_youtube_url: bool = False
    ) -> Dict[str, Any]:
        """
        비디오 구간의 시각적 분석 수행
        
        Args:
            video_source: 비디오 파일 경로 또는 YouTube URL
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초)
            is_youtube_url: YouTube URL 여부
            
        Returns:
            시각 분석 결과
        """
        try:
            # 임시 디렉토리 생성
            temp_dir = tempfile.mkdtemp()
            
            # YouTube URL인 경우 구간 다운로드
            if is_youtube_url:
                video_path = self.frame_extractor.download_youtube_segment(
                    video_source, start_time, end_time,
                    os.path.join(temp_dir, "segment.mp4")
                )
                if not video_path:
                    return self._empty_result()
                
                # 다운로드된 구간에서는 전체 길이로 프레임 추출
                segment_start = 0
                segment_end = end_time - start_time
            else:
                video_path = video_source
                segment_start = start_time
                segment_end = end_time
            
            # 프레임 추출 (1초 간격)
            frame_paths = self.frame_extractor.extract_frames_from_video(
                video_path,
                segment_start,
                segment_end,
                frame_interval=1.0,
                output_dir=os.path.join(temp_dir, "frames")
            )
            
            if not frame_paths:
                logger.warning("추출된 프레임이 없습니다.")
                return self._empty_result()
            
            # OCR 분석
            ocr_results = self.ocr.extract_text_from_frames(frame_paths)
            
            # 객체 인식 (현재는 더미 구현)
            object_results = self._analyze_objects(frame_paths)
            
            # 결과 정리
            analysis_result = {
                'ocr_text': [result['text'] for result in ocr_results],
                'text_regions': ocr_results,
                'objects': object_results,
                'frames_analyzed': len(frame_paths),
                'analysis_timestamp': datetime.now().isoformat(),
                'temp_dir': temp_dir  # 정리용
            }
            
            logger.info(f"시각 분석 완료: OCR {len(ocr_results)}개, 객체 {len(object_results)}개")
            return analysis_result
            
        except Exception as e:
            logger.error(f"시각 분석 실패: {e}")
            return self._empty_result()
    
    def _analyze_objects(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """
        객체 인식 분석 (현재는 더미 구현)
        TODO: YOLOv8 또는 다른 객체 인식 모델 통합
        """
        # 더미 객체 결과
        dummy_objects = [
            {
                'class': 'product',
                'confidence': 0.8,
                'bbox': {'x1': 100, 'y1': 50, 'x2': 300, 'y2': 200},
                'description': '제품으로 추정되는 객체'
            }
        ]
        
        logger.debug(f"객체 인식 분석 (더미): {len(frame_paths)}개 프레임")
        return dummy_objects
    
    def _empty_result(self) -> Dict[str, Any]:
        """빈 분석 결과 반환"""
        return {
            'ocr_text': [],
            'text_regions': [],
            'objects': [],
            'frames_analyzed': 0,
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def cleanup_temp_files(self, analysis_result: Dict[str, Any]):
        """임시 파일 정리"""
        try:
            temp_dir = analysis_result.get('temp_dir')
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
                logger.debug(f"임시 파일 정리 완료: {temp_dir}")
        except Exception as e:
            logger.warning(f"임시 파일 정리 실패: {e}")


def create_visual_analyzer(languages: List[str] = None, gpu: bool = True) -> VisualAnalyzer:
    """시각 분석기 생성"""
    return VisualAnalyzer(languages, gpu)


if __name__ == "__main__":
    # 테스트 코드
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # 시각 분석기 테스트
    analyzer = create_visual_analyzer()
    
    print("시각 분석 모듈이 준비되었습니다.")
    print("실제 영상으로 테스트하려면 analyze_video_segment() 메소드를 사용하세요.")
    
    # 더미 이미지로 OCR 테스트 (있다면)
    test_image = "test_image.jpg"
    if os.path.exists(test_image):
        ocr_results = analyzer.ocr.extract_text_from_image(test_image)
        print(f"OCR 테스트 결과: {len(ocr_results)}개 텍스트 발견")