"""
이미지 전처리 모듈

OCR 성능 향상을 위한 이미지 전처리 및 최적화 기능을 제공합니다.
"""

import logging
from typing import Optional, Tuple, Union, Any
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageEnhance
except ImportError:
    # 테스트 환경에서 모듈이 없을 경우를 위한 처리
    cv2 = None
    np = None
    Image = None
    ImageEnhance = None

from config.config import Config
from ..gpu_optimizer import GPUOptimizer


class ImagePreprocessor:
    """이미지 전처리 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        이미지 전처리기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # GPU 최적화 초기화 (활성화된 경우)
        self.gpu_optimizer = None
        if getattr(self.config, 'ENABLE_GPU_OPTIMIZATION', True):
            try:
                self.gpu_optimizer = GPUOptimizer(self.config)
                self.logger.info("GPU 최적화 활성화됨")
            except Exception as e:
                self.logger.warning(f"GPU 최적화 초기화 실패: {str(e)}")
                self.gpu_optimizer = None
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        
        # 안전한 로그 레벨 설정
        try:
            if hasattr(self.config, 'LOG_LEVEL') and isinstance(self.config.LOG_LEVEL, str):
                level_str = self.config.LOG_LEVEL.upper()
                if level_str in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                    logger.setLevel(getattr(logging, level_str))
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
    
    def optimize_for_ocr(self, image: Any) -> Any:
        """
        OCR을 위한 이미지 최적화
        
        Args:
            image: 원본 이미지 (BGR 형식)
            
        Returns:
            최적화된 이미지
        """
        if cv2 is None or np is None:
            self.logger.warning("OpenCV 모듈이 설치되지 않았습니다. 원본 이미지를 반환합니다.")
            return image
        
        try:
            self.logger.debug("OCR 최적화 전처리 시작")
            
            # 1. 그레이스케일 변환
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 2. 이미지 품질 평가
            quality_score = self._assess_image_quality(gray)
            self.logger.debug(f"이미지 품질 점수: {quality_score:.2f}")
            
            # 3. 단계별 전처리 적용
            processed = gray.copy()
            
            # 노이즈 제거
            if self._needs_denoising(processed):
                processed = self._apply_denoising(processed)
            
            # 대비 향상
            if self._needs_contrast_enhancement(processed):
                processed = self._enhance_contrast(processed)
            
            # 해상도 최적화
            processed = self._optimize_resolution(processed)
            
            # 이진화 (필요시)
            if self._needs_binarization(processed):
                processed = self._apply_binarization(processed)
            
            self.logger.debug("OCR 최적화 전처리 완료")
            return processed
            
        except Exception as e:
            self.logger.error(f"이미지 전처리 실패: {str(e)}")
            return image
    
    def _assess_image_quality(self, image: Any) -> float:
        """
        이미지 품질 평가
        
        Args:
            image: 그레이스케일 이미지
            
        Returns:
            품질 점수 (0.0-1.0, 높을수록 좋음)
        """
        try:
            # 라플라시안 분산을 이용한 선명도 측정
            laplacian_var = cv2.Laplacian(image, cv2.CV_64F).var()
            
            # 대비 측정 (표준편차 기반)
            contrast = np.std(image) / 255.0
            
            # 밝기 균등성 측정
            hist = cv2.calcHist([image], [0], None, [256], [0, 256])
            hist_norm = hist / hist.sum()
            brightness_uniformity = 1.0 - np.std(hist_norm)
            
            # 종합 품질 점수 계산
            sharpness_score = min(laplacian_var / 1000.0, 1.0)  # 정규화
            contrast_score = min(contrast * 2, 1.0)  # 대비가 클수록 좋음
            uniformity_score = brightness_uniformity
            
            quality_score = (sharpness_score * 0.4 + 
                           contrast_score * 0.4 + 
                           uniformity_score * 0.2)
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            self.logger.warning(f"이미지 품질 평가 실패: {str(e)}")
            return 0.5  # 기본값
    
    def _needs_denoising(self, image: Any) -> bool:
        """
        노이즈 제거 필요성 판단
        
        Args:
            image: 그레이스케일 이미지
            
        Returns:
            노이즈 제거 필요 여부
        """
        try:
            # 가우시안 블러 적용 후 차이 계산
            blurred = cv2.GaussianBlur(image, (5, 5), 0)
            diff = cv2.absdiff(image, blurred)
            noise_level = np.mean(diff)
            
            return bool(noise_level > 10)  # 임계값 - bool로 명시적 변환
            
        except Exception:
            return False
    
    def _apply_denoising(self, image: Any) -> Any:
        """
        노이즈 제거 적용
        
        Args:
            image: 원본 이미지
            
        Returns:
            노이즈가 제거된 이미지
        """
        try:
            # fastNlMeansDenoising 사용
            denoised = cv2.fastNlMeansDenoising(
                image, 
                None, 
                h=10,  # 필터 강도
                templateWindowSize=7, 
                searchWindowSize=21
            )
            return denoised
            
        except Exception as e:
            self.logger.warning(f"노이즈 제거 실패: {str(e)}")
            return image
    
    def _needs_contrast_enhancement(self, image: Any) -> bool:
        """
        대비 향상 필요성 판단
        
        Args:
            image: 그레이스케일 이미지
            
        Returns:
            대비 향상 필요 여부
        """
        try:
            # 히스토그램 분석
            hist = cv2.calcHist([image], [0], None, [256], [0, 256])
            
            # 동적 범위 계산
            non_zero_indices = np.nonzero(hist)[0]
            if len(non_zero_indices) == 0:
                return False
            
            dynamic_range = non_zero_indices[-1] - non_zero_indices[0]
            
            # 대비가 낮으면 향상 필요
            return bool(dynamic_range < 200)  # 0-255 범위에서 - bool로 명시적 변환
            
        except Exception:
            return False
    
    def _enhance_contrast(self, image: Any) -> Any:
        """
        대비 향상 적용
        
        Args:
            image: 원본 이미지
            
        Returns:
            대비가 향상된 이미지
        """
        try:
            # CLAHE (Contrast Limited Adaptive Histogram Equalization) 적용
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)
            
            # 추가적인 감마 보정 (필요시)
            gamma = self._calculate_optimal_gamma(image)
            if gamma != 1.0:
                enhanced = self._apply_gamma_correction(enhanced, gamma)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"대비 향상 실패: {str(e)}")
            return image
    
    def _calculate_optimal_gamma(self, image: Any) -> float:
        """
        최적 감마값 계산
        
        Args:
            image: 이미지
            
        Returns:
            최적 감마값
        """
        try:
            # 이미지의 평균 밝기 기반으로 감마 계산
            mean_brightness = np.mean(image) / 255.0
            
            if mean_brightness < 0.3:  # 어두운 이미지
                return 0.7  # 밝게
            elif mean_brightness > 0.7:  # 밝은 이미지
                return 1.3  # 어둡게
            else:
                return 1.0  # 변경 없음
                
        except Exception:
            return 1.0
    
    def _apply_gamma_correction(self, image: Any, gamma: float) -> Any:
        """
        감마 보정 적용
        
        Args:
            image: 원본 이미지
            gamma: 감마값
            
        Returns:
            감마 보정된 이미지
        """
        try:
            # 룩업 테이블 생성
            inv_gamma = 1.0 / gamma
            table = np.array([
                ((i / 255.0) ** inv_gamma) * 255 
                for i in np.arange(0, 256)
            ]).astype("uint8")
            
            # 룩업 테이블 적용
            return cv2.LUT(image, table)
            
        except Exception:
            return image
    
    def _optimize_resolution(self, image: Any) -> Any:
        """
        OCR을 위한 해상도 최적화
        
        Args:
            image: 원본 이미지
            
        Returns:
            해상도가 최적화된 이미지
        """
        try:
            height, width = image.shape[:2]
            
            # 최소 해상도 확보 (OCR 성능을 위해)
            min_height = 64
            min_width = 64
            
            # 최대 해상도 제한 (처리 속도를 위해)
            max_height = 2048
            max_width = 2048
            
            scale_factor = 1.0
            
            # 너무 작은 경우 확대
            if height < min_height or width < min_width:
                scale_factor = max(min_height / height, min_width / width)
            
            # 너무 큰 경우 축소
            elif height > max_height or width > max_width:
                scale_factor = min(max_height / height, max_width / width)
            
            # 리사이징 적용
            if scale_factor != 1.0:
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                
                # 고품질 보간법 사용
                interpolation = cv2.INTER_CUBIC if scale_factor > 1.0 else cv2.INTER_AREA
                resized = cv2.resize(image, (new_width, new_height), interpolation=interpolation)
                
                self.logger.debug(f"해상도 조정: {width}x{height} -> {new_width}x{new_height}")
                return resized
            
            return image
            
        except Exception as e:
            self.logger.warning(f"해상도 최적화 실패: {str(e)}")
            return image
    
    def _needs_binarization(self, image: Any) -> bool:
        """
        이진화 필요성 판단
        
        Args:
            image: 그레이스케일 이미지
            
        Returns:
            이진화 필요 여부
        """
        try:
            # 이미지의 동적 범위와 분산 확인
            std_dev = np.std(image)
            
            # 분산이 낮으면 이진화가 도움될 수 있음
            return bool(std_dev < 40)  # bool로 명시적 변환
            
        except Exception:
            return False
    
    def _apply_binarization(self, image: Any) -> Any:
        """
        적응적 이진화 적용
        
        Args:
            image: 그레이스케일 이미지
            
        Returns:
            이진화된 이미지
        """
        try:
            # Otsu 방법과 적응적 임계값 중 최적 선택
            
            # 1. Otsu 이진화 시도
            _, otsu_binary = cv2.threshold(
                image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            
            # 2. 적응적 이진화 시도
            adaptive_binary = cv2.adaptiveThreshold(
                image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # 3. 두 결과 중 더 나은 것 선택 (간단한 휴리스틱)
            otsu_std = np.std(otsu_binary)
            adaptive_std = np.std(adaptive_binary)
            
            # 분산이 더 큰 것을 선택 (더 많은 정보 보존)
            if otsu_std > adaptive_std:
                self.logger.debug("Otsu 이진화 적용")
                return otsu_binary
            else:
                self.logger.debug("적응적 이진화 적용")
                return adaptive_binary
                
        except Exception as e:
            self.logger.warning(f"이진화 실패: {str(e)}")
            return image
    
    def enhance_text_regions(
        self, 
        image: Any, 
        text_boxes: list = None
    ) -> Any:
        """
        텍스트 영역 집중 향상
        
        Args:
            image: 원본 이미지
            text_boxes: 텍스트 바운딩 박스 리스트 (선택사항)
            
        Returns:
            텍스트 영역이 향상된 이미지
        """
        if cv2 is None:
            return image
        
        try:
            enhanced = image.copy()
            
            if text_boxes:
                # 특정 텍스트 영역만 향상
                for box in text_boxes:
                    x1, y1, x2, y2 = self._normalize_text_box(box)
                    roi = enhanced[y1:y2, x1:x2]
                    
                    if roi.size > 0:
                        # ROI에 집중적인 전처리 적용
                        enhanced_roi = self._apply_intensive_preprocessing(roi)
                        enhanced[y1:y2, x1:x2] = enhanced_roi
            else:
                # 전체 이미지에 텍스트 특화 향상 적용
                enhanced = self._apply_text_specific_enhancement(enhanced)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"텍스트 영역 향상 실패: {str(e)}")
            return image
    
    def _normalize_text_box(self, box) -> Tuple[int, int, int, int]:
        """
        텍스트 박스 좌표 정규화
        
        Args:
            box: 텍스트 박스 좌표
            
        Returns:
            정규화된 (x1, y1, x2, y2) 좌표
        """
        try:
            if isinstance(box, list) and len(box) == 4:
                if isinstance(box[0], list):
                    # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 형태
                    xs = [point[0] for point in box]
                    ys = [point[1] for point in box]
                    x1, x2 = min(xs), max(xs)
                    y1, y2 = min(ys), max(ys)
                else:
                    # [x1, y1, x2, y2] 형태
                    x1, y1, x2, y2 = box
            else:
                return (0, 0, 0, 0)
            
            return (int(x1), int(y1), int(x2), int(y2))
            
        except Exception:
            return (0, 0, 0, 0)
    
    def _apply_intensive_preprocessing(self, roi: Any) -> Any:
        """
        ROI에 집중적인 전처리 적용
        
        Args:
            roi: 관심 영역
            
        Returns:
            전처리된 ROI
        """
        try:
            # 샤프닝 필터 적용
            kernel = np.array([[-1, -1, -1],
                              [-1,  9, -1],
                              [-1, -1, -1]])
            sharpened = cv2.filter2D(roi, -1, kernel)
            
            # 모폴로지 연산으로 텍스트 정리
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(sharpened, cv2.MORPH_CLOSE, kernel)
            
            return cleaned
            
        except Exception:
            return roi
    
    def _apply_text_specific_enhancement(self, image: Any) -> Any:
        """
        텍스트 특화 향상 적용
        
        Args:
            image: 원본 이미지
            
        Returns:
            텍스트 특화 향상된 이미지
        """
        try:
            # 언샤프 마스킹으로 텍스트 경계 강화
            blurred = cv2.GaussianBlur(image, (0, 0), 1.0)
            enhanced = cv2.addWeighted(image, 1.5, blurred, -0.5, 0)
            
            return enhanced
            
        except Exception:
            return image
    
    def batch_optimize_for_ocr(self, images: list) -> list:
        """
        배치 이미지 OCR 최적화 (GPU 최적화 적용)
        
        Args:
            images: 이미지 리스트
            
        Returns:
            최적화된 이미지 리스트
        """
        if not images:
            return []
        
        if self.gpu_optimizer and len(images) > 1:
            try:
                # GPU 최적화된 배치 처리
                return self.gpu_optimizer.process_with_optimization(
                    images, 
                    self._batch_process_images
                )
            except Exception as e:
                self.logger.warning(f"GPU 배치 처리 실패, CPU로 대체: {str(e)}")
        
        # 일반 처리 (순차적)
        return [self.optimize_for_ocr(image) for image in images]
    
    def _batch_process_images(self, image_batch: list) -> list:
        """
        이미지 배치 처리 내부 메서드
        
        Args:
            image_batch: 처리할 이미지 배치
            
        Returns:
            처리된 이미지 배치
        """
        return [self.optimize_for_ocr(image) for image in image_batch]
    
    def get_preprocessing_info(self) -> dict:
        """
        전처리기 정보 반환
        
        Returns:
            전처리기 정보
        """
        return {
            'opencv_available': cv2 is not None,
            'supported_operations': [
                'denoising',
                'contrast_enhancement', 
                'resolution_optimization',
                'binarization',
                'text_region_enhancement'
            ],
            'recommended_input_formats': ['jpg', 'png', 'bmp'],
            'optimal_resolution_range': '64x64 to 2048x2048'
        }