"""
API Usage and Cost Tracking System for Influence Item Project

이 모듈은 PRD 섹션 6.2에 명시된 API 비용 구조를 기반으로
모든 API 호출을 추적하고 비용을 계산합니다.

추적 대상 API:
- Google Gemini 2.5 Flash API (월 약 700원)
- Coupang Partners API (무료)
- OpenAI Whisper API (0원 - 오픈소스 사용)
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from contextlib import contextmanager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class APIUsageRecord:
    """API 사용 기록을 저장하는 데이터클래스"""
    timestamp: str
    api_name: str
    endpoint: str
    method: str
    tokens_used: int
    cost_krw: float
    status_code: int
    response_time_ms: float
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class CostConfig:
    """API 비용 설정"""
    # PRD 기반 비용 설정 (월 900편 기준)
    GEMINI_COST_PER_1K_TOKENS = 0.0008  # KRW per 1K tokens (월 700원 / 월 900편)
    COUPANG_COST_PER_REQUEST = 0.0  # 무료
    WHISPER_COST_PER_REQUEST = 0.0  # 오픈소스 사용


class APIUsageTracker:
    """API 사용량 및 비용 추적 시스템"""
    
    def __init__(self, db_path: str = "influence_item_usage.db"):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self.cost_config = CostConfig()
        self._lock = threading.Lock()
        self._initialize_database()
        
        logger.info(f"API Usage Tracker 초기화 완료: {self.db_path}")
    
    def _initialize_database(self):
        """데이터베이스 및 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    api_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    cost_krw REAL DEFAULT 0.0,
                    status_code INTEGER,
                    response_time_ms REAL,
                    error_message TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON api_usage(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_name ON api_usage(api_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON api_usage(date(timestamp))")
            
            conn.commit()
    
    def track_api_call(self, 
                      api_name: str,
                      endpoint: str,
                      method: str = "POST",
                      tokens_used: int = 0,
                      status_code: int = 200,
                      response_time_ms: float = 0.0,
                      error_message: Optional[str] = None,
                      metadata: Optional[Dict] = None) -> None:
        """
        API 호출을 추적하고 비용을 계산합니다.
        
        Args:
            api_name: API 이름 (gemini, coupang, whisper)
            endpoint: API 엔드포인트
            method: HTTP 메소드
            tokens_used: 사용된 토큰 수 (Gemini의 경우)
            status_code: HTTP 상태 코드
            response_time_ms: 응답 시간 (밀리초)
            error_message: 에러 메시지 (있는 경우)
            metadata: 추가 메타데이터
        """
        try:
            # 비용 계산
            cost_krw = self._calculate_cost(api_name, tokens_used)
            
            # 기록 생성
            record = APIUsageRecord(
                timestamp=datetime.now().isoformat(),
                api_name=api_name.lower(),
                endpoint=endpoint,
                method=method.upper(),
                tokens_used=tokens_used,
                cost_krw=cost_krw,
                status_code=status_code,
                response_time_ms=response_time_ms,
                error_message=error_message,
                metadata=metadata
            )
            
            # 데이터베이스에 저장
            self._save_record(record)
            
            logger.info(f"API 호출 추적됨: {api_name} - 비용: ₩{cost_krw:.4f}")
            
        except Exception as e:
            logger.error(f"API 사용량 추적 실패: {e}")
    
    def _calculate_cost(self, api_name: str, tokens_used: int) -> float:
        """API별 비용 계산"""
        api_name = api_name.lower()
        
        if api_name == "gemini":
            return (tokens_used / 1000) * self.cost_config.GEMINI_COST_PER_1K_TOKENS
        elif api_name == "coupang":
            return self.cost_config.COUPANG_COST_PER_REQUEST
        elif api_name == "whisper":
            return self.cost_config.WHISPER_COST_PER_REQUEST
        else:
            logger.warning(f"알 수 없는 API: {api_name}")
            return 0.0
    
    def _save_record(self, record: APIUsageRecord) -> None:
        """데이터베이스에 기록 저장"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO api_usage 
                    (timestamp, api_name, endpoint, method, tokens_used, 
                     cost_krw, status_code, response_time_ms, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.timestamp, record.api_name, record.endpoint, 
                    record.method, record.tokens_used, record.cost_krw,
                    record.status_code, record.response_time_ms, 
                    record.error_message, 
                    json.dumps(record.metadata) if record.metadata else None
                ))
                conn.commit()
    
    def get_usage_summary(self, days: int = 30) -> Dict:
        """
        지정된 기간의 사용량 요약을 반환합니다.
        
        Args:
            days: 조회할 일수 (기본: 30일)
            
        Returns:
            사용량 및 비용 요약 딕셔너리
        """
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 전체 요약
            cursor = conn.execute("""
                SELECT 
                    api_name,
                    COUNT(*) as total_calls,
                    SUM(tokens_used) as total_tokens,
                    SUM(cost_krw) as total_cost,
                    AVG(response_time_ms) as avg_response_time,
                    COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count
                FROM api_usage 
                WHERE timestamp >= ?
                GROUP BY api_name
                ORDER BY total_cost DESC
            """, (start_date,))
            
            api_summary = []
            total_cost = 0.0
            total_calls = 0
            
            for row in cursor:
                api_data = dict(row)
                api_summary.append(api_data)
                total_cost += api_data['total_cost']
                total_calls += api_data['total_calls']
            
            # 일별 사용량
            cursor = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    api_name,
                    COUNT(*) as calls,
                    SUM(cost_krw) as cost
                FROM api_usage 
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp), api_name
                ORDER BY date DESC
            """, (start_date,))
            
            daily_usage = {}
            for row in cursor:
                date = row['date']
                if date not in daily_usage:
                    daily_usage[date] = {}
                daily_usage[date][row['api_name']] = {
                    'calls': row['calls'],
                    'cost': row['cost']
                }
        
        return {
            'period_days': days,
            'total_cost_krw': total_cost,
            'total_calls': total_calls,
            'api_breakdown': api_summary,
            'daily_usage': daily_usage,
            'generated_at': datetime.now().isoformat()
        }
    
    def get_monthly_projection(self) -> Dict:
        """현재 사용량 기반 월간 예상 비용 계산"""
        # 최근 7일 데이터로 월간 예상 계산
        recent_summary = self.get_usage_summary(days=7)
        
        if recent_summary['total_calls'] == 0:
            return {
                'projected_monthly_cost': 0.0,
                'projected_monthly_calls': 0,
                'daily_average_cost': 0.0,
                'warning': None
            }
        
        daily_average_cost = recent_summary['total_cost_krw'] / 7
        monthly_projection = daily_average_cost * 30
        
        # PRD 기준 월 예산 (15,000원)과 비교
        budget_warning = None
        if monthly_projection > 15000:
            budget_warning = f"월 예산 초과 예상: ₩{monthly_projection:,.0f} > ₩15,000"
        
        return {
            'projected_monthly_cost': monthly_projection,
            'projected_monthly_calls': int(recent_summary['total_calls'] * 30 / 7),
            'daily_average_cost': daily_average_cost,
            'budget_status': 'over_budget' if monthly_projection > 15000 else 'within_budget',
            'warning': budget_warning,
            'prd_monthly_budget': 15000
        }
    
    @contextmanager
    def track_request(self, api_name: str, endpoint: str, method: str = "POST"):
        """
        컨텍스트 매니저로 API 요청을 자동 추적합니다.
        
        사용 예:
        with tracker.track_request("gemini", "/v1/generate") as tracking:
            # API 호출 코드
            response = api_call()
            tracking.set_tokens(response.usage.total_tokens)
        """
        tracking_data = {
            'start_time': datetime.now(),
            'tokens_used': 0,
            'status_code': 200,
            'error_message': None,
            'metadata': {}
        }
        
        class TrackingContext:
            def set_tokens(self, tokens: int):
                tracking_data['tokens_used'] = tokens
            
            def set_status(self, status_code: int):
                tracking_data['status_code'] = status_code
            
            def set_error(self, error_message: str):
                tracking_data['error_message'] = error_message
            
            def add_metadata(self, key: str, value):
                tracking_data['metadata'][key] = value
        
        context = TrackingContext()
        
        try:
            yield context
        except Exception as e:
            tracking_data['error_message'] = str(e)
            tracking_data['status_code'] = 500
            raise
        finally:
            # 응답 시간 계산
            end_time = datetime.now()
            response_time = (end_time - tracking_data['start_time']).total_seconds() * 1000
            
            # 추적 기록
            self.track_api_call(
                api_name=api_name,
                endpoint=endpoint,
                method=method,
                tokens_used=tracking_data['tokens_used'],
                status_code=tracking_data['status_code'],
                response_time_ms=response_time,
                error_message=tracking_data['error_message'],
                metadata=tracking_data['metadata'] if tracking_data['metadata'] else None
            )


# 전역 추적기 인스턴스
_global_tracker = None

def get_tracker() -> APIUsageTracker:
    """전역 추적기 인스턴스를 반환합니다."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = APIUsageTracker()
    return _global_tracker


# 편의 함수들
def track_gemini_call(tokens_used: int, endpoint: str = "/v1/generate", **kwargs):
    """Gemini API 호출 추적"""
    tracker = get_tracker()
    tracker.track_api_call("gemini", endpoint, tokens_used=tokens_used, **kwargs)


def track_coupang_call(endpoint: str, **kwargs):
    """Coupang API 호출 추적"""
    tracker = get_tracker()
    tracker.track_api_call("coupang", endpoint, **kwargs)


def track_whisper_call(endpoint: str = "/transcribe", **kwargs):
    """Whisper API 호출 추적"""
    tracker = get_tracker()
    tracker.track_api_call("whisper", endpoint, **kwargs)