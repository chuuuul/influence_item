"""
통합 파이프라인 테스트

AI 분석 파이프라인의 end-to-end 테스트를 수행합니다.
"""

import pytest
import pytest_asyncio
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.gemini_analyzer.pipeline import AIAnalysisPipeline, PipelineStatus, analyze_youtube_video_sync
from config import Config


class TestIntegratedPipeline:
    """통합 파이프라인 테스트 클래스"""
    
    @pytest.fixture
    def config(self):
        """테스트용 설정 객체"""
        return Config()
    
    @pytest.fixture
    def pipeline(self, config):
        """파이프라인 인스턴스"""
        return AIAnalysisPipeline(config)
    
    def test_pipeline_initialization(self, pipeline):
        """파이프라인 초기화 테스트"""
        assert pipeline is not None
        assert pipeline.current_status == PipelineStatus.PENDING
        assert len(pipeline.step_logs) == 0
        assert hasattr(pipeline, 'youtube_downloader')
        assert hasattr(pipeline, 'whisper_processor')
        assert hasattr(pipeline, 'first_pass_analyzer')
        assert hasattr(pipeline, 'second_pass_analyzer')
        assert hasattr(pipeline, 'state_manager')
    
    def test_pipeline_status_tracking(self, pipeline):
        """파이프라인 상태 추적 테스트"""
        status = pipeline.get_pipeline_status()
        
        assert 'status' in status
        assert 'step_count' in status
        assert 'config' in status
        assert status['status'] == 'pending'
        assert status['step_count'] == 0
    
    def test_step_logging(self, pipeline):
        """단계별 로깅 테스트"""
        pipeline._log_step("test_step", "success", "테스트 성공", 1.5)
        
        assert len(pipeline.step_logs) == 1
        log_entry = pipeline.step_logs[0]
        
        assert log_entry['step'] == 'test_step'
        assert log_entry['status'] == 'success'
        assert log_entry['message'] == '테스트 성공'
        assert log_entry['execution_time'] == 1.5
        assert 'timestamp' in log_entry
    
    def test_url_validation(self, pipeline):
        """URL 검증 테스트"""
        # 유효한 URL
        valid_urls = [
            "https://youtube.com/watch?v=test",
            "https://www.youtube.com/watch?v=test"
        ]
        
        for url in valid_urls:
            try:
                asyncio.run(pipeline._step_initialization(url))
            except ValueError:
                pytest.fail(f"유효한 URL이 거부됨: {url}")
        
        # 무효한 URL
        invalid_urls = [
            "",
            "https://google.com",
            "not_a_url",
            "https://vimeo.com/test"
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                asyncio.run(pipeline._step_initialization(url))
    
    def test_module_validation(self, pipeline):
        """모듈 검증 테스트"""
        # 정상 상태에서는 에러가 발생하지 않아야 함
        pipeline._validate_modules()
        
        # 모듈이 없는 경우 에러 발생
        original_downloader = pipeline.youtube_downloader
        del pipeline.youtube_downloader
        
        with pytest.raises(Exception, match="YouTube 다운로더 초기화 실패"):
            pipeline._validate_modules()
        
        # 복구
        pipeline.youtube_downloader = original_downloader
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, pipeline):
        """재시도 메커니즘 테스트"""
        call_count = 0
        
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("일시적 실패")
            return "성공"
        
        # 재시도 성공 케이스
        result = await pipeline._retry_with_backoff(failing_function, max_retries=3)
        assert result == "성공"
        assert call_count == 3
        
        # 재시도 실패 케이스
        call_count = 0
        
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("항상 실패")
        
        with pytest.raises(Exception, match="항상 실패"):
            await pipeline._retry_with_backoff(always_failing_function, max_retries=2)
        
        assert call_count == 3  # 초기 시도 + 2회 재시도
    
    def test_segment_data_extraction(self, pipeline):
        """세그먼트 데이터 추출 테스트"""
        candidate = {
            'start_time': 30.0,
            'end_time': 60.0
        }
        
        script_data = [
            {'start': 10.0, 'end': 25.0, 'text': '구간 1'},
            {'start': 25.0, 'end': 40.0, 'text': '구간 2'},  # 겹침
            {'start': 50.0, 'end': 70.0, 'text': '구간 3'},  # 겹침
            {'start': 80.0, 'end': 90.0, 'text': '구간 4'}   # 겹치지 않음
        ]
        
        extracted = pipeline._extract_segment_data(candidate, script_data)
        
        assert len(extracted) == 2
        assert extracted[0]['text'] == '구간 2'
        assert extracted[1]['text'] == '구간 3'
    
    def test_performance_metrics(self, pipeline):
        """성능 메트릭 테스트"""
        # 로그 데이터 추가
        pipeline._log_step("step1", "success", "완료", 1.0)
        pipeline._log_step("step2", "success", "완료", 2.0)
        pipeline._log_step("step3", "error", "실패", 0.5)
        
        metrics = pipeline.get_performance_metrics()
        
        assert metrics['total_time'] == 3.5
        assert metrics['step_breakdown']['step1'] == 1.0
        assert metrics['step_breakdown']['step2'] == 2.0
        assert metrics['step_breakdown']['step3'] == 0.5
        assert metrics['steps_completed'] == 2
        assert metrics['errors_count'] == 1
    
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline_mock(self, pipeline):
        """End-to-End 파이프라인 테스트 (Mock 사용)"""
        test_url = "https://www.youtube.com/watch?v=test"
        
        # Mock 데이터
        mock_audio_path = Path("/tmp/test_audio.wav")
        mock_script_data = [
            {'start': 0.0, 'end': 5.0, 'text': '안녕하세요', 'confidence': 0.95}
        ]
        mock_candidates = [
            {'start_time': 0.0, 'end_time': 5.0, 'reason': '테스트', 'confidence_score': 0.9}
        ]
        mock_final_results = [
            {'product_name': '테스트 제품', 'score': 85}
        ]
        
        with patch.object(pipeline, '_step_download_audio') as mock_download, \
             patch.object(pipeline, '_step_transcribe_audio') as mock_transcribe, \
             patch.object(pipeline, '_step_first_pass_analysis') as mock_first_pass, \
             patch.object(pipeline, '_step_second_pass_analysis') as mock_second_pass, \
             patch.object(pipeline, '_step_finalization') as mock_finalization:
            
            # Mock 설정
            mock_download.return_value = mock_audio_path
            mock_transcribe.return_value = mock_script_data
            mock_first_pass.return_value = mock_candidates
            mock_second_pass.return_value = mock_final_results
            mock_finalization.return_value = None
            
            # 파이프라인 실행
            result = await pipeline.process_video(test_url)
            
            # 결과 검증
            assert result.status == PipelineStatus.COMPLETED
            assert result.video_url == test_url
            assert result.result_data == mock_final_results
            assert result.processing_time > 0
            assert len(result.step_logs) > 0
            
            # 모든 Mock이 호출되었는지 확인
            mock_download.assert_called_once()
            mock_transcribe.assert_called_once()
            mock_first_pass.assert_called_once()
            mock_second_pass.assert_called_once()
            mock_finalization.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, pipeline):
        """파이프라인 에러 핸들링 테스트"""
        test_url = "https://www.youtube.com/watch?v=test"
        
        with patch.object(pipeline, '_step_download_audio') as mock_download:
            # 다운로드 단계에서 에러 발생
            mock_download.side_effect = Exception("다운로드 실패")
            
            result = await pipeline.process_video(test_url)
            
            # 에러 결과 검증
            assert result.status == PipelineStatus.FAILED
            assert result.video_url == test_url
            assert result.error_message is not None
            assert "다운로드 실패" in result.error_message
            assert result.processing_time > 0
    
    def test_sync_wrapper_function(self, config):
        """동기 래퍼 함수 테스트"""
        test_url = "https://www.youtube.com/watch?v=test"
        
        with patch('src.gemini_analyzer.pipeline.analyze_youtube_video') as mock_async:
            from src.gemini_analyzer.pipeline import PipelineResult, PipelineStatus
            
            # Mock 결과 설정
            mock_result = PipelineResult(
                status=PipelineStatus.COMPLETED,
                video_url=test_url,
                processing_time=1.5,
                result_data={'test': 'data'}
            )
            mock_async.return_value = mock_result
            
            # 동기 래퍼 함수 호출
            result = analyze_youtube_video_sync(test_url, config)
            
            # 결과 검증
            assert result.status == PipelineStatus.COMPLETED
            assert result.video_url == test_url
            assert result.processing_time == 1.5
            assert result.result_data == {'test': 'data'}
            
            # 비동기 함수가 호출되었는지 확인
            mock_async.assert_called_once_with(test_url, config)


class TestPipelineIntegration:
    """파이프라인 통합 테스트"""
    
    def test_pipeline_components_integration(self):
        """파이프라인 컴포넌트 통합 테스트"""
        config = Config()
        pipeline = AIAnalysisPipeline(config)
        
        # 모든 컴포넌트가 정상적으로 초기화되었는지 확인
        assert pipeline.youtube_downloader is not None
        assert pipeline.whisper_processor is not None
        assert pipeline.first_pass_analyzer is not None
        assert pipeline.second_pass_analyzer is not None
        assert pipeline.state_manager is not None
        
        # 각 컴포넌트의 설정이 일관되는지 확인
        assert pipeline.youtube_downloader.config == config
        assert pipeline.whisper_processor.config == config
        assert pipeline.first_pass_analyzer.config == config
        assert pipeline.second_pass_analyzer.config == config
        assert pipeline.state_manager.config == config
    
    def test_pipeline_data_flow(self):
        """파이프라인 데이터 플로우 테스트"""
        pipeline = AIAnalysisPipeline()
        
        # 테스트 데이터
        test_candidate = {'start_time': 10.0, 'end_time': 20.0}
        test_script = [
            {'start': 5.0, 'end': 15.0, 'text': '첫 번째'},
            {'start': 15.0, 'end': 25.0, 'text': '두 번째'}
        ]
        
        # 세그먼트 추출 테스트
        segments = pipeline._extract_segment_data(test_candidate, test_script)
        
        assert len(segments) == 2
        assert all('start' in seg and 'end' in seg and 'text' in seg for seg in segments)
    
    def test_pipeline_state_consistency(self):
        """파이프라인 상태 일관성 테스트"""
        pipeline = AIAnalysisPipeline()
        
        # 초기 상태 확인
        assert pipeline.current_status == PipelineStatus.PENDING
        assert len(pipeline.step_logs) == 0
        
        # 로그 추가 후 상태 확인
        pipeline._log_step("test", "success", "테스트")
        assert len(pipeline.step_logs) == 1
        
        # 상태 정보 일관성 확인
        status = pipeline.get_pipeline_status()
        assert status['step_count'] == 1
        assert status['status'] == 'pending'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])