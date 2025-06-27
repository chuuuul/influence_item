"""영상 수집 페이지"""
import streamlit as st
import pandas as pd

def render_video_collection():
    st.header("🎥 영상 수집")
    st.info("승인된 채널의 신규 영상을 RSS 피드로 수집하거나, 과거 영상을 웹 스크래핑으로 수집합니다.")
    
    # 수집 설정
    st.subheader("⚙️ 수집 설정")
    
    collection_type = st.radio("수집 유형", ["신규 영상 (RSS)", "과거 영상 (스크래핑)"])
    
    if collection_type == "신규 영상 (RSS)":
        st.info("매일 자동으로 RSS 피드를 통해 신규 영상을 수집합니다.")
        if st.button("🔄 수동 수집 실행"):
            st.success("RSS 피드 수집이 시작되었습니다!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            channel = st.selectbox("채널 선택", ["등록된 채널 없음"])
        with col2:
            period = st.selectbox("분석 기간", ["최근 1개월", "최근 3개월", "최근 6개월"])
        
        if st.button("🚀 수집 시작"):
            st.success(f"{channel}의 {period} 영상 수집이 시작되었습니다!")
    
    # 수집 현황
    st.subheader("📊 수집 현황")
    st.info("등록된 채널이 없습니다. 먼저 채널을 등록해주세요.")