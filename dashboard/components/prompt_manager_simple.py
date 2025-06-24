"""
간단한 프롬프트 매니저 (의존성 최소화)
"""

import streamlit as st
from typing import Dict, List, Any

class PromptTemplate:
    def __init__(self, name: str, template: str):
        self.name = name
        self.template = template

class PromptManager:
    def __init__(self):
        self.templates = {
            "basic": PromptTemplate("기본형", "기본적인 제품 추천 템플릿"),
            "emotional": PromptTemplate("감정적", "감정에 호소하는 템플릿"),
            "informative": PromptTemplate("정보형", "정보 중심 템플릿")
        }
    
    def get_template(self, template_id: str):
        return self.templates.get(template_id)
    
    def update_template_usage(self, template_id: str, score: float):
        pass

def render_template_selector() -> List[str]:
    """템플릿 선택기"""
    st.markdown("사용할 템플릿을 선택하세요:")
    
    selected = []
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.checkbox("기본형", value=True, key="template_basic"):
            selected.append("basic")
    
    with col2:
        if st.checkbox("감정적", key="template_emotional"):
            selected.append("emotional")
    
    with col3:
        if st.checkbox("정보형", key="template_informative"):
            selected.append("informative")
    
    return selected

def render_custom_template_creator():
    """사용자 정의 템플릿 생성기"""
    st.markdown("### 🎨 사용자 정의 템플릿")
    st.info("사용자 정의 템플릿 기능은 곧 구현됩니다.")

def render_template_comparison(results: List[Dict[str, Any]]):
    """템플릿 비교"""
    st.markdown("### 📊 템플릿 성능 비교")
    
    if not results:
        return
    
    for result in results:
        with st.expander(f"{result['template_name']} - {result['quality_score']:.1f}점"):
            st.write(result['content'])