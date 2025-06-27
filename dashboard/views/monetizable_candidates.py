"""수익화 가능 후보 페이지"""
import streamlit as st
import pandas as pd

def render_monetizable_candidates():
    st.header("🎯 수익화 가능 후보")
    st.info("AI 2-Pass 분석을 통해 발견된 제품 추천 후보들")
    
    st.warning("실제 데이터를 표시하려면 데이터베이스 연결이 필요합니다.")
    st.info("메인 대시보드에서 데이터베이스 기반의 후보 목록을 확인할 수 있습니다.")