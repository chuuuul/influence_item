"""채널 탐색 결과 페이지"""
import streamlit as st
import pandas as pd

def render_channel_discovery_results():
    st.header("📊 채널 탐색 결과")
    st.info("신규 채널 탐색 결과를 검토하고 승인/제외 처리합니다.")
    
    st.warning("채널 탐색 결과가 없습니다.")
    st.info("'신규 채널 탐색' 페이지에서 먼저 채널을 검색해주세요.")