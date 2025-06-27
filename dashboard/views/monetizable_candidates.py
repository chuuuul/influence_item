"""수익화 가능 후보 페이지"""
import streamlit as st
import pandas as pd

def render_monetizable_candidates():
    st.header("🎯 수익화 가능 후보")
    st.info("AI 2-Pass 분석을 통해 발견된 제품 추천 후보들")
    
    # 샘플 데이터
    data = pd.DataFrame({
        "연예인": ["강민경", "아이유", "박보영", "이사배", "홍지윤"],
        "제품명": ["아비에무아 숄더백", "닥터자르트 크림", "나이키 운동화", "맥 립스틱", "헤라 쿠션"],
        "영상 제목": ["파리 출장 VLOG", "스킨케어 루틴", "운동 브이로그", "메이크업 튜토리얼", "겟레디윗미"],
        "매력도 점수": [88, 92, 85, 79, 83],
        "업로드 날짜": ["2025-06-20", "2025-06-19", "2025-06-18", "2025-06-17", "2025-06-16"],
        "상태": ["needs_review", "approved", "needs_review", "approved", "needs_review"]
    })
    
    # 필터링
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("상태 필터", ["전체", "needs_review", "approved", "rejected"])
    with col2:
        sort_by = st.selectbox("정렬 기준", ["매력도 점수", "업로드 날짜", "연예인"])
    
    # 필터 적용
    if status_filter != "전체":
        data = data[data["상태"] == status_filter]
    
    # 정렬 적용
    if sort_by == "매력도 점수":
        data = data.sort_values("매력도 점수", ascending=False)
    elif sort_by == "업로드 날짜":
        data = data.sort_values("업로드 날짜", ascending=False)
    else:
        data = data.sort_values("연예인")
    
    # 테이블 표시
    st.dataframe(data, use_container_width=True)
    
    # 상태별 통계
    st.subheader("📊 상태별 통계")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("검토 대기", len(data[data["상태"] == "needs_review"]))
    with col2:
        st.metric("승인됨", len(data[data["상태"] == "approved"]))
    with col3:
        st.metric("전체", len(data))