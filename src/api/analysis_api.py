"""
n8n 워크플로우와 연동하기 위한 분석 API 엔드포인트
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, HttpUrl
import logging
from contextlib import asynccontextmanager

from ..workflow.workflow_manager import WorkflowManager
from ..schema.models import AnalysisRequest, AnalysisStatus
from config.config import Config

# Logging 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Key 보안
security = HTTPBearer()

class VideoAnalysisRequest(BaseModel):
    """영상 분석 요청 모델"""
    video_url: HttpUrl
    channel_name: str
    video_title: str
    publish_date: str
    priority: str = "normal"  # normal, high, urgent
    
class AnalysisStatusResponse(BaseModel):
    """분석 상태 응답 모델"""
    job_id: str
    status: str  # queued, processing, completed, failed
    progress: Optional[float] = None
    estimated_completion: Optional[str] = None
    result_preview: Optional[Dict[str, Any]] = None
    
class AnalysisResultResponse(BaseModel):
    """분석 결과 응답 모델"""
    job_id: str
    status: str
    candidates: list
    processing_time: float
    metadata: Dict[str, Any]

# 진행 중인 작업 추적
active_jobs: Dict[str, Dict[str, Any]] = {}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """API 키 검증"""
    expected_key = Config.ANALYSIS_API_KEY
    if not expected_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    if credentials.credentials != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return credentials.credentials

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 애플리케이션 생명주기 관리"""
    logger.info("분석 API 서버 시작")
    yield
    logger.info("분석 API 서버 종료")

# FastAPI 앱 생성
app = FastAPI(
    title="연예인 추천 아이템 분석 API",
    description="n8n 워크플로우와 연동하는 영상 분석 API",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_jobs": len(active_jobs)
    }

@app.post("/analyze", response_model=Dict[str, str])
async def start_analysis(
    request: VideoAnalysisRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    영상 분석을 시작합니다.
    
    Args:
        request: 분석 요청 데이터
        background_tasks: 백그라운드 작업 관리자
        api_key: 인증된 API 키
        
    Returns:
        job_id와 상태 정보
    """
    try:
        # 고유 작업 ID 생성
        job_id = str(uuid.uuid4())
        
        # 작업 초기 상태 설정
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "request": request.dict(),
            "created_at": datetime.now().isoformat(),
            "progress": 0.0,
            "estimated_completion": None
        }
        
        active_jobs[job_id] = job_data
        
        # 백그라운드에서 분석 실행
        background_tasks.add_task(process_video_analysis, job_id, request)
        
        logger.info(f"분석 작업 시작: {job_id} - {request.video_title}")
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "분석 작업이 큐에 추가되었습니다"
        }
        
    except Exception as e:
        logger.error(f"분석 시작 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"분석 시작 실패: {str(e)}")

@app.get("/status/{job_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    분석 작업의 현재 상태를 조회합니다.
    
    Args:
        job_id: 작업 ID
        api_key: 인증된 API 키
        
    Returns:
        분석 상태 정보
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job_data = active_jobs[job_id]
    
    return AnalysisStatusResponse(
        job_id=job_id,
        status=job_data["status"],
        progress=job_data.get("progress"),
        estimated_completion=job_data.get("estimated_completion"),
        result_preview=job_data.get("result_preview")
    )

@app.get("/result/{job_id}", response_model=AnalysisResultResponse)
async def get_analysis_result(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    완료된 분석 작업의 결과를 조회합니다.
    
    Args:
        job_id: 작업 ID
        api_key: 인증된 API 키
        
    Returns:
        분석 결과 데이터
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job_data = active_jobs[job_id]
    
    if job_data["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"작업이 아직 완료되지 않았습니다. 현재 상태: {job_data['status']}"
        )
    
    return AnalysisResultResponse(
        job_id=job_id,
        status=job_data["status"],
        candidates=job_data.get("candidates", []),
        processing_time=job_data.get("processing_time", 0),
        metadata=job_data.get("metadata", {})
    )

@app.delete("/job/{job_id}")
async def cancel_analysis_job(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    진행 중인 분석 작업을 취소합니다.
    
    Args:
        job_id: 취소할 작업 ID
        api_key: 인증된 API 키
        
    Returns:
        취소 확인 메시지
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job_data = active_jobs[job_id]
    
    if job_data["status"] in ["completed", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"완료된 작업은 취소할 수 없습니다. 현재 상태: {job_data['status']}"
        )
    
    # 작업 상태를 cancelled로 변경
    active_jobs[job_id]["status"] = "cancelled"
    active_jobs[job_id]["cancelled_at"] = datetime.now().isoformat()
    
    logger.info(f"분석 작업 취소: {job_id}")
    
    return {"message": f"작업 {job_id}가 취소되었습니다"}

@app.get("/jobs")
async def list_active_jobs(api_key: str = Depends(verify_api_key)):
    """
    현재 진행 중인 모든 작업 목록을 조회합니다.
    
    Args:
        api_key: 인증된 API 키
        
    Returns:
        활성 작업 목록
    """
    jobs_summary = []
    
    for job_id, job_data in active_jobs.items():
        jobs_summary.append({
            "job_id": job_id,
            "status": job_data["status"],
            "video_title": job_data["request"]["video_title"],
            "channel_name": job_data["request"]["channel_name"],
            "created_at": job_data["created_at"],
            "progress": job_data.get("progress", 0)
        })
    
    return {
        "total_jobs": len(jobs_summary),
        "jobs": jobs_summary
    }

async def process_video_analysis(job_id: str, request: VideoAnalysisRequest):
    """
    실제 영상 분석을 수행하는 백그라운드 함수
    
    Args:
        job_id: 작업 ID
        request: 분석 요청 데이터
    """
    start_time = datetime.now()
    
    try:
        # 작업 상태를 processing으로 변경
        active_jobs[job_id]["status"] = "processing"
        active_jobs[job_id]["started_at"] = start_time.isoformat()
        active_jobs[job_id]["progress"] = 5.0
        
        logger.info(f"영상 분석 시작: {request.video_title}")
        
        # WorkflowManager를 통한 실제 분석 실행
        workflow_manager = WorkflowManager()
        
        # 분석 요청 생성
        analysis_request = AnalysisRequest(
            video_url=str(request.video_url),
            channel_name=request.channel_name,
            video_title=request.video_title,
            upload_date=request.publish_date,
            priority=request.priority
        )
        
        # 단계별 진행률 업데이트
        active_jobs[job_id]["progress"] = 10.0  # 음성 분석 시작
        
        # 실제 분석 실행
        result = await workflow_manager.analyze_video(analysis_request)
        
        # 완료 처리
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        active_jobs[job_id].update({
            "status": "completed",
            "completed_at": end_time.isoformat(),
            "processing_time": processing_time,
            "progress": 100.0,
            "candidates": result.candidates if result else [],
            "metadata": {
                "video_url": str(request.video_url),
                "channel_name": request.channel_name,
                "analysis_version": "2.0",
                "processing_duration": processing_time
            }
        })
        
        logger.info(f"영상 분석 완료: {job_id} ({processing_time:.2f}초)")
        
    except Exception as e:
        # 에러 처리
        error_time = datetime.now()
        error_message = str(e)
        
        active_jobs[job_id].update({
            "status": "failed",
            "failed_at": error_time.isoformat(),
            "error": error_message,
            "progress": -1
        })
        
        logger.error(f"영상 분석 실패: {job_id} - {error_message}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)