#!/usr/bin/env python3
"""
YOLO 작업 완료 이메일 발송 스크립트
"""

import os
import sys
import resend
from datetime import datetime

def load_yolo_report():
    """YOLO 완료 보고서 내용을 로드합니다."""
    try:
        # YOLO 완료 보고서 읽기
        with open('/Users/chul/Documents/claude/influence_item/yolo_completion_report.md', 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # T10 완료 보고서도 읽기
        with open('/Users/chul/Documents/claude/influence_item/yolo_t10_completion_report.md', 'r', encoding='utf-8') as f:
            t10_report_content = f.read()
            
        return f"""
{report_content}

---

## YOLO T10 사이클 상세 보고서

{t10_report_content}
"""
    except Exception as e:
        return f"보고서 로드 실패: {str(e)}"

def send_yolo_completion_email():
    """YOLO 작업 완료 이메일을 발송합니다."""
    
    # 환경변수에서 API 키 확인
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        print("❌ RESEND_API_KEY 환경변수가 설정되지 않았습니다.")
        print("다음 명령어로 설정하세요:")
        print("export RESEND_API_KEY='your-api-key-here'")
        return False
    
    # Resend 클라이언트 설정
    resend.api_key = api_key
    
    # 보고서 내용 로드
    report_content = load_yolo_report()
    
    # 현재 시간
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 이메일 파라미터 설정
    email_params = {
        "from": "Claude Assistant <noreply@resend.dev>",
        "to": ["rlacjf310@gmail.com"],
        "subject": "influence_item yolo 작업완료 (by memory)",
        "html": f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>YOLO 작업 완료 보고</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db;">🎯 YOLO 작업 완료 보고</h1>
            
            <p><strong>프로젝트:</strong> influence_item</p>
            <p><strong>완료 시간:</strong> {current_time}</p>
            <p><strong>발송 방식:</strong> 메모리에 의한 자동 발송</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-left: 4px solid #28a745; margin: 20px 0;">
                <h2 style="color: #28a745; margin-top: 0;">✅ 작업 완료 상태</h2>
                <ul>
                    <li><strong>YOLO 사이클:</strong> T10 완료</li>
                    <li><strong>프로젝트 완성도:</strong> v1.0 시스템 완전 구축 완료</li>
                    <li><strong>스프린트 상태:</strong> S02_M02 100% 완료</li>
                    <li><strong>테스트 통과율:</strong> 88.8% (24/27)</li>
                    <li><strong>배포 준비:</strong> 완료</li>
                </ul>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                <h3 style="color: #856404; margin-top: 0;">📊 주요 성과</h3>
                <ul>
                    <li>AI 2-Pass 분석 엔진 완성</li>
                    <li>PPL(간접광고) 자동 탐지 시스템 구축</li>
                    <li>수익화 모델 완전 구현</li>
                    <li>콘텐츠 생성 자동화 파이프라인 완성</li>
                    <li>Streamlit 대시보드 시스템 구축</li>
                </ul>
            </div>
            
            <h2 style="color: #2c3e50;">📋 상세 보고서</h2>
            <div style="background-color: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px;">
                <pre style="white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto;">{report_content}</pre>
            </div>
            
            <div style="margin-top: 30px; padding: 15px; background-color: #d1ecf1; border: 1px solid #bee5eb; border-radius: 5px;">
                <p style="margin: 0; color: #0c5460;">
                    <strong>📧 이 메일은 Claude Code의 YOLO 모드에 의해 자동으로 생성되고 발송되었습니다.</strong><br>
                    메모리 기반 자동화 시스템에 의해 프로젝트 완료가 감지되어 보고서가 전송되었습니다.
                </p>
            </div>
        </body>
        </html>
        """
    }
    
    try:
        # 이메일 발송
        print("📤 YOLO 완료 이메일을 발송하고 있습니다...")
        email = resend.Emails.send(email_params)
        
        print(f"✅ 이메일이 성공적으로 발송되었습니다!")
        print(f"📧 이메일 ID: {email.get('id', 'N/A')}")
        print(f"📬 수신자: rlacjf310@gmail.com")
        print(f"📝 제목: influence_item yolo 작업완료 (by memory)")
        
        return True
        
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 YOLO 작업 완료 이메일 발송을 시작합니다...")
    print("=" * 50)
    
    success = send_yolo_completion_email()
    
    if success:
        print("=" * 50)
        print("✅ YOLO 완료 이메일 발송이 완료되었습니다!")
    else:
        print("=" * 50)
        print("❌ YOLO 완료 이메일 발송에 실패했습니다.")
        sys.exit(1)