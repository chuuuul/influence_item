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

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.channel_discovery.channel_discovery_engine import ChannelDiscoveryEngine
from src.channel_discovery.models import DiscoveryConfig, ChannelType

app = Flask(__name__)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "channel_discovery_api"
    })

@app.route('/discover', methods=['POST'])
def run_channel_discovery():
    """채널 디스커버리 실행"""
    
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
        
        logger.info(f"채널 디스커버리 API 호출: keywords={keywords}, days_back={days_back}")
        
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
    result_data = {
        "success": True,
        "timestamp": end_time.isoformat(),
        "execution_time_seconds": duration,
        "total_candidates": len(candidates),
        "high_score_candidates": len([c for c in candidates if c.total_score >= 70]),
        "session_id": engine.current_session.session_id if engine.current_session else None,
        "candidates": [
            {
                "channel_id": c.channel_id,
                "channel_name": c.channel_name,
                "channel_url": c.channel_url,
                "total_score": c.total_score,
                "subscriber_count": c.subscriber_count,
                "video_count": c.video_count,
                "verified": c.verified,
                "country": c.country,
                "description": c.description[:200] + "..." if len(c.description) > 200 else c.description
            } for c in candidates[:20]  # 상위 20개만 반환
        ]
    }
    
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

if __name__ == '__main__':
    load_env_variables()
    
    # 개발용 서버 실행
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )