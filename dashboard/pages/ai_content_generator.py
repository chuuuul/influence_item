"""
S03-005: AI 콘텐츠 생성기 독립 페이지
제품 정보를 입력하면 AI 콘텐츠를 생성하는 독립적인 도구
"""

import streamlit as st
import pandas as pd
from dashboard.components.ai_content_display import render_ai_content_display, generate_ai_content

def render_product_input_form():
    """제품 정보 입력 폼"""
    st.markdown("### 📝 제품 정보 입력")
    
    col1, col2 = st.columns(2)
    
    with col1:
        channel_name = st.text_input(
            "채널명",
            placeholder="예: 홍지윤 Yoon",
            key="input_channel"
        )
        
        product_name = st.text_input(
            "제품명", 
            placeholder="예: 히알루론산 세럼 - 프리미엄",
            key="input_product"
        )
        
        category = st.selectbox(
            "카테고리",
            ["스킨케어", "메이크업", "헤어케어", "패션", "향수", "액세서리", 
             "홈인테리어", "건강식품", "전자기기", "라이프스타일"],
            key="input_category"
        )
    
    with col2:
        attraction_score = st.slider(
            "매력도 점수",
            min_value=0,
            max_value=100,
            value=75,
            step=1,
            key="input_score"
        )
        
        expected_price = st.text_input(
            "예상 가격",
            placeholder="예: 45,000원",
            key="input_price"
        )
        
        video_title = st.text_input(
            "영상 제목 (선택사항)",
            placeholder="예: [일상VLOG] 스킨케어 추천 | 솔직 후기",
            key="input_video_title"
        )
    
    # 추가 옵션
    with st.expander("🔧 고급 옵션"):
        col1, col2 = st.columns(2)
        
        with col1:
            content_tone = st.selectbox(
                "콘텐츠 톤",
                ["친근함", "전문적", "유머러스", "감성적", "정보 중심"],
                key="content_tone"
            )
            
            target_platform = st.selectbox(
                "타겟 플랫폼",
                ["Instagram", "TikTok", "YouTube Shorts", "Facebook", "범용"],
                key="target_platform"
            )
        
        with col2:
            include_price = st.checkbox("가격 정보 포함", value=True, key="include_price")
            include_score = st.checkbox("매력도 점수 포함", value=True, key="include_score")
            include_emojis = st.checkbox("이모지 포함", value=True, key="include_emojis")
    
    # 생성 버튼
    if st.button("🚀 AI 콘텐츠 생성", type="primary", use_container_width=True):
        if channel_name and product_name:
            # 제품 데이터 구성
            product_data = {
                "id": f"MANUAL_{channel_name}_{product_name}",
                "채널명": channel_name,
                "제품명": product_name,
                "카테고리": category,
                "매력도_점수": attraction_score,
                "예상_가격": expected_price,
                "영상_제목": video_title,
                "콘텐츠_톤": content_tone,
                "타겟_플랫폼": target_platform,
                "옵션": {
                    "include_price": include_price,
                    "include_score": include_score,
                    "include_emojis": include_emojis
                }
            }
            
            st.session_state.manual_product_data = product_data
            st.success("✅ 제품 정보가 입력되었습니다! 아래에서 AI 콘텐츠를 확인하세요.")
            st.rerun()
        else:
            st.error("❌ 채널명과 제품명은 필수 입력 항목입니다.")

def render_preset_products():
    """사전 정의된 제품 프리셋"""
    st.markdown("### 🎯 빠른 시작 (프리셋 제품)")
    
    presets = [
        {
            "name": "홍지윤 - 히알루론산 세럼",
            "data": {
                "채널명": "홍지윤 Yoon",
                "제품명": "히알루론산 세럼 - 프리미엄",
                "카테고리": "스킨케어",
                "매력도_점수": 85.3,
                "예상_가격": "45,000원"
            }
        },
        {
            "name": "아이유 - 틴트 립",
            "data": {
                "채널명": "아이유IU",
                "제품명": "틴트 립 - 에센셜",
                "카테고리": "메이크업",
                "매력도_점수": 92.2,
                "예상_가격": "18,000원"
            }
        },
        {
            "name": "이사배 - 와이드 데님",
            "data": {
                "채널명": "이사배(RISABAE)",
                "제품명": "와이드 데님 - 프리미엄",
                "카테고리": "패션",
                "매력도_점수": 87.7,
                "예상_가격": "90,000원"
            }
        }
    ]
    
    col1, col2, col3 = st.columns(3)
    
    for i, preset in enumerate(presets):
        with [col1, col2, col3][i]:
            if st.button(
                preset["name"],
                use_container_width=True,
                key=f"preset_{i}"
            ):
                st.session_state.manual_product_data = preset["data"]
                st.success(f"✅ {preset['name']} 프리셋이 로드되었습니다!")
                st.rerun()

def render_ai_content_generator():
    """AI 콘텐츠 생성기 메인 페이지"""
    st.markdown("## 🤖 AI 콘텐츠 생성기")
    
    st.info("""
    📝 **AI 콘텐츠 생성기에 오신 것을 환영합니다!**  
    제품 정보를 입력하면 Instagram, TikTok 등에 최적화된 콘텐츠를 자동으로 생성합니다.  
    제목, 해시태그, 캡션을 한 번에 만들어보세요!
    """)
    
    # 탭으로 구분
    tab1, tab2 = st.tabs(["📝 수동 입력", "🎯 프리셋 사용"])
    
    with tab1:
        render_product_input_form()
    
    with tab2:
        render_preset_products()
        
        # 기존 후보에서 선택
        st.markdown("---")
        st.markdown("### 📊 기존 후보에서 선택")
        
        if st.button("수익화 후보에서 가져오기", use_container_width=True):
            st.info("🚧 수익화 후보 데이터 연동 기능은 향후 구현됩니다.")
    
    # AI 콘텐츠 표시
    if 'manual_product_data' in st.session_state:
        st.markdown("---")
        
        # 입력된 제품 정보 요약
        product_data = st.session_state.manual_product_data
        
        with st.expander("📋 입력된 제품 정보", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**채널명**: {product_data.get('채널명', '-')}")
                st.markdown(f"**제품명**: {product_data.get('제품명', '-')}")
                st.markdown(f"**카테고리**: {product_data.get('카테고리', '-')}")
            
            with col2:
                st.markdown(f"**매력도 점수**: {product_data.get('매력도_점수', 0)}점")
                st.markdown(f"**예상 가격**: {product_data.get('예상_가격', '-')}")
                st.markdown(f"**영상 제목**: {product_data.get('영상_제목', '-') or '미입력'}")
        
        # AI 콘텐츠 생성 및 표시
        render_ai_content_display(product_data)
        
        # 초기화 버튼
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("🔄 새로 시작", use_container_width=True):
                if 'manual_product_data' in st.session_state:
                    del st.session_state.manual_product_data
                if 'saved_content' in st.session_state:
                    del st.session_state.saved_content
                st.rerun()
    
    else:
        st.markdown("---")
        st.markdown("### 🎯 시작하기")
        st.markdown("""
        위의 탭에서 다음 중 하나를 선택하세요:
        
        1. **📝 수동 입력**: 제품 정보를 직접 입력하여 맞춤형 콘텐츠 생성
        2. **🎯 프리셋 사용**: 미리 준비된 제품 예시로 빠른 테스트
        
        입력이 완료되면 자동으로 AI가 최적화된 콘텐츠를 생성합니다! 🚀
        """)

if __name__ == "__main__":
    render_ai_content_generator()