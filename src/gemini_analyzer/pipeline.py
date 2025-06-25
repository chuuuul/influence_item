"""
AI 분석 파이프라인 오케스트레이터

YouTube URL 입력부터 최종 제품 정보 JSON 출력까지의 완전 자동화된 워크플로우를 제공합니다.
"""

import asyncio
import json
import logging
import tempfile
import time
import gc
import psutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.config import Config
from ..whisper_processor.whisper_processor import WhisperProcessor
from ..whisper_processor.youtube_downloader import YouTubeDownloader
from .first_pass_analyzer import GeminiFirstPassAnalyzer
from .second_pass_analyzer import GeminiSecondPassAnalyzer
from .state_manager import StateManager
from ..visual_processor.target_frame_extractor import TargetFrameExtractor
from ..monetization.monetization_service import MonetizationService
from ..scoring.score_calculator import ScoreCalculator, ScoringInput
from ..scoring.influencer_analyzer import ChannelMetrics
from .models import TargetTimeframe
from ..schema.models import ProductRecommendationCandidate, SourceInfo, CandidateInfo, MonetizationInfo, StatusInfo, ScoreDetails
from ..schema.formatters import APIResponseFormatter
from ..youtube_api.youtube_client import YouTubeAPIClient
from ..youtube_api.quota_manager import QuotaManager
from ..error_handling.graceful_degradation import GracefulDegradationHandler, get_degradation_handler, with_graceful_degradation


class PipelineStatus(Enum):
    """파이프라인 실행 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""
    status: PipelineStatus
    video_url: str
    processing_time: float
    result_data: Optional[Dict] = None
    error_message: Optional[str] = None
    step_logs: List[Dict] = None
    
    def __post_init__(self):
        if self.step_logs is None:
            self.step_logs = []


class AIAnalysisPipeline:
    """AI 분석 파이프라인 오케스트레이터 (최적화된 버전)"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        파이프라인 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # 성능 모니터링 초기화
        self.process = psutil.Process()
        self.performance_metrics = {
            'memory_peak': 0,
            'cpu_peak': 0,
            'step_times': {},
            'bottlenecks': []
        }
        
        # Thread Pool Executor 초기화 (CPU 집약적 작업용)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=min(4, psutil.cpu_count()),
            thread_name_prefix="pipeline_worker"
        )
        
        # Graceful Degradation 핸들러 초기화
        self.degradation_handler = get_degradation_handler(config)
        
        # 모듈 초기화 (에러 처리 강화)
        self.youtube_downloader = self._init_youtube_downloader(config)
        self.whisper_processor = self._init_whisper_processor(config)
        self.first_pass_analyzer = self._init_first_pass_analyzer(config)
        self.second_pass_analyzer = self._init_second_pass_analyzer(config)
        self.target_frame_extractor = self._init_target_frame_extractor(config)
        self.state_manager = self._init_state_manager(config)
        self.monetization_service = self._init_monetization_service()
        self.score_calculator = self._init_score_calculator()
        
        # YouTube API 클라이언트 초기화
        self.youtube_api_client = self._init_youtube_api_client(config)
        
        # 상태 관리
        self.current_status = PipelineStatus.PENDING
        self.step_logs = []
        
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
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _init_youtube_downloader(self, config: Config) -> YouTubeDownloader:
        """YouTube 다운로더 초기화"""
        try:
            downloader = YouTubeDownloader(config)
            self.degradation_handler.register_service('youtube_downloader')
            self.logger.info("YouTube 다운로더 초기화 완료")
            return downloader
        except Exception as e:
            self.degradation_handler.record_service_error('youtube_downloader', str(e))
            self.logger.error(f"YouTube 다운로더 초기화 실패: {e}")
            raise
    
    def _init_whisper_processor(self, config: Config) -> WhisperProcessor:
        """Whisper 프로세서 초기화"""
        try:
            processor = WhisperProcessor(config)
            self.degradation_handler.register_service('whisper')
            self.logger.info("Whisper 프로세서 초기화 완료")
            return processor
        except Exception as e:
            self.degradation_handler.record_service_error('whisper', str(e))
            self.logger.warning(f"Whisper 프로세서 초기화 실패: {e}")
            # Whisper는 대체 가능하므로 None 반환
            return None
    
    def _init_first_pass_analyzer(self, config: Config) -> GeminiFirstPassAnalyzer:
        """Gemini 1차 분석기 초기화"""
        try:
            analyzer = GeminiFirstPassAnalyzer(config)
            self.degradation_handler.register_service('gemini_api')
            self.logger.info("Gemini 1차 분석기 초기화 완료")
            return analyzer
        except Exception as e:
            self.degradation_handler.record_service_error('gemini_api', str(e))
            self.logger.error(f"Gemini 1차 분석기 초기화 실패: {e}")
            raise
    
    def _init_second_pass_analyzer(self, config: Config) -> GeminiSecondPassAnalyzer:
        """Gemini 2차 분석기 초기화"""
        try:
            analyzer = GeminiSecondPassAnalyzer(config)
            self.logger.info("Gemini 2차 분석기 초기화 완료")
            return analyzer
        except Exception as e:
            self.degradation_handler.record_service_error('gemini_api', str(e))
            self.logger.error(f"Gemini 2차 분석기 초기화 실패: {e}")
            raise
    
    def _init_target_frame_extractor(self, config: Config) -> TargetFrameExtractor:
        """타겟 프레임 추출기 초기화"""
        try:
            extractor = TargetFrameExtractor(config)
            self.degradation_handler.register_service('visual_analysis')
            self.logger.info("타겟 프레임 추출기 초기화 완료")
            return extractor
        except Exception as e:
            self.degradation_handler.record_service_error('visual_analysis', str(e))
            self.logger.warning(f"타겟 프레임 추출기 초기화 실패: {e}")
            # 시각 분석은 선택적이므로 None 반환
            return None
    
    def _init_state_manager(self, config: Config) -> StateManager:
        """상태 관리자 초기화"""
        try:
            manager = StateManager(config)
            self.logger.info("상태 관리자 초기화 완료")
            return manager
        except Exception as e:
            self.logger.warning(f"상태 관리자 초기화 실패: {e}")
            # 상태 관리는 선택적이므로 None 반환
            return None
    
    def _init_monetization_service(self) -> MonetizationService:
        """수익화 서비스 초기화"""
        try:
            service = MonetizationService()
            self.degradation_handler.register_service('monetization')
            self.logger.info("수익화 서비스 초기화 완료")
            return service
        except Exception as e:
            self.degradation_handler.record_service_error('monetization', str(e))
            self.logger.warning(f"수익화 서비스 초기화 실패: {e}")
            # 수익화는 선택적이므로 None 반환
            return None
    
    def _init_score_calculator(self) -> ScoreCalculator:
        """점수 계산기 초기화"""
        try:
            calculator = ScoreCalculator()
            self.logger.info("점수 계산기 초기화 완료")
            return calculator
        except Exception as e:
            self.logger.warning(f"점수 계산기 초기화 실패: {e}")
            # 점수 계산은 선택적이므로 None 반환
            return None
    
    def _init_youtube_api_client(self, config: Config) -> Optional[YouTubeAPIClient]:
        """YouTube API 클라이언트 초기화"""
        try:
            client = YouTubeAPIClient(
                api_key=config.YOUTUBE_API_KEY,
                quota_manager=QuotaManager(daily_limit=config.YOUTUBE_API_DAILY_QUOTA)
            )
            self.degradation_handler.register_service('youtube_api')
            self.logger.info("YouTube API 클라이언트 초기화 완료")
            return client
        except Exception as e:
            self.degradation_handler.record_service_error('youtube_api', str(e))
            self.logger.warning(f"YouTube API 클라이언트 초기화 실패 (폴백 모드): {str(e)}")
            return None
    
    def _monitor_performance(self, step_name: str):
        """성능 모니터링"""
        try:
            # 메모리 사용량 체크
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # CPU 사용률 체크
            cpu_percent = self.process.cpu_percent()
            
            # 최고점 기록
            self.performance_metrics['memory_peak'] = max(
                self.performance_metrics['memory_peak'], memory_mb
            )
            self.performance_metrics['cpu_peak'] = max(
                self.performance_metrics['cpu_peak'], cpu_percent
            )
            
            # 메모리 사용량이 과도한 경우 경고
            if memory_mb > 2048:  # 2GB 이상
                self.logger.warning(f"[{step_name}] 높은 메모리 사용량: {memory_mb:.1f}MB")
                self.performance_metrics['bottlenecks'].append({
                    'step': step_name,
                    'type': 'high_memory',
                    'value': memory_mb,
                    'timestamp': time.time()
                })
                
                # 강제 가비지 컬렉션
                gc.collect()
                
        except Exception as e:
            self.logger.debug(f"성능 모니터링 실패: {str(e)}")

    def _log_step(self, step_name: str, status: str, message: str, 
                  execution_time: Optional[float] = None, **extra_data):
        """파이프라인 단계 로그 기록 (성능 모니터링 포함)"""
        # 성능 모니터링
        self._monitor_performance(step_name)
        
        log_entry = {
            'step': step_name,
            'status': status,
            'message': message,
            'timestamp': time.time(),
            'execution_time': execution_time,
            **extra_data
        }
        
        # 실행 시간 기록
        if execution_time and step_name not in ['pipeline']:
            self.performance_metrics['step_times'][step_name] = execution_time
            
            # 느린 단계 감지 (30초 이상)
            if execution_time > 30:
                self.performance_metrics['bottlenecks'].append({
                    'step': step_name,
                    'type': 'slow_execution',
                    'value': execution_time,
                    'timestamp': time.time()
                })
        
        self.step_logs.append(log_entry)
        
        # 로거에도 기록
        if status == 'success':
            self.logger.info(f"[{step_name}] {message}")
        elif status == 'error':
            self.logger.error(f"[{step_name}] {message}")
        else:
            self.logger.debug(f"[{step_name}] {message}")
    
    async def process_video(self, video_url: str) -> PipelineResult:
        """
        YouTube 영상을 완전 자동화 분석
        
        Args:
            video_url: YouTube 영상 URL
            
        Returns:
            파이프라인 실행 결과
        """
        start_time = time.time()
        self.current_status = PipelineStatus.PROCESSING
        self.step_logs = []
        
        result = PipelineResult(
            status=PipelineStatus.PROCESSING,
            video_url=video_url,
            processing_time=0.0
        )
        
        try:
            self.logger.info(f"AI 분석 파이프라인 시작: {video_url}")
            self._log_step("pipeline", "start", "AI 분석 파이프라인 시작")
            
            # 1단계: 초기화 및 검증
            await self._step_initialization(video_url)
            
            # 2단계: YouTube 영상 및 음성 다운로드
            audio_path, video_path = await self._step_download_media(video_url)
            
            # 3단계: Whisper 음성 인식
            script_data = await self._step_transcribe_audio(audio_path)
            self.state_manager.create_checkpoint(video_url, "transcription_complete", 
                                               {"script_data": script_data}, ["initialization", "download", "transcription"])
            
            # 4단계: Gemini 1차 분석 (후보 구간 탐지)
            candidates = await self._step_first_pass_analysis(script_data)
            self.state_manager.create_checkpoint(video_url, "first_pass_complete", 
                                               {"candidates": candidates}, ["initialization", "download", "transcription", "first_pass"])
            
            # 5단계: 타겟 시간대 시각 분석
            visual_analysis_results = await self._step_target_frame_analysis(video_path, candidates)
            self.state_manager.create_checkpoint(video_url, "visual_analysis_complete", 
                                               {"visual_analysis": visual_analysis_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis"])
            
            # 6단계: Gemini 2차 분석 (상세 정보 추출)
            final_results = await self._step_second_pass_analysis(
                candidates, script_data, visual_analysis_results, video_url
            )
            self.state_manager.create_checkpoint(video_url, "second_pass_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass"])
            
            # 7단계: PPL 콘텐츠 필터링
            final_results, filtered_ppl_results = await self._step_ppl_filtering(final_results)
            self.state_manager.create_checkpoint(video_url, "ppl_filtering_complete", 
                                               {"final_results": final_results, "filtered_ppl_results": filtered_ppl_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "ppl_filtering"])
            
            # 8단계: 수익화 검증 (쿠팡 파트너스 API)
            final_results = await self._step_monetization_verification(final_results)
            self.state_manager.create_checkpoint(video_url, "monetization_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "ppl_filtering", "monetization"])
            
            # 9단계: 매력도 스코어링
            final_results = await self._step_attractiveness_scoring(final_results, script_data, video_url)
            self.state_manager.create_checkpoint(video_url, "scoring_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "ppl_filtering", "monetization", "scoring"])
            
            # 10단계: 최종 JSON 스키마 매핑
            final_results = await self._step_final_schema_mapping(final_results, video_url)
            self.state_manager.create_checkpoint(video_url, "schema_mapping_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "ppl_filtering", "monetization", "scoring", "schema_mapping"])
            
            # 11단계: 후처리 및 정리
            await self._step_finalization(audio_path, video_path)
            
            # 파이프라인 성공 완료
            processing_time = time.time() - start_time
            result.status = PipelineStatus.COMPLETED
            result.processing_time = processing_time
            result.result_data = final_results
            result.step_logs = self.step_logs
            
            self.current_status = PipelineStatus.COMPLETED
            self.logger.info(f"AI 분석 파이프라인 완료 - 소요시간: {processing_time:.2f}초")
            self._log_step("pipeline", "success", f"파이프라인 완료 - 소요시간: {processing_time:.2f}초")
            
            # 완료 상태 저장 및 상태 파일 정리
            self.state_manager.mark_completed(video_url, {"result": final_results, "processing_time": processing_time})
            
            return result
            
        except Exception as e:
            # 파이프라인 실패 처리
            processing_time = time.time() - start_time
            error_message = f"파이프라인 실패: {str(e)}"
            
            result.status = PipelineStatus.FAILED
            result.processing_time = processing_time
            result.error_message = error_message
            result.step_logs = self.step_logs
            
            self.current_status = PipelineStatus.FAILED
            self.logger.error(f"{error_message}\n{traceback.format_exc()}")
            self._log_step("pipeline", "error", error_message, processing_time)
            
            # 에러 상태 저장
            self.state_manager.mark_error(video_url, "pipeline_error", {
                "error_message": error_message,
                "traceback": traceback.format_exc(),
                "processing_time": processing_time
            })
            
            return result
    
    async def _step_initialization(self, video_url: str):
        """1단계: 초기화 및 검증"""
        step_start = time.time()
        
        try:
            # URL 형식 검증
            if not video_url or not video_url.startswith(('https://youtube.com/', 'https://www.youtube.com/')):
                raise ValueError("유효하지 않은 YouTube URL입니다")
            
            # 모듈 상태 검증
            self._validate_modules()
            
            step_time = time.time() - step_start
            self._log_step("initialization", "success", "초기화 및 검증 완료", step_time)
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("initialization", "error", f"초기화 실패: {str(e)}", step_time)
            raise
    
    async def _step_download_media(self, video_url: str) -> tuple[Path, Path]:
        """2단계: YouTube 영상 및 음성 다운로드"""
        step_start = time.time()
        
        try:
            self.logger.info("YouTube 영상 및 음성 다운로드 시작")
            
            # 다운로드 실행 (컨텍스트 매니저 사용하지 않음 - 파일 유지 필요)
            audio_path = self.youtube_downloader.download_audio(video_url)
            # 영상 다운로드 (720p 이하 품질)
            video_path = self.youtube_downloader.download_video(video_url)
                
            if not audio_path or not audio_path.exists():
                raise Exception("오디오 다운로드 실패")
            
            if not video_path or not video_path.exists():
                raise Exception("영상 다운로드 실패")
            
            step_time = time.time() - step_start
            self._log_step("download", "success", 
                         f"미디어 다운로드 완료: 음성({audio_path}), 영상({video_path})", 
                         step_time)
            
            return audio_path, video_path
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("download", "error", f"다운로드 실패: {str(e)}", step_time)
            raise
    
    @with_graceful_degradation('whisper', fallback_func=lambda self, audio_path: self.degradation_handler.get_fallback_transcription_result())
    async def _step_transcribe_audio(self, audio_path: Path) -> List[Dict[str, Any]]:
        """3단계: Whisper 음성 인식 (Graceful Degradation 적용)"""
        step_start = time.time()
        
        try:
            # Whisper 프로세서가 없는 경우 폴백
            if self.whisper_processor is None:
                self.logger.warning("Whisper 프로세서가 없음 - 폴백 결과 사용")
                fallback_result = self.degradation_handler.get_fallback_transcription_result()
                step_time = time.time() - step_start
                self._log_step("transcription", "fallback", 
                              f"음성 인식 폴백 - {len(fallback_result)}개 세그먼트", step_time)
                return fallback_result
            
            self.logger.info("Whisper 음성 인식 시작")
            
            # 음성 인식 실행 
            segments = self.whisper_processor.transcribe_audio_file(audio_path)
            
            if not segments:
                raise Exception("음성 인식 실패 - 결과 없음")
            
            # JSON 형태로 포맷팅
            script_data = self.whisper_processor.format_segments_to_json(segments)
            
            # 성공 기록
            self.degradation_handler.record_service_success('whisper')
            
            step_time = time.time() - step_start
            self._log_step("transcription", "success", 
                          f"음성 인식 완료 - {len(script_data)}개 세그먼트", step_time)
            
            return script_data
            
        except Exception as e:
            self.degradation_handler.record_service_error('whisper', str(e))
            step_time = time.time() - step_start
            self._log_step("transcription", "error", f"음성 인식 실패: {str(e)}", step_time)
            raise
    
    async def _step_first_pass_analysis(self, script_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """4단계: Gemini 1차 분석 (후보 구간 탐지)"""
        step_start = time.time()
        
        try:
            self.logger.info("Gemini 1차 분석 시작")
            
            # 재시도 로직으로 1차 분석 실행
            candidates = await self._retry_with_backoff(
                self.first_pass_analyzer.analyze_script, 
                script_data,
                max_retries=2
            )
            
            step_time = time.time() - step_start
            self._log_step("first_pass", "success", 
                          f"1차 분석 완료 - {len(candidates)}개 후보 구간 탐지", step_time)
            
            return candidates
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("first_pass", "error", f"1차 분석 실패: {str(e)}", step_time)
            raise
    
    async def _step_target_frame_analysis(
        self, 
        video_path: Path, 
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """5단계: 타겟 시간대 시각 분석"""
        step_start = time.time()
        
        try:
            self.logger.info("타겟 프레임 시각 분석 시작")
            
            if not candidates:
                self.logger.warning("1차 분석에서 후보 구간이 발견되지 않았습니다")
                return []
            
            # 후보 구간들을 TargetTimeframe 객체로 변환
            target_timeframes = []
            for candidate in candidates:
                timeframe = TargetTimeframe(
                    start_time=candidate.get('start_time', 0),
                    end_time=candidate.get('end_time', 0),
                    reason=candidate.get('reason', ''),
                    confidence_score=candidate.get('confidence_score', 0.5)
                )
                target_timeframes.append(timeframe)
            
            # 다중 시간대 시각 분석 수행
            visual_analysis_results = await asyncio.get_event_loop().run_in_executor(
                None, 
                self.target_frame_extractor.analyze_multiple_timeframes,
                str(video_path),
                target_timeframes
            )
            
            # 결과를 딕셔너리 형태로 변환 (JSON 직렬화 가능하도록)
            serializable_results = []
            for result in visual_analysis_results:
                serializable_result = {
                    'target_timeframe': {
                        'start_time': result.target_timeframe.start_time,
                        'end_time': result.target_timeframe.end_time,
                        'reason': result.target_timeframe.reason,
                        'confidence_score': result.target_timeframe.confidence_score
                    },
                    'total_frames_extracted': result.total_frames_extracted,
                    'successful_analyses': result.successful_analyses,
                    'summary_texts': result.summary_texts,
                    'summary_objects': result.summary_objects,
                    'processing_stats': result.processing_stats,
                    'total_processing_time': result.total_processing_time
                }
                serializable_results.append(serializable_result)
            
            step_time = time.time() - step_start
            self._log_step("visual_analysis", "success", 
                         f"시각 분석 완료: {len(visual_analysis_results)}개 구간 처리", step_time,
                         processed_timeframes=len(visual_analysis_results))
            
            return serializable_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("visual_analysis", "error", f"시각 분석 실패: {str(e)}", step_time)
            raise
    
    async def _step_second_pass_analysis(
        self, 
        candidates: List[Dict[str, Any]], 
        script_data: List[Dict[str, Any]],
        visual_analysis_results: List[Dict[str, Any]],
        video_url: str
    ) -> List[Dict[str, Any]]:
        """5단계: Gemini 2차 분석 (시각 분석 결과 통합) - 병렬 처리 최적화"""
        step_start = time.time()
        
        try:
            self.logger.info("Gemini 2차 분석 시작 (병렬 처리 적용)")
            
            if not candidates:
                self.logger.warning("1차 분석에서 후보 구간이 발견되지 않았습니다")
                return []
            
            # 병렬 처리를 위한 작업 준비
            analysis_tasks = []
            
            for i, candidate in enumerate(candidates):
                # 각 후보에 대한 분석 작업 준비
                segment_data = self._extract_segment_data(candidate, script_data)
                visual_data = self._match_visual_analysis_results(candidate, visual_analysis_results)
                
                source_info = {
                    'video_url': video_url,
                    'segment_data': segment_data,
                    'visual_analysis': visual_data
                }
                
                # 비동기 작업 생성
                task = self._analyze_candidate_parallel(i, candidate, source_info, visual_data)
                analysis_tasks.append(task)
            
            # 병렬 실행 (최대 3개 동시 처리)
            final_results = []
            batch_size = min(3, len(analysis_tasks))  # API 제한 고려
            
            for i in range(0, len(analysis_tasks), batch_size):
                batch = analysis_tasks[i:i+batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                
                # 결과 처리
                for result in batch_results:
                    if isinstance(result, Exception):
                        self.logger.warning(f"병렬 분석 작업 실패: {str(result)}")
                        continue
                    if result:
                        final_results.append(result)
                
                # 배치 간 간격 (API 제한 고려)
                if i + batch_size < len(analysis_tasks):
                    await asyncio.sleep(1)
            
            step_time = time.time() - step_start
            self._log_step("second_pass", "success", 
                          f"2차 분석 완료 (병렬 처리) - {len(final_results)}개 제품 정보 추출", step_time)
            
            return final_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("second_pass", "error", f"2차 분석 실패: {str(e)}", step_time)
            raise
    
    async def _analyze_candidate_parallel(
        self, 
        index: int, 
        candidate: Dict[str, Any], 
        source_info: Dict[str, Any], 
        visual_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """개별 후보에 대한 병렬 분석"""
        try:
            self.logger.debug(f"후보 구간 {index+1} 병렬 분석 시작")
            
            # 재시도 로직으로 2차 분석 실행
            detailed_info = await self._retry_with_backoff(
                self.second_pass_analyzer.extract_product_info,
                candidate, source_info,
                max_retries=2
            )
            
            if detailed_info:
                # 시각 분석 결과 통합
                detailed_info = self._integrate_visual_analysis_to_result(detailed_info, visual_data)
                return detailed_info
                
        except Exception as e:
            self.logger.warning(f"후보 구간 {index+1} 병렬 분석 실패: {str(e)}")
            return None
    
    async def _step_ppl_filtering(self, analysis_results: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """7단계: PPL 콘텐츠 필터링 (PRD 3.1 요구사항)"""
        step_start = time.time()
        
        try:
            self.logger.info("PPL 콘텐츠 필터링 시작")
            
            passed_results = []
            filtered_ppl_results = []
            
            ppl_threshold = self.config.PPL_FILTER_THRESHOLD
            
            for result in analysis_results:
                try:
                    # status_info에서 PPL 확률 추출
                    status_info = result.get('status_info', {})
                    ppl_confidence = status_info.get('ppl_confidence', 0.0)
                    
                    # PPL 확률이 임계값을 초과하는지 확인
                    if ppl_confidence >= ppl_threshold:
                        # PPL 필터링 상태로 분류
                        result['status_info']['current_status'] = 'filtered_ppl'
                        result['status_info']['is_ppl'] = True
                        filtered_ppl_results.append(result)
                        
                        # 제품명 추출
                        product_name = result.get('candidate_info', {}).get('product_name_ai', 'Unknown')
                        self.logger.info(f"제품 '{product_name}' PPL 필터링됨 - 확률: {ppl_confidence:.3f}")
                        
                    else:
                        # 필터링 통과
                        result['status_info']['is_ppl'] = False
                        if result['status_info']['current_status'] == 'analysis_complete':
                            result['status_info']['current_status'] = 'needs_review'
                        passed_results.append(result)
                        
                        # 제품명 추출
                        product_name = result.get('candidate_info', {}).get('product_name_ai', 'Unknown')
                        self.logger.debug(f"제품 '{product_name}' PPL 필터링 통과 - 확률: {ppl_confidence:.3f}")
                        
                except Exception as e:
                    self.logger.warning(f"개별 PPL 필터링 실패: {str(e)}")
                    # 실패한 경우 안전하게 필터링 통과로 처리
                    if 'status_info' not in result:
                        result['status_info'] = {}
                    result['status_info']['is_ppl'] = False
                    result['status_info']['ppl_confidence'] = 0.0
                    if result['status_info'].get('current_status') == 'analysis_complete':
                        result['status_info']['current_status'] = 'needs_review'
                    passed_results.append(result)
                    continue
            
            step_time = time.time() - step_start
            
            self._log_step("ppl_filtering", "success", 
                          f"PPL 필터링 완료 - 통과: {len(passed_results)}개, 필터링: {len(filtered_ppl_results)}개 (임계값: {ppl_threshold})", 
                          step_time,
                          passed_count=len(passed_results),
                          filtered_count=len(filtered_ppl_results),
                          threshold=ppl_threshold)
            
            return passed_results, filtered_ppl_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("ppl_filtering", "error", f"PPL 필터링 실패: {str(e)}", step_time)
            
            # 실패한 경우 모든 결과를 통과로 처리 (안전 모드)
            for result in analysis_results:
                if 'status_info' not in result:
                    result['status_info'] = {}
                result['status_info']['is_ppl'] = False
                result['status_info']['ppl_confidence'] = 0.0
                if result['status_info'].get('current_status') == 'analysis_complete':
                    result['status_info']['current_status'] = 'needs_review'
            
            return analysis_results, []

    async def _step_monetization_verification(self, analysis_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """8단계: 수익화 검증 (쿠팡 파트너스 API)"""
        step_start = time.time()
        
        try:
            self.logger.info("수익화 검증 시작")
            
            updated_results = []
            
            for result in analysis_results:
                try:
                    # 제품명 추출
                    candidate_info = result.get('candidate_info', {})
                    product_name = candidate_info.get('product_name_ai', '')
                    
                    if not product_name:
                        self.logger.warning("제품명이 없어 수익화 검증 건너뜀")
                        # 수익화 정보 기본값 설정
                        result['monetization_info'] = {
                            'is_coupang_product': False,
                            'coupang_url_ai': None,
                            'coupang_url_manual': None,
                            'search_keywords_used': [],
                            'product_match_confidence': None,
                            'commission_rate': None,
                            'coupang_price': None,
                            'verification_timestamp': time.time()
                        }
                        updated_results.append(result)
                        continue
                    
                    # 수익화 검증 수행
                    monetization_result = self.monetization_service.verify_product_monetization(product_name)
                    
                    # 결과를 JSON 스키마에 맞게 업데이트
                    monetization_info = {
                        'is_coupang_product': monetization_result.is_monetizable,
                        'coupang_url_ai': None,
                        'coupang_url_manual': None,
                        'search_keywords_used': monetization_result.search_keywords_used,
                        'product_match_confidence': None,
                        'commission_rate': None,
                        'coupang_price': None,
                        'verification_timestamp': time.time()
                    }
                    
                    # 성공적으로 매칭된 경우 추가 정보 설정
                    if monetization_result.is_monetizable and monetization_result.best_match:
                        monetization_info.update({
                            'product_match_confidence': monetization_result.best_match.match_confidence,
                            'commission_rate': monetization_result.best_match.commission_rate,
                            'coupang_price': monetization_result.best_match.price
                        })
                        
                        if monetization_result.affiliate_link:
                            monetization_info['coupang_url_ai'] = monetization_result.affiliate_link.affiliate_url
                    
                    # 결과에 수익화 정보 추가
                    result['monetization_info'] = monetization_info
                    
                    # 상태 정보도 업데이트 (수익화 불가능한 경우 필터링 목록으로 분류)
                    if 'status_info' in result:
                        if not monetization_result.is_monetizable:
                            result['status_info']['current_status'] = 'filtered_no_coupang'
                    
                    updated_results.append(result)
                    
                    self.logger.info(f"제품 '{product_name}' 수익화 검증 완료 - 가능: {monetization_result.is_monetizable}")
                    
                except Exception as e:
                    self.logger.warning(f"개별 제품 수익화 검증 실패: {str(e)}")
                    # 실패한 경우 기본값으로 설정
                    result['monetization_info'] = {
                        'is_coupang_product': False,
                        'coupang_url_ai': None,
                        'coupang_url_manual': None,
                        'search_keywords_used': [],
                        'product_match_confidence': None,
                        'commission_rate': None,
                        'coupang_price': None,
                        'verification_timestamp': time.time()
                    }
                    updated_results.append(result)
                    continue
            
            step_time = time.time() - step_start
            monetizable_count = sum(1 for r in updated_results if r.get('monetization_info', {}).get('is_coupang_product', False))
            
            self._log_step("monetization", "success", 
                         f"수익화 검증 완료 - {monetizable_count}/{len(updated_results)}개 제품 수익화 가능", 
                         step_time)
            
            return updated_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("monetization", "error", f"수익화 검증 실패: {str(e)}", step_time)
            
            # 실패한 경우 기본 수익화 정보로 결과 반환
            for result in analysis_results:
                if 'monetization_info' not in result:
                    result['monetization_info'] = {
                        'is_coupang_product': False,
                        'coupang_url_ai': None,
                        'coupang_url_manual': None,
                        'search_keywords_used': [],
                        'product_match_confidence': None,
                        'commission_rate': None,
                        'coupang_price': None,
                        'verification_timestamp': time.time()
                    }
            
            return analysis_results

    async def _step_attractiveness_scoring(
        self, 
        analysis_results: List[Dict[str, Any]], 
        script_data: List[Dict[str, Any]], 
        video_url: str
    ) -> List[Dict[str, Any]]:
        """9단계: 매력도 스코어링"""
        step_start = time.time()
        
        try:
            self.logger.info("매력도 스코어링 시작")
            
            # 채널 정보 추출 (video_url에서)
            channel_metrics = self._extract_channel_metrics(video_url)
            
            updated_results = []
            
            for result in analysis_results:
                try:
                    candidate_info = result.get('candidate_info', {})
                    
                    # 스코어링 입력 데이터 준비
                    scoring_input = self._prepare_scoring_input(
                        result, script_data, channel_metrics
                    )
                    
                    # 매력도 점수 계산
                    score_details = self.score_calculator.calculate_attractiveness_score(scoring_input)
                    
                    # 기존 score_details 업데이트
                    if 'candidate_info' in result and 'score_details' in result['candidate_info']:
                        result['candidate_info']['score_details'] = {
                            'total': score_details.total,
                            'sentiment_score': score_details.sentiment_score,
                            'endorsement_score': score_details.endorsement_score,
                            'influencer_score': score_details.influencer_score
                        }
                    
                    # 분류 및 추천사항 생성
                    classification = self.score_calculator.classify_by_thresholds(score_details.total)
                    
                    # 상태 정보 업데이트 (스코어 기반)
                    if 'status_info' in result:
                        # 낮은 점수는 리뷰 필요로 분류
                        if score_details.total < 60 and result['status_info']['current_status'] == 'needs_review':
                            result['status_info']['current_status'] = 'needs_review'
                        elif score_details.total >= 80:
                            # 높은 점수는 자동 승인 고려
                            if result['status_info']['current_status'] == 'needs_review':
                                result['status_info']['current_status'] = 'approved'
                    
                    updated_results.append(result)
                    
                    self.logger.debug(f"매력도 스코어링 완료 - 점수: {score_details.total}")
                    
                except Exception as e:
                    self.logger.warning(f"개별 결과 스코어링 실패: {str(e)}")
                    # 스코어링 실패 시 기본값 설정
                    if 'candidate_info' in result and 'score_details' not in result['candidate_info']:
                        result['candidate_info']['score_details'] = {
                            'total': 50,
                            'sentiment_score': 0.5,
                            'endorsement_score': 0.5,
                            'influencer_score': 0.5
                        }
                    updated_results.append(result)
                    continue
            
            step_time = time.time() - step_start
            avg_score = sum(r.get('candidate_info', {}).get('score_details', {}).get('total', 0) 
                           for r in updated_results) / len(updated_results) if updated_results else 0
            
            self._log_step("scoring", "success", 
                         f"매력도 스코어링 완료 - {len(updated_results)}개 결과, 평균 점수: {avg_score:.1f}", 
                         step_time)
            
            return updated_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("scoring", "error", f"매력도 스코어링 실패: {str(e)}", step_time)
            
            # 실패한 경우 기본 점수로 결과 반환
            for result in analysis_results:
                if 'candidate_info' in result and 'score_details' not in result['candidate_info']:
                    result['candidate_info']['score_details'] = {
                        'total': 50,
                        'sentiment_score': 0.5,
                        'endorsement_score': 0.5,
                        'influencer_score': 0.5
                    }
            
            return analysis_results

    async def _step_final_schema_mapping(
        self,
        analysis_results: List[Dict[str, Any]],
        video_url: str
    ) -> List[Dict[str, Any]]:
        """10단계: 최종 JSON 스키마 매핑"""
        step_start = time.time()
        
        try:
            self.logger.info("최종 JSON 스키마 매핑 시작")
            
            mapped_results = []
            formatter = APIResponseFormatter()
            
            for result in analysis_results:
                try:
                    # PRD 완전한 JSON 스키마로 매핑
                    mapped_result = self._map_to_prd_schema(result, video_url)
                    
                    # Pydantic 모델로 검증
                    validated_candidate = ProductRecommendationCandidate(**mapped_result)
                    
                    # API 응답 형식으로 포맷팅
                    api_formatted = formatter.format_candidate_response(validated_candidate)
                    
                    mapped_results.append(api_formatted)
                    
                    self.logger.debug(f"스키마 매핑 완료: {validated_candidate.get_final_product_name()}")
                    
                except Exception as e:
                    self.logger.warning(f"개별 결과 스키마 매핑 실패: {str(e)}")
                    # 매핑 실패 시 원본 결과 유지
                    mapped_results.append(result)
                    continue
            
            step_time = time.time() - step_start
            self._log_step("schema_mapping", "success", 
                         f"스키마 매핑 완료 - {len(mapped_results)}개 결과 검증", step_time)
            
            return mapped_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("schema_mapping", "error", f"스키마 매핑 실패: {str(e)}", step_time)
            
            # 매핑 실패 시 원본 결과 반환
            return analysis_results
    
    async def _get_video_metadata(self, video_url: str) -> Dict[str, Any]:
        """YouTube API를 사용하여 비디오 메타데이터 추출"""
        try:
            if self.youtube_api_client:
                video_info = await self.youtube_api_client.get_video_info(video_url)
                channel_info = await self.youtube_api_client.get_channel_info(video_info.channel_id)
                
                # 업로드 날짜 포맷팅
                try:
                    upload_date = datetime.fromisoformat(video_info.published_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                except:
                    upload_date = datetime.now().strftime('%Y-%m-%d')
                
                return {
                    'video_title': video_info.title,
                    'channel_name': video_info.channel_title,
                    'channel_id': video_info.channel_id,
                    'upload_date': upload_date,
                    'view_count': video_info.view_count,
                    'like_count': video_info.like_count,
                    'subscriber_count': channel_info.subscriber_count
                }
            else:
                self.logger.warning("YouTube API 클라이언트가 없어 기본 메타데이터 사용")
                
        except Exception as e:
            self.logger.warning(f"YouTube API를 통한 비디오 메타데이터 추출 실패: {str(e)}")
        
        # API 사용 불가능한 경우 기본값 반환
        import re
        url_pattern = r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
        video_id_match = re.search(url_pattern, video_url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        
        return {
            'video_title': f'영상 제목 ({video_id})',
            'channel_name': '알려지지 않은 채널',
            'channel_id': 'unknown',
            'upload_date': datetime.now().strftime('%Y-%m-%d'),
            'view_count': 0,
            'like_count': 0,
            'subscriber_count': 0
        }
    
    async def _map_to_prd_schema(self, result: Dict[str, Any], video_url: str) -> Dict[str, Any]:
        """개별 결과를 PRD 완전한 JSON 스키마로 매핑"""
        from datetime import datetime
        
        # YouTube API를 통한 실제 비디오 메타데이터 추출
        video_metadata = await self._get_video_metadata(video_url)
        
        candidate_info = result.get('candidate_info', {})
        monetization_info = result.get('monetization_info', {})
        status_info = result.get('status_info', {})
        
        # 현재 시간
        now = datetime.now().isoformat()
        
        return {
            "source_info": {
                "celebrity_name": result.get('source_info', {}).get('celebrity_name', video_metadata['channel_name']),
                "channel_name": video_metadata['channel_name'],
                "video_title": video_metadata['video_title'],
                "video_url": video_url,
                "upload_date": video_metadata['upload_date']
            },
            "candidate_info": {
                "product_name_ai": candidate_info.get('product_name_ai', ''),
                "product_name_manual": candidate_info.get('product_name_manual'),
                "clip_start_time": candidate_info.get('clip_start_time', 0),
                "clip_end_time": candidate_info.get('clip_end_time', 0),
                "category_path": candidate_info.get('category_path', ['기타']),
                "features": candidate_info.get('features', []),
                "score_details": {
                    "total": candidate_info.get('score_details', {}).get('total', 50),
                    "sentiment_score": candidate_info.get('score_details', {}).get('sentiment_score', 0.5),
                    "endorsement_score": candidate_info.get('score_details', {}).get('endorsement_score', 0.5),
                    "influencer_score": candidate_info.get('score_details', {}).get('influencer_score', 0.5)
                },
                "hook_sentence": candidate_info.get('hook_sentence', ''),
                "summary_for_caption": candidate_info.get('summary_for_caption', ''),
                "target_audience": candidate_info.get('target_audience', []),
                "price_point": candidate_info.get('price_point', '일반'),
                "endorsement_type": candidate_info.get('endorsement_type', '자연스러운 언급'),
                "recommended_titles": candidate_info.get('recommended_titles', []),
                "recommended_hashtags": candidate_info.get('recommended_hashtags', [])
            },
            "monetization_info": {
                "is_coupang_product": monetization_info.get('is_coupang_product', False),
                "coupang_url_ai": monetization_info.get('coupang_url_ai'),
                "coupang_url_manual": monetization_info.get('coupang_url_manual')
            },
            "status_info": {
                "current_status": status_info.get('current_status', 'needs_review'),
                "is_ppl": status_info.get('is_ppl', False),
                "ppl_confidence": status_info.get('ppl_confidence', 0.1),
                "last_updated": now
            },
            "schema_version": "1.0",
            "created_at": now,
            "updated_at": now
        }
    
    async def _extract_channel_metrics(self, video_url: str) -> ChannelMetrics:
        """비디오 URL에서 채널 메트릭스 추출"""
        try:
            if self.youtube_api_client:
                # YouTube API를 사용하여 실제 채널 정보 추출
                channel_info = await self.youtube_api_client.get_channel_info_from_video(video_url)
                
                # 채널 생성일로부터 개월 수 계산
                from datetime import datetime
                try:
                    published_date = datetime.fromisoformat(channel_info.published_at.replace('Z', '+00:00'))
                    current_date = datetime.now(published_date.tzinfo)
                    channel_age_months = max(1, int((current_date - published_date).days / 30.44))
                except:
                    channel_age_months = 24  # 기본값
                
                # 평균 영상 조회수 계산 (전체 조회수 / 영상 수)
                avg_video_views = channel_info.view_count // max(1, channel_info.video_count)
                
                # 참여율 추정 (실제 API로는 정확한 계산 어려움, 추정값 사용)
                engagement_rate = min(0.1, max(0.01, (channel_info.subscriber_count / max(1, channel_info.view_count)) * 10))
                
                return ChannelMetrics(
                    subscriber_count=channel_info.subscriber_count,
                    video_view_count=avg_video_views,
                    video_count=channel_info.video_count,
                    channel_age_months=channel_age_months,
                    engagement_rate=engagement_rate,
                    verified_status=channel_info.verified
                )
                
            else:
                self.logger.warning("YouTube API 클라이언트가 없어 기본값 사용")
                
        except Exception as e:
            self.logger.warning(f"YouTube API를 통한 채널 정보 추출 실패, 기본값 사용: {str(e)}")
        
        # YouTube API 사용 불가능한 경우 기본값 반환
        return ChannelMetrics(
            subscriber_count=100000,  # 기본값 10만
            video_view_count=50000,   # 기본값 5만
            video_count=200,          # 기본값 200개
            channel_age_months=24,    # 기본값 2년
            engagement_rate=0.05,     # 기본값 5%
            verified_status=False     # 기본값 미인증
        )
    
    def _prepare_scoring_input(
        self, 
        result: Dict[str, Any], 
        script_data: List[Dict[str, Any]], 
        channel_metrics: ChannelMetrics
    ) -> ScoringInput:
        """스코어링 입력 데이터 준비"""
        candidate_info = result.get('candidate_info', {})
        
        # 텍스트 추출
        start_time = candidate_info.get('clip_start_time', 0)
        end_time = candidate_info.get('clip_end_time', 0)
        
        # 해당 구간의 스크립트 텍스트 추출
        transcript_text = ""
        for segment in script_data:
            seg_start = segment.get('start', 0)
            seg_end = segment.get('end', 0)
            
            # 겹치는 구간인지 확인
            if seg_start <= end_time and seg_end >= start_time:
                transcript_text += segment.get('text', '') + " "
        
        # 사용 패턴 추출 (features에서)
        usage_patterns = candidate_info.get('features', [])
        if isinstance(usage_patterns, list):
            usage_patterns = [str(feature) for feature in usage_patterns]
        else:
            usage_patterns = [str(usage_patterns)] if usage_patterns else []
        
        # 시연 레벨 추정 (임시)
        demonstration_level = 1
        if any(keyword in transcript_text.lower() for keyword in ['보여드릴', '직접', '시연', '테스트']):
            demonstration_level = 2
        if any(keyword in transcript_text.lower() for keyword in ['실시간', '지금', '바로']):
            demonstration_level = 3
        
        return ScoringInput(
            transcript_text=transcript_text.strip(),
            usage_patterns=usage_patterns,
            demonstration_level=demonstration_level,
            channel_metrics=channel_metrics,
            tone_indicators=None,
            reputation_score=None
        )
    
    def _match_visual_analysis_results(self, candidate: Dict[str, Any], visual_analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """후보 구간과 시각 분석 결과 매칭"""
        candidate_start = candidate.get('start_time', 0)
        candidate_end = candidate.get('end_time', 0)
        
        # 해당 구간과 겹치는 시각 분석 결과 찾기
        matched_visual_data = {
            'detected_texts': [],
            'detected_objects': [],
            'product_images': [],
            'frame_analysis_count': 0
        }
        
        for visual_result in visual_analysis_results:
            timeframe = visual_result.get('target_timeframe', {})
            visual_start = timeframe.get('start_time', 0)
            visual_end = timeframe.get('end_time', 0)
            
            # 시간대 겹침 확인
            if visual_start <= candidate_end and visual_end >= candidate_start:
                # 텍스트 결과 수집
                summary_texts = visual_result.get('summary_texts', [])
                matched_visual_data['detected_texts'].extend(summary_texts)
                
                # 객체 결과 수집
                summary_objects = visual_result.get('summary_objects', [])
                matched_visual_data['detected_objects'].extend(summary_objects)
                
                # 제품 이미지 수집 (확장 속성이 있는 경우)
                if hasattr(visual_result, 'selected_product_images'):
                    matched_visual_data['product_images'].extend(visual_result.selected_product_images)
                
                # 분석된 프레임 수 집계
                matched_visual_data['frame_analysis_count'] += visual_result.get('successful_analyses', 0)
        
        # 중복 제거
        matched_visual_data['detected_texts'] = list(set(matched_visual_data['detected_texts']))
        matched_visual_data['detected_objects'] = list(set(matched_visual_data['detected_objects']))
        
        return matched_visual_data
    
    def _integrate_visual_analysis_to_result(self, result: Dict[str, Any], visual_data: Dict[str, Any]) -> Dict[str, Any]:
        """시각 분석 결과를 최종 결과에 통합"""
        try:
            # 기존 결과에 시각 분석 정보 추가
            if 'candidate_info' not in result:
                result['candidate_info'] = {}
            
            # OCR로 발견된 텍스트 정보 추가
            detected_texts = visual_data.get('detected_texts', [])
            if detected_texts:
                result['candidate_info']['detected_texts_from_video'] = detected_texts
                
                # 제품명과 OCR 텍스트 매칭도 계산
                product_name = result['candidate_info'].get('product_name_ai', '')
                if product_name:
                    text_match_score = self._calculate_visual_text_match(product_name, detected_texts)
                    result['candidate_info']['visual_text_match_score'] = text_match_score
            
            # 객체 탐지 정보 추가
            detected_objects = visual_data.get('detected_objects', [])
            if detected_objects:
                result['candidate_info']['detected_objects_from_video'] = detected_objects
                
                # 제품 카테고리와 객체 매칭도 계산
                category_path = result['candidate_info'].get('category_path', [])
                if category_path:
                    object_match_score = self._calculate_visual_object_match(category_path, detected_objects)
                    result['candidate_info']['visual_object_match_score'] = object_match_score
            
            # 제품 이미지 정보 추가
            product_images = visual_data.get('product_images', [])
            if product_images:
                result['candidate_info']['product_images'] = product_images
                result['candidate_info']['product_image_count'] = len(product_images)
            
            # 시각 분석 메타데이터 추가
            result['candidate_info']['visual_analysis_metadata'] = {
                'frame_analysis_count': visual_data.get('frame_analysis_count', 0),
                'has_visual_confirmation': len(detected_texts) > 0 or len(detected_objects) > 0,
                'visual_confidence_boost': self._calculate_visual_confidence_boost(visual_data)
            }
            
            self.logger.debug(f"시각 분석 결과 통합 완료: 텍스트 {len(detected_texts)}개, 객체 {len(detected_objects)}개")
            
        except Exception as e:
            self.logger.warning(f"시각 분석 결과 통합 실패: {str(e)}")
        
        return result
    
    def _calculate_visual_text_match(self, product_name: str, detected_texts: List[str]) -> float:
        """제품명과 OCR 텍스트 매칭도 계산"""
        if not product_name or not detected_texts:
            return 0.0
        
        product_words = set(product_name.lower().split())
        max_match_score = 0.0
        
        for text in detected_texts:
            text_words = set(text.lower().split())
            if text_words and product_words:
                intersection = product_words.intersection(text_words)
                union = product_words.union(text_words)
                jaccard_score = len(intersection) / len(union) if union else 0
                max_match_score = max(max_match_score, jaccard_score)
        
        return round(max_match_score, 3)
    
    def _calculate_visual_object_match(self, category_path: List[str], detected_objects: List[str]) -> float:
        """제품 카테고리와 객체 탐지 매칭도 계산"""
        if not category_path or not detected_objects:
            return 0.0
        
        # 카테고리를 객체 클래스와 매핑하는 간단한 룰
        category_to_objects = {
            '화장품': ['bottle', 'tube', 'container', 'cosmetics'],
            '패션': ['clothing', 'shirt', 'pants', 'dress', 'shoes'],
            '액세서리': ['jewelry', 'watch', 'bag', 'accessory'],
            '전자제품': ['electronics', 'phone', 'computer', 'device'],
            '식품': ['food', 'drink', 'bottle', 'package']
        }
        
        max_match_score = 0.0
        for category in category_path:
            if category in category_to_objects:
                expected_objects = set(category_to_objects[category])
                detected_set = set([obj.lower() for obj in detected_objects])
                
                intersection = expected_objects.intersection(detected_set)
                if intersection:
                    match_score = len(intersection) / len(expected_objects)
                    max_match_score = max(max_match_score, match_score)
        
        return round(max_match_score, 3)
    
    def _calculate_visual_confidence_boost(self, visual_data: Dict[str, Any]) -> float:
        """시각 분석 기반 신뢰도 부스트 계산"""
        boost = 0.0
        
        # 텍스트 발견시 +0.1
        if visual_data.get('detected_texts'):
            boost += 0.1
        
        # 객체 발견시 +0.1
        if visual_data.get('detected_objects'):
            boost += 0.1
        
        # 제품 이미지 있을시 +0.05
        if visual_data.get('product_images'):
            boost += 0.05
        
        # 분석된 프레임 수에 따른 추가 보너스
        frame_count = visual_data.get('frame_analysis_count', 0)
        if frame_count >= 5:
            boost += 0.05
        
        return round(min(boost, 0.3), 3)  # 최대 30% 부스트

    async def _step_finalization(self, audio_path: Path, video_path: Path):
        """11단계: 후처리 및 리소스 정리"""
        step_start = time.time()
        
        try:
            # 임시 파일 정리
            if audio_path and audio_path.exists():
                try:
                    audio_path.unlink()
                    self.logger.debug(f"임시 오디오 파일 삭제: {audio_path}")
                except Exception as e:
                    self.logger.warning(f"임시 오디오 파일 삭제 실패: {str(e)}")
                    
            if video_path and video_path.exists() and video_path != audio_path:
                try:
                    video_path.unlink()
                    self.logger.debug(f"임시 비디오 파일 삭제: {video_path}")
                except Exception as e:
                    self.logger.warning(f"임시 비디오 파일 삭제 실패: {str(e)}")
            
            step_time = time.time() - step_start
            self._log_step("finalization", "success", "후처리 및 정리 완료", step_time)
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("finalization", "error", f"후처리 실패: {str(e)}", step_time)
            # 후처리 실패는 전체 파이프라인을 중단시키지 않음
    
    def _extract_segment_data(
        self, 
        candidate: Dict[str, Any], 
        script_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """후보 구간에 해당하는 스크립트 데이터 추출"""
        start_time = candidate.get('start_time', 0)
        end_time = candidate.get('end_time', 0)
        
        segment_data = []
        for segment in script_data:
            seg_start = segment.get('start', 0)
            seg_end = segment.get('end', 0)
            
            # 겹치는 구간인지 확인
            if seg_start <= end_time and seg_end >= start_time:
                segment_data.append(segment)
        
        return segment_data
    
    async def _retry_with_backoff(self, func, *args, max_retries: int = 3, **kwargs):
        """
        지수 백오프를 사용한 재시도 메커니즘
        
        Args:
            func: 실행할 함수
            max_retries: 최대 재시도 횟수
            *args, **kwargs: 함수 인자
            
        Returns:
            함수 실행 결과
            
        Raises:
            Exception: 모든 재시도 실패 시
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                if attempt == max_retries:
                    self.logger.error(f"재시도 {max_retries}회 모두 실패: {str(e)}")
                    raise
                
                # 지수 백오프 (1초, 2초, 4초...)
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(f"재시도 {attempt + 1}/{max_retries} - {wait_time:.1f}초 후 재시도: {str(e)}")
                
                await asyncio.sleep(wait_time)
        
        # 이 라인에 도달하면 안 됨
        raise last_exception
    
    def _validate_modules(self):
        """모듈 상태 검증"""
        try:
            # 필수 모듈 초기화 상태 확인
            if not hasattr(self, 'youtube_downloader'):
                raise Exception("YouTube 다운로더 초기화 실패")
            
            if not hasattr(self, 'whisper_processor'):
                raise Exception("Whisper 프로세서 초기화 실패")
                
            if not hasattr(self, 'first_pass_analyzer'):
                raise Exception("Gemini 1차 분석기 초기화 실패")
                
            if not hasattr(self, 'second_pass_analyzer'):
                raise Exception("Gemini 2차 분석기 초기화 실패")
                
            if not hasattr(self, 'target_frame_extractor'):
                raise Exception("타겟 프레임 추출기 초기화 실패")
            
            self.logger.debug("모든 모듈 상태 검증 완료")
            
        except Exception as e:
            self.logger.error(f"모듈 검증 실패: {str(e)}")
            raise
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """현재 파이프라인 상태 반환"""
        return {
            'status': self.current_status.value,
            'step_count': len(self.step_logs),
            'last_step': self.step_logs[-1] if self.step_logs else None,
            'config': {
                'whisper_model': self.config.WHISPER_MODEL_SIZE,
                'gemini_model': self.config.GEMINI_MODEL,
                'log_level': self.config.LOG_LEVEL
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """파이프라인 성능 메트릭 반환"""
        if not self.step_logs:
            return {}
        
        step_times = {}
        total_time = 0
        
        for log_entry in self.step_logs:
            step = log_entry['step']
            exec_time = log_entry.get('execution_time', 0)
            
            if exec_time and step != 'pipeline':
                step_times[step] = exec_time
                total_time += exec_time
        
        return {
            'total_time': total_time,
            'step_breakdown': step_times,
            'steps_completed': len([log for log in self.step_logs if log['status'] == 'success']),
            'errors_count': len([log for log in self.step_logs if log['status'] == 'error']),
            'performance_metrics': self.performance_metrics,
            'memory_usage': {
                'peak_mb': self.performance_metrics['memory_peak'],
                'current_mb': self._get_current_memory_usage()
            }
        }
    
    def _get_current_memory_usage(self) -> float:
        """현재 메모리 사용량 반환 (MB)"""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024
        except:
            return 0.0
    
    def cleanup(self):
        """리소스 정리"""
        try:
            # Thread Pool 종료
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=True)
                self.logger.info("Thread Pool 종료 완료")
            
            # 강제 가비지 컬렉션
            gc.collect()
            
            self.logger.info("파이프라인 리소스 정리 완료")
            
        except Exception as e:
            self.logger.warning(f"리소스 정리 중 오류: {str(e)}")
    
    def __del__(self):
        """소멸자에서 리소스 정리"""
        self.cleanup()


# 편의 함수
async def analyze_youtube_video(video_url: str, config: Optional[Config] = None) -> PipelineResult:
    """
    YouTube 영상 분석을 위한 편의 함수
    
    Args:
        video_url: YouTube 영상 URL
        config: 설정 객체
        
    Returns:
        분석 결과
    """
    pipeline = AIAnalysisPipeline(config)
    return await pipeline.process_video(video_url)


def analyze_youtube_video_sync(video_url: str, config: Optional[Config] = None) -> PipelineResult:
    """
    동기 실행을 위한 래퍼 함수
    
    Args:
        video_url: YouTube 영상 URL
        config: 설정 객체
        
    Returns:
        분석 결과
    """
    return asyncio.run(analyze_youtube_video(video_url, config))