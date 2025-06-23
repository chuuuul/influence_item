"""
T04_S03_M03: 장애 감지 및 자동 복구 시스템 - 다채널 알림 관리자
Slack, 이메일, SMS 등 다양한 채널을 통한 알림 시스템
"""

import time
import asyncio
import smtplib
import logging
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from pathlib import Path

# 기존 모듈 임포트
from dashboard.utils.failure_detector import FailureEvent, FailureSeverity
from dashboard.utils.recovery_orchestrator import RecoverySession
from config.config import Config

logger = logging.getLogger(__name__)


class AlertChannel(Enum):
    """알림 채널"""
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    LOG = "log"


class AlertType(Enum):
    """알림 유형"""
    FAILURE_DETECTED = "failure_detected"
    RECOVERY_SUCCESS = "recovery_success"
    RECOVERY_FAILED = "recovery_failed"
    ESCALATION = "escalation"
    SYSTEM_STATUS = "system_status"
    MAINTENANCE = "maintenance"


class AlertPriority(Enum):
    """알림 우선순위"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class AlertMessage:
    """알림 메시지"""
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    timestamp: datetime
    source_component: str
    channels: List[AlertChannel]
    context: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['alert_type'] = self.alert_type.value
        data['priority'] = self.priority.value
        data['timestamp'] = self.timestamp.isoformat()
        data['channels'] = [ch.value for ch in self.channels]
        return data


@dataclass
class AlertDelivery:
    """알림 전송 결과"""
    channel: AlertChannel
    success: bool
    message: str
    timestamp: datetime
    response_time_ms: Optional[float] = None
    error_details: Optional[str] = None


class SlackNotifier:
    """Slack 알림 전송"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or self._get_webhook_url()
        self.enabled = bool(self.webhook_url)
    
    def _get_webhook_url(self) -> Optional[str]:
        """설정에서 Slack Webhook URL 조회"""
        try:
            config = Config()
            return getattr(config, 'SLACK_WEBHOOK_URL', None)
        except Exception:
            return None
    
    async def send(self, alert: AlertMessage) -> AlertDelivery:
        """Slack 메시지 전송"""
        start_time = time.time()
        
        if not self.enabled:
            return AlertDelivery(
                channel=AlertChannel.SLACK,
                success=False,
                message="Slack webhook URL not configured",
                timestamp=datetime.now()
            )
        
        try:
            # Slack 메시지 포맷팅
            slack_message = self._format_slack_message(alert)
            
            # Webhook 전송
            response = requests.post(
                self.webhook_url,
                json=slack_message,
                timeout=30
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return AlertDelivery(
                    channel=AlertChannel.SLACK,
                    success=True,
                    message="Slack message sent successfully",
                    timestamp=datetime.now(),
                    response_time_ms=response_time
                )
            else:
                return AlertDelivery(
                    channel=AlertChannel.SLACK,
                    success=False,
                    message=f"Slack API error: HTTP {response.status_code}",
                    timestamp=datetime.now(),
                    response_time_ms=response_time,
                    error_details=response.text
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return AlertDelivery(
                channel=AlertChannel.SLACK,
                success=False,
                message=f"Slack send failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=response_time,
                error_details=str(e)
            )
    
    def _format_slack_message(self, alert: AlertMessage) -> Dict[str, Any]:
        """Slack 메시지 포맷팅"""
        # 우선순위별 색상 및 이모지
        priority_config = {
            AlertPriority.EMERGENCY: {"color": "#FF0000", "emoji": "🚨"},
            AlertPriority.CRITICAL: {"color": "#FF4500", "emoji": "🔥"},
            AlertPriority.HIGH: {"color": "#FFA500", "emoji": "⚠️"},
            AlertPriority.MEDIUM: {"color": "#FFFF00", "emoji": "⚡"},
            AlertPriority.LOW: {"color": "#00FF00", "emoji": "ℹ️"}
        }
        
        config = priority_config.get(alert.priority, priority_config[AlertPriority.MEDIUM])
        
        # 메시지 구성
        text = f"{config['emoji']} *{alert.title}*"
        
        attachment = {
            "color": config["color"],
            "fields": [
                {
                    "title": "Message",
                    "value": alert.message,
                    "short": False
                },
                {
                    "title": "Component",
                    "value": alert.source_component,
                    "short": True
                },
                {
                    "title": "Priority",
                    "value": alert.priority.value.upper(),
                    "short": True
                },
                {
                    "title": "Time",
                    "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "short": True
                }
            ]
        }
        
        # 컨텍스트 정보 추가
        if alert.context:
            for key, value in alert.context.items():
                if len(attachment["fields"]) < 10:  # Slack 제한
                    attachment["fields"].append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True
                    })
        
        return {
            "text": text,
            "attachments": [attachment]
        }


class EmailNotifier:
    """이메일 알림 전송"""
    
    def __init__(self):
        self.smtp_config = self._get_smtp_config()
        self.enabled = self._validate_config()
    
    def _get_smtp_config(self) -> Dict[str, Any]:
        """SMTP 설정 조회"""
        try:
            config = Config()
            return {
                'smtp_server': getattr(config, 'SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': getattr(config, 'SMTP_PORT', 587),
                'username': getattr(config, 'SMTP_USERNAME', None),
                'password': getattr(config, 'SMTP_PASSWORD', None),
                'from_email': getattr(config, 'ALERT_FROM_EMAIL', None),
                'to_emails': getattr(config, 'ALERT_TO_EMAILS', [])
            }
        except Exception:
            return {}
    
    def _validate_config(self) -> bool:
        """설정 유효성 확인"""
        required_fields = ['smtp_server', 'username', 'password', 'from_email']
        return all(self.smtp_config.get(field) for field in required_fields)
    
    async def send(self, alert: AlertMessage) -> AlertDelivery:
        """이메일 전송"""
        start_time = time.time()
        
        if not self.enabled:
            return AlertDelivery(
                channel=AlertChannel.EMAIL,
                success=False,
                message="Email configuration not complete",
                timestamp=datetime.now()
            )
        
        try:
            # 이메일 메시지 생성
            msg = self._create_email_message(alert)
            
            # SMTP 서버 연결 및 전송
            with smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                
                to_emails = self.smtp_config['to_emails']
                if isinstance(to_emails, str):
                    to_emails = [to_emails]
                
                server.send_message(msg, to_addrs=to_emails)
            
            response_time = (time.time() - start_time) * 1000
            
            return AlertDelivery(
                channel=AlertChannel.EMAIL,
                success=True,
                message=f"Email sent to {len(to_emails)} recipients",
                timestamp=datetime.now(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return AlertDelivery(
                channel=AlertChannel.EMAIL,
                success=False,
                message=f"Email send failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=response_time,
                error_details=str(e)
            )
    
    def _create_email_message(self, alert: AlertMessage) -> MimeMultipart:
        """이메일 메시지 생성"""
        msg = MimeMultipart('alternative')
        
        # 헤더 설정
        msg['From'] = self.smtp_config['from_email']
        msg['To'] = ', '.join(self.smtp_config['to_emails'] if isinstance(self.smtp_config['to_emails'], list) 
                             else [self.smtp_config['to_emails']])
        msg['Subject'] = f"[{alert.priority.value.upper()}] {alert.title}"
        
        # 텍스트 버전
        text_content = self._format_text_email(alert)
        text_part = MimeText(text_content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # HTML 버전
        html_content = self._format_html_email(alert)
        html_part = MimeText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        return msg
    
    def _format_text_email(self, alert: AlertMessage) -> str:
        """텍스트 이메일 포맷팅"""
        content = f"""
{alert.title}

Message: {alert.message}
Component: {alert.source_component}
Priority: {alert.priority.value.upper()}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Alert Type: {alert.alert_type.value}
"""
        
        if alert.context:
            content += "\nAdditional Information:\n"
            for key, value in alert.context.items():
                content += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        content += "\n---\nInfluence Item Auto Recovery System"
        
        return content
    
    def _format_html_email(self, alert: AlertMessage) -> str:
        """HTML 이메일 포맷팅"""
        priority_colors = {
            AlertPriority.EMERGENCY: "#FF0000",
            AlertPriority.CRITICAL: "#FF4500",
            AlertPriority.HIGH: "#FFA500",
            AlertPriority.MEDIUM: "#FFFF00",
            AlertPriority.LOW: "#00FF00"
        }
        
        color = priority_colors.get(alert.priority, "#CCCCCC")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: {color}; padding: 15px; border-radius: 5px; }}
        .content {{ margin: 20px 0; }}
        .info-table {{ border-collapse: collapse; width: 100%; }}
        .info-table th, .info-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .info-table th {{ background-color: #f2f2f2; }}
        .footer {{ margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>{alert.title}</h2>
    </div>
    
    <div class="content">
        <p><strong>Message:</strong> {alert.message}</p>
        
        <table class="info-table">
            <tr><th>Property</th><th>Value</th></tr>
            <tr><td>Component</td><td>{alert.source_component}</td></tr>
            <tr><td>Priority</td><td>{alert.priority.value.upper()}</td></tr>
            <tr><td>Alert Type</td><td>{alert.alert_type.value}</td></tr>
            <tr><td>Time</td><td>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
"""
        
        if alert.context:
            html += """
        <h3>Additional Information</h3>
        <table class="info-table">
"""
            for key, value in alert.context.items():
                html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value}</td></tr>"
            html += "</table>"
        
        html += """
    </div>
    
    <div class="footer">
        <p>This message was sent by the Influence Item Auto Recovery System.</p>
    </div>
</body>
</html>
"""
        
        return html


class SMSNotifier:
    """SMS 알림 전송 (향후 확장용)"""
    
    def __init__(self):
        self.enabled = False  # 현재 비활성화
    
    async def send(self, alert: AlertMessage) -> AlertDelivery:
        """SMS 전송 (향후 구현)"""
        return AlertDelivery(
            channel=AlertChannel.SMS,
            success=False,
            message="SMS notifications not implemented yet",
            timestamp=datetime.now()
        )


class WebhookNotifier:
    """Webhook 알림 전송"""
    
    def __init__(self):
        self.webhook_urls = self._get_webhook_urls()
        self.enabled = bool(self.webhook_urls)
    
    def _get_webhook_urls(self) -> List[str]:
        """설정에서 Webhook URL 목록 조회"""
        try:
            config = Config()
            urls = getattr(config, 'ALERT_WEBHOOK_URLS', [])
            return urls if isinstance(urls, list) else [urls] if urls else []
        except Exception:
            return []
    
    async def send(self, alert: AlertMessage) -> AlertDelivery:
        """Webhook 전송"""
        start_time = time.time()
        
        if not self.enabled:
            return AlertDelivery(
                channel=AlertChannel.WEBHOOK,
                success=False,
                message="No webhook URLs configured",
                timestamp=datetime.now()
            )
        
        try:
            # 모든 Webhook에 전송
            results = []
            for url in self.webhook_urls:
                try:
                    response = requests.post(
                        url,
                        json=alert.to_dict(),
                        timeout=30
                    )
                    results.append(response.status_code == 200)
                except Exception:
                    results.append(False)
            
            response_time = (time.time() - start_time) * 1000
            success_count = sum(results)
            
            return AlertDelivery(
                channel=AlertChannel.WEBHOOK,
                success=success_count > 0,
                message=f"Webhooks sent: {success_count}/{len(self.webhook_urls)} successful",
                timestamp=datetime.now(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return AlertDelivery(
                channel=AlertChannel.WEBHOOK,
                success=False,
                message=f"Webhook send failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=response_time,
                error_details=str(e)
            )


class AlertManager:
    """다채널 알림 관리자"""
    
    def __init__(self, alert_db: str = "alert_system.db"):
        """
        Args:
            alert_db: 알림 시스템 데이터베이스 파일
        """
        self.alert_db = Path(alert_db)
        self.alert_db.parent.mkdir(exist_ok=True)
        
        # 채널별 알림기 초기화
        self.notifiers = {
            AlertChannel.SLACK: SlackNotifier(),
            AlertChannel.EMAIL: EmailNotifier(),
            AlertChannel.SMS: SMSNotifier(),
            AlertChannel.WEBHOOK: WebhookNotifier()
        }
        
        # 우선순위별 채널 매핑
        self.priority_channels = {
            AlertPriority.EMERGENCY: [AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.SMS],
            AlertPriority.CRITICAL: [AlertChannel.SLACK, AlertChannel.EMAIL],
            AlertPriority.HIGH: [AlertChannel.SLACK, AlertChannel.EMAIL],
            AlertPriority.MEDIUM: [AlertChannel.SLACK],
            AlertPriority.LOW: [AlertChannel.LOG]
        }
        
        # 쿨다운 설정 (같은 유형의 알림 반복 방지)
        self.cooldown_periods = {
            AlertType.FAILURE_DETECTED: 300,    # 5분
            AlertType.RECOVERY_FAILED: 600,     # 10분
            AlertType.ESCALATION: 60,           # 1분
            AlertType.RECOVERY_SUCCESS: 60,     # 1분
            AlertType.SYSTEM_STATUS: 1800,      # 30분
            AlertType.MAINTENANCE: 3600         # 1시간
        }
        
        # 최근 알림 추적 (쿨다운용)
        self.recent_alerts = {}
        
        # 데이터베이스 초기화
        self._init_database()
    
    def _init_database(self):
        """알림 시스템 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.alert_db)
            cursor = conn.cursor()
            
            # 알림 메시지 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source_component TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    context TEXT,
                    channels TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 알림 전송 로그 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_message_id INTEGER,
                    channel TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    response_time_ms REAL,
                    error_details TEXT,
                    FOREIGN KEY (alert_message_id) REFERENCES alert_messages (id)
                )
            ''')
            
            # 알림 통계 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_statistics (
                    date TEXT PRIMARY KEY,
                    total_alerts INTEGER DEFAULT 0,
                    emergency_alerts INTEGER DEFAULT 0,
                    critical_alerts INTEGER DEFAULT 0,
                    high_alerts INTEGER DEFAULT 0,
                    medium_alerts INTEGER DEFAULT 0,
                    low_alerts INTEGER DEFAULT 0,
                    successful_deliveries INTEGER DEFAULT 0,
                    failed_deliveries INTEGER DEFAULT 0
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Alert system database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize alert database: {e}")
            raise
    
    async def send_alert(
        self, 
        alert_type: AlertType,
        title: str,
        message: str,
        source_component: str,
        priority: Optional[AlertPriority] = None,
        channels: Optional[List[AlertChannel]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[AlertDelivery]:
        """
        알림 전송
        
        Args:
            alert_type: 알림 유형
            title: 알림 제목
            message: 알림 메시지
            source_component: 소스 컴포넌트
            priority: 우선순위 (자동 결정 가능)
            channels: 전송 채널 목록 (자동 결정 가능)
            context: 추가 컨텍스트 정보
            
        Returns:
            전송 결과 목록
        """
        try:
            # 우선순위 자동 결정
            if priority is None:
                priority = self._determine_priority(alert_type, context)
            
            # 채널 자동 결정
            if channels is None:
                channels = self.priority_channels.get(priority, [AlertChannel.LOG])
            
            # 알림 메시지 생성
            alert = AlertMessage(
                alert_type=alert_type,
                priority=priority,
                title=title,
                message=message,
                timestamp=datetime.now(),
                source_component=source_component,
                channels=channels,
                context=context or {}
            )
            
            # 쿨다운 확인
            if not self._check_cooldown(alert):
                logger.debug(f"Alert skipped due to cooldown: {alert_type.value}")
                return []
            
            # 데이터베이스에 저장
            alert_id = self._save_alert_message(alert)
            
            # 각 채널로 전송
            deliveries = []
            for channel in channels:
                try:
                    notifier = self.notifiers.get(channel)
                    if notifier and getattr(notifier, 'enabled', True):
                        delivery = await notifier.send(alert)
                        deliveries.append(delivery)
                        
                        # 전송 로그 저장
                        self._save_delivery_log(alert_id, delivery)
                        
                    else:
                        # 비활성화된 채널
                        delivery = AlertDelivery(
                            channel=channel,
                            success=False,
                            message="Channel not enabled or configured",
                            timestamp=datetime.now()
                        )
                        deliveries.append(delivery)
                        self._save_delivery_log(alert_id, delivery)
                        
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")
                    delivery = AlertDelivery(
                        channel=channel,
                        success=False,
                        message=f"Send error: {str(e)}",
                        timestamp=datetime.now(),
                        error_details=str(e)
                    )
                    deliveries.append(delivery)
                    self._save_delivery_log(alert_id, delivery)
            
            # 로그 채널 처리
            if AlertChannel.LOG in channels:
                self._log_alert(alert)
            
            # 쿨다운 업데이트
            self._update_cooldown(alert)
            
            # 성공/실패 통계
            successful = sum(1 for d in deliveries if d.success)
            failed = len(deliveries) - successful
            
            logger.info(f"Alert sent: {alert_type.value} - {successful}/{len(deliveries)} successful")
            
            return deliveries
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return []
    
    def _determine_priority(self, alert_type: AlertType, context: Optional[Dict[str, Any]]) -> AlertPriority:
        """알림 유형에 따른 우선순위 자동 결정"""
        if alert_type == AlertType.ESCALATION:
            return AlertPriority.CRITICAL
        elif alert_type == AlertType.FAILURE_DETECTED:
            # 컨텍스트에서 심각도 확인
            if context and 'severity' in context:
                severity = context['severity']
                if severity == 'critical':
                    return AlertPriority.CRITICAL
                elif severity == 'high':
                    return AlertPriority.HIGH
                elif severity == 'medium':
                    return AlertPriority.MEDIUM
                else:
                    return AlertPriority.LOW
            return AlertPriority.MEDIUM
        elif alert_type == AlertType.RECOVERY_FAILED:
            return AlertPriority.HIGH
        elif alert_type == AlertType.RECOVERY_SUCCESS:
            return AlertPriority.LOW
        elif alert_type == AlertType.SYSTEM_STATUS:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.MEDIUM
    
    def _check_cooldown(self, alert: AlertMessage) -> bool:
        """쿨다운 확인"""
        cooldown_key = f"{alert.alert_type.value}:{alert.source_component}"
        cooldown_period = self.cooldown_periods.get(alert.alert_type, 300)
        
        last_time = self.recent_alerts.get(cooldown_key, 0)
        current_time = time.time()
        
        return (current_time - last_time) >= cooldown_period
    
    def _update_cooldown(self, alert: AlertMessage):
        """쿨다운 업데이트"""
        cooldown_key = f"{alert.alert_type.value}:{alert.source_component}"
        self.recent_alerts[cooldown_key] = time.time()
    
    def _save_alert_message(self, alert: AlertMessage) -> int:
        """알림 메시지 저장"""
        try:
            conn = sqlite3.connect(self.alert_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO alert_messages 
                (alert_type, priority, title, message, source_component, timestamp, context, channels)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.alert_type.value,
                alert.priority.value,
                alert.title,
                alert.message,
                alert.source_component,
                alert.timestamp.isoformat(),
                json.dumps(alert.context, ensure_ascii=False),
                json.dumps([ch.value for ch in alert.channels], ensure_ascii=False)
            ))
            
            alert_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return alert_id
            
        except Exception as e:
            logger.error(f"Failed to save alert message: {e}")
            return 0
    
    def _save_delivery_log(self, alert_id: int, delivery: AlertDelivery):
        """전송 로그 저장"""
        try:
            conn = sqlite3.connect(self.alert_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO alert_deliveries 
                (alert_message_id, channel, success, message, timestamp, response_time_ms, error_details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert_id,
                delivery.channel.value,
                delivery.success,
                delivery.message,
                delivery.timestamp.isoformat(),
                delivery.response_time_ms,
                delivery.error_details
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save delivery log: {e}")
    
    def _log_alert(self, alert: AlertMessage):
        """로그로 알림 기록"""
        log_level = {
            AlertPriority.EMERGENCY: logging.CRITICAL,
            AlertPriority.CRITICAL: logging.CRITICAL,
            AlertPriority.HIGH: logging.ERROR,
            AlertPriority.MEDIUM: logging.WARNING,
            AlertPriority.LOW: logging.INFO
        }.get(alert.priority, logging.INFO)
        
        log_message = f"ALERT [{alert.priority.value.upper()}] {alert.title}: {alert.message} (Component: {alert.source_component})"
        logger.log(log_level, log_message)
    
    # 편의 메서드들
    async def send_failure_alert(self, failure: FailureEvent) -> List[AlertDelivery]:
        """장애 알림 전송"""
        return await self.send_alert(
            alert_type=AlertType.FAILURE_DETECTED,
            title=f"System Failure Detected: {failure.component}",
            message=failure.message,
            source_component=failure.component,
            context={
                'failure_type': failure.failure_type.value,
                'severity': failure.severity.value,
                'timestamp': failure.timestamp.isoformat(),
                **failure.context
            }
        )
    
    async def send_recovery_success_alert(self, session: RecoverySession) -> List[AlertDelivery]:
        """복구 성공 알림 전송"""
        return await self.send_alert(
            alert_type=AlertType.RECOVERY_SUCCESS,
            title=f"Recovery Successful: {session.failure_event.component}",
            message=f"System has been successfully recovered after {session.total_attempts} attempts",
            source_component=session.failure_event.component,
            priority=AlertPriority.LOW,
            context={
                'session_id': session.session_id,
                'recovery_attempts': session.total_attempts,
                'recovery_time_minutes': (session.end_time - session.start_time).total_seconds() / 60 if session.end_time else 0
            }
        )
    
    async def send_escalation_alert(self, session: RecoverySession) -> List[AlertDelivery]:
        """에스컬레이션 알림 전송"""
        return await self.send_alert(
            alert_type=AlertType.ESCALATION,
            title=f"ESCALATION REQUIRED: {session.failure_event.component}",
            message=f"Automatic recovery failed. Manual intervention required. Reason: {session.escalation_reason}",
            source_component=session.failure_event.component,
            priority=AlertPriority.CRITICAL,
            context={
                'session_id': session.session_id,
                'escalation_reason': session.escalation_reason,
                'recovery_attempts': session.total_attempts,
                'failure_type': session.failure_event.failure_type.value
            }
        )
    
    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """알림 통계 조회"""
        try:
            conn = sqlite3.connect(self.alert_db)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 기간별 알림 통계
            cursor.execute('''
                SELECT 
                    priority,
                    alert_type,
                    COUNT(*) as count
                FROM alert_messages 
                WHERE timestamp >= ?
                GROUP BY priority, alert_type
                ORDER BY count DESC
            ''', (cutoff_date,))
            
            alert_breakdown = []
            for row in cursor.fetchall():
                alert_breakdown.append({
                    'priority': row[0],
                    'alert_type': row[1],
                    'count': row[2]
                })
            
            # 채널별 성공률
            cursor.execute('''
                SELECT 
                    d.channel,
                    COUNT(*) as total_attempts,
                    COUNT(CASE WHEN d.success = 1 THEN 1 END) as successful_attempts,
                    AVG(d.response_time_ms) as avg_response_time
                FROM alert_deliveries d
                JOIN alert_messages a ON d.alert_message_id = a.id
                WHERE a.timestamp >= ?
                GROUP BY d.channel
            ''', (cutoff_date,))
            
            channel_stats = []
            for row in cursor.fetchall():
                success_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
                channel_stats.append({
                    'channel': row[0],
                    'total_attempts': row[1],
                    'successful_attempts': row[2],
                    'success_rate': round(success_rate, 2),
                    'avg_response_time_ms': round(row[3], 2) if row[3] else 0
                })
            
            conn.close()
            
            return {
                'period_days': days,
                'alert_breakdown': alert_breakdown,
                'channel_statistics': channel_stats,
                'total_alerts': sum(item['count'] for item in alert_breakdown)
            }
            
        except Exception as e:
            logger.error(f"Failed to get alert statistics: {e}")
            return {'error': str(e)}


# 전역 알림 관리자 인스턴스
_alert_manager = None


def get_alert_manager() -> AlertManager:
    """싱글톤 알림 관리자 반환"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager