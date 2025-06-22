"""
타겟 프레임 추출기 테스트

T05_S02 - 타겟 시간대 시각 분석 시스템의 테스트 케이스들
"""

import pytest
import numpy as np
import tempfile
import os
try:
    import cv2
except ImportError:
    cv2 = None
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.visual_processor.target_frame_extractor import TargetFrameExtractor
from src.gemini_analyzer.models import (
    TargetTimeframe, ExtractedFrame, FrameAnalysisResult, 
    TargetFrameAnalysisResult, VideoMetadata, FrameExtractionConfig
)


class TestTargetFrameExtractor:
    """타겟 프레임 추출기 테스트 클래스"""
    
    @pytest.fixture
    def mock_config(self):
        """모킹된 설정 객체"""
        config = Mock()
        config.LOG_LEVEL = "INFO"
        config.YOLO_CONFIDENCE_THRESHOLD = 0.25
        config.YOLO_IOU_THRESHOLD = 0.45
        return config
    
    @pytest.fixture
    def target_timeframe(self):
        """테스트용 타겟 시간대"""
        return TargetTimeframe(
            start_time=30.0,
            end_time=45.0,
            reason="제품 사용 언급",
            confidence_score=0.85
        )
    
    @pytest.fixture
    def extraction_config(self):
        """프레임 추출 설정"""
        return FrameExtractionConfig(
            sampling_interval=2.0,
            max_frames_per_timeframe=10,
            min_quality_threshold=0.3,
            prefer_keyframes=True
        )
    
    @pytest.fixture
    def extractor(self, mock_config):
        """타겟 프레임 추출기 인스턴스"""
        with patch('src.visual_processor.target_frame_extractor.GPUOptimizer'), \
             patch('src.visual_processor.target_frame_extractor.OCRProcessor'), \
             patch('src.visual_processor.target_frame_extractor.ObjectDetector'):
            return TargetFrameExtractor(config=mock_config)
    
    def test_extractor_initialization(self, extractor):
        """추출기 초기화 테스트"""
        assert extractor is not None
        assert extractor.logger is not None
        assert extractor.extraction_config is not None
        
        # 기본 설정값 확인
        assert extractor.extraction_config.sampling_interval == 1.0
        assert extractor.extraction_config.max_frames_per_timeframe == 30
        assert extractor.extraction_config.min_quality_threshold == 0.5
    
    @patch('cv2.VideoCapture')
    def test_extract_video_metadata_success(self, mock_cv2_cap, extractor):
        """영상 메타데이터 추출 성공 테스트"""
        # Mock VideoCapture 설정
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 1800,
            cv2.CAP_PROP_FRAME_WIDTH: 1920,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080,
            cv2.CAP_PROP_FOURCC: 1635148593.0  # 'MP4V'
        }.get(prop, 0)
        mock_cv2_cap.return_value = mock_cap
        
        # 메타데이터 추출 실행
        metadata = extractor.extract_video_metadata("test_video.mp4")
        
        # 검증
        assert isinstance(metadata, VideoMetadata)
        assert metadata.duration_seconds == 60.0  # 1800 frames / 30 fps
        assert metadata.fps == 30.0
        assert metadata.total_frames == 1800
        assert metadata.width == 1920
        assert metadata.height == 1080
        
        mock_cap.release.assert_called_once()
    
    @patch('cv2.VideoCapture')
    def test_extract_video_metadata_failure(self, mock_cv2_cap, extractor):
        """영상 메타데이터 추출 실패 테스트"""
        # Mock VideoCapture - 파일 열기 실패
        mock_cap = Mock()
        mock_cap.isOpened.return_value = False
        mock_cv2_cap.return_value = mock_cap
        
        # 예외 발생 확인
        with pytest.raises(ValueError, match="영상 파일을 열 수 없습니다"):
            extractor.extract_video_metadata("invalid_video.mp4")
    
    def test_assess_frame_quality_laplacian(self, extractor):
        """프레임 품질 평가 테스트 (Laplacian 방법)"""
        # 테스트 프레임 생성 (선명한 이미지)
        sharp_frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        # 가장자리 추가로 더 선명하게 만들기
        sharp_frame[40:60, 40:60] = [255, 255, 255]
        sharp_frame[45:55, 45:55] = [0, 0, 0]
        
        quality_score = extractor.assess_frame_quality(sharp_frame, "laplacian")
        
        assert 0.0 <= quality_score <= 1.0
        assert isinstance(quality_score, float)
    
    def test_assess_frame_quality_sobel(self, extractor):
        """프레임 품질 평가 테스트 (Sobel 방법)"""
        frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        quality_score = extractor.assess_frame_quality(frame, "sobel")
        
        assert 0.0 <= quality_score <= 1.0
        assert isinstance(quality_score, float)
    
    def test_assess_frame_quality_brightness(self, extractor):
        """프레임 품질 평가 테스트 (기본 밝기 방법)"""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)  # 중간 밝기
        
        quality_score = extractor.assess_frame_quality(frame, "brightness")
        
        assert abs(quality_score - 0.5) < 0.1  # 중간 밝기이므로 약 0.5 예상
    
    @patch('cv2.VideoCapture')
    def test_extract_frames_from_timeframe_success(self, mock_cv2_cap, extractor, target_timeframe, extraction_config):
        """타겟 시간대 프레임 추출 성공 테스트"""
        # Mock VideoCapture 설정
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0  # FPS
        
        # Mock frames
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)
        mock_cv2_cap.return_value = mock_cap
        
        # 프레임 추출 실행
        frames = extractor.extract_frames_from_timeframe(
            "test_video.mp4", target_timeframe, extraction_config
        )
        
        # 검증
        assert len(frames) > 0
        assert all(isinstance(frame, ExtractedFrame) for frame in frames)
        
        # 첫 번째 프레임 검증
        first_frame = frames[0]
        assert first_frame.timestamp >= target_timeframe.start_time
        assert first_frame.timestamp <= target_timeframe.end_time
        assert first_frame.width == 640
        assert first_frame.height == 480
        assert 0.0 <= first_frame.quality_score <= 1.0
        
        mock_cap.release.assert_called_once()
    
    @patch('cv2.VideoCapture')
    def test_extract_frames_from_timeframe_no_frames(self, mock_cv2_cap, extractor, target_timeframe):
        """프레임 추출 시 추출된 프레임이 없는 경우 테스트"""
        # Mock VideoCapture - 프레임 읽기 실패
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0
        mock_cap.read.return_value = (False, None)  # 읽기 실패
        mock_cv2_cap.return_value = mock_cap
        
        frames = extractor.extract_frames_from_timeframe("test_video.mp4", target_timeframe)
        
        assert len(frames) == 0
    
    def test_analyze_single_frame_success(self, extractor):
        """단일 프레임 분석 성공 테스트"""
        # 테스트 프레임 생성
        test_frame_data = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        test_frame = ExtractedFrame(
            timestamp=35.5,
            frame_index=1065,
            frame_data=test_frame_data,
            quality_score=0.8,
            width=640,
            height=480
        )
        
        # Mock OCR와 객체 탐지 결과
        extractor.ocr_processor.process_image.return_value = {
            'texts': ['브랜드명', '제품명'],
            'raw_results': [{'text': '브랜드명', 'confidence': 0.9}]
        }
        
        extractor.object_detector.detect_objects.return_value = {
            'detections': [{'class': 'bottle', 'confidence': 0.8}]
        }
        
        # 분석 실행
        result = extractor.analyze_single_frame(test_frame)
        
        # 검증
        assert isinstance(result, FrameAnalysisResult)
        assert result.frame == test_frame
        assert len(result.detected_texts) == 2
        assert len(result.detected_objects) == 1
        assert result.processing_time_ms > 0
    
    def test_analyze_single_frame_with_errors(self, extractor):
        """단일 프레임 분석 시 에러 처리 테스트"""
        test_frame = ExtractedFrame(
            timestamp=35.5,
            frame_index=1065,
            frame_data=None,  # 프레임 데이터 없음
            quality_score=0.8,
            width=640,
            height=480
        )
        
        # OCR와 객체 탐지에서 예외 발생
        extractor.ocr_processor.process_image.side_effect = Exception("OCR 오류")
        extractor.object_detector.detect_objects.side_effect = Exception("객체 탐지 오류")
        
        result = extractor.analyze_single_frame(test_frame)
        
        # 에러가 발생해도 결과 객체는 반환되어야 함
        assert isinstance(result, FrameAnalysisResult)
        assert result.frame == test_frame
        assert len(result.detected_texts) == 0
        assert len(result.detected_objects) == 0
    
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.extract_frames_from_timeframe')
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.analyze_single_frame')
    def test_analyze_target_timeframe_success(self, mock_analyze_frame, mock_extract_frames, 
                                            extractor, target_timeframe):
        """타겟 시간대 전체 분석 성공 테스트"""
        # Mock 프레임 데이터
        test_frames = [
            ExtractedFrame(
                timestamp=32.0, frame_index=960, frame_data=np.zeros((480, 640, 3)),
                quality_score=0.8, width=640, height=480
            ),
            ExtractedFrame(
                timestamp=34.0, frame_index=1020, frame_data=np.zeros((480, 640, 3)),
                quality_score=0.9, width=640, height=480
            )
        ]
        mock_extract_frames.return_value = test_frames
        
        # Mock 분석 결과
        mock_frame_results = []
        for frame in test_frames:
            mock_result = Mock(spec=FrameAnalysisResult)
            mock_result.detected_texts = ['텍스트1', '텍스트2']
            mock_result.detected_objects = ['객체1']
            mock_frame_results.append(mock_result)
        
        mock_analyze_frame.side_effect = mock_frame_results
        
        # GPU 최적화 컨텍스트 Mock
        extractor.gpu_optimizer.optimized_context.return_value.__enter__ = Mock()
        extractor.gpu_optimizer.optimized_context.return_value.__exit__ = Mock()
        
        # 분석 실행
        result = extractor.analyze_target_timeframe("test_video.mp4", target_timeframe)
        
        # 검증
        assert isinstance(result, TargetFrameAnalysisResult)
        assert result.target_timeframe == target_timeframe
        assert result.total_frames_extracted == 2
        assert result.successful_analyses == 2
        assert len(result.frame_results) == 2
        assert 'analysis_success_rate' in result.processing_stats
        assert result.total_processing_time > 0
    
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.extract_frames_from_timeframe')
    def test_analyze_target_timeframe_no_frames(self, mock_extract_frames, extractor, target_timeframe):
        """타겟 시간대 분석 시 추출된 프레임이 없는 경우 테스트"""
        mock_extract_frames.return_value = []  # 빈 프레임 리스트
        
        with pytest.raises(ValueError, match="추출된 프레임이 없습니다"):
            extractor.analyze_target_timeframe("test_video.mp4", target_timeframe)
    
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.extract_video_metadata')
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.analyze_target_timeframe')
    def test_analyze_multiple_timeframes_success(self, mock_analyze_timeframe, mock_extract_metadata, extractor):
        """다중 타겟 시간대 분석 성공 테스트"""
        # Mock 메타데이터
        mock_metadata = VideoMetadata(
            file_path="test_video.mp4",
            duration_seconds=120.0,
            fps=30.0,
            total_frames=3600,
            width=1920,
            height=1080
        )
        mock_extract_metadata.return_value = mock_metadata
        
        # Mock 분석 결과들
        mock_results = []
        timeframes = [
            TargetTimeframe(start_time=10.0, end_time=20.0, reason="구간1", confidence_score=0.8),
            TargetTimeframe(start_time=30.0, end_time=40.0, reason="구간2", confidence_score=0.9),
        ]
        
        for timeframe in timeframes:
            mock_result = Mock(spec=TargetFrameAnalysisResult)
            mock_result.target_timeframe = timeframe
            mock_results.append(mock_result)
        
        mock_analyze_timeframe.side_effect = mock_results
        
        # 다중 분석 실행
        results = extractor.analyze_multiple_timeframes("test_video.mp4", timeframes)
        
        # 검증
        assert len(results) == 2
        assert all(isinstance(result, TargetFrameAnalysisResult) for result in results)
        assert mock_analyze_timeframe.call_count == 2
    
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.extract_video_metadata')
    @patch('src.visual_processor.target_frame_extractor.TargetFrameExtractor.analyze_target_timeframe')
    def test_analyze_multiple_timeframes_partial_failure(self, mock_analyze_timeframe, 
                                                        mock_extract_metadata, extractor):
        """다중 분석 시 일부 실패 테스트"""
        # Mock 메타데이터
        mock_metadata = VideoMetadata(
            file_path="test_video.mp4",
            duration_seconds=120.0,
            fps=30.0,
            total_frames=3600,
            width=1920,
            height=1080
        )
        mock_extract_metadata.return_value = mock_metadata
        
        timeframes = [
            TargetTimeframe(start_time=10.0, end_time=20.0, reason="구간1", confidence_score=0.8),
            TargetTimeframe(start_time=30.0, end_time=40.0, reason="구간2", confidence_score=0.9),
        ]
        
        # 첫 번째는 성공, 두 번째는 실패
        success_result = Mock(spec=TargetFrameAnalysisResult)
        mock_analyze_timeframe.side_effect = [success_result, Exception("분석 실패")]
        
        results = extractor.analyze_multiple_timeframes("test_video.mp4", timeframes)
        
        # 성공한 것만 반환되어야 함
        assert len(results) == 1
        assert results[0] == success_result
    
    def test_get_analysis_info(self, extractor):
        """분석기 정보 반환 테스트"""
        info = extractor.get_analysis_info()
        
        assert isinstance(info, dict)
        assert info['component'] == 'TargetFrameExtractor'
        assert 'version' in info
        assert 'gpu_optimizer_enabled' in info
        assert 'extraction_config' in info
        assert 'supported_video_formats' in info
        assert 'quality_assessment_methods' in info


class TestFrameExtractionConfig:
    """프레임 추출 설정 테스트 클래스"""
    
    def test_default_config(self):
        """기본 설정 테스트"""
        config = FrameExtractionConfig()
        
        assert config.sampling_interval == 1.0
        assert config.max_frames_per_timeframe == 30
        assert config.min_quality_threshold == 0.5
        assert config.prefer_keyframes == True
        assert config.quality_assessment_method == "laplacian"
    
    def test_custom_config(self):
        """커스텀 설정 테스트"""
        config = FrameExtractionConfig(
            sampling_interval=2.5,
            max_frames_per_timeframe=20,
            min_quality_threshold=0.7,
            prefer_keyframes=False,
            quality_assessment_method="sobel"
        )
        
        assert config.sampling_interval == 2.5
        assert config.max_frames_per_timeframe == 20
        assert config.min_quality_threshold == 0.7
        assert config.prefer_keyframes == False
        assert config.quality_assessment_method == "sobel"
    
    def test_invalid_sampling_interval(self):
        """잘못된 샘플링 간격 테스트"""
        with pytest.raises(ValueError, match="샘플링 간격은 0보다 커야 합니다"):
            FrameExtractionConfig(sampling_interval=0.0)
        
        with pytest.raises(ValueError, match="샘플링 간격이 너무 큽니다"):
            FrameExtractionConfig(sampling_interval=15.0)


class TestDataModels:
    """데이터 모델 테스트 클래스"""
    
    def test_target_timeframe_valid(self):
        """유효한 타겟 시간대 테스트"""
        timeframe = TargetTimeframe(
            start_time=10.0,
            end_time=20.0,
            reason="제품 언급",
            confidence_score=0.85
        )
        
        assert timeframe.start_time == 10.0
        assert timeframe.end_time == 20.0
        assert timeframe.confidence_score == 0.85
    
    def test_target_timeframe_invalid_time_order(self):
        """잘못된 시간 순서 테스트"""
        with pytest.raises(ValueError, match="종료 시간이 시작 시간보다 늦어야 합니다"):
            TargetTimeframe(
                start_time=20.0,
                end_time=10.0,  # 시작 시간보다 빠름
                reason="잘못된 시간",
                confidence_score=0.5
            )
    
    def test_extracted_frame_model(self):
        """추출된 프레임 모델 테스트"""
        frame_data = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        frame = ExtractedFrame(
            timestamp=35.5,
            frame_index=1065,
            frame_data=frame_data,
            quality_score=0.8,
            width=640,
            height=480,
            is_keyframe=True
        )
        
        assert frame.timestamp == 35.5
        assert frame.frame_index == 1065
        assert frame.quality_score == 0.8
        assert frame.is_keyframe == True
        assert frame.frame_data.shape == (480, 640, 3)
    
    def test_video_metadata_model(self):
        """영상 메타데이터 모델 테스트"""
        metadata = VideoMetadata(
            file_path="/path/to/video.mp4",
            duration_seconds=120.0,
            fps=30.0,
            total_frames=3600,
            width=1920,
            height=1080,
            codec="H264"
        )
        
        assert metadata.duration_seconds == 120.0
        assert metadata.total_frames == 3600
        assert metadata.fps == 30.0
    
    def test_video_metadata_frame_count_validation(self):
        """영상 메타데이터 프레임 수 검증 테스트"""
        with pytest.raises(ValueError, match="총 프레임 수.*가 예상값.*와 차이가 큽니다"):
            VideoMetadata(
                file_path="/path/to/video.mp4",
                duration_seconds=60.0,  # 60초
                fps=30.0,               # 30fps
                total_frames=1000,      # 예상: 1800, 실제: 1000 (차이가 큼)
                width=1920,
                height=1080
            )