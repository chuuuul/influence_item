"""
YOLOv8/YOLO11 기반 객체 탐지 프로세서

영상 프레임에서 제품 객체를 자동으로 탐지하고 분류하는 
YOLO11 기반 객체 인식 시스템입니다.
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
try:
    from ultralytics import YOLO
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    # 테스트 환경에서 모듈이 없을 경우를 위한 처리
    YOLO = None
    cv2 = None
    np = None
    Image = None

from config.config import Config


class ObjectDetector:
    """YOLO11 기반 고성능 객체 탐지 프로세서 클래스"""
    
    def __init__(self, config: Optional[Config] = None, model_name: str = "yolo11m.pt", gpu_optimizer=None):
        """
        객체 탐지 프로세서 초기화 (성능 최적화)
        
        Args:
            config: 설정 객체
            model_name: 사용할 YOLO 모델명 (기본값: yolo11m.pt - 정확도 향상)
            gpu_optimizer: GPU 최적화 객체 (선택적)
        """
        self.config = config or Config()
        self.model_name = model_name
        self.gpu_optimizer = gpu_optimizer
        self.logger = self._setup_logger()
        self.model = None
        
        # 향상된 임계값 설정 (정확도 95% 목표)
        self.confidence_threshold = getattr(self.config, 'YOLO_CONFIDENCE_THRESHOLD', 0.35)  # 0.25 -> 0.35
        self.iou_threshold = getattr(self.config, 'YOLO_IOU_THRESHOLD', 0.5)  # 0.45 -> 0.5
        
        # 성능 캐싱 시스템
        self.detection_cache = {}
        self.cache_max_size = 100
        
        # 제품 특화 클래스 매핑
        self.product_classes = {
            'cosmetics': ['bottle', 'tube', 'container', 'cup'],
            'fashion': ['clothing', 'shirt', 'pants', 'dress', 'shoe'],
            'accessories': ['bag', 'handbag', 'watch', 'jewelry'],
            'electronics': ['cell phone', 'laptop', 'mouse', 'keyboard'],
            'food': ['bottle', 'cup', 'bowl', 'spoon', 'fork']
        }
        
        if self.gpu_optimizer:
            self.logger.info("객체 탐지 GPU 최적화 활성화됨")
        
        self._load_model()
    
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
    
    def _load_model(self) -> None:
        """YOLO 모델 로딩 (최적화된 모델 선택 및 GPU 최적화)"""
        if YOLO is None:
            self.logger.warning("ultralytics 라이브러리가 설치되지 않았습니다. 객체 탐지 기능을 사용할 수 없습니다.")
            return
        
        try:
            start_time = time.time()
            self.logger.info(f"YOLO 모델 로드 시작: {self.model_name}")
            
            # 성능 최적화된 모델 로딩
            self.model = YOLO(self.model_name)
            
            # GPU 사용 가능할 때 모델을 GPU로 이동
            if self.gpu_optimizer and self.gpu_optimizer.is_gpu_available:
                self.model.to('cuda')
                # GPU 최적화 설정
                self.model.overrides['device'] = 'cuda'
                self.model.overrides['half'] = True  # FP16 추론 활성화
                self.logger.info("YOLO 모델이 GPU로 이동되었습니다 (FP16 최적화)")
            else:
                self.model.to('cpu')
                self.logger.info("YOLO 모델이 CPU에서 실행됩니다")
            
            # 모델 워밍업 (첫 추론 속도 향상)
            if hasattr(self.model, 'warmup'):
                self.model.warmup()
                self.logger.debug("YOLO 모델 워밍업 완료")
            
            load_time = time.time() - start_time
            self.logger.info(f"YOLO 모델 로드 완료 - 소요시간: {load_time:.2f}초")
            
        except Exception as e:
            self.logger.error(f"YOLO 모델 로딩 실패: {str(e)}")
            self.model = None
    
    def detect_objects(
        self, 
        frame_image: Union[str, Path, Any],
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        enable_cache: bool = True
    ) -> Dict[str, Any]:
        """
        단일 프레임에서 객체 탐지 (캐싱 및 성능 최적화)
        
        Args:
            frame_image: 입력 이미지 (파일 경로, PIL Image, numpy array 등)
            confidence_threshold: 신뢰도 임계값 (None이면 기본값 사용)
            iou_threshold: IoU 임계값 (None이면 기본값 사용)
            enable_cache: 캐싱 활성화 여부
            
        Returns:
            탐지 결과 딕셔너리
        """
        if self.model is None:
            self.logger.warning("YOLO 모델이 로드되지 않았습니다. 빈 결과를 반환합니다.")
            return self._get_empty_result()
        
        try:
            # 임계값 설정
            conf_thresh = confidence_threshold or self.confidence_threshold
            iou_thresh = iou_threshold or self.iou_threshold
            
            # 캐시 키 생성
            cache_key = None
            if enable_cache and isinstance(frame_image, (str, Path)):
                cache_key = f"{frame_image}_{conf_thresh}_{iou_thresh}"
                if cache_key in self.detection_cache:
                    self.logger.debug("캐시된 탐지 결과 반환")
                    return self.detection_cache[cache_key]
            
            start_time = time.time()
            
            # YOLO 추론 실행 (최적화된 파라미터)
            results = self.model.predict(
                source=frame_image,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False,
                device='cuda' if self.gpu_optimizer and self.gpu_optimizer.is_gpu_available else 'cpu',
                half=True if self.gpu_optimizer and self.gpu_optimizer.is_gpu_available else False,
                augment=False,  # TTA 비활성화로 속도 향상
                agnostic_nms=True  # 클래스 무관 NMS
            )
            
            processing_time = time.time() - start_time
            
            # 결과 파싱
            if results and len(results) > 0:
                result = results[0]
                detection_result = self._parse_detection_result(result, processing_time)
                
                # 제품 특화 필터링 적용
                detection_result = self._apply_product_filtering(detection_result)
                
                # 캐시 저장
                if enable_cache and cache_key:
                    self._update_cache(cache_key, detection_result)
                
                self.logger.debug(
                    f"객체 탐지 완료 - {len(detection_result['detections'])}개 객체 탐지, "
                    f"소요시간: {processing_time:.3f}초"
                )
                
                return detection_result
            else:
                return self._get_empty_result(processing_time)
                
        except Exception as e:
            self.logger.error(f"객체 탐지 실패: {str(e)}")
            return self._get_empty_result()
    
    def detect_objects_batch(
        self,
        frame_list: List[Union[str, Path, Any]],
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        배치 프레임에서 객체 탐지
        
        Args:
            frame_list: 입력 이미지 리스트
            confidence_threshold: 신뢰도 임계값
            iou_threshold: IoU 임계값
            
        Returns:
            탐지 결과 리스트
        """
        if self.model is None:
            self.logger.warning("YOLO 모델이 로드되지 않았습니다. 빈 결과 리스트를 반환합니다.")
            return [self._get_empty_result() for _ in frame_list]
        
        try:
            # 임계값 설정
            conf_thresh = confidence_threshold or self.confidence_threshold
            iou_thresh = iou_threshold or self.iou_threshold
            
            start_time = time.time()
            
            # 배치 추론 실행
            results = self.model.predict(
                source=frame_list,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False
            )
            
            total_processing_time = time.time() - start_time
            avg_processing_time = total_processing_time / len(frame_list)
            
            # 결과 파싱
            detection_results = []
            for i, result in enumerate(results):
                detection_result = self._parse_detection_result(result, avg_processing_time)
                detection_results.append(detection_result)
            
            self.logger.info(
                f"배치 객체 탐지 완료 - {len(frame_list)}개 프레임, "
                f"총 소요시간: {total_processing_time:.3f}초, "
                f"평균 프레임당: {avg_processing_time:.3f}초"
            )
            
            return detection_results
            
        except Exception as e:
            self.logger.error(f"배치 객체 탐지 실패: {str(e)}")
            return [self._get_empty_result() for _ in frame_list]
    
    def _parse_detection_result(self, result: Any, processing_time: float) -> Dict[str, Any]:
        """YOLO 결과를 구조화된 딕셔너리로 파싱"""
        detections = []
        
        if result.boxes is not None:
            try:
                boxes_length = len(result.boxes)
                has_detections = boxes_length > 0
            except (TypeError, AttributeError):
                # Mock 객체나 길이를 계산할 수 없는 경우
                has_detections = True
                
            if has_detections:
                boxes = result.boxes
                
                # 바운딩 박스 좌표 (xyxy 형식)
                xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, 'cpu') else boxes.xyxy
                
                # 신뢰도 점수
                confidences = boxes.conf.cpu().numpy() if hasattr(boxes.conf, 'cpu') else boxes.conf
                
                # 클래스 ID
                class_ids = boxes.cls.cpu().numpy() if hasattr(boxes.cls, 'cpu') else boxes.cls
                
                # 클래스 이름
                class_names = [result.names[int(cls_id)] for cls_id in class_ids]
                
                for i in range(len(xyxy)):
                    x1, y1, x2, y2 = xyxy[i]
                    
                    detection = {
                        'class_id': int(class_ids[i]),
                        'class_name': class_names[i],
                        'confidence': float(confidences[i]),
                        'bbox': {
                            'x1': float(x1),
                            'y1': float(y1),
                            'x2': float(x2),
                            'y2': float(y2),
                            'width': float(x2 - x1),
                            'height': float(y2 - y1)
                        }
                    }
                    detections.append(detection)
        
        return {
            'success': True,
            'processing_time': processing_time,
            'model_name': self.model_name,
            'confidence_threshold': self.confidence_threshold,
            'iou_threshold': self.iou_threshold,
            'detections': detections,
            'total_detections': len(detections)
        }
    
    def _get_empty_result(self, processing_time: float = 0.0) -> Dict[str, Any]:
        """빈 결과 딕셔너리 반환"""
        return {
            'success': False,
            'processing_time': processing_time,
            'model_name': self.model_name,
            'confidence_threshold': self.confidence_threshold,
            'iou_threshold': self.iou_threshold,
            'detections': [],
            'total_detections': 0
        }
    
    def filter_by_confidence(
        self, 
        detection_result: Dict[str, Any], 
        min_confidence: float
    ) -> Dict[str, Any]:
        """신뢰도 기반 탐지 결과 필터링"""
        if not detection_result.get('success', False):
            return detection_result
        
        filtered_detections = [
            detection for detection in detection_result['detections']
            if detection['confidence'] >= min_confidence
        ]
        
        filtered_result = detection_result.copy()
        filtered_result['detections'] = filtered_detections
        filtered_result['total_detections'] = len(filtered_detections)
        
        return filtered_result
    
    def filter_by_classes(
        self, 
        detection_result: Dict[str, Any], 
        target_classes: List[str]
    ) -> Dict[str, Any]:
        """특정 클래스만 필터링"""
        if not detection_result.get('success', False):
            return detection_result
        
        filtered_detections = [
            detection for detection in detection_result['detections']
            if detection['class_name'] in target_classes
        ]
        
        filtered_result = detection_result.copy()
        filtered_result['detections'] = filtered_detections
        filtered_result['total_detections'] = len(filtered_detections)
        
        return filtered_result
    
    def get_available_classes(self) -> List[str]:
        """사용 가능한 클래스 목록 반환"""
        if self.model is None:
            return []
        
        try:
            if hasattr(self.model, 'names'):
                return list(self.model.names.values())
            else:
                return []
        except Exception:
            return []
    
    def _apply_product_filtering(self, detection_result: Dict[str, Any]) -> Dict[str, Any]:
        """제품 관련 객체에 대한 특화 필터링 적용"""
        if not detection_result.get('success', False):
            return detection_result
        
        # 제품 관련 클래스 우선순위 적용
        product_related_classes = set()
        for category_classes in self.product_classes.values():
            product_related_classes.update(category_classes)
        
        enhanced_detections = []
        for detection in detection_result['detections']:
            class_name = detection['class_name']
            
            # 제품 관련 클래스는 신뢰도 가중치 적용
            if class_name in product_related_classes:
                detection['confidence'] = min(1.0, detection['confidence'] * 1.1)  # 10% 가중치
                detection['is_product_related'] = True
            else:
                detection['is_product_related'] = False
            
            enhanced_detections.append(detection)
        
        # 제품 관련성과 신뢰도 순으로 정렬
        enhanced_detections.sort(
            key=lambda x: (x['is_product_related'], x['confidence']), 
            reverse=True
        )
        
        detection_result['detections'] = enhanced_detections
        return detection_result
    
    def _update_cache(self, cache_key: str, result: Dict[str, Any]) -> None:
        """캐시 업데이트 (LRU 방식)"""
        if len(self.detection_cache) >= self.cache_max_size:
            # 가장 오래된 항목 제거
            oldest_key = next(iter(self.detection_cache))
            del self.detection_cache[oldest_key]
        
        self.detection_cache[cache_key] = result
    
    def clear_cache(self) -> None:
        """캐시 초기화"""
        self.detection_cache.clear()
        self.logger.debug("객체 탐지 캐시 초기화 완료")
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        return {
            'model_name': self.model_name,
            'model_loaded': self.model is not None,
            'confidence_threshold': self.confidence_threshold,
            'iou_threshold': self.iou_threshold,
            'available_classes': self.get_available_classes(),
            'product_classes': self.product_classes,
            'cache_size': len(self.detection_cache),
            'gpu_optimized': self.gpu_optimizer is not None and self.gpu_optimizer.is_gpu_available
        }