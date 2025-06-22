"""
S03-005: AI 생성 콘텐츠 표시 및 복사 기능
추천 제목, 해시태그, 캡션 표시 및 복사
"""

import streamlit as st
import json
import re
from datetime import datetime
import pyperclip
import os

def generate_ai_content(product_data):
    """제품 데이터를 기반으로 AI 콘텐츠 생성"""
    
    channel_name = product_data.get('채널명', '연예인')
    product_name = product_data.get('제품명', '제품')
    category = product_data.get('카테고리', '뷰티')
    score = product_data.get('매력도_점수', 75)
    price = product_data.get('예상_가격', '가격 미정')
    
    # 카테고리별 템플릿
    category_templates = {
        "스킨케어": {
            "title_templates": [
                f"{channel_name}이 매일 쓰는 {product_name}! 🌟",
                f"이게 {channel_name} 피부 비결? {product_name} 리뷰 💧",
                f"{channel_name} 추천 {product_name} 써봤더니... 🔥"
            ],
            "hashtags": ["#스킨케어", "#뷰티", "#연예인템", "#피부관리", "#케이뷰티", "#스킨케어루틴"],
            "caption_template": f"""
{channel_name}이 영상에서 직접 사용한 {product_name}!
피부가 정말 촉촉해 보여서 바로 검색해봤어요 😍

✨ 이 제품의 포인트
- {channel_name}이 실제로 사용하는 모습
- 자연스러운 추천 (매력도 {score}점!)
- 가격대: {price}

지금 쿠팡에서 확인해보세요! 💧
            """
        },
        "메이크업": {
            "title_templates": [
                f"{channel_name}의 메이크업 필수템! {product_name} 🎨",
                f"이 컬러 미쳤다! {channel_name} 추천 {product_name} 💄",
                f"{channel_name}이 쓰는 {product_name} 발색 실화? 🔥"
            ],
            "hashtags": ["#메이크업", "#뷰티", "#코스메틱", "#연예인템", "#메이크업템", "#뷰티템"],
            "caption_template": f"""
{channel_name}의 메이크업에서 발견한 {product_name}!
발색이 너무 예뻐서 깜짝 놀랐어요 💄

✨ 이 제품의 포인트  
- {channel_name} 실제 사용
- 자연스러운 추천 (매력도 {score}점!)
- 가격: {price}

쿠팡에서 바로 구매 가능! 🎨
            """
        },
        "패션": {
            "title_templates": [
                f"{channel_name} 스타일링! {product_name} 어디꺼? 👗",
                f"이 옷 정보 좀 주세요! {channel_name} 착용 {product_name} 💫",
                f"{channel_name}이 입은 {product_name} 너무 예뻐! 🔥"
            ],
            "hashtags": ["#패션", "#스타일링", "#연예인패션", "#OOTD", "#패션템", "#옷스타그램"],
            "caption_template": f"""
{channel_name}이 착용한 {product_name}!
스타일링이 너무 완벽해서 똑같이 입고 싶어요 👗

✨ 이 아이템의 포인트
- {channel_name} 실제 착용
- 자연스러운 스타일링 (매력도 {score}점!)  
- 가격: {price}

쿠팡에서 비슷한 제품 찾아보세요! ✨
            """
        },
        "향수": {
            "title_templates": [
                f"{channel_name}이 뿌리는 향수는? {product_name} 🌸",
                f"이 향 뭔지 알고싶다! {channel_name} 추천 {product_name} 💐",
                f"{channel_name} 시그니처 향! {product_name} 후기 🔥"
            ],
            "hashtags": ["#향수", "#퍼퓸", "#연예인향수", "#시그니처향", "#뷰티", "#향수추천"],
            "caption_template": f"""
{channel_name}이 사용하는 {product_name}!
영상에서 언급하는 걸 보고 너무 궁금했어요 🌸

✨ 이 향수의 포인트
- {channel_name} 실제 사용
- 자연스러운 추천 (매력도 {score}점!)
- 가격: {price}

쿠팡에서 확인해보세요! 💐
            """
        }
    }
    
    # 기본 템플릿 (카테고리가 없을 때)
    default_template = {
        "title_templates": [
            f"{channel_name}이 추천한 {product_name}! ⭐",
            f"이거 뭐야? {channel_name} 사용 {product_name} 💫",
            f"{channel_name} 픽! {product_name} 후기 🔥"
        ],
        "hashtags": ["#연예인템", "#추천템", "#뷰티", "#라이프스타일"],
        "caption_template": f"""
{channel_name}이 영상에서 사용한 {product_name}!
자연스럽게 언급하는 걸 보고 관심이 생겼어요 ✨

✨ 이 제품의 포인트
- {channel_name} 실제 사용
- 자연스러운 추천 (매력도 {score}점!)
- 가격: {price}

쿠팡에서 확인 가능해요! 🛒
        """
    }
    
    template = category_templates.get(category, default_template)
    
    # 콘텐츠 생성
    ai_content = {
        "titles": template["title_templates"],
        "selected_title": template["title_templates"][0],  # 첫 번째를 기본 선택
        "hashtags": template["hashtags"],
        "caption": template["caption_template"].strip(),
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "product_id": product_data.get('id', 'unknown'),
            "channel": channel_name,
            "category": category,
            "score": score
        }
    }
    
    return ai_content

def copy_to_clipboard(text, content_type="텍스트"):
    """클립보드에 텍스트 복사"""
    try:
        # pyperclip 사용 (크로스 플랫폼)
        pyperclip.copy(text)
        return True
    except:
        # pyperclip이 없거나 오류가 날 경우 세션 스테이트 사용
        st.session_state.clipboard_content = text
        return False

def render_title_section(ai_content, product_data):
    """제목 섹션 렌더링"""
    st.markdown("#### 📝 추천 제목")
    
    # 제목 옵션들
    titles = ai_content.get('titles', [])
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 제목 선택
        selected_title = st.selectbox(
            "제목 옵션 선택",
            titles,
            index=0,
            key="title_selector"
        )
        
        # 커스텀 제목 입력
        custom_title = st.text_input(
            "커스텀 제목 (선택사항)",
            placeholder="직접 제목을 입력하세요...",
            key="custom_title"
        )
        
        final_title = custom_title if custom_title else selected_title
        
        # 제목 미리보기
        st.markdown("**미리보기:**")
        st.markdown(f"> {final_title}")
    
    with col2:
        st.markdown("**액션**")
        
        if st.button("📋 제목 복사", key="copy_title_btn", use_container_width=True):
            if copy_to_clipboard(final_title, "제목"):
                st.success("✅ 제목이 복사되었습니다!")
            else:
                st.info("💾 제목이 임시 저장되었습니다.")
        
        if st.button("🔄 제목 재생성", key="regen_title_btn", use_container_width=True):
            st.info("🚧 제목 재생성 기능은 향후 AI 모델 연동 시 구현됩니다.")
        
        if st.button("💾 제목 저장", key="save_title_btn", use_container_width=True):
            # 세션 스테이트에 저장
            if 'saved_content' not in st.session_state:
                st.session_state.saved_content = {}
            st.session_state.saved_content['title'] = final_title
            st.success("✅ 제목이 저장되었습니다!")
    
    return final_title

def render_hashtags_section(ai_content, product_data):
    """해시태그 섹션 렌더링"""
    st.markdown("#### #️⃣ 해시태그")
    
    hashtags = ai_content.get('hashtags', [])
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 해시태그 선택 (다중 선택)
        selected_hashtags = st.multiselect(
            "해시태그 선택",
            hashtags,
            default=hashtags[:5],  # 처음 5개를 기본 선택
            key="hashtag_selector"
        )
        
        # 추가 해시태그 입력
        additional_hashtags = st.text_input(
            "추가 해시태그 (스페이스로 구분)",
            placeholder="#추가태그1 #추가태그2",
            key="additional_hashtags"
        )
        
        # 최종 해시태그 조합
        final_hashtags = selected_hashtags.copy()
        
        if additional_hashtags:
            # 해시태그 파싱
            extra_tags = re.findall(r'#[^\s#]+', additional_hashtags)
            final_hashtags.extend(extra_tags)
        
        hashtag_text = " ".join(final_hashtags)
        
        # 해시태그 미리보기
        st.markdown("**미리보기:**")
        st.markdown(f"> {hashtag_text}")
        
        # 글자 수 체크
        char_count = len(hashtag_text)
        if char_count > 100:
            st.warning(f"⚠️ 해시태그가 너무 깁니다. ({char_count}/100자)")
        else:
            st.info(f"📝 {char_count}/100자")
    
    with col2:
        st.markdown("**액션**")
        
        if st.button("📋 해시태그 복사", key="copy_hashtags_btn", use_container_width=True):
            if copy_to_clipboard(hashtag_text, "해시태그"):
                st.success("✅ 해시태그가 복사되었습니다!")
            else:
                st.info("💾 해시태그가 임시 저장되었습니다.")
        
        if st.button("🔄 태그 추천", key="suggest_hashtags_btn", use_container_width=True):
            st.info("🚧 해시태그 추천 기능은 향후 구현됩니다.")
        
        if st.button("💾 태그 저장", key="save_hashtags_btn", use_container_width=True):
            if 'saved_content' not in st.session_state:
                st.session_state.saved_content = {}
            st.session_state.saved_content['hashtags'] = hashtag_text
            st.success("✅ 해시태그가 저장되었습니다!")
    
    return final_hashtags

def render_caption_section(ai_content, product_data):
    """캡션 섹션 렌더링"""
    st.markdown("#### 📖 캡션")
    
    caption = ai_content.get('caption', '')
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 캡션 편집
        edited_caption = st.text_area(
            "캡션 편집",
            value=caption,
            height=200,
            key="caption_editor"
        )
        
        # 캡션 템플릿 선택
        template_options = {
            "기본형": "간단하고 직관적인 설명",
            "상세형": "자세한 제품 정보와 사용 후기",
            "감성형": "감성적이고 개인적인 톤",
            "정보형": "객관적이고 정보 중심적인 톤"
        }
        
        selected_template = st.selectbox(
            "캡션 템플릿",
            list(template_options.keys()),
            key="caption_template"
        )
        
        if st.button("📝 템플릿 적용", key="apply_template_btn"):
            st.info(f"🚧 {selected_template} 템플릿 적용 기능은 향후 구현됩니다.")
        
        # 글자 수 체크
        char_count = len(edited_caption)
        if char_count > 2000:
            st.warning(f"⚠️ 캡션이 너무 깁니다. ({char_count}/2000자)")
        else:
            st.info(f"📝 {char_count}/2000자")
    
    with col2:
        st.markdown("**액션**")
        
        if st.button("📋 캡션 복사", key="copy_caption_btn", use_container_width=True):
            if copy_to_clipboard(edited_caption, "캡션"):
                st.success("✅ 캡션이 복사되었습니다!")
            else:
                st.info("💾 캡션이 임시 저장되었습니다.")
        
        if st.button("🔄 캡션 재생성", key="regen_caption_btn", use_container_width=True):
            st.info("🚧 캡션 재생성 기능은 향후 AI 모델 연동 시 구현됩니다.")
        
        if st.button("💾 캡션 저장", key="save_caption_btn", use_container_width=True):
            if 'saved_content' not in st.session_state:
                st.session_state.saved_content = {}
            st.session_state.saved_content['caption'] = edited_caption
            st.success("✅ 캡션이 저장되었습니다!")
        
        if st.button("📱 SNS 프리셋", key="sns_preset_btn", use_container_width=True):
            st.info("🚧 SNS별 최적화 프리셋은 향후 구현됩니다.")
    
    return edited_caption

def render_complete_content_section(title, hashtags, caption):
    """완성된 콘텐츠 통합 뷰"""
    st.markdown("#### 🎯 완성된 콘텐츠")
    
    # 통합 콘텐츠 조합
    complete_content = f"{title}\n\n{caption}\n\n{' '.join(hashtags)}"
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("**최종 콘텐츠 미리보기:**")
        st.markdown("---")
        st.markdown(f"**{title}**")
        st.markdown("")
        st.markdown(caption)
        st.markdown("")
        st.markdown(' '.join(hashtags))
        st.markdown("---")
        
        # 통계
        total_chars = len(complete_content)
        st.info(f"📝 총 글자 수: {total_chars}자")
    
    with col2:
        st.markdown("**최종 액션**")
        
        if st.button("📋 전체 복사", key="copy_all_btn", use_container_width=True, type="primary"):
            if copy_to_clipboard(complete_content, "전체 콘텐츠"):
                st.success("✅ 전체 콘텐츠가 복사되었습니다!")
                st.balloons()
            else:
                st.info("💾 전체 콘텐츠가 임시 저장되었습니다.")
        
        if st.button("💾 전체 저장", key="save_all_btn", use_container_width=True):
            if 'saved_content' not in st.session_state:
                st.session_state.saved_content = {}
            st.session_state.saved_content['complete'] = complete_content
            st.success("✅ 전체 콘텐츠가 저장되었습니다!")
        
        if st.button("📤 내보내기", key="export_btn", use_container_width=True):
            # JSON 형태로 내보내기
            export_data = {
                "title": title,
                "caption": caption,
                "hashtags": hashtags,
                "complete_content": complete_content,
                "exported_at": datetime.now().isoformat()
            }
            
            json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="📁 JSON 다운로드",
                data=json_str,
                file_name=f"ai_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_json_btn"
            )

def render_ai_content_display(product_data):
    """AI 생성 콘텐츠 메인 컴포넌트"""
    st.markdown("## 🤖 AI 생성 콘텐츠")
    
    # AI 콘텐츠 생성
    ai_content = generate_ai_content(product_data)
    
    # 안내 메시지
    st.info(f"""
    🤖 **AI가 생성한 콘텐츠입니다**  
    제품: {product_data.get('제품명', '제품명')} | 채널: {product_data.get('채널명', '채널명')}  
    매력도 점수: {product_data.get('매력도_점수', 0)}점을 바탕으로 최적화된 콘텐츠를 생성했습니다.
    """)
    
    # 탭으로 구분
    tab1, tab2, tab3, tab4 = st.tabs(["📝 제목", "#️⃣ 해시태그", "📖 캡션", "🎯 완성본"])
    
    with tab1:
        final_title = render_title_section(ai_content, product_data)
    
    with tab2:
        final_hashtags = render_hashtags_section(ai_content, product_data)
    
    with tab3:
        final_caption = render_caption_section(ai_content, product_data)
    
    with tab4:
        render_complete_content_section(final_title, final_hashtags, final_caption)
    
    # 저장된 콘텐츠 표시
    if 'saved_content' in st.session_state and st.session_state.saved_content:
        st.markdown("---")
        st.markdown("### 💾 저장된 콘텐츠")
        
        saved = st.session_state.saved_content
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'title' in saved:
                st.markdown("**저장된 제목:**")
                st.code(saved['title'])
        
        with col2:
            if 'hashtags' in saved:
                st.markdown("**저장된 해시태그:**")
                st.code(saved['hashtags'])
        
        with col3:
            if 'caption' in saved:
                st.markdown("**저장된 캡션:**")
                st.code(saved['caption'][:100] + "..." if len(saved['caption']) > 100 else saved['caption'])
        
        if st.button("🗑️ 저장된 콘텐츠 지우기", key="clear_saved_btn"):
            st.session_state.saved_content = {}
            st.rerun()

if __name__ == "__main__":
    # 테스트용 샘플 데이터
    sample_product = {
        "id": "PROD_001",
        "제품명": "히알루론산 세럼 - 프리미엄",
        "채널명": "홍지윤 Yoon",
        "카테고리": "스킨케어",
        "매력도_점수": 85.3,
        "예상_가격": "45,000원"
    }
    
    render_ai_content_display(sample_product)