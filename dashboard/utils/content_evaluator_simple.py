"""
간단한 콘텐츠 평가자 (의존성 최소화)
"""

import streamlit as st
from typing import Dict, List, Any
import random

class ContentEvaluator:
    def evaluate_content(self, content: Dict[str, str], product_data: Dict[str, Any]) -> Dict[str, Any]:
        """콘텐츠 품질 평가"""
        
        # 간단한 평가 로직
        score = random.uniform(7.0, 9.5)
        
        if score >= 9.0:
            grade = "A"
        elif score >= 8.0:
            grade = "B"
        elif score >= 7.0:
            grade = "C"
        else:
            grade = "D"
        
        return {
            'total_score': score,
            'grade': grade,
            'engagement_score': random.uniform(7.0, 10.0),
            'readability_score': random.uniform(7.0, 10.0),
            'emotion_score': random.uniform(6.0, 9.0),
            'suggestions': ["더 감정적인 표현 추가", "해시태그 최적화"]
        }

def render_evaluation_results(evaluation: Dict[str, Any]):
    """평가 결과 표시"""
    st.markdown("#### 📊 품질 평가")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총점", f"{evaluation['total_score']:.1f}/10")
    
    with col2:
        st.metric("등급", evaluation['grade'])
    
    with col3:
        st.metric("참여도", f"{evaluation['engagement_score']:.1f}/10")
    
    with col4:
        st.metric("가독성", f"{evaluation['readability_score']:.1f}/10")

def batch_evaluate_contents(contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """배치 콘텐츠 평가"""
    evaluator = ContentEvaluator()
    results = []
    
    for content in contents:
        evaluation = evaluator.evaluate_content(content, {})
        results.append({**content, 'evaluation': evaluation})
    
    return results