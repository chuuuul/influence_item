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
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageEnhance

from ..gemini_analyzer.models import (
    TargetTimeframe, ExtractedFrame, FrameAnalysisResult, 
    TargetFrameAnalysisResult, VideoMetadata, FrameExtractionConfig
)
from .ocr_processor import OCRProcessor
from .object_detector import ObjectDetector
from ..gpu_optimizer.gpu_optimizer import GPUOptimizer
from config.config import Config


class ProductImageExtractor:
    """제품 이미지 추출 및 품질 평가 클래스"""
    
    def __init__(self, output_dir: str = "temp/product_images"):
        """
        제품 이미지 추출기 초기화
        
        Args:
            output_dir: 이미지 저장 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 썸네일 디렉토리들
        self.thumbnail_150_dir = self.output_dir / "thumbnails_150"
        self.thumbnail_300_dir = self.output_dir / "thumbnails_300"
        self.thumbnail_150_dir.mkdir(exist_ok=True)
        self.thumbnail_300_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    def _calculate_frame_hash(self, frame: np.ndarray) -> str:
        """프레임 해시 계산 (중복 방지용)"""
        frame_bytes = cv2.imencode('.jpg', frame)[1].tobytes()
        return hashlib.md5(frame_bytes).hexdigest()
    
    def _assess_image_quality(self, frame: np.ndarray) -> Dict[str, float]:
        """
        이미지 품질 평가 (다중 기준)
        
        Args:
            frame: 평가할 프레임
            
        Returns:
            Dict[str, float]: 품질 점수들
        """
        try:
            # 1. 선명도 평가 (Laplacian variance)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(laplacian_var / 1000.0, 1.0)
            
            # 2. 크기 평가 (해상도)
            height, width = frame.shape[:2]
            size_score = min((width * height) / (1920 * 1080), 1.0)  # Full HD 기준
            
            # 3. 밝기 평가
            brightness = np.mean(gray)
            brightness_score = 1.0 - abs(brightness - 128) / 128  # 중간 밝기가 최적
            
            # 4. 대비 평가
            contrast_score = np.std(gray) / 128.0
            contrast_score = min(contrast_score, 1.0)
            
            return {
                "sharpness": float(sharpness_score),
                "size": float(size_score),
                "brightness": float(brightness_score),
                "contrast": float(contrast_score)
            }
            
        except Exception as e:
            self.logger.warning(f"이미지 품질 평가 실패: {e}")
            return {
                "sharpness": 0.5,
                "size": 0.5,
                "brightness": 0.5,
                "contrast": 0.5
            }
    
    def _calculate_composite_score(self, quality_scores: Dict[str, float], object_confidence: float = 0.0) -> float:
        """
        종합 품질 점수 계산
        
        Args:
            quality_scores: 개별 품질 점수들
            object_confidence: 객체 탐지 신뢰도
            
        Returns:
            float: 종합 품질 점수 (0-1)
        """
        # 가중치: 선명도 40%, 크기 30%, 객체 탐지 30%
        weighted_score = (
            quality_scores["sharpness"] * 0.4 +
            quality_scores["size"] * 0.3 +
            object_confidence * 0.3
        )
        
        # 밝기와 대비도 보너스/페널티 (최대 ±10%)
        brightness_bonus = (quality_scores["brightness"] - 0.5) * 0.1
        contrast_bonus = (quality_scores["contrast"] - 0.5) * 0.1
        
        final_score = weighted_score + brightness_bonus + contrast_bonus
        return max(0.0, min(1.0, final_score))
    
    def _create_thumbnail(self, image: np.ndarray, size: int) -> np.ndarray:
        """썸네일 생성"""
        try:
            # OpenCV to PIL
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            
            # 종횡비 유지하며 리사이즈
            pil_image.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # PIL to OpenCV
            thumbnail_rgb = np.array(pil_image)
            thumbnail_bgr = cv2.cvtColor(thumbnail_rgb, cv2.COLOR_RGB2BGR)
            
            return thumbnail_bgr
            
        except Exception as e:
            self.logger.error(f"썸네일 생성 실패: {e}")
            # 단순 리사이즈로 폴백
            height, width = image.shape[:2]
            scale = size / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
    
    def save_product_image(
        self, 
        frame: np.ndarray, 
        metadata: Dict[str, Any], 
        object_confidence: float = 0.0
    ) -> Dict[str, Any]:
        """
        제품 이미지 저장 및 메타데이터 생성
        
        Args:
            frame: 저장할 프레임
            metadata: 이미지 메타데이터 (timestamp, timeframe_info 등)
            object_confidence: 객체 탐지 신뢰도
            
        Returns:
            Dict[str, Any]: 저장된 이미지 정보
        """
        try:
            # 해시 기반 파일명 생성
            frame_hash = self._calculate_frame_hash(frame)
            
            # 품질 평가
            quality_scores = self._assess_image_quality(frame)
            composite_score = self._calculate_composite_score(quality_scores, object_confidence)
            
            # 파일 경로 설정
            original_path = self.output_dir / f"{frame_hash}.jpg"
            thumbnail_150_path = self.thumbnail_150_dir / f"{frame_hash}_150.jpg"
            thumbnail_300_path = self.thumbnail_300_dir / f"{frame_hash}_300.jpg"
            metadata_path = self.output_dir / f"{frame_hash}.json"
            
            # 이미 존재하는 파일인지 확인
            if original_path.exists():
                self.logger.debug(f"이미지 이미 존재: {frame_hash}")
                # 기존 메타데이터 로드
                if metadata_path.exists():
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        existing_metadata = json.load(f)
                    return existing_metadata
            
            # 원본 이미지 저장
            cv2.imwrite(str(original_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # 썸네일 생성 및 저장
            thumbnail_150 = self._create_thumbnail(frame, 150)
            thumbnail_300 = self._create_thumbnail(frame, 300)
            
            cv2.imwrite(str(thumbnail_150_path), thumbnail_150, [cv2.IMWRITE_JPEG_QUALITY, 90])
            cv2.imwrite(str(thumbnail_300_path), thumbnail_300, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            # 완전한 메타데이터 생성
            image_metadata = {
                "hash": frame_hash,
                "timestamp": metadata.get("timestamp", time.time()),
                "timeframe_info": metadata.get("timeframe_info", {}),
                "quality_scores": quality_scores,
                "composite_score": composite_score,
                "object_confidence": object_confidence,
                "image_dimensions": {
                    "width": frame.shape[1],
                    "height": frame.shape[0]
                },
                "file_paths": {
                    "original": str(original_path),
                    "thumbnail_150": str(thumbnail_150_path),
                    "thumbnail_300": str(thumbnail_300_path),
                    "metadata": str(metadata_path)
                },
                "extracted_at": time.time(),
                "file_sizes": {
                    "original": original_path.stat().st_size if original_path.exists() else 0,
                    "thumbnail_150": thumbnail_150_path.stat().st_size if thumbnail_150_path.exists() else 0,
                    "thumbnail_300": thumbnail_300_path.stat().st_size if thumbnail_300_path.exists() else 0
                }
            }
            
            # 메타데이터 저장
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(image_metadata, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"제품 이미지 저장 완료: {frame_hash} (품질: {composite_score:.3f})")
            return image_metadata
            
        except Exception as e:
            self.logger.error(f"제품 이미지 저장 실패: {e}")
            raise
    
    def select_best_images(self, image_metadata_list: List[Dict[str, Any]], max_count: int = 5) -> List[Dict[str, Any]]:
        """
        최고 품질 이미지 선별
        
        Args:
            image_metadata_list: 이미지 메타데이터 리스트
            max_count: 최대 선택 개수
            
        Returns:
            List[Dict[str, Any]]: 선별된 이미지 메타데이터 리스트
        """
        try:
            # 종합 점수 기준으로 정렬
            sorted_images = sorted(
                image_metadata_list, 
                key=lambda x: x.get("composite_score", 0), 
                reverse=True
            )
            
            selected_images = sorted_images[:max_count]
            
            self.logger.info(f"최고 품질 이미지 {len(selected_images)}개 선별 완료")
            return selected_images
            
        except Exception as e:
            self.logger.error(f"이미지 선별 실패: {e}")
            return image_metadata_list[:max_count]  # 폴백
    
    def cleanup_low_quality_images(self, min_score: float = 0.3) -> int:
        """
        낮은 품질 이미지 파일 정리
        
        Args:
            min_score: 최소 품질 점수
            
        Returns:
            int: 삭제된 파일 수
        """
        deleted_count = 0
        try:
            # 메타데이터 파일들 순회
            for metadata_file in self.output_dir.glob("*.json"):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    composite_score = metadata.get("composite_score", 0)
                    if composite_score < min_score:
                        # 관련 파일들 삭제
                        file_paths = metadata.get("file_paths", {})
                        for path_key, path_str in file_paths.items():
                            path_obj = Path(path_str)
                            if path_obj.exists():
                                path_obj.unlink()
                        
                        deleted_count += 1
                        self.logger.debug(f"낮은 품질 이미지 삭제: {metadata.get('hash', 'unknown')}")
                
                except Exception as e:
                    self.logger.warning(f"이미지 정리 중 오류: {e}")
                    continue
            
            self.logger.info(f"낮은 품질 이미지 {deleted_count}개 정리 완료")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"이미지 정리 실패: {e}")
            return 0


class TargetFrameExtractor:
    """타겟 시간대 프레임 추출 및 분석 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        타겟 프레임 추출기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # 컴포넌트 초기화
        self.gpu_optimizer = GPUOptimizer()
        self.ocr_processor = OCRProcessor(config=self.config)
        self.object_detector = ObjectDetector(gpu_optimizer=self.gpu_optimizer)
        
        # 제품 이미지 추출기 초기화
        self.product_image_extractor = ProductImageExtractor()
        
        # 기본 설정
        self.extraction_config = FrameExtractionConfig()
        
        self.logger.info("타겟 프레임 추출기 초기화 완료")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        
        # 안전한 로그 레벨 설정
        try:
            if hasattr(self.config, 'LOG_LEVEL') and isinstance(self.config.LOG_LEVEL, str):
                level_str = self.config.LOG_LEVEL.upper()
                if level_str == 'DEBUG':
                    logger.setLevel(logging.DEBUG)
                elif level_str == 'INFO':
                    logger.setLevel(logging.INFO)
                elif level_str == 'WARNING':
                    logger.setLevel(logging.WARNING)
                elif level_str == 'ERROR':
                    logger.setLevel(logging.ERROR)
                elif level_str == 'CRITICAL':
                    logger.setLevel(logging.CRITICAL)
                else:
                    logger.setLevel(logging.INFO)
            else:
                logger.setLevel(logging.INFO)
        except (AttributeError, TypeError):
            logger.setLevel(logging.INFO)
        
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
    
    def analyze_single_frame(self, frame: ExtractedFrame, save_product_images: bool = False, timeframe_info: Dict[str, Any] = None) -> FrameAnalysisResult:
        """
        단일 프레임 분석 수행
        
        Args:
            frame: 분석할 프레임
            save_product_images: 제품 이미지 저장 여부
            timeframe_info: 타임프레임 정보
            
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
                    # OCR 처리 메서드 수정
                    ocr_text_results = self.ocr_processor.extract_text_from_frame(frame.frame_data)
                    if ocr_text_results:
                        ocr_results = ocr_text_results
                        detected_texts = [result['text'] for result in ocr_text_results if result.get('text')]
                except Exception as e:
                    self.logger.warning(f"OCR 처리 실패 (프레임 {frame.frame_index}): {e}")
            
            # 객체 인식
            object_detection_results = []
            detected_objects = []
            
            if frame.frame_data is not None:
                try:
                    detection_result = self.object_detector.detect_objects(frame.frame_data)
                    if detection_result and detection_result.get('success') and detection_result.get('detections'):
                        object_detection_results = detection_result['detections']
                        detected_objects = [d.get('class_name', 'unknown') for d in detection_result['detections']]
                except Exception as e:
                    self.logger.warning(f"객체 인식 실패 (프레임 {frame.frame_index}): {e}")
            
            # 제품 이미지 저장 (옵션)
            product_image_metadata = None
            if save_product_images and frame.frame_data is not None:
                try:
                    # 객체 탐지 신뢰도 계산 (평균)
                    object_confidence = 0.0
                    if object_detection_results:
                        confidences = [d.get('confidence', 0) for d in object_detection_results]
                        object_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                    
                    # 이미지 메타데이터 준비
                    image_metadata = {
                        "timestamp": frame.timestamp,
                        "timeframe_info": timeframe_info or {}
                    }
                    
                    # 제품 이미지 저장
                    product_image_metadata = self.product_image_extractor.save_product_image(
                        frame.frame_data, 
                        image_metadata, 
                        object_confidence
                    )
                    
                except Exception as e:
                    self.logger.warning(f"제품 이미지 저장 실패 (프레임 {frame.frame_index}): {e}")

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
            
            # 제품 이미지 메타데이터를 결과에 추가 (확장 속성)
            if product_image_metadata:
                result.product_image_metadata = product_image_metadata
            
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
        config: Optional[FrameExtractionConfig] = None,
        save_product_images: bool = False
    ) -> TargetFrameAnalysisResult:
        """
        타겟 시간대 전체 분석 수행
        
        Args:
            video_path: 영상 파일 경로
            timeframe: 분석할 타겟 시간대
            config: 프레임 추출 설정
            save_product_images: 제품 이미지 저장 여부
            
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
            product_image_metadata_list = []
            
            # 타임프레임 정보 준비 (이미지 메타데이터용)
            timeframe_info = {
                "start_time": timeframe.start_time,
                "end_time": timeframe.end_time,
                "confidence_score": timeframe.confidence_score,
                "reason": getattr(timeframe, 'reason', '')
            }
            
            with self.gpu_optimizer.optimized_context():
                for frame in extracted_frames:
                    try:
                        result = self.analyze_single_frame(frame, save_product_images, timeframe_info)
                        frame_results.append(result)
                        successful_analyses += 1
                        
                        # 제품 이미지 메타데이터 수집
                        if hasattr(result, 'product_image_metadata') and result.product_image_metadata:
                            product_image_metadata_list.append(result.product_image_metadata)
                            
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
            
            # 4. 제품 이미지 선별 (최고 품질 이미지만)
            selected_product_images = []
            if product_image_metadata_list:
                selected_product_images = self.product_image_extractor.select_best_images(
                    product_image_metadata_list, max_count=5
                )
            
            # 5. 처리 통계
            analysis_end = time.time()
            total_processing_time = analysis_end - analysis_start
            
            processing_stats = {
                "total_frames_processed": len(frame_results),
                "successful_analyses": successful_analyses,
                "average_processing_time_per_frame": total_processing_time / len(extracted_frames) if extracted_frames else 0,
                "extraction_success_rate": len(extracted_frames) / max(1, (timeframe.end_time - timeframe.start_time)) if timeframe.end_time > timeframe.start_time else 0,
                "analysis_success_rate": successful_analyses / len(extracted_frames) if extracted_frames else 0,
                "product_images_extracted": len(product_image_metadata_list),
                "product_images_selected": len(selected_product_images)
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
            
            # 제품 이미지 정보를 결과에 추가 (확장 속성)
            if selected_product_images:
                result.selected_product_images = selected_product_images
                result.all_product_images = product_image_metadata_list
            
            self.logger.info(
                f"타겟 시간대 분석 완료: "
                f"{len(extracted_frames)}개 프레임 처리, "
                f"{successful_analyses}개 성공, "
                f"텍스트 {len(summary_texts)}개, 객체 {len(summary_objects)}개 발견, "
                f"제품 이미지 {len(product_image_metadata_list)}개 추출 ({len(selected_product_images)}개 선별), "
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