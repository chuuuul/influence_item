"""
타겟 시간대 프레임 추출 모듈

Gemini 1차 분석에서 탐지된 후보 시간대만을 선별하여 정밀한 시각 분석을 수행합니다.
GPU 비용을 최소화하면서 분석 정확도를 극대화하는 핵심 최적화 전략입니다.
"""

import cv2
import numpy as np
import logging
import time
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from ..gemini_analyzer.models import (
    TargetTimeframe, ExtractedFrame, FrameAnalysisResult, 
    TargetFrameAnalysisResult, VideoMetadata, FrameExtractionConfig
)
from .ocr_processor import OCRProcessor
from .object_detector import ObjectDetector
from ..gpu_optimizer.gpu_optimizer import GPUOptimizer
from config import Config


class TargetFrameExtractor:
    """타겟 시간대 프레임 추출 및 분석 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        타겟 프레임 추출기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        
        # 컴포넌트 초기화
        self.gpu_optimizer = GPUOptimizer()
        self.ocr_processor = OCRProcessor(gpu_optimizer=self.gpu_optimizer)
        self.object_detector = ObjectDetector(gpu_optimizer=self.gpu_optimizer)
        
        # 기본 설정
        self.extraction_config = FrameExtractionConfig()
        
        self.logger.info("타겟 프레임 추출기 초기화 완료")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def extract_video_metadata(self, video_path: str) -> VideoMetadata:
        """
        영상 메타데이터 추출
        
        Args:
            video_path: 영상 파일 경로
            
        Returns:
            VideoMetadata: 영상 메타데이터
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"영상 파일을 열 수 없습니다: {video_path}")
            
            # 메타데이터 추출
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            # 코덱 정보 (선택적)
            fourcc = cap.get(cv2.CAP_PROP_FOURCC)
            codec = None
            if fourcc:
                codec = "".join([chr((int(fourcc) >> 8 * i) & 0xFF) for i in range(4)])
            
            cap.release()
            
            metadata = VideoMetadata(
                file_path=video_path,
                duration_seconds=duration,
                fps=fps,
                total_frames=total_frames,
                width=width,
                height=height,
                codec=codec
            )
            
            self.logger.info(f"영상 메타데이터 추출 완료: {duration:.1f}초, {fps:.1f}fps, {total_frames}프레임")
            return metadata
            
        except Exception as e:
            self.logger.error(f"영상 메타데이터 추출 실패: {e}")
            raise
    
    def assess_frame_quality(self, frame: np.ndarray, method: str = "laplacian") -> float:
        """
        프레임 품질 평가
        
        Args:
            frame: 프레임 이미지 (numpy array)
            method: 품질 평가 방법
            
        Returns:
            float: 품질 점수 (0-1)
        """
        try:
            if method == "laplacian":
                # Laplacian variance로 blur 정도 측정
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                # 정규화 (경험적 최대값 기준)
                quality_score = min(laplacian_var / 1000.0, 1.0)
                
            elif method == "sobel":
                # Sobel 엣지 강도로 선명도 측정
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                sobel_magnitude = np.sqrt(sobelx**2 + sobely**2)
                quality_score = min(np.mean(sobel_magnitude) / 100.0, 1.0)
                
            else:
                # 기본값: 평균 밝기 기반 단순 평가
                quality_score = np.mean(frame) / 255.0
            
            return float(quality_score)
            
        except Exception as e:
            self.logger.warning(f"프레임 품질 평가 실패: {e}")
            return 0.5  # 기본값 반환
    
    def extract_frames_from_timeframe(
        self, 
        video_path: str, 
        timeframe: TargetTimeframe,
        config: Optional[FrameExtractionConfig] = None
    ) -> List[ExtractedFrame]:
        """
        타겟 시간대에서 프레임 추출
        
        Args:
            video_path: 영상 파일 경로
            timeframe: 타겟 시간대
            config: 프레임 추출 설정
            
        Returns:
            List[ExtractedFrame]: 추출된 프레임 리스트
        """
        config = config or self.extraction_config
        extracted_frames = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"영상 파일을 열 수 없습니다: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 시간대를 프레임 인덱스로 변환
            start_frame = int(timeframe.start_time * fps)
            end_frame = int(timeframe.end_time * fps)
            
            # 샘플링 간격을 프레임 단위로 변환
            frame_interval = int(config.sampling_interval * fps)
            frame_interval = max(1, frame_interval)  # 최소 1프레임
            
            self.logger.info(
                f"프레임 추출 시작: {timeframe.start_time:.1f}s-{timeframe.end_time:.1f}s "
                f"(프레임 {start_frame}-{end_frame}, 간격: {frame_interval})"
            )
            
            frame_count = 0
            for frame_idx in range(start_frame, end_frame + 1, frame_interval):
                if frame_count >= config.max_frames_per_timeframe:
                    self.logger.info(f"최대 프레임 수 도달: {config.max_frames_per_timeframe}")
                    break
                
                # 프레임 위치로 이동
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if not ret:
                    self.logger.warning(f"프레임 {frame_idx} 읽기 실패")
                    continue
                
                # 프레임 품질 평가
                quality_score = self.assess_frame_quality(frame, config.quality_assessment_method)
                
                if quality_score < config.min_quality_threshold:
                    self.logger.debug(f"프레임 {frame_idx} 품질 부족: {quality_score:.3f}")
                    continue
                
                # 타임스탬프 계산
                timestamp = frame_idx / fps
                
                # 키프레임 여부 확인 (간단한 방법)
                is_keyframe = (frame_idx % int(fps)) == 0  # 1초마다를 키프레임으로 가정
                
                extracted_frame = ExtractedFrame(
                    timestamp=timestamp,
                    frame_index=frame_idx,
                    frame_data=frame.copy(),
                    quality_score=quality_score,
                    width=frame.shape[1],
                    height=frame.shape[0],
                    is_keyframe=is_keyframe
                )
                
                extracted_frames.append(extracted_frame)
                frame_count += 1
                
                self.logger.debug(f"프레임 추출 완료: {frame_idx} (품질: {quality_score:.3f})")
            
            cap.release()
            
            # 키프레임 우선 정렬 (설정에 따라)
            if config.prefer_keyframes and len(extracted_frames) > config.max_frames_per_timeframe:
                extracted_frames.sort(key=lambda f: (-f.is_keyframe, -f.quality_score))
                extracted_frames = extracted_frames[:config.max_frames_per_timeframe]
            
            self.logger.info(f"프레임 추출 완료: {len(extracted_frames)}개 프레임")
            return extracted_frames
            
        except Exception as e:
            self.logger.error(f"프레임 추출 실패: {e}")
            if 'cap' in locals():
                cap.release()
            raise
    
    def analyze_single_frame(self, frame: ExtractedFrame) -> FrameAnalysisResult:
        """
        단일 프레임 분석 수행
        
        Args:
            frame: 분석할 프레임
            
        Returns:
            FrameAnalysisResult: 프레임 분석 결과
        """
        start_time = time.time()
        
        try:
            # OCR 텍스트 인식
            ocr_results = []
            detected_texts = []
            
            if frame.frame_data is not None:
                try:
                    ocr_result = self.ocr_processor.process_image(frame.frame_data)
                    if ocr_result and 'texts' in ocr_result:
                        ocr_results = ocr_result['raw_results']
                        detected_texts = ocr_result['texts']
                except Exception as e:
                    self.logger.warning(f"OCR 처리 실패 (프레임 {frame.frame_index}): {e}")
            
            # 객체 인식
            object_detection_results = []
            detected_objects = []
            
            if frame.frame_data is not None:
                try:
                    detection_result = self.object_detector.detect_objects(frame.frame_data)
                    if detection_result and 'detections' in detection_result:
                        object_detection_results = detection_result['detections']
                        detected_objects = [d.get('class', 'unknown') for d in detection_result['detections']]
                except Exception as e:
                    self.logger.warning(f"객체 인식 실패 (프레임 {frame.frame_index}): {e}")
            
            processing_time = (time.time() - start_time) * 1000  # 밀리초
            
            result = FrameAnalysisResult(
                frame=frame,
                ocr_results=ocr_results,
                object_detection_results=object_detection_results,
                detected_texts=detected_texts,
                detected_objects=detected_objects,
                analysis_timestamp=time.time(),
                processing_time_ms=processing_time
            )
            
            self.logger.debug(
                f"프레임 분석 완료 (#{frame.frame_index}): "
                f"텍스트 {len(detected_texts)}개, 객체 {len(detected_objects)}개, "
                f"소요시간 {processing_time:.1f}ms"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"프레임 분석 실패 (#{frame.frame_index}): {e}")
            # 빈 결과 반환
            return FrameAnalysisResult(
                frame=frame,
                analysis_timestamp=time.time(),
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    def analyze_target_timeframe(
        self, 
        video_path: str, 
        timeframe: TargetTimeframe,
        config: Optional[FrameExtractionConfig] = None
    ) -> TargetFrameAnalysisResult:
        """
        타겟 시간대 전체 분석 수행
        
        Args:
            video_path: 영상 파일 경로
            timeframe: 분석할 타겟 시간대
            config: 프레임 추출 설정
            
        Returns:
            TargetFrameAnalysisResult: 전체 분석 결과
        """
        analysis_start = time.time()
        
        try:
            self.logger.info(
                f"타겟 시간대 분석 시작: {timeframe.start_time:.1f}s-{timeframe.end_time:.1f}s "
                f"(신뢰도: {timeframe.confidence_score:.3f})"
            )
            
            # 1. 프레임 추출
            extracted_frames = self.extract_frames_from_timeframe(video_path, timeframe, config)
            
            if not extracted_frames:
                raise ValueError("추출된 프레임이 없습니다")
            
            # 2. GPU 최적화 컨텍스트에서 배치 분석
            frame_results = []
            successful_analyses = 0
            
            with self.gpu_optimizer.optimized_context():
                for frame in extracted_frames:
                    try:
                        result = self.analyze_single_frame(frame)
                        frame_results.append(result)
                        successful_analyses += 1
                    except Exception as e:
                        self.logger.error(f"프레임 분석 중 오류: {e}")
                        continue
            
            # 3. 결과 집계
            all_texts = []
            all_objects = []
            
            for result in frame_results:
                all_texts.extend(result.detected_texts)
                all_objects.extend(result.detected_objects)
            
            # 중복 제거 및 정리
            summary_texts = list(set(filter(None, all_texts)))
            summary_objects = list(set(filter(None, all_objects)))
            
            # 4. 처리 통계
            analysis_end = time.time()
            total_processing_time = analysis_end - analysis_start
            
            processing_stats = {
                "total_frames_processed": len(frame_results),
                "successful_analyses": successful_analyses,
                "average_processing_time_per_frame": total_processing_time / len(extracted_frames) if extracted_frames else 0,
                "extraction_success_rate": len(extracted_frames) / max(1, (timeframe.end_time - timeframe.start_time)) if timeframe.end_time > timeframe.start_time else 0,
                "analysis_success_rate": successful_analyses / len(extracted_frames) if extracted_frames else 0
            }
            
            result = TargetFrameAnalysisResult(
                target_timeframe=timeframe,
                video_file_path=video_path,
                total_frames_extracted=len(extracted_frames),
                successful_analyses=successful_analyses,
                frame_results=frame_results,
                summary_texts=summary_texts,
                summary_objects=summary_objects,
                processing_stats=processing_stats,
                analysis_start_time=analysis_start,
                analysis_end_time=analysis_end,
                total_processing_time=total_processing_time
            )
            
            self.logger.info(
                f"타겟 시간대 분석 완료: "
                f"{len(extracted_frames)}개 프레임 처리, "
                f"{successful_analyses}개 성공, "
                f"텍스트 {len(summary_texts)}개, 객체 {len(summary_objects)}개 발견, "
                f"소요시간 {total_processing_time:.1f}초"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"타겟 시간대 분석 실패: {e}")
            raise
    
    def analyze_multiple_timeframes(
        self,
        video_path: str,
        timeframes: List[TargetTimeframe],
        config: Optional[FrameExtractionConfig] = None
    ) -> List[TargetFrameAnalysisResult]:
        """
        여러 타겟 시간대 분석 수행
        
        Args:
            video_path: 영상 파일 경로
            timeframes: 분석할 타겟 시간대 리스트
            config: 프레임 추출 설정
            
        Returns:
            List[TargetFrameAnalysisResult]: 각 시간대 분석 결과 리스트
        """
        try:
            # 비디오 메타데이터 사전 확인
            metadata = self.extract_video_metadata(video_path)
            
            self.logger.info(
                f"다중 시간대 분석 시작: {len(timeframes)}개 구간, "
                f"영상 길이 {metadata.duration_seconds:.1f}초"
            )
            
            results = []
            for i, timeframe in enumerate(timeframes, 1):
                try:
                    self.logger.info(f"구간 {i}/{len(timeframes)} 분석 중...")
                    result = self.analyze_target_timeframe(video_path, timeframe, config)
                    results.append(result)
                    
                except Exception as e:
                    self.logger.error(f"구간 {i} 분석 실패: {e}")
                    continue
            
            self.logger.info(f"다중 시간대 분석 완료: {len(results)}/{len(timeframes)}개 성공")
            return results
            
        except Exception as e:
            self.logger.error(f"다중 시간대 분석 실패: {e}")
            raise
    
    def get_analysis_info(self) -> Dict[str, Any]:
        """분석기 정보 반환"""
        return {
            "component": "TargetFrameExtractor",
            "version": "1.0.0",
            "gpu_optimizer_enabled": self.gpu_optimizer is not None,
            "ocr_processor_enabled": self.ocr_processor is not None,
            "object_detector_enabled": self.object_detector is not None,
            "extraction_config": self.extraction_config.dict(),
            "supported_video_formats": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
            "quality_assessment_methods": ["laplacian", "sobel", "brightness"]
        }