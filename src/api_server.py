"""
API 서버 - n8n 워크플로우와 연동
PRD v1.0 - REST API for automation pipeline
"""

import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import traceback

# FastAPI imports
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from pydantic import BaseModel
import secrets
import hashlib

# 프로젝트 imports
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.youtube_api import create_youtube_manager, create_youtube_downloader
from src.ai_analysis import create_ai_pipeline
from src.slack_integration import create_slack_notifier, NotificationType
from dashboard.utils.database_manager import get_database_manager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="연예인 추천 아이템 자동화 API",
    description="PRD v1.0 - n8n 워크플로우 연동 API 서버",
    version="1.0.0"
)

# CORS 설정 - 보안 강화
allowed_origins = [
    "http://localhost:8501",  # Streamlit 대시보드
    "http://localhost:5678",  # n8n 기본 포트
    "http://localhost:5002",  # API 서버 자체
    "http://127.0.0.1:8501",
    "http://127.0.0.1:5678",
    "http://127.0.0.1:5002"
]

# 환경변수로 추가 허용 도메인 설정 가능
if os.getenv('ALLOWED_ORIGINS'):
    additional_origins = os.getenv('ALLOWED_ORIGINS').split(',')
    allowed_origins.extend([origin.strip() for origin in additional_origins])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 전역 변수
youtube_manager = None
youtube_downloader = None
ai_pipeline = None
db_manager = None
slack_notifier = None

# 보안 설정
API_KEY = os.getenv('API_SECRET_KEY', 'default-dev-key-change-in-production')
security = HTTPBearer()

# 허용된 API 키들 (환경변수에서 읽기)
VALID_API_KEYS = set()
if os.getenv('VALID_API_KEYS'):
    VALID_API_KEYS = set(os.getenv('VALID_API_KEYS').split(','))
elif API_KEY != 'default-dev-key-change-in-production':
    VALID_API_KEYS.add(API_KEY)

# 개발 모드 체크
DEV_MODE = os.getenv('ENVIRONMENT', 'development') == 'development'

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """API 키 검증"""
    if DEV_MODE and not VALID_API_KEYS:
        # 개발 모드에서 API 키가 설정되지 않은 경우 경고 후 통과
        logger.warning("개발 모드: API 키 검증을 건너뜁니다.")
        return True
    
    token = credentials.credentials
    
    # API 키 해시 검증
    if not VALID_API_KEYS:
        raise HTTPException(status_code=500, detail="서버 보안 설정이 완료되지 않았습니다.")
    
    # 단순 토큰 매칭 또는 해시 검증
    if token in VALID_API_KEYS:
        return True
    
    # 해시된 키 검증
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if token_hash in VALID_API_KEYS:
        return True
    
    raise HTTPException(
        status_code=401,
        detail="유효하지 않은 API 키입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

def optional_auth(authorization: str = Header(None)):
    """선택적 인증 (읽기 전용 엔드포인트용)"""
    if DEV_MODE:
        return True
    
    if not authorization:
        return False
    
    try:
        token = authorization.replace("Bearer ", "")
        return token in VALID_API_KEYS
    except:
        return False

# Pydantic 모델들
class ChannelInfo(BaseModel):
    channel_id: str
    channel_name: str
    channel_type: str = "individual"
    celebrity_name: str = ""
    rss_url: str = ""

class RSSCollectionRequest(BaseModel):
    channels: List[ChannelInfo]
    session_id: str
    exclude_shorts: bool = True
    days_back: int = 1

class VideoAnalysisRequest(BaseModel):
    videos: List[Dict[str, Any]]
    session_id: str
    analysis_type: str = "full_pipeline"
    prd_compliant: bool = True

class BatchAnalysisRequest(BaseModel):
    video_urls: List[str]
    session_id: str = None

class SlackNotificationRequest(BaseModel):
    notification_type: str
    data: Dict[str, Any]
    fallback_text: str = None

@app.on_event("startup")
async def startup_event():
    """서버 시작시 초기화"""
    global youtube_manager, youtube_downloader, ai_pipeline, db_manager, slack_notifier
    
    try:
        logger.info("API 서버 초기화 중...")
        
        # 각 컴포넌트 초기화
        youtube_manager = create_youtube_manager()
        youtube_downloader = create_youtube_downloader()
        ai_pipeline = create_ai_pipeline()
        db_manager = get_database_manager()
        slack_notifier = create_slack_notifier()
        
        logger.info("API 서버 초기화 완료")
        
    except Exception as e:
        logger.error(f"서버 초기화 실패: {e}")
        raise

@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "message": "연예인 추천 아이템 자동화 API v1.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "youtube_api": youtube_manager is not None,
            "ai_pipeline": ai_pipeline is not None,
            "database": db_manager is not None,
            "slack_notifier": slack_notifier is not None
        }
    }

@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # YouTube API 상태
    try:
        if youtube_manager and youtube_manager.youtube:
            # 간단한 테스트 요청
            test_result = youtube_manager.get_channel_info("UCE_M8A5yxnLfW0KghEeajjw")  # Apple Music
            health_status["components"]["youtube_api"] = {
                "status": "healthy" if test_result else "degraded",
                "last_check": datetime.now().isoformat()
            }
        else:
            health_status["components"]["youtube_api"] = {
                "status": "unhealthy",
                "error": "YouTube API not initialized"
            }
    except Exception as e:
        health_status["components"]["youtube_api"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # AI 파이프라인 상태
    try:
        if ai_pipeline and ai_pipeline.transcriber.model and ai_pipeline.analyzer.model:
            health_status["components"]["ai_pipeline"] = {
                "status": "healthy",
                "whisper_model": ai_pipeline.transcriber.model_size,
                "gemini_model": "gemini-2.5-flash"
            }
        else:
            health_status["components"]["ai_pipeline"] = {
                "status": "unhealthy",
                "error": "AI models not initialized"
            }
    except Exception as e:
        health_status["components"]["ai_pipeline"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # 데이터베이스 상태
    try:
        if db_manager:
            stats = db_manager.get_status_statistics()
            health_status["components"]["database"] = {
                "status": "healthy",
                "total_candidates": stats.get("total_candidates", 0),
                "last_check": datetime.now().isoformat()
            }
        else:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": "Database not initialized"
            }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # 전체 상태 결정
    unhealthy_components = [
        name for name, comp in health_status["components"].items()
        if comp.get("status") != "healthy"
    ]
    
    if unhealthy_components:
        health_status["status"] = "unhealthy"
        health_status["unhealthy_components"] = unhealthy_components
    
    return health_status

@app.post("/collect-rss")
async def collect_rss_feeds(
    request: RSSCollectionRequest,
    background_tasks: BackgroundTasks
):
    """RSS 피드 수집 엔드포인트 (n8n 연동)"""
    try:
        logger.info(f"RSS 수집 시작: 세션 {request.session_id}, {len(request.channels)}개 채널")
        
        if not youtube_manager:
            raise HTTPException(status_code=503, detail="YouTube API가 초기화되지 않았습니다")
        
        # 백그라운드에서 RSS 수집 실행
        background_tasks.add_task(
            process_rss_collection,
            request.channels,
            request.session_id,
            request.exclude_shorts,
            request.days_back
        )
        
        return {
            "status": "processing",
            "session_id": request.session_id,
            "channels_count": len(request.channels),
            "message": "RSS 피드 수집이 시작되었습니다"
        }
        
    except Exception as e:
        logger.error(f"RSS 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RSS 수집 실패: {str(e)}")

async def process_rss_collection(
    channels: List[ChannelInfo],
    session_id: str,
    exclude_shorts: bool,
    days_back: int
):
    """RSS 피드 수집 백그라운드 처리"""
    try:
        # 수집 기간 설정
        published_after = datetime.now() - timedelta(days=days_back)
        
        new_videos = []
        
        for channel in channels:
            try:
                logger.info(f"채널 처리 중: {channel.channel_name}")
                
                # 채널 영상 수집
                videos = youtube_manager.get_channel_videos(
                    channel.channel_id,
                    max_results=10,  # 최근 10개
                    published_after=published_after
                )
                
                # 새로운 영상만 필터링 (이미 DB에 있는지 확인)
                for video in videos:
                    existing = db_manager.get_candidate(video['video_id'])
                    if not existing:
                        video['celebrity_name'] = channel.celebrity_name
                        video['channel_type'] = channel.channel_type
                        new_videos.append(video)
                
            except Exception as e:
                logger.error(f"채널 {channel.channel_name} 처리 실패: {e}")
                continue
        
        logger.info(f"RSS 수집 완료: {len(new_videos)}개 신규 영상")
        
        # 결과를 임시 저장 (추후 n8n에서 조회)
        result = {
            "session_id": session_id,
            "new_videos": new_videos,
            "total_videos": len(new_videos),
            "processed_channels": len(channels),
            "completed_at": datetime.now().isoformat()
        }
        
        # TODO: 결과를 Redis나 임시 저장소에 저장하여 n8n에서 조회 가능하도록 구현
        
    except Exception as e:
        logger.error(f"RSS 수집 백그라운드 처리 실패: {e}")

@app.post("/analyze/batch")
async def analyze_videos_batch(
    request: VideoAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """비디오 배치 분석 엔드포인트 (n8n 연동)"""
    try:
        logger.info(f"배치 분석 시작: 세션 {request.session_id}, {len(request.videos)}개 영상")
        
        if not ai_pipeline:
            raise HTTPException(status_code=503, detail="AI 파이프라인이 초기화되지 않았습니다")
        
        # 백그라운드에서 분석 실행
        background_tasks.add_task(
            process_batch_analysis,
            request.videos,
            request.session_id,
            request.analysis_type,
            request.prd_compliant
        )
        
        return {
            "status": "processing",
            "session_id": request.session_id,
            "videos_count": len(request.videos),
            "estimated_time_minutes": len(request.videos) * 3,  # 영상당 약 3분 예상
            "message": "AI 2-Pass 분석이 시작되었습니다"
        }
        
    except Exception as e:
        logger.error(f"배치 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 분석 실패: {str(e)}")

async def process_batch_analysis(
    videos: List[Dict[str, Any]],
    session_id: str,
    analysis_type: str,
    prd_compliant: bool
):
    """배치 분석 백그라운드 처리"""
    try:
        analysis_results = {
            "session_id": session_id,
            "total_videos": len(videos),
            "processed_videos": 0,
            "total_products": 0,
            "monetizable_products": 0,
            "ppl_filtered": 0,
            "candidates": [],
            "errors": [],
            "started_at": datetime.now().isoformat()
        }
        
        for video in videos:
            try:
                logger.info(f"영상 분석 중: {video.get('title', 'Unknown')}")
                
                # 1. 영상 오디오 다운로드
                audio_result = youtube_downloader.download_audio(video['url'])
                if not audio_result or not audio_result.get('audio_file'):
                    logger.error(f"오디오 다운로드 실패: {video['url']}")
                    continue
                
                # 2. AI 2-Pass 분석 실행
                candidates = ai_pipeline.analyze_video(video, audio_result['audio_file'])
                
                analysis_results["processed_videos"] += 1
                analysis_results["total_products"] += len(candidates)
                
                for candidate in candidates:
                    analysis_results["candidates"].append(candidate)
                    
                    # 수익화 가능한 후보 카운트
                    if candidate["status_info"]["current_status"] != "filtered_no_coupang":
                        analysis_results["monetizable_products"] += 1
                    
                    # PPL 필터링된 후보 카운트
                    if candidate["status_info"]["is_ppl"]:
                        analysis_results["ppl_filtered"] += 1
                
                logger.info(f"영상 분석 완료: {len(candidates)}개 후보 생성")
                
            except Exception as e:
                error_info = {
                    "video_url": video.get('url', 'Unknown'),
                    "video_title": video.get('title', 'Unknown'),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                analysis_results["errors"].append(error_info)
                logger.error(f"영상 분석 실패: {e}")
                continue
        
        # 분석 완료
        analysis_results["completed_at"] = datetime.now().isoformat()
        analysis_results["average_score"] = 0
        
        if analysis_results["candidates"]:
            scores = [
                c["candidate_info"]["score_details"]["total"]
                for c in analysis_results["candidates"]
            ]
            analysis_results["average_score"] = round(sum(scores) / len(scores), 1)
        
        logger.info(f"배치 분석 완료: {analysis_results['total_products']}개 제품, {analysis_results['monetizable_products']}개 수익화 가능")
        
        # TODO: 결과를 저장하여 n8n에서 조회 가능하도록 구현
        
    except Exception as e:
        logger.error(f"배치 분석 백그라운드 처리 실패: {e}")

@app.post("/analyze/single")
async def analyze_single_video(request: BatchAnalysisRequest):
    """단일 영상 분석"""
    try:
        if not request.video_urls:
            raise HTTPException(status_code=400, detail="영상 URL이 필요합니다")
        
        video_url = request.video_urls[0]
        logger.info(f"단일 영상 분석: {video_url}")
        
        # 영상 정보 가져오기
        video_id = youtube_manager.extract_video_id(video_url)
        if not video_id:
            raise HTTPException(status_code=400, detail="올바르지 않은 YouTube URL입니다")
        
        video_metadata = youtube_manager.get_video_info(video_id)
        if not video_metadata:
            raise HTTPException(status_code=404, detail="영상을 찾을 수 없습니다")
        
        # 오디오 다운로드
        audio_result = youtube_downloader.download_audio(video_url)
        if not audio_result or not audio_result.get('audio_file'):
            raise HTTPException(status_code=500, detail="오디오 다운로드에 실패했습니다")
        
        # AI 분석 실행
        candidates = ai_pipeline.analyze_video(video_metadata, audio_result['audio_file'])
        
        return {
            "video_info": video_metadata,
            "candidates": candidates,
            "analysis_summary": {
                "total_candidates": len(candidates),
                "monetizable_candidates": len([
                    c for c in candidates 
                    if c["status_info"]["current_status"] != "filtered_no_coupang"
                ]),
                "ppl_filtered": len([
                    c for c in candidates 
                    if c["status_info"]["is_ppl"]
                ])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"단일 영상 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")

@app.get("/candidates")
async def get_candidates(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """후보 목록 조회"""
    try:
        if not db_manager:
            raise HTTPException(status_code=503, detail="데이터베이스가 초기화되지 않았습니다")
        
        candidates = db_manager.get_candidates_by_status(
            status=status,
            limit=limit,
            offset=offset
        )
        
        return {
            "candidates": candidates,
            "count": len(candidates),
            "status_filter": status,
            "pagination": {
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        logger.error(f"후보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"후보 조회 실패: {str(e)}")

@app.get("/statistics")
async def get_statistics():
    """시스템 통계 조회"""
    try:
        if not db_manager:
            raise HTTPException(status_code=503, detail="데이터베이스가 초기화되지 않았습니다")
        
        stats = db_manager.get_status_statistics()
        db_stats = db_manager.get_database_stats()
        
        return {
            "candidate_statistics": stats,
            "database_statistics": db_stats,
            "system_info": {
                "api_version": "1.0.0",
                "uptime": "계산 필요",  # TODO: 실제 업타임 계산
                "last_updated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@app.post("/channels/discover")
async def discover_channels(
    query: str,
    max_results: int = 20,
    celebrity_keywords: List[str] = None
):
    """신규 채널 탐색"""
    try:
        if not youtube_manager:
            raise HTTPException(status_code=503, detail="YouTube API가 초기화되지 않았습니다")
        
        channels = youtube_manager.search_channels(
            query=query,
            max_results=max_results,
            celebrity_keywords=celebrity_keywords or []
        )
        
        return {
            "query": query,
            "channels": channels,
            "count": len(channels)
        }
        
    except Exception as e:
        logger.error(f"채널 탐색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"채널 탐색 실패: {str(e)}")

@app.post("/notifications/slack")
async def send_slack_notification(request: SlackNotificationRequest):
    """Slack 알림 발송"""
    try:
        if not slack_notifier:
            raise HTTPException(status_code=503, detail="Slack 알림 서비스가 초기화되지 않았습니다")
        
        # 알림 유형 변환
        try:
            notification_type = NotificationType(request.notification_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 알림 유형: {request.notification_type}")
        
        # 알림 발송
        success = slack_notifier.send_notification(
            notification_type,
            request.data,
            request.fallback_text
        )
        
        if success:
            return {
                "status": "success",
                "message": "Slack 알림이 성공적으로 발송되었습니다",
                "notification_type": request.notification_type
            }
        else:
            raise HTTPException(status_code=500, detail="Slack 알림 발송에 실패했습니다")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slack 알림 발송 실패: {e}")
        raise HTTPException(status_code=500, detail=f"알림 발송 실패: {str(e)}")

@app.post("/notifications/pipeline-start")
async def notify_pipeline_start(session_id: str, channels_count: int):
    """파이프라인 시작 알림"""
    try:
        if not slack_notifier:
            raise HTTPException(status_code=503, detail="Slack 알림 서비스가 초기화되지 않았습니다")
        
        success = slack_notifier.send_notification(
            NotificationType.PIPELINE_START,
            {
                'session_id': session_id,
                'channels_count': channels_count
            }
        )
        
        return {"status": "success" if success else "failed"}
        
    except Exception as e:
        logger.error(f"파이프라인 시작 알림 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/notifications/pipeline-success")
async def notify_pipeline_success(
    session_id: str,
    statistics: Dict[str, Any],
    execution_time: float,
    channels_count: int
):
    """파이프라인 성공 알림"""
    try:
        if not slack_notifier:
            raise HTTPException(status_code=503, detail="Slack 알림 서비스가 초기화되지 않았습니다")
        
        success = slack_notifier.send_notification(
            NotificationType.PIPELINE_SUCCESS,
            {
                'session_id': session_id,
                'statistics': statistics,
                'execution_time': execution_time,
                'channels_count': channels_count
            }
        )
        
        return {"status": "success" if success else "failed"}
        
    except Exception as e:
        logger.error(f"파이프라인 성공 알림 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/notifications/pipeline-error")
async def notify_pipeline_error(
    session_id: str,
    error_message: str,
    error_step: str
):
    """파이프라인 오류 알림"""
    try:
        if not slack_notifier:
            raise HTTPException(status_code=503, detail="Slack 알림 서비스가 초기화되지 않았습니다")
        
        success = slack_notifier.send_notification(
            NotificationType.PIPELINE_ERROR,
            {
                'session_id': session_id,
                'error_message': error_message,
                'error_step': error_step,
                'error_time': datetime.now().isoformat()
            }
        )
        
        return {"status": "success" if success else "failed"}
        
    except Exception as e:
        logger.error(f"파이프라인 오류 알림 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/notifications/no-videos")
async def notify_no_videos(session_id: str, channels_count: int):
    """신규 영상 없음 알림"""
    try:
        if not slack_notifier:
            raise HTTPException(status_code=503, detail="Slack 알림 서비스가 초기화되지 않았습니다")
        
        success = slack_notifier.send_notification(
            NotificationType.NO_NEW_VIDEOS,
            {
                'session_id': session_id,
                'channels_count': channels_count
            }
        )
        
        return {"status": "success" if success else "failed"}
        
    except Exception as e:
        logger.error(f"신규 영상 없음 알림 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """글로벌 예외 처리"""
    logger.error(f"예상치 못한 오류: {exc}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "내부 서버 오류가 발생했습니다",
            "detail": str(exc) if os.getenv("DEBUG") else "서버 관리자에게 문의하세요",
            "timestamp": datetime.now().isoformat()
        }
    )

# 개발용 실행
if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )