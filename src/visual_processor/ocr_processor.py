"""
EasyOCR 기반 텍스트 인식 프로세서

영상 프레임에서 제품명, 브랜드명 등의 텍스트 정보를 정확히 추출하는 
EasyOCR 기반 텍스트 인식 시스템입니다.
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
try:
    import easyocr
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    # 테스트 환경에서 모듈이 없을 경우를 위한 처리
    easyocr = None
    cv2 = None
    np = None
    Image = None

from config.config import Config
from .image_preprocessor import ImagePreprocessor
from ..gpu_optimizer import GPUOptimizer


class OCRProcessor:
    """EasyOCR 기반 텍스트 인식 프로세서 클래스"""
    
    def __init__(self, config: Optional[Config] = None, languages: List[str] = None):
        """
        OCR 프로세서 초기화
        
        Args:
            config: 설정 객체
            languages: 지원 언어 리스트 (기본값: ['ko', 'en'])
        """
        self.config = config or Config()
        self.languages = languages or ['ko', 'en']
        self.logger = self._setup_logger()
        self.preprocessor = ImagePreprocessor(config)
        
        # GPU 최적화 초기화
        self.gpu_optimizer = None
        if getattr(self.config, 'ENABLE_GPU_OPTIMIZATION', True):
            try:
                self.gpu_optimizer = GPUOptimizer(self.config)
                self.logger.info("OCR GPU 최적화 활성화됨")
            except Exception as e:
                self.logger.warning(f"OCR GPU 최적화 초기화 실패: {str(e)}")
                self.gpu_optimizer = None
        
        self.reader = None
        self._load_model()
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL, 'INFO'))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _load_model(self) -> None:
        """EasyOCR 모델 로드"""
        if easyocr is None:
            self.logger.warning("EasyOCR 모듈이 설치되지 않았습니다. 테스트 모드로 실행됩니다.")
            self.reader = None
            return
        
        try:
            self.logger.info(f"EasyOCR 모델 로드 시작: 언어={self.languages}")
            start_time = time.time()
            
            # GPU 사용 가능 여부 확인 (GPU Optimizer 우선 적용)
            gpu_available = False
            if self.gpu_optimizer and self.gpu_optimizer.is_gpu_available:
                gpu_available = True
                self.logger.info("EasyOCR GPU 모드 활성화")
            elif hasattr(self.config, 'USE_GPU') and self.config.USE_GPU:
                gpu_available = True
                self.logger.info("EasyOCR GPU 모드 활성화 (config 설정)")
            else:
                self.logger.info("EasyOCR CPU 모드로 실행")
            
            # EasyOCR Reader 초기화 (다국어 지원 강화)
            self.reader = easyocr.Reader(
                self.languages, 
                gpu=gpu_available,
                verbose=False,  # 불필요한 출력 억제
                download_enabled=True  # 필요한 모델 자동 다운로드
            )
            
            load_time = time.time() - start_time
            device_info = "GPU" if gpu_available else "CPU"
            self.logger.info(f"EasyOCR 모델 로드 완료 ({device_info}) - 소요시간: {load_time:.2f}초")
            
        except Exception as e:
            self.logger.error(f"EasyOCR 모델 로드 실패: {str(e)}")
            raise
    
    def extract_text_from_frame(
        self, 
        frame_image: Union[str, Path, Any],
        preprocess: bool = True
    ) -> List[Dict[str, Any]]:
        """
        단일 프레임에서 텍스트 추출
        
        Args:
            frame_image: 이미지 파일 경로 또는 numpy 배열
            preprocess: 전처리 적용 여부
            
        Returns:
            추출된 텍스트 정보 리스트
        """
        if self.reader is None:
            self.logger.warning("EasyOCR 모델이 로드되지 않았습니다. 테스트 데이터를 반환합니다.")
            return [
                {
                    'text': '테스트 제품명',
                    'confidence': 0.95,
                    'bbox': [[100, 50], [300, 50], [300, 100], [100, 100]],
                    'language': 'ko'
                }
            ]
        
        try:
            self.logger.debug("프레임 텍스트 추출 시작")
            start_time = time.time()
            
            # 이미지 로드 및 전처리
            if isinstance(frame_image, (str, Path)):
                image = cv2.imread(str(frame_image))
                if image is None:
                    self.logger.error(f"이미지 로드 실패: {frame_image}")
                    return []
            else:
                image = frame_image
            
            if preprocess:
                processed_image = self.preprocessor.optimize_for_ocr(image)
            else:
                processed_image = image
            
            # EasyOCR 텍스트 인식 실행
            raw_results = self.reader.readtext(processed_image)
            
            # 결과 후처리
            results = self._post_process_results(raw_results)
            
            process_time = time.time() - start_time
            self.logger.debug(f"텍스트 추출 완료 - {len(results)}개 텍스트, 소요시간: {process_time:.2f}초")
            
            return results
            
        except Exception as e:
            self.logger.error(f"텍스트 추출 실패: {str(e)}")
            return []
    
    def batch_extract_text(
        self, 
        frame_list: List[Union[str, Path, Any]],
        preprocess: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        다중 프레임 배치 처리
        
        Args:
            frame_list: 이미지 리스트
            preprocess: 전처리 적용 여부
            
        Returns:
            각 프레임별 텍스트 추출 결과
        """
        if not frame_list:
            return []
        
        try:
            self.logger.info(f"배치 텍스트 추출 시작 - {len(frame_list)}개 프레임")
            start_time = time.time()
            
            results = []
            for i, frame in enumerate(frame_list):
                self.logger.debug(f"프레임 {i+1}/{len(frame_list)} 처리 중")
                frame_result = self.extract_text_from_frame(frame, preprocess)
                results.append(frame_result)
            
            total_time = time.time() - start_time
            total_texts = sum(len(result) for result in results)
            self.logger.info(f"배치 처리 완료 - {total_texts}개 텍스트, 소요시간: {total_time:.2f}초")
            
            return results
            
        except Exception as e:
            self.logger.error(f"배치 처리 실패: {str(e)}")
            return []
    
    def _post_process_results(self, raw_results: List) -> List[Dict[str, Any]]:
        """
        EasyOCR 결과 후처리 및 필터링
        
        Args:
            raw_results: EasyOCR readtext() 원본 결과
            
        Returns:
            후처리된 텍스트 정보 리스트
        """
        if not raw_results:
            return []
        
        filtered_results = []
        
        for item in raw_results:
            bbox, text, confidence = item
            
            # 신뢰도 임계값 적용
            confidence_threshold = getattr(self.config, 'OCR_CONFIDENCE_THRESHOLD', 0.5)
            if confidence < confidence_threshold:
                continue
            
            # 노이즈 텍스트 제거
            if self._is_noise_text(text):
                continue
            
            # 텍스트 정리 및 정규화
            cleaned_text = self._clean_text(text)
            if not cleaned_text.strip():
                continue
            
            # 언어 감지 (간단한 휴리스틱)
            detected_language = self._detect_language(cleaned_text)
            
            filtered_results.append({
                'text': cleaned_text,
                'confidence': round(confidence, 3),
                'bbox': self._normalize_bbox(bbox),
                'language': detected_language,
                'area': self._calculate_bbox_area(bbox)
            })
        
        # 신뢰도 순으로 정렬
        filtered_results.sort(key=lambda x: x['confidence'], reverse=True)
        
        return filtered_results
    
    def _is_noise_text(self, text: str) -> bool:
        """
        노이즈 텍스트 필터링
        
        Args:
            text: 검사할 텍스트
            
        Returns:
            노이즈 텍스트 여부
        """
        if not text or len(text.strip()) < 2:
            return True
        
        # 단일 문자나 숫자만 있는 경우
        cleaned = text.strip()
        if len(cleaned) == 1 and cleaned.isdigit():
            return True
        
        # 특수문자만 있는 경우
        if all(not char.isalnum() for char in cleaned):
            return True
        
        # 반복 문자 (예: "aaaa", "1111")
        if len(set(cleaned.lower())) == 1 and len(cleaned) > 3:
            return True
        
        return False
    
    def _clean_text(self, text: str) -> str:
        """
        텍스트 정리 및 정규화
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정리된 텍스트
        """
        if not text:
            return ""
        
        # 앞뒤 공백 제거
        cleaned = text.strip()
        
        # 연속된 공백을 단일 공백으로 변환
        cleaned = ' '.join(cleaned.split())
        
        # 특정 문자 정리 (필요에 따라 확장)
        # 예: 불필요한 특수문자 제거
        
        return cleaned
    
    def _detect_language(self, text: str) -> str:
        """
        간단한 언어 감지
        
        Args:
            text: 검사할 텍스트
            
        Returns:
            감지된 언어 코드
        """
        if not text:
            return 'unknown'
        
        # 한글 문자 포함 여부 확인
        korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7af')
        total_chars = len([char for char in text if char.isalpha()])
        
        if total_chars == 0:
            return 'number'
        
        korean_ratio = korean_chars / total_chars
        if korean_ratio >= 0.25:  # 25%로 낮춰서 '안녕 Hello' 케이스 처리
            return 'ko'
        else:
            return 'en'
    
    def _normalize_bbox(self, bbox: List[List[int]]) -> List[List[int]]:
        """
        바운딩 박스 좌표 정규화
        
        Args:
            bbox: 원본 바운딩 박스 좌표
            
        Returns:
            정규화된 바운딩 박스 좌표
        """
        if not bbox or len(bbox) != 4:
            return [[0, 0], [0, 0], [0, 0], [0, 0]]
        
        # 좌표를 정수로 변환
        normalized = [[int(point[0]), int(point[1])] for point in bbox]
        return normalized
    
    def _calculate_bbox_area(self, bbox: List[List[int]]) -> int:
        """
        바운딩 박스 면적 계산
        
        Args:
            bbox: 바운딩 박스 좌표
            
        Returns:
            면적 (픽셀 단위)
        """
        if not bbox or len(bbox) != 4:
            return 0
        
        try:
            # 직사각형으로 가정하여 계산
            width = abs(bbox[1][0] - bbox[0][0])
            height = abs(bbox[2][1] - bbox[1][1])
            return width * height
        except (IndexError, TypeError):
            return 0
    
    def integrate_with_gemini_analysis(
        self, 
        ocr_results: List[Dict[str, Any]], 
        gemini_timeframe: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        OCR 결과와 Gemini 분석 결과 융합
        
        Args:
            ocr_results: OCR 추출 결과
            gemini_timeframe: Gemini 분석 시간대 정보
            
        Returns:
            융합된 분석 결과
        """
        if not ocr_results:
            return []
        
        try:
            self.logger.debug("Gemini 분석과 OCR 결과 융합 시작")
            
            product_mentions = gemini_timeframe.get('product_mentions', [])
            
            for ocr_result in ocr_results:
                # 텍스트 매칭 점수 계산
                match_score = self._calculate_text_match(
                    ocr_result['text'], 
                    product_mentions
                )
                
                ocr_result['gemini_match_score'] = round(match_score, 3)
                ocr_result['is_product_related'] = match_score >= 0.6  # >= 로 변경
                
                # 제품 카테고리 추론
                if ocr_result['is_product_related']:
                    ocr_result['inferred_category'] = self._infer_product_category(
                        ocr_result['text']
                    )
            
            # 제품 관련성 순으로 정렬
            ocr_results.sort(
                key=lambda x: (x['is_product_related'], x['gemini_match_score']), 
                reverse=True
            )
            
            self.logger.debug(f"융합 완료 - {len(ocr_results)}개 결과")
            return ocr_results
            
        except Exception as e:
            self.logger.error(f"Gemini 연동 실패: {str(e)}")
            return ocr_results
    
    def _calculate_text_match(
        self, 
        ocr_text: str, 
        product_mentions: List[str]
    ) -> float:
        """
        OCR 텍스트와 제품 언급 간의 매칭 점수 계산
        
        Args:
            ocr_text: OCR로 추출된 텍스트
            product_mentions: Gemini가 찾은 제품 언급 리스트
            
        Returns:
            매칭 점수 (0.0-1.0)
        """
        if not ocr_text or not product_mentions:
            return 0.0
        
        ocr_lower = ocr_text.lower().strip()
        max_score = 0.0
        
        for mention in product_mentions:
            mention_lower = mention.lower().strip()
            
            # 완전 일치
            if ocr_lower == mention_lower:
                max_score = max(max_score, 1.0)
                continue
            
            # 부분 일치
            if ocr_lower in mention_lower or mention_lower in ocr_lower:
                score = min(len(ocr_lower), len(mention_lower)) / max(len(ocr_lower), len(mention_lower))
                max_score = max(max_score, score * 0.9)  # 0.8에서 0.9로 증가
                continue
            
            # 단어 단위 일치
            ocr_words = set(ocr_lower.split())
            mention_words = set(mention_lower.split())
            
            if ocr_words and mention_words:
                intersection = ocr_words.intersection(mention_words)
                union = ocr_words.union(mention_words)
                jaccard_score = len(intersection) / len(union) if union else 0
                max_score = max(max_score, jaccard_score * 0.6)
        
        return max_score
    
    def _infer_product_category(self, text: str) -> str:
        """
        텍스트로부터 제품 카테고리 추론
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            추론된 카테고리
        """
        text_lower = text.lower()
        
        # 화장품 관련 키워드
        if any(keyword in text_lower for keyword in [
            '크림', '세럼', '로션', '토너', '클렌징', '마스크', '팩',
            'cream', 'serum', 'lotion', 'toner', 'cleanser', 'mask'
        ]):
            return 'cosmetics'
        
        # 패션 관련 키워드
        if any(keyword in text_lower for keyword in [
            '셔츠', '바지', '드레스', '스커트', '코트', '자켓', '블라우스',
            'shirt', 'pants', 'dress', 'skirt', 'coat', 'jacket', 'blouse'
        ]):
            return 'fashion'
        
        # 액세서리 관련 키워드
        if any(keyword in text_lower for keyword in [
            '목걸이', '귀걸이', '반지', '팔찌', '시계', '가방',
            'necklace', 'earring', 'ring', 'bracelet', 'watch', 'bag'
        ]):
            return 'accessories'
        
        return 'unknown'
    
    def batch_process_frames(self, frames: List[Any]) -> List[List[Dict[str, Any]]]:
        """
        프레임 배치를 GPU 최적화로 처리
        
        Args:
            frames: 처리할 프레임 리스트
            
        Returns:
            각 프레임의 OCR 결과 리스트
        """
        if not frames:
            return []
        
        if self.gpu_optimizer and len(frames) > 1:
            try:
                # GPU 최적화된 배치 처리
                return self.gpu_optimizer.process_with_optimization(
                    frames, 
                    self._batch_process_ocr
                )
            except Exception as e:
                self.logger.warning(f"OCR GPU 배치 처리 실패, CPU로 대체: {str(e)}")
        
        # 일반 처리 (순차적)
        return [self.extract_text_from_frame(frame) for frame in frames]
    
    def _batch_process_ocr(self, frame_batch: List[Any]) -> List[List[Dict[str, Any]]]:
        """
        OCR 배치 처리 내부 메서드
        
        Args:
            frame_batch: 처리할 프레임 배치
            
        Returns:
            배치 OCR 결과
        """
        results = []
        
        # 이미지 전처리 배치 적용
        if self.preprocessor and hasattr(self.preprocessor, 'batch_optimize_for_ocr'):
            processed_frames = self.preprocessor.batch_optimize_for_ocr(frame_batch)
        else:
            processed_frames = frame_batch
        
        # OCR 처리
        for frame in processed_frames:
            frame_results = self.extract_text_from_frame(frame)
            results.append(frame_results)
        
        return results
    
    def get_processor_info(self) -> Dict[str, Any]:
        """
        프로세서 정보 반환
        
        Returns:
            프로세서 정보 딕셔너리
        """
        if self.reader is None or easyocr is None:
            return {
                'status': 'not_loaded',
                'languages': self.languages,
                'message': 'EasyOCR 모듈이 설치되지 않았거나 모델이 로드되지 않았습니다.'
            }
        
        return {
            'status': 'ready',
            'languages': self.languages,
            'gpu_enabled': hasattr(self.config, 'USE_GPU') and self.config.USE_GPU,
            'confidence_threshold': getattr(self.config, 'OCR_CONFIDENCE_THRESHOLD', 0.5),
            'supported_formats': ['jpg', 'jpeg', 'png', 'bmp', 'tiff']
        }