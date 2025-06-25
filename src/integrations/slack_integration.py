#!/usr/bin/env python3
"""
Slack 통합 모듈
채널 탐색 결과 및 시스템 알림을 Slack으로 전송
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

class SlackIntegration:
    """Slack 통합 관리 클래스"""
    
    def __init__(self, webhook_url: str = None):
        """
        Slack 통합 초기화
        
        Args:
            webhook_url: Slack 웹훅 URL
        """
        self.webhook_url = webhook_url or self._get_webhook_url()
        
        if not self.webhook_url or self.webhook_url == 'your_slack_webhook_url_here':
            raise ValueError("Slack 웹훅 URL이 설정되지 않았습니다.")
        
        logger.info("Slack 통합 초기화 완료")
    
    def _get_webhook_url(self) -> str:
        """웹훅 URL 가져오기"""
        # 환경변수에서 확인
        webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        if webhook_url and webhook_url != 'your_slack_webhook_url_here':
            return webhook_url
        
        # .env 파일에서 확인
        env_file = project_root / '.env'
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('SLACK_WEBHOOK_URL='):
                        url = line.split('=', 1)[1].strip()
                        if url and url != 'your_slack_webhook_url_here':
                            return url
        
        raise ValueError("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
    
    def send_message(self, text: str, blocks: List[Dict] = None, channel: str = None) -> bool:
        """
        Slack 메시지 전송
        
        Args:
            text: 메시지 텍스트
            blocks: Slack Block Kit 블록 (선택사항)
            channel: 채널 지정 (선택사항)
        
        Returns:
            bool: 전송 성공 여부
        """
        try:
            payload = {"text": text}
            
            if blocks:
                payload["blocks"] = blocks
            
            if channel:
                payload["channel"] = channel
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info("Slack 메시지 전송 성공")
                return True
            else:
                logger.error(f"Slack 메시지 전송 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Slack 메시지 전송 오류: {str(e)}")
            return False
    
    def send_channel_discovery_results(self, candidates: List[Dict], session_info: Dict = None) -> bool:
        """
        채널 탐색 결과를 Slack으로 전송
        
        Args:
            candidates: 발견된 채널 후보 목록
            session_info: 세션 정보
        
        Returns:
            bool: 전송 성공 여부
        """
        if not candidates:
            return self.send_simple_message("🔍 채널 탐색 완료", "새로운 채널 후보를 찾지 못했습니다.")
        
        try:
            # 기본 정보 수집
            total_count = len(candidates)
            high_score_count = len([c for c in candidates if c.get('total_score', 0) >= 70])
            execution_time = session_info.get('execution_time', 0) if session_info else 0
            session_id = session_info.get('session_id', 'unknown') if session_info else 'unknown'
            
            # 메시지 제목
            title = f"🎉 채널 디스커버리 완료! {total_count}개 후보 발견"
            
            # 기본 통계 정보
            stats_text = f"""📊 *실행 결과:*
• 실행 시간: {execution_time:.1f}초
• 발견된 후보: {total_count}개
• 고득점 후보 (70점+): {high_score_count}개
• 세션 ID: {session_id}
• 발견 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            # 상위 채널 정보
            top_channels = candidates[:5]  # 상위 5개
            channels_text = "\n🏆 *상위 후보들:*\n"
            
            for i, candidate in enumerate(top_channels, 1):
                name = candidate.get('channel_name', 'Unknown')
                score = candidate.get('total_score', 0)
                subscribers = candidate.get('subscriber_count', 0)
                verified = "✓" if candidate.get('verified', False) else "✗"
                url = candidate.get('channel_url', '')
                
                if url:
                    channels_text += f"{i}. <{url}|{name}> ({score:.1f}점, {subscribers:,}명) {verified}\n"
                else:
                    channels_text += f"{i}. {name} ({score:.1f}점, {subscribers:,}명) {verified}\n"
            
            # 전체 메시지 구성
            full_message = f"{title}\n\n{stats_text}\n{channels_text}"
            
            # Block Kit 형태로 구성 (더 예쁜 형태)
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🎉 채널 디스커버리 완료!"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*발견된 후보:*\n{total_count}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*고득점 후보:*\n{high_score_count}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*실행 시간:*\n{execution_time:.1f}초"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*발견 시간:*\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        }
                    ]
                }
            ]
            
            # 상위 채널들을 블록으로 추가
            if top_channels:
                channels_block = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🏆 *상위 후보들:*"
                    }
                }
                blocks.append(channels_block)
                
                for i, candidate in enumerate(top_channels, 1):
                    name = candidate.get('channel_name', 'Unknown')
                    score = candidate.get('total_score', 0)
                    subscribers = candidate.get('subscriber_count', 0)
                    verified = "✓" if candidate.get('verified', False) else "✗"
                    url = candidate.get('channel_url', '')
                    description = candidate.get('description', '')[:100]
                    
                    channel_block = {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{i}. {name}* {verified}\n점수: {score:.1f}점 | 구독자: {subscribers:,}명\n{description}..."
                        }
                    }
                    
                    if url:
                        channel_block["accessory"] = {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "채널 보기"
                            },
                            "url": url
                        }
                    
                    blocks.append(channel_block)
            
            # 구분선 추가
            blocks.append({"type": "divider"})
            
            # 세션 정보
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"세션 ID: {session_id} | 시스템: 채널 디스커버리 엔진"
                    }
                ]
            })
            
            # 메시지 전송 (Block Kit 사용)
            success = self.send_message(full_message, blocks=blocks)
            
            if success:
                logger.info(f"Slack으로 {total_count}개 채널 탐색 결과 전송 완료")
            
            return success
            
        except Exception as e:
            logger.error(f"채널 탐색 결과 Slack 전송 실패: {str(e)}")
            # 실패시 간단한 메시지라도 전송
            return self.send_simple_message(
                "❌ 채널 탐색 알림 오류",
                f"채널 탐색이 완료되었지만 결과 전송 중 오류가 발생했습니다.\n오류: {str(e)}"
            )
    
    def send_simple_message(self, title: str, message: str) -> bool:
        """간단한 메시지 전송"""
        try:
            full_text = f"{title}\n\n{message}"
            return self.send_message(full_text)
        except Exception as e:
            logger.error(f"간단 메시지 전송 실패: {str(e)}")
            return False
    
    def send_error_notification(self, error_title: str, error_details: str, session_id: str = None) -> bool:
        """오류 알림 전송"""
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"❌ {error_title}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*오류 내용:*\n```{error_details}```"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*발생 시간:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*세션 ID:*\n{session_id or 'unknown'}"
                        }
                    ]
                }
            ]
            
            text = f"❌ {error_title}\n\n{error_details}"
            return self.send_message(text, blocks=blocks)
            
        except Exception as e:
            logger.error(f"오류 알림 전송 실패: {str(e)}")
            return False
    
    def send_system_status(self, status: str, details: Dict = None) -> bool:
        """시스템 상태 알림 전송"""
        try:
            status_emoji = {
                'healthy': '✅',
                'warning': '⚠️',
                'error': '❌',
                'maintenance': '🔧',
                'starting': '🚀'
            }.get(status.lower(), '📊')
            
            title = f"{status_emoji} 시스템 상태: {status.upper()}"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                }
            ]
            
            if details:
                fields = []
                for key, value in details.items():
                    fields.append({
                        "type": "mrkdwn",
                        "text": f"*{key}:*\n{value}"
                    })
                
                if fields:
                    blocks.append({
                        "type": "section",
                        "fields": fields
                    })
            
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"체크 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 시스템: Influence Item"
                    }
                ]
            })
            
            text = f"{title}\n\n" + "\n".join([f"{k}: {v}" for k, v in (details or {}).items()])
            return self.send_message(text, blocks=blocks)
            
        except Exception as e:
            logger.error(f"시스템 상태 알림 전송 실패: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """Slack 연결 테스트"""
        try:
            test_message = f"🤖 Slack 연결 테스트\n\n시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n상태: 정상 작동"
            
            success = self.send_message(test_message)
            
            if success:
                logger.info("Slack 연결 테스트 성공")
            else:
                logger.error("Slack 연결 테스트 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"Slack 연결 테스트 오류: {str(e)}")
            return False

def test_slack_integration():
    """Slack 통합 테스트"""
    try:
        print("🔍 Slack 통합 테스트 시작...")
        
        # 통합 모듈 초기화
        slack = SlackIntegration()
        
        # 연결 테스트
        if not slack.test_connection():
            print("❌ Slack 연결 테스트 실패")
            return False
        
        print("✅ Slack 연결 테스트 성공")
        
        # 채널 탐색 결과 테스트
        test_candidates = [
            {
                "channel_name": "테스트 뷰티 채널",
                "channel_id": "UC_TEST_001",
                "channel_url": "https://www.youtube.com/channel/UC_TEST_001",
                "subscriber_count": 150000,
                "video_count": 200,
                "total_score": 85.5,
                "verified": True,
                "description": "테스트용 뷰티 채널입니다. 다양한 메이크업과 스킨케어 컨텐츠를 제공합니다."
            },
            {
                "channel_name": "패션 인플루언서 테스트",
                "channel_id": "UC_TEST_002", 
                "channel_url": "https://www.youtube.com/channel/UC_TEST_002",
                "subscriber_count": 75000,
                "video_count": 120,
                "total_score": 72.3,
                "verified": False,
                "description": "패션과 라이프스타일 컨텐츠를 다루는 테스트 채널입니다."
            }
        ]
        
        session_info = {
            "session_id": "test_session_slack_001",
            "execution_time": 2.5
        }
        
        if slack.send_channel_discovery_results(test_candidates, session_info):
            print("✅ 채널 탐색 결과 알림 테스트 성공")
        else:
            print("❌ 채널 탐색 결과 알림 테스트 실패")
        
        # 시스템 상태 알림 테스트
        status_details = {
            "API 서버": "정상 작동",
            "데이터베이스": "연결됨",
            "YouTube API": "정상",
            "메모리 사용률": "65%"
        }
        
        if slack.send_system_status("healthy", status_details):
            print("✅ 시스템 상태 알림 테스트 성공")
        else:
            print("❌ 시스템 상태 알림 테스트 실패")
        
        print("🎉 Slack 통합 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ Slack 통합 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    test_slack_integration()