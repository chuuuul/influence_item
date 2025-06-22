"""
Audio-Visual Fusion 통합 테스트

전체 파이프라인과의 연동을 포함한 통합 테스트 케이스들입니다.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.gemini_analyzer.audio_visual_fusion import AudioVisualFusion
from src.gemini_analyzer.pipeline import AIAnalysisPipeline
from src.gemini_analyzer.models import FusedAnalysisResult
from src.visual_processor.ocr_processor import OCRProcessor
from config import Config


class TestAudioVisualIntegration:
    """Audio-Visual Fusion 통합 테스트"""
    
    @pytest.fixture
    def config(self):
        """테스트용 설정 객체"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = 'DEBUG'
        config.FUSION_TIME_TOLERANCE = 2.0
        config.TEXT_SIMILARITY_THRESHOLD = 0.6
        config.FUSION_CONFIDENCE_THRESHOLD = 0.7
        config.OCR_CONFIDENCE_THRESHOLD = 0.5
        config.USE_GPU = False
        return config
    
    @pytest.fixture
    def fusion_engine(self, config):
        """AudioVisualFusion 인스턴스"""
        return AudioVisualFusion(config)
    
    @pytest.fixture
    def mock_pipeline(self, config):
        """모의 AI 파이프라인"""
        pipeline = Mock(spec=AIAnalysisPipeline)
        pipeline.config = config
        return pipeline
    
    @pytest.fixture
    def sample_whisper_output(self):
        """실제 Whisper 출력 형태의 샘플 데이터"""
        return [
            {
                "start": 45.2,
                "end": 50.8,
                "text": "안녕하세요 여러분, 오늘은 제가 최근에 구매한 샤넬 No.5 향수에 대해서 리뷰해드릴게요"
            },
            {
                "start": 51.0,
                "end": 56.5,
                "text": "이 향수는 정말 클래식한 향이고요, 지속력도 굉장히 좋습니다"
            },
            {
                "start": 57.0,
                "end": 62.3,
                "text": "가격은 조금 비싸지만 그만한 가치가 있다고 생각해요"
            }
        ]
    
    @pytest.fixture
    def sample_visual_frames(self):
        """샘플 시각 분석 프레임 데이터"""
        return [
            {
                "timestamp": 47.5,
                "ocr_results": [
                    {
                        "text": "CHANEL",
                        "confidence": 0.96,
                        "bbox": [[150, 80], [250, 80], [250, 120], [150, 120]],
                        "language": "en",
                        "area": 4000
                    },
                    {
                        "text": "N°5",
                        "confidence": 0.92,
                        "bbox": [[160, 130], [220, 130], [220, 160], [160, 160]],
                        "language": "en",
                        "area": 1800
                    }
                ],
                "object_detections": [
                    {
                        "class": "perfume_bottle",
                        "confidence": 0.89,
                        "bbox": [140, 70, 260, 200],
                        "area": 15600
                    }
                ],
                "frame_path": "/tmp/frame_47_5.jpg"
            },
            {
                "timestamp": 53.2,
                "ocr_results": [
                    {
                        "text": "샤넬",
                        "confidence": 0.88,
                        "bbox": [[100, 50], [180, 50], [180, 90], [100, 90]],
                        "language": "ko",
                        "area": 3200
                    }
                ],
                "object_detections": [
                    {
                        "class": "cosmetic",
                        "confidence": 0.82,
                        "bbox": [95, 45, 185, 95],
                        "area": 4500
                    }
                ],
                "frame_path": "/tmp/frame_53_2.jpg"
            }
        ]
    
    @pytest.fixture
    def sample_gemini_candidate(self):
        """Gemini 1차 분석 결과 후보"""
        return {
            "start_time": 45.0,
            "end_time": 62.0,
            "reason": "향수 제품에 대한 상세한 리뷰 언급",
            "confidence_score": 0.92
        }
    
    def test_integration_with_whisper_data(self, fusion_engine, sample_whisper_output, sample_visual_frames):
        """Whisper 출력과의 통합 테스트"""
        # 실제 Whisper 출력 형태 처리
        fused_result = fusion_engine.fuse_timeframe_data(
            audio_data=sample_whisper_output,
            visual_data=sample_visual_frames,
            timeframe_start=44.0,
            timeframe_end=63.0
        )
        
        assert isinstance(fused_result, FusedAnalysisResult)
        assert len(fused_result.audio_analysis.segments) == 3
        assert "샤넬 No.5 향수" in fused_result.audio_analysis.full_text
        assert len(fused_result.visual_analysis) == 2
        
        # 제품 언급 검증
        assert len(fused_result.product_mentions) > 0
        
        # 시각적 확인 검증
        assert len(fused_result.visual_confirmations) > 0
        
        # 브랜드명 매칭 확인
        found_chanel = any('chanel' in mention.lower() for mention in fused_result.product_mentions)
        found_visual_chanel = any('chanel' in conf.lower() for conf in fused_result.visual_confirmations)
        
        assert found_chanel or found_visual_chanel
    
    def test_integration_with_ocr_processor(self, fusion_engine, config):
        """OCRProcessor와의 통합 테스트"""
        ocr_processor = OCRProcessor(config)
        
        # 모의 OCR 결과 생성
        mock_ocr_results = [
            {
                'text': 'DIOR',
                'confidence': 0.95,
                'bbox': [[100, 50], [200, 50], [200, 100], [100, 100]],
                'language': 'en',
                'area': 5000
            }
        ]
        
        # Gemini 시간대 정보
        gemini_timeframe = {
            'product_mentions': ['디올', 'DIOR', '립스틱']
        }
        
        # OCR과 Gemini 결과 융합
        integrated_results = ocr_processor.integrate_with_gemini_analysis(
            mock_ocr_results, 
            gemini_timeframe
        )
        
        assert len(integrated_results) > 0
        assert 'gemini_match_score' in integrated_results[0]
        assert 'is_product_related' in integrated_results[0]
    
    def test_pipeline_integration_workflow(self, fusion_engine, mock_pipeline):
        """전체 파이프라인과의 워크플로우 통합 테스트"""
        # 파이프라인 각 단계의 출력 모의
        whisper_output = [
            {
                "start": 120.5,
                "end": 128.2,
                "text": "이 크림은 정말 보습력이 뛰어나고 흡수도 빨라요"
            }
        ]
        
        visual_output = [
            {
                "timestamp": 124.0,
                "ocr_results": [
                    {
                        "text": "Moisturizing Cream",
                        "confidence": 0.91,
                        "bbox": [[50, 30], [200, 30], [200, 60], [50, 60]],
                        "language": "en",
                        "area": 4500
                    }
                ],
                "object_detections": []
            }
        ]
        
        # 융합 실행
        fused_result = fusion_engine.fuse_timeframe_data(
            audio_data=whisper_output,
            visual_data=visual_output,
            timeframe_start=118.0,
            timeframe_end=130.0
        )
        
        # Gemini 2차 분석용 데이터 생성
        prompt_data = fusion_engine.generate_gemini_prompt_data(fused_result)
        
        # 검증
        assert 'audio_analysis' in prompt_data
        assert 'visual_analysis' in prompt_data
        assert 'fusion_metadata' in prompt_data
        
        # 실제 파이프라인에서 사용할 수 있는 형태인지 확인
        assert prompt_data['audio_analysis']['transcription'] == "이 크림은 정말 보습력이 뛰어나고 흡수도 빨라요"
        assert prompt_data['visual_analysis']['frame_count'] == 1
    
    def test_end_to_end_fusion_quality(self, fusion_engine):
        """종단간 융합 품질 테스트"""
        # 고품질 데이터 시나리오
        high_quality_audio = [
            {
                "start": 30.0,
                "end": 35.5,
                "text": "오늘 소개할 제품은 랑콤의 제네피크 세럼입니다"
            },
            {
                "start": 36.0,
                "end": 41.2,
                "text": "이 세럼은 피부 재생에 정말 효과적이에요"
            }
        ]
        
        high_quality_visual = [
            {
                "timestamp": 32.5,
                "ocr_results": [
                    {
                        "text": "LANCÔME",
                        "confidence": 0.97,
                        "bbox": [[120, 60], [220, 60], [220, 100], [120, 100]],
                        "language": "en",
                        "area": 4000
                    },
                    {
                        "text": "Génifique",
                        "confidence": 0.94,
                        "bbox": [[125, 110], [215, 110], [215, 140], [125, 140]],
                        "language": "en",
                        "area": 2700
                    }
                ],
                "object_detections": [
                    {
                        "class": "serum_bottle",
                        "confidence": 0.93,
                        "bbox": [115, 55, 225, 145],
                        "area": 9900
                    }
                ]
            }
        ]
        
        result = fusion_engine.fuse_timeframe_data(
            audio_data=high_quality_audio,
            visual_data=high_quality_visual,
            timeframe_start=29.0,
            timeframe_end=42.0
        )
        
        # 품질 검증
        validation = fusion_engine.validate_fusion_result(result)
        
        assert validation['is_valid'] == True
        assert validation['quality_score'] > 0.7  # 높은 품질 점수
        assert len(validation['issues']) == 0
        
        # 융합 신뢰도 검증
        assert result.fusion_confidence.overall_confidence > 0.6
        assert result.consistency_check == True
    
    def test_low_quality_data_handling(self, fusion_engine):
        """저품질 데이터 처리 테스트"""
        # 저품질 데이터 시나리오
        low_quality_audio = [
            {
                "start": 15.0,
                "end": 18.0,
                "text": "음... 이거..."  # 불명확한 음성
            }
        ]
        
        low_quality_visual = [
            {
                "timestamp": 16.5,
                "ocr_results": [
                    {
                        "text": "블러리텍스트",  # 낮은 품질의 OCR
                        "confidence": 0.45,
                        "bbox": [[50, 50], [150, 50], [150, 80], [50, 80]],
                        "language": "ko",
                        "area": 3000
                    }
                ],
                "object_detections": []
            }
        ]
        
        result = fusion_engine.fuse_timeframe_data(
            audio_data=low_quality_audio,
            visual_data=low_quality_visual,
            timeframe_start=14.0,
            timeframe_end=19.0
        )
        
        # 저품질 처리 검증
        validation = fusion_engine.validate_fusion_result(result)
        
        assert validation['quality_score'] < 0.5  # 낮은 품질 점수
        assert len(validation['warnings']) > 0
        assert 'require_manual_review' in validation['recommendations'] or len(validation['warnings']) > 0
    
    def test_time_synchronization_accuracy(self, fusion_engine):
        """시간 동기화 정확도 테스트"""
        # 정확한 시간 동기화 시나리오
        audio_data = [
            {
                "start": 100.0,
                "end": 105.0,
                "text": "이 제품을 보시면"
            }
        ]
        
        # 다양한 시간대의 시각 데이터
        visual_data = [
            {
                "timestamp": 98.0,  # 범위 밖
                "ocr_results": [{"text": "불일치", "confidence": 0.8, "bbox": [], "language": "ko", "area": 1000}],
                "object_detections": []
            },
            {
                "timestamp": 102.5,  # 범위 내
                "ocr_results": [{"text": "일치", "confidence": 0.9, "bbox": [], "language": "ko", "area": 1000}],
                "object_detections": []
            },
            {
                "timestamp": 108.0,  # 범위 밖
                "ocr_results": [{"text": "불일치2", "confidence": 0.85, "bbox": [], "language": "ko", "area": 1000}],
                "object_detections": []
            }
        ]
        
        result = fusion_engine.fuse_timeframe_data(
            audio_data=audio_data,
            visual_data=visual_data,
            timeframe_start=99.0,
            timeframe_end=106.0
        )
        
        # 시간 동기화 검증
        assert len(result.visual_analysis) == 1  # 범위 내 프레임만 포함
        assert result.visual_analysis[0].frame_timestamp == 102.5
        
        # 시간 정렬 점수 확인
        assert result.fusion_confidence.temporal_alignment_score > 0.0
    
    def test_multilingual_content_handling(self, fusion_engine):
        """다국어 콘텐츠 처리 테스트"""
        multilingual_audio = [
            {
                "start": 60.0,
                "end": 65.0,
                "text": "This is a great product 정말 좋은 제품이에요"
            }
        ]
        
        multilingual_visual = [
            {
                "timestamp": 62.0,
                "ocr_results": [
                    {
                        "text": "Great Product",
                        "confidence": 0.93,
                        "bbox": [[100, 50], [200, 50], [200, 80], [100, 80]],
                        "language": "en",
                        "area": 3000
                    },
                    {
                        "text": "좋은 제품",
                        "confidence": 0.89,
                        "bbox": [[100, 90], [180, 90], [180, 120], [100, 120]],
                        "language": "ko",
                        "area": 2400
                    }
                ],
                "object_detections": []
            }
        ]
        
        result = fusion_engine.fuse_timeframe_data(
            audio_data=multilingual_audio,
            visual_data=multilingual_visual,
            timeframe_start=58.0,
            timeframe_end=67.0
        )
        
        # 다국어 처리 검증
        assert len(result.visual_analysis) > 0
        assert len(result.visual_analysis[0].ocr_results) == 2
        
        # 언어별 텍스트 매칭 확인
        ocr_texts = [ocr.text for ocr in result.visual_analysis[0].ocr_results]
        assert "Great Product" in ocr_texts
        assert "좋은 제품" in ocr_texts
    
    @patch('src.gemini_analyzer.audio_visual_fusion.time.time')
    def test_performance_monitoring(self, mock_time, fusion_engine, sample_whisper_output, sample_visual_frames):
        """성능 모니터링 테스트"""
        # 시간 측정 모의
        mock_time.side_effect = [0.0, 1.5]  # 1.5초 소요
        
        result = fusion_engine.fuse_timeframe_data(
            audio_data=sample_whisper_output,
            visual_data=sample_visual_frames,
            timeframe_start=44.0,
            timeframe_end=63.0
        )
        
        # 성능 검증 (실제 시간 측정이 모의되었으므로 기본적인 완료 확인)
        assert isinstance(result, FusedAnalysisResult)
        assert result.fusion_summary is not None
    
    def test_error_recovery_integration(self, fusion_engine):
        """에러 복구 통합 테스트"""
        # 부분적으로 손상된 데이터
        corrupted_audio = [
            {
                "start": 10.0,
                "end": 15.0,
                "text": "정상 데이터"
            },
            {
                # 'start' 키 누락
                "end": 20.0,
                "text": "손상된 데이터"
            }
        ]
        
        corrupted_visual = [
            {
                "timestamp": 12.0,
                "ocr_results": [
                    {
                        "text": "정상 OCR",
                        "confidence": 0.9,
                        "bbox": [[0, 0], [100, 0], [100, 50], [0, 50]],
                        "language": "ko",
                        "area": 5000
                    }
                ],
                "object_detections": []
            },
            {
                # 'timestamp' 키 누락
                "ocr_results": [],
                "object_detections": []
            }
        ]
        
        # 에러가 발생해도 부분적으로 처리 가능한지 확인
        try:
            result = fusion_engine.fuse_timeframe_data(
                audio_data=corrupted_audio,
                visual_data=corrupted_visual,
                timeframe_start=8.0,
                timeframe_end=22.0
            )
            
            # 부분적으로라도 처리되었는지 확인
            assert isinstance(result, FusedAnalysisResult)
            
        except Exception as e:
            # 예상된 에러인지 확인
            assert "처리" in str(e) or "데이터" in str(e) or "시간" in str(e)
    
    def test_large_dataset_handling(self, fusion_engine):
        """대용량 데이터셋 처리 테스트"""
        # 대량의 세그먼트 생성
        large_audio_data = []
        for i in range(50):  # 50개 세그먼트
            large_audio_data.append({
                "start": i * 2.0,
                "end": (i + 1) * 2.0 - 0.1,
                "text": f"세그먼트 {i}의 텍스트 내용입니다"
            })
        
        # 대량의 시각 프레임 생성
        large_visual_data = []
        for i in range(25):  # 25개 프레임
            large_visual_data.append({
                "timestamp": i * 4.0 + 1.0,
                "ocr_results": [
                    {
                        "text": f"프레임{i}",
                        "confidence": 0.8 + (i % 10) * 0.02,
                        "bbox": [[i*10, i*10], [i*10+100, i*10], [i*10+100, i*10+50], [i*10, i*10+50]],
                        "language": "ko",
                        "area": 5000
                    }
                ],
                "object_detections": []
            })
        
        # 대용량 데이터 처리
        result = fusion_engine.fuse_timeframe_data(
            audio_data=large_audio_data,
            visual_data=large_visual_data,
            timeframe_start=0.0,
            timeframe_end=100.0
        )
        
        # 처리 결과 검증
        assert isinstance(result, FusedAnalysisResult)
        assert len(result.audio_analysis.segments) > 0
        assert len(result.visual_analysis) > 0
        
        # 성능 관련 검증
        validation = fusion_engine.validate_fusion_result(result)
        assert validation['is_valid'] == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])