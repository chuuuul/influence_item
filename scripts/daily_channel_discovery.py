#!/usr/bin/env python3
"""
매일 자동 채널 디스커버리 실행 스크립트
"""

import os
import asyncio
import logging
import sys
from datetime import date, timedelta, datetime
from pathlib import Path
import json

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.channel_discovery.channel_discovery_engine import ChannelDiscoveryEngine
from src.channel_discovery.models import DiscoveryConfig, ChannelType
from scripts.notification_alternatives import NotificationManager

# 로깅 설정
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"daily_discovery_{date.today().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)

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

async def send_notifications(daily_report, candidates):
    """다양한 방법으로 알림 전송"""
    
    notifier = NotificationManager()
    
    # 알림 제목과 메시지 생성
    title = f"🎉 채널 디스커버리 완료! {daily_report['total_candidates']}개 후보 발견"
    
    message = f"""
📊 실행 결과:
• 실행 시간: {daily_report['execution_time']:.1f}초
• 발견된 후보: {daily_report['total_candidates']}개
• 고득점 후보: {daily_report['high_score_candidates']}개

🏆 상위 후보들:
"""
    
    for i, candidate in enumerate(daily_report['top_candidates'], 1):
        verified = "✓" if candidate['verified'] else "✗"
        message += f"• {candidate['name']} ({candidate['score']:.1f}점, {candidate['subscribers']:,}명) {verified}\n"
    
    message += f"""
📅 날짜: {daily_report['date']}
🆔 세션 ID: {daily_report['session_id']}
"""
    
    # 1. 항상 콘솔에 출력
    notifier.send_notification(title, message, method='console')
    
    # 2. 데스크톱 알림 (macOS)
    notifier.send_notification(title, f"{daily_report['total_candidates']}개 후보 발견!", method='desktop')
    
    # 3. 파일에 저장
    notifier.send_notification(title, message, method='file', 
                             filename='logs/daily_notifications.log')
    
    # 4. Slack (설정된 경우)
    slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
    if slack_webhook and slack_webhook != 'your_slack_webhook_url_here':
        try:
            import requests
            payload = {"text": f"{title}\n{message}"}
            response = requests.post(slack_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Slack 알림 전송 완료")
            else:
                logger.warning(f"⚠️ Slack 알림 실패: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Slack 알림 오류: {str(e)}")
    
    # 5. Discord (설정된 경우)
    discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if discord_webhook and discord_webhook != 'your_discord_webhook_url_here':
        notifier.send_notification(title, message, method='discord', webhook_url=discord_webhook)
    
    # 6. 이메일 (설정된 경우)
    gmail_email = os.getenv('GMAIL_EMAIL')
    if gmail_email and gmail_email != 'your_gmail@gmail.com':
        notifier.send_notification(title, message, method='email')

async def run_daily_discovery():
    """매일 채널 디스커버리 실행"""
    
    logger.info("🚀 매일 자동 채널 디스커버리 시작")
    
    try:
        # 환경변수 로드
        load_env_variables()
        
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
            logger.error("❌ YouTube API 키를 찾을 수 없습니다.")
            return False
        
        logger.info(f"✅ API 키 확인: {api_key[:10]}...")
        
        # 채널 탐색 엔진 초기화
        engine = ChannelDiscoveryEngine(youtube_api_key=api_key, mock_mode=False)
        logger.info(f"🔧 채널 탐색 엔진 초기화 완료 (Mock 모드: {engine.mock_mode})")
        
        # 매일 실행용 포괄적 탐색 설정
        config = DiscoveryConfig(
            start_date=date.today() - timedelta(days=7),  # 최근 1주일
            end_date=date.today(),
            target_keywords=[
                "아이유", "IU", "뷰티", "패션", "메이크업", "스킨케어",
                "라이프스타일", "vlog", "일상", "화장품", "코디", "스타일링"
            ],
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
            max_results_per_query=25,
            max_total_candidates=100,
            min_matching_score=0.1,
            search_methods=["keyword_search", "trending", "related_channels"]
        )
        
        # 진행 상황 로깅
        def progress_callback(percentage, message):
            logger.info(f"📊 {percentage:3.0f}% - {message}")
        
        # 채널 탐색 실행
        start_time = datetime.now()
        logger.info("🔍 포괄적 채널 탐색 시작...")
        
        candidates = await engine.discover_channels(config, progress_callback)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 결과 정리
        logger.info(f"🎉 채널 탐색 완료!")
        logger.info(f"   - 소요 시간: {duration:.1f}초")
        logger.info(f"   - 발견된 후보: {len(candidates)}개")
        
        if candidates:
            # 점수별 분류
            high_score = [c for c in candidates if c.total_score >= 70]
            medium_score = [c for c in candidates if 50 <= c.total_score < 70]
            
            logger.info(f"   - 고득점 후보 (70점 이상): {len(high_score)}개")
            logger.info(f"   - 중간 후보 (50-70점): {len(medium_score)}개")
            
            # 상위 10개 후보 로깅
            logger.info("🏆 상위 10개 후보:")
            for i, candidate in enumerate(candidates[:10], 1):
                logger.info(f"   {i:2d}. {candidate.channel_name} (점수: {candidate.total_score:.1f}, 구독자: {candidate.subscriber_count:,}명)")
        
        # 세션 통계
        session_status = engine.get_session_status(engine.current_session.session_id)
        if session_status:
            logger.info(f"📋 세션 통계:")
            logger.info(f"   - 총 후보 발견: {session_status['total_candidates_found']}개")
            logger.info(f"   - 필터링 후: {session_status.get('candidates_after_filtering', 0)}개")
            logger.info(f"   - 처리 오류: {session_status['processing_errors']}개")
        
        # 일일 리포트 저장
        daily_report = {
            "date": date.today().isoformat(),
            "execution_time": duration,
            "total_candidates": len(candidates),
            "high_score_candidates": len([c for c in candidates if c.total_score >= 70]),
            "session_id": engine.current_session.session_id,
            "top_candidates": [
                {
                    "name": c.channel_name,
                    "score": c.total_score,
                    "subscribers": c.subscriber_count,
                    "verified": c.verified
                } for c in candidates[:5]
            ]
        }
        
        # 리포트 저장
        reports_dir = project_root / "daily_reports"
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / f"discovery_report_{date.today().strftime('%Y%m%d')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(daily_report, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"📄 일일 리포트 저장: {report_file}")
        
        # 알림 전송 (여러 방법 동시 사용)
        await send_notifications(daily_report, candidates)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 매일 채널 탐색 실패: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(run_daily_discovery())
    
    if success:
        logger.info("✅ 매일 채널 디스커버리 완료!")
        exit(0)
    else:
        logger.error("❌ 매일 채널 디스커버리 실패!")
        exit(1)