"""
Visual Processor 통합 테스트
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.visual_processor import OCRProcessor, ImagePreprocessor
from config.config import Config


class TestVisualProcessorIntegration:
    """Visual Processor 통합 테스트 클래스"""
    
    @pytest.fixture
    def mock_config(self):
        """테스트용 설정"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = "INFO"
        config.OCR_CONFIDENCE_THRESHOLD = 0.6
        config.USE_GPU = False
        config.MAX_IMAGE_SIZE = 2048
        config.MIN_IMAGE_SIZE = 64
        config.get_temp_dir.return_value = Path("/tmp/test")
        return config
    
    @pytest.fixture
    def sample_text_image(self):
        """텍스트가 포함된 샘플 이미지 생성"""
        # 실제로는 PIL로 텍스트가 포함된 이미지를 생성하지만,
        # 테스트에서는 numpy 배열로 시뮬레이션
        image = np.ones((300, 400, 3), dtype=np.uint8) * 255  # 흰색 배경
        
        # 텍스트 영역 시뮬레이션 (어두운 직사각형)
        image[50:100, 50:200] = [0, 0, 0]  # 제품명 영역
        image[120:150, 80:180] = [0, 0, 0]  # 브랜드명 영역
        
        return image
    
    @pytest.mark.integration
    @patch('src.visual_processor.ocr_processor.easyocr')
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_full_ocr_pipeline(self, mock_cv2, mock_easyocr, mock_config, sample_text_image):
        """전체 OCR 파이프라인 통합 테스트"""
        # EasyOCR Reader 모의
        mock_reader = Mock()
        mock_reader.readtext.return_value = [
            ([[50, 50], [200, 50], [200, 100], [50, 100]], '나이키 에어맥스', 0.95),
            ([[80, 120], [180, 120], [180, 150], [80, 150]], 'Nike', 0.88),
            ([[250, 200], [300, 200], [300, 220], [250, 220]], 'x', 0.2)  # 낮은 신뢰도
        ]
        mock_easyocr.Reader.return_value = mock_reader
        
        # OpenCV 모의
        mock_cv2.cvtColor.return_value = sample_text_image[:, :, 0]
        mock_cv2.fastNlMeansDenoising.return_value = sample_text_image[:, :, 0]
        mock_cv2.createCLAHE.return_value.apply.return_value = sample_text_image[:, :, 0]
        
        # OCR 프로세서 초기화
        ocr_processor = OCRProcessor(mock_config)
        
        # 텍스트 추출 실행
        results = ocr_processor.extract_text_from_frame(sample_text_image, preprocess=True)
        
        # 결과 검증
        assert len(results) == 2  # 신뢰도 낮은 결과 제외
        
        # 첫 번째 결과 (가장 높은 신뢰도)
        assert results[0]['text'] == '나이키 에어맥스'
        assert results[0]['confidence'] == 0.95
        assert results[0]['language'] == 'ko'
        
        # 두 번째 결과
        assert results[1]['text'] == 'Nike'
        assert results[1]['confidence'] == 0.88
        assert results[1]['language'] == 'en'
        
        # OpenCV 함수들이 호출되었는지 확인 (전처리)
        mock_cv2.cvtColor.assert_called()
        
        # EasyOCR이 호출되었는지 확인
        mock_reader.readtext.assert_called_once()
    
    @pytest.mark.integration
    @patch('src.visual_processor.ocr_processor.easyocr')
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_batch_processing_integration(self, mock_cv2, mock_easyocr, mock_config):
        """배치 처리 통합 테스트"""
        # 여러 이미지 생성
        images = [
            np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8),
            np.random.randint(0, 255, (150, 250, 3), dtype=np.uint8),
            np.random.randint(0, 255, (180, 280, 3), dtype=np.uint8)
        ]
        
        # EasyOCR Reader 모의
        mock_reader = Mock()
        mock_reader.readtext.return_value = [
            ([[10, 10], [100, 10], [100, 30], [10, 30]], '제품명', 0.9)
        ]
        mock_easyocr.Reader.return_value = mock_reader
        
        # OpenCV 모의
        mock_cv2.cvtColor.side_effect = lambda img, _: img[:, :, 0]
        mock_cv2.fastNlMeansDenoising.side_effect = lambda img, *args, **kwargs: img
        mock_cv2.createCLAHE.return_value.apply.side_effect = lambda img: img
        
        # OCR 프로세서 초기화
        ocr_processor = OCRProcessor(mock_config)
        
        # 배치 처리 실행
        batch_results = ocr_processor.batch_extract_text(images, preprocess=True)
        
        # 결과 검증
        assert len(batch_results) == 3
        assert all(isinstance(result, list) for result in batch_results)
        assert all(len(result) > 0 for result in batch_results)
        
        # 각 이미지에 대해 OCR이 실행되었는지 확인
        assert mock_reader.readtext.call_count == 3
    
    @pytest.mark.integration
    def test_gemini_integration_workflow(self, mock_config):
        """Gemini 분석과의 연동 워크플로우 테스트"""
        with patch('src.visual_processor.ocr_processor.easyocr') as mock_easyocr:
            # OCR 결과 모의
            mock_reader = Mock()
            mock_reader.readtext.return_value = [
                ([[50, 50], [200, 50], [200, 100], [50, 100]], '디올 향수', 0.92),
                ([[80, 120], [180, 120], [180, 150], [80, 150]], 'Dior', 0.88)
            ]
            mock_easyocr.Reader.return_value = mock_reader
            
            # OCR 프로세서 초기화
            ocr_processor = OCRProcessor(mock_config)
            
            # 샘플 이미지로 OCR 실행
            sample_image = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
            ocr_results = ocr_processor.extract_text_from_frame(sample_image)
            
            # Gemini 분석 결과 시뮬레이션
            gemini_timeframe = {
                'product_mentions': ['디올 향수', '크리스챤 디올', 'perfume'],
                'start_time': 120.0,
                'end_time': 180.0
            }
            
            # OCR과 Gemini 결과 융합
            integrated_results = ocr_processor.integrate_with_gemini_analysis(
                ocr_results, gemini_timeframe
            )
            
            # 융합 결과 검증
            assert len(integrated_results) == 2
            
            # 첫 번째 결과 (디올 향수)
            first_result = integrated_results[0]
            assert 'gemini_match_score' in first_result
            assert 'is_product_related' in first_result
            assert first_result['gemini_match_score'] == 1.0  # 완전 일치
            assert first_result['is_product_related'] == True
            
            # 두 번째 결과 (Dior)
            second_result = integrated_results[1]
            assert second_result['gemini_match_score'] > 0.0  # 부분 일치
    
    @pytest.mark.integration
    @patch('src.visual_processor.image_preprocessor.cv2')
    def test_image_preprocessing_quality_improvement(self, mock_cv2, mock_config):
        """이미지 전처리를 통한 품질 개선 테스트"""
        # 저품질 이미지 시뮬레이션
        noisy_image = np.random.randint(0, 255, (100, 200), dtype=np.uint8)
        
        # OpenCV 함수들 모의
        mock_cv2.GaussianBlur.return_value = noisy_image
        mock_cv2.absdiff.return_value = np.ones_like(noisy_image) * 15  # 높은 노이즈
        mock_cv2.fastNlMeansDenoising.return_value = noisy_image
        mock_cv2.calcHist.return_value = np.ones((256, 1)) * 2  # 낮은 대비
        mock_cv2.createCLAHE.return_value.apply.return_value = noisy_image
        mock_cv2.resize.return_value = noisy_image
        
        # 전처리기 초기화
        preprocessor = ImagePreprocessor(mock_config)
        
        # 전처리 실행
        processed_image = preprocessor.optimize_for_ocr(noisy_image)
        
        # 전처리 함수들이 호출되었는지 확인
        mock_cv2.fastNlMeansDenoising.assert_called()  # 노이즈 제거
        mock_cv2.createCLAHE.assert_called()  # 대비 향상
        
        assert processed_image is not None
        assert processed_image.shape == noisy_image.shape
    
    @pytest.mark.integration
    def test_end_to_end_performance(self, mock_config):
        """종단간 성능 테스트"""
        import time
        
        with patch('src.visual_processor.ocr_processor.easyocr') as mock_easyocr:
            with patch('src.visual_processor.image_preprocessor.cv2') as mock_cv2:
                # 빠른 모의 응답 설정
                mock_reader = Mock()
                mock_reader.readtext.return_value = [
                    ([[10, 10], [100, 10], [100, 30], [10, 30]], '테스트', 0.9)
                ]
                mock_easyocr.Reader.return_value = mock_reader
                
                mock_cv2.cvtColor.side_effect = lambda img, _: img[:, :, 0] if len(img.shape) == 3 else img
                mock_cv2.fastNlMeansDenoising.side_effect = lambda img, *args, **kwargs: img
                mock_cv2.createCLAHE.return_value.apply.side_effect = lambda img: img
                
                # OCR 프로세서 초기화
                ocr_processor = OCRProcessor(mock_config)
                
                # 여러 이미지로 성능 측정
                test_images = [
                    np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
                    for _ in range(10)
                ]
                
                start_time = time.time()
                results = ocr_processor.batch_extract_text(test_images)
                end_time = time.time()
                
                # 성능 검증
                processing_time = end_time - start_time
                assert processing_time < 5.0  # 10개 이미지를 5초 내에 처리
                assert len(results) == 10
                assert all(len(result) > 0 for result in results)
    
    @pytest.mark.integration
    def test_error_recovery_integration(self, mock_config):
        """오류 복구 통합 테스트"""
        with patch('src.visual_processor.ocr_processor.easyocr') as mock_easyocr:
            # OCR 에러 시뮬레이션
            mock_reader = Mock()
            mock_reader.readtext.side_effect = Exception("OCR processing error")
            mock_easyocr.Reader.return_value = mock_reader
            
            # OCR 프로세서 초기화
            ocr_processor = OCRProcessor(mock_config)
            
            # 에러 상황에서 처리
            sample_image = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
            results = ocr_processor.extract_text_from_frame(sample_image)
            
            # 빈 결과 반환 확인 (에러 시)
            assert results == []
    
    @pytest.mark.integration
    def test_memory_usage_optimization(self, mock_config):
        """메모리 사용량 최적화 테스트"""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('src.visual_processor.ocr_processor.easyocr') as mock_easyocr:
            with patch('src.visual_processor.image_preprocessor.cv2') as mock_cv2:
                # 메모리 효율적인 모의 응답
                mock_reader = Mock()
                mock_reader.readtext.return_value = []
                mock_easyocr.Reader.return_value = mock_reader
                
                mock_cv2.cvtColor.side_effect = lambda img, _: img[:, :, 0] if len(img.shape) == 3 else img
                
                # 대량 이미지 처리
                ocr_processor = OCRProcessor(mock_config)
                
                for _ in range(50):  # 50개 이미지 처리
                    large_image = np.random.randint(0, 255, (1000, 1000, 3), dtype=np.uint8)
                    ocr_processor.extract_text_from_frame(large_image)
                    
                    # 명시적 가비지 컬렉션
                    del large_image
                    gc.collect()
                
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                # 메모리 증가량이 합리적인 범위 내인지 확인 (1GB 이하)
                assert memory_increase < 1024  # 1GB
    
    def test_processor_info_integration(self, mock_config):
        """프로세서 정보 통합 테스트"""
        with patch('src.visual_processor.ocr_processor.easyocr') as mock_easyocr:
            with patch('src.visual_processor.image_preprocessor.cv2') as mock_cv2:
                mock_easyocr.Reader.return_value = Mock()
                
                # 프로세서들 초기화
                ocr_processor = OCRProcessor(mock_config)
                image_preprocessor = ImagePreprocessor(mock_config)
                
                # 정보 수집
                ocr_info = ocr_processor.get_processor_info()
                preprocessing_info = image_preprocessor.get_preprocessing_info()
                
                # OCR 정보 검증
                assert 'status' in ocr_info
                assert 'languages' in ocr_info
                assert 'gpu_enabled' in ocr_info
                
                # 전처리 정보 검증
                assert 'opencv_available' in preprocessing_info
                assert 'supported_operations' in preprocessing_info
                assert 'recommended_input_formats' in preprocessing_info