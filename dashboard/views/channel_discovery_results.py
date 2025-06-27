"""채널 탐색 결과 페이지"""
import streamlit as st
import pandas as pd

def render_channel_discovery_results():
    st.header("📊 채널 탐색 결과")
    st.info("신규 채널 탐색 결과를 검토하고 승인/제외 처리합니다.")
    
    # 결과 데이터
    data = pd.DataFrame({
        "채널명": ["홍지윤 Yoon", "아이유IU", "이사배", "소이와여니", "김민정"],
        "구독자수": ["1.2M", "8.5M", "2.1M", "450K", "800K"],
        "카테고리": ["뷰티/라이프", "음악/라이프", "뷰티", "육아/라이프", "패션"],
        "매칭점수": [92, 88, 95, 72, 83],
        "예상 제품수": [45, 23, 67, 12, 34],
        "상태": ["검토 대기", "승인", "검토 대기", "검토 대기", "제외"]
    })
    
    # 필터
    status_filter = st.selectbox("상태 필터", ["전체", "검토 대기", "승인", "제외"])
    if status_filter != "전체":
        data = data[data["상태"] == status_filter]
    
    st.dataframe(data, use_container_width=True)
    
    # 일괄 처리
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ 전체 승인"):
            st.success("선택된 채널이 승인되었습니다!")
    with col2:
        if st.button("🎯 고득점 승인 (85점 이상)"):
            st.success("고득점 채널이 승인되었습니다!")
    with col3:
        if st.button("📊 Google Sheets 내보내기"):
            st.info("Google Sheets로 내보내는 중...")