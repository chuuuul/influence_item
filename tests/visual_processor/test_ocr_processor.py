"""
OCRProcessor 단위 테스트
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.visual_processor.ocr_processor import OCRProcessor
from config import Config


class TestOCRProcessor:
    """OCRProcessor 테스트 클래스"""
    
    @pytest.fixture
    def mock_config(self):
        """테스트용 설정 모의객체"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = "INFO"
        config.OCR_CONFIDENCE_THRESHOLD = 0.5
        config.USE_GPU = False
        config.get_temp_dir.return_value = Path("/tmp/test")
        return config
    
    @pytest.fixture
    def mock_easyocr_reader(self):
        """EasyOCR Reader 모의객체"""
        reader = Mock()
        
        # readtext 메서드 모의
        reader.readtext.return_value = [
            (
                [[100, 50], [300, 50], [300, 100], [100, 100]], 
                '테스트 제품명', 
                0.95
            ),
            (
                [[150, 120], [350, 120], [350, 160], [150, 160]], 
                'Test Brand', 
                0.88
            ),
            (
                [[50, 200], [100, 200], [100, 220], [50, 220]], 
                'x', 
                0.3  # 낮은 신뢰도
            )
        ]
        return reader
    
    @pytest.fixture
    def processor(self, mock_config):
        """OCRProcessor 인스턴스"""
        with patch('src.visual_processor.ocr_processor.easyocr'):
            return OCRProcessor(mock_config)
    
    @patch('src.visual_processor.ocr_processor.easyocr')
    def test_ocr_processor_init(self, mock_easyocr, mock_config, mock_easyocr_reader):
        """OCRProcessor 초기화 테스트"""
        mock_easyocr.Reader.return_value = mock_easyocr_reader
        
        processor = OCRProcessor(mock_config, languages=['ko', 'en'])
        
        assert processor.config == mock_config
        assert processor.languages == ['ko', 'en']
        assert processor.reader == mock_easyocr_reader
        mock_easyocr.Reader.assert_called_once_with(['ko', 'en'], gpu=False, verbose=False)
    
    @patch('src.visual_processor.ocr_processor.easyocr')
    def test_extract_text_from_frame(self, mock_easyocr, mock_config, mock_easyocr_reader):
        """프레임 텍스트 추출 테스트"""
        mock_easyocr.Reader.return_value = mock_easyocr_reader
        
        processor = OCRProcessor(mock_config)
        
        # 테스트 이미지 (numpy 배열)
        test_image = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
        
        with patch.object(processor.preprocessor, 'optimize_for_ocr', return_value=test_image):
            results = processor.extract_text_from_frame(test_image)
        
        # 신뢰도 임계값 이상의 결과만 반환되는지 확인
        assert len(results) == 2  # 신뢰도 0.3인 'x'는 제외됨
        
        # 첫 번째 결과 확인
        assert results[0]['text'] == '테스트 제품명'
        assert results[0]['confidence'] == 0.95
        assert results[0]['language'] == 'ko'
        assert 'bbox' in results[0]
        assert 'area' in results[0]
        
        mock_easyocr_reader.readtext.assert_called_once()
    
    @patch('src.visual_processor.ocr_processor.easyocr')
    def test_batch_extract_text(self, mock_easyocr, mock_config, mock_easyocr_reader):
        """배치 텍스트 추출 테스트"""
        mock_easyocr.Reader.return_value = mock_easyocr_reader
        
        processor = OCRProcessor(mock_config)
        
        # 테스트 이미지 리스트
        test_images = [
            np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8),
            np.random.randint(0, 255, (150, 250, 3), dtype=np.uint8)
        ]
        
        with patch.object(processor.preprocessor, 'optimize_for_ocr', side_effect=lambda x: x):
            results = processor.batch_extract_text(test_images)
        
        assert len(results) == 2
        assert all(isinstance(result, list) for result in results)
        assert mock_easyocr_reader.readtext.call_count == 2
    
    def test_post_process_results(self, processor):
        """결과 후처리 테스트"""
        raw_results = [
            ([[100, 50], [300, 50], [300, 100], [100, 100]], '  테스트 제품명  ', 0.95),
            ([[150, 120], [350, 120], [350, 160], [150, 160]], 'Valid Text', 0.88),
            ([[50, 200], [100, 200], [100, 220], [50, 220]], 'x', 0.3),  # 낮은 신뢰도
            ([[200, 300], [250, 300], [250, 320], [200, 320]], '', 0.9),  # 빈 텍스트
            ([[300, 400], [400, 400], [400, 420], [300, 420]], '@@@@', 0.8),  # 노이즈
        ]
        
        results = processor._post_process_results(raw_results)
        
        # 필터링 결과 확인
        assert len(results) == 2
        
        # 신뢰도 순으로 정렬되었는지 확인
        assert results[0]['confidence'] >= results[1]['confidence']
        
        # 텍스트 정리 확인 (앞뒤 공백 제거)
        assert results[0]['text'] == '테스트 제품명'
    
    def test_is_noise_text(self, processor):
        """노이즈 텍스트 판별 테스트"""
        # 노이즈 케이스
        assert processor._is_noise_text('')
        assert processor._is_noise_text(' ')
        assert processor._is_noise_text('a')
        assert processor._is_noise_text('1')
        assert processor._is_noise_text('@@@@@@')
        assert processor._is_noise_text('aaaaaaa')
        
        # 유효한 텍스트
        assert not processor._is_noise_text('Valid Text')
        assert not processor._is_noise_text('제품명')
        assert not processor._is_noise_text('Brand123')
    
    def test_detect_language(self, processor):
        """언어 감지 테스트"""
        assert processor._detect_language('안녕하세요') == 'ko'
        assert processor._detect_language('Hello World') == 'en'
        assert processor._detect_language('안녕 Hello') == 'ko'  # 한글이 30% 이상
        assert processor._detect_language('123456') == 'number'
        assert processor._detect_language('') == 'unknown'
    
    def test_calculate_text_match(self, processor):
        """텍스트 매칭 점수 계산 테스트"""
        ocr_text = '나이키 에어맥스'
        product_mentions = ['나이키 에어맥스 270', '아디다스 신발', 'Nike Air Max']
        
        score = processor._calculate_text_match(ocr_text, product_mentions)
        
        # 부분 일치로 높은 점수 예상
        assert score > 0.5
        
        # 완전 일치 테스트
        exact_score = processor._calculate_text_match('나이키', ['나이키'])
        assert exact_score == 1.0
        
        # 불일치 테스트
        no_match_score = processor._calculate_text_match('완전다른텍스트', ['나이키'])
        assert no_match_score == 0.0
    
    def test_infer_product_category(self, processor):
        """제품 카테고리 추론 테스트"""
        assert processor._infer_product_category('보습 크림') == 'cosmetics'
        assert processor._infer_product_category('Moisturizing Cream') == 'cosmetics'
        assert processor._infer_product_category('블라우스') == 'fashion'
        assert processor._infer_product_category('목걸이') == 'accessories'
        assert processor._infer_product_category('알 수 없는 제품') == 'unknown'
    
    def test_integrate_with_gemini_analysis(self, processor):
        """Gemini 분석 연동 테스트"""
        ocr_results = [
            {
                'text': '나이키 에어맥스',
                'confidence': 0.95,
                'bbox': [[100, 50], [300, 50], [300, 100], [100, 100]],
                'language': 'ko'
            }
        ]
        
        gemini_timeframe = {
            'product_mentions': ['나이키 에어맥스 270', '운동화']
        }
        
        integrated_results = processor.integrate_with_gemini_analysis(
            ocr_results, gemini_timeframe
        )
        
        assert len(integrated_results) == 1
        assert 'gemini_match_score' in integrated_results[0]
        assert 'is_product_related' in integrated_results[0]
        assert integrated_results[0]['gemini_match_score'] > 0.5
        assert integrated_results[0]['is_product_related'] == True
    
    def test_get_processor_info_no_easyocr(self, mock_config):
        """EasyOCR 없는 환경에서 프로세서 정보 테스트"""
        with patch('src.visual_processor.ocr_processor.easyocr', None):
            processor = OCRProcessor(mock_config)
            info = processor.get_processor_info()
            
            assert info['status'] == 'not_loaded'
            assert 'message' in info
    
    @patch('src.visual_processor.ocr_processor.easyocr')
    def test_get_processor_info_with_easyocr(self, mock_easyocr, mock_config, mock_easyocr_reader):
        """EasyOCR 있는 환경에서 프로세서 정보 테스트"""
        mock_easyocr.Reader.return_value = mock_easyocr_reader
        
        processor = OCRProcessor(mock_config)
        info = processor.get_processor_info()
        
        assert info['status'] == 'ready'
        assert info['languages'] == ['ko', 'en']
        assert 'gpu_enabled' in info
        assert 'confidence_threshold' in info
        assert 'supported_formats' in info
    
    def test_model_load_failure(self, mock_config):
        """모델 로드 실패 테스트"""
        with patch('src.visual_processor.ocr_processor.easyocr') as mock_easyocr:
            mock_easyocr.Reader.side_effect = Exception("모델 로드 실패")
            
            with pytest.raises(Exception) as exc_info:
                OCRProcessor(mock_config)
            
            assert "모델 로드 실패" in str(exc_info.value)
    
    def test_extract_text_no_model(self, mock_config):
        """모델 없는 상태에서 텍스트 추출 테스트"""
        with patch('src.visual_processor.ocr_processor.easyocr', None):
            processor = OCRProcessor(mock_config)
            
            test_image = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
            results = processor.extract_text_from_frame(test_image)
            
            # 테스트 데이터 반환 확인
            assert len(results) == 1
            assert results[0]['text'] == '테스트 제품명'
            assert results[0]['confidence'] == 0.95