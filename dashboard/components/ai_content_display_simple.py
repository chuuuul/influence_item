"""
간단한 AI 콘텐츠 디스플레이 컴포넌트 (의존성 최소화)
"""

import streamlit as st
from typing import Dict, List, Any

def render_ai_content_display(content_data: Dict[str, Any]) -> None:
    """AI 생성 콘텐츠 표시"""
    if not content_data:
        st.warning("표시할 콘텐츠가 없습니다.")
        return
    
    # 제목
    if 'title' in content_data:
        st.markdown("**🎯 제목**")
        st.info(content_data['title'])
    
    # 해시태그
    if 'hashtags' in content_data:
        st.markdown("**#️⃣ 해시태그**")
        st.info(content_data['hashtags'])
    
    # 캡션
    if 'caption' in content_data:
        st.markdown("**💬 캡션**")
        st.info(content_data['caption'])

def generate_ai_content(product_data: Dict[str, Any]) -> Dict[str, str]:
    """AI 콘텐츠 생성 (시뮬레이션)"""
    return {
        'title': f"{product_data.get('채널명', '채널')}의 {product_data.get('제품명', '제품')} 추천!",
        'hashtags': '#뷰티 #추천 #인스타그램 #좋아요 #신상 #후기',
        'caption': f"{product_data.get('제품명', '이 제품')}을 사용해봤는데 정말 좋아요! 추천합니다 💕"
    }