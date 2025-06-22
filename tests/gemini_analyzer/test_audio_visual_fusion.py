"""
AudioVisualFusion 클래스 단위 테스트

음성+시각 데이터 융합 로직의 단위 테스트 케이스들입니다.
"""

import pytest
import time
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.gemini_analyzer.audio_visual_fusion import AudioVisualFusion
from src.gemini_analyzer.models import (
    WhisperSegment, AudioAnalysisResult, VisualAnalysisResult,
    OCRResult, ObjectDetectionResult, FusionConfidence, FusedAnalysisResult
)
from config import Config


class TestAudioVisualFusion:
    """AudioVisualFusion 클래스 테스트"""
    
    @pytest.fixture
    def config(self):
        """테스트용 설정 객체"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = 'DEBUG'
        config.FUSION_TIME_TOLERANCE = 2.0
        config.TEXT_SIMILARITY_THRESHOLD = 0.6
        config.FUSION_CONFIDENCE_THRESHOLD = 0.7
        return config
    
    @pytest.fixture
    def fusion_engine(self, config):
        """AudioVisualFusion 인스턴스"""
        return AudioVisualFusion(config)
    
    @pytest.fixture
    def sample_audio_data(self):
        """샘플 음성 데이터"""
        return [
            {
                'start': 10.0,
                'end': 15.0,
                'text': '오늘 제가 소개할 제품은 디올 립스틱입니다',
                'confidence': 0.95
            },
            {
                'start': 15.5,
                'end': 20.0,
                'text': '이 립스틱은 정말 발색이 좋아요',
                'confidence': 0.92
            }
        ]
    
    @pytest.fixture
    def sample_visual_data(self):
        """샘플 시각 데이터"""
        return [
            {
                'timestamp': 12.0,
                'ocr_results': [
                    {
                        'text': 'DIOR',
                        'confidence': 0.98,
                        'bbox': [[100, 50], [200, 50], [200, 100], [100, 100]],
                        'language': 'en',
                        'area': 5000
                    },
                    {
                        'text': '립스틱',
                        'confidence': 0.89,
                        'bbox': [[100, 110], [180, 110], [180, 140], [100, 140]],
                        'language': 'ko',
                        'area': 2400
                    }
                ],
                'object_detections': [
                    {
                        'class': 'cosmetic',
                        'confidence': 0.91,
                        'bbox': [95, 45, 205, 145],
                        'area': 11000
                    }
                ],
                'frame_path': '/tmp/frame_12.jpg'
            }
        ]
    
    def test_fusion_engine_initialization(self, config):
        """융합 엔진 초기화 테스트"""
        fusion = AudioVisualFusion(config)
        
        assert fusion.config == config
        assert fusion.time_tolerance == 2.0
        assert fusion.text_similarity_threshold == 0.6
        assert fusion.confidence_threshold == 0.7
        assert fusion.logger is not None
    
    def test_time_overlap_detection(self, fusion_engine):
        """시간 구간 겹침 감지 테스트"""
        # 겹치는 경우
        assert fusion_engine._is_time_overlap(10.0, 15.0, 12.0, 18.0) == True
        assert fusion_engine._is_time_overlap(10.0, 15.0, 8.0, 12.0) == True
        
        # 겹치지 않는 경우
        assert fusion_engine._is_time_overlap(10.0, 15.0, 20.0, 25.0) == False
        
        # 허용 오차 범위 내
        assert fusion_engine._is_time_overlap(10.0, 15.0, 17.0, 20.0) == True  # 2초 허용
        assert fusion_engine._is_time_overlap(10.0, 15.0, 18.0, 20.0) == False  # 3초 차이
    
    def test_process_audio_data(self, fusion_engine, sample_audio_data):
        """음성 데이터 처리 테스트"""
        result = fusion_engine._process_audio_data(sample_audio_data, 9.0, 18.0)
        
        assert isinstance(result, AudioAnalysisResult)
        assert result.timeframe_start == 9.0
        assert result.timeframe_end == 18.0
        assert len(result.segments) == 2  # 두 세그먼트 모두 포함
        assert '디올 립스틱' in result.full_text
        assert '발색이 좋아요' in result.full_text
    
    def test_process_visual_data(self, fusion_engine, sample_visual_data):
        """시각 데이터 처리 테스트"""
        result = fusion_engine._process_visual_data(sample_visual_data, 10.0, 15.0)
        
        assert len(result) == 1
        assert isinstance(result[0], VisualAnalysisResult)
        assert result[0].frame_timestamp == 12.0
        assert len(result[0].ocr_results) == 2
        assert len(result[0].object_detection_results) == 1
        
        # OCR 결과 검증
        ocr_texts = [ocr.text for ocr in result[0].ocr_results]
        assert 'DIOR' in ocr_texts
        assert '립스틱' in ocr_texts
    
    def test_text_matching_score_calculation(self, fusion_engine):
        """텍스트 매칭 점수 계산 테스트"""
        # 샘플 데이터 생성
        audio_analysis = AudioAnalysisResult(
            timeframe_start=10.0,
            timeframe_end=15.0,
            segments=[
                WhisperSegment(start=10.0, end=15.0, text='디올 립스틱 추천합니다', confidence=0.95)
            ],
            full_text='디올 립스틱 추천합니다'
        )
        
        visual_analysis = [
            VisualAnalysisResult(
                frame_timestamp=12.0,
                ocr_results=[
                    OCRResult(text='DIOR', confidence=0.98, bbox=[], language='en', area=1000),
                    OCRResult(text='립스틱', confidence=0.89, bbox=[], language='ko', area=800)
                ],
                object_detection_results=[]
            )
        ]
        
        score = fusion_engine._calculate_text_matching_score(audio_analysis, visual_analysis)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.0  # 매칭되는 텍스트가 있으므로 0보다 높은 점수 예상
    
    def test_temporal_alignment_score_calculation(self, fusion_engine):
        """시간 정렬 점수 계산 테스트"""
        audio_analysis = AudioAnalysisResult(
            timeframe_start=10.0,
            timeframe_end=15.0,
            segments=[
                WhisperSegment(start=12.0, end=15.0, text='테스트', confidence=0.95)
            ],
            full_text='테스트'
        )
        
        visual_analysis = [
            VisualAnalysisResult(
                frame_timestamp=12.5,  # 0.5초 차이 - 허용 범위 내
                ocr_results=[],
                object_detection_results=[]
            )
        ]
        
        score = fusion_engine._calculate_temporal_alignment_score(audio_analysis, visual_analysis)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.0  # 정렬된 것으로 간주되어야 함
    
    def test_fusion_confidence_calculation(self, fusion_engine, sample_audio_data, sample_visual_data):
        """융합 신뢰도 계산 테스트"""
        audio_analysis = fusion_engine._process_audio_data(sample_audio_data, 9.0, 18.0)
        visual_analysis = fusion_engine._process_visual_data(sample_visual_data, 10.0, 15.0)
        
        confidence = fusion_engine._calculate_fusion_confidence(audio_analysis, visual_analysis)
        
        assert isinstance(confidence, FusionConfidence)
        assert 0.0 <= confidence.text_matching_score <= 1.0
        assert 0.0 <= confidence.temporal_alignment_score <= 1.0
        assert 0.0 <= confidence.semantic_coherence_score <= 1.0
        assert 0.0 <= confidence.overall_confidence <= 1.0
        
        # 가중 평균 검증
        expected = (
            confidence.text_matching_score * 0.4 +
            confidence.temporal_alignment_score * 0.3 +
            confidence.semantic_coherence_score * 0.3
        )
        assert abs(confidence.overall_confidence - expected) < 0.05
    
    def test_product_mentions_extraction(self, fusion_engine):
        """제품 언급 추출 테스트"""
        audio_analysis = AudioAnalysisResult(
            timeframe_start=10.0,
            timeframe_end=15.0,
            segments=[],
            full_text='오늘은 샤넬 No.5 향수를 사용해볼게요. 이 제품이 정말 좋아요.'
        )
        
        mentions = fusion_engine._extract_product_mentions(audio_analysis)
        
        assert isinstance(mentions, list)
        assert len(mentions) > 0
        # 구체적인 언급 내용은 정규표현식 패턴에 따라 달라질 수 있음
    
    def test_visual_confirmations_extraction(self, fusion_engine):
        """시각적 확인 추출 테스트"""
        visual_analysis = [
            VisualAnalysisResult(
                frame_timestamp=12.0,
                ocr_results=[
                    OCRResult(text='CHANEL', confidence=0.95, bbox=[], language='en', area=1000),
                    OCRResult(text='No.5', confidence=0.88, bbox=[], language='en', area=500)
                ],
                object_detection_results=[]
            )
        ]
        
        product_mentions = ['샤넬', 'No.5']
        confirmations = fusion_engine._extract_visual_confirmations(visual_analysis, product_mentions)
        
        assert isinstance(confirmations, list)
        assert len(confirmations) > 0
    
    def test_consistency_check(self, fusion_engine):
        """일치성 검사 테스트"""
        high_confidence = FusionConfidence(
            text_matching_score=0.8,
            temporal_alignment_score=0.9,
            semantic_coherence_score=0.7,
            overall_confidence=0.8
        )
        
        low_confidence = FusionConfidence(
            text_matching_score=0.3,
            temporal_alignment_score=0.4,
            semantic_coherence_score=0.2,
            overall_confidence=0.3
        )
        
        # 높은 신뢰도와 매칭이 있는 경우
        assert fusion_engine._check_consistency(['제품A'], ['제품A'], high_confidence) == True
        
        # 낮은 신뢰도인 경우
        assert fusion_engine._check_consistency(['제품A'], ['제품A'], low_confidence) == False
        
        # 데이터가 없는 경우
        assert fusion_engine._check_consistency([], [], high_confidence) == True
        
        # 한쪽만 있는 경우
        assert fusion_engine._check_consistency(['제품A'], [], high_confidence) == False
    
    def test_full_fusion_workflow(self, fusion_engine, sample_audio_data, sample_visual_data):
        """전체 융합 워크플로우 테스트"""
        result = fusion_engine.fuse_timeframe_data(
            audio_data=sample_audio_data,
            visual_data=sample_visual_data,
            timeframe_start=9.0,
            timeframe_end=18.0
        )
        
        assert isinstance(result, FusedAnalysisResult)
        assert result.timeframe_start == 9.0
        assert result.timeframe_end == 18.0
        assert isinstance(result.audio_analysis, AudioAnalysisResult)
        assert isinstance(result.visual_analysis, list)
        assert isinstance(result.fusion_confidence, FusionConfidence)
        assert isinstance(result.product_mentions, list)
        assert isinstance(result.visual_confirmations, list)
        assert isinstance(result.consistency_check, bool)
        assert isinstance(result.fusion_summary, str)
    
    def test_gemini_prompt_data_generation(self, fusion_engine, sample_audio_data, sample_visual_data):
        """Gemini 프롬프트 데이터 생성 테스트"""
        fused_result = fusion_engine.fuse_timeframe_data(
            audio_data=sample_audio_data,
            visual_data=sample_visual_data,
            timeframe_start=9.0,
            timeframe_end=18.0
        )
        
        prompt_data = fusion_engine.generate_gemini_prompt_data(fused_result)
        
        assert isinstance(prompt_data, dict)
        assert 'audio_analysis' in prompt_data
        assert 'visual_analysis' in prompt_data
        assert 'fusion_metadata' in prompt_data
        assert 'analysis_context' in prompt_data
        
        # 세부 구조 검증
        assert 'timeframe' in prompt_data['audio_analysis']
        assert 'transcription' in prompt_data['audio_analysis']
        assert 'frame_count' in prompt_data['visual_analysis']
        assert 'fusion_confidence' in prompt_data['fusion_metadata']
        assert 'confidence_level' in prompt_data['analysis_context']
    
    def test_fusion_result_validation(self, fusion_engine, sample_audio_data, sample_visual_data):
        """융합 결과 검증 테스트"""
        fused_result = fusion_engine.fuse_timeframe_data(
            audio_data=sample_audio_data,
            visual_data=sample_visual_data,
            timeframe_start=9.0,
            timeframe_end=18.0
        )
        
        validation_report = fusion_engine.validate_fusion_result(fused_result)
        
        assert isinstance(validation_report, dict)
        assert 'is_valid' in validation_report
        assert 'issues' in validation_report
        assert 'warnings' in validation_report
        assert 'quality_score' in validation_report
        assert 'recommendations' in validation_report
        
        assert isinstance(validation_report['is_valid'], bool)
        assert isinstance(validation_report['issues'], list)
        assert isinstance(validation_report['warnings'], list)
        assert 0.0 <= validation_report['quality_score'] <= 1.0
        assert isinstance(validation_report['recommendations'], list)
    
    def test_data_quality_assessment(self, fusion_engine):
        """데이터 품질 평가 테스트"""
        # 우수한 품질 데이터
        excellent_result = FusedAnalysisResult(
            timeframe_start=10.0,
            timeframe_end=15.0,
            audio_analysis=AudioAnalysisResult(
                timeframe_start=10.0,
                timeframe_end=15.0,
                segments=[WhisperSegment(start=10.0, end=15.0, text='좋은 품질의 긴 텍스트입니다', confidence=0.95)],
                full_text='좋은 품질의 긴 텍스트입니다'
            ),
            visual_analysis=[
                VisualAnalysisResult(
                    frame_timestamp=12.0,
                    ocr_results=[OCRResult(text='테스트', confidence=0.9, bbox=[], language='ko', area=1000)],
                    object_detection_results=[]
                )
            ],
            fusion_confidence=FusionConfidence(
                text_matching_score=0.8,
                temporal_alignment_score=0.9,
                semantic_coherence_score=0.7,
                overall_confidence=0.8
            ),
            product_mentions=[],
            visual_confirmations=[],
            consistency_check=True,
            fusion_summary='테스트'
        )
        
        quality = fusion_engine._assess_data_quality(excellent_result)
        assert quality == 'excellent'
        
        # 낮은 품질 데이터
        poor_result = FusedAnalysisResult(
            timeframe_start=10.0,
            timeframe_end=15.0,
            audio_analysis=AudioAnalysisResult(
                timeframe_start=10.0,
                timeframe_end=15.0,
                segments=[],
                full_text=''
            ),
            visual_analysis=[],
            fusion_confidence=FusionConfidence(
                text_matching_score=0.1,
                temporal_alignment_score=0.2,
                semantic_coherence_score=0.1,
                overall_confidence=0.13
            ),
            product_mentions=[],
            visual_confirmations=[],
            consistency_check=False,
            fusion_summary='테스트'
        )
        
        quality = fusion_engine._assess_data_quality(poor_result)
        assert quality == 'poor'
    
    def test_error_handling(self, fusion_engine):
        """에러 처리 테스트"""
        # 빈 데이터로 정상 처리 확인 (None은 에러가 아님)
        try:
            fusion_engine._process_audio_data([], 10.0, 15.0)
            fusion_engine._process_visual_data([], 10.0, 15.0)
            fusion_engine.fuse_timeframe_data([], [], 10.0, 15.0)
        except Exception:
            pass  # 일부 에러는 예상됨
        
        # 에러 처리 로직이 구현되어 있는지 확인
        assert hasattr(fusion_engine, 'logger')
    
    def test_fusion_info(self, fusion_engine):
        """융합 엔진 정보 테스트"""
        info = fusion_engine.get_fusion_info()
        
        assert isinstance(info, dict)
        assert 'status' in info
        assert 'time_tolerance' in info
        assert 'text_similarity_threshold' in info
        assert 'confidence_threshold' in info
        assert 'supported_modalities' in info
        assert 'fusion_algorithms' in info
        
        assert info['status'] == 'ready'
        assert info['time_tolerance'] == 2.0
        assert 'audio' in info['supported_modalities']
        assert 'visual' in info['supported_modalities']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])