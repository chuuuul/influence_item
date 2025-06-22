"""
T07_S01_M02: AI Generated Content Display Component
PRD SPEC-DASH-03 요구사항에 따라 AI가 생성한 모든 콘텐츠 정보를 복사 기능과 함께 제공
"""

import streamlit as st
import json
import re
from datetime import datetime
import pyperclip
import os
from typing import Dict, List, Any, Optional

def extract_ai_content_from_json_schema(candidate_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    PRD JSON 스키마에서 AI 생성 콘텐츠 추출
    candidate_data: PRD JSON 스키마 구조의 데이터
    """
    if not candidate_data or 'candidate_info' not in candidate_data:
        return {
            'recommended_titles': [],
            'recommended_hashtags': [],
            'summary_for_caption': '',
            'hook_sentence': '',
            'target_audience': [],
            'price_point': '',
            'endorsement_type': ''
        }
    
    candidate_info = candidate_data['candidate_info']
    
    return {
        'recommended_titles': candidate_info.get('recommended_titles', []),
        'recommended_hashtags': candidate_info.get('recommended_hashtags', []),
        'summary_for_caption': candidate_info.get('summary_for_caption', ''),
        'hook_sentence': candidate_info.get('hook_sentence', ''),
        'target_audience': candidate_info.get('target_audience', []),
        'price_point': candidate_info.get('price_point', ''),
        'endorsement_type': candidate_info.get('endorsement_type', '')
    }

def copy_to_clipboard_with_feedback(text: str, content_type: str = "텍스트") -> None:
    """클립보드 복사 및 피드백 표시"""
    try:
        # JavaScript를 통한 클립보드 API 사용 (Streamlit 환경에서 더 안정적)
        st.write(f"""
        <script>
        navigator.clipboard.writeText(`{text.replace('`', '\\`')}`).then(function() {{
            console.log('복사 성공: {content_type}');
        }}).catch(function(err) {{
            console.error('복사 실패: ', err);
        }});
        </script>
        """, unsafe_allow_html=True)
        
        # 백업: pyperclip 사용
        pyperclip.copy(text)
        st.success(f"✅ {content_type}이(가) 복사되었습니다!")
        
    except Exception as e:
        # 세션 스테이트에 저장
        if 'clipboard_content' not in st.session_state:
            st.session_state.clipboard_content = {}
        st.session_state.clipboard_content[content_type] = text
        st.info(f"💾 {content_type}이(가) 임시 저장되었습니다. (복사 기능 제한)")

def render_ai_titles_section(ai_content: Dict[str, Any]) -> None:
    """AI 생성 제목 목록 표시 및 개별 복사 기능"""
    st.markdown("### 📝 AI 생성 제목")
    
    titles = ai_content.get('recommended_titles', [])
    
    if not titles:
        st.warning("⚠️ AI 생성 제목이 없습니다.")
        return
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown("**추천 제목 목록:**")
        for i, title in enumerate(titles, 1):
            st.markdown(f"`{i}.` {title}")
    
    with col2:
        st.markdown("**복사 액션**")
        for i, title in enumerate(titles, 1):
            if st.button(f"📋 제목 {i}", key=f"copy_title_{i}", use_container_width=True):
                copy_to_clipboard_with_feedback(title, f"제목 {i}")

def render_ai_hashtags_section(ai_content: Dict[str, Any]) -> None:
    """AI 생성 해시태그 표시 및 전체 복사 기능"""
    st.markdown("### #️⃣ AI 생성 해시태그")
    
    hashtags = ai_content.get('recommended_hashtags', [])
    
    if not hashtags:
        st.warning("⚠️ AI 생성 해시태그가 없습니다.")
        return
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        # 해시태그를 보기 좋게 표시
        hashtag_text = " ".join(hashtags)
        st.markdown("**생성된 해시태그:**")
        st.markdown(f"> {hashtag_text}")
        
        # 개별 해시태그 표시
        st.markdown("**개별 해시태그:**")
        for hashtag in hashtags:
            st.markdown(f"• `{hashtag}`")
    
    with col2:
        st.markdown("**복사 액션**")
        
        # 전체 해시태그 복사
        if st.button("📋 전체 복사", key="copy_all_hashtags", use_container_width=True, type="primary"):
            copy_to_clipboard_with_feedback(hashtag_text, "해시태그 전체")
        
        # 개별 해시태그 복사
        st.markdown("**개별 복사:**")
        for i, hashtag in enumerate(hashtags):
            if st.button(f"`{hashtag[:8]}...`", key=f"copy_hashtag_{i}", use_container_width=True):
                copy_to_clipboard_with_feedback(hashtag, f"해시태그 '{hashtag}'")

def render_ai_caption_section(ai_content: Dict[str, Any]) -> None:
    """AI 생성 캡션/요약 표시 및 복사 기능"""
    st.markdown("### 📖 AI 생성 캡션")
    
    summary = ai_content.get('summary_for_caption', '')
    
    if not summary:
        st.warning("⚠️ AI 생성 캡션이 없습니다.")
        return
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown("**캡션용 요약:**")
        st.text_area("", value=summary, height=150, disabled=True, key="caption_display")
        
        # 글자 수 표시
        char_count = len(summary)
        st.info(f"📝 총 {char_count}자")
    
    with col2:
        st.markdown("**복사 액션**")
        
        if st.button("📋 캡션 복사", key="copy_caption", use_container_width=True, type="primary"):
            copy_to_clipboard_with_feedback(summary, "캡션")

def render_hook_sentence_section(ai_content: Dict[str, Any]) -> None:
    """후크 문장 표시 및 복사 기능"""
    st.markdown("### 🎣 후크 문장")
    
    hook = ai_content.get('hook_sentence', '')
    
    if not hook:
        st.warning("⚠️ 후크 문장이 없습니다.")
        return
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown("**후크 문장:**")
        st.markdown(f"> {hook}")
    
    with col2:
        st.markdown("**복사 액션**")
        
        if st.button("📋 후크 복사", key="copy_hook", use_container_width=True, type="primary"):
            copy_to_clipboard_with_feedback(hook, "후크 문장")

def render_additional_info_section(ai_content: Dict[str, Any]) -> None:
    """추가 정보 표시 (타겟 오디언스, 가격대 등)"""
    st.markdown("### ℹ️ 추가 정보")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        target_audience = ai_content.get('target_audience', [])
        if target_audience:
            st.markdown("**타겟 오디언스:**")
            for audience in target_audience:
                st.markdown(f"• {audience}")
    
    with col2:
        price_point = ai_content.get('price_point', '')
        if price_point:
            st.markdown("**가격대:**")
            st.markdown(f"• {price_point}")
    
    with col3:
        endorsement_type = ai_content.get('endorsement_type', '')
        if endorsement_type:
            st.markdown("**추천 유형:**")
            st.markdown(f"• {endorsement_type}")

def render_empty_state() -> None:
    """빈 데이터 상태 처리"""
    st.warning("⚠️ AI 생성 콘텐츠가 없습니다.")
    st.info("""
    **가능한 원인:**
    • 아직 AI 분석이 완료되지 않았습니다
    • 데이터 구조에 문제가 있습니다
    • candidate_info 섹션이 누락되었습니다
    """)

def render_ai_content_display_component(candidate_data: Dict[str, Any]) -> None:
    """
    PRD JSON 스키마 기반 AI 콘텐츠 표시 메인 컴포넌트
    SPEC-DASH-03 요구사항 구현
    """
    st.markdown("## 🤖 AI 생성 콘텐츠")
    
    # AI 콘텐츠 추출
    ai_content = extract_ai_content_from_json_schema(candidate_data)
    
    # 데이터 검증
    has_content = any([
        ai_content.get('recommended_titles'),
        ai_content.get('recommended_hashtags'),
        ai_content.get('summary_for_caption'),
        ai_content.get('hook_sentence')
    ])
    
    if not has_content:
        render_empty_state()
        return
    
    # 소스 정보 표시
    if 'source_info' in candidate_data:
        source_info = candidate_data['source_info']
        st.info(f"""
        🎬 **소스 정보**  
        연예인: {source_info.get('celebrity_name', 'N/A')} | 
        채널: {source_info.get('channel_name', 'N/A')} | 
        영상: {source_info.get('video_title', 'N/A')[:50]}...
        """)
    
    # 탭 구성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 제목", "#️⃣ 해시태그", "📖 캡션", "🎣 후크", "ℹ️ 추가정보"
    ])
    
    with tab1:
        render_ai_titles_section(ai_content)
    
    with tab2:
        render_ai_hashtags_section(ai_content)
    
    with tab3:
        render_ai_caption_section(ai_content)
    
    with tab4:
        render_hook_sentence_section(ai_content)
    
    with tab5:
        render_additional_info_section(ai_content)
    
    # 전체 콘텐츠 통합 복사
    st.markdown("---")
    st.markdown("### 🎯 통합 콘텐츠")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 통합 콘텐츠 구성
        titles = ai_content.get('recommended_titles', [])
        hashtags = ai_content.get('recommended_hashtags', [])
        caption = ai_content.get('summary_for_caption', '')
        hook = ai_content.get('hook_sentence', '')
        
        complete_content = ""
        if titles:
            complete_content += f"제목: {titles[0]}\n\n"
        if hook:
            complete_content += f"후크: {hook}\n\n"
        if caption:
            complete_content += f"캡션:\n{caption}\n\n"
        if hashtags:
            complete_content += f"해시태그: {' '.join(hashtags)}"
        
        st.text_area("완성된 콘텐츠 미리보기", value=complete_content, height=200, disabled=True)
    
    with col2:
        st.markdown("**통합 액션**")
        
        if st.button("📋 전체 복사", key="copy_complete_content", use_container_width=True, type="primary"):
            copy_to_clipboard_with_feedback(complete_content, "전체 콘텐츠")
            st.balloons()  # 성공 피드백

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

# 모바일 환경에서의 복사 기능 최적화
def render_mobile_optimized_copy_section() -> None:
    """모바일 터치 인터페이스 최적화"""
    if st.session_state.get('is_mobile', False):
        st.markdown("""
        <style>
        .stButton > button {
            height: 3rem;
            font-size: 1.1rem;
            border-radius: 0.5rem;
        }
        .mobile-copy-zone {
            padding: 1rem;
            background-color: #f0f2f6;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
        }
        </style>
        """, unsafe_allow_html=True)

def add_mobile_detection_script() -> None:
    """모바일 환경 감지 스크립트 추가"""
    st.markdown("""
    <script>
    // 모바일 환경 감지
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    if (isMobile) {
        // Streamlit session state에 모바일 정보 전달
        const stateEvent = new CustomEvent('streamlit:setState', {
            detail: { is_mobile: true }
        });
        window.dispatchEvent(stateEvent);
    }
    </script>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    # PRD JSON 스키마 기반 테스트 데이터
    sample_candidate_data = {
        "source_info": {
            "celebrity_name": "강민경",
            "channel_name": "걍밍경",
            "video_title": "파리 출장 다녀왔습니다 VLOG",
            "video_url": "https://www.youtube.com/watch?v=...",
            "upload_date": "2025-06-22"
        },
        "candidate_info": {
            "product_name_ai": "아비에무아 숄더백 (베이지)",
            "product_name_manual": None,
            "clip_start_time": 315,
            "clip_end_time": 340,
            "category_path": ["패션잡화", "여성가방", "숄더백"],
            "features": ["수납이 넉넉해요", "가죽이 부드러워요"],
            "score_details": {
                "total": 88,
                "sentiment_score": 0.9,
                "endorsement_score": 0.85,
                "influencer_score": 0.9
            },
            "hook_sentence": "강민경이 '이것만 쓴다'고 말한 바로 그 숄더백?",
            "summary_for_caption": "사복 장인 강민경 님의 데일리백 정보! 넉넉한 수납과 부드러운 가죽이 특징인 아비에무아 숄더백이라고 해요. 어떤 옷에나 잘 어울려서 매일 손이 가는 찐 애정템이라고 하네요.",
            "target_audience": ["20대 후반 여성", "30대 직장인", "미니멀룩 선호자"],
            "price_point": "프리미엄",
            "endorsement_type": "습관적 사용",
            "recommended_titles": [
                "요즘 강민경이 매일 드는 '그 가방' 정보 (바로가기)",
                "사복 장인 강민경의 찐 애정템! 아비에무아 숄더백",
                "여름 데일리백 고민 끝! 강민경 PICK 가방 추천"
            ],
            "recommended_hashtags": [
                "#강민경",
                "#걍밍경", 
                "#강민경패션",
                "#아비에무아",
                "#숄더백추천",
                "#여름가방",
                "#데일리백",
                "#연예인패션"
            ]
        },
        "monetization_info": {
            "is_coupang_product": True,
            "coupang_url_ai": "https://link.coupang.com/...",
            "coupang_url_manual": None
        },
        "status_info": {
            "current_status": "needs_review",
            "is_ppl": False,
            "ppl_confidence": 0.1
        }
    }
    
    # 모바일 감지 스크립트 추가
    add_mobile_detection_script()
    
    # 메인 컴포넌트 테스트
    st.title("🧪 AI 콘텐츠 표시 컴포넌트 테스트")
    
    render_ai_content_display_component(sample_candidate_data)
    
    # 레거시 테스트 (기존 구조 호환성)
    st.markdown("---")
    st.markdown("## 🔄 레거시 구조 테스트")
    
    legacy_product = {
        "id": "PROD_001",
        "제품명": "히알루론산 세럼 - 프리미엄", 
        "채널명": "홍지윤 Yoon",
        "카테고리": "스킨케어",
        "매력도_점수": 85.3,
        "예상_가격": "45,000원"
    }
    
    render_ai_content_display(legacy_product)