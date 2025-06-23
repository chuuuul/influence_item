#!/usr/bin/env python3
"""
YOLO 작업 완료 이메일 발송 스크립트
"""

import os
import sys
import resend
from datetime import datetime

def send_yolo_completion_email():
    """YOLO 작업 완료 이메일 발송"""
    
    # Resend API 키 설정 (환경변수에서 읽기)
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        print("RESEND_API_KEY 환경변수가 설정되지 않았습니다.")
        return False
    
    resend.api_key = api_key
    
    # YOLO 완료 보고서 읽기
    try:
        with open('/Users/chul/Documents/claude/influence_item/yolo_t10_completion_report.md', 'r', encoding='utf-8') as f:
            report_content = f.read()
    except FileNotFoundError:
        try:
            with open('/Users/chul/Documents/claude/influence_item/yolo_completion_report.md', 'r', encoding='utf-8') as f:
                report_content = f.read()
        except FileNotFoundError:
            print("YOLO 완료 보고서 파일을 찾을 수 없습니다.")
            return False
    
    # 이메일 내용 구성
    subject = "influence_item yolo 작업완료 (by memory)"
    
    # HTML 형식으로 변환
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
            .content {{ background-color: #fff; padding: 20px; }}
            .report {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #007cba; margin: 20px 0; }}
            pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }}
            .timestamp {{ color: #666; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🎯 YOLO 작업 완료 알림</h2>
            <p class="timestamp">발송 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="content">
            <p>이 메일은 메모리에 의해서 전송된 메일입니다.</p>
            
            <div class="report">
                <h3>📋 YOLO에서 출력된 보고서 내용:</h3>
                <pre>{report_content}</pre>
            </div>
            
            <hr>
            <p><small>자동 생성된 이메일입니다. - influence_item 프로젝트</small></p>
        </div>
    </body>
    </html>
    """
    
    # 이메일 발송 파라미터
    params = {
        "from": "Claude YOLO <onboarding@resend.dev>",
        "to": ["rlacjf310@gmail.com"],
        "subject": subject,
        "html": html_content,
    }
    
    try:
        # 이메일 발송
        email = resend.Emails.send(params)
        print(f"✅ YOLO 작업 완료 이메일이 성공적으로 발송되었습니다.")
        print(f"📧 이메일 ID: {email.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"❌ 이메일 발송 중 오류가 발생했습니다: {str(e)}")
        return False

if __name__ == "__main__":
    # 환경변수 체크
    if not os.environ.get('RESEND_API_KEY'):
        print("⚠️  RESEND_API_KEY 환경변수를 설정해주세요.")
        print("예시: export RESEND_API_KEY='re_xxxxxxxxxx'")
        sys.exit(1)
    
    # 이메일 발송 실행
    success = send_yolo_completion_email()
    
    if success:
        print("\n🎉 YOLO 작업 완료 이메일 발송이 완료되었습니다!")
    else:
        print("\n❌ 이메일 발송에 실패했습니다.")
        sys.exit(1)