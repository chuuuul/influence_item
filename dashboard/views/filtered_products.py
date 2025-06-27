"""수익화 필터링 목록 페이지"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
dashboard_root = Path(__file__).parent.parent  # dashboard 폴더
project_root = dashboard_root.parent           # influence_item 폴더
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(dashboard_root))

try:
    from utils.database_manager import get_database_manager
except ImportError:
    get_database_manager = None

def render_filtered_products():
    st.header("🚫 수익화 필터링 목록")
    st.info("쿠팡 파트너스에서 검색되지 않은 제품들 (filtered_no_coupang 상태)")
    
    if get_database_manager:
        try:
            db = get_database_manager()
            
            # 필터링된 후보들 조회
            filtered_candidates = db.get_candidates_by_status(status="filtered_no_coupang", limit=100)
            
            if filtered_candidates:
                col1, col2 = st.columns([3, 1])
                with col1:
                    search = st.text_input("🔍 검색", placeholder="연예인, 제품명, 영상 제목...", key="search_filtered")
                with col2:
                    limit = st.selectbox("표시 개수", [10, 25, 50, 100], index=1, key="limit_filtered")
                
                # 데이터프레임 생성
                df_data = []
                for candidate in filtered_candidates[:limit]:
                    source_info = candidate.get('source_info', {})
                    candidate_info = candidate.get('candidate_info', {})
                    status_info = candidate.get('status_info', {})
                    
                    # 검색 필터 적용
                    if search:
                        search_text = f"{source_info.get('celebrity_name', '')} {candidate_info.get('product_name_ai', '')} {source_info.get('video_title', '')}".lower()
                        if search.lower() not in search_text:
                            continue
                    
                    df_data.append({
                        "ID": candidate['id'][:12] + "...",
                        "연예인": source_info.get('celebrity_name', 'N/A'),
                        "제품명": candidate_info.get('product_name_ai', 'N/A'),
                        "영상 제목": source_info.get('video_title', 'N/A')[:30] + "...",
                        "필터링 사유": "쿠팡 파트너스 미등록",
                        "매력도 점수": candidate_info.get('score_details', {}).get('total', 0),
                        "생성일": candidate.get('created_at', '')[:10] if candidate.get('created_at') else 'N/A',
                        "복원 가능": "✅ 가능"
                    })
                
                if df_data:
                    df = pd.DataFrame(df_data)
                    
                    # 데이터 표시
                    st.dataframe(
                        df,
                        use_container_width=True,
                        column_config={
                            "매력도 점수": st.column_config.ProgressColumn(
                                "매력도 점수",
                                help="AI가 산출한 매력도 점수",
                                format="%d",
                                min_value=0,
                                max_value=100,
                            )
                        }
                    )
                    
                    # 복원 기능
                    st.markdown("---")
                    st.markdown("### 🔗 수동 복원 기능")
                    
                    selected_id = st.selectbox(
                        "복원할 후보 선택",
                        options=[row["ID"] for row in df_data],
                        format_func=lambda x: f"{x} - {next(row['제품명'] for row in df_data if row['ID'] == x)}"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        manual_url = st.text_input("수동 제휴 링크", placeholder="https://link.coupang.com/...")
                    with col2:
                        if st.button("메인 목록으로 복원", type="primary"):
                            if manual_url and selected_id:
                                # 실제 ID 찾기
                                full_id = None
                                for candidate in filtered_candidates:
                                    if candidate['id'].startswith(selected_id.replace("...", "")):
                                        full_id = candidate['id']
                                        break
                                
                                if full_id:
                                    success = db.update_candidate_status(
                                        full_id,
                                        "needs_review",
                                        f"수동 복원: {manual_url}",
                                        "dashboard_user"
                                    )
                                    
                                    if success:
                                        st.success("✅ 성공적으로 복원되었습니다!")
                                        st.rerun()
                                    else:
                                        st.error("❌ 복원 실패")
                                else:
                                    st.error("❌ 후보를 찾을 수 없습니다")
                            else:
                                st.error("제휴 링크를 입력해주세요")
                    
                    st.info(f"📊 총 {len(df_data)}개의 필터링된 후보를 표시하고 있습니다.")
                else:
                    st.warning("검색 조건에 맞는 필터링된 후보가 없습니다.")
            else:
                st.success("🎉 현재 필터링된 후보가 없습니다. 모든 후보가 수익화 가능합니다!")
                
        except Exception as e:
            st.error(f"데이터 로딩 오류: {e}")
            st.info("데이터베이스가 초기화되지 않았거나 연결에 문제가 있습니다.")
    else:
        st.error("데이터베이스 연결을 설정할 수 없습니다.")
    
    # 도움말
    with st.expander("💡 필터링 목록 사용법"):
        st.markdown("""
        **필터링된 후보란?**
        - 쿠팡 파트너스 API에서 검색되지 않은 제품들
        - 해외 브랜드, 한정판, 빈티지 제품 등이 주로 해당
        
        **복원 방법:**
        1. 수동으로 쿠팡에서 유사 제품 찾기
        2. 제휴 링크 생성 후 입력
        3. "메인 목록으로 복원" 버튼 클릭
        
        **주의사항:**
        - 복원된 후보는 다시 검토가 필요합니다
        - 제휴 링크는 정확한지 확인 후 입력하세요
        """)