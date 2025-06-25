#!/usr/bin/env python3
"""
통합 알림 관리 시스템

슬랙, 이메일, 웹훅을 통한 실시간 알림 시스템
"""

import os
import json
import time
import smtplib
import asyncio
import logging
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import requests
import aiohttp
from src.config.config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertChannel(Enum):
    """알림 채널"""
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"

@dataclass
class Alert:
    """알림 데이터 클래스"""
    title: str
    message: str
    level: AlertLevel
    service: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    channels: List[AlertChannel] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.channels is None:
            self.channels = [AlertChannel.SLACK]

class NotificationManager:
    """통합 알림 관리자"""
    
    def __init__(self):
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.email_config = {
            "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("EMAIL_USERNAME"),
            "password": os.getenv("EMAIL_PASSWORD"),
            "from_email": os.getenv("FROM_EMAIL"),
            "to_emails": os.getenv("TO_EMAILS", "").split(",") if os.getenv("TO_EMAILS") else []
        }
        self.webhook_urls = {
            "monitoring": os.getenv("MONITORING_WEBHOOK_URL"),
            "deployment": os.getenv("DEPLOYMENT_WEBHOOK_URL"),
            "security": os.getenv("SECURITY_WEBHOOK_URL")
        }
        
        # 알림 제한 설정 (스팸 방지)
        self.rate_limits = {}
        self.max_alerts_per_hour = 10
        
    def _check_rate_limit(self, alert: Alert) -> bool:
        """알림 속도 제한 확인"""
        key = f"{alert.service}:{alert.level.value}"
        now = datetime.now()
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
        
        # 1시간 이전 기록 제거
        cutoff = now - timedelta(hours=1)
        self.rate_limits[key] = [
            timestamp for timestamp in self.rate_limits[key] 
            if timestamp > cutoff
        ]
        
        # 제한 확인
        if len(self.rate_limits[key]) >= self.max_alerts_per_hour:
            logger.warning(f"알림 속도 제한 초과: {key}")
            return False
        
        self.rate_limits[key].append(now)
        return True
    
    def _get_slack_color(self, level: AlertLevel) -> str:
        """슬랙 메시지 색상 반환"""
        color_map = {
            AlertLevel.INFO: "good",
            AlertLevel.WARNING: "warning", 
            AlertLevel.ERROR: "danger",
            AlertLevel.CRITICAL: "#ff0000"
        }
        return color_map.get(level, "good")
    
    def _get_slack_emoji(self, level: AlertLevel) -> str:
        """슬랙 메시지 이모지 반환"""
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "🚨",
            AlertLevel.CRITICAL: "🔥"
        }
        return emoji_map.get(level, "ℹ️")
    
    async def send_slack_notification(self, alert: Alert) -> bool:
        """슬랙 알림 전송"""
        if not self.slack_webhook_url:
            logger.warning("슬랙 웹훅 URL이 설정되지 않음")
            return False
        
        try:
            payload = {
                "username": "Influence Item Alert",
                "icon_emoji": ":robot_face:",
                "attachments": [{
                    "color": self._get_slack_color(alert.level),
                    "title": f"{self._get_slack_emoji(alert.level)} {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "서비스",
                            "value": alert.service,
                            "short": True
                        },
                        {
                            "title": "레벨",
                            "value": alert.level.value.upper(),
                            "short": True
                        },
                        {
                            "title": "시간",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        }
                    ],
                    "footer": "Influence Item Monitoring",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            # 메타데이터 추가
            if alert.metadata:
                for key, value in alert.metadata.items():
                    payload["attachments"][0]["fields"].append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True
                    })
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"슬랙 알림 전송 성공: {alert.title}")
                        return True
                    else:
                        logger.error(f"슬랙 알림 전송 실패: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"슬랙 알림 전송 예외: {e}")
            return False
    
    async def send_email_notification(self, alert: Alert) -> bool:
        """이메일 알림 전송"""
        if not self.email_config["username"] or not self.email_config["to_emails"]:
            logger.warning("이메일 설정이 불완전함")
            return False
        
        try:
            # 이메일 내용 구성
            msg = MimeMultipart()
            msg['From'] = self.email_config["from_email"] or self.email_config["username"]
            msg['To'] = ", ".join(self.email_config["to_emails"])
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"
            
            # HTML 본문 생성
            html_body = f"""
            <html>
            <body>
                <h2 style="color: {'red' if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL] else 'orange' if alert.level == AlertLevel.WARNING else 'blue'};">
                    {self._get_slack_emoji(alert.level)} {alert.title}
                </h2>
                <p><strong>메시지:</strong> {alert.message}</p>
                <p><strong>서비스:</strong> {alert.service}</p>
                <p><strong>레벨:</strong> {alert.level.value.upper()}</p>
                <p><strong>시간:</strong> {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>
                
                {f'''
                <h3>추가 정보:</h3>
                <ul>
                    {''.join([f"<li><strong>{k.replace('_', ' ').title()}:</strong> {v}</li>" for k, v in alert.metadata.items()])}
                </ul>
                ''' if alert.metadata else ''}
                
                <hr>
                <p><small>Influence Item 모니터링 시스템에서 발송된 자동 알림입니다.</small></p>
            </body>
            </html>
            """
            
            msg.attach(MimeText(html_body, 'html'))
            
            # 이메일 전송
            with smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.starttls()
                server.login(self.email_config["username"], self.email_config["password"])
                server.send_message(msg)
            
            logger.info(f"이메일 알림 전송 성공: {alert.title}")
            return True
            
        except Exception as e:
            logger.error(f"이메일 알림 전송 예외: {e}")
            return False
    
    async def send_webhook_notification(self, alert: Alert, webhook_type: str = "monitoring") -> bool:
        """웹훅 알림 전송"""
        webhook_url = self.webhook_urls.get(webhook_type)
        if not webhook_url:
            logger.warning(f"웹훅 URL이 설정되지 않음: {webhook_type}")
            return False
        
        try:
            payload = {
                "alert": {
                    "title": alert.title,
                    "message": alert.message,
                    "level": alert.level.value,
                    "service": alert.service,
                    "timestamp": alert.timestamp.isoformat(),
                    "metadata": alert.metadata
                },
                "source": "influence-item-monitoring"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 201, 202]:
                        logger.info(f"웹훅 알림 전송 성공: {alert.title}")
                        return True
                    else:
                        logger.error(f"웹훅 알림 전송 실패: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"웹훅 알림 전송 예외: {e}")
            return False
    
    async def send_alert(self, alert: Alert) -> Dict[str, bool]:
        """알림 전송 (모든 채널)"""
        # 속도 제한 확인
        if not self._check_rate_limit(alert):
            return {"rate_limited": True}
        
        results = {}
        tasks = []
        
        for channel in alert.channels:
            if channel == AlertChannel.SLACK:
                tasks.append(("slack", self.send_slack_notification(alert)))
            elif channel == AlertChannel.EMAIL:
                tasks.append(("email", self.send_email_notification(alert)))
            elif channel == AlertChannel.WEBHOOK:
                webhook_type = alert.metadata.get("webhook_type", "monitoring")
                tasks.append(("webhook", self.send_webhook_notification(alert, webhook_type)))
        
        # 병렬 전송
        if tasks:
            task_results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
            
            for i, (channel_name, _) in enumerate(tasks):
                result = task_results[i]
                if isinstance(result, Exception):
                    logger.error(f"{channel_name} 알림 전송 예외: {result}")
                    results[channel_name] = False
                else:
                    results[channel_name] = result
        
        return results

class SystemMonitor:
    """시스템 모니터링 및 자동 알림"""
    
    def __init__(self):
        self.notification_manager = NotificationManager()
        self.last_check = {}
        
    async def check_service_health(self, service_name: str, endpoint: str) -> Dict[str, Any]:
        """서비스 헬스체크"""
        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_time = time.time() - start_time
                    
                    return {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "status_code": response.status,
                        "response_time": response_time,
                        "error": None
                    }
                    
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "status_code": None,
                "response_time": None,
                "error": "Timeout"
            }
        except Exception as e:
            return {
                "status": "error",
                "status_code": None,
                "response_time": None,
                "error": str(e)
            }
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """시스템 리소스 체크"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except ImportError:
            logger.warning("psutil이 설치되지 않음 - 시스템 리소스 모니터링 불가")
            return {}
        except Exception as e:
            logger.error(f"시스템 리소스 체크 실패: {e}")
            return {}
    
    async def monitor_services(self):
        """서비스 모니터링 루프"""
        services = {
            "gpu-server": os.getenv("GPU_SERVER_URL", "http://localhost:8001") + "/health",
            "cpu-server": os.getenv("CPU_SERVER_URL", "http://localhost:8501") + "/_stcore/health"
        }
        
        while True:
            try:
                for service_name, endpoint in services.items():
                    health = await self.check_service_health(service_name, endpoint)
                    
                    if health["status"] != "healthy":
                        alert = Alert(
                            title=f"{service_name} 서비스 이상",
                            message=f"{service_name} 서비스가 비정상 상태입니다.",
                            level=AlertLevel.ERROR,
                            service=service_name,
                            timestamp=datetime.now(),
                            metadata={
                                "status_code": health["status_code"],
                                "response_time": health["response_time"],
                                "error": health["error"],
                                "endpoint": endpoint
                            },
                            channels=[AlertChannel.SLACK, AlertChannel.EMAIL]
                        )
                        
                        await self.notification_manager.send_alert(alert)
                    
                    # 응답 시간 경고
                    elif health["response_time"] and health["response_time"] > 5.0:
                        alert = Alert(
                            title=f"{service_name} 응답 시간 지연",
                            message=f"{service_name} 서비스의 응답 시간이 느립니다.",
                            level=AlertLevel.WARNING,
                            service=service_name,
                            timestamp=datetime.now(),
                            metadata={
                                "response_time": health["response_time"],
                                "threshold": 5.0
                            },
                            channels=[AlertChannel.SLACK]
                        )
                        
                        await self.notification_manager.send_alert(alert)
                
                # 시스템 리소스 체크
                resources = await self.check_system_resources()
                if resources:
                    alerts = []
                    
                    if resources.get("cpu_percent", 0) > 80:
                        alerts.append(("CPU 사용률 높음", f"CPU 사용률: {resources['cpu_percent']}%"))
                    
                    if resources.get("memory_percent", 0) > 85:
                        alerts.append(("메모리 사용률 높음", f"메모리 사용률: {resources['memory_percent']}%"))
                    
                    if resources.get("disk_percent", 0) > 90:
                        alerts.append(("디스크 사용률 높음", f"디스크 사용률: {resources['disk_percent']}%"))
                    
                    for title, message in alerts:
                        alert = Alert(
                            title=title,
                            message=message,
                            level=AlertLevel.WARNING,
                            service="system",
                            timestamp=datetime.now(),
                            metadata=resources,
                            channels=[AlertChannel.SLACK]
                        )
                        
                        await self.notification_manager.send_alert(alert)
                
                # 다음 체크까지 대기
                await asyncio.sleep(300)  # 5분 간격
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                await asyncio.sleep(60)

# 유틸리티 함수들
async def send_info_alert(title: str, message: str, service: str = "system", **metadata):
    """정보 알림 전송"""
    manager = NotificationManager()
    alert = Alert(
        title=title,
        message=message,
        level=AlertLevel.INFO,
        service=service,
        timestamp=datetime.now(),
        metadata=metadata,
        channels=[AlertChannel.SLACK]
    )
    return await manager.send_alert(alert)

async def send_warning_alert(title: str, message: str, service: str = "system", **metadata):
    """경고 알림 전송"""
    manager = NotificationManager()
    alert = Alert(
        title=title,
        message=message,
        level=AlertLevel.WARNING,
        service=service,
        timestamp=datetime.now(),
        metadata=metadata,
        channels=[AlertChannel.SLACK]
    )
    return await manager.send_alert(alert)

async def send_error_alert(title: str, message: str, service: str = "system", **metadata):
    """오류 알림 전송"""
    manager = NotificationManager()
    alert = Alert(
        title=title,
        message=message,
        level=AlertLevel.ERROR,
        service=service,
        timestamp=datetime.now(),
        metadata=metadata,
        channels=[AlertChannel.SLACK, AlertChannel.EMAIL]
    )
    return await manager.send_alert(alert)

async def send_critical_alert(title: str, message: str, service: str = "system", **metadata):
    """치명적 알림 전송"""
    manager = NotificationManager()
    alert = Alert(
        title=title,
        message=message,
        level=AlertLevel.CRITICAL,
        service=service,
        timestamp=datetime.now(),
        metadata=metadata,
        channels=[AlertChannel.SLACK, AlertChannel.EMAIL, AlertChannel.WEBHOOK]
    )
    return await manager.send_alert(alert)

if __name__ == "__main__":
    # 테스트 실행
    async def test_notifications():
        await send_info_alert("시스템 시작", "Influence Item 시스템이 정상적으로 시작되었습니다.")
        
        # 모니터링 시작
        monitor = SystemMonitor()
        await monitor.monitor_services()
    
    asyncio.run(test_notifications())