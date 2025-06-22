"""
S02_M02_T001: 프롬프트 관리자
다양한 AI 프롬프트 템플릿을 관리하고 A/B 테스트를 지원하는 컴포넌트
"""

import streamlit as st
import json
import time
from typing import Dict, List, Any, Tuple
from datetime import datetime
import random

class PromptTemplate:
    """프롬프트 템플릿 클래스"""
    
    def __init__(self, name: str, template: str, description: str, category: str = "기본"):
        self.name = name
        self.template = template
        self.description = description
        self.category = category
        self.created_at = datetime.now()
        self.usage_count = 0
        self.avg_score = 0.0
        self.feedback_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "template": self.template,
            "description": self.description,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "usage_count": self.usage_count,
            "avg_score": self.avg_score,
            "feedback_count": self.feedback_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptTemplate':
        template = cls(
            name=data["name"],
            template=data["template"],
            description=data["description"],
            category=data.get("category", "기본")
        )
        template.usage_count = data.get("usage_count", 0)
        template.avg_score = data.get("avg_score", 0.0)
        template.feedback_count = data.get("feedback_count", 0)
        return template

class PromptManager:
    """프롬프트 관리자"""
    
    def __init__(self):
        self.templates = self._initialize_default_templates()
        self._load_saved_templates()
    
    def _initialize_default_templates(self) -> Dict[str, PromptTemplate]:
        """기본 프롬프트 템플릿 초기화"""
        templates = {}
        
        # 1. 기본형 (현재 사용중)
        templates["basic"] = PromptTemplate(
            name="기본형",
            template="""
당신은 전문적인 소셜미디어 콘텐츠 작성자입니다.
다음 제품 정보를 바탕으로 Instagram Reels/TikTok용 콘텐츠를 생성해주세요.

제품 정보:
- 채널명: {channel_name}
- 제품명: {product_name}
- 카테고리: {category}
- 매력도 점수: {attraction_score}점
- 예상 가격: {expected_price}

다음 형식으로 작성해주세요:
1. 제목 (15자 이내, 임팩트 있게)
2. 해시태그 (10개 이상, 트렌드 반영)
3. 캡션 (50자 이내, 호기심 유발)

매력적이고 클릭을 유도하는 콘텐츠로 작성해주세요.
""",
            description="균형 잡힌 기본 템플릿으로 모든 상황에 적합",
            category="기본"
        )
        
        # 2. 감정적 어필형
        templates["emotional"] = PromptTemplate(
            name="감정적 어필형",
            template="""
당신은 감정적 스토리텔링 전문가입니다.
제품에 대한 개인적이고 진정성 있는 콘텐츠를 만들어주세요.

제품 정보:
- 채널명: {channel_name}
- 제품명: {product_name}
- 카테고리: {category}
- 매력도 점수: {attraction_score}점
- 예상 가격: {expected_price}

감정적 키워드: 설렘, 놀라움, 만족감, 특별함, 변화

다음 요소를 포함해서 작성해주세요:
1. 제목: 개인적 경험이나 감정 표현 (예: "이거 쓰고 완전 달라졌어요")
2. 해시태그: 감정적 표현과 공감 유발 태그
3. 캡션: 진솔한 후기나 변화 스토리

진정성있고 공감할 수 있는 콘텐츠로 작성해주세요.
""",
            description="감정적 공감대 형성과 진정성 어필에 특화",
            category="스타일"
        )
        
        # 3. 정보 중심형
        templates["informative"] = PromptTemplate(
            name="정보 중심형",
            template="""
당신은 전문적인 제품 리뷰어입니다.
객관적이고 유용한 정보를 제공하는 콘텐츠를 작성해주세요.

제품 정보:
- 채널명: {channel_name}
- 제품명: {product_name}
- 카테고리: {category}
- 매력도 점수: {attraction_score}점
- 예상 가격: {expected_price}

정보 요소 강조:
- 제품 특징과 장점
- 사용법이나 팁
- 가격 대비 효과
- 타 제품과의 차별점

다음 형식으로 작성:
1. 제목: 구체적인 특징이나 효과 명시
2. 해시태그: 제품 특성, 기능, 카테고리 관련 태그
3. 캡션: 핵심 정보 요약 (성분, 효과, 사용팁 등)

신뢰할 수 있고 구매 결정에 도움이 되는 내용으로 작성해주세요.
""",
            description="제품 정보와 실용적 가치에 중점을 둔 템플릿",
            category="스타일"
        )
        
        # 4. 트렌드 반영형
        templates["trendy"] = PromptTemplate(
            name="트렌드 반영형",
            template="""
당신은 트렌드에 민감한 Z세대 인플루언서입니다.
최신 트렌드와 밈을 활용한 재미있는 콘텐츠를 만들어주세요.

제품 정보:
- 채널명: {channel_name}
- 제품명: {product_name}
- 카테고리: {category}
- 매력도 점수: {attraction_score}점
- 예상 가격: {expected_price}

트렌드 요소:
- 2024년 유행어나 밈
- 짧고 강렬한 표현
- 젊은 층이 좋아하는 표현법
- 바이럴 요소

작성 스타일:
1. 제목: 트렌디한 표현, 줄임말, 유행어 활용
2. 해시태그: 트렌드 태그, 챌린지 태그, 밈 태그
3. 캡션: 재미있고 캐주얼한 톤

젊고 트렌디한 느낌으로 바이럴 가능성을 높여주세요.
""",
            description="최신 트렌드와 젊은 감성을 반영한 템플릿",
            category="스타일"
        )
        
        # 5. 긴급성 어필형
        templates["urgent"] = PromptTemplate(
            name="긴급성 어필형",
            template="""
당신은 마케팅 전문가입니다.
긴급성과 희소성을 강조하여 즉시 행동을 유도하는 콘텐츠를 작성해주세요.

제품 정보:
- 채널명: {channel_name}
- 제품명: {product_name}
- 카테고리: {category}
- 매력도 점수: {attraction_score}점
- 예상 가격: {expected_price}

긴급성 요소:
- 한정 수량/시간
- 특별 할인
- 놓치면 안 되는 기회
- 빠른 결정 필요

작성 요소:
1. 제목: 긴급함을 나타내는 표현 (지금, 마지막, 한정 등)
2. 해시태그: 할인, 한정, 특가 관련 태그
3. 캡션: FOMO(Fear of Missing Out) 유발

구매 욕구를 즉시 자극하는 콘텐츠로 작성해주세요.
""",
            description="긴급성과 희소성으로 즉시 행동을 유도하는 템플릿",
            category="전략"
        )
        
        return templates
    
    def _load_saved_templates(self):
        """저장된 사용자 정의 템플릿 로드"""
        try:
            if hasattr(st, 'session_state') and 'custom_templates' in st.session_state:
                for template_data in st.session_state.custom_templates:
                    template = PromptTemplate.from_dict(template_data)
                    self.templates[template.name.lower().replace(" ", "_")] = template
        except Exception:
            # 세션 상태를 사용할 수 없는 환경에서는 무시
            pass
    
    def get_template(self, template_id: str) -> PromptTemplate:
        """특정 템플릿 반환"""
        return self.templates.get(template_id)
    
    def get_all_templates(self) -> Dict[str, PromptTemplate]:
        """모든 템플릿 반환"""
        return self.templates
    
    def get_templates_by_category(self, category: str) -> Dict[str, PromptTemplate]:
        """카테고리별 템플릿 반환"""
        return {k: v for k, v in self.templates.items() if v.category == category}
    
    def add_custom_template(self, template: PromptTemplate):
        """사용자 정의 템플릿 추가"""
        template_id = template.name.lower().replace(" ", "_")
        self.templates[template_id] = template
        self._save_custom_templates()
    
    def _save_custom_templates(self):
        """사용자 정의 템플릿 저장"""
        custom_templates = []
        for template in self.templates.values():
            if template.category not in ["기본", "스타일", "전략"]:
                custom_templates.append(template.to_dict())
        
        # Streamlit 세션 상태가 사용 가능한 경우에만 저장
        try:
            if hasattr(st, 'session_state'):
                st.session_state.custom_templates = custom_templates
        except Exception:
            # 세션 상태를 사용할 수 없는 환경에서는 무시
            pass
    
    def update_template_usage(self, template_id: str, score: float = None):
        """템플릿 사용 통계 업데이트"""
        if template_id in self.templates:
            template = self.templates[template_id]
            template.usage_count += 1
            
            if score is not None:
                # 평균 점수 업데이트
                template.avg_score = (
                    (template.avg_score * template.feedback_count + score) / 
                    (template.feedback_count + 1)
                )
                template.feedback_count += 1

def render_template_selector() -> List[str]:
    """템플릿 선택 UI"""
    manager = PromptManager()
    
    st.markdown("### 🎯 프롬프트 템플릿 선택")
    
    # 선택 모드
    selection_mode = st.radio(
        "선택 모드",
        ["단일 템플릿", "다중 템플릿 (A/B 테스트)"],
        horizontal=True
    )
    
    # 템플릿 목록 표시
    templates = manager.get_all_templates()
    
    if selection_mode == "단일 템플릿":
        # 단일 선택
        template_options = {}
        for template_id, template in templates.items():
            display_name = f"{template.name} ({template.category})"
            if template.usage_count > 0:
                display_name += f" - 평균 점수: {template.avg_score:.1f}"
            template_options[display_name] = template_id
        
        selected_display = st.selectbox(
            "템플릿 선택",
            list(template_options.keys()),
            key="single_template_select"
        )
        
        selected_template_id = template_options[selected_display]
        
        # 선택된 템플릿 정보 표시
        selected_template = templates[selected_template_id]
        with st.expander(f"📋 {selected_template.name} 템플릿 정보"):
            st.markdown(f"**설명**: {selected_template.description}")
            st.markdown(f"**카테고리**: {selected_template.category}")
            if selected_template.usage_count > 0:
                st.markdown(f"**사용 횟수**: {selected_template.usage_count}")
                st.markdown(f"**평균 점수**: {selected_template.avg_score:.1f}/10")
        
        return [selected_template_id]
    
    else:
        # 다중 선택
        st.markdown("여러 템플릿을 선택하여 비교 테스트하세요:")
        
        selected_templates = []
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**기본/스타일 템플릿**")
            for template_id, template in templates.items():
                if template.category in ["기본", "스타일"]:
                    if st.checkbox(
                        f"{template.name} ({template.category})",
                        key=f"multi_select_{template_id}"
                    ):
                        selected_templates.append(template_id)
        
        with col2:
            st.markdown("**전략/사용자 정의 템플릿**")
            for template_id, template in templates.items():
                if template.category not in ["기본", "스타일"]:
                    if st.checkbox(
                        f"{template.name} ({template.category})",
                        key=f"multi_select_{template_id}"
                    ):
                        selected_templates.append(template_id)
        
        if len(selected_templates) < 2:
            st.warning("⚠️ A/B 테스트를 위해서는 최소 2개의 템플릿을 선택해주세요.")
        elif len(selected_templates) > 4:
            st.warning("⚠️ 한 번에 최대 4개까지만 비교할 수 있습니다.")
            selected_templates = selected_templates[:4]
        
        return selected_templates

def render_custom_template_creator():
    """사용자 정의 템플릿 생성 UI"""
    st.markdown("### ➕ 사용자 정의 템플릿 만들기")
    
    with st.expander("새 템플릿 추가"):
        col1, col2 = st.columns(2)
        
        with col1:
            template_name = st.text_input("템플릿 이름", key="new_template_name")
            template_category = st.selectbox(
                "카테고리",
                ["사용자 정의", "업종별", "특수 목적"],
                key="new_template_category"
            )
        
        with col2:
            template_description = st.text_area(
                "템플릿 설명",
                height=100,
                key="new_template_description"
            )
        
        template_content = st.text_area(
            "프롬프트 템플릿",
            height=200,
            placeholder="""예시:
당신은 [역할]입니다.
다음 제품 정보를 바탕으로 [목적]에 맞는 콘텐츠를 생성해주세요.

제품 정보:
- 채널명: {channel_name}
- 제품명: {product_name}
- 카테고리: {category}
- 매력도 점수: {attraction_score}점
- 예상 가격: {expected_price}

[특별 지시사항]

형식:
1. 제목: [조건]
2. 해시태그: [조건]
3. 캡션: [조건]""",
            key="new_template_content"
        )
        
        if st.button("템플릿 추가", type="primary"):
            if template_name and template_content and template_description:
                manager = PromptManager()
                new_template = PromptTemplate(
                    name=template_name,
                    template=template_content,
                    description=template_description,
                    category=template_category
                )
                manager.add_custom_template(new_template)
                st.success(f"✅ '{template_name}' 템플릿이 추가되었습니다!")
                st.rerun()
            else:
                st.error("❌ 모든 필드를 입력해주세요.")

def render_template_comparison(results: List[Dict[str, Any]]):
    """템플릿 비교 결과 표시"""
    if len(results) < 2:
        return
    
    st.markdown("### 🔄 A/B 테스트 결과 비교")
    
    # 결과를 나란히 표시
    cols = st.columns(len(results))
    
    for i, (col, result) in enumerate(zip(cols, results)):
        with col:
            template_name = result['template_name']
            content = result['content']
            score = result.get('quality_score', 0)
            
            st.markdown(f"#### {template_name}")
            st.markdown(f"**품질 점수**: {score:.1f}/10")
            
            # 생성된 콘텐츠 표시
            with st.container():
                if 'title' in content:
                    st.markdown(f"**제목**: {content['title']}")
                if 'hashtags' in content:
                    st.markdown(f"**해시태그**: {content['hashtags']}")
                if 'caption' in content:
                    st.markdown(f"**캡션**: {content['caption']}")
            
            # 개별 복사 버튼
            if st.button(f"이 결과 선택", key=f"select_result_{i}"):
                st.session_state.selected_ab_result = result
                st.success("✅ 선택되었습니다!")
    
    # 전체 비교 분석
    st.markdown("### 📊 비교 분석")
    
    comparison_data = []
    for result in results:
        comparison_data.append({
            "템플릿": result['template_name'],
            "품질 점수": result.get('quality_score', 0),
            "제목 길이": len(result['content'].get('title', '')),
            "해시태그 수": len(result['content'].get('hashtags', '').split()),
            "캡션 길이": len(result['content'].get('caption', ''))
        })
    
    import pandas as pd
    df = pd.DataFrame(comparison_data)
    st.dataframe(df, use_container_width=True)
    
    # 최고 점수 템플릿 하이라이트
    best_result = max(results, key=lambda x: x.get('quality_score', 0))
    st.success(f"🏆 **최고 점수**: {best_result['template_name']} ({best_result.get('quality_score', 0):.1f}점)")

def calculate_content_quality_score(content: Dict[str, str]) -> float:
    """콘텐츠 품질 점수 계산"""
    score = 0.0
    max_score = 10.0
    
    title = content.get('title', '')
    hashtags = content.get('hashtags', '')
    caption = content.get('caption', '')
    
    # 제목 평가 (3점 만점)
    if title:
        # 길이 적정성 (10-20자)
        title_len = len(title)
        if 10 <= title_len <= 20:
            score += 1.0
        elif 8 <= title_len <= 25:
            score += 0.7
        else:
            score += 0.3
        
        # 특수 문자/이모지 사용
        if any(char in title for char in "!?😍💕✨🔥"):
            score += 0.5
        
        # 대문자/느낌표 적절한 사용
        if title.count('!') <= 2 and any(c.isupper() for c in title):
            score += 0.5
        
        # 숫자나 구체적 표현
        if any(char.isdigit() or word in title for word in ["최고", "대박", "완전", "진짜"]):
            score += 1.0
    
    # 해시태그 평가 (3점 만점)
    if hashtags:
        hashtag_list = [tag.strip() for tag in hashtags.split() if tag.startswith('#')]
        hashtag_count = len(hashtag_list)
        
        # 개수 적정성 (8-15개)
        if 8 <= hashtag_count <= 15:
            score += 1.5
        elif 5 <= hashtag_count <= 20:
            score += 1.0
        else:
            score += 0.5
        
        # 다양성 (카테고리, 브랜드, 감정, 트렌드 등)
        categories = {
            'product': ['뷰티', '스킨케어', '메이크업', '패션', '코스메틱'],
            'emotion': ['좋아요', '추천', '만족', '사랑', '완전'],
            'trend': ['인스타', '틱톡', '릴스', '바이럴', '핫'],
            'action': ['리뷰', '후기', '체험', '사용법', '비교']
        }
        
        found_categories = 0
        for category, keywords in categories.items():
            if any(keyword in hashtags for keyword in keywords):
                found_categories += 1
        
        score += min(1.5, found_categories * 0.3)
    
    # 캡션 평가 (4점 만점)
    if caption:
        caption_len = len(caption)
        
        # 길이 적정성 (30-80자)
        if 30 <= caption_len <= 80:
            score += 1.5
        elif 20 <= caption_len <= 100:
            score += 1.0
        else:
            score += 0.5
        
        # 호기심 유발 요소
        curiosity_words = ["궁금", "비밀", "놀라", "대박", "완전", "진짜", "솔직"]
        if any(word in caption for word in curiosity_words):
            score += 1.0
        
        # 개인적 경험/감정 표현
        personal_words = ["저는", "제가", "정말", "너무", "완전", "진심"]
        if any(word in caption for word in personal_words):
            score += 0.5
        
        # 질문이나 상호작용 유도
        if '?' in caption or any(word in caption for word in ["어떤가요", "어때요", "댓글"]):
            score += 1.0
    
    # 전체적 일관성 보너스
    if title and hashtags and caption:
        score += 1.0  # 모든 요소가 생성된 경우 보너스
    
    return min(score, max_score)

if __name__ == "__main__":
    st.title("🎯 프롬프트 관리자 테스트")
    
    # 템플릿 선택기 테스트
    selected_templates = render_template_selector()
    st.write("선택된 템플릿:", selected_templates)
    
    # 사용자 정의 템플릿 생성기 테스트
    render_custom_template_creator()