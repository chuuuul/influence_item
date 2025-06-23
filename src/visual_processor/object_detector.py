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
    """YOLO11 기반 객체 탐지 프로세서 클래스"""
    
    def __init__(self, config: Optional[Config] = None, model_name: str = "yolo11n.pt", gpu_optimizer=None):
        """
        객체 탐지 프로세서 초기화
        
        Args:
            config: 설정 객체
            model_name: 사용할 YOLO 모델명 (기본값: yolo11n.pt)
            gpu_optimizer: GPU 최적화 객체 (선택적)
        """
        self.config = config or Config()
        self.model_name = model_name
        self.gpu_optimizer = gpu_optimizer
        self.logger = self._setup_logger()
        self.model = None
        self.confidence_threshold = getattr(self.config, 'YOLO_CONFIDENCE_THRESHOLD', 0.25)
        self.iou_threshold = getattr(self.config, 'YOLO_IOU_THRESHOLD', 0.45)
        
        if self.gpu_optimizer:
            self.logger.info("객체 탐지 GPU 최적화 활성화됨")
        
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
        """YOLO 모델 로딩 (GPU 최적화)"""
        if YOLO is None:
            self.logger.warning("ultralytics 라이브러리가 설치되지 않았습니다. 객체 탐지 기능을 사용할 수 없습니다.")
            return
        
        try:
            start_time = time.time()
            self.logger.info(f"YOLO 모델 로드 시작: {self.model_name}")
            
            # GPU 최적화된 모델 로딩
            self.model = YOLO(self.model_name)
            
            # GPU 사용 가능할 때 모델을 GPU로 이동
            if self.gpu_optimizer and self.gpu_optimizer.is_gpu_available:
                self.model.to('cuda')
                self.logger.info("YOLO 모델이 GPU로 이동되었습니다")
            else:
                self.model.to('cpu')
                self.logger.info("YOLO 모델이 CPU에서 실행됩니다")
            
            load_time = time.time() - start_time
            self.logger.info(f"YOLO 모델 로드 완료 - 소요시간: {load_time:.2f}초")
            
        except Exception as e:
            self.logger.error(f"YOLO 모델 로딩 실패: {str(e)}")
            self.model = None
    
    def detect_objects(
        self, 
        frame_image: Union[str, Path, Any],
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        단일 프레임에서 객체 탐지
        
        Args:
            frame_image: 입력 이미지 (파일 경로, PIL Image, numpy array 등)
            confidence_threshold: 신뢰도 임계값 (None이면 기본값 사용)
            iou_threshold: IoU 임계값 (None이면 기본값 사용)
            
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
            
            start_time = time.time()
            
            # YOLO 추론 실행
            results = self.model.predict(
                source=frame_image,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False
            )
            
            processing_time = time.time() - start_time
            
            # 결과 파싱
            if results and len(results) > 0:
                result = results[0]
                detection_result = self._parse_detection_result(result, processing_time)
                
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
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        return {
            'model_name': self.model_name,
            'model_loaded': self.model is not None,
            'confidence_threshold': self.confidence_threshold,
            'iou_threshold': self.iou_threshold,
            'available_classes': self.get_available_classes()
        }