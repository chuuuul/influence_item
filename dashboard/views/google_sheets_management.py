"""
Google Sheets 관리 페이지 - PRD v1.0 구현

리뷰어 지적사항 해결:
- 통합된 Google Sheets 클라이언트 사용
- 단일 인증 시스템으로 안정성 확보
- 중앙화된 경로 관리 시스템 적용
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any

# 중앙화된 경로 관리 시스템 import
try:
    from config.path_config import get_path_manager
    pm = get_path_manager()
except ImportError:
    # fallback
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config.path_config import get_path_manager
    pm = get_path_manager()

# 통합 Google Sheets 클라이언트 import
try:
    from utils.google_sheets_unified import get_google_sheets_client, AuthMethod
    from utils.env_loader import ensure_gemini_api_key
except ImportError as e:
    st.error(f"필수 모듈 import 실패: {e}")
    get_google_sheets_client = None
    ensure_gemini_api_key = None

def render_google_sheets_management():
    """
    Google Sheets 관리 페이지 - PRD v1.0 구현
    
    주요 기능:
    - 채널 목록 관리 (Google Sheets)
    - 신규 채널 탐색 결과 관리
    - 운영자 검토 및 승인 처리
    """
    st.header("📋 Google Sheets 관리")
    st.markdown("**PRD v1.0**: 연예인 채널 목록을 Google Sheets로 관리하고 n8n 워크플로우와 연동합니다.")
    
    if not get_google_sheets_client:
        st.error("❌ Google Sheets 통합 클라이언트를 로드할 수 없습니다.")
        return
    
    # 통합 클라이언트 가져오기
    client = get_google_sheets_client()
    
    # === 연결 상태 및 시스템 정보 ===
    st.markdown("### 🔌 연결 상태")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        success, info = client.get_connection_status()
        if success:
            auth_method = info.get('auth_method', 'Unknown')
            auth_color = {
                'service_account': '🟢',
                'oauth': '🟡', 
                'api_key': '🔵'
            }.get(auth_method, '⚪')
            
            st.success(f"{auth_color} **{auth_method}** 인증으로 연결됨")
            
            # 상세 정보 표시
            st.write(f"**시트 제목**: {info.get('title', 'N/A')}")
            st.write(f"**시트 ID**: {info.get('sheet_id', 'N/A')[:15]}...")
            if info.get('url'):
                st.markdown(f"**[🔗 Google Sheets 열기]({info['url']})**")
            
            # 권한 정보
            capabilities = info.get('capabilities', [])
            if 'write' in capabilities:
                st.info("✅ 읽기/쓰기 권한")
            else:
                st.warning("⚠️ 읽기 전용 권한")
                
        else:
            st.error(f"❌ 연결 실패: {info}")
    
    with col2:
        if st.button("🔄 동기화", type="secondary"):
            with st.spinner("동기화 중..."):
                if client.sync_data():
                    st.success("✅ 동기화 완료!")
                    st.rerun()
                else:
                    st.error("❌ 동기화 실패")
    
    with col3:
        if st.button("🧪 연결 테스트", type="secondary"):
            test_connection_status(client)
    
    # === API 키 상태 확인 ===
    st.markdown("### 🔑 API 설정")
    
    api_status_col1, api_status_col2 = st.columns(2)
    
    with api_status_col1:
        # Gemini API 키 확인
        try:
            if ensure_gemini_api_key:
                gemini_key = ensure_gemini_api_key()
                st.success(f"✅ Gemini API 키: {gemini_key[:10]}...")
            else:
                st.warning("⚠️ Gemini API 키 확인 불가")
        except ValueError as e:
            st.error(f"❌ Gemini API: {str(e)}")
        except Exception as e:
            st.error(f"❌ API 키 확인 오류: {str(e)}")
    
    with api_status_col2:
        # Google Sheets 설정 확인
        sheet_id = os.getenv('GOOGLE_SHEET_ID', 'Not set')
        if sheet_id != 'Not set':
            st.success(f"✅ Sheet ID: {sheet_id[:15]}...")
        else:
            st.error("❌ GOOGLE_SHEET_ID 미설정")
    
    st.markdown("---")
    
    # === 채널 통계 및 데이터 관리 ===
    st.markdown("### 📊 채널 데이터 현황")
    
    # 통계 정보 표시
    stats = client.get_statistics()
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    
    with stat_col1:
        st.metric("총 채널 수", stats['total_channels'])
    
    with stat_col2:
        active_count = stats['by_status'].get('활성', 0)
        st.metric("활성 채널", active_count)
    
    with stat_col3:
        review_count = stats['by_status'].get('검토중', 0)
        st.metric("검토 대기", review_count)
    
    with stat_col4:
        total_subs = stats['total_subscribers']
        if total_subs > 1000000:
            subs_display = f"{total_subs/1000000:.1f}M"
        elif total_subs > 1000:
            subs_display = f"{total_subs/1000:.1f}K"
        else:
            subs_display = str(total_subs)
        st.metric("총 구독자", subs_display)
    
    # === 채널 목록 표시 ===
    st.markdown("### 📺 등록된 채널 목록")
    
    channels = client.get_channels()
    
    if channels:
        # 필터링 옵션
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            status_filter = st.selectbox(
                "상태 필터",
                options=["전체"] + list(stats['by_status'].keys()),
                key="status_filter"
            )
        
        with filter_col2:
            category_filter = st.selectbox(
                "카테고리 필터", 
                options=["전체"] + list(stats['by_category'].keys()),
                key="category_filter"
            )
        
        with filter_col3:
            search_term = st.text_input("채널명 검색", key="search_channels")
        
        # 필터링 적용
        filtered_channels = channels
        
        if status_filter != "전체":
            filtered_channels = [ch for ch in filtered_channels if ch.get('상태') == status_filter]
        
        if category_filter != "전체":
            filtered_channels = [ch for ch in filtered_channels if ch.get('카테고리') == category_filter]
        
        if search_term:
            filtered_channels = [ch for ch in filtered_channels 
                               if search_term.lower() in ch.get('채널명', '').lower()]
        
        # 데이터프레임으로 표시
        if filtered_channels:
            df = pd.DataFrame(filtered_channels)
            
            # 컬럼 순서 정리
            column_order = ['채널명', '채널 ID', '카테고리', '구독자수', '상태', '마지막 업데이트', '설명', '추가일']
            df = df.reindex(columns=[col for col in column_order if col in df.columns])
            
            # 상태별 색상 표시를 위한 스타일링
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "구독자수": st.column_config.NumberColumn(
                        "구독자수",
                        format="%d",
                    ),
                    "상태": st.column_config.SelectboxColumn(
                        "상태",
                        options=["검토중", "활성", "비활성", "제외"]
                    ),
                    "채널 ID": st.column_config.TextColumn(
                        "채널 ID",
                        width="medium"
                    )
                }
            )
            
            st.info(f"📋 총 {len(filtered_channels)}개 채널 (전체: {len(channels)}개)")
        else:
            st.warning("필터 조건에 맞는 채널이 없습니다.")
    else:
        st.info("등록된 채널이 없습니다. 아래에서 새 채널을 추가해주세요.")
    
    # === 채널 추가 ===
    st.markdown("### ➕ 새 채널 추가")
    
    with st.form("add_channel_form"):
        add_col1, add_col2, add_col3 = st.columns(3)
        
        with add_col1:
            new_channel_name = st.text_input("채널명", help="YouTube 채널 이름")
            new_channel_id = st.text_input("채널 ID", help="YouTube 채널 ID (UC로 시작)")
        
        with add_col2:
            new_category = st.selectbox(
                "카테고리", 
                ["뷰티", "패션", "라이프스타일", "음악", "먹방", "게임", "기타"],
                help="PRD 카테고리 분류"
            )
            new_subscribers = st.number_input(
                "구독자수", 
                min_value=0, 
                step=1000, 
                value=0,
                help="현재 구독자 수"
            )
        
        with add_col3:
            new_description = st.text_area(
                "설명", 
                height=100,
                help="채널에 대한 간단한 설명"
            )
        
        submitted = st.form_submit_button("📌 채널 추가", type="primary")
        
        if submitted:
            if new_channel_name and new_channel_id:
                if client.is_read_only():
                    st.error("❌ 읽기 전용 모드에서는 채널을 추가할 수 없습니다.")
                else:
                    with st.spinner("채널 추가 중..."):
                        success = client.add_channel(
                            channel_name=new_channel_name,
                            channel_id=new_channel_id,
                            category=new_category,
                            subscribers=new_subscribers,
                            description=new_description
                        )
                        
                        if success:
                            st.success(f"✅ '{new_channel_name}' 채널이 추가되었습니다!")
                            st.info("💡 새로 추가된 채널은 '검토중' 상태입니다. 운영자 승인 후 활성화됩니다.")
                            st.rerun()
                        else:
                            st.error("❌ 채널 추가에 실패했습니다.")
            else:
                st.error("❌ 채널명과 채널 ID를 모두 입력해주세요.")
    
    # === 상태 관리 ===
    if channels and not client.is_read_only():
        st.markdown("### ⚙️ 채널 상태 관리")
        
        with st.expander("채널 상태 변경", expanded=False):
            status_col1, status_col2, status_col3 = st.columns(3)
            
            with status_col1:
                channel_options = [f"{ch['채널명']} ({ch['채널 ID']})" for ch in channels]
                selected_channel = st.selectbox("변경할 채널", channel_options)
            
            with status_col2:
                new_status = st.selectbox(
                    "새 상태",
                    ["검토중", "활성", "비활성", "제외"],
                    help="PRD 상태 관리"
                )
            
            with status_col3:
                if st.button("상태 변경", type="secondary"):
                    if selected_channel:
                        # 채널 ID 추출
                        channel_id = selected_channel.split('(')[1].split(')')[0]
                        
                        if client.update_channel_status(channel_id, new_status):
                            st.success(f"✅ 채널 상태가 '{new_status}'로 변경되었습니다!")
                            st.rerun()
                        else:
                            st.error("❌ 상태 변경에 실패했습니다.")
    
    # === 데이터 내보내기 ===
    st.markdown("### 📤 데이터 관리")
    
    data_col1, data_col2, data_col3 = st.columns(3)
    
    with data_col1:
        if st.button("📊 CSV 내보내기", type="secondary"):
            with st.spinner("CSV 파일 생성 중..."):
                csv_path = client.export_to_csv()
                if csv_path:
                    st.success("✅ CSV 파일이 생성되었습니다!")
                    st.code(f"저장 경로: {csv_path}")
                else:
                    st.error("❌ CSV 내보내기에 실패했습니다.")
    
    with data_col2:
        if st.button("🔄 헤더 재설정", type="secondary"):
            if client.is_read_only():
                st.error("❌ 읽기 전용 모드에서는 헤더를 설정할 수 없습니다.")
            else:
                with st.spinner("헤더 설정 중..."):
                    if client.ensure_headers():
                        st.success("✅ 헤더가 재설정되었습니다!")
                    else:
                        st.error("❌ 헤더 설정에 실패했습니다.")
    
    with data_col3:
        if st.button("📧 n8n 알림 테스트", type="secondary"):
            st.info("💡 n8n 워크플로우 연동 기능은 개발 중입니다.")
    
    # === PRD 템플릿 정보 ===
    st.markdown("### 📄 PRD 요구사항")
    
    with st.expander("Google Sheets 구조 (PRD v1.0)", expanded=False):
        st.markdown("""
        **필수 컬럼 구조:**
        - `채널명`: YouTube 채널 이름
        - `채널 ID`: YouTube 채널 고유 ID (UC로 시작)
        - `카테고리`: 콘텐츠 분류 (뷰티, 패션, 라이프스타일 등)
        - `구독자수`: 현재 구독자 수
        - `상태`: 채널 관리 상태 (검토중, 활성, 비활성, 제외)
        - `마지막 업데이트`: 최근 수정 시간
        - `설명`: 채널에 대한 설명
        - `추가일`: 채널이 등록된 날짜
        
        **워크플로우 (PRD 2.1):**
        1. 신규 채널 탐색 → 자동 추가 (검토중 상태)
        2. 운영자 검토 → 승인/반려
        3. n8n 워크플로우와 연동 → 자동 영상 수집
        """)
    
    # === 환경 설정 정보 ===
    with st.expander("환경 설정 정보", expanded=False):
        env_info = {
            "GOOGLE_SHEET_ID": os.getenv('GOOGLE_SHEET_ID', '❌ 미설정'),
            "GOOGLE_SHEET_URL": os.getenv('GOOGLE_SHEET_URL', '❌ 미설정'),
            "GEMINI_API_KEY": "✅ 설정됨" if os.getenv('GEMINI_API_KEY') else "❌ 미설정",
            "인증 방법": client.auth_method.value if client.auth_method else "❌ 인증 실패",
            "경로 관리": f"✅ {pm.dashboard_root}",
            "인증 파일 경로": str(pm.google_credentials_dir)
        }
        
        for key, value in env_info.items():
            if "API_KEY" in key and "설정됨" in value:
                st.write(f"**{key}**: {value}")
            elif "❌" in value:
                st.error(f"**{key}**: {value}")
            else:
                st.success(f"**{key}**: {value}")


def test_connection_status(client):
    """연결 상태 상세 테스트"""
    st.markdown("#### 🧪 연결 테스트 결과")
    
    # 기본 연결 테스트
    success, info = client.get_connection_status()
    
    if success:
        st.success("✅ 기본 연결: 성공")
        
        # 데이터 읽기 테스트
        try:
            channels = client.get_channels()
            st.success(f"✅ 데이터 읽기: 성공 ({len(channels)}개 채널)")
        except Exception as e:
            st.error(f"❌ 데이터 읽기: 실패 - {e}")
        
        # 쓰기 권한 테스트
        if not client.is_read_only():
            st.success("✅ 쓰기 권한: 있음")
        else:
            st.warning("⚠️ 쓰기 권한: 읽기 전용")
        
        # 상세 정보
        st.json(info)
        
    else:
        st.error(f"❌ 기본 연결: 실패 - {info}")
        
        # 문제 해결 가이드
        st.markdown("#### 🔧 문제 해결 가이드")
        st.markdown("""
        1. **서비스 계정 인증**: `credentials/service_account.json` 파일 확인
        2. **OAuth 인증**: `~/.config/gspread/credentials.json` 파일 확인  
        3. **API 키 인증**: `YOUTUBE_API_KEY` 환경변수 확인
        4. **환경변수**: `GOOGLE_SHEET_ID` 설정 확인
        """)


if __name__ == "__main__":
    render_google_sheets_management()