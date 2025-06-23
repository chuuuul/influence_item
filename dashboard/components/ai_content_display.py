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
import uuid
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
    """향상된 클립보드 복사 및 토스트 피드백 표시"""
    try:
        # 텍스트 전처리 (특수문자 및 줄바꿈 처리)
        safe_text = text.replace('`', '\\`').replace('\n', '\\n').replace('\r', '').replace('"', '\\"')
        
        # 향상된 JavaScript 클립보드 API 사용
        st.markdown(f"""
        <script>
        // 클립보드 복사 함수
        async function copyToClipboard(text, contentType) {{
            try {{
                // 최신 브라우저의 Clipboard API 사용
                if (navigator.clipboard && window.isSecureContext) {{
                    await navigator.clipboard.writeText(text);
                    showToast('✅ ' + contentType + ' 복사 완료!', 'success');
                }} else {{
                    // 레거시 브라우저 지원
                    const textArea = document.createElement('textarea');
                    textArea.value = text;
                    textArea.style.position = 'fixed';
                    textArea.style.opacity = '0';
                    document.body.appendChild(textArea);
                    textArea.focus();
                    textArea.select();
                    
                    try {{
                        const successful = document.execCommand('copy');
                        if (successful) {{
                            showToast('✅ ' + contentType + ' 복사 완료!', 'success');
                        }} else {{
                            throw new Error('execCommand failed');
                        }}
                    }} catch (err) {{
                        showToast('⚠️ 복사 실패. 수동으로 복사해주세요.', 'warning');
                    }} finally {{
                        document.body.removeChild(textArea);
                    }}
                }}
            }} catch (err) {{
                console.error('복사 실패:', err);
                showToast('⚠️ 복사 실패. 브라우저가 지원하지 않습니다.', 'error');
            }}
        }}
        
        // 토스트 알림 표시 함수
        function showToast(message, type = 'info') {{
            // 기존 토스트 제거
            const existingToast = document.querySelector('.ai-content-toast');
            if (existingToast) {{
                existingToast.remove();
            }}
            
            // 토스트 엘리먼트 생성
            const toast = document.createElement('div');
            toast.className = 'ai-content-toast ai-toast-' + type;
            toast.innerHTML = message;
            
            // 토스트 스타일 적용
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: ${{type === 'success' ? '#d4edda' : type === 'warning' ? '#fff3cd' : type === 'error' ? '#f8d7da' : '#d1ecf1'}};
                color: ${{type === 'success' ? '#155724' : type === 'warning' ? '#856404' : type === 'error' ? '#721c24' : '#0c5460'}};
                border: 1px solid ${{type === 'success' ? '#c3e6cb' : type === 'warning' ? '#ffeaa7' : type === 'error' ? '#f5c6cb' : '#bee5eb'}};
                padding: 12px 20px;
                border-radius: 6px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 9999;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
                max-width: 300px;
                animation: slideInRight 0.3s ease-out;
            `;
            
            // 애니메이션 키프레임 추가
            if (!document.querySelector('#toast-animations')) {{
                const style = document.createElement('style');
                style.id = 'toast-animations';
                style.textContent = `
                    @keyframes slideInRight {{
                        from {{ transform: translateX(100%); opacity: 0; }}
                        to {{ transform: translateX(0); opacity: 1; }}
                    }}
                    @keyframes slideOutRight {{
                        from {{ transform: translateX(0); opacity: 1; }}
                        to {{ transform: translateX(100%); opacity: 0; }}
                    }}
                `;
                document.head.appendChild(style);
            }}
            
            // 토스트 표시
            document.body.appendChild(toast);
            
            // 3초 후 자동 제거
            setTimeout(() => {{
                toast.style.animation = 'slideOutRight 0.3s ease-in';
                setTimeout(() => {{
                    if (toast.parentNode) {{
                        toast.parentNode.removeChild(toast);
                    }}
                }}, 300);
            }}, 3000);
        }}
        
        // 복사 실행
        copyToClipboard(`{safe_text}`, `{content_type}`);
        </script>
        """, unsafe_allow_html=True)
        
        # 백업: pyperclip 사용 (서버 사이드)
        try:
            pyperclip.copy(text)
        except:
            pass  # pyperclip 실패해도 JavaScript 버전이 있으므로 계속 진행
        
        # 세션 스테이트에 복사 기록 저장
        if 'clipboard_history' not in st.session_state:
            st.session_state.clipboard_history = []
        
        st.session_state.clipboard_history.append({
            'content': text[:100] + "..." if len(text) > 100 else text,
            'type': content_type,
            'timestamp': datetime.now().isoformat(),
            'length': len(text)
        })
        
        # 기록은 최대 10개까지만 유지
        if len(st.session_state.clipboard_history) > 10:
            st.session_state.clipboard_history = st.session_state.clipboard_history[-10:]
        
    except Exception as e:
        # 완전한 실패 상황 - 세션 스테이트에만 저장
        if 'clipboard_content' not in st.session_state:
            st.session_state.clipboard_content = {}
        st.session_state.clipboard_content[content_type] = text
        
        st.error(f"❌ {content_type} 복사에 실패했습니다. 수동으로 복사해주세요.")
        st.code(text)

def save_content_edit_history(content_id: str, content_type: str, original_content: str, edited_content: str, edit_reason: str = "") -> None:
    """콘텐츠 수정 이력 저장"""
    if 'content_edit_history' not in st.session_state:
        st.session_state.content_edit_history = {}
    
    if content_id not in st.session_state.content_edit_history:
        st.session_state.content_edit_history[content_id] = []
    
    edit_record = {
        'edit_id': str(uuid.uuid4()),
        'timestamp': datetime.now().isoformat(),
        'content_type': content_type,
        'original_content': original_content,
        'edited_content': edited_content,
        'edit_reason': edit_reason,
        'char_diff': len(edited_content) - len(original_content)
    }
    
    st.session_state.content_edit_history[content_id].append(edit_record)
    
    # 최대 20개 기록까지만 유지
    if len(st.session_state.content_edit_history[content_id]) > 20:
        st.session_state.content_edit_history[content_id] = st.session_state.content_edit_history[content_id][-20:]

def render_inline_editor(content_id: str, content_type: str, original_content: str, 
                        placeholder: str = "", max_length: int = 2000, height: int = 100) -> str:
    """인라인 편집 컴포넌트"""
    
    # 세션 스테이트에서 편집된 콘텐츠 가져오기
    edit_key = f"edited_{content_id}_{content_type}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = original_content
    
    # 편집 모드 토글
    edit_mode_key = f"edit_mode_{content_id}_{content_type}"
    if edit_mode_key not in st.session_state:
        st.session_state[edit_mode_key] = False
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        if st.session_state[edit_mode_key]:
            # 편집 모드
            if content_type in ['title', 'hook']:
                edited_content = st.text_input(
                    f"{content_type} 편집",
                    value=st.session_state[edit_key],
                    placeholder=placeholder,
                    max_chars=max_length,
                    key=f"editor_{content_id}_{content_type}",
                    label_visibility="collapsed"
                )
            else:
                edited_content = st.text_area(
                    f"{content_type} 편집", 
                    value=st.session_state[edit_key],
                    placeholder=placeholder,
                    max_chars=max_length,
                    height=height,
                    key=f"editor_{content_id}_{content_type}",
                    label_visibility="collapsed"
                )
            
            # 실시간 글자 수 체크
            char_count = len(edited_content)
            if char_count > max_length * 0.9:
                st.warning(f"⚠️ {char_count}/{max_length}자 (한계에 근접)")
            else:
                st.info(f"📝 {char_count}/{max_length}자")
            
        else:
            # 읽기 모드
            if content_type in ['title', 'hook']:
                st.markdown(f"**{st.session_state[edit_key]}**")
            else:
                st.text_area(
                    "",
                    value=st.session_state[edit_key],
                    height=height,
                    disabled=True,
                    key=f"display_{content_id}_{content_type}",
                    label_visibility="collapsed"
                )
    
    with col2:
        if st.session_state[edit_mode_key]:
            # 편집 모드 버튼들
            if st.button("💾 저장", key=f"save_{content_id}_{content_type}", use_container_width=True, type="primary"):
                # 변경사항이 있으면 이력 저장
                if st.session_state[edit_key] != original_content:
                    save_content_edit_history(
                        content_id, content_type, 
                        original_content, st.session_state[edit_key],
                        "수동 편집"
                    )
                st.session_state[edit_mode_key] = False
                st.success(f"✅ {content_type} 저장됨")
                st.rerun()
            
            if st.button("❌ 취소", key=f"cancel_{content_id}_{content_type}", use_container_width=True):
                st.session_state[edit_key] = original_content
                st.session_state[edit_mode_key] = False
                st.rerun()
            
            if st.button("🔄 원본복원", key=f"reset_{content_id}_{content_type}", use_container_width=True):
                st.session_state[edit_key] = original_content
                st.info("원본으로 복원됨")
                st.rerun()
        
        else:
            # 읽기 모드 버튼들
            if st.button("✏️ 편집", key=f"edit_{content_id}_{content_type}", use_container_width=True):
                st.session_state[edit_mode_key] = True
                st.rerun()
            
            if st.button("📋 복사", key=f"copy_{content_id}_{content_type}", use_container_width=True, type="primary"):
                copy_to_clipboard_with_feedback(st.session_state[edit_key], content_type)
    
    return st.session_state[edit_key]

def render_edit_history_sidebar(content_id: str) -> None:
    """수정 이력 사이드바 표시"""
    if 'content_edit_history' not in st.session_state or content_id not in st.session_state.content_edit_history:
        st.info("수정 이력이 없습니다.")
        return
    
    history = st.session_state.content_edit_history[content_id]
    
    st.markdown("### 📋 수정 이력")
    
    for i, record in enumerate(reversed(history[-5:]), 1):  # 최근 5개만 표시
        with st.expander(f"{i}. {record['content_type']} ({record['timestamp'][:16]})"):
            st.markdown(f"**변경 이유:** {record['edit_reason']}")
            st.markdown(f"**글자 수 변화:** {record['char_diff']:+d}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**원본:**")
                st.code(record['original_content'][:100] + "..." if len(record['original_content']) > 100 else record['original_content'])
            
            with col2:
                st.markdown("**수정 후:**")  
                st.code(record['edited_content'][:100] + "..." if len(record['edited_content']) > 100 else record['edited_content'])

def render_content_templates_panel() -> Dict[str, str]:
    """콘텐츠 템플릿 패널"""
    st.markdown("### 🎨 템플릿")
    
    templates = {
        "인플루언서 스타일": {
            "title": "{celebrity}이 실제로 쓰는 {product}! 😍",
            "caption": "{celebrity}님이 영상에서 실제로 사용하는 모습을 보고 너무 궁금해서 찾아봤어요! ✨\n\n이 제품의 특징:\n• 실제 사용 모습 공개\n• 자연스러운 추천\n• 믿을만한 후기\n\n지금 쿠팡에서 확인해보세요! 🛒",
            "hashtags": ["#{celebrity}", "#{celebrity}템", "#연예인추천", "#뷰티템", "#인기템"]
        },
        "정보 중심형": {
            "title": "{product} 상세 정보 및 구매 가이드",
            "caption": "{celebrity}님이 사용한 {product}에 대한 상세 정보를 정리해드려요.\n\n제품 특징:\n• 브랜드: {brand}\n• 카테고리: {category}\n• 가격대: {price}\n\n구매 링크는 프로필에서 확인하세요! 📎",
            "hashtags": ["#제품정보", "#구매가이드", "#{category}", "#추천템", "#정보공유"]
        },
        "감성적 스타일": {
            "title": "요즘 내가 푹 빠진 {product} 💕",
            "caption": "{celebrity}님이 쓰는 걸 보고 나도 모르게 주문했던 {product} 💕\n\n써보니까 정말 좋더라구요!\n특히 이런 점이 마음에 들어요:\n✨ {feature1}\n✨ {feature2}\n\n같이 써보실 분들 있나요? 🤗",
            "hashtags": ["#일상", "#추천템", "#좋아요", "#공유", "#{product}"]
        }
    }
    
    template_name = st.selectbox(
        "템플릿 선택",
        ["사용자 정의"] + list(templates.keys()),
        key="template_selector"
    )
    
    if template_name != "사용자 정의":
        template = templates[template_name]
        
        st.markdown("**미리보기:**")
        st.info(f"제목: {template['title']}")
        st.info(f"캡션: {template['caption'][:100]}...")
        st.info(f"해시태그: {' '.join(template['hashtags'][:3])}...")
        
        if st.button("📋 템플릿 적용", key="apply_template", use_container_width=True):
            return template
    
    return {}

def render_enhanced_ai_content_management(candidate_data: Dict[str, Any]) -> None:
    """
    향상된 AI 콘텐츠 관리 인터페이스 - T01_S02_M02 구현
    PRD SPEC-DASH-03 요구사항에 따른 완전한 AI 콘텐츠 관리 시스템
    """
    st.markdown("## 🤖 AI 콘텐츠 관리 인터페이스 v2.0")
    
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
    
    # 콘텐츠 ID 생성 (영상별 고유 ID)
    content_id = candidate_data.get('source_info', {}).get('video_url', 'unknown').split('=')[-1][:8]
    
    # 소스 정보 표시
    if 'source_info' in candidate_data:
        source_info = candidate_data['source_info']
        st.info(f"""
        🎬 **소스 정보**  
        연예인: {source_info.get('celebrity_name', 'N/A')} | 
        채널: {source_info.get('channel_name', 'N/A')} | 
        영상: {source_info.get('video_title', 'N/A')[:50]}...
        """)
    
    # 메인 레이아웃: 컨텐츠 관리 + 사이드바
    col_main, col_sidebar = st.columns([3, 1])
    
    with col_main:
        # 탭 구성: 편집 인터페이스
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📝 제목 관리", "#️⃣ 해시태그 관리", "📖 캡션 관리", "🎣 후크 관리", "🎯 통합 미리보기"
        ])
        
        with tab1:
            st.markdown("### 📝 제목 관리")
            titles = ai_content.get('recommended_titles', [])
            
            if titles:
                # 다중 제목 선택 및 편집
                for i, title in enumerate(titles):
                    st.markdown(f"**제목 옵션 {i+1}:**")
                    edited_title = render_inline_editor(
                        content_id, f"title_{i}", title, 
                        "제목을 입력하세요...", 100, 50
                    )
                
                # 커스텀 제목 추가
                st.markdown("---")
                st.markdown("**새 제목 추가:**")
                render_inline_editor(
                    content_id, "custom_title", "", 
                    "새로운 제목을 입력하세요...", 100, 50
                )
            else:
                st.warning("⚠️ AI 생성 제목이 없습니다.")
        
        with tab2:
            st.markdown("### #️⃣ 해시태그 관리")
            hashtags = ai_content.get('recommended_hashtags', [])
            
            if hashtags:
                # 해시태그 편집
                hashtag_text = " ".join(hashtags)
                edited_hashtags = render_inline_editor(
                    content_id, "hashtags", hashtag_text,
                    "해시태그를 입력하세요 (#태그1 #태그2 형식)", 500, 100
                )
                
                # 해시태그 유효성 검사
                parsed_hashtags = re.findall(r'#[^\s#]+', edited_hashtags)
                if len(parsed_hashtags) != len(edited_hashtags.split()):
                    st.warning("⚠️ 해시태그는 #을 포함해야 하며 공백으로 구분해주세요.")
                
                st.info(f"📊 해시태그 개수: {len(parsed_hashtags)} | 총 글자수: {len(edited_hashtags)}")
            else:
                st.warning("⚠️ AI 생성 해시태그가 없습니다.")
        
        with tab3:
            st.markdown("### 📖 캡션 관리")
            caption = ai_content.get('summary_for_caption', '')
            
            if caption:
                edited_caption = render_inline_editor(
                    content_id, "caption", caption,
                    "캡션을 입력하세요...", 2000, 200
                )
                
                # 캡션 분석
                lines = edited_caption.split('\n')
                words = len(edited_caption.split())
                st.info(f"📊 줄 수: {len(lines)} | 단어 수: {words} | 글자 수: {len(edited_caption)}")
            else:
                st.warning("⚠️ AI 생성 캡션이 없습니다.")
        
        with tab4:
            st.markdown("### 🎣 후크 문장 관리")
            hook = ai_content.get('hook_sentence', '')
            
            if hook:
                edited_hook = render_inline_editor(
                    content_id, "hook", hook,
                    "후크 문장을 입력하세요...", 200, 80
                )
            else:
                st.warning("⚠️ 후크 문장이 없습니다.")
        
        with tab5:
            st.markdown("### 🎯 통합 미리보기")
            
            # 최종 편집된 콘텐츠 수집
            final_content = {}
            
            # 제목들 수집
            titles = ai_content.get('recommended_titles', [])
            final_titles = []
            for i in range(len(titles)):
                title_key = f"edited_{content_id}_title_{i}"
                if title_key in st.session_state:
                    final_titles.append(st.session_state[title_key])
            
            # 커스텀 제목
            custom_title_key = f"edited_{content_id}_custom_title"
            if custom_title_key in st.session_state and st.session_state[custom_title_key]:
                final_titles.append(st.session_state[custom_title_key])
            
            # 해시태그
            hashtags_key = f"edited_{content_id}_hashtags"
            final_hashtags = st.session_state.get(hashtags_key, " ".join(ai_content.get('recommended_hashtags', [])))
            
            # 캡션
            caption_key = f"edited_{content_id}_caption"
            final_caption = st.session_state.get(caption_key, ai_content.get('summary_for_caption', ''))
            
            # 후크
            hook_key = f"edited_{content_id}_hook"
            final_hook = st.session_state.get(hook_key, ai_content.get('hook_sentence', ''))
            
            # 미리보기 표시
            st.markdown("**📱 SNS 포스트 미리보기:**")
            
            with st.container():
                st.markdown("""
                <div style="border: 2px solid #e1e1e1; border-radius: 10px; padding: 20px; margin: 10px 0;">
                """, unsafe_allow_html=True)
                
                # 제목 선택
                if final_titles:
                    selected_title = st.selectbox("사용할 제목 선택:", final_titles, key="preview_title_select")
                    st.markdown(f"### {selected_title}")
                
                # 후크 문장 표시
                if final_hook:
                    st.markdown(f"*{final_hook}*")
                    st.markdown("")
                
                # 캡션 표시
                if final_caption:
                    st.markdown(final_caption)
                    st.markdown("")
                
                # 해시태그 표시
                if final_hashtags:
                    st.markdown(f"**{final_hashtags}**")
                
                st.markdown("</div>", unsafe_allow_html=True)
            
            # 통합 액션 버튼들
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 전체 복사", key="copy_integrated", use_container_width=True, type="primary"):
                    complete_content = ""
                    if final_titles and 'selected_title' in locals():
                        complete_content += f"{selected_title}\n\n"
                    if final_hook:
                        complete_content += f"{final_hook}\n\n"
                    if final_caption:
                        complete_content += f"{final_caption}\n\n"
                    if final_hashtags:
                        complete_content += final_hashtags
                    
                    copy_to_clipboard_with_feedback(complete_content, "통합 콘텐츠")
            
            with col2:
                if st.button("💾 콘텐츠 저장", key="save_integrated", use_container_width=True):
                    # 세션 스테이트에 최종 콘텐츠 저장
                    if 'saved_integrated_content' not in st.session_state:
                        st.session_state.saved_integrated_content = {}
                    
                    st.session_state.saved_integrated_content[content_id] = {
                        'titles': final_titles,
                        'hashtags': final_hashtags,
                        'caption': final_caption,
                        'hook': final_hook,
                        'saved_at': datetime.now().isoformat()
                    }
                    st.success("✅ 통합 콘텐츠가 저장되었습니다!")
            
            with col3:
                # JSON 내보내기
                export_data = {
                    'content_id': content_id,
                    'source_info': candidate_data.get('source_info', {}),
                    'edited_content': {
                        'titles': final_titles,
                        'hashtags': final_hashtags,
                        'caption': final_caption,
                        'hook': final_hook
                    },
                    'export_timestamp': datetime.now().isoformat()
                }
                
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📤 JSON 내보내기",
                    data=json_str,
                    file_name=f"ai_content_{content_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="export_integrated",
                    use_container_width=True
                )
    
    with col_sidebar:
        # 사이드바: 템플릿, 이력, 도구
        st.markdown("### 🛠️ 관리 도구")
        
        # 템플릿 패널
        with st.expander("🎨 템플릿 적용", expanded=False):
            template = render_content_templates_panel()
            if template:
                st.success("템플릿이 적용되었습니다!")
                # 템플릿 적용 로직은 향후 구현
        
        # 수정 이력
        with st.expander("📋 수정 이력", expanded=False):
            render_edit_history_sidebar(content_id)
        
        # 복사 이력
        with st.expander("📎 복사 이력", expanded=False):
            if 'clipboard_history' in st.session_state and st.session_state.clipboard_history:
                st.markdown("**최근 복사한 항목:**")
                for i, item in enumerate(reversed(st.session_state.clipboard_history[-5:]), 1):
                    st.markdown(f"**{i}.** {item['type']} ({item['timestamp'][:16]})")
                    st.code(item['content'][:50] + "..." if len(item['content']) > 50 else item['content'])
            else:
                st.info("복사 이력이 없습니다.")
        
        # 유효성 검사 결과
        with st.expander("✅ 유효성 검사", expanded=False):
            validation_results = []
            
            # 제목 검사
            if final_titles:
                for i, title in enumerate(final_titles):
                    if len(title) > 100:
                        validation_results.append(f"⚠️ 제목 {i+1}: 너무 길음 ({len(title)}자)")
                    elif len(title) < 10:
                        validation_results.append(f"⚠️ 제목 {i+1}: 너무 짧음 ({len(title)}자)")
                    else:
                        validation_results.append(f"✅ 제목 {i+1}: 적절함")
            
            # 해시태그 검사
            if final_hashtags:
                hashtag_count = len(re.findall(r'#[^\s#]+', final_hashtags))
                if hashtag_count > 20:
                    validation_results.append(f"⚠️ 해시태그: 너무 많음 ({hashtag_count}개)")
                elif hashtag_count < 3:
                    validation_results.append(f"⚠️ 해시태그: 너무 적음 ({hashtag_count}개)")
                else:
                    validation_results.append(f"✅ 해시태그: 적절함 ({hashtag_count}개)")
            
            # 캡션 검사
            if final_caption:
                if len(final_caption) > 2000:
                    validation_results.append(f"⚠️ 캡션: 너무 길음 ({len(final_caption)}자)")
                elif len(final_caption) < 50:
                    validation_results.append(f"⚠️ 캡션: 너무 짧음 ({len(final_caption)}자)")
                else:
                    validation_results.append(f"✅ 캡션: 적절함 ({len(final_caption)}자)")
            
            for result in validation_results:
                st.markdown(result)
            
            if not validation_results:
                st.info("검사할 콘텐츠가 없습니다.")

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

def add_responsive_mobile_styles() -> None:
    """반응형 모바일 스타일 추가"""
    st.markdown("""
    <style>
    /* 모바일 반응형 스타일 */
    @media (max-width: 768px) {
        .stButton > button {
            height: 3rem;
            font-size: 1.1rem;
            border-radius: 0.5rem;
            width: 100% !important;
            margin-bottom: 0.5rem;
        }
        
        .ai-content-toast {
            max-width: 90% !important;
            left: 5% !important;
            right: 5% !important;
            font-size: 12px !important;
        }
        
        .element-container {
            margin-bottom: 1rem;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            flex-wrap: wrap;
        }
        
        .stTabs [data-baseweb="tab"] {
            font-size: 0.9rem;
            padding: 0.5rem;
        }
        
        .stTextArea textarea {
            font-size: 16px; /* iOS zoom 방지 */
        }
        
        .stTextInput input {
            font-size: 16px; /* iOS zoom 방지 */
        }
    }
    
    /* 태블릿 스타일 */
    @media (min-width: 769px) and (max-width: 1024px) {
        .stColumns {
            gap: 1rem;
        }
        
        .stButton > button {
            height: 2.5rem;
        }
    }
    
    /* 데스크톱 스타일 */
    @media (min-width: 1025px) {
        .ai-content-management {
            max-width: 1200px;
            margin: 0 auto;
        }
    }
    
    /* 공통 개선 사항 */
    .stExpander {
        border: 1px solid #e1e1e1;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    .stExpander > div > div {
        padding: 0.5rem;
    }
    
    /* 복사 버튼 스타일 개선 */
    .copy-button {
        background: linear-gradient(90deg, #1f77b4, #17a2b8);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .copy-button:hover {
        background: linear-gradient(90deg, #17a2b8, #1f77b4);
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* 편집 모드 스타일 */
    .edit-mode {
        background-color: #fff3cd;
        border: 2px solid #ffc107;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* 미리보기 스타일 */
    .preview-container {
        background: #f8f9fa;
        border: 2px solid #e9ecef;
        border-radius: 1rem;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .preview-container h3 {
        color: #495057;
        margin-bottom: 1rem;
    }
    
    /* 유효성 검사 결과 스타일 */
    .validation-success {
        color: #28a745;
        font-weight: 500;
    }
    
    .validation-warning {
        color: #ffc107;
        font-weight: 500;
    }
    
    .validation-error {
        color: #dc3545;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

def detect_mobile_device() -> bool:
    """모바일 디바이스 감지"""
    # User-Agent 기반 간단한 모바일 감지
    # 실제 구현에서는 JavaScript를 통한 더 정확한 감지 필요
    return st.session_state.get('is_mobile', False)

def add_mobile_detection_script() -> None:
    """향상된 모바일 환경 감지 스크립트"""
    st.markdown("""
    <script>
    // 향상된 모바일/태블릿 감지
    function detectDevice() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/i.test(userAgent);
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;
        
        // 화면 크기 기반 추가 감지
        const isSmallScreen = Math.min(screenWidth, screenHeight) < 768;
        const isMediumScreen = Math.min(screenWidth, screenHeight) >= 768 && Math.min(screenWidth, screenHeight) < 1024;
        
        return {
            isMobile: isMobile || isSmallScreen,
            isTablet: isTablet || isMediumScreen,
            isDesktop: !isMobile && !isTablet && !isSmallScreen && !isMediumScreen,
            screenWidth: screenWidth,
            screenHeight: screenHeight
        };
    }
    
    // 디바이스 정보 저장
    const deviceInfo = detectDevice();
    
    // Streamlit에서 접근 가능한 전역 변수로 설정
    window.streamlitDeviceInfo = deviceInfo;
    
    // 뷰포트 변경 감지
    window.addEventListener('resize', function() {
        const newDeviceInfo = detectDevice();
        window.streamlitDeviceInfo = newDeviceInfo;
    });
    
    // 터치 이벤트 지원 감지
    const supportsTouchEvents = 'ontouchstart' in window;
    window.streamlitDeviceInfo.supportsTouch = supportsTouchEvents;
    
    console.log('Device Info:', window.streamlitDeviceInfo);
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
    
    # 모바일 감지 스크립트 및 스타일 추가
    add_mobile_detection_script()
    add_responsive_mobile_styles()
    
    # 메인 컴포넌트 테스트
    st.title("🧪 AI 콘텐츠 관리 인터페이스 v2.0 테스트")
    
    # 새로운 향상된 인터페이스 테스트
    render_enhanced_ai_content_management(sample_candidate_data)
    
    # 구분선
    st.markdown("---")
    st.markdown("## 🔄 레거시 인터페이스 (호환성 테스트)")
    
    # 기존 인터페이스 테스트
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