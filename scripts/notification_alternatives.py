#!/usr/bin/env python3
"""
Slack 대신 사용할 수 있는 알림 방법들
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import subprocess
import requests

class NotificationManager:
    """다양한 알림 방법을 제공하는 매니저"""
    
    def __init__(self):
        self.methods = {
            'desktop': self.send_desktop_notification,
            'email': self.send_email_notification,
            'file': self.save_to_file,
            'discord': self.send_discord_webhook,
            'telegram': self.send_telegram_message,
            'console': self.print_to_console
        }
    
    def send_notification(self, title, message, method='console', **kwargs):
        """지정된 방법으로 알림 전송"""
        
        if method in self.methods:
            return self.methods[method](title, message, **kwargs)
        else:
            print(f"❌ 지원되지 않는 알림 방법: {method}")
            return False
    
    def send_desktop_notification(self, title, message, **kwargs):
        """macOS 데스크톱 알림"""
        try:
            # macOS osascript 사용
            script = f'''
            display notification "{message}" with title "{title}" sound name "Ping"
            '''
            subprocess.run(['osascript', '-e', script], check=True)
            print(f"✅ 데스크톱 알림 전송 완료: {title}")
            return True
        except Exception as e:
            print(f"❌ 데스크톱 알림 실패: {str(e)}")
            return False
    
    def send_email_notification(self, title, message, **kwargs):
        """Gmail을 통한 이메일 알림"""
        
        # 환경변수에서 설정 읽기
        gmail_email = os.getenv('GMAIL_EMAIL')
        gmail_password = os.getenv('GMAIL_APP_PASSWORD')  # 앱 비밀번호 사용
        recipient = kwargs.get('recipient', gmail_email)
        
        if not gmail_email or not gmail_password:
            print("❌ Gmail 설정이 필요합니다. (.env 파일에 GMAIL_EMAIL, GMAIL_APP_PASSWORD 추가)")
            return False
        
        try:
            # 이메일 구성
            msg = MIMEMultipart()
            msg['From'] = gmail_email
            msg['To'] = recipient
            msg['Subject'] = f"[채널 디스커버리] {title}"
            
            # HTML 메시지 생성
            html_message = f"""
            <html>
            <body>
                <h2>🤖 채널 디스커버리 알림</h2>
                <h3>{title}</h3>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">
                    <pre>{message}</pre>
                </div>
                <p><small>📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_message, 'html'))
            
            # Gmail SMTP 서버 연결
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(gmail_email, gmail_password)
            server.send_message(msg)
            server.quit()
            
            print(f"✅ 이메일 알림 전송 완료: {recipient}")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 전송 실패: {str(e)}")
            return False
    
    def save_to_file(self, title, message, **kwargs):
        """파일로 알림 저장"""
        
        filename = kwargs.get('filename', 'notifications.log')
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"[{timestamp}] {title}\n{message}\n{'='*50}\n\n"
            
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            print(f"✅ 파일 알림 저장 완료: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ 파일 저장 실패: {str(e)}")
            return False
    
    def send_discord_webhook(self, title, message, **kwargs):
        """Discord 웹훅 알림"""
        
        webhook_url = kwargs.get('webhook_url') or os.getenv('DISCORD_WEBHOOK_URL')
        
        if not webhook_url:
            print("❌ Discord 웹훅 URL이 필요합니다.")
            return False
        
        try:
            payload = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": 0x00ff00,  # 녹색
                    "timestamp": datetime.now().isoformat(),
                    "footer": {
                        "text": "Channel Discovery Bot"
                    }
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 204:
                print("✅ Discord 알림 전송 완료")
                return True
            else:
                print(f"❌ Discord 알림 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Discord 알림 실패: {str(e)}")
            return False
    
    def send_telegram_message(self, title, message, **kwargs):
        """Telegram 봇 알림"""
        
        bot_token = kwargs.get('bot_token') or os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = kwargs.get('chat_id') or os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            print("❌ Telegram 설정이 필요합니다. (BOT_TOKEN, CHAT_ID)")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": f"🤖 *{title}*\n\n{message}",
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print("✅ Telegram 알림 전송 완료")
                return True
            else:
                print(f"❌ Telegram 알림 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Telegram 알림 실패: {str(e)}")
            return False
    
    def print_to_console(self, title, message, **kwargs):
        """콘솔 출력"""
        
        print("\n" + "="*60)
        print(f"📢 {title}")
        print("="*60)
        print(message)
        print("="*60)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")
        return True

# 사용 예시
def test_all_notifications():
    """모든 알림 방법 테스트"""
    
    notifier = NotificationManager()
    
    title = "채널 디스커버리 테스트"
    message = """
🎉 채널 탐색 완료!
• 실행 시간: 1.9초
• 발견된 후보: 6개
• 고득점 후보: 3개

🏆 상위 후보들:
• 뷰티라이프 (65.4점, 97.6K 구독자)
• 딩고 뷰티 (61.9점, 351K 구독자)
• 아이유 에델바이스 (59.4점, 437K 구독자)
    """
    
    print("🔔 알림 방법 테스트 시작...")
    
    # 1. 콘솔 출력 (항상 동작)
    notifier.send_notification(title, message, method='console')
    
    # 2. 데스크톱 알림 (macOS)
    notifier.send_notification(title, "채널 6개 발견!", method='desktop')
    
    # 3. 파일 저장
    notifier.send_notification(title, message, method='file', 
                             filename='channel_discovery_notifications.log')
    
    # 4. 이메일 (설정된 경우)
    if os.getenv('GMAIL_EMAIL'):
        notifier.send_notification(title, message, method='email')
    
    print("✅ 알림 테스트 완료!")

if __name__ == "__main__":
    test_all_notifications()