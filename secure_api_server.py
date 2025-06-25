#!/usr/bin/env python3
"""
보안 강화된 프로덕션 API 서버
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import time
import os
import logging
from datetime import datetime, timedelta
import jwt
from typing import Optional
import hashlib
import hmac

app = FastAPI(
    title="연예인 추천 아이템 자동화 시스템 API",
    description="프로덕션 보안 강화 버전",
    version="1.0.0",
    docs_url=None if os.getenv("ENVIRONMENT") == "production" else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT") == "production" else "/redoc"
)

# 보안 미들웨어
security = HTTPBearer()

# CORS 설정 (프로덕션용)
allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
if allowed_origins and allowed_origins[0]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

# 신뢰할 수 있는 호스트만 허용
allowed_hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
if allowed_hosts and allowed_hosts[0]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts
    )

# 요청 제한
request_counts = {}
RATE_LIMIT = 100  # 분당 요청 수 제한

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    current_time = time.time()
    
    # 1분 이전 요청 기록 삭제
    cutoff_time = current_time - 60
    request_counts[client_ip] = [
        req_time for req_time in request_counts.get(client_ip, [])
        if req_time > cutoff_time
    ]
    
    # 요청 수 확인
    if len(request_counts.get(client_ip, [])) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"}
        )
    
    # 현재 요청 기록
    request_counts.setdefault(client_ip, []).append(current_time)
    
    response = await call_next(request)
    return response

# JWT 토큰 검증
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        secret_key = os.getenv("JWT_SECRET")
        if not secret_key:
            raise HTTPException(status_code=500, detail="JWT secret not configured")
        
        payload = jwt.decode(credentials.credentials, secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# API 엔드포인트들 (보안 강화)
@app.get("/health")
async def health_check():
    """Health check (인증 불필요)"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.post("/auth/token")
async def get_access_token(request: Request):
    """액세스 토큰 발급"""
    # 실제로는 사용자 인증 로직 구현 필요
    api_key = request.headers.get("X-API-Key")
    if not api_key or not verify_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    secret_key = os.getenv("JWT_SECRET")
    payload = {
        "sub": "api_user",
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    
    return {"access_token": token, "token_type": "bearer"}

def verify_api_key(api_key: str) -> bool:
    """API 키 검증"""
    expected_key = os.getenv("API_ACCESS_KEY")
    if not expected_key:
        return False
    
    # HMAC을 사용한 안전한 비교
    return hmac.compare_digest(api_key, expected_key)

# 보안이 필요한 엔드포인트들
@app.get("/api/v1/collection/status")
async def get_collection_status(user: str = Depends(verify_token)):
    """수집 상태 조회 (인증 필요)"""
    return {
        "status": "active",
        "total_channels": 25,
        "active_channels": 23,
        "total_videos_collected": 1247,
        "last_collection_time": datetime.now().isoformat()
    }

@app.post("/api/v1/analysis/video")
async def analyze_video(request: dict, user: str = Depends(verify_token)):
    """비디오 분석 (인증 필요)"""
    video_url = request.get("video_url")
    if not video_url:
        raise HTTPException(status_code=400, detail="video_url is required")
    
    # 분석 로직 (모의)
    return {
        "status": "completed",
        "video_url": video_url,
        "processing_time": 0.05,
        "candidates_found": 3,
        "results": [
            {
                "product_name": "보안 강화 제품",
                "confidence_score": 0.95,
                "ppl_probability": 0.10
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    # HTTPS 설정
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    
    if ssl_keyfile and ssl_certfile:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
