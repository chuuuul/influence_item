"""
ImagePreprocessor 단위 테스트
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
from pathlib import Path

from src.visual_processor.image_preprocessor import ImagePreprocessor
from config import Config


class TestImagePreprocessor:
    """ImagePreprocessor 테스트 클래스"""
    
    @pytest.fixture
    def mock_config(self):
        """테스트용 설정 모의객체"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = "INFO"
        config.MAX_IMAGE_SIZE = 2048
        config.MIN_IMAGE_SIZE = 64
        return config
    
    @pytest.fixture
    def preprocessor(self, mock_config):
        """ImagePreprocessor 인스턴스"""
        return ImagePreprocessor(mock_config)
    
    @pytest.fixture
    def sample_image(self):
        """테스트용 샘플 이미지"""
        # 200x150 크기의 그레이스케일 이미지 생성
        return np.random.randint(0, 255, (150, 200), dtype=np.uint8)
    
    @pytest.fixture
    def sample_color_image(self):
        """테스트용 컬러 이미지"""
        # 200x150 크기의 BGR 이미지 생성
        return np.random.randint(0, 255, (150, 200, 3), dtype=np.uint8)
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_preprocessor_init(self, mock_cv2, mock_config):
        """ImagePreprocessor 초기화 테스트"""
        preprocessor = ImagePreprocessor(mock_config)
        
        assert preprocessor.config == mock_config
        assert preprocessor.logger is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_optimize_for_ocr_color_image(self, mock_cv2, preprocessor, sample_color_image):
        """컬러 이미지 OCR 최적화 테스트"""
        # Mock OpenCV 함수들
        mock_cv2.cvtColor.return_value = sample_color_image[:, :, 0]  # 그레이스케일 변환
        mock_cv2.fastNlMeansDenoising.return_value = sample_color_image[:, :, 0]
        mock_cv2.createCLAHE.return_value.apply.return_value = sample_color_image[:, :, 0]
        mock_cv2.resize.return_value = sample_color_image[:, :, 0]
        
        result = preprocessor.optimize_for_ocr(sample_color_image)
        
        # 그레이스케일 변환이 호출되었는지 확인
        mock_cv2.cvtColor.assert_called_once()
        assert result is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2', None)
    def test_optimize_for_ocr_no_opencv(self, preprocessor, sample_image):
        """OpenCV 없는 환경에서 최적화 테스트"""
        result = preprocessor.optimize_for_ocr(sample_image)
        
        # 원본 이미지 반환 확인
        assert np.array_equal(result, sample_image)
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_assess_image_quality(self, mock_cv2, preprocessor, sample_image):
        """이미지 품질 평가 테스트"""
        # Mock OpenCV 함수들
        mock_cv2.Laplacian.return_value.var.return_value = 500.0
        mock_cv2.calcHist.return_value = np.ones((256, 1)) * 10  # 균등한 히스토그램
        
        quality_score = preprocessor._assess_image_quality(sample_image)
        
        assert 0.0 <= quality_score <= 1.0
        mock_cv2.Laplacian.assert_called_once()
        mock_cv2.calcHist.assert_called_once()
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_needs_denoising(self, mock_cv2, preprocessor, sample_image):
        """노이즈 제거 필요성 판단 테스트"""
        # 노이즈가 많은 경우 시뮬레이션
        mock_cv2.GaussianBlur.return_value = sample_image
        mock_cv2.absdiff.return_value = np.ones_like(sample_image) * 15  # 높은 차이값
        
        needs_denoising = preprocessor._needs_denoising(sample_image)
        
        assert isinstance(needs_denoising, bool)
        mock_cv2.GaussianBlur.assert_called_once()
        mock_cv2.absdiff.assert_called_once()
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_apply_denoising(self, mock_cv2, preprocessor, sample_image):
        """노이즈 제거 적용 테스트"""
        mock_cv2.fastNlMeansDenoising.return_value = sample_image
        
        result = preprocessor._apply_denoising(sample_image)
        
        mock_cv2.fastNlMeansDenoising.assert_called_once()
        assert result is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_needs_contrast_enhancement(self, mock_cv2, preprocessor, sample_image):
        """대비 향상 필요성 판단 테스트"""
        # 낮은 대비 이미지 시뮬레이션
        hist = np.zeros((256, 1))
        hist[100:150] = 10  # 좁은 범위에만 값이 있음 (낮은 대비)
        mock_cv2.calcHist.return_value = hist
        
        needs_enhancement = preprocessor._needs_contrast_enhancement(sample_image)
        
        assert isinstance(needs_enhancement, bool)
        mock_cv2.calcHist.assert_called_once()
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_enhance_contrast(self, mock_cv2, preprocessor, sample_image):
        """대비 향상 테스트"""
        # Mock CLAHE
        mock_clahe = Mock()
        mock_clahe.apply.return_value = sample_image
        mock_cv2.createCLAHE.return_value = mock_clahe
        
        result = preprocessor._enhance_contrast(sample_image)
        
        mock_cv2.createCLAHE.assert_called_once()
        mock_clahe.apply.assert_called_once()
        assert result is not None
    
    def test_calculate_optimal_gamma(self, preprocessor):
        """최적 감마값 계산 테스트"""
        # 어두운 이미지
        dark_image = np.ones((100, 100), dtype=np.uint8) * 50
        gamma_dark = preprocessor._calculate_optimal_gamma(dark_image)
        assert gamma_dark < 1.0  # 밝게 만들기 위해 감마 < 1
        
        # 밝은 이미지
        bright_image = np.ones((100, 100), dtype=np.uint8) * 200
        gamma_bright = preprocessor._calculate_optimal_gamma(bright_image)
        assert gamma_bright > 1.0  # 어둡게 만들기 위해 감마 > 1
        
        # 중간 밝기 이미지
        normal_image = np.ones((100, 100), dtype=np.uint8) * 128
        gamma_normal = preprocessor._calculate_optimal_gamma(normal_image)
        assert gamma_normal == 1.0  # 변경 없음
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_apply_gamma_correction(self, mock_cv2, preprocessor, sample_image):
        """감마 보정 적용 테스트"""
        mock_cv2.LUT.return_value = sample_image
        
        result = preprocessor._apply_gamma_correction(sample_image, 1.2)
        
        mock_cv2.LUT.assert_called_once()
        assert result is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_optimize_resolution_small_image(self, mock_cv2, preprocessor):
        """작은 이미지 해상도 최적화 테스트"""
        # 너무 작은 이미지 (32x32)
        small_image = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
        mock_cv2.resize.return_value = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
        
        result = preprocessor._optimize_resolution(small_image)
        
        # 리사이징이 호출되었는지 확인
        mock_cv2.resize.assert_called_once()
        assert result is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_optimize_resolution_large_image(self, mock_cv2, preprocessor):
        """큰 이미지 해상도 최적화 테스트"""
        # 너무 큰 이미지 (3000x3000)
        large_image = np.random.randint(0, 255, (3000, 3000), dtype=np.uint8)
        mock_cv2.resize.return_value = np.random.randint(0, 255, (2048, 2048), dtype=np.uint8)
        
        result = preprocessor._optimize_resolution(large_image)
        
        # 리사이징이 호출되었는지 확인
        mock_cv2.resize.assert_called_once()
        assert result is not None
    
    def test_needs_binarization(self, preprocessor, sample_image):
        """이진화 필요성 판단 테스트"""
        # 낮은 분산 이미지 (이진화 필요)
        low_variance_image = np.ones((100, 100), dtype=np.uint8) * 128
        low_variance_image[40:60, 40:60] = 130  # 약간의 변화만
        
        needs_binary = preprocessor._needs_binarization(low_variance_image)
        assert needs_binary == True
        
        # 높은 분산 이미지 (이진화 불필요)
        high_variance_image = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        needs_binary_high = preprocessor._needs_binarization(high_variance_image)
        assert isinstance(needs_binary_high, bool)
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_apply_binarization(self, mock_cv2, preprocessor, sample_image):
        """이진화 적용 테스트"""
        # Mock 이진화 함수들
        mock_cv2.threshold.return_value = (128, sample_image)
        mock_cv2.adaptiveThreshold.return_value = sample_image
        
        result = preprocessor._apply_binarization(sample_image)
        
        mock_cv2.threshold.assert_called_once()
        mock_cv2.adaptiveThreshold.assert_called_once()
        assert result is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_enhance_text_regions_with_boxes(self, mock_cv2, preprocessor, sample_image):
        """텍스트 박스 지정 영역 향상 테스트"""
        text_boxes = [
            [[10, 10], [50, 10], [50, 30], [10, 30]]  # 텍스트 박스
        ]
        
        mock_cv2.filter2D.return_value = sample_image[10:30, 10:50]
        mock_cv2.getStructuringElement.return_value = np.ones((2, 2), dtype=np.uint8)
        mock_cv2.morphologyEx.return_value = sample_image[10:30, 10:50]
        
        result = preprocessor.enhance_text_regions(sample_image, text_boxes)
        
        assert result is not None
        # 전체 이미지 크기가 유지되는지 확인
        assert result.shape == sample_image.shape
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_enhance_text_regions_without_boxes(self, mock_cv2, preprocessor, sample_image):
        """전체 이미지 텍스트 향상 테스트"""
        mock_cv2.GaussianBlur.return_value = sample_image
        mock_cv2.addWeighted.return_value = sample_image
        
        result = preprocessor.enhance_text_regions(sample_image)
        
        mock_cv2.GaussianBlur.assert_called_once()
        mock_cv2.addWeighted.assert_called_once()
        assert result is not None
    
    def test_normalize_text_box(self, preprocessor):
        """텍스트 박스 좌표 정규화 테스트"""
        # 4점 형태 박스
        box_4points = [[10, 20], [100, 20], [100, 60], [10, 60]]
        normalized = preprocessor._normalize_text_box(box_4points)
        assert normalized == (10, 20, 100, 60)
        
        # 직사각형 형태 박스
        box_rect = [10, 20, 100, 60]
        normalized_rect = preprocessor._normalize_text_box(box_rect)
        assert normalized_rect == (10, 20, 100, 60)
        
        # 잘못된 형태
        invalid_box = [10, 20]
        normalized_invalid = preprocessor._normalize_text_box(invalid_box)
        assert normalized_invalid == (0, 0, 0, 0)
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_apply_intensive_preprocessing(self, mock_cv2, preprocessor, sample_image):
        """집중적인 전처리 테스트"""
        roi = sample_image[10:50, 20:80]
        
        mock_cv2.filter2D.return_value = roi
        mock_cv2.getStructuringElement.return_value = np.ones((2, 2), dtype=np.uint8)
        mock_cv2.morphologyEx.return_value = roi
        
        result = preprocessor._apply_intensive_preprocessing(roi)
        
        mock_cv2.filter2D.assert_called_once()
        mock_cv2.morphologyEx.assert_called_once()
        assert result is not None
    
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_apply_text_specific_enhancement(self, mock_cv2, preprocessor, sample_image):
        """텍스트 특화 향상 테스트"""
        mock_cv2.GaussianBlur.return_value = sample_image
        mock_cv2.addWeighted.return_value = sample_image
        
        result = preprocessor._apply_text_specific_enhancement(sample_image)
        
        mock_cv2.GaussianBlur.assert_called_once()
        mock_cv2.addWeighted.assert_called_once()
        assert result is not None
    
    def test_get_preprocessing_info_with_opencv(self, preprocessor):
        """OpenCV 있는 환경에서 전처리기 정보 테스트"""
        with patch('src.visual_processor.image_preprocessor.cv2', Mock()):
            info = preprocessor.get_preprocessing_info()
            
            assert info['opencv_available'] == True
            assert 'supported_operations' in info
            assert 'recommended_input_formats' in info
            assert 'optimal_resolution_range' in info
    
    def test_get_preprocessing_info_without_opencv(self, preprocessor):
        """OpenCV 없는 환경에서 전처리기 정보 테스트"""
        with patch('src.visual_processor.image_preprocessor.cv2', None):
            info = preprocessor.get_preprocessing_info()
            
            assert info['opencv_available'] == False
            assert 'supported_operations' in info
    
    def test_preprocessing_exception_handling(self, preprocessor, sample_image):
        """전처리 예외 처리 테스트"""
        with patch('src.visual_processor.image_preprocessor.cv2') as mock_cv2:
            # OpenCV 함수에서 예외 발생
            mock_cv2.cvtColor.side_effect = Exception("OpenCV error")
            
            # 예외가 발생해도 원본 이미지를 반환해야 함
            result = preprocessor.optimize_for_ocr(sample_image)
            assert np.array_equal(result, sample_image)