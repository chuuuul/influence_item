#!/usr/bin/env python3
'''
자동 에러 감지 및 알림 시스템
매 5분마다 로그를 모니터링하고 에러 발생 시 Slack 알림
'''

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

def check_recent_errors():
    '''최근 에러 로그 확인'''
    log_files = [
        'logs/daily_discovery.log',
        'logs/sheets_sync.log', 
        'logs/n8n_status.log',
        'logs/monitoring.log',
        'dashboard_server.log',
        'influence_item.log'
    ]
    
    errors = []
    current_time = datetime.now()
    check_time = current_time - timedelta(minutes=10)  # 지난 10분 확인
    
    for log_file in log_files:
        if Path(log_file).exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-100:]  # 최근 100줄만 확인
                    
                for line in lines:
                    if any(keyword in line.lower() for keyword in ['error', 'exception', 'failed', 'critical']):
                        errors.append({
                            'file': log_file,
                            'message': line.strip(),
                            'timestamp': current_time.isoformat()
                        })
            except Exception:
                pass
    
    return errors

def send_error_notification(errors):
    '''Slack으로 에러 알림 전송'''
    if not errors:
        return
    
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url or 'your_' in webhook_url:
        return
    
    message = f"🚨 **Influence Item 시스템 에러 감지** ({len(errors)}건)\n\n"
    
    for error in errors[:5]:  # 최대 5개까지만 표시
        message += f"📁 **{error['file']}**\n"
        message += f"🕐 {error['timestamp']}\n"
        message += f"💬 {error['message'][:200]}\n\n"
    
    if len(errors) > 5:
        message += f"... 추가 {len(errors) - 5}개 에러\n"
    
    payload = {
        'text': message,
        'username': 'Influence Item Monitor',
        'icon_emoji': ':warning:'
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ 에러 알림 전송 완료 ({len(errors)}건)")
        else:
            print(f"❌ 에러 알림 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"❌ 에러 알림 전송 중 오류: {e}")

if __name__ == "__main__":
    errors = check_recent_errors()
    if errors:
        send_error_notification(errors)
        print(f"⚠️  {len(errors)}개의 에러가 감지되어 알림을 전송했습니다.")
    else:
        print("✅ 최근 에러가 감지되지 않았습니다.")
