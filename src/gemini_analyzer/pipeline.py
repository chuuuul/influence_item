"""
AI 분석 파이프라인 오케스트레이터

YouTube URL 입력부터 최종 제품 정보 JSON 출력까지의 완전 자동화된 워크플로우를 제공합니다.
"""

import asyncio
import json
import logging
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback
import random

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
    """AI 분석 파이프라인 오케스트레이터"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        파이프라인 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        
        # 모듈 초기화
        self.youtube_downloader = YouTubeDownloader(config)
        self.whisper_processor = WhisperProcessor(config)
        self.first_pass_analyzer = GeminiFirstPassAnalyzer(config)
        self.second_pass_analyzer = GeminiSecondPassAnalyzer(config)
        self.target_frame_extractor = TargetFrameExtractor(config)
        self.state_manager = StateManager(config)
        self.monetization_service = MonetizationService()
        self.score_calculator = ScoreCalculator()
        
        # 상태 관리
        self.current_status = PipelineStatus.PENDING
        self.step_logs = []
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _log_step(self, step_name: str, status: str, message: str, 
                  execution_time: Optional[float] = None, **extra_data):
        """파이프라인 단계 로그 기록"""
        log_entry = {
            'step': step_name,
            'status': status,
            'message': message,
            'timestamp': time.time(),
            'execution_time': execution_time,
            **extra_data
        }
        
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
            
            # 7단계: 수익화 검증 (쿠팡 파트너스 API)
            final_results = await self._step_monetization_verification(final_results)
            self.state_manager.create_checkpoint(video_url, "monetization_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "monetization"])
            
            # 8단계: 매력도 스코어링
            final_results = await self._step_attractiveness_scoring(final_results, script_data, video_url)
            self.state_manager.create_checkpoint(video_url, "scoring_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "monetization", "scoring"])
            
            # 9단계: 최종 JSON 스키마 매핑
            final_results = await self._step_final_schema_mapping(final_results, video_url)
            self.state_manager.create_checkpoint(video_url, "schema_mapping_complete", 
                                               {"final_results": final_results}, 
                                               ["initialization", "download", "transcription", "first_pass", "visual_analysis", "second_pass", "monetization", "scoring", "schema_mapping"])
            
            # 10단계: 후처리 및 정리
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
            
            with self.youtube_downloader:
                audio_path = self.youtube_downloader.download_audio(video_url)
                # 영상 다운로드는 임시로 음성 파일과 같은 경로로 설정 (실제로는 다른 메서드 필요)
                video_path = audio_path  # TODO: 실제 영상 다운로드 구현
                
            if not audio_path or not audio_path.exists():
                raise Exception("오디오 다운로드 실패")
            
            step_time = time.time() - step_start
            self._log_step("download", "success", f"미디어 다운로드 완료: 음성({audio_path})", step_time)
            
            return audio_path, video_path
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("download", "error", f"다운로드 실패: {str(e)}", step_time)
            raise
    
    async def _step_transcribe_audio(self, audio_path: Path) -> List[Dict[str, Any]]:
        """3단계: Whisper 음성 인식"""
        step_start = time.time()
        
        try:
            self.logger.info("Whisper 음성 인식 시작")
            
            # 음성 인식 실행 
            segments = self.whisper_processor.transcribe_audio_file(audio_path)
            
            if not segments:
                raise Exception("음성 인식 실패 - 결과 없음")
            
            # JSON 형태로 포맷팅
            script_data = self.whisper_processor.format_segments_to_json(segments)
            
            step_time = time.time() - step_start
            self._log_step("transcription", "success", 
                          f"음성 인식 완료 - {len(script_data)}개 세그먼트", step_time)
            
            return script_data
            
        except Exception as e:
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
        """5단계: Gemini 2차 분석 (상세 정보 추출)"""
        step_start = time.time()
        
        try:
            self.logger.info("Gemini 2차 분석 시작")
            
            if not candidates:
                self.logger.warning("1차 분석에서 후보 구간이 발견되지 않았습니다")
                return []
            
            final_results = []
            
            for i, candidate in enumerate(candidates):
                try:
                    self.logger.info(f"후보 구간 {i+1}/{len(candidates)} 상세 분석 중")
                    
                    # 해당 구간의 스크립트 추출
                    segment_data = self._extract_segment_data(candidate, script_data)
                    
                    # 영상 소스 정보 구성
                    source_info = {
                        'video_url': video_url,
                        'segment_data': segment_data
                    }
                    
                    # 재시도 로직으로 2차 분석 실행
                    detailed_info = await self._retry_with_backoff(
                        self.second_pass_analyzer.extract_product_info,
                        candidate, source_info,
                        max_retries=2
                    )
                    
                    if detailed_info:
                        final_results.append(detailed_info)
                        
                except Exception as e:
                    self.logger.warning(f"후보 구간 {i+1} 분석 실패: {str(e)}")
                    continue
            
            step_time = time.time() - step_start
            self._log_step("second_pass", "success", 
                          f"2차 분석 완료 - {len(final_results)}개 제품 정보 추출", step_time)
            
            return final_results
            
        except Exception as e:
            step_time = time.time() - step_start
            self._log_step("second_pass", "error", f"2차 분석 실패: {str(e)}", step_time)
            raise
    
    async def _step_monetization_verification(self, analysis_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """7단계: 수익화 검증 (쿠팡 파트너스 API)"""
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
        """8단계: 매력도 스코어링"""
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
        """9단계: 최종 JSON 스키마 매핑"""
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
    
    def _map_to_prd_schema(self, result: Dict[str, Any], video_url: str) -> Dict[str, Any]:
        """개별 결과를 PRD 완전한 JSON 스키마로 매핑"""
        from datetime import datetime
        import re
        
        # 비디오 URL에서 채널명과 제목 추출 (임시 구현)
        # TODO: 실제 YouTube API로 교체
        url_pattern = r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
        video_id_match = re.search(url_pattern, video_url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        
        candidate_info = result.get('candidate_info', {})
        monetization_info = result.get('monetization_info', {})
        status_info = result.get('status_info', {})
        
        # 현재 시간
        now = datetime.now().isoformat()
        
        return {
            "source_info": {
                "celebrity_name": result.get('source_info', {}).get('celebrity_name', '알려지지 않은 연예인'),
                "channel_name": result.get('source_info', {}).get('channel_name', '알려지지 않은 채널'),
                "video_title": result.get('source_info', {}).get('video_title', '영상 제목'),
                "video_url": video_url,
                "upload_date": result.get('source_info', {}).get('upload_date', datetime.now().strftime('%Y-%m-%d'))
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
    
    def _extract_channel_metrics(self, video_url: str) -> ChannelMetrics:
        """비디오 URL에서 채널 메트릭스 추출 (임시 구현)"""
        # TODO: 실제 YouTube API 또는 웹 스크래핑으로 채널 정보 수집
        # 현재는 기본값으로 설정
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

    async def _step_finalization(self, audio_path: Path, video_path: Path):
        """6단계: 후처리 및 리소스 정리"""
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
            'errors_count': len([log for log in self.step_logs if log['status'] == 'error'])
        }


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