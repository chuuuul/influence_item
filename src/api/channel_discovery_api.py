"""
채널 디스커버리 API 엔드포인트
n8n에서 호출할 수 있는 간단한 REST API
"""

from flask import Flask, request, jsonify
import asyncio
import os
import sys
from datetime import date, timedelta, datetime
from pathlib import Path
import json
import logging
import time
import threading
from functools import wraps, lru_cache
from typing import Dict, Any, Optional
import hashlib

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.channel_discovery.channel_discovery_engine import ChannelDiscoveryEngine
from src.channel_discovery.models import DiscoveryConfig, ChannelType
from src.integrations.google_sheets_integration import GoogleSheetsIntegration
from src.integrations.slack_integration import SlackIntegration

app = Flask(__name__)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 성능 최적화를 위한 캐시
_cache = {}
_cache_lock = threading.Lock()
_cache_ttl = 300  # 5분 TTL

# 요청 통계
_request_stats = {
    'total_requests': 0,
    'cache_hits': 0,
    'avg_response_time': 0.0,
    'last_reset': time.time()
}

def load_env_variables():
    """환경변수 로드"""
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    if not os.getenv(key):
                        os.environ[key] = value

def cache_key_from_request(data: Dict[str, Any]) -> str:
    """요청 데이터로부터 캐시 키 생성"""
    # 주요 파라미터만 사용하여 캐시 키 생성
    key_data = {
        'keywords': sorted(data.get('keywords', [])),
        'days_back': data.get('days_back', 7),
        'max_candidates': data.get('max_candidates', 50),
        'min_score': data.get('min_matching_score', 0.3)
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

def get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """캐시에서 결과 조회"""
    with _cache_lock:
        if cache_key in _cache:
            cached_data, timestamp = _cache[cache_key]
            if time.time() - timestamp < _cache_ttl:
                _request_stats['cache_hits'] += 1
                logger.info(f"Cache hit for key: {cache_key}")
                return cached_data
            else:
                # 만료된 캐시 삭제
                del _cache[cache_key]
    return None

def set_cached_result(cache_key: str, result: Dict[str, Any]):
    """결과를 캐시에 저장"""
    with _cache_lock:
        _cache[cache_key] = (result, time.time())
        # 캐시 크기 제한 (최대 100개)
        if len(_cache) > 100:
            # 가장 오래된 항목 삭제
            oldest_key = min(_cache.keys(), key=lambda k: _cache[k][1])
            del _cache[oldest_key]

def performance_monitor(func):
    """성능 모니터링 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        _request_stats['total_requests'] += 1
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 평균 응답 시간 업데이트
            current_avg = _request_stats['avg_response_time']
            total_requests = _request_stats['total_requests']
            _request_stats['avg_response_time'] = (
                (current_avg * (total_requests - 1) + execution_time) / total_requests
            )
            
            logger.info(f"Request completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Request failed after {execution_time:.2f}s: {str(e)}")
            raise
            
    return wrapper

def cleanup_cache():
    """만료된 캐시 항목 정리"""
    with _cache_lock:
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in _cache.items()
            if current_time - timestamp >= _cache_ttl
        ]
        for key in expired_keys:
            del _cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "channel_discovery_api"
    })

@app.route('/discover', methods=['POST'])
@performance_monitor
def run_channel_discovery():
    """채널 디스커버리 실행 (캐싱 및 성능 최적화 적용)"""
    
    try:
        # 환경변수 로드
        load_env_variables()
        
        # 요청 데이터 파싱
        data = request.get_json() or {}
        
        # 설정 파라미터 (기본값 설정)
        keywords = data.get('keywords', ["아이유", "뷰티", "패션"])
        days_back = data.get('days_back', 7)
        max_candidates = data.get('max_candidates', 50)
        min_score = data.get('min_matching_score', 0.3)
        force_refresh = data.get('force_refresh', False)  # 강제 새로고침 옵션
        
        logger.info(f"채널 디스커버리 API 호출: keywords={keywords}, days_back={days_back}")
        
        # 캐시 키 생성
        cache_key = cache_key_from_request(data)
        
        # 캐시에서 결과 확인 (강제 새로고침이 아닌 경우)
        if not force_refresh:
            cached_result = get_cached_result(cache_key)
            if cached_result:
                # 캐시에서 조회됨을 표시
                cached_result['cached'] = True
                cached_result['cache_timestamp'] = datetime.now().isoformat()
                logger.info(f"캐시된 결과 반환: {cache_key}")
                return jsonify(cached_result)
        
        # API 키 확인
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
            return jsonify({
                "success": False,
                "error": "YouTube API 키가 설정되지 않았습니다.",
                "timestamp": datetime.now().isoformat()
            }), 500
        
        # 비동기 실행을 위한 이벤트 루프
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 채널 탐색 실행
        result = loop.run_until_complete(
            _run_discovery_async(api_key, keywords, days_back, max_candidates, min_score)
        )
        
        # 성공한 결과만 캐시에 저장
        if result.get('success', False):
            result['cached'] = False
            result['cache_key'] = cache_key
            set_cached_result(cache_key, result)
            logger.info(f"결과를 캐시에 저장: {cache_key}")
        
        # 캐시 정리 (비동기)
        threading.Thread(target=cleanup_cache, daemon=True).start()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"채널 디스커버리 API 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

async def _run_discovery_async(api_key, keywords, days_back, max_candidates, min_score):
    """비동기 채널 탐색 실행"""
    
    start_time = datetime.now()
    
    # 채널 탐색 엔진 초기화
    engine = ChannelDiscoveryEngine(youtube_api_key=api_key, mock_mode=False)
    
    # 탐색 설정
    config = DiscoveryConfig(
        start_date=date.today() - timedelta(days=days_back),
        end_date=date.today(),
        target_keywords=keywords,
        target_categories=['Entertainment', 'People & Blogs', 'Howto & Style'],
        target_channel_types=[
            ChannelType.CELEBRITY_PERSONAL, 
            ChannelType.BEAUTY_INFLUENCER,
            ChannelType.FASHION_INFLUENCER,
            ChannelType.LIFESTYLE_INFLUENCER
        ],
        min_subscriber_count=10000,
        max_subscriber_count=3000000,
        min_video_count=20,
        target_language="ko",
        target_country="KR",
        max_results_per_query=20,
        max_total_candidates=max_candidates,
        min_matching_score=min_score,
        search_methods=["keyword_search", "trending"]
    )
    
    # 채널 탐색 실행
    candidates = await engine.discover_channels(config)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # 결과 정리
    candidates_data = [
        {
            "channel_id": c.channel_id,
            "channel_name": c.channel_name,
            "channel_url": c.channel_url,
            "total_score": c.total_score,
            "matching_score": getattr(c, 'matching_score', 0),
            "quality_score": getattr(c, 'quality_score', 0),
            "potential_score": getattr(c, 'potential_score', 0),
            "monetization_score": getattr(c, 'monetization_score', 0),
            "subscriber_count": c.subscriber_count,
            "video_count": c.video_count,
            "verified": c.verified,
            "country": c.country,
            "channel_type": getattr(c, 'channel_type', ''),
            "description": c.description[:200] + "..." if len(c.description) > 200 else c.description
        } for c in candidates
    ]
    
    result_data = {
        "success": True,
        "timestamp": end_time.isoformat(),
        "execution_time_seconds": duration,
        "total_candidates": len(candidates),
        "high_score_candidates": len([c for c in candidates if c.total_score >= 70]),
        "session_id": engine.current_session.session_id if engine.current_session else None,
        "candidates": candidates_data[:20]  # 상위 20개만 반환
    }
    
    # 세션 정보
    session_info = {
        'session_id': engine.current_session.session_id if engine.current_session else 'unknown',
        'execution_time': duration
    }
    
    # Google Sheets 저장 (비동기로 실행하되 오류는 로그만)
    try:
        if candidates_data:
            sheets = GoogleSheetsIntegration()
            saved = sheets.save_channel_discovery_results(candidates_data, session_info)
            if saved:
                logger.info(f"Google Sheets에 {len(candidates_data)}개 결과 저장 완료")
                result_data["sheets_saved"] = True
            else:
                logger.warning("Google Sheets 저장 실패")
                result_data["sheets_saved"] = False
    except Exception as e:
        logger.error(f"Google Sheets 저장 오류: {str(e)}")
        result_data["sheets_saved"] = False
    
    # Slack 알림 (비동기로 실행하되 오류는 로그만)
    try:
        slack = SlackIntegration()
        sent = slack.send_channel_discovery_results(candidates_data, session_info)
        if sent:
            logger.info("Slack 알림 전송 완료")
            result_data["slack_sent"] = True
        else:
            logger.warning("Slack 알림 전송 실패")
            result_data["slack_sent"] = False
    except Exception as e:
        logger.error(f"Slack 알림 오류: {str(e)}")
        result_data["slack_sent"] = False
    
    # 세션 통계
    if engine.current_session:
        session_status = engine.get_session_status(engine.current_session.session_id)
        if session_status:
            result_data["session_stats"] = {
                "total_found": session_status['total_candidates_found'],
                "after_filtering": session_status.get('candidates_after_filtering', 0),
                "processing_errors": session_status['processing_errors']
            }
    
    return result_data

@app.route('/recent-results', methods=['GET'])
def get_recent_results():
    """최근 탐색 결과 조회"""
    
    try:
        results_dir = project_root / "channel_discovery_results"
        
        if not results_dir.exists():
            return jsonify({
                "success": False,
                "error": "결과 디렉토리가 존재하지 않습니다."
            }), 404
        
        # 최근 결과 파일들 찾기
        result_files = list(results_dir.glob("session_*.json"))
        result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        recent_results = []
        for file_path in result_files[:5]:  # 최근 5개
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                session_info = data.get('session_info', {})
                summary = data.get('summary', {})
                
                recent_results.append({
                    "session_id": session_info.get('session_id'),
                    "started_at": session_info.get('started_at'),
                    "total_candidates": summary.get('total_candidates', 0),
                    "high_score_count": summary.get('high_score_count', 0),
                    "status": session_info.get('status', 'unknown')
                })
                
            except Exception as e:
                logger.warning(f"결과 파일 읽기 실패 {file_path}: {str(e)}")
                continue
        
        return jsonify({
            "success": True,
            "recent_results": recent_results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"최근 결과 조회 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/sheets/statistics', methods=['GET'])
def get_sheets_statistics():
    """Google Sheets 통계 조회"""
    try:
        sheets = GoogleSheetsIntegration()
        stats = sheets.get_statistics()
        
        return jsonify({
            "success": True,
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Google Sheets 통계 조회 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/sheets/recent-discoveries', methods=['GET'])
def get_sheets_recent_discoveries():
    """Google Sheets에서 최근 탐색 결과 조회"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        sheets = GoogleSheetsIntegration()
        discoveries = sheets.get_latest_discoveries(limit=limit)
        
        return jsonify({
            "success": True,
            "discoveries": discoveries,
            "count": len(discoveries),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"최근 탐색 결과 조회 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/slack/test', methods=['POST'])
def test_slack_notification():
    """Slack 알림 테스트"""
    try:
        data = request.get_json() or {}
        message = data.get('message', 'API 서버에서 보내는 테스트 메시지')
        
        slack = SlackIntegration()
        sent = slack.send_simple_message("API 테스트", message)
        
        return jsonify({
            "success": sent,
            "message": "테스트 알림 전송 완료" if sent else "테스트 알림 전송 실패",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Slack 테스트 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/integrations/status', methods=['GET'])
def get_integrations_status():
    """통합 모듈 상태 확인"""
    status = {
        "google_sheets": {"available": False, "error": None},
        "slack": {"available": False, "error": None},
        "youtube_api": {"available": False, "error": None}
    }
    
    # Google Sheets 확인
    try:
        sheets = GoogleSheetsIntegration()
        info = sheets.get_spreadsheet_info()
        status["google_sheets"]["available"] = True
        status["google_sheets"]["spreadsheet_title"] = info.get('title')
        status["google_sheets"]["sheets_count"] = len(info.get('sheets', []))
    except Exception as e:
        status["google_sheets"]["error"] = str(e)
    
    # Slack 확인
    try:
        slack = SlackIntegration()
        test_result = slack.test_connection()
        status["slack"]["available"] = test_result
        if not test_result:
            status["slack"]["error"] = "연결 테스트 실패"
    except Exception as e:
        status["slack"]["error"] = str(e)
    
    # YouTube API 확인
    try:
        api_key = os.getenv('YOUTUBE_API_KEY')
        if api_key:
            status["youtube_api"]["available"] = True
            status["youtube_api"]["key_length"] = len(api_key)
        else:
            status["youtube_api"]["error"] = "API 키가 설정되지 않음"
    except Exception as e:
        status["youtube_api"]["error"] = str(e)
    
    return jsonify({
        "success": True,
        "integrations": status,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/performance/stats', methods=['GET'])
def get_performance_stats():
    """API 성능 통계 조회"""
    try:
        cache_hit_rate = (
            _request_stats['cache_hits'] / _request_stats['total_requests'] 
            if _request_stats['total_requests'] > 0 else 0.0
        )
        
        uptime = time.time() - _request_stats['last_reset']
        
        with _cache_lock:
            cache_size = len(_cache)
            cache_items = [
                {
                    'key': key[:8] + '...',  # 키의 일부만 표시
                    'age_seconds': time.time() - timestamp,
                    'size_estimate': len(str(data))
                }
                for key, (data, timestamp) in list(_cache.items())[:10]  # 최근 10개만
            ]
        
        stats = {
            'total_requests': _request_stats['total_requests'],
            'cache_hits': _request_stats['cache_hits'],
            'cache_hit_rate': round(cache_hit_rate * 100, 2),
            'avg_response_time': round(_request_stats['avg_response_time'], 3),
            'uptime_seconds': round(uptime, 1),
            'cache_info': {
                'size': cache_size,
                'ttl_seconds': _cache_ttl,
                'items': cache_items
            }
        }
        
        return jsonify({
            "success": True,
            "performance_stats": stats,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"성능 통계 조회 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """캐시 수동 삭제"""
    try:
        with _cache_lock:
            cache_size_before = len(_cache)
            _cache.clear()
        
        logger.info(f"캐시 수동 삭제: {cache_size_before}개 항목")
        
        return jsonify({
            "success": True,
            "message": f"{cache_size_before}개 캐시 항목이 삭제되었습니다.",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"캐시 삭제 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/cache/cleanup', methods=['POST'])
def manual_cleanup_cache():
    """만료된 캐시 수동 정리"""
    try:
        with _cache_lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in _cache.items()
                if current_time - timestamp >= _cache_ttl
            ]
            for key in expired_keys:
                del _cache[key]
        
        logger.info(f"만료된 캐시 정리: {len(expired_keys)}개 항목")
        
        return jsonify({
            "success": True,
            "cleaned_items": len(expired_keys),
            "message": f"{len(expired_keys)}개 만료된 캐시 항목이 정리되었습니다.",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"캐시 정리 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/stats/reset', methods=['POST'])
def reset_stats():
    """통계 초기화"""
    try:
        _request_stats['total_requests'] = 0
        _request_stats['cache_hits'] = 0
        _request_stats['avg_response_time'] = 0.0
        _request_stats['last_reset'] = time.time()
        
        logger.info("API 통계가 초기화되었습니다.")
        
        return jsonify({
            "success": True,
            "message": "통계가 초기화되었습니다.",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"통계 초기화 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    load_env_variables()
    
    # 개발용 서버 실행
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )