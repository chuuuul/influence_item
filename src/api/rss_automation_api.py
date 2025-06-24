"""
RSS 자동화 시스템 API 엔드포인트

n8n 워크플로우와의 연동을 위한 REST API
PRD 2.2 요구사항에 따른 자동화 시스템의 HTTP API 인터페이스 제공
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import logging
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.rss_automation.rss_collector import RSSCollector, ChannelInfo, CollectionResult
from src.rss_automation.historical_scraper import HistoricalScraper, ScrapingConfig, ScrapingResult
from src.rss_automation.content_filter import ContentFilter, FilterResult
from src.rss_automation.sheets_integration import SheetsIntegration, SheetsConfig, ChannelCandidate

# 분석 파이프라인 관련 import 추가
# from src.workflow.workflow_manager import WorkflowManager
# from src.api.analysis_api import AnalysisAPI
import uuid
import json


# Pydantic 모델 정의
class ChannelInfoModel(BaseModel):
    channel_id: str = Field(..., description="YouTube 채널 ID")
    channel_name: str = Field(..., description="채널명")
    channel_type: str = Field(..., description="채널 유형 (personal/media)")
    rss_url: str = Field(..., description="RSS 피드 URL")
    is_active: bool = Field(True, description="활성 상태")


class CollectionRequest(BaseModel):
    force_update: bool = Field(False, description="강제 업데이트 여부")
    channel_ids: Optional[List[str]] = Field(None, description="특정 채널만 수집 (선택사항)")


class ScrapingRequest(BaseModel):
    channel_id: str = Field(..., description="채널 ID")
    channel_name: str = Field(..., description="채널명")
    start_date: datetime = Field(..., description="시작 날짜")
    end_date: datetime = Field(..., description="종료 날짜")
    config: Optional[Dict[str, Any]] = Field(None, description="스크래핑 설정")


class FilterTestRequest(BaseModel):
    title: str = Field(..., description="비디오 제목")
    description: str = Field("", description="비디오 설명")
    channel_type: str = Field("personal", description="채널 유형")


class ChannelCandidateModel(BaseModel):
    channel_id: str = Field(..., description="채널 ID")
    channel_name: str = Field(..., description="채널명")
    channel_type: str = Field(..., description="채널 유형")
    rss_url: str = Field(..., description="RSS URL")
    discovery_score: float = Field(..., description="발견 점수")
    discovery_reason: str = Field(..., description="발견 사유")


class SheetsConfigModel(BaseModel):
    spreadsheet_id: str = Field(..., description="Google Sheets ID")
    channels_sheet_name: str = Field("승인된 채널", description="승인된 채널 시트명")
    candidates_sheet_name: str = Field("후보 채널", description="후보 채널 시트명")


class AnalysisRequest(BaseModel):
    video_url: str = Field(..., description="YouTube 영상 URL")
    channel_name: str = Field(..., description="채널명")
    video_title: str = Field(..., description="영상 제목")
    publish_date: str = Field(..., description="업로드 날짜")
    priority: str = Field("normal", description="처리 우선순위")


class DailyStatsRequest(BaseModel):
    start_date: str = Field(..., description="시작 날짜 (YYYY-MM-DD)")
    end_date: str = Field(..., description="종료 날짜 (YYYY-MM-DD)")


class WebhookNotification(BaseModel):
    job_id: str = Field(..., description="작업 ID")
    video_title: str = Field(..., description="영상 제목")
    channel_name: str = Field(..., description="채널명")
    video_url: str = Field(..., description="영상 URL")
    status: str = Field(..., description="분석 상태")
    candidates_found: int = Field(0, description="발견된 후보 수")
    approved_candidates: int = Field(0, description="승인된 후보 수")
    rejected_candidates: int = Field(0, description="거절된 후보 수")
    avg_score: float = Field(0.0, description="평균 점수")
    top_product: Optional[Dict[str, Any]] = Field(None, description="최고 점수 제품")
    processing_time_seconds: float = Field(0.0, description="처리 시간(초)")
    error_message: Optional[str] = Field(None, description="에러 메시지")


class APIResponse(BaseModel):
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    data: Optional[Dict[str, Any]] = Field(None, description="응답 데이터")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")


# FastAPI 앱 초기화
app = FastAPI(
    title="RSS 자동화 시스템 API",
    description="PRD 2.2 요구사항에 따른 RSS 피드 자동화 시스템 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영환경에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 인스턴스
rss_collector = None
historical_scraper = None
content_filter = None
sheets_integration = None
workflow_manager = None
analysis_api = None

# 작업 상태 저장소 (실제 운영시에는 Redis 등 사용)
analysis_jobs = {}
webhook_callbacks = {}


def get_rss_collector() -> RSSCollector:
    """RSS 수집기 인스턴스 반환"""
    global rss_collector
    if rss_collector is None:
        rss_collector = RSSCollector()
    return rss_collector


def get_historical_scraper() -> HistoricalScraper:
    """과거 영상 수집기 인스턴스 반환"""
    global historical_scraper
    if historical_scraper is None:
        historical_scraper = HistoricalScraper()
    return historical_scraper


def get_content_filter() -> ContentFilter:
    """컨텐츠 필터 인스턴스 반환"""
    global content_filter
    if content_filter is None:
        content_filter = ContentFilter()
    return content_filter


def get_sheets_integration(config: Optional[SheetsConfigModel] = None) -> SheetsIntegration:
    """Google Sheets 연동 인스턴스 반환"""
    global sheets_integration
    if sheets_integration is None and config:
        sheets_config = SheetsConfig(
            spreadsheet_id=config.spreadsheet_id,
            channels_sheet_name=config.channels_sheet_name,
            candidates_sheet_name=config.candidates_sheet_name
        )
        sheets_integration = SheetsIntegration(sheets_config)
    return sheets_integration


def get_workflow_manager():
    """워크플로우 매니저 인스턴스 반환 (임시 구현)"""
    global workflow_manager
    if workflow_manager is None:
        # 임시로 None 반환
        workflow_manager = None
    return workflow_manager


def get_analysis_api():
    """분석 API 인스턴스 반환 (임시 구현)"""
    global analysis_api
    if analysis_api is None:
        # 임시로 None 반환
        analysis_api = None
    return analysis_api


def verify_api_key(x_api_key: str = Header(...)):
    """API 키 검증"""
    expected_api_key = os.getenv("RSS_API_KEY", "default-api-key")
    if x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# RSS 수집 엔드포인트
@app.post("/api/v1/rss/collect", response_model=APIResponse)
async def collect_rss_feeds(
    request: CollectionRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """RSS 피드 자동 수집 실행"""
    try:
        collector = get_rss_collector()
        
        # 백그라운드에서 수집 실행
        result = await collector.collect_daily_videos()
        
        if result.success:
            return APIResponse(
                success=True,
                message="RSS 수집이 성공적으로 완료되었습니다.",
                data={
                    "collected_count": result.collected_count,
                    "filtered_count": result.filtered_count,
                    "error_count": result.error_count,
                    "execution_time": result.execution_time
                }
            )
        else:
            return APIResponse(
                success=False,
                message="RSS 수집 중 오류가 발생했습니다.",
                data={
                    "errors": result.errors,
                    "execution_time": result.execution_time
                }
            )
    
    except Exception as e:
        logger.error(f"RSS 수집 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RSS 수집 실행 실패: {str(e)}")


@app.get("/api/v1/rss/channels", response_model=APIResponse)
async def get_rss_channels(api_key: str = Depends(verify_api_key)):
    """RSS 채널 목록 조회"""
    try:
        collector = get_rss_collector()
        channels = collector.get_active_channels()
        
        channels_data = [
            {
                "channel_id": ch.channel_id,
                "channel_name": ch.channel_name,
                "channel_type": ch.channel_type,
                "rss_url": ch.rss_url,
                "is_active": ch.is_active
            }
            for ch in channels
        ]
        
        return APIResponse(
            success=True,
            message=f"{len(channels)}개의 활성 채널을 조회했습니다.",
            data={"channels": channels_data}
        )
    
    except Exception as e:
        logger.error(f"RSS 채널 조회 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채널 조회 실패: {str(e)}")


@app.post("/api/v1/rss/channels", response_model=APIResponse)
async def add_rss_channel(
    channel: ChannelInfoModel,
    api_key: str = Depends(verify_api_key)
):
    """RSS 채널 추가"""
    try:
        collector = get_rss_collector()
        
        channel_info = ChannelInfo(
            channel_id=channel.channel_id,
            channel_name=channel.channel_name,
            channel_type=channel.channel_type,
            rss_url=channel.rss_url,
            is_active=channel.is_active
        )
        
        if collector.add_channel(channel_info):
            return APIResponse(
                success=True,
                message=f"채널 '{channel.channel_name}'이 성공적으로 추가되었습니다.",
                data={"channel_id": channel.channel_id}
            )
        else:
            return APIResponse(
                success=False,
                message="채널 추가에 실패했습니다."
            )
    
    except Exception as e:
        logger.error(f"RSS 채널 추가 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채널 추가 실패: {str(e)}")


@app.get("/api/v1/rss/statistics", response_model=APIResponse)
async def get_rss_statistics(
    days: int = 7,
    api_key: str = Depends(verify_api_key)
):
    """RSS 수집 통계 조회"""
    try:
        collector = get_rss_collector()
        stats = collector.get_collection_statistics(days=days)
        
        return APIResponse(
            success=True,
            message=f"최근 {days}일간의 RSS 수집 통계를 조회했습니다.",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"RSS 통계 조회 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


# 과거 영상 스크래핑 엔드포인트
@app.post("/api/v1/scraping/start", response_model=APIResponse)
async def start_historical_scraping(
    request: ScrapingRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """과거 영상 스크래핑 시작"""
    try:
        scraper = get_historical_scraper()
        
        # 설정 적용
        config = ScrapingConfig()
        if request.config:
            for key, value in request.config.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # 백그라운드에서 스크래핑 실행
        result = await scraper.scrape_channel_videos(
            request.channel_id,
            request.channel_name,
            request.start_date,
            request.end_date
        )
        
        if result.success:
            return APIResponse(
                success=True,
                message="과거 영상 스크래핑이 성공적으로 완료되었습니다.",
                data={
                    "total_found": result.total_found,
                    "collected_count": result.collected_count,
                    "filtered_count": result.filtered_count,
                    "error_count": result.error_count,
                    "execution_time": result.execution_time
                }
            )
        else:
            return APIResponse(
                success=False,
                message="과거 영상 스크래핑 중 오류가 발생했습니다.",
                data={
                    "errors": result.errors,
                    "execution_time": result.execution_time
                }
            )
    
    except Exception as e:
        logger.error(f"과거 영상 스크래핑 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스크래핑 실행 실패: {str(e)}")


@app.get("/api/v1/scraping/jobs", response_model=APIResponse)
async def get_scraping_jobs(
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
):
    """스크래핑 작업 목록 조회"""
    try:
        scraper = get_historical_scraper()
        jobs = scraper.get_scraping_jobs(limit=limit)
        
        return APIResponse(
            success=True,
            message=f"{len(jobs)}개의 스크래핑 작업을 조회했습니다.",
            data={"jobs": jobs}
        )
    
    except Exception as e:
        logger.error(f"스크래핑 작업 조회 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 조회 실패: {str(e)}")


@app.get("/api/v1/scraping/jobs/{job_id}/videos", response_model=APIResponse)
async def get_scraped_videos(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """스크래핑된 비디오 목록 조회"""
    try:
        scraper = get_historical_scraper()
        videos = scraper.get_scraped_videos(job_id)
        
        return APIResponse(
            success=True,
            message=f"작업 {job_id}의 {len(videos)}개 비디오를 조회했습니다.",
            data={"videos": videos}
        )
    
    except Exception as e:
        logger.error(f"스크래핑된 비디오 조회 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"비디오 조회 실패: {str(e)}")


# 컨텐츠 필터링 엔드포인트
@app.post("/api/v1/filter/test", response_model=APIResponse)
async def test_content_filter(
    request: FilterTestRequest,
    api_key: str = Depends(verify_api_key)
):
    """컨텐츠 필터링 테스트"""
    try:
        filter_system = get_content_filter()
        
        result = filter_system.comprehensive_filter(
            request.title,
            request.description,
            request.channel_type
        )
        
        return APIResponse(
            success=True,
            message="필터링 테스트가 완료되었습니다.",
            data={
                "passed": result.passed,
                "reason": result.reason,
                "confidence": result.confidence,
                "matched_names": result.matched_names
            }
        )
    
    except Exception as e:
        logger.error(f"필터링 테스트 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"필터링 테스트 실패: {str(e)}")


@app.get("/api/v1/filter/statistics", response_model=APIResponse)
async def get_filter_statistics(
    days: int = 7,
    api_key: str = Depends(verify_api_key)
):
    """필터링 통계 조회"""
    try:
        filter_system = get_content_filter()
        stats = filter_system.get_filter_statistics(days=days)
        
        return APIResponse(
            success=True,
            message=f"최근 {days}일간의 필터링 통계를 조회했습니다.",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"필터링 통계 조회 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


# Google Sheets 연동 엔드포인트
@app.post("/api/v1/sheets/sync/channels", response_model=APIResponse)
async def sync_channels_to_sheets(
    config: SheetsConfigModel,
    api_key: str = Depends(verify_api_key)
):
    """승인된 채널을 Google Sheets로 동기화"""
    try:
        sheets = get_sheets_integration(config)
        if not sheets:
            raise HTTPException(status_code=400, detail="Google Sheets 설정이 필요합니다")
        
        if sheets.sync_approved_channels_to_sheets():
            return APIResponse(
                success=True,
                message="승인된 채널이 Google Sheets로 동기화되었습니다."
            )
        else:
            return APIResponse(
                success=False,
                message="채널 동기화에 실패했습니다."
            )
    
    except Exception as e:
        logger.error(f"채널 Sheets 동기화 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


@app.post("/api/v1/sheets/sync/candidates", response_model=APIResponse)
async def sync_candidates_to_sheets(
    config: SheetsConfigModel,
    api_key: str = Depends(verify_api_key)
):
    """후보 채널을 Google Sheets로 동기화"""
    try:
        sheets = get_sheets_integration(config)
        if not sheets:
            raise HTTPException(status_code=400, detail="Google Sheets 설정이 필요합니다")
        
        if sheets.sync_channel_candidates_to_sheets():
            return APIResponse(
                success=True,
                message="후보 채널이 Google Sheets로 동기화되었습니다."
            )
        else:
            return APIResponse(
                success=False,
                message="후보 채널 동기화에 실패했습니다."
            )
    
    except Exception as e:
        logger.error(f"후보 채널 Sheets 동기화 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


@app.post("/api/v1/sheets/sync/reviews", response_model=APIResponse)
async def sync_reviews_from_sheets(
    config: SheetsConfigModel,
    api_key: str = Depends(verify_api_key)
):
    """Google Sheets에서 검토 결과 동기화"""
    try:
        sheets = get_sheets_integration(config)
        if not sheets:
            raise HTTPException(status_code=400, detail="Google Sheets 설정이 필요합니다")
        
        if sheets.sync_reviews_from_sheets():
            return APIResponse(
                success=True,
                message="검토 결과가 Google Sheets에서 동기화되었습니다."
            )
        else:
            return APIResponse(
                success=False,
                message="검토 결과 동기화에 실패했습니다."
            )
    
    except Exception as e:
        logger.error(f"검토 결과 Sheets 동기화 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


@app.post("/api/v1/sheets/sync/full", response_model=APIResponse)
async def full_sheets_sync(
    config: SheetsConfigModel,
    api_key: str = Depends(verify_api_key)
):
    """Google Sheets 전체 동기화"""
    try:
        sheets = get_sheets_integration(config)
        if not sheets:
            raise HTTPException(status_code=400, detail="Google Sheets 설정이 필요합니다")
        
        results = sheets.full_sync()
        success_count = sum(results.values())
        
        return APIResponse(
            success=success_count > 0,
            message=f"전체 동기화 완료: {success_count}/3개 성공",
            data={
                "results": results,
                "success_count": success_count,
                "total_count": 3
            }
        )
    
    except Exception as e:
        logger.error(f"전체 Sheets 동기화 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"전체 동기화 실패: {str(e)}")


@app.post("/api/v1/sheets/candidates", response_model=APIResponse)
async def add_channel_candidate(
    candidate: ChannelCandidateModel,
    config: SheetsConfigModel,
    api_key: str = Depends(verify_api_key)
):
    """채널 후보 추가"""
    try:
        sheets = get_sheets_integration(config)
        if not sheets:
            raise HTTPException(status_code=400, detail="Google Sheets 설정이 필요합니다")
        
        candidate_obj = ChannelCandidate(
            channel_id=candidate.channel_id,
            channel_name=candidate.channel_name,
            channel_type=candidate.channel_type,
            rss_url=candidate.rss_url,
            discovery_score=candidate.discovery_score,
            discovery_reason=candidate.discovery_reason,
            discovered_at=datetime.now()
        )
        
        if sheets.add_channel_candidate(candidate_obj):
            return APIResponse(
                success=True,
                message=f"채널 후보 '{candidate.channel_name}'이 추가되었습니다.",
                data={"channel_id": candidate.channel_id}
            )
        else:
            return APIResponse(
                success=False,
                message="채널 후보 추가에 실패했습니다."
            )
    
    except Exception as e:
        logger.error(f"채널 후보 추가 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"후보 추가 실패: {str(e)}")


# 헬스체크 엔드포인트
@app.get("/api/v1/health")
async def health_check():
    """API 헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


# 시스템 상태 조회
@app.get("/api/v1/status", response_model=APIResponse)
async def get_system_status(api_key: str = Depends(verify_api_key)):
    """시스템 전체 상태 조회"""
    try:
        collector = get_rss_collector()
        filter_system = get_content_filter()
        
        # 각 시스템 상태 조회
        rss_stats = collector.get_collection_statistics(days=1)
        filter_stats = filter_system.get_filter_statistics(days=1)
        
        return APIResponse(
            success=True,
            message="시스템 상태를 조회했습니다.",
            data={
                "rss_collection": {
                    "total_executions": rss_stats.get('total_executions', 0),
                    "successful_executions": rss_stats.get('successful_executions', 0),
                    "total_collected": rss_stats.get('total_collected', 0),
                    "total_errors": rss_stats.get('total_errors', 0)
                },
                "content_filtering": {
                    "total_filtered": filter_stats.get('total_filtered', 0),
                    "filter_breakdown": filter_stats.get('filter_breakdown', {})
                },
                "last_updated": datetime.now().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"시스템 상태 조회 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")


# n8n 워크플로우 연동 엔드포인트
@app.post("/api/v1/analyze", response_model=APIResponse)
async def trigger_video_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """n8n에서 영상 분석 요청"""
    try:
        # 고유 작업 ID 생성
        job_id = str(uuid.uuid4())
        
        logger.info(f"분석 요청 받음: {job_id} - {request.video_title}")
        
        # 작업 상태 초기화
        analysis_jobs[job_id] = {
            "status": "queued",
            "video_url": request.video_url,
            "channel_name": request.channel_name,
            "video_title": request.video_title,
            "publish_date": request.publish_date,
            "priority": request.priority,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # 백그라운드에서 분석 실행
        background_tasks.add_task(
            process_video_analysis,
            job_id,
            request.video_url,
            request.channel_name,
            request.video_title,
            request.publish_date,
            request.priority
        )
        
        return APIResponse(
            success=True,
            message="영상 분석이 시작되었습니다.",
            data={
                "job_id": job_id,
                "video_title": request.video_title,
                "channel_name": request.channel_name,
                "estimated_completion": "10-15분"
            }
        )
    
    except Exception as e:
        logger.error(f"분석 요청 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"분석 요청 실패: {str(e)}")


@app.get("/api/v1/analyze/{job_id}/status", response_model=APIResponse)
async def get_analysis_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """분석 작업 상태 조회"""
    try:
        if job_id not in analysis_jobs:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        job_info = analysis_jobs[job_id]
        
        return APIResponse(
            success=True,
            message="작업 상태를 조회했습니다.",
            data=job_info
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 상태 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")


@app.get("/api/v1/stats/daily", response_model=APIResponse)
async def get_daily_statistics(
    start_date: str,
    end_date: str,
    api_key: str = Depends(verify_api_key)
):
    """일일 운영 통계 조회 (n8n 리포트용)"""
    try:
        logger.info(f"일일 통계 조회: {start_date} ~ {end_date}")
        
        # 분석 API를 통해 통계 수집
        analysis_api = get_analysis_api()
        
        # 실제 구현에서는 데이터베이스에서 통계를 조회
        # 여기서는 예시 데이터 반환
        stats = {
            "total_videos_analyzed": 45,
            "total_candidates_found": 127,
            "total_approved_candidates": 38,
            "total_rejected_candidates": 89,
            "active_channels": 23,
            "new_channels_added": 2,
            "avg_processing_time_seconds": 485.2,
            "avg_score_per_candidate": 67.8,
            "total_errors": 3,
            "critical_errors": 0,
            "monetizable_candidates": 32,
            "coupang_products_found": 28,
            "system_uptime_percentage": 99.2,
            "api_calls_count": 1247,
            "storage_used_gb": 12.4
        }
        
        return APIResponse(
            success=True,
            message=f"{start_date}부터 {end_date}까지의 통계를 조회했습니다.",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"일일 통계 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@app.post("/api/v1/webhook/analysis-complete")
async def analysis_complete_webhook(notification: WebhookNotification):
    """분석 완료 알림을 받는 웹훅 (내부 사용)"""
    try:
        job_id = notification.job_id
        
        logger.info(f"분석 완료 알림 받음: {job_id}")
        
        # 작업 상태 업데이트
        if job_id in analysis_jobs:
            analysis_jobs[job_id].update({
                "status": notification.status,
                "candidates_found": notification.candidates_found,
                "approved_candidates": notification.approved_candidates,
                "rejected_candidates": notification.rejected_candidates,
                "avg_score": notification.avg_score,
                "top_product": notification.top_product,
                "processing_time_seconds": notification.processing_time_seconds,
                "error_message": notification.error_message,
                "completed_at": datetime.now(),
                "updated_at": datetime.now()
            })
        
        # n8n 알림 워크플로우에 결과 전송
        await send_analysis_result_to_n8n(notification)
        
        return {"status": "success", "message": "알림 처리 완료"}
    
    except Exception as e:
        logger.error(f"분석 완료 웹훅 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"웹훅 처리 실패: {str(e)}")


async def process_video_analysis(
    job_id: str,
    video_url: str,
    channel_name: str,
    video_title: str,
    publish_date: str,
    priority: str
):
    """백그라운드에서 영상 분석 처리"""
    try:
        logger.info(f"영상 분석 시작: {job_id}")
        
        # 작업 상태 업데이트
        analysis_jobs[job_id]["status"] = "processing"
        analysis_jobs[job_id]["updated_at"] = datetime.now()
        
        # 워크플로우 매니저를 통해 분석 실행
        workflow_manager = get_workflow_manager()
        
        # 실제 분석 실행 (예시)
        start_time = datetime.now()
        
        # TODO: 실제 분석 로직 구현
        # result = await workflow_manager.process_video(video_url, channel_name, video_title)
        
        # 임시 결과 생성
        await asyncio.sleep(5)  # 분석 시뮬레이션
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # 결과 데이터 구성
        result_notification = WebhookNotification(
            job_id=job_id,
            video_title=video_title,
            channel_name=channel_name,
            video_url=video_url,
            status="completed",
            candidates_found=5,
            approved_candidates=3,
            rejected_candidates=2,
            avg_score=75.2,
            top_product={
                "name": "샘플 제품",
                "score": 88.5,
                "category": "뷰티"
            },
            processing_time_seconds=processing_time
        )
        
        # 분석 완료 알림 발송
        await analysis_complete_webhook(result_notification)
        
        logger.info(f"영상 분석 완료: {job_id}")
        
    except Exception as e:
        logger.error(f"영상 분석 처리 오류: {job_id} - {str(e)}")
        
        # 에러 상태 업데이트
        if job_id in analysis_jobs:
            analysis_jobs[job_id].update({
                "status": "failed",
                "error_message": str(e),
                "updated_at": datetime.now()
            })
        
        # 에러 알림 발송
        error_notification = WebhookNotification(
            job_id=job_id,
            video_title=video_title,
            channel_name=channel_name,
            video_url=video_url,
            status="failed",
            error_message=str(e),
            processing_time_seconds=0.0
        )
        
        try:
            await analysis_complete_webhook(error_notification)
        except Exception as webhook_error:
            logger.error(f"에러 알림 발송 실패: {str(webhook_error)}")


async def send_analysis_result_to_n8n(notification: WebhookNotification):
    """n8n 알림 워크플로우에 분석 결과 전송"""
    try:
        import aiohttp
        
        # n8n 웹훅 URL (환경변수에서 읽기)
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/analysis-complete")
        
        # 알림 데이터 구성
        webhook_data = {
            "job_id": notification.job_id,
            "video_title": notification.video_title,
            "channel_name": notification.channel_name,
            "video_url": notification.video_url,
            "status": notification.status,
            "candidates_found": notification.candidates_found,
            "approved_candidates": notification.approved_candidates,
            "rejected_candidates": notification.rejected_candidates,
            "avg_score": notification.avg_score,
            "top_product": notification.top_product,
            "processing_time_seconds": notification.processing_time_seconds,
            "error_message": notification.error_message,
            "timestamp": datetime.now().isoformat()
        }
        
        # n8n 웹훅으로 POST 요청
        async with aiohttp.ClientSession() as session:
            async with session.post(n8n_webhook_url, json=webhook_data) as response:
                if response.status == 200:
                    logger.info(f"n8n 알림 전송 성공: {notification.job_id}")
                else:
                    logger.error(f"n8n 알림 전송 실패: {response.status} - {await response.text()}")
                    
    except Exception as e:
        logger.error(f"n8n 알림 전송 오류: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    # 개발 환경에서 실행
    uvicorn.run(
        "rss_automation_api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )