"""
S03-002: 수익화 가능 후보 대시보드
매력도 점수별 테이블 표시, 정렬 및 필터링 기능
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dashboard.components.workflow_state_manager import WorkflowStateManager
    from dashboard.utils.database_manager import get_database_manager
except ImportError:
    WorkflowStateManager = None
    get_database_manager = None

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
        
        # 상태 생성 (PRD SPEC-DASH-05 기준)
        statuses = ["needs_review", "approved", "rejected", "under_revision", "published"]
        weights = [0.4, 0.25, 0.15, 0.1, 0.1]  # needs_review에 가중치
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
    """상태 배지 렌더링 (워크플로우 상태 관리 시스템 연동)"""
    if WorkflowStateManager:
        manager = WorkflowStateManager()
        return manager.render_status_badge(status)
    else:
        # 폴백: 기본 상태 표시
        colors = {
            "needs_review": "🟡 검토 대기",
            "approved": "🟢 승인됨",
            "rejected": "🔴 반려됨",
            "under_revision": "🟠 수정중",
            "published": "🚀 업로드 완료",
            "filtered_no_coupang": "🔗 수익화 불가"
        }
        return colors.get(status, f"⚪ {status}")

def render_monetizable_candidates():
    """수익화 가능 후보 페이지 렌더링"""
    
    # 반응형 CSS 스타일 추가
    st.markdown("""
    <style>
    /* 테이블 반응형 스타일 */
    .stDataFrame {
        width: 100%;
        overflow-x: auto;
    }
    
    /* 모바일 환경 대응 */
    @media (max-width: 768px) {
        .stDataFrame table {
            font-size: 12px;
        }
        
        .stColumns > div {
            min-width: 0;
            padding: 0 0.25rem;
        }
        
        .stButton button {
            font-size: 12px;
            padding: 0.25rem 0.5rem;
        }
    }
    
    /* 점수 컬럼 강조 */
    .stDataFrame table td:first-child {
        font-weight: bold;
        background-color: rgba(255, 193, 7, 0.1);
    }
    
    /* 상태 배지 스타일 */
    .status-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("## 💰 수익화 가능 후보 관리")
    
    # 데이터 로드
    if 'candidates_data' not in st.session_state:
        with st.spinner("🔄 후보 데이터를 불러오는 중입니다..."):
            # 로딩 상태 표시를 위한 프로그레스 바
            progress_bar = st.progress(0, text="데이터베이스 연결 중...")
            progress_bar.progress(30, text="후보 목록 조회 중...")
            progress_bar.progress(70, text="분석 데이터 로드 중...")
            st.session_state.candidates_data = create_sample_data()
            progress_bar.progress(100, text="로드 완료!")
            progress_bar.empty()  # 프로그레스 바 제거
    
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
        st.markdown("### 🔍 검색 결과가 없습니다")
        st.info("""
        현재 설정된 필터 조건에 맞는 후보가 없습니다.
        
        **💡 해결 방법:**
        - 검색어를 다시 확인해주세요
        - 카테고리 필터를 '전체'로 변경해보세요  
        - 상태 필터를 '전체'로 변경해보세요
        - 매력도 점수 범위를 넓혀보세요
        """)
        
        # 필터 초기화 버튼
        if st.button("🔄 모든 필터 초기화"):
            st.rerun()
        return
    
    # 정렬 옵션 - 더 직관적인 UI
    st.markdown("**📊 정렬 및 표시 옵션**")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        sort_options = {
            "매력도_점수": "🎯 매력도 점수",
            "업로드_날짜": "📅 업로드 날짜", 
            "감성_강도": "❤️ 감성 강도",
            "실사용_인증": "✅ 실사용 인증",
            "인플루언서_신뢰도": "⭐ 인플루언서 신뢰도",
            "채널명": "📺 채널명",
            "제품명": "🎯 제품명"
        }
        sort_column = st.selectbox(
            "정렬 기준",
            options=list(sort_options.keys()),
            format_func=lambda x: sort_options[x],
            index=0
        )
    
    with col2:
        sort_ascending = st.selectbox(
            "정렬 순서", 
            ["내림차순 ⬇️", "오름차순 ⬆️"]
        ) == "오름차순 ⬆️"
    
    with col3:
        # 컬럼 표시/숨김 옵션
        show_detailed_columns = st.checkbox("상세 컬럼 표시", value=True)
    
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
    
    # 테이블용 컬럼 선택 및 정리 - 상세 표시 옵션에 따라 조정
    if show_detailed_columns:
        display_columns = [
            '매력도_점수', '채널명', '영상_제목', '제품명', '카테고리', 
            '상태', '업로드_날짜', '타임스탬프', '조회수'
        ]
        column_names = ['점수', '채널명', '영상 제목', '제품명', '카테고리', '상태', '업로드일', '구간', '조회수']
    else:
        display_columns = [
            '매력도_점수', '채널명', '제품명', '상태', '업로드_날짜'
        ] 
        column_names = ['점수', '채널명', '제품명', '상태', '업로드일']
    
    # 테이블 데이터 준비
    table_df = page_df[display_columns].copy()
    
    # 컬럼명 한국어로 정리
    table_df.columns = column_names
    
    # 상태 컬럼에 이모지 추가
    table_df['상태'] = table_df['상태'].apply(render_status_badge)
    
    # 클릭 가능한 테이블 렌더링 
    st.markdown("**💡 행을 클릭하면 상세 정보를 볼 수 있습니다.**")
    
    # Streamlit dataframe with selection
    selected_rows = st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # 선택된 행 처리
    if selected_rows and len(selected_rows.selection.rows) > 0:
        selected_idx = selected_rows.selection.rows[0]
        selected_row = page_df.iloc[start_idx + selected_idx]
        
        st.markdown("---")
        st.markdown("### 📋 선택된 후보 상세 정보")
        
        # 상세 정보 표시
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"""
            **📺 채널**: {selected_row['채널명']}  
            **🎬 영상**: {selected_row['영상_제목']}  
            **🎯 제품**: {selected_row['제품명']}  
            **🏷️ 카테고리**: {selected_row['카테고리']}  
            **💰 예상 가격**: {selected_row['예상_가격']}  
            **📅 업로드**: {selected_row['업로드_날짜']}  
            **⏰ 타임스탬프**: {selected_row['타임스탬프']}  
            **👀 조회수**: {selected_row['조회수']}  
            **🎞️ 영상 길이**: {selected_row['영상_길이']}
            """)
        
        with col2:
            st.markdown("**📊 분석 지표**")
            st.progress(selected_row['감성_강도'], text=f"감성 강도: {selected_row['감성_강도']:.2f}")
            st.progress(selected_row['실사용_인증'], text=f"실사용 인증: {selected_row['실사용_인증']:.2f}")
            st.progress(selected_row['인플루언서_신뢰도'], text=f"신뢰도: {selected_row['인플루언서_신뢰도']:.2f}")
            
            st.markdown(f"**상태**: {render_status_badge(selected_row['상태'])}")
        
        # 액션 버튼
        st.markdown("**🎛️ 액션**")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("✅ 승인", key=f"approve_{selected_row['id']}"):
                st.success(f"{selected_row['제품명']} 승인되었습니다!")
        with col2:
            if st.button("❌ 반려", key=f"reject_{selected_row['id']}"):
                st.error(f"{selected_row['제품명']} 반려되었습니다!")
        with col3:
            if st.button("✏️ 수정", key=f"edit_{selected_row['id']}"):
                st.info(f"{selected_row['제품명']} 수정 모드로 전환합니다.")
        with col4:
            if st.button("📹 영상보기", key=f"video_{selected_row['id']}"):
                st.info("영상 재생 기능은 T06에서 구현 예정입니다.")
        with col5:
            if st.button("📊 상세뷰", key=f"detail_{selected_row['id']}"):
                # 상세 뷰로 이동
                st.session_state.selected_product = selected_row.to_dict()
                st.session_state.current_page = 'detail_view'
                st.rerun()
    
    # 빈 상태 처리
    elif len(page_df) == 0:
        st.markdown("### 📭 데이터가 없습니다")
        st.info("현재 표시할 후보가 없습니다. 필터 조건을 조정해보세요.")
    
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