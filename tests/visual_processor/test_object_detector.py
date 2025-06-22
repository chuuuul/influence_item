"""
ObjectDetector 클래스 단위 테스트

YOLO11 기반 객체 탐지 기능을 테스트합니다.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from pathlib import Path

from src.visual_processor.object_detector import ObjectDetector
from config import Config


class TestObjectDetector(unittest.TestCase):
    """ObjectDetector 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.config = Config()
        
    @patch('src.visual_processor.object_detector.YOLO')
    def test_detector_initialization(self, mock_yolo):
        """객체 탐지기 초기화 테스트"""
        # Mock YOLO 모델
        mock_model = Mock()
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        
        self.assertIsNotNone(detector)
        self.assertEqual(detector.model_name, "yolo11n.pt")
        self.assertEqual(detector.confidence_threshold, 0.25)
        self.assertEqual(detector.iou_threshold, 0.45)
        mock_yolo.assert_called_once_with("yolo11n.pt")
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_detector_with_custom_model(self, mock_yolo):
        """커스텀 모델로 초기화 테스트"""
        mock_model = Mock()
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config, model_name="yolo11s.pt")
        
        self.assertEqual(detector.model_name, "yolo11s.pt")
        mock_yolo.assert_called_once_with("yolo11s.pt")
    
    def test_detector_no_yolo_library(self):
        """YOLO 라이브러리가 없을 때 테스트"""
        with patch('src.visual_processor.object_detector.YOLO', None):
            detector = ObjectDetector(self.config)
            self.assertIsNone(detector.model)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_detect_objects_success(self, mock_yolo):
        """객체 탐지 성공 테스트"""
        # Mock YOLO 모델과 결과
        mock_model = Mock()
        mock_result = Mock()
        
        # Mock boxes 데이터
        mock_boxes = Mock()
        mock_boxes.xyxy.cpu.return_value.numpy.return_value = np.array([[100, 100, 200, 200]])
        mock_boxes.conf.cpu.return_value.numpy.return_value = np.array([0.85])
        mock_boxes.cls.cpu.return_value.numpy.return_value = np.array([0])
        
        mock_result.boxes = mock_boxes
        mock_result.names = {0: 'person'}
        
        mock_model.predict.return_value = [mock_result]
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        result = detector.detect_objects("test_image.jpg")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_detections'], 1)
        self.assertEqual(len(result['detections']), 1)
        
        detection = result['detections'][0]
        self.assertEqual(detection['class_name'], 'person')
        self.assertEqual(detection['confidence'], 0.85)
        self.assertEqual(detection['bbox']['x1'], 100.0)
        self.assertEqual(detection['bbox']['y1'], 100.0)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_detect_objects_no_detection(self, mock_yolo):
        """객체를 탐지하지 못한 경우 테스트"""
        # Mock YOLO 모델과 빈 결과
        mock_model = Mock()
        mock_result = Mock()
        mock_result.boxes = None
        
        mock_model.predict.return_value = [mock_result]
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        result = detector.detect_objects("test_image.jpg")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_detections'], 0)
        self.assertEqual(len(result['detections']), 0)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_detect_objects_batch(self, mock_yolo):
        """배치 객체 탐지 테스트"""
        # Mock YOLO 모델과 결과
        mock_model = Mock()
        mock_result1 = Mock()
        mock_result2 = Mock()
        
        # 첫 번째 결과 설정
        mock_boxes1 = Mock()
        mock_boxes1.xyxy.cpu.return_value.numpy.return_value = np.array([[100, 100, 200, 200]])
        mock_boxes1.conf.cpu.return_value.numpy.return_value = np.array([0.85])
        mock_boxes1.cls.cpu.return_value.numpy.return_value = np.array([0])
        
        mock_result1.boxes = mock_boxes1
        mock_result1.names = {0: 'person'}
        
        # 두 번째 결과 설정 (빈 결과)
        mock_result2.boxes = None
        
        mock_model.predict.return_value = [mock_result1, mock_result2]
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        results = detector.detect_objects_batch(["image1.jpg", "image2.jpg"])
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]['success'])
        self.assertEqual(results[0]['total_detections'], 1)
        self.assertTrue(results[1]['success'])
        self.assertEqual(results[1]['total_detections'], 0)
    
    def test_detect_objects_no_model(self):
        """모델이 로드되지 않은 상태에서 탐지 테스트"""
        with patch('src.visual_processor.object_detector.YOLO', None):
            detector = ObjectDetector(self.config)
            result = detector.detect_objects("test_image.jpg")
            
            self.assertFalse(result['success'])
            self.assertEqual(result['total_detections'], 0)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_filter_by_confidence(self, mock_yolo):
        """신뢰도 기반 필터링 테스트"""
        mock_yolo.return_value = Mock()
        detector = ObjectDetector(self.config)
        
        # 테스트 탐지 결과 생성
        detection_result = {
            'success': True,
            'detections': [
                {'class_name': 'person', 'confidence': 0.9},
                {'class_name': 'car', 'confidence': 0.5},
                {'class_name': 'bike', 'confidence': 0.3}
            ],
            'total_detections': 3
        }
        
        filtered_result = detector.filter_by_confidence(detection_result, 0.6)
        
        self.assertEqual(filtered_result['total_detections'], 1)
        self.assertEqual(filtered_result['detections'][0]['class_name'], 'person')
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_filter_by_classes(self, mock_yolo):
        """클래스 기반 필터링 테스트"""
        mock_yolo.return_value = Mock()
        detector = ObjectDetector(self.config)
        
        # 테스트 탐지 결과 생성
        detection_result = {
            'success': True,
            'detections': [
                {'class_name': 'person', 'confidence': 0.9},
                {'class_name': 'car', 'confidence': 0.8},
                {'class_name': 'bike', 'confidence': 0.7}
            ],
            'total_detections': 3
        }
        
        filtered_result = detector.filter_by_classes(detection_result, ['person', 'bike'])
        
        self.assertEqual(filtered_result['total_detections'], 2)
        class_names = [det['class_name'] for det in filtered_result['detections']]
        self.assertIn('person', class_names)
        self.assertIn('bike', class_names)
        self.assertNotIn('car', class_names)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_get_available_classes(self, mock_yolo):
        """사용 가능한 클래스 목록 반환 테스트"""
        mock_model = Mock()
        mock_model.names = {0: 'person', 1: 'car', 2: 'bike'}
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        classes = detector.get_available_classes()
        
        self.assertEqual(len(classes), 3)
        self.assertIn('person', classes)
        self.assertIn('car', classes)
        self.assertIn('bike', classes)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_get_model_info(self, mock_yolo):
        """모델 정보 반환 테스트"""
        mock_model = Mock()
        mock_model.names = {0: 'person', 1: 'car'}
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        info = detector.get_model_info()
        
        self.assertEqual(info['model_name'], 'yolo11n.pt')
        self.assertTrue(info['model_loaded'])
        self.assertEqual(info['confidence_threshold'], 0.25)
        self.assertEqual(info['iou_threshold'], 0.45)
        self.assertEqual(len(info['available_classes']), 2)
    
    @patch('src.visual_processor.object_detector.YOLO')
    def test_detect_objects_with_custom_thresholds(self, mock_yolo):
        """커스텀 임계값으로 객체 탐지 테스트"""
        # Mock YOLO 모델
        mock_model = Mock()
        mock_result = Mock()
        mock_result.boxes = None
        
        mock_model.predict.return_value = [mock_result]
        mock_yolo.return_value = mock_model
        
        detector = ObjectDetector(self.config)
        result = detector.detect_objects(
            "test_image.jpg", 
            confidence_threshold=0.8, 
            iou_threshold=0.6
        )
        
        # predict 호출 시 커스텀 임계값이 사용되었는지 확인
        mock_model.predict.assert_called_once()
        call_kwargs = mock_model.predict.call_args[1]
        self.assertEqual(call_kwargs['conf'], 0.8)
        self.assertEqual(call_kwargs['iou'], 0.6)


if __name__ == '__main__':
    unittest.main()