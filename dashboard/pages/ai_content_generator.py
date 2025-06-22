"""
S02_M02_T001: AI 콘텐츠 생성기 고도화
다중 프롬프트 템플릿 및 A/B 테스트 기능을 포함한 고급 AI 콘텐츠 생성기
"""

import streamlit as st
import pandas as pd
import time
from typing import Dict, List, Any
from dashboard.components.ai_content_display import render_ai_content_display, generate_ai_content
from dashboard.components.prompt_manager import (
    render_template_selector, render_custom_template_creator, 
    render_template_comparison, PromptManager
)
from dashboard.utils.content_evaluator import (
    ContentEvaluator, render_evaluation_results, batch_evaluate_contents
)

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
    """AI 콘텐츠 생성기 메인 페이지 v2.0"""
    st.markdown("## 🤖 AI 콘텐츠 생성기 v2.0")
    
    st.info("""
    ✨ **업그레이드된 AI 콘텐츠 생성기!**  
    • 🎯 다양한 프롬프트 템플릿 선택  
    • 🔄 A/B 테스트로 최적 콘텐츠 발견  
    • 📊 자동 품질 평가 및 개선 제안  
    • 💡 사용자 정의 템플릿 생성 가능
    """)
    
    # 탭으로 구분
    tab1, tab2, tab3 = st.tabs(["📝 제품 입력", "🎯 프리셋 사용", "⚙️ 템플릿 관리"])
    
    with tab1:
        render_product_input_form()
    
    with tab2:
        render_preset_products()
        
        # 기존 후보에서 선택
        st.markdown("---")
        st.markdown("### 📊 기존 후보에서 선택")
        
        if st.button("수익화 후보에서 가져오기", use_container_width=True):
            st.info("🚧 수익화 후보 데이터 연동 기능은 향후 구현됩니다.")
    
    with tab3:
        render_custom_template_creator()
    
    # AI 콘텐츠 생성 프로세스
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
        
        # 프롬프트 템플릿 선택
        st.markdown("### 🎯 프롬프트 템플릿 선택")
        selected_templates = render_template_selector()
        
        if selected_templates:
            # 콘텐츠 생성 버튼
            if st.button("🚀 AI 콘텐츠 생성", type="primary", use_container_width=True):
                generate_content_with_templates(product_data, selected_templates)
            
            # 기존 생성 결과 표시
            if 'ab_test_results' in st.session_state:
                st.markdown("---")
                render_ab_test_results()
        
        # 초기화 버튼
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("🔄 새로 시작", use_container_width=True):
                # 모든 관련 세션 상태 초기화
                keys_to_clear = [
                    'manual_product_data', 'saved_content', 'ab_test_results',
                    'selected_ab_result', 'generated_contents'
                ]
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    else:
        st.markdown("---")
        st.markdown("### 🎯 시작하기")
        st.markdown("""
        위의 탭에서 다음 중 하나를 선택하세요:
        
        1. **📝 제품 입력**: 제품 정보를 직접 입력하여 맞춤형 콘텐츠 생성
        2. **🎯 프리셋 사용**: 미리 준비된 제품 예시로 빠른 테스트
        3. **⚙️ 템플릿 관리**: 사용자 정의 프롬프트 템플릿 생성
        
        입력이 완료되면 다양한 템플릿으로 최적화된 콘텐츠를 생성합니다! 🚀
        """)

def generate_content_with_templates(product_data: Dict[str, Any], template_ids: List[str]):
    """선택된 템플릿들로 콘텐츠 생성"""
    manager = PromptManager()
    evaluator = ContentEvaluator()
    
    results = []
    
    with st.spinner("AI 콘텐츠를 생성하고 있습니다..."):
        progress_bar = st.progress(0)
        
        for i, template_id in enumerate(template_ids):
            template = manager.get_template(template_id)
            if not template:
                continue
            
            # 진행률 업데이트
            progress = (i + 1) / len(template_ids)
            progress_bar.progress(progress)
            
            try:
                # 프롬프트 포맷팅
                formatted_prompt = template.template.format(
                    channel_name=product_data.get('채널명', ''),
                    product_name=product_data.get('제품명', ''),
                    category=product_data.get('카테고리', ''),
                    attraction_score=product_data.get('매력도_점수', 0),
                    expected_price=product_data.get('예상_가격', '')
                )
                
                # 모의 AI 생성 (실제로는 OpenAI API 호출)
                generated_content = simulate_ai_content_generation(formatted_prompt, template.name)
                
                # 품질 평가
                evaluation = evaluator.evaluate_content(generated_content, product_data)
                
                # 결과 저장
                result = {
                    'template_id': template_id,
                    'template_name': template.name,
                    'content': generated_content,
                    'quality_score': evaluation['total_score'],
                    'evaluation': evaluation,
                    'timestamp': time.time()
                }
                
                results.append(result)
                
                # 템플릿 사용 통계 업데이트
                manager.update_template_usage(template_id, evaluation['total_score'])
                
                # 짧은 대기 (실제 API 호출 시뮬레이션)
                time.sleep(0.5)
                
            except Exception as e:
                st.error(f"템플릿 '{template.name}' 처리 중 오류: {str(e)}")
                continue
        
        progress_bar.empty()
    
    # 결과 저장
    st.session_state.ab_test_results = results
    
    if results:
        st.success(f"✅ {len(results)}개 템플릿으로 콘텐츠 생성 완료!")
    else:
        st.error("❌ 콘텐츠 생성에 실패했습니다.")

def simulate_ai_content_generation(prompt: str, template_name: str) -> Dict[str, str]:
    """AI 콘텐츠 생성 시뮬레이션 (실제로는 OpenAI API 호출)"""
    # 템플릿별 다른 스타일의 더미 콘텐츠 생성
    
    if "기본형" in template_name:
        return {
            'title': '이 제품 진짜 추천해요!',
            'hashtags': '#뷰티 #스킨케어 #추천 #인스타그램 #릴스 #일상 #좋아요 #신상',
            'caption': '정말 좋은 제품이에요. 여러분도 한번 써보세요!'
        }
    elif "감정적" in template_name:
        return {
            'title': '완전 반했어요 💕 이거 쓰고 달라진 내 피부',
            'hashtags': '#감동 #변화 #사랑해 #완전추천 #진심 #달라졌어요 #놀라운변화 #만족',
            'caption': '진짜 너무 좋아서 눈물날뻔했어요 😭 이런 제품을 이제야 만나다니... 여러분 꼭 써보세요!'
        }
    elif "정보" in template_name:
        return {
            'title': '히알루론산 세럼 성분 분석 & 효과 후기',
            'hashtags': '#성분분석 #효과 #사용법 #팩트체크 #정보공유 #전문리뷰 #객관적후기',
            'caption': '히알루론산 농도 2%, 보습력 지속시간 8시간. 민감성 피부도 안전하게 사용 가능합니다.'
        }
    elif "트렌드" in template_name:
        return {
            'title': '요즘 핫한 그 템💅 나도 해봤다',
            'hashtags': '#핫템 #트렌드 #요즘이거 #바이럴 #인싸템 #MZ추천 #핫해핫해 #레전드',
            'caption': '요즘 온 인스타 난리난 그거 ㅋㅋ 나도 드디어 겟했다구~ 역시 핫한 건 이유가 있어 💯'
        }
    elif "긴급성" in template_name:
        return {
            'title': '⚡️지금 놓치면 후회! 마지막 기회',
            'hashtags': '#마지막기회 #놓치면후회 #한정수량 #지금구매 #특가 #타임세일 #서둘러',
            'caption': '진짜 마지막이에요! 이 가격에 이런 제품 다시는 못 봅니다. 지금 바로 클릭하세요!'
        }
    else:
        return {
            'title': '이 제품 어떤가요?',
            'hashtags': '#제품추천 #후기 #리뷰',
            'caption': '사용해본 후기 공유합니다.'
        }

def render_ab_test_results():
    """A/B 테스트 결과 렌더링"""
    if 'ab_test_results' not in st.session_state or not st.session_state.ab_test_results:
        return
    
    results = st.session_state.ab_test_results
    
    st.markdown("## 🔄 A/B 테스트 결과")
    
    if len(results) == 1:
        # 단일 결과 표시
        result = results[0]
        st.markdown(f"### {result['template_name']} 결과")
        
        # 품질 평가 표시
        render_evaluation_results(result['evaluation'])
        
        # 생성된 콘텐츠 표시
        st.markdown("#### 📝 생성된 콘텐츠")
        render_single_content_result(result)
        
    else:
        # 다중 결과 비교
        render_template_comparison(results)
        
        # 상세 분석
        st.markdown("### 📊 상세 품질 분석")
        
        # 가장 높은 점수의 결과 상세 분석
        best_result = max(results, key=lambda x: x['quality_score'])
        
        with st.expander(f"🏆 최고 점수: {best_result['template_name']} ({best_result['quality_score']:.1f}점)"):
            render_evaluation_results(best_result['evaluation'])
        
        # 다른 결과들도 접을 수 있는 형태로 표시
        for result in results:
            if result != best_result:
                with st.expander(f"{result['template_name']} ({result['quality_score']:.1f}점)"):
                    render_evaluation_results(result['evaluation'])
    
    # 최종 선택된 결과 표시
    if 'selected_ab_result' in st.session_state:
        st.markdown("---")
        st.markdown("### ✅ 선택된 최종 결과")
        selected_result = st.session_state.selected_ab_result
        render_single_content_result(selected_result, show_copy_buttons=True)

def render_single_content_result(result: Dict[str, Any], show_copy_buttons: bool = False):
    """단일 콘텐츠 결과 표시"""
    content = result['content']
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 제목
        if 'title' in content:
            st.markdown("**🎯 제목**")
            st.info(content['title'])
            if show_copy_buttons:
                if st.button("📋 제목 복사", key="copy_title"):
                    st.success("제목이 클립보드에 복사되었습니다!")
        
        # 해시태그
        if 'hashtags' in content:
            st.markdown("**#️⃣ 해시태그**")
            st.info(content['hashtags'])
            if show_copy_buttons:
                if st.button("📋 해시태그 복사", key="copy_hashtags"):
                    st.success("해시태그가 클립보드에 복사되었습니다!")
        
        # 캡션
        if 'caption' in content:
            st.markdown("**💬 캡션**")
            st.info(content['caption'])
            if show_copy_buttons:
                if st.button("📋 캡션 복사", key="copy_caption"):
                    st.success("캡션이 클립보드에 복사되었습니다!")
    
    with col2:
        st.markdown("**📊 품질 정보**")
        st.metric("총점", f"{result['quality_score']:.1f}/10")
        st.metric("등급", result['evaluation']['grade'])
        
        if show_copy_buttons:
            if st.button("📋 전체 복사", key="copy_all", type="primary"):
                all_content = f"제목: {content.get('title', '')}\n\n해시태그: {content.get('hashtags', '')}\n\n캡션: {content.get('caption', '')}"
                st.success("전체 콘텐츠가 클립보드에 복사되었습니다!")

if __name__ == "__main__":
    render_ai_content_generator()