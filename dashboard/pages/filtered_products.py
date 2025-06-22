"""
S03-003: 수익화 필터링 목록 대시보드
쿠팡 검색 실패 제품 관리 및 수동 링크 연결
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import re

def create_filtered_sample_data():
    """필터링된 제품 샘플 데이터 생성"""
    np.random.seed(123)
    
    # 연예인 채널 목록
    channels = [
        "홍지윤 Yoon", "아이유IU", "이사배(RISABAE)", "다영 DAYOUNG",
        "소이와여니", "윰댕Yummy D", "SEJEONG OFFICIAL", "수린 SURIN"
    ]
    
    # 필터링 사유 유형
    filter_reasons = [
        "쿠팡 API 검색 결과 없음",
        "브랜드명 불일치",
        "단종된 제품",
        "해외 브랜드 (쿠팡 미취급)",
        "제품명 불분명",
        "가격 정보 부족",
        "카테고리 매칭 실패"
    ]
    
    # 제품 카테고리
    categories = [
        "스킨케어", "메이크업", "헤어케어", "패션", "향수", 
        "액세서리", "홈인테리어", "건강식품", "전자기기", "라이프스타일"
    ]
    
    # 샘플 데이터 생성
    num_samples = 18
    data = []
    
    for i in range(num_samples):
        channel = np.random.choice(channels)
        category = np.random.choice(categories)
        filter_reason = np.random.choice(filter_reasons)
        detected_date = datetime.now() - timedelta(days=np.random.randint(1, 15))
        
        # 제품명 생성 (일부러 모호하거나 검색이 어려운 제품명으로 설정)
        problem_products = {
            "스킨케어": ["그 브랜드 세럼", "화장품 가게에서 산 크림", "일본에서 구매한 토너", "언니가 추천한 마스크"],
            "메이크업": ["요즘 핫한 파운데이션", "인스타에서 본 틴트", "해외 직구 팔레트", "브랜드명 모르는 컨실러"],
            "헤어케어": ["미용실 전용 샴푸", "세일즈 샴푸", "외국 브랜드 트리트먼트", "프로페셔널 헤어세럼"],
            "패션": ["작년에 산 후드티", "해외쇼핑몰 원피스", "온라인몰 데님", "브랜드 불명 가디건"],
            "향수": ["면세점 향수", "해외 브랜드 향수", "리미티드 에디션 향수", "단종된 향수"],
            "액세서리": ["핸드메이드 목걸이", "빈티지 귀걸이", "수제 시계", "브랜드 없는 백"],
            "홈인테리어": ["카페에서 본 디퓨저", "수입 캔들", "주문제작 쿠션", "맞춤 커튼"],
            "건강식품": ["병원 추천 비타민", "해외직구 오메가3", "일본산 프로바이오틱스", "수입 콜라겐"],
            "전자기기": ["신제품 이어폰", "해외 출시 스마트워치", "단종 모델 노트북", "중국 브랜드 태블릿"],
            "라이프스타일": ["카페 텀블러", "요가 스튜디오 매트", "핸드메이드 플래너", "아티스트 향초"]
        }
        
        product_name = np.random.choice(problem_products[category])
        
        # 제품 분석 점수 (필터링되었지만 나름 괜찮은 점수들)
        attraction_score = np.random.uniform(45, 85)
        
        # 상태 (필터링된 제품들의 상태)
        statuses = ["검색실패", "수동연결대기", "재검토중", "연결완료", "최종제외"]
        weights = [0.4, 0.3, 0.15, 0.1, 0.05]
        status = np.random.choice(statuses, p=weights)
        
        # 타임스탬프 
        start_time = np.random.randint(60, 900)  # 1분 ~ 15분
        duration = np.random.randint(20, 180)    # 20초 ~ 3분
        
        data.append({
            "id": f"FILT_{i+1:03d}",
            "제품명": product_name,
            "카테고리": category,
            "채널명": channel,
            "영상_제목": f"[VLOG] {category} 솔직 리뷰 | 실패템 vs 성공템",
            "필터링_사유": filter_reason,
            "매력도_점수": round(attraction_score, 1),
            "감지_날짜": detected_date.strftime("%Y-%m-%d"),
            "상태": status,
            "타임스탬프": f"{start_time//60:02d}:{start_time%60:02d} - {(start_time+duration)//60:02d}:{(start_time+duration)%60:02d}",
            "조회수": f"{np.random.randint(8000, 200000):,}",
            "수동_링크": "" if status != "연결완료" else f"https://coupa.ng/sample_{i+1}",
            "검색_키워드": "",
            "메모": "",
            "처리자": "시스템" if status == "검색실패" else "",
            "처리_일시": detected_date.strftime("%Y-%m-%d %H:%M") if status == "검색실패" else "",
            "youtube_url": f"https://www.youtube.com/watch?v=filtered_{i+1}"
        })
    
    return pd.DataFrame(data)

def apply_filtered_filters(df, search_term, category_filter, status_filter, reason_filter):
    """필터 적용"""
    filtered_df = df.copy()
    
    # 검색어 필터
    if search_term:
        search_cols = ['제품명', '채널명', '영상_제목', '검색_키워드']
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
    
    # 필터링 사유 필터
    if reason_filter != "전체":
        filtered_df = filtered_df[filtered_df['필터링_사유'] == reason_filter]
    
    return filtered_df

def render_status_badge_filtered(status):
    """필터링 제품 상태 배지 렌더링"""
    colors = {
        "검색실패": "🔴",
        "수동연결대기": "🟡",
        "재검토중": "🔵",
        "연결완료": "🟢",
        "최종제외": "⚫"
    }
    return f"{colors.get(status, '⚪')} {status}"

def render_manual_link_form(product_id, current_link=""):
    """수동 링크 연결 폼"""
    with st.form(f"link_form_{product_id}"):
        st.markdown("#### 🔗 수동 링크 연결")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            manual_link = st.text_input(
                "쿠팡 파트너스 링크",
                value=current_link,
                placeholder="https://coupa.ng/..."
            )
            
            keywords = st.text_input(
                "검색 키워드 (옵션)",
                placeholder="제품 검색에 사용할 키워드를 입력하세요"
            )
            
            memo = st.text_area(
                "메모 (옵션)",
                placeholder="추가 정보나 특이사항을 입력하세요"
            )
        
        with col2:
            st.markdown("**🔍 보조 검색**")
            
            if st.form_submit_button("Google 검색", use_container_width=True):
                st.info("Google 검색 기능은 S03-006에서 구현됩니다.")
            
            if st.form_submit_button("네이버 검색", use_container_width=True):
                st.info("네이버 검색 기능은 S03-006에서 구현됩니다.")
            
            if st.form_submit_button("쿠팡 직접 검색", use_container_width=True):
                st.info("쿠팡 검색 기능은 S03-006에서 구현됩니다.")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            submit_connect = st.form_submit_button("✅ 링크 연결", type="primary")
        with col2:
            submit_restore = st.form_submit_button("🔄 메인 복원")
        with col3:
            submit_exclude = st.form_submit_button("❌ 최종 제외")
        
        if submit_connect and manual_link:
            if re.match(r'https?://coupa\.ng/[a-zA-Z0-9]+', manual_link):
                st.success(f"✅ 링크가 연결되었습니다! 메인 목록으로 복원됩니다.")
                st.balloons()
                return "연결완료", manual_link, keywords, memo
            else:
                st.error("올바른 쿠팡 파트너스 링크 형식이 아닙니다. (https://coupa.ng/...)")
        
        elif submit_restore:
            st.success("🔄 메인 목록으로 복원되었습니다!")
            return "복원완료", "", keywords, memo
        
        elif submit_exclude:
            st.warning("❌ 최종 제외 처리되었습니다.")
            return "최종제외", "", keywords, memo
        
        elif submit_connect and not manual_link:
            st.error("링크를 입력해주세요.")
    
    return None, current_link, "", ""

def render_filtered_products():
    """수익화 필터링 목록 페이지 렌더링"""
    st.markdown("## 🔍 필터링된 제품 관리")
    
    # 데이터 로드
    if 'filtered_data' not in st.session_state:
        with st.spinner("필터링된 데이터를 불러오는 중..."):
            st.session_state.filtered_data = create_filtered_sample_data()
    
    df = st.session_state.filtered_data
    
    # 안내 메시지
    st.info("""
    🔍 **필터링된 제품 관리**  
    자동 수익화 검증 과정에서 쿠팡 파트너스 API 검색에 실패한 제품들을 관리합니다.  
    수동으로 제품을 검색하여 링크를 연결하거나, 메인 목록으로 복원할 수 있습니다.
    """)
    
    # 필터 컨트롤
    st.markdown("### 🔍 필터 및 검색")
    
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    
    with col1:
        search_term = st.text_input(
            "🔍 검색 (제품명, 채널명, 키워드)",
            placeholder="검색어를 입력하세요..."
        )
    
    with col2:
        categories = ["전체"] + sorted(df['카테고리'].unique().tolist())
        category_filter = st.selectbox("카테고리", categories)
    
    with col3:
        statuses = ["전체"] + sorted(df['상태'].unique().tolist())
        status_filter = st.selectbox("상태", statuses)
    
    with col4:
        reasons = ["전체"] + sorted(df['필터링_사유'].unique().tolist())
        reason_filter = st.selectbox("필터링 사유", reasons)
    
    # 필터 적용
    filtered_df = apply_filtered_filters(df, search_term, category_filter, status_filter, reason_filter)
    
    # 통계 정보
    st.markdown("### 📊 현황 요약")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("총 필터링", len(df))
    with col2:
        st.metric("검색 결과", len(filtered_df))
    with col3:
        search_failed = len(df[df['상태'] == '검색실패'])
        st.metric("검색실패", search_failed)
    with col4:
        waiting = len(df[df['상태'] == '수동연결대기'])
        st.metric("연결대기", waiting)
    with col5:
        connected = len(df[df['상태'] == '연결완료'])
        st.metric("연결완료", connected)
    
    # 필터링 사유 분석
    st.markdown("### 📈 필터링 사유 분석")
    reason_counts = df['필터링_사유'].value_counts()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.bar_chart(reason_counts)
    with col2:
        st.markdown("**주요 필터링 사유**")
        for reason, count in reason_counts.head(5).items():
            percentage = (count / len(df)) * 100
            st.metric(reason, f"{count}개", f"{percentage:.1f}%")
    
    # 데이터 테이블
    st.markdown("### 📋 필터링된 제품 목록")
    
    if len(filtered_df) == 0:
        st.warning("검색 조건에 맞는 데이터가 없습니다.")
        return
    
    # 정렬 옵션
    col1, col2 = st.columns([1, 1])
    with col1:
        sort_column = st.selectbox(
            "정렬 기준",
            ["감지_날짜", "매력도_점수", "상태", "필터링_사유"]
        )
    with col2:
        sort_ascending = st.selectbox("정렬 순서", ["내림차순", "오름차순"]) == "오름차순"
    
    # 정렬 적용
    sorted_df = filtered_df.sort_values(sort_column, ascending=sort_ascending)
    
    # 페이지네이션
    items_per_page = st.selectbox("페이지당 항목 수", [5, 10, 20], index=1)
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
    
    # 상세한 제품 관리 인터페이스
    for idx, row in page_df.iterrows():
        with st.expander(f"🔍 {row['제품명']} (점수: {row['매력도_점수']}) - {render_status_badge_filtered(row['상태'])}"):
            
            # 기본 정보 표시
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"""
                **📺 채널**: {row['채널명']}  
                **🎬 영상**: {row['영상_제목']}  
                **🏷️ 카테고리**: {row['카테고리']}  
                **📅 감지 날짜**: {row['감지_날짜']}  
                **⏰ 타임스탬프**: {row['타임스탬프']}  
                **👀 조회수**: {row['조회수']}  
                **🚫 필터링 사유**: {row['필터링_사유']}
                """)
                
                if row['수동_링크']:
                    st.markdown(f"**🔗 연결된 링크**: {row['수동_링크']}")
                
                if row['검색_키워드']:
                    st.markdown(f"**🔍 검색 키워드**: {row['검색_키워드']}")
                
                if row['메모']:
                    st.markdown(f"**📝 메모**: {row['메모']}")
            
            with col2:
                st.markdown("**📊 제품 정보**")
                st.progress(row['매력도_점수']/100, text=f"매력도: {row['매력도_점수']:.1f}")
                
                st.markdown(f"**상태**: {render_status_badge_filtered(row['상태'])}")
                
                if row['처리자']:
                    st.markdown(f"**처리자**: {row['처리자']}")
                
                if row['처리_일시']:
                    st.markdown(f"**처리시간**: {row['처리_일시']}")
            
            # 수동 처리 인터페이스 (검색실패나 수동연결대기 상태일 때만)
            if row['상태'] in ['검색실패', '수동연결대기', '재검토중']:
                st.markdown("---")
                action, link, keywords, memo = render_manual_link_form(
                    row['id'], 
                    row['수동_링크']
                )
                
                # 액션 처리 (실제로는 데이터베이스 업데이트)
                if action:
                    st.success(f"처리 완료: {action}")
            
            # 추가 액션 버튼들
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("📹 영상보기", key=f"video_{row['id']}"):
                    st.info("영상 재생 기능은 S03-004에서 구현됩니다.")
            
            with col2:
                if st.button("📊 상세분석", key=f"detail_{row['id']}"):
                    # 상세 뷰로 이동
                    st.session_state.selected_product = row.to_dict()
                    st.session_state.current_page = 'detail_view'
                    st.rerun()
            
            with col3:
                if st.button("🔄 재분석", key=f"reanalyze_{row['id']}"):
                    st.info("재분석 기능은 향후 구현됩니다.")
            
            with col4:
                if st.button("📋 이력보기", key=f"history_{row['id']}"):
                    st.info("처리 이력 기능은 S03-007에서 구현됩니다.")
    
    # 일괄 처리 기능
    st.markdown("---")
    st.markdown("### 🔧 일괄 처리 도구")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 검색실패 → 대기상태", use_container_width=True):
            failed_count = len(filtered_df[filtered_df['상태'] == '검색실패'])
            st.success(f"{failed_count}개 항목이 수동연결대기 상태로 변경되었습니다.")
    
    with col2:
        if st.button("❌ 오래된 항목 정리", use_container_width=True):
            old_count = len(filtered_df[filtered_df['감지_날짜'] < (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")])
            st.warning(f"{old_count}개의 오래된 항목이 정리되었습니다.")
    
    with col3:
        if st.button("📊 필터링 리포트", use_container_width=True):
            st.info("리포트 생성 기능은 향후 구현됩니다.")
    
    # 데이터 내보내기
    st.markdown("---")
    st.markdown("### 📤 데이터 내보내기")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 CSV 다운로드",
            data=csv,
            file_name=f"filtered_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        json_data = filtered_df.to_json(orient='records', force_ascii=False, indent=2)
        st.download_button(
            label="🔧 JSON 다운로드",
            data=json_data,
            file_name=f"filtered_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col3:
        if st.button("🔄 데이터 새로고침"):
            st.session_state.pop('filtered_data', None)
            st.rerun()

if __name__ == "__main__":
    render_filtered_products()