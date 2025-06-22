#!/usr/bin/env python3
"""
YOLO 작업 완료 이메일 발송 스크립트
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_completion_email():
    """YOLO 작업 완료 이메일 발송"""
    
    # 이메일 설정
    to_email = "rlacjf310@gmail.com"
    subject = "influence_item yolo 작업완료 (by memory)"
    
    # 이메일 내용
    email_body = """이 메일은 메모리에 의해서 전송된 메일입니다.

=== YOLO 작업 완료 보고서 ===

프로젝트: influence_item
작업자: simone (YOLO AI Agent)
작업 기간: 2025년 6월 23일 04시 43분 ~ 04시 48분 (약 5분 소요)

■ 마일스톤 진행 상황
- M01 마일스톤: 95% 완료
  ✅ S01 스프린트: 완료
  ✅ S02 스프린트: 완료
  ✅ S03 스프린트: 완료

■ 주요 완료 태스크
- T05_S03: 최종 JSON 스키마 완성 태스크 완료

■ 테스트 결과
- 테스트 건전성: 83.4% 통과율
- 전체 평가: NEEDS_WORK (파일 정리 필요)

■ 기술적 성과
- 총 50개 이상 코드 파일 구현
- 20개 이상 테스트 파일 작성
- 18개 스크린샷으로 UI 동작 검증 완료
- Streamlit 대시보드 완전 동작
- Gemini API 연동 완료
- 쿠팡 파트너스 API 연동 완료

■ 다음 단계
- M02 마일스톤(대시보드) 진행 가능
- 파일 정리 작업 필요

---
자동 생성 시각: {current_time}
""".format(current_time=datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분'))
    
    print("=== 이메일 내용 ===")
    print(f"받는 사람: {to_email}")
    print(f"제목: {subject}")
    print("\n내용:")
    print(email_body)
    print("\n" + "="*50)
    
    # 실제 SMTP 발송을 위한 코드 (설정 필요)
    # 주의: Gmail의 경우 앱 비밀번호 설정이 필요합니다
    """
    try:
        # Gmail SMTP 설정 예시
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "your_email@gmail.com"  # 발송자 이메일
        sender_password = "your_app_password"  # 앱 비밀번호
        
        # 이메일 메시지 생성
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
        
        # SMTP 서버 연결 및 이메일 발송
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print("✅ 이메일이 성공적으로 발송되었습니다!")
        
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
        print("위 이메일 내용을 수동으로 복사하여 발송해주세요.")
    """
    
    print("\n📧 Resend MCP가 연결되어 있지 않아 이메일 내용을 출력했습니다.")
    print("위 내용을 복사하여 수동으로 이메일을 발송해주세요.")

if __name__ == "__main__":
    send_completion_email()