"""
Slack 웹훅 연동 모듈
PRD v1.0 - 자동화 파이프라인 알림 시스템
"""

import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """알림 유형"""
    PIPELINE_START = "pipeline_start"
    PIPELINE_SUCCESS = "pipeline_success"
    PIPELINE_ERROR = "pipeline_error"
    NO_NEW_VIDEOS = "no_new_videos"
    RSS_COLLECTION_COMPLETE = "rss_collection_complete"
    AI_ANALYSIS_COMPLETE = "ai_analysis_complete"
    DAILY_SUMMARY = "daily_summary"
    SYSTEM_HEALTH = "system_health"


class SlackNotifier:
    """Slack 알림 관리자"""
    
    def __init__(self, webhook_url: str = None):
        """
        Args:
            webhook_url: Slack 웹훅 URL
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning("Slack 웹훅 URL이 설정되지 않았습니다. 환경변수 SLACK_WEBHOOK_URL를 설정하세요.")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def send_notification(
        self,
        notification_type: NotificationType,
        data: Dict[str, Any],
        fallback_text: str = None
    ) -> bool:
        """
        알림 발송
        
        Args:
            notification_type: 알림 유형
            data: 알림 데이터
            fallback_text: 대체 텍스트
            
        Returns:
            발송 성공 여부
        """
        if not self.webhook_url:
            logger.error("Slack 웹훅 URL이 설정되지 않았습니다.")
            return False
        
        try:
            payload = self._build_message(notification_type, data, fallback_text)
            
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Slack 알림 발송 성공: {notification_type.value}")
                return True
            else:
                logger.error(f"Slack 알림 발송 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Slack 알림 발송 오류: {e}")
            return False
    
    def _build_message(
        self,
        notification_type: NotificationType,
        data: Dict[str, Any],
        fallback_text: str = None
    ) -> Dict[str, Any]:
        """알림 메시지 구성"""
        
        if notification_type == NotificationType.PIPELINE_START:
            return self._build_pipeline_start_message(data)
        elif notification_type == NotificationType.PIPELINE_SUCCESS:
            return self._build_pipeline_success_message(data)
        elif notification_type == NotificationType.PIPELINE_ERROR:
            return self._build_pipeline_error_message(data)
        elif notification_type == NotificationType.NO_NEW_VIDEOS:
            return self._build_no_videos_message(data)
        elif notification_type == NotificationType.RSS_COLLECTION_COMPLETE:
            return self._build_rss_complete_message(data)
        elif notification_type == NotificationType.AI_ANALYSIS_COMPLETE:
            return self._build_ai_complete_message(data)
        elif notification_type == NotificationType.DAILY_SUMMARY:
            return self._build_daily_summary_message(data)
        elif notification_type == NotificationType.SYSTEM_HEALTH:
            return self._build_health_message(data)
        else:
            return {
                "text": fallback_text or "알림",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": fallback_text or "알 수 없는 알림 유형입니다."
                        }
                    }
                ]
            }
    
    def _build_pipeline_start_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """파이프라인 시작 알림"""
        session_id = data.get('session_id', 'Unknown')
        channels_count = data.get('channels_count', 0)
        
        return {
            "text": "🚀 마스터 자동화 파이프라인 시작",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚀 PRD 마스터 자동화 파이프라인 시작!"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*세션 ID:*\n{session_id}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*모니터링 채널:*\n{channels_count}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*시작 시간:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*예상 소요 시간:*\n10-15분"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📋 *실행 단계:*\n✅ Google Sheets 채널 목록 읽기\n⏳ RSS 피드 수집\n⏳ AI 2-Pass 분석\n⏳ 결과 알림"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "자동화 시스템: n8n | 분석 엔진: Whisper + Gemini 2.5 Flash"
                        }
                    ]
                }
            ]
        }
    
    def _build_pipeline_success_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """파이프라인 성공 알림"""
        session_id = data.get('session_id', 'Unknown')
        stats = data.get('statistics', {})
        execution_time = data.get('execution_time', 0)
        channels_count = data.get('channels_count', 0)
        
        return {
            "text": "🎉 마스터 자동화 파이프라인 완료!",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎉 PRD 마스터 자동화 파이프라인 완료!"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*실행 시간:*\n{execution_time:.1f}분"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*처리된 채널:*\n{channels_count}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*분석된 영상:*\n{stats.get('videos_analyzed', 0)}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*발견된 제품:*\n{stats.get('products_found', 0)}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*수익화 가능:*\n{stats.get('monetizable_products', 0)}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*평균 점수:*\n{stats.get('avg_score', 0)}점"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📋 *PRD 파이프라인 단계:*\n✅ Google Sheets 채널 읽기\n✅ RSS 피드 수집\n✅ Whisper 음성 분석\n✅ Gemini 1차 탐색\n✅ 시각 분석 (OCR+Object)\n✅ Gemini 2차 종합\n✅ PPL 필터링\n✅ 쿠팡 수익화 검증\n✅ 매력도 스코어링"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🎯 *다음 단계:* 관리 대시보드에서 후보 검토 및 승인\n📊 <https://docs.google.com/spreadsheets/d/{os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID', 'SHEET_ID')}|Google Sheets에서 결과 확인>"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 세션: {session_id} | 시스템: n8n 마스터 자동화"
                        }
                    ]
                }
            ]
        }
    
    def _build_pipeline_error_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """파이프라인 오류 알림"""
        session_id = data.get('session_id', 'Unknown')
        error_message = data.get('error_message', 'Unknown error')
        error_step = data.get('error_step', 'Unknown')
        error_time = data.get('error_time', datetime.now().isoformat())
        
        return {
            "text": "🚨 마스터 자동화 파이프라인 오류",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 마스터 자동화 파이프라인 오류"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*오류 내용:*\n```{error_message}```\n\n*발생 단계:* {error_step}\n*세션 ID:* {session_id}\n*발생 시간:* {datetime.fromisoformat(error_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🔧 *긴급 조치 필요:*\n• API 서버 상태 확인\n• 환경변수 설정 검토\n• 로그 파일 분석\n• 시스템 재시작 고려"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "우선순위: 높음 | 24/7 자동화 중단됨 | 즉시 확인 필요"
                        }
                    ]
                }
            ]
        }
    
    def _build_no_videos_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """신규 영상 없음 알림"""
        session_id = data.get('session_id', 'Unknown')
        channels_count = data.get('channels_count', 0)
        
        return {
            "text": "😴 일일 수집 완료 - 새로운 영상 없음",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "😴 일일 자동화 완료 - 신규 콘텐츠 없음"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📊 *처리 결과:*\n• 채널 수: {channels_count}개\n• RSS 피드 확인: 완료\n• 신규 영상: 0개\n\n💡 지난 24시간 내 새로운 영상이 업로드되지 않았거나, 이미 분석이 완료된 영상들입니다."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 세션: {session_id} | 다음 실행: 내일 오전 7시"
                        }
                    ]
                }
            ]
        }
    
    def _build_rss_complete_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """RSS 수집 완료 알림"""
        new_videos = data.get('new_videos', 0)
        channels_processed = data.get('channels_processed', 0)
        
        return {
            "text": f"📡 RSS 수집 완료: {new_videos}개 신규 영상",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📡 *RSS 피드 수집 완료*\n• 처리된 채널: {channels_processed}개\n• 신규 영상: {new_videos}개\n• 다음 단계: AI 분석 시작"
                    }
                }
            ]
        }
    
    def _build_ai_complete_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """AI 분석 완료 알림"""
        stats = data.get('statistics', {})
        
        return {
            "text": f"🤖 AI 분석 완료: {stats.get('products_found', 0)}개 제품 발견",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🤖 *AI 2-Pass 분석 완료*\n• 분석된 영상: {stats.get('videos_analyzed', 0)}개\n• 발견된 제품: {stats.get('products_found', 0)}개\n• 수익화 가능: {stats.get('monetizable_products', 0)}개\n• 평균 점수: {stats.get('avg_score', 0)}점"
                    }
                }
            ]
        }
    
    def _build_daily_summary_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """일일 요약 알림"""
        daily_stats = data.get('daily_stats', {})
        
        return {
            "text": "📈 일일 성과 요약",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📈 일일 성과 요약"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*오늘 처리된 영상:*\n{daily_stats.get('total_videos', 0)}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*신규 후보:*\n{daily_stats.get('new_candidates', 0)}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*수익화 가능:*\n{daily_stats.get('monetizable', 0)}개"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*평균 매력도:*\n{daily_stats.get('avg_score', 0)}점"
                        }
                    ]
                }
            ]
        }
    
    def _build_health_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """시스템 상태 알림"""
        health_status = data.get('status', 'unknown')
        components = data.get('components', {})
        
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌'
        }.get(health_status, '❓')
        
        return {
            "text": f"{status_emoji} 시스템 상태: {health_status}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *시스템 상태 체크: {health_status.upper()}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*YouTube API:*\n{self._format_component_status(components.get('youtube_api', {}))}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*AI Pipeline:*\n{self._format_component_status(components.get('ai_pipeline', {}))}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Database:*\n{self._format_component_status(components.get('database', {}))}"
                        }
                    ]
                }
            ]
        }
    
    def _format_component_status(self, component: Dict[str, Any]) -> str:
        """컴포넌트 상태 포맷팅"""
        status = component.get('status', 'unknown')
        emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌'
        }.get(status, '❓')
        
        error = component.get('error', '')
        if error:
            return f"{emoji} {status}\n{error[:50]}..."
        else:
            return f"{emoji} {status}"


def create_slack_notifier(webhook_url: str = None) -> SlackNotifier:
    """Slack 알림 객체 생성"""
    return SlackNotifier(webhook_url)


# 편의 함수들
def send_pipeline_start_notification(
    session_id: str,
    channels_count: int,
    webhook_url: str = None
) -> bool:
    """파이프라인 시작 알림 발송"""
    notifier = create_slack_notifier(webhook_url)
    return notifier.send_notification(
        NotificationType.PIPELINE_START,
        {
            'session_id': session_id,
            'channels_count': channels_count
        }
    )


def send_pipeline_success_notification(
    session_id: str,
    statistics: Dict[str, Any],
    execution_time: float,
    channels_count: int,
    webhook_url: str = None
) -> bool:
    """파이프라인 성공 알림 발송"""
    notifier = create_slack_notifier(webhook_url)
    return notifier.send_notification(
        NotificationType.PIPELINE_SUCCESS,
        {
            'session_id': session_id,
            'statistics': statistics,
            'execution_time': execution_time,
            'channels_count': channels_count
        }
    )


def send_pipeline_error_notification(
    session_id: str,
    error_message: str,
    error_step: str,
    webhook_url: str = None
) -> bool:
    """파이프라인 오류 알림 발송"""
    notifier = create_slack_notifier(webhook_url)
    return notifier.send_notification(
        NotificationType.PIPELINE_ERROR,
        {
            'session_id': session_id,
            'error_message': error_message,
            'error_step': error_step,
            'error_time': datetime.now().isoformat()
        }
    )


def send_no_videos_notification(
    session_id: str,
    channels_count: int,
    webhook_url: str = None
) -> bool:
    """신규 영상 없음 알림 발송"""
    notifier = create_slack_notifier(webhook_url)
    return notifier.send_notification(
        NotificationType.NO_NEW_VIDEOS,
        {
            'session_id': session_id,
            'channels_count': channels_count
        }
    )


if __name__ == "__main__":
    # 테스트 코드
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if not os.getenv('SLACK_WEBHOOK_URL'):
        print("Slack 웹훅 URL이 설정되지 않았습니다.")
        print("환경변수 SLACK_WEBHOOK_URL를 설정해주세요.")
        sys.exit(1)
    
    # 테스트 알림 발송
    notifier = create_slack_notifier()
    
    # 파이프라인 시작 알림 테스트
    success = notifier.send_notification(
        NotificationType.PIPELINE_START,
        {
            'session_id': f'test_{int(datetime.now().timestamp())}',
            'channels_count': 5
        }
    )
    
    if success:
        print("✅ Slack 알림 테스트 성공")
    else:
        print("❌ Slack 알림 테스트 실패")