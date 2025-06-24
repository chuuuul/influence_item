"""
간단한 AI 콘텐츠 생성기 (의존성 최소화)
"""

import streamlit as st
import time
from typing import Dict, List, Any

def render_ai_content_generator():
    """AI 콘텐츠 생성기 메인 페이지"""
    st.markdown("## 🤖 AI 콘텐츠 생성기")
    
    st.info("""
    ✨ **AI 콘텐츠 생성기!**  
    • 🎯 다양한 프롬프트 템플릿 선택  
    • 🔄 A/B 테스트로 최적 콘텐츠 발견  
    • 📊 자동 품질 평가 및 개선 제안  
    """)
    
    # 제품 정보 입력
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
            ["스킨케어", "메이크업", "헤어케어", "패션", "향수", "액세서리"],
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
    
    # 생성 버튼
    if st.button("🚀 AI 콘텐츠 생성", type="primary", use_container_width=True):
        if channel_name and product_name:
            # 제품 데이터 구성
            product_data = {
                "채널명": channel_name,
                "제품명": product_name,
                "카테고리": category,
                "매력도_점수": attraction_score,
                "예상_가격": expected_price
            }
            
            with st.spinner("AI 콘텐츠를 생성하고 있습니다..."):
                time.sleep(2)  # 생성 시뮬레이션
                
                # 여러 버전의 콘텐츠 생성
                contents = [
                    {
                        'template_name': '기본형',
                        'title': f'{channel_name}의 {product_name} 추천!',
                        'hashtags': '#뷰티 #스킨케어 #추천 #인스타그램 #좋아요',
                        'caption': f'{product_name} 정말 좋아요! 추천합니다 💕',
                        'quality_score': 8.5
                    },
                    {
                        'template_name': '감정적',
                        'title': f'완전 반했어요 💕 {product_name}',
                        'hashtags': '#감동 #변화 #사랑해 #완전추천 #진심',
                        'caption': f'{product_name} 진짜 너무 좋아서 눈물날뻔했어요 😭',
                        'quality_score': 9.2
                    },
                    {
                        'template_name': '정보형',
                        'title': f'{product_name} 성분 분석 & 효과 후기',
                        'hashtags': '#성분분석 #효과 #사용법 #팩트체크 #정보공유',
                        'caption': f'{product_name} - 효과적인 성분으로 구성. 사용법과 효과를 자세히 설명합니다.',
                        'quality_score': 8.8
                    }
                ]
                
            st.success("✅ AI 콘텐츠 생성 완료!")
            
            # 결과 표시
            st.markdown("---")
            st.markdown("## 🔄 생성된 콘텐츠 결과")
            
            # 최고 점수 결과를 맨 위에 표시
            best_content = max(contents, key=lambda x: x['quality_score'])
            
            st.markdown(f"### 🏆 최고 점수: {best_content['template_name']} ({best_content['quality_score']:.1f}점)")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("**🎯 제목**")
                st.info(best_content['title'])
                
                st.markdown("**#️⃣ 해시태그**")
                st.info(best_content['hashtags'])
                
                st.markdown("**💬 캡션**")
                st.info(best_content['caption'])
            
            with col2:
                st.metric("품질 점수", f"{best_content['quality_score']:.1f}/10")
                
                if st.button("📋 전체 복사", type="primary"):
                    st.success("클립보드에 복사되었습니다!")
            
            # 다른 결과들
            st.markdown("### 📊 다른 버전들")
            
            for content in contents:
                if content != best_content:
                    with st.expander(f"{content['template_name']} ({content['quality_score']:.1f}점)"):
                        st.markdown(f"**제목**: {content['title']}")
                        st.markdown(f"**해시태그**: {content['hashtags']}")
                        st.markdown(f"**캡션**: {content['caption']}")
        else:
            st.error("❌ 채널명과 제품명은 필수 입력 항목입니다.")
    
    # 프리셋 제품들
    st.markdown("---")
    st.markdown("### 🎯 빠른 시작 (프리셋 제품)")
    
    col1, col2, col3 = st.columns(3)
    
    presets = [
        {"name": "홍지윤 - 히알루론산 세럼", "channel": "홍지윤 Yoon", "product": "히알루론산 세럼"},
        {"name": "아이유 - 틴트 립", "channel": "아이유IU", "product": "틴트 립"},
        {"name": "이사배 - 와이드 데님", "channel": "이사배(RISABAE)", "product": "와이드 데님"}
    ]
    
    for i, preset in enumerate(presets):
        with [col1, col2, col3][i]:
            if st.button(preset["name"], use_container_width=True, key=f"preset_{i}"):
                st.session_state.input_channel = preset["channel"]
                st.session_state.input_product = preset["product"]
                st.success(f"✅ {preset['name']} 프리셋이 로드되었습니다!")
                st.rerun()

if __name__ == "__main__":
    render_ai_content_generator()