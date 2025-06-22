"""
S02_M02_T001: 콘텐츠 품질 평가기
AI 생성 콘텐츠의 품질을 자동으로 평가하고 점수를 부여하는 유틸리티
"""

import re
import json
from typing import Dict, List, Any, Tuple
from datetime import datetime
import streamlit as st

class ContentEvaluator:
    """AI 생성 콘텐츠 품질 평가기"""
    
    def __init__(self):
        self.evaluation_weights = {
            'title': 0.35,      # 제목 중요도 35%
            'hashtags': 0.30,   # 해시태그 중요도 30%
            'caption': 0.35     # 캡션 중요도 35%
        }
        
        # 평가 기준 데이터
        self.quality_criteria = self._load_quality_criteria()
    
    def _load_quality_criteria(self) -> Dict[str, Any]:
        """품질 평가 기준 데이터 로드"""
        return {
            'title': {
                'optimal_length': (10, 20),
                'max_length': 25,
                'positive_elements': [
                    '!', '?', '😍', '💕', '✨', '🔥', '💖', '🎉', '👍',
                    '최고', '대박', '완전', '진짜', '솔직', '리얼'
                ],
                'engagement_words': [
                    '추천', '후기', '리뷰', '체험', '사용법', '비교',
                    '솔직', '진짜', '완전', '대박', '놀라운'
                ],
                'power_words': [
                    '무조건', '반드시', '꼭', '절대', '진심', '레전드'
                ]
            },
            'hashtags': {
                'optimal_count': (8, 15),
                'max_count': 20,
                'categories': {
                    'product': ['뷰티', '스킨케어', '메이크업', '패션', '헤어', '향수'],
                    'emotion': ['좋아요', '추천', '만족', '사랑', '완전', '대박'],
                    'platform': ['인스타그램', '인스타', '릴스', '틱톡', '유튜브'],
                    'trend': ['바이럴', '핫', '트렌드', '인기', '화제', '신상'],
                    'action': ['리뷰', '후기', '체험', '사용법', '비교', '추천']
                }
            },
            'caption': {
                'optimal_length': (30, 80),
                'max_length': 100,
                'curiosity_words': [
                    '궁금', '비밀', '놀라', '대박', '완전', '진짜', 
                    '솔직', '레전드', '미쳤다', '개좋아'
                ],
                'personal_words': [
                    '저는', '제가', '나는', '내가', '정말', '너무', 
                    '완전', '진심', '솔직히', '개인적으로'
                ],
                'interaction_words': [
                    '어떤가요', '어때요', '댓글', '알려주세요', 
                    '궁금해요', '공유해요', '?'
                ]
            }
        }
    
    def evaluate_content(self, content: Dict[str, str], product_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """콘텐츠 전체 품질 평가"""
        title = content.get('title', '')
        hashtags = content.get('hashtags', '')
        caption = content.get('caption', '')
        
        # 개별 요소 평가
        title_score, title_feedback = self.evaluate_title(title)
        hashtags_score, hashtags_feedback = self.evaluate_hashtags(hashtags)
        caption_score, caption_feedback = self.evaluate_caption(caption)
        
        # 가중평균 계산
        total_score = (
            title_score * self.evaluation_weights['title'] +
            hashtags_score * self.evaluation_weights['hashtags'] +
            caption_score * self.evaluation_weights['caption']
        )
        
        # 전체적 일관성 보너스
        consistency_bonus = self._evaluate_consistency(content, product_data)
        total_score = min(10.0, total_score + consistency_bonus)
        
        # 상세 분석 결과
        analysis = {
            'total_score': round(total_score, 1),
            'grade': self._get_grade(total_score),
            'components': {
                'title': {
                    'score': round(title_score, 1),
                    'feedback': title_feedback
                },
                'hashtags': {
                    'score': round(hashtags_score, 1),
                    'feedback': hashtags_feedback
                },
                'caption': {
                    'score': round(caption_score, 1),
                    'feedback': caption_feedback
                }
            },
            'consistency_bonus': round(consistency_bonus, 1),
            'overall_feedback': self._generate_overall_feedback(total_score, content),
            'improvement_suggestions': self._generate_improvement_suggestions(
                title_score, hashtags_score, caption_score, content
            )
        }
        
        return analysis
    
    def evaluate_title(self, title: str) -> Tuple[float, List[str]]:
        """제목 평가"""
        if not title:
            return 0.0, ["제목이 생성되지 않았습니다."]
        
        score = 0.0
        feedback = []
        criteria = self.quality_criteria['title']
        
        # 1. 길이 평가 (3점)
        title_len = len(title)
        optimal_min, optimal_max = criteria['optimal_length']
        
        if optimal_min <= title_len <= optimal_max:
            score += 3.0
            feedback.append(f"✅ 제목 길이가 적절합니다 ({title_len}자)")
        elif title_len < optimal_min:
            score += 1.5
            feedback.append(f"⚠️ 제목이 다소 짧습니다 ({title_len}자, 권장: {optimal_min}-{optimal_max}자)")
        elif title_len <= criteria['max_length']:
            score += 2.0
            feedback.append(f"⚠️ 제목이 다소 깁니다 ({title_len}자, 권장: {optimal_min}-{optimal_max}자)")
        else:
            score += 0.5
            feedback.append(f"❌ 제목이 너무 깁니다 ({title_len}자, 최대: {criteria['max_length']}자)")
        
        # 2. 임팩트 요소 평가 (2점)
        positive_count = sum(1 for element in criteria['positive_elements'] if element in title)
        if positive_count >= 2:
            score += 2.0
            feedback.append("✅ 임팩트 있는 요소가 충분합니다")
        elif positive_count == 1:
            score += 1.0
            feedback.append("⚠️ 더 많은 임팩트 요소를 추가해보세요")
        else:
            score += 0.0
            feedback.append("❌ 감정적 어필 요소가 부족합니다")
        
        # 3. 참여 유도 요소 (2점)
        engagement_count = sum(1 for word in criteria['engagement_words'] if word in title)
        if engagement_count >= 1:
            score += 2.0
            feedback.append("✅ 참여를 유도하는 키워드가 포함되어 있습니다")
        else:
            score += 0.0
            feedback.append("⚠️ 참여 유도 요소를 추가해보세요")
        
        # 4. 파워 워드 사용 (1점)
        power_count = sum(1 for word in criteria['power_words'] if word in title)
        if power_count >= 1:
            score += 1.0
            feedback.append("✅ 강력한 표현이 포함되어 있습니다")
        
        # 5. 특수문자 적절성 (2점)
        exclamation_count = title.count('!')
        question_count = title.count('?')
        
        if 1 <= exclamation_count <= 2 or question_count == 1:
            score += 2.0
            feedback.append("✅ 특수문자 사용이 적절합니다")
        elif exclamation_count > 2:
            score += 0.5
            feedback.append("⚠️ 느낌표가 너무 많습니다")
        else:
            score += 1.0
            feedback.append("⚠️ 느낌표나 물음표를 추가해보세요")
        
        return min(score, 10.0), feedback
    
    def evaluate_hashtags(self, hashtags: str) -> Tuple[float, List[str]]:
        """해시태그 평가"""
        if not hashtags:
            return 0.0, ["해시태그가 생성되지 않았습니다."]
        
        score = 0.0
        feedback = []
        criteria = self.quality_criteria['hashtags']
        
        # 해시태그 파싱
        hashtag_list = [tag.strip() for tag in hashtags.split() if tag.startswith('#')]
        hashtag_count = len(hashtag_list)
        
        # 1. 개수 평가 (3점)
        optimal_min, optimal_max = criteria['optimal_count']
        
        if optimal_min <= hashtag_count <= optimal_max:
            score += 3.0
            feedback.append(f"✅ 해시태그 개수가 적절합니다 ({hashtag_count}개)")
        elif hashtag_count < optimal_min:
            score += 1.5
            feedback.append(f"⚠️ 해시태그가 부족합니다 ({hashtag_count}개, 권장: {optimal_min}-{optimal_max}개)")
        elif hashtag_count <= criteria['max_count']:
            score += 2.0
            feedback.append(f"⚠️ 해시태그가 다소 많습니다 ({hashtag_count}개)")
        else:
            score += 0.5
            feedback.append(f"❌ 해시태그가 너무 많습니다 ({hashtag_count}개)")
        
        # 2. 카테고리 다양성 평가 (4점)
        category_coverage = {}
        for category, keywords in criteria['categories'].items():
            category_coverage[category] = any(
                keyword in hashtags.lower() for keyword in keywords
            )
        
        covered_categories = sum(category_coverage.values())
        
        if covered_categories >= 4:
            score += 4.0
            feedback.append("✅ 다양한 카테고리의 해시태그가 포함되어 있습니다")
        elif covered_categories >= 3:
            score += 3.0
            feedback.append("✅ 해시태그 카테고리가 적절합니다")
        elif covered_categories >= 2:
            score += 2.0
            feedback.append("⚠️ 더 다양한 카테고리의 해시태그를 추가해보세요")
        else:
            score += 1.0
            feedback.append("❌ 해시태그 카테고리가 너무 단조롭습니다")
        
        # 3. 해시태그 형식 검증 (2점)
        valid_hashtags = 0
        invalid_hashtags = []
        
        for tag in hashtag_list:
            if len(tag) > 1 and tag[1:].replace('_', '').isalnum():
                valid_hashtags += 1
            else:
                invalid_hashtags.append(tag)
        
        if invalid_hashtags:
            score += 1.0
            feedback.append(f"⚠️ 잘못된 형식의 해시태그: {', '.join(invalid_hashtags)}")
        else:
            score += 2.0
            feedback.append("✅ 모든 해시태그 형식이 올바릅니다")
        
        # 4. 트렌드/인기 태그 포함 (1점)
        popular_tags = ['인스타그램', '릴스', '일상', '데일리', '추천', '좋아요']
        has_popular = any(tag in hashtags for tag in popular_tags)
        
        if has_popular:
            score += 1.0
            feedback.append("✅ 인기 해시태그가 포함되어 있습니다")
        
        return min(score, 10.0), feedback
    
    def evaluate_caption(self, caption: str) -> Tuple[float, List[str]]:
        """캡션 평가"""
        if not caption:
            return 0.0, ["캡션이 생성되지 않았습니다."]
        
        score = 0.0
        feedback = []
        criteria = self.quality_criteria['caption']
        
        # 1. 길이 평가 (2점)
        caption_len = len(caption)
        optimal_min, optimal_max = criteria['optimal_length']
        
        if optimal_min <= caption_len <= optimal_max:
            score += 2.0
            feedback.append(f"✅ 캡션 길이가 적절합니다 ({caption_len}자)")
        elif caption_len < optimal_min:
            score += 1.0
            feedback.append(f"⚠️ 캡션이 다소 짧습니다 ({caption_len}자)")
        elif caption_len <= criteria['max_length']:
            score += 1.5
            feedback.append(f"⚠️ 캡션이 다소 깁니다 ({caption_len}자)")
        else:
            score += 0.5
            feedback.append(f"❌ 캡션이 너무 깁니다 ({caption_len}자)")
        
        # 2. 호기심 유발 요소 (3점)
        curiosity_count = sum(1 for word in criteria['curiosity_words'] if word in caption)
        if curiosity_count >= 2:
            score += 3.0
            feedback.append("✅ 호기심을 유발하는 표현이 풍부합니다")
        elif curiosity_count == 1:
            score += 2.0
            feedback.append("✅ 호기심 유발 요소가 포함되어 있습니다")
        else:
            score += 0.5
            feedback.append("❌ 호기심을 유발하는 표현이 부족합니다")
        
        # 3. 개인적 경험/감정 표현 (2점)
        personal_count = sum(1 for word in criteria['personal_words'] if word in caption)
        if personal_count >= 2:
            score += 2.0
            feedback.append("✅ 개인적이고 진정성 있는 표현이 포함되어 있습니다")
        elif personal_count == 1:
            score += 1.0
            feedback.append("⚠️ 더 개인적인 경험을 표현해보세요")
        else:
            score += 0.0
            feedback.append("❌ 개인적 경험 표현이 부족합니다")
        
        # 4. 상호작용 유도 (2점)
        interaction_count = sum(1 for word in criteria['interaction_words'] if word in caption)
        if interaction_count >= 1:
            score += 2.0
            feedback.append("✅ 팔로워와의 상호작용을 유도합니다")
        else:
            score += 0.0
            feedback.append("⚠️ 댓글이나 반응을 유도하는 요소를 추가해보세요")
        
        # 5. 문장 구조와 가독성 (1점)
        sentences = re.split(r'[.!?]', caption)
        avg_sentence_length = sum(len(s.strip()) for s in sentences if s.strip()) / max(len([s for s in sentences if s.strip()]), 1)
        
        if avg_sentence_length <= 30:
            score += 1.0
            feedback.append("✅ 문장 구조가 읽기 쉽습니다")
        else:
            score += 0.5
            feedback.append("⚠️ 문장을 더 간결하게 만들어보세요")
        
        return min(score, 10.0), feedback
    
    def _evaluate_consistency(self, content: Dict[str, str], product_data: Dict[str, Any]) -> float:
        """전체적 일관성 평가"""
        bonus = 0.0
        
        # 모든 요소가 생성되었는지 확인
        if all(content.get(key) for key in ['title', 'hashtags', 'caption']):
            bonus += 0.5
        
        # 제품 정보와의 일관성 확인
        if product_data:
            product_name = product_data.get('제품명', '').lower()
            category = product_data.get('카테고리', '').lower()
            
            all_text = ' '.join(content.values()).lower()
            
            # 제품명 또는 카테고리 언급
            if product_name and any(word in all_text for word in product_name.split()):
                bonus += 0.3
            
            if category and category in all_text:
                bonus += 0.2
        
        # 톤의 일관성 (감정적 vs 정보적)
        emotional_indicators = ['완전', '대박', '진짜', '너무', '정말']
        informational_indicators = ['효과', '성분', '사용법', '특징', '장점']
        
        all_text = ' '.join(content.values())
        emotional_score = sum(1 for word in emotional_indicators if word in all_text)
        info_score = sum(1 for word in informational_indicators if word in all_text)
        
        # 어느 한쪽으로 일관성 있게 기울어져 있으면 보너스
        if emotional_score >= 3 or info_score >= 2:
            bonus += 0.3
        
        return min(bonus, 1.0)
    
    def _get_grade(self, score: float) -> str:
        """점수를 등급으로 변환"""
        if score >= 9.0:
            return "S"
        elif score >= 8.0:
            return "A"
        elif score >= 7.0:
            return "B"
        elif score >= 6.0:
            return "C"
        elif score >= 4.0:
            return "D"
        else:
            return "F"
    
    def _generate_overall_feedback(self, score: float, content: Dict[str, str]) -> str:
        """전체적인 피드백 생성"""
        grade = self._get_grade(score)
        
        if grade == "S":
            return "🎉 완벽한 콘텐츠입니다! 바로 사용하셔도 좋습니다."
        elif grade == "A":
            return "✨ 우수한 콘텐츠입니다. 약간의 수정으로 더욱 완벽해질 수 있습니다."
        elif grade == "B":
            return "👍 괜찮은 콘텐츠입니다. 몇 가지 개선점을 반영해보세요."
        elif grade == "C":
            return "⚠️ 평균적인 수준입니다. 개선이 필요한 부분들이 있습니다."
        elif grade == "D":
            return "🔧 많은 개선이 필요합니다. 다른 템플릿을 시도해보세요."
        else:
            return "❌ 콘텐츠를 다시 생성하는 것을 추천합니다."
    
    def _generate_improvement_suggestions(self, title_score: float, hashtags_score: float, 
                                        caption_score: float, content: Dict[str, str]) -> List[str]:
        """개선 제안 생성"""
        suggestions = []
        
        # 가장 낮은 점수 영역에 대한 구체적 제안
        scores = {
            'title': title_score,
            'hashtags': hashtags_score,
            'caption': caption_score
        }
        
        lowest_component = min(scores.keys(), key=lambda k: scores[k])
        
        if lowest_component == 'title':
            suggestions.extend([
                "💡 제목에 감정적 어필 요소(!, 대박, 완전 등)를 추가해보세요",
                "💡 제목 길이를 10-20자로 조정해보세요",
                "💡 '추천', '후기', '솔직' 같은 참여 유도 키워드를 포함해보세요"
            ])
        
        if lowest_component == 'hashtags':
            suggestions.extend([
                "💡 해시태그를 8-15개 범위로 조정해보세요",
                "💡 제품, 감정, 플랫폼, 트렌드 등 다양한 카테고리 해시태그를 포함해보세요",
                "💡 '#인스타그램', '#릴스', '#일상' 같은 인기 태그를 추가해보세요"
            ])
        
        if lowest_component == 'caption':
            suggestions.extend([
                "💡 캡션에 개인적 경험이나 감정('저는', '정말', '너무' 등)을 표현해보세요",
                "💡 호기심을 유발하는 표현('궁금', '비밀', '놀라운' 등)을 추가해보세요",
                "💡 질문이나 댓글 유도 문구를 포함해보세요"
            ])
        
        # 전체적 개선 제안
        if all(score < 7.0 for score in scores.values()):
            suggestions.append("💡 다른 프롬프트 템플릿을 시도해보세요")
        
        return suggestions[:3]  # 최대 3개까지만 제안

def render_evaluation_results(evaluation: Dict[str, Any]):
    """평가 결과 시각화"""
    st.markdown("### 📊 콘텐츠 품질 분석")
    
    # 전체 점수와 등급
    col1, col2, col3 = st.columns(3)
    
    with col1:
        score = evaluation['total_score']
        grade = evaluation['grade']
        
        # 점수에 따른 색상 결정
        if score >= 8.0:
            color = "green"
        elif score >= 6.0:
            color = "orange"
        else:
            color = "red"
        
        st.metric(
            label="총점",
            value=f"{score}/10",
            delta=f"등급: {grade}"
        )
        
        # 점수 바 차트
        progress_value = score / 10.0
        st.progress(progress_value)
    
    with col2:
        if evaluation['consistency_bonus'] > 0:
            st.metric(
                label="일관성 보너스",
                value=f"+{evaluation['consistency_bonus']}",
                delta="전체적 완성도"
            )
    
    with col3:
        st.markdown(f"**전체 평가**")
        st.info(evaluation['overall_feedback'])
    
    # 세부 항목별 점수
    st.markdown("#### 📋 세부 항목별 분석")
    
    components = evaluation['components']
    
    for component_name, component_data in components.items():
        with st.expander(f"{component_name.upper()} - {component_data['score']}/10점"):
            for feedback_item in component_data['feedback']:
                st.markdown(f"• {feedback_item}")
    
    # 개선 제안
    if evaluation['improvement_suggestions']:
        st.markdown("#### 💡 개선 제안")
        for suggestion in evaluation['improvement_suggestions']:
            st.markdown(f"• {suggestion}")

def batch_evaluate_contents(content_list: List[Dict[str, str]], 
                          product_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """여러 콘텐츠 일괄 평가"""
    evaluator = ContentEvaluator()
    results = []
    
    for i, content in enumerate(content_list):
        evaluation = evaluator.evaluate_content(content, product_data)
        evaluation['content_index'] = i
        results.append(evaluation)
    
    # 점수순으로 정렬
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    return results

if __name__ == "__main__":
    st.title("📊 콘텐츠 품질 평가기 테스트")
    
    # 테스트 콘텐츠
    test_content = {
        'title': '이 제품 진짜 대박! 완전 추천해요',
        'hashtags': '#뷰티 #스킨케어 #추천 #인스타그램 #릴스 #일상 #좋아요 #신상 #트렌드 #화제',
        'caption': '정말 너무 좋아서 여러분께 공유해요! 궁금한 점 있으면 댓글 남겨주세요 😍'
    }
    
    evaluator = ContentEvaluator()
    evaluation = evaluator.evaluate_content(test_content)
    
    render_evaluation_results(evaluation)