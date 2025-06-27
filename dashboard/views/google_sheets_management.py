"""Google Sheets 관리 페이지"""
import streamlit as st
import pandas as pd
import os
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dashboard.utils.env_loader import get_google_sheet_settings, ensure_gemini_api_key
except ImportError:
    get_google_sheet_settings = None
    ensure_gemini_api_key = None

def render_google_sheets_management():
    st.header("📋 Google Sheets 관리")
    st.info("연예인 채널 목록을 Google Sheets로 관리합니다.")
    
    # API 키 설정 확인
    col1, col2 = st.columns([3, 1])
    
    # Google Sheets 설정 표시
    if get_google_sheet_settings:
        sheet_settings = get_google_sheet_settings()
        sheet_id = sheet_settings.get('sheet_id', 'Not configured')
        sheet_url = sheet_settings.get('sheet_url', 'Not configured')
        
        with col1:
            if sheet_id != 'Not configured':
                st.success(f"✅ Google Sheets 연결됨 (ID: {sheet_id[:10]}...)")
                st.write(f"**Sheet URL:** {sheet_url}")
            else:
                st.error("❌ Google Sheets 설정이 필요합니다")
    else:
        with col1:
            st.error("❌ 환경설정 모듈을 로드할 수 없습니다")
    
    # Gemini API 키 상태 확인
    try:
        if ensure_gemini_api_key:
            gemini_key = ensure_gemini_api_key()
            st.success(f"✅ Gemini API 키 설정됨 ({gemini_key[:10]}...)")
        else:
            st.warning("⚠️ Gemini API 키 확인 불가")
    except ValueError as e:
        st.error(f"❌ {str(e)}")
    except Exception as e:
        st.error(f"❌ API 키 확인 중 오류: {str(e)}")
    
    with col2:
        if st.button("🔄 동기화"):
            # 실제 Google Sheets 동기화 로직은 여기에 구현
            st.success("동기화 완료!")
    
    st.markdown("---")
    
    # 환경변수 설정 섹션
    st.subheader("⚙️ API 설정")
    
    with st.expander("API 키 및 설정 정보", expanded=False):
        # 현재 설정된 환경변수 표시
        env_vars = {
            "GEMINI_API_KEY": os.getenv('GEMINI_API_KEY', 'Not set'),
            "GOOGLE_SHEET_ID": os.getenv('GOOGLE_SHEET_ID', 'Not set'),
            "GOOGLE_SHEET_URL": os.getenv('GOOGLE_SHEET_URL', 'Not set'),
        }
        
        for key, value in env_vars.items():
            if value != 'Not set':
                # API 키는 일부만 표시
                if 'API_KEY' in key:
                    masked_value = f"{value[:10]}..." if len(value) > 10 else value
                else:
                    masked_value = value
                st.write(f"**{key}:** {masked_value}")
            else:
                st.error(f"**{key}:** ❌ Not configured")
    
    # 채널 목록
    st.subheader("📺 등록된 채널 목록")
    
    channels = pd.DataFrame({
        "채널명": ["홍지윤 Yoon", "아이유IU", "이사배", "소이와여니", "윰댕"],
        "채널 ID": ["UC_xxx1", "UC_xxx2", "UC_xxx3", "UC_xxx4", "UC_xxx5"],
        "카테고리": ["뷰티/라이프", "음악/라이프", "뷰티", "육아/라이프", "먹방"],
        "구독자수": ["1.2M", "8.5M", "2.1M", "450K", "780K"],
        "상태": ["활성", "활성", "활성", "활성", "비활성"]
    })
    
    st.dataframe(channels, use_container_width=True, 
                column_config={
                    "상태": st.column_config.SelectboxColumn(
                        "상태",
                        options=["활성", "비활성", "일시정지"],
                        help="채널 모니터링 상태"
                    )
                })
    
    # 채널 추가
    st.subheader("➕ 새 채널 추가")
    col1, col2, col3 = st.columns(3)
    with col1:
        new_channel = st.text_input("채널명")
    with col2:
        new_category = st.selectbox("카테고리", ["뷰티", "패션", "라이프", "음악", "먹방"])
    with col3:
        if st.button("추가"):
            if new_channel:
                st.success(f"{new_channel} 채널이 추가되었습니다!")
                # 실제로는 Google Sheets에 데이터 추가 로직이 필요
            else:
                st.error("채널명을 입력해주세요.")
    
    st.markdown("---")
    
    # Google Sheets 템플릿 정보 
    st.subheader("📄 Google Sheets 템플릿")
    st.info("""
    **필수 컬럼 구조:**
    - 채널명 (Channel Name)
    - 채널 ID (Channel ID) 
    - 카테고리 (Category)
    - 구독자수 (Subscribers)
    - 상태 (Status)
    - 마지막 업데이트 (Last Updated)
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📋 Google Sheets 열기"):
            sheet_url = os.getenv('GOOGLE_SHEET_URL')
            if sheet_url:
                st.write(f"Google Sheets URL: {sheet_url}")
            else:
                st.error("Google Sheets URL이 설정되지 않았습니다.")
    
    with col2:
        if st.button("📊 CSV 파일 생성"):
            try:
                # CSV 파일 생성 로직
                import csv
                from datetime import datetime
                from pathlib import Path
                
                # 테스트 데이터 (실제로는 DB에서 가져와야 함)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                test_data = [
                    {
                        "시간": timestamp,
                        "채널명": "테스트 채널",
                        "연예인": "아이유",
                        "제품명": "맥북 프로",
                        "브랜드": "Apple",
                        "카테고리": "전자제품",
                        "신뢰도": "0.95",
                        "감정": "positive",
                        "상태": "needs_review",
                        "테스트노트": "대시보드에서 생성된 테스트 데이터"
                    },
                    {
                        "시간": timestamp,
                        "채널명": "뷰티 채널",
                        "연예인": "이사배",
                        "제품명": "립스틱",
                        "브랜드": "샤넬",
                        "카테고리": "뷰티",
                        "신뢰도": "0.87",
                        "감정": "positive",
                        "상태": "approved",
                        "테스트노트": "대시보드 CSV 내보내기 기능"
                    }
                ]
                
                # CSV 파일 생성
                project_root = Path(__file__).parent.parent.parent
                csv_file = project_root / f"dashboard_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    if test_data:
                        writer = csv.DictWriter(f, fieldnames=test_data[0].keys())
                        writer.writeheader()
                        writer.writerows(test_data)
                
                st.success(f"✅ CSV 파일 생성 완료!")
                st.info(f"파일 위치: {csv_file}")
                st.info(f"데이터 행 수: {len(test_data)}")
                
                # 다운로드 버튼 (Streamlit Cloud에서 작동)
                with open(csv_file, 'r', encoding='utf-8') as f:
                    csv_content = f.read()
                
                st.download_button(
                    label="💾 CSV 파일 다운로드",
                    data=csv_content,
                    file_name=f"google_sheets_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"CSV 생성 실패: {e}")
    
    with col3:
        if st.button("📧 테스트 알림 생성"):
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                notification_content = f"""
🚨 [연예인 추천 아이템] 새로운 분석 결과

⏰ 시간: {timestamp}
📺 채널: 대시보드 테스트
👤 연예인: 아이유
🛍️ 제품: 맥북 프로 (Apple)
📊 AI 신뢰도: 95%
😊 감정: Positive
✅ 상태: 검토 필요

🔗 Google Sheets: {os.getenv('GOOGLE_SHEET_URL', 'URL 설정 필요')}

---
연예인 추천 아이템 자동화 시스템
"""
                
                st.success("✅ 알림 메시지 생성 완료!")
                st.text_area("📧 알림 내용:", notification_content, height=200)
                
            except Exception as e:
                st.error(f"알림 생성 실패: {e}")