"""
S03-002: 수익화 가능 후보 대시보드
매력도 점수별 테이블 표시, 정렬 및 필터링 기능
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

def create_sample_data():
    """샘플 데이터 생성 (실제로는 데이터베이스에서 가져와야 함)"""
    np.random.seed(42)
    
    # 연예인 채널 목록
    channels = [
        "홍지윤 Yoon", "아이유IU", "이사배(RISABAE)", "다영 DAYOUNG",
        "소이와여니", "윰댕Yummy D", "SEJEONG OFFICIAL", "수린 SURIN",
        "김희철 KimHeeChul", "강미나 Mina Kang"
    ]
    
    # 제품 카테고리
    categories = [
        "스킨케어", "메이크업", "헤어케어", "패션", "향수", 
        "액세서리", "홈인테리어", "건강식품", "전자기기", "라이프스타일"
    ]
    
    # 샘플 데이터 생성
    num_samples = 45
    data = []
    
    for i in range(num_samples):
        # 매력도 스코어 생성 (정규분포, 높은 점수에 가중치)
        score = min(100, max(20, np.random.normal(75, 15)))
        
        # 영상 정보
        channel = np.random.choice(channels)
        upload_date = datetime.now() - timedelta(days=np.random.randint(1, 30))
        
        # 제품 정보
        category = np.random.choice(categories)
        
        # 제품명 생성
        product_names = {
            "스킨케어": ["히알루론산 세럼", "비타민C 크림", "카시아 토너", "콜라겐 마스크"],
            "메이크업": ["글로우 파운데이션", "틴트 립", "아이섀도우 팔레트", "컨실러"],
            "헤어케어": ["아르간 오일 샴푸", "단백질 트리트먼트", "헤어 세럼", "드라이 샴푸"],
            "패션": ["오버사이즈 후드티", "와이드 데님", "니트 가디건", "원피스"],
            "향수": ["플로럴 향수", "우디 향수", "시트러스 향수", "머스크 향수"],
            "액세서리": ["실버 목걸이", "진주 귀걸이", "가죽 시계", "크로스백"],
            "홈인테리어": ["디퓨저", "캔들", "쿠션", "블랙아웃 커튼"],
            "건강식품": ["비타민D", "오메가3", "프로바이오틱스", "콜라겐"],
            "전자기기": ["무선 이어폰", "스마트워치", "노트북", "태블릿"],
            "라이프스타일": ["텀블러", "요가매트", "플래너", "향초"]
        }
        
        product_name = f"{np.random.choice(product_names[category])} - {np.random.choice(['프리미엄', '에센셜', '럭셔리', '내추럴'])}"
        
        # 가격 정보
        price_ranges = {
            "스킨케어": (15000, 80000),
            "메이크업": (10000, 50000), 
            "헤어케어": (12000, 35000),
            "패션": (25000, 150000),
            "향수": (30000, 120000),
            "액세서리": (15000, 80000),
            "홈인테리어": (20000, 100000),
            "건강식품": (15000, 60000),
            "전자기기": (50000, 300000),
            "라이프스타일": (10000, 50000)
        }
        
        min_price, max_price = price_ranges[category]
        price = np.random.randint(min_price, max_price)
        
        # 분석 결과 생성
        sentiment_score = np.random.uniform(0.6, 0.95)
        usage_evidence = np.random.uniform(0.4, 0.9)
        influencer_trust = np.random.uniform(0.7, 1.0)
        
        # 상태 생성
        statuses = ["대기중", "검토중", "승인됨", "반려됨", "수정필요"]
        weights = [0.3, 0.2, 0.25, 0.15, 0.1]  # 대기중과 승인됨에 가중치
        status = np.random.choice(statuses, p=weights)
        
        # 타임스탬프 생성
        start_time = np.random.randint(30, 600)  # 30초 ~ 10분
        duration = np.random.randint(15, 120)    # 15초 ~ 2분
        
        data.append({
            "id": f"PROD_{i+1:03d}",
            "매력도_점수": round(score, 1),
            "채널명": channel,
            "영상_제목": f"[일상VLOG] {category} 추천 | 솔직 후기",
            "제품명": product_name,
            "카테고리": category,
            "예상_가격": f"{price:,}원",
            "감성_강도": round(sentiment_score, 2),
            "실사용_인증": round(usage_evidence, 2), 
            "인플루언서_신뢰도": round(influencer_trust, 2),
            "상태": status,
            "업로드_날짜": upload_date.strftime("%Y-%m-%d"),
            "분석_완료_시간": (upload_date + timedelta(hours=np.random.randint(1, 12))).strftime("%Y-%m-%d %H:%M"),
            "타임스탬프": f"{start_time//60:02d}:{start_time%60:02d} - {(start_time+duration)//60:02d}:{(start_time+duration)%60:02d}",
            "조회수": f"{np.random.randint(5000, 500000):,}",
            "영상_길이": f"{np.random.randint(5, 25):02d}:{np.random.randint(0, 59):02d}",
            "youtube_url": f"https://www.youtube.com/watch?v=sample_{i+1}"
        })
    
    return pd.DataFrame(data)

def apply_filters(df, search_term, category_filter, status_filter, score_range):
    """필터 적용"""
    filtered_df = df.copy()
    
    # 검색어 필터
    if search_term:
        search_cols = ['채널명', '제품명', '영상_제목']
        mask = False
        for col in search_cols:
            mask |= filtered_df[col].str.contains(search_term, case=False, na=False)
        filtered_df = filtered_df[mask]
    
    # 카테고리 필터
    if category_filter != "전체":
        filtered_df = filtered_df[filtered_df['카테고리'] == category_filter]
    
    # 상태 필터
    if status_filter != "전체":
        filtered_df = filtered_df[filtered_df['상태'] == status_filter]
    
    # 점수 범위 필터
    min_score, max_score = score_range
    filtered_df = filtered_df[
        (filtered_df['매력도_점수'] >= min_score) & 
        (filtered_df['매력도_점수'] <= max_score)
    ]
    
    return filtered_df

def render_status_badge(status):
    """상태 배지 렌더링"""
    colors = {
        "대기중": "🟡",
        "검토중": "🔵", 
        "승인됨": "🟢",
        "반려됨": "🔴",
        "수정필요": "🟠"
    }
    return f"{colors.get(status, '⚪')} {status}"

def render_monetizable_candidates():
    """수익화 가능 후보 페이지 렌더링"""
    st.markdown("## 💰 수익화 가능 후보 관리")
    
    # 데이터 로드
    if 'candidates_data' not in st.session_state:
        with st.spinner("데이터를 불러오는 중..."):
            st.session_state.candidates_data = create_sample_data()
    
    df = st.session_state.candidates_data
    
    # 필터 컨트롤
    st.markdown("### 🔍 필터 및 검색")
    
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    
    with col1:
        search_term = st.text_input(
            "🔍 검색 (채널명, 제품명, 영상 제목)",
            placeholder="검색어를 입력하세요..."
        )
    
    with col2:
        categories = ["전체"] + sorted(df['카테고리'].unique().tolist())
        category_filter = st.selectbox("카테고리", categories)
    
    with col3:
        statuses = ["전체"] + sorted(df['상태'].unique().tolist())
        status_filter = st.selectbox("상태", statuses)
    
    with col4:
        score_range = st.slider(
            "매력도 점수 범위",
            min_value=0,
            max_value=100,
            value=(50, 100),
            step=5
        )
    
    # 필터 적용
    filtered_df = apply_filters(df, search_term, category_filter, status_filter, score_range)
    
    # 통계 정보
    st.markdown("### 📊 현황 요약")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("전체 후보", len(df))
    with col2:
        st.metric("필터링 결과", len(filtered_df))
    with col3:
        avg_score = filtered_df['매력도_점수'].mean() if len(filtered_df) > 0 else 0
        st.metric("평균 점수", f"{avg_score:.1f}")
    with col4:
        approved = len(filtered_df[filtered_df['상태'] == '승인됨'])
        st.metric("승인됨", approved)
    with col5:
        pending = len(filtered_df[filtered_df['상태'] == '대기중'])
        st.metric("대기중", pending)
    
    # 데이터 테이블
    st.markdown("### 📋 후보 목록")
    
    if len(filtered_df) == 0:
        st.warning("검색 조건에 맞는 데이터가 없습니다.")
        return
    
    # 정렬 옵션
    col1, col2 = st.columns([1, 1])
    with col1:
        sort_column = st.selectbox(
            "정렬 기준",
            ["매력도_점수", "업로드_날짜", "감성_강도", "실사용_인증", "인플루언서_신뢰도"]
        )
    with col2:
        sort_ascending = st.selectbox("정렬 순서", ["내림차순", "오름차순"]) == "오름차순"
    
    # 정렬 적용
    sorted_df = filtered_df.sort_values(sort_column, ascending=sort_ascending)
    
    # 페이지네이션
    items_per_page = st.selectbox("페이지당 항목 수", [10, 20, 50, 100], index=1)
    total_pages = (len(sorted_df) - 1) // items_per_page + 1
    
    if total_pages > 1:
        page_number = st.number_input(
            f"페이지 (1-{total_pages})",
            min_value=1,
            max_value=total_pages,
            value=1
        )
    else:
        page_number = 1
    
    # 현재 페이지 데이터
    start_idx = (page_number - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = sorted_df.iloc[start_idx:end_idx]
    
    # 테이블 표시
    st.markdown(f"**{start_idx + 1}-{min(end_idx, len(sorted_df))} / {len(sorted_df)} 항목**")
    
    # 상세한 테이블 렌더링
    for idx, row in page_df.iterrows():
        with st.expander(f"🎯 {row['제품명']} (점수: {row['매력도_점수']})"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"""
                **📺 채널**: {row['채널명']}  
                **🎬 영상**: {row['영상_제목']}  
                **🏷️ 카테고리**: {row['카테고리']}  
                **💰 예상 가격**: {row['예상_가격']}  
                **📅 업로드**: {row['업로드_날짜']}  
                **⏰ 타임스탬프**: {row['타임스탬프']}  
                **👀 조회수**: {row['조회수']}
                """)
            
            with col2:
                st.markdown("**📊 분석 지표**")
                st.progress(row['감성_강도'], text=f"감성 강도: {row['감성_강도']:.2f}")
                st.progress(row['실사용_인증'], text=f"실사용 인증: {row['실사용_인증']:.2f}")
                st.progress(row['인플루언서_신뢰도'], text=f"신뢰도: {row['인플루언서_신뢰도']:.2f}")
                
                st.markdown(f"**상태**: {render_status_badge(row['상태'])}")
            
            # 액션 버튼
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                if st.button("✅ 승인", key=f"approve_{row['id']}"):
                    st.success(f"{row['제품명']} 승인됨")
            with col2:
                if st.button("❌ 반려", key=f"reject_{row['id']}"):
                    st.error(f"{row['제품명']} 반려됨")
            with col3:
                if st.button("✏️ 수정", key=f"edit_{row['id']}"):
                    st.info(f"{row['제품명']} 수정 모드")
            with col4:
                if st.button("📹 영상보기", key=f"video_{row['id']}"):
                    st.info("영상 재생 기능은 S03-004에서 구현됩니다.")
            with col5:
                if st.button("📊 상세", key=f"detail_{row['id']}"):
                    # 상세 뷰로 이동
                    st.session_state.selected_product = row.to_dict()
                    st.session_state.current_page = 'detail_view'
                    st.rerun()
    
    # 데이터 내보내기
    st.markdown("---")
    st.markdown("### 📤 데이터 내보내기")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 CSV 다운로드",
            data=csv,
            file_name=f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        json_data = filtered_df.to_json(orient='records', force_ascii=False, indent=2)
        st.download_button(
            label="🔧 JSON 다운로드", 
            data=json_data,
            file_name=f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col3:
        if st.button("🔄 데이터 새로고침"):
            st.session_state.pop('candidates_data', None)
            st.rerun()

if __name__ == "__main__":
    render_monetizable_candidates()