#!/usr/bin/env python3
"""
간단한 API 서버 - Health Check 테스트용
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import logging
import os
import json

app = FastAPI(
    title="연예인 추천 아이템 자동화 시스템 API",
    description="PRD 요구사항에 따른 전체 시스템 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic 모델들
class HealthCheckResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    version: str
    components: Dict[str, str]

class VideoAnalysisRequest(BaseModel):
    video_url: str
    channel_name: Optional[str] = None

class VideoAnalysisResponse(BaseModel):
    status: str
    video_url: str
    processing_time: float
    candidates_found: int
    results: List[Dict[str, Any]]

class CollectionStatusResponse(BaseModel):
    status: str
    total_channels: int
    active_channels: int
    total_videos_collected: int
    last_collection_time: str

# Health Check 엔드포인트
@app.get("/", response_model=HealthCheckResponse)
async def root():
    """루트 엔드포인트 - 기본 Health Check"""
    return HealthCheckResponse(
        status="healthy",
        message="연예인 추천 아이템 자동화 시스템 API가 정상 작동 중입니다",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        components={
            "database": "connected",
            "ai_pipeline": "ready",
            "rss_collector": "active",
            "monetization_service": "ready"
        }
    )

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """상세 Health Check"""
    return HealthCheckResponse(
        status="healthy",
        message="모든 시스템 구성 요소가 정상 작동 중입니다",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        components={
            "database": "connected",
            "ai_pipeline": "ready",
            "rss_collector": "active",
            "monetization_service": "ready",
            "youtube_api": "ready",
            "gemini_api": "ready",
            "coupang_api": "ready"
        }
    )

# Phase 1: 영상 수집 관련 엔드포인트
@app.get("/api/v1/collection/status", response_model=CollectionStatusResponse)
async def get_collection_status():
    """영상 수집 현황 조회"""
    return CollectionStatusResponse(
        status="active",
        total_channels=25,
        active_channels=23,
        total_videos_collected=1247,
        last_collection_time=datetime.now().isoformat()
    )

@app.post("/api/v1/collection/start")
async def start_collection():
    """RSS 자동 수집 시작"""
    return {
        "status": "started",
        "message": "RSS 자동 수집이 시작되었습니다",
        "job_id": "job_001",
        "estimated_duration": "5-10분"
    }

@app.get("/api/v1/collection/channels")
async def get_channels():
    """채널 목록 조회"""
    return {
        "channels": [
            {
                "channel_id": "UCqm0d0-s9CzoFNJWTGZ-8jw",
                "channel_name": "장원영",
                "channel_type": "personal",
                "is_active": True,
                "last_collected": datetime.now().isoformat()
            },
            {
                "channel_id": "UC123456789",
                "channel_name": "아이유 공식",
                "channel_type": "personal", 
                "is_active": True,
                "last_collected": datetime.now().isoformat()
            }
        ]
    }

# Phase 2: AI 분석 관련 엔드포인트
@app.post("/api/v1/analysis/video", response_model=VideoAnalysisResponse)
async def analyze_video(request: VideoAnalysisRequest):
    """영상 AI 분석 시작"""
    # 모의 분석 결과
    await asyncio.sleep(0.1)  # 처리 시간 시뮬레이션
    
    return VideoAnalysisResponse(
        status="completed",
        video_url=request.video_url,
        processing_time=0.05,
        candidates_found=3,
        results=[
            {
                "product_name": "블루투스 이어폰",
                "clip_start_time": 120,
                "clip_end_time": 145,
                "confidence_score": 0.92,
                "ppl_probability": 0.15
            },
            {
                "product_name": "핸드크림",
                "clip_start_time": 200,
                "clip_end_time": 220,
                "confidence_score": 0.88,
                "ppl_probability": 0.05
            },
            {
                "product_name": "선글라스",
                "clip_start_time": 300,
                "clip_end_time": 315,
                "confidence_score": 0.85,
                "ppl_probability": 0.03
            }
        ]
    )

@app.get("/api/v1/analysis/status/{job_id}")
async def get_analysis_status(job_id: str):
    """분석 작업 상태 조회"""
    return {
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "started_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat()
    }

# Phase 3: PPL 필터링 관련 엔드포인트
@app.post("/api/v1/filtering/ppl")
async def filter_ppl_content():
    """PPL 콘텐츠 필터링"""
    return {
        "status": "completed",
        "total_analyzed": 3,
        "ppl_detected": 1,
        "passed_filtering": 2,
        "filter_accuracy": 0.90,
        "filtered_results": [
            {
                "product_name": "핸드크림",
                "is_ppl": False,
                "confidence": 0.95
            },
            {
                "product_name": "선글라스", 
                "is_ppl": False,
                "confidence": 0.97
            }
        ]
    }

# Phase 4: 수익화 관련 엔드포인트
@app.post("/api/v1/monetization/check")
async def check_monetization():
    """수익화 가능성 검증"""
    return {
        "status": "completed",
        "total_checked": 2,
        "monetizable_count": 1,
        "monetization_rate": 0.5,
        "results": [
            {
                "product_name": "핸드크림",
                "is_monetizable": True,
                "coupang_url": "https://link.coupang.com/mock/handcream",
                "commission_rate": 0.035
            },
            {
                "product_name": "선글라스",
                "is_monetizable": False,
                "reason": "쿠팡에서 검색 결과 없음"
            }
        ]
    }

# Phase 5: 스코어링 관련 엔드포인트
@app.post("/api/v1/scoring/calculate")
async def calculate_scores():
    """매력도 스코어 계산"""
    return {
        "status": "completed",
        "total_scored": 1,
        "average_score": 88.0,
        "results": [
            {
                "product_name": "핸드크림",
                "sentiment_score": 0.9,
                "endorsement_score": 0.88,
                "influencer_score": 0.92,
                "total_score": 88.0,
                "grade": "A"
            }
        ]
    }

# Phase 6: 워크플로우 관리 관련 엔드포인트
@app.get("/api/v1/candidates")
async def get_candidates():
    """후보 목록 조회"""
    return {
        "candidates": [
            {
                "id": "candidate_001",
                "product_name": "핸드크림",
                "celebrity_name": "장원영",
                "total_score": 88.0,
                "status": "needs_review",
                "created_at": datetime.now().isoformat()
            }
        ],
        "total_count": 1,
        "page": 1,
        "per_page": 10
    }

@app.post("/api/v1/candidates/{candidate_id}/approve")
async def approve_candidate(candidate_id: str):
    """후보 승인"""
    return {
        "status": "approved",
        "candidate_id": candidate_id,
        "approved_at": datetime.now().isoformat()
    }

# 시스템 통계 엔드포인트
@app.get("/api/v1/stats/overview")
async def get_system_stats():
    """시스템 전체 통계"""
    return {
        "total_videos_processed": 1247,
        "total_candidates_found": 142,
        "approval_rate": 0.68,
        "average_processing_time": 0.05,
        "system_uptime": "99.9%",
        "last_updated": datetime.now().isoformat()
    }

# 에러 핸들러
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": f"서버 내부 오류: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)