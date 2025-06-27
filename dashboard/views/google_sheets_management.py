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
    from dashboard.utils.google_sheets_oauth import get_google_sheets_oauth_client, test_connection
    from dashboard.utils.google_sheets_api_key import get_google_sheets_api_key_client, test_api_key_connection
    from dashboard.utils.csv_data_manager import get_csv_data_manager, test_csv_connection
except ImportError:
    get_google_sheet_settings = None
    ensure_gemini_api_key = None
    get_google_sheets_oauth_client = None
    test_connection = None
    get_google_sheets_api_key_client = None
    test_api_key_connection = None
    get_csv_data_manager = None
    test_csv_connection = None

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
            if get_google_sheets_oauth_client:
                try:
                    client = get_google_sheets_oauth_client()
                    success = client.sync_data()
                    if success:
                        st.success("✅ 구글 시트 동기화 완료!")
                    else:
                        st.error("❌ 동기화 실패. 연결 상태를 확인해주세요.")
                except Exception as e:
                    st.error(f"❌ 동기화 중 오류: {str(e)}")
            else:
                st.error("❌ Google Sheets 클라이언트를 로드할 수 없습니다.")
    
    st.markdown("---")
    
    # 연결 테스트 섹션
    st.subheader("🔗 구글 시트 연결 테스트")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("실제 구글 시트에 연결하여 데이터를 읽고 쓸 수 있는지 테스트합니다.")
    
    with col2:
        test_method = st.selectbox("테스트 방법", ["CSV 로컬 파일", "API 키 (공개 시트)", "OAuth (인증 필요)"], key="test_method")
        
        if st.button("🧪 연결 테스트"):
            if test_method == "CSV 로컬 파일":
                if test_csv_connection:
                    test_csv_connection()
                else:
                    st.error("❌ CSV 테스트 함수를 로드할 수 없습니다.")
            elif test_method == "API 키 (공개 시트)":
                if test_api_key_connection:
                    test_api_key_connection()
                else:
                    st.error("❌ API 키 테스트 함수를 로드할 수 없습니다.")
            else:
                if test_connection:
                    test_connection()
                else:
                    st.error("❌ OAuth 테스트 함수를 로드할 수 없습니다.")
    
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
    
    # CSV 데이터 매니저를 우선으로 시도
    channels_loaded = False
    data_source = "없음"
    
    if get_csv_data_manager:
        try:
            csv_client = get_csv_data_manager()
            channels = csv_client.get_channels()
            
            if channels:
                # 채널 데이터를 테이블로 표시
                df = pd.DataFrame(channels)
                st.dataframe(df, use_container_width=True)
                st.success(f"✅ 총 {len(channels)}개의 채널이 등록되어 있습니다. (CSV 로컬 파일)")
                channels_loaded = True
                data_source = "CSV"
                
        except Exception as e:
            st.warning(f"CSV 데이터 로드 중 오류: {str(e)}")
    
    # CSV 로드 실패시 API 키 클라이언트 시도
    if not channels_loaded and get_google_sheets_api_key_client:
        try:
            api_client = get_google_sheets_api_key_client()
            channels = api_client.get_channels()
            
            if channels:
                # 채널 데이터를 테이블로 표시
                df = pd.DataFrame(channels)
                st.dataframe(df, use_container_width=True)
                st.info(f"📊 총 {len(channels)}개의 채널이 등록되어 있습니다. (Google Sheets API 키)")
                channels_loaded = True
                data_source = "Google Sheets API"
                
        except Exception as e:
            st.warning(f"Google Sheets API 키로 채널 목록을 불러오는 중 오류: {str(e)}")
            
            # OAuth 클라이언트로 최종 시도
            if get_google_sheets_oauth_client:
                try:
                    st.info("OAuth 인증으로 재시도 중...")
                    oauth_client = get_google_sheets_oauth_client()
                    channels = oauth_client.get_channels()
                    
                    if channels:
                        df = pd.DataFrame(channels)
                        st.dataframe(df, use_container_width=True)
                        st.info(f"📊 총 {len(channels)}개의 채널이 등록되어 있습니다. (Google Sheets OAuth)")
                        channels_loaded = True
                        data_source = "Google Sheets OAuth"
                        
                except Exception as oauth_e:
                    st.error(f"OAuth 연결도 실패: {str(oauth_e)}")
    
    if not channels_loaded:
        st.info("등록된 채널이 없습니다. 아래에서 새 채널을 추가해주세요.")
    
    # 채널 추가
    st.subheader("➕ 새 채널 추가")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        new_channel = st.text_input("채널명")
    with col2:
        new_category = st.selectbox("카테고리", ["뷰티", "패션", "라이프", "음악", "먹방"])
    with col3:
        new_subscribers = st.number_input("구독자수", min_value=0, step=1000, value=0)
    with col4:
        if st.button("추가"):
            if new_channel:
                # CSV 데이터 매니저를 우선으로 시도
                success = False
                
                if get_csv_data_manager:
                    try:
                        csv_client = get_csv_data_manager()
                        success = csv_client.add_channel(new_channel, new_category, subscribers=new_subscribers)
                        if success:
                            st.success(f"✅ {new_channel} 채널이 CSV 파일에 추가되었습니다!")
                            st.rerun()  # 페이지 새로고침하여 채널 목록 업데이트
                        else:
                            st.warning("⚠️ 중복된 채널이거나 CSV 추가에 실패했습니다.")
                    except Exception as e:
                        st.warning(f"CSV 추가 중 오류: {str(e)}")
                
                # CSV 실패시 Google Sheets OAuth 시도
                if not success and get_google_sheets_oauth_client:
                    try:
                        oauth_client = get_google_sheets_oauth_client()
                        success = oauth_client.add_channel(new_channel, new_category, subscribers=new_subscribers)
                        if success:
                            st.success(f"✅ {new_channel} 채널이 구글 시트에 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("❌ 구글 시트 채널 추가에 실패했습니다.")
                    except Exception as e:
                        st.error(f"❌ 구글 시트 채널 추가 중 오류: {str(e)}")
                
                if not success:
                    st.error("❌ 모든 데이터 저장소에 채널 추가 실패. 연결 상태를 확인해주세요.")
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
            # CSV 데이터 매니저를 우선으로 시도
            export_success = False
            
            if get_csv_data_manager:
                try:
                    csv_client = get_csv_data_manager()
                    csv_path = csv_client.export_to_csv()
                    if csv_path:
                        st.success(f"✅ CSV 파일이 생성되었습니다!")
                        st.info(f"저장 경로: {csv_path}")
                        export_success = True
                except Exception as e:
                    st.warning(f"CSV 내보내기 중 오류: {str(e)}")
            
            # CSV 실패시 Google Sheets 시도
            if not export_success and get_google_sheets_oauth_client:
                try:
                    oauth_client = get_google_sheets_oauth_client()
                    csv_path = oauth_client.export_to_csv()
                    if csv_path:
                        st.success(f"✅ CSV 파일이 생성되었습니다!")
                        st.info(f"저장 경로: {csv_path}")
                        export_success = True
                except Exception as e:
                    st.error(f"❌ 구글 시트 CSV 생성 중 오류: {str(e)}")
            
            if not export_success:
                st.warning("내보낼 데이터가 없거나 파일 생성에 실패했습니다.")
    
    with col3:
        if st.button("📧 테스트 알림 생성"):
            st.warning("알림을 생성할 데이터가 없습니다. 먼저 시스템이 데이터를 수집하고 분석하도록 설정해주세요.")