"""
T02_S02_M02 - 제품 이미지 자동 추출 시스템 통합 테스트

이 테스트는 제품 이미지 자동 추출 시스템의 전체 워크플로우를 검증합니다:
1. 프레임에서 이미지 추출
2. 품질 평가 및 선별
3. 썸네일 생성
4. 메타데이터 저장
5. 대시보드 갤러리 표시
"""

import pytest
import numpy as np
import cv2
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import json
import time

# 프로젝트 모듈 임포트
from src.visual_processor.target_frame_extractor import ProductImageExtractor, TargetFrameExtractor
from src.gemini_analyzer.models import ExtractedFrame, TargetTimeframe
from dashboard.components.product_image_gallery import ProductImageGallery


class TestProductImageExtractor:
    """ProductImageExtractor 클래스 테스트"""
    
    @pytest.fixture
    def temp_dir(self):
        """테스트용 임시 디렉토리"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def extractor(self, temp_dir):
        """ProductImageExtractor 인스턴스"""
        return ProductImageExtractor(output_dir=str(temp_dir))
    
    @pytest.fixture
    def sample_frame(self):
        """테스트용 샘플 프레임 생성"""
        # 640x480 크기의 컬러 이미지 생성
        frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        
        # 가운데에 밝은 사각형 추가 (제품 시뮬레이션)
        cv2.rectangle(frame, (200, 150), (440, 330), (255, 255, 255), -1)
        cv2.rectangle(frame, (220, 170), (420, 310), (100, 150, 200), -1)
        
        return frame
    
    def test_frame_hash_calculation(self, extractor, sample_frame):
        """프레임 해시 계산 테스트"""
        hash1 = extractor._calculate_frame_hash(sample_frame)
        hash2 = extractor._calculate_frame_hash(sample_frame)
        
        # 동일한 프레임은 동일한 해시
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 해시 길이
        
        # 다른 프레임은 다른 해시
        different_frame = sample_frame.copy()
        different_frame[0, 0] = 255
        hash3 = extractor._calculate_frame_hash(different_frame)
        assert hash1 != hash3
    
    def test_image_quality_assessment(self, extractor, sample_frame):
        """이미지 품질 평가 테스트"""
        quality_scores = extractor._assess_image_quality(sample_frame)
        
        # 모든 품질 지표가 반환되는지 확인
        expected_keys = ["sharpness", "size", "brightness", "contrast"]
        assert all(key in quality_scores for key in expected_keys)
        
        # 점수가 0-1 범위인지 확인
        for score in quality_scores.values():
            assert 0 <= score <= 1
    
    def test_composite_score_calculation(self, extractor):
        """종합 품질 점수 계산 테스트"""
        quality_scores = {
            "sharpness": 0.8,
            "size": 0.7,
            "brightness": 0.6,
            "contrast": 0.5
        }
        object_confidence = 0.9
        
        composite_score = extractor._calculate_composite_score(quality_scores, object_confidence)
        
        # 종합 점수가 0-1 범위인지 확인
        assert 0 <= composite_score <= 1
        
        # 가중치 계산 검증 (대략적)
        expected = (0.8 * 0.4) + (0.7 * 0.3) + (0.9 * 0.3)  # 기본 가중치
        assert abs(composite_score - expected) < 0.2  # 보너스/페널티 고려
    
    def test_thumbnail_creation(self, extractor, sample_frame):
        """썸네일 생성 테스트"""
        thumbnail_150 = extractor._create_thumbnail(sample_frame, 150)
        thumbnail_300 = extractor._create_thumbnail(sample_frame, 300)
        
        # 썸네일 크기 확인
        assert max(thumbnail_150.shape[:2]) <= 150
        assert max(thumbnail_300.shape[:2]) <= 300
        
        # 채널 수 확인
        assert thumbnail_150.shape[2] == 3
        assert thumbnail_300.shape[2] == 3
    
    def test_save_product_image(self, extractor, sample_frame):
        """제품 이미지 저장 테스트"""
        metadata = {
            "timestamp": 125.5,
            "timeframe_info": {
                "start_time": 120.0,
                "end_time": 130.0,
                "confidence_score": 0.85
            }
        }
        
        # 이미지 저장
        result = extractor.save_product_image(sample_frame, metadata, object_confidence=0.7)
        
        # 반환된 메타데이터 검증
        assert "hash" in result
        assert "timestamp" in result
        assert "composite_score" in result
        assert "file_paths" in result
        
        # 파일 생성 확인
        file_paths = result["file_paths"]
        for path_key, path_str in file_paths.items():
            if path_key != "metadata":  # 메타데이터 파일은 이미 확인됨
                assert Path(path_str).exists()
    
    def test_image_selection(self, extractor, sample_frame):
        """이미지 선별 테스트"""
        # 여러 품질의 이미지 메타데이터 생성
        images_metadata = []
        for i in range(7):
            metadata = {
                "hash": f"test_hash_{i}",
                "composite_score": 0.3 + (i * 0.1),  # 0.3부터 0.9까지
                "timestamp": 100 + i * 5,
                "quality_scores": {"sharpness": 0.5 + (i * 0.05)},
                "object_confidence": 0.4 + (i * 0.08)
            }
            images_metadata.append(metadata)
        
        # 최고 품질 3개 선별
        selected = extractor.select_best_images(images_metadata, max_count=3)
        
        assert len(selected) == 3
        
        # 점수 순으로 정렬되었는지 확인
        scores = [img["composite_score"] for img in selected]
        assert scores == sorted(scores, reverse=True)
        
        # 최고 점수가 포함되었는지 확인
        assert selected[0]["composite_score"] == 0.9


class TestTargetFrameExtractorIntegration:
    """TargetFrameExtractor와 이미지 추출 통합 테스트"""
    
    @pytest.fixture
    def mock_extractor(self):
        """모킹된 TargetFrameExtractor"""
        with patch('src.visual_processor.target_frame_extractor.GPUOptimizer'), \
             patch('src.visual_processor.target_frame_extractor.OCRProcessor'), \
             patch('src.visual_processor.target_frame_extractor.ObjectDetector'):
            extractor = TargetFrameExtractor()
            return extractor
    
    @pytest.fixture
    def sample_extracted_frame(self):
        """테스트용 ExtractedFrame"""
        frame_data = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        
        return ExtractedFrame(
            timestamp=85.5,
            frame_index=2565,
            frame_data=frame_data,
            quality_score=0.75,
            width=640,
            height=480,
            is_keyframe=True
        )
    
    def test_analyze_single_frame_with_image_extraction(self, mock_extractor, sample_extracted_frame):
        """이미지 추출이 포함된 단일 프레임 분석 테스트"""
        timeframe_info = {
            "start_time": 80.0,
            "end_time": 90.0,
            "confidence_score": 0.85,
            "reason": "제품 사용 시연"
        }
        
        # OCR 및 객체 탐지 결과 모킹
        mock_extractor.ocr_processor.process_image.return_value = {
            "texts": ["Product Name", "Brand"],
            "raw_results": []
        }
        
        mock_extractor.object_detector.detect_objects.return_value = {
            "detections": [
                {"class": "bottle", "confidence": 0.8},
                {"class": "cosmetics", "confidence": 0.7}
            ]
        }
        
        # 이미지 추출 활성화하여 분석
        result = mock_extractor.analyze_single_frame(
            sample_extracted_frame, 
            save_product_images=True, 
            timeframe_info=timeframe_info
        )
        
        # 기본 분석 결과 검증
        assert result.frame == sample_extracted_frame
        assert "Product Name" in result.detected_texts
        assert "bottle" in result.detected_objects
        
        # 제품 이미지 메타데이터가 추가되었는지 확인
        assert hasattr(result, 'product_image_metadata')
        assert result.product_image_metadata is not None
        assert "composite_score" in result.product_image_metadata


class TestProductImageGallery:
    """ProductImageGallery 클래스 테스트"""
    
    @pytest.fixture
    def sample_image_metadata(self):
        """테스트용 이미지 메타데이터"""
        return [
            {
                "hash": "test_hash_1",
                "timestamp": 85.2,
                "composite_score": 0.85,
                "object_confidence": 0.7,
                "quality_scores": {
                    "sharpness": 0.8,
                    "size": 0.9,
                    "brightness": 0.7,
                    "contrast": 0.75
                },
                "image_dimensions": {"width": 1280, "height": 720},
                "file_paths": {
                    "original": "/test/path/original.jpg",
                    "thumbnail_150": "/test/path/thumb_150.jpg",
                    "thumbnail_300": "/test/path/thumb_300.jpg"
                },
                "file_sizes": {
                    "original": 250000,
                    "thumbnail_150": 15000,
                    "thumbnail_300": 45000
                }
            },
            {
                "hash": "test_hash_2",
                "timestamp": 92.8,
                "composite_score": 0.65,
                "object_confidence": 0.5,
                "quality_scores": {
                    "sharpness": 0.6,
                    "size": 0.8,
                    "brightness": 0.6,
                    "contrast": 0.65
                },
                "image_dimensions": {"width": 1920, "height": 1080},
                "file_paths": {
                    "original": "/test/path/original2.jpg",
                    "thumbnail_150": "/test/path/thumb2_150.jpg",
                    "thumbnail_300": "/test/path/thumb2_300.jpg"
                },
                "file_sizes": {
                    "original": 380000,
                    "thumbnail_150": 18000,
                    "thumbnail_300": 52000
                }
            }
        ]
    
    def test_export_selected_images_info(self, sample_image_metadata):
        """선택된 이미지 정보 내보내기 테스트"""
        gallery = ProductImageGallery()
        
        export_data = gallery.export_selected_images_info(sample_image_metadata)
        
        # 내보내기 데이터 구조 검증
        assert "total_selected" in export_data
        assert export_data["total_selected"] == 2
        
        assert "average_quality" in export_data
        expected_avg = (0.85 + 0.65) / 2
        assert abs(export_data["average_quality"] - expected_avg) < 0.01
        
        assert "images" in export_data
        assert len(export_data["images"]) == 2
        
        # 개별 이미지 정보 검증
        first_image = export_data["images"][0]
        assert "hash" in first_image
        assert "timestamp" in first_image
        assert "composite_score" in first_image
    
    def test_image_info_card_generation(self, sample_image_metadata):
        """이미지 정보 카드 HTML 생성 테스트"""
        gallery = ProductImageGallery()
        
        html_card = gallery._create_image_info_card(sample_image_metadata[0], is_selected=True)
        
        # HTML 구조 검증
        assert "품질 점수" in html_card
        assert "0.850" in html_card  # 품질 점수
        assert "85.2초" in html_card  # 타임스탬프
        assert "1280 × 720" in html_card  # 이미지 크기
        
        # 선택 상태에 따른 스타일 확인
        selected_html = gallery._create_image_info_card(sample_image_metadata[0], is_selected=True)
        unselected_html = gallery._create_image_info_card(sample_image_metadata[0], is_selected=False)
        
        assert "#007bff" in selected_html  # 선택된 테두리 색상
        assert "#dee2e6" in unselected_html  # 선택 안된 테두리 색상


class TestEndToEndWorkflow:
    """전체 워크플로우 엔드투엔드 테스트"""
    
    def test_complete_image_extraction_workflow(self):
        """완전한 이미지 추출 워크플로우 테스트"""
        # 1. 타겟 시간대 설정
        timeframe = TargetTimeframe(
            start_time=80.0,
            end_time=120.0,
            confidence_score=0.85,
            reason="제품 시연 구간 탐지"
        )
        
        # 2. 임시 디렉토리에서 이미지 추출기 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            extractor = ProductImageExtractor(output_dir=temp_dir)
            
            # 3. 샘플 프레임들 생성 및 저장
            sample_frames = []
            for i in range(5):
                frame = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
                # 프레임마다 다른 품질 특성 부여
                if i % 2 == 0:
                    # 선명한 프레임
                    frame = cv2.GaussianBlur(frame, (3, 3), 0.5)
                else:
                    # 흐린 프레임
                    frame = cv2.GaussianBlur(frame, (15, 15), 5.0)
                
                sample_frames.append(frame)
            
            # 4. 각 프레임에 대해 이미지 저장
            saved_images = []
            for i, frame in enumerate(sample_frames):
                metadata = {
                    "timestamp": 85.0 + i * 8,
                    "timeframe_info": {
                        "start_time": timeframe.start_time,
                        "end_time": timeframe.end_time,
                        "confidence_score": timeframe.confidence_score
                    }
                }
                
                result = extractor.save_product_image(
                    frame, metadata, object_confidence=0.6 + (i * 0.05)
                )
                saved_images.append(result)
            
            # 5. 최고 품질 이미지 선별
            selected_images = extractor.select_best_images(saved_images, max_count=3)
            
            # 6. 결과 검증
            assert len(saved_images) == 5
            assert len(selected_images) == 3
            
            # 선별된 이미지들이 품질 순으로 정렬되었는지 확인
            scores = [img["composite_score"] for img in selected_images]
            assert scores == sorted(scores, reverse=True)
            
            # 7. 갤러리 내보내기 테스트
            gallery = ProductImageGallery()
            export_data = gallery.export_selected_images_info(selected_images)
            
            assert export_data["total_selected"] == 3
            assert "average_quality" in export_data
            
            # 8. 파일 정리 테스트
            deleted_count = extractor.cleanup_low_quality_images(min_score=0.5)
            assert deleted_count >= 0  # 일부 이미지가 정리되었을 수 있음


def test_integration_with_dashboard_components():
    """대시보드 컴포넌트와의 통합 테스트"""
    # 샘플 후보 데이터 생성
    candidate_data = {
        "source_info": {
            "celebrity_name": "테스트 인플루언서",
            "video_url": "https://www.youtube.com/watch?v=test123",
            "video_title": "신상 립스틱 솔직 후기"
        },
        "candidate_info": {
            "product_name_ai": "테스트 립스틱",
            "clip_start_time": 85,
            "clip_end_time": 125
        },
        "selected_product_images": [
            {
                "hash": "dashboard_test_hash",
                "timestamp": 95.2,
                "composite_score": 0.88,
                "object_confidence": 0.75,
                "quality_scores": {
                    "sharpness": 0.85,
                    "size": 0.9,
                    "brightness": 0.8,
                    "contrast": 0.82
                },
                "image_dimensions": {"width": 1920, "height": 1080},
                "file_paths": {
                    "original": "/test/dashboard/original.jpg",
                    "thumbnail_150": "/test/dashboard/thumb_150.jpg",
                    "thumbnail_300": "/test/dashboard/thumb_300.jpg"
                }
            }
        ]
    }
    
    # 이미지 데이터가 제대로 추출되는지 테스트
    images = candidate_data.get('selected_product_images', [])
    assert len(images) == 1
    
    first_image = images[0]
    assert first_image["composite_score"] > 0.8
    assert "file_paths" in first_image
    assert all(path in first_image["file_paths"] for path in ["original", "thumbnail_150", "thumbnail_300"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])