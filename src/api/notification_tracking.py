"""
알림 이력 로깅 및 추적 API
Google Sheets 연동 및 알림 시스템을 위한 백엔드 지원
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
import uuid

# 라우터 설정
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

class NotificationLog(BaseModel):
    """알림 로그 모델"""
    id: Optional[str] = None
    notification_type: str
    priority: str
    channels: List[str]
    content: Dict[str, Any]
    status: str  # 'pending', 'sent', 'failed', 'throttled'
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
class ChannelSyncRequest(BaseModel):
    """채널 동기화 요청 모델"""
    channels: List[Dict[str, Any]]
    sync_time: str
    total_channels: int

class ThrottleCheck(BaseModel):
    """스로틀링 체크 요청 모델"""
    key: str
    seconds: int

class NotificationTracker:
    """알림 추적 및 로깅 클래스"""
    
    def __init__(self):
        self.logs = []  # 실제 구현에서는 데이터베이스 사용
        self.throttle_cache = {}  # 실제 구현에서는 Redis 사용
    
    def log_notification(self, log: NotificationLog) -> str:
        """알림 로그 기록"""
        if not log.id:
            log.id = str(uuid.uuid4())
        
        log.created_at = datetime.now()
        self.logs.append(log)
        
        return log.id
    
    def update_notification_status(self, log_id: str, status: str, error_message: Optional[str] = None):
        """알림 상태 업데이트"""
        for log in self.logs:
            if log.id == log_id:
                log.status = status
                if status == 'sent':
                    log.sent_at = datetime.now()
                if error_message:
                    log.error_message = error_message
                break
    
    def check_throttle(self, key: str, seconds: int) -> Dict[str, Any]:
        """스로틀링 상태 확인"""
        now = datetime.now()
        
        if key in self.throttle_cache:
            last_sent = self.throttle_cache[key]['last_sent']
            if (now - last_sent).total_seconds() < seconds:
                return {
                    'is_throttled': True,
                    'last_sent': last_sent.isoformat(),
                    'next_allowed': (last_sent + timedelta(seconds=seconds)).isoformat(),
                    'reason': 'frequency_limit'
                }
        
        return {
            'is_throttled': False,
            'last_sent': None,
            'next_allowed': now.isoformat()
        }
    
    def set_throttle(self, key: str, seconds: int, metadata: Optional[Dict] = None):
        """스로틀링 상태 설정"""
        self.throttle_cache[key] = {
            'last_sent': datetime.now(),
            'throttle_seconds': seconds,
            'metadata': metadata or {}
        }
    
    def get_notification_history(self, 
                               notification_type: Optional[str] = None,
                               priority: Optional[str] = None,
                               status: Optional[str] = None,
                               hours: int = 24) -> List[NotificationLog]:
        """알림 이력 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_logs = []
        for log in self.logs:
            if hasattr(log, 'created_at') and log.created_at < cutoff_time:
                continue
                
            if notification_type and log.notification_type != notification_type:
                continue
                
            if priority and log.priority != priority:
                continue
                
            if status and log.status != status:
                continue
                
            filtered_logs.append(log)
        
        return sorted(filtered_logs, key=lambda x: x.created_at if hasattr(x, 'created_at') else datetime.now(), reverse=True)

# 전역 트래커 인스턴스
tracker = NotificationTracker()

@router.post("/log")
async def log_notification(log: NotificationLog):
    """알림 로그 기록"""
    try:
        log_id = tracker.log_notification(log)
        return {
            "success": True,
            "log_id": log_id,
            "message": "알림 로그가 기록되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/log/{log_id}/status")
async def update_notification_status(log_id: str, status: str, error_message: Optional[str] = None):
    """알림 상태 업데이트"""
    try:
        tracker.update_notification_status(log_id, status, error_message)
        return {
            "success": True,
            "message": f"알림 상태가 {status}로 업데이트되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/throttle/check")
async def check_throttle(key: str, seconds: int):
    """스로틀링 상태 확인"""
    try:
        result = tracker.check_throttle(key, seconds)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/throttle/set")
async def set_throttle(request: Dict[str, Any]):
    """스로틀링 상태 설정"""
    try:
        key = request.get('key')
        seconds = request.get('seconds')
        metadata = request.get('metadata', {})
        
        if not key or not seconds:
            raise HTTPException(status_code=400, detail="key와 seconds는 필수입니다.")
        
        tracker.set_throttle(key, seconds, metadata)
        return {
            "success": True,
            "message": f"스로틀링이 {seconds}초 동안 설정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_notification_history(
    notification_type: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    hours: int = 24
):
    """알림 이력 조회"""
    try:
        logs = tracker.get_notification_history(notification_type, priority, status, hours)
        return {
            "success": True,
            "total_count": len(logs),
            "logs": [log.dict() for log in logs]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-channels")
async def sync_channels(request: ChannelSyncRequest):
    """채널 목록 동기화 (Google Sheets에서 호출)"""
    try:
        # 채널 동기화 로직
        sync_log = NotificationLog(
            notification_type="channel_sync",
            priority="LOW",
            channels=["slack"],
            content={
                "sync_time": request.sync_time,
                "total_channels": request.total_channels,
                "channels": request.channels
            },
            status="completed"
        )
        
        log_id = tracker.log_notification(sync_log)
        
        return {
            "success": True,
            "message": f"{request.total_channels}개 채널이 동기화되었습니다.",
            "log_id": log_id,
            "sync_time": request.sync_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/daily")
async def get_daily_stats(start_date: str, end_date: str):
    """일일 통계 조회 (리포트 워크플로우에서 호출)"""
    try:
        # 실제 구현에서는 데이터베이스에서 통계 조회
        stats = {
            "total_videos_analyzed": 15,
            "total_candidates_found": 42,
            "total_approved_candidates": 18,
            "total_rejected_candidates": 24,
            "active_channels": 8,
            "new_channels_added": 1,
            "avg_processing_time_seconds": 127.5,
            "avg_score_per_candidate": 73.2,
            "total_errors": 2,
            "critical_errors": 0,
            "monetizable_candidates": 16,
            "coupang_products_found": 14,
            "system_uptime_percentage": 99.2,
            "api_calls_count": 156,
            "storage_used_gb": 2.3
        }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "notification_tracking",
        "timestamp": datetime.now().isoformat(),
        "total_logs": len(tracker.logs),
        "throttle_entries": len(tracker.throttle_cache)
    }