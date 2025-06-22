"""
T04_S01_M02: Advanced Data Table Component with Sorting, Filtering & Pagination
PRD SPEC-DASH-01 핵심 요구사항인 고급 정렬 및 필터링 시스템 구현
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import time


class AdvancedDataTable:
    """고급 데이터 테이블 컴포넌트 클래스"""
    
    def __init__(self, data: pd.DataFrame, table_id: str = "data_table"):
        """
        Advanced Data Table 초기화
        
        Args:
            data: 표시할 DataFrame
            table_id: 테이블 고유 식별자 (세션 상태 키로 사용)
        """
        self.data = data.copy()
        self.table_id = table_id
        self.session_key_prefix = f"{table_id}_"
        
        # 초기 상태 설정
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """세션 상태 초기화"""
        session_keys = {
            f"{self.session_key_prefix}sort_column": "매력도_점수",
            f"{self.session_key_prefix}sort_ascending": False,
            f"{self.session_key_prefix}search_term": "",
            f"{self.session_key_prefix}current_page": 1,
            f"{self.session_key_prefix}items_per_page": 20,
            f"{self.session_key_prefix}category_filter": "전체",
            f"{self.session_key_prefix}status_filter": "전체",
            f"{self.session_key_prefix}score_range": (0, 100)
        }
        
        for key, default_value in session_keys.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    def _get_session_value(self, key: str) -> Any:
        """세션 상태 값 가져오기"""
        return st.session_state.get(f"{self.session_key_prefix}{key}")
    
    def _set_session_value(self, key: str, value: Any):
        """세션 상태 값 설정"""
        st.session_state[f"{self.session_key_prefix}{key}"] = value
    
    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """모든 필터 적용"""
        filtered_df = df.copy()
        
        # 검색어 필터
        search_term = self._get_session_value("search_term")
        if search_term:
            search_cols = ['채널명', '제품명', '영상_제목'] if '영상_제목' in df.columns else ['채널명', '제품명']
            mask = pd.Series([False] * len(filtered_df))
            
            for col in search_cols:
                if col in filtered_df.columns:
                    mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
            
            filtered_df = filtered_df[mask]
        
        # 카테고리 필터
        category_filter = self._get_session_value("category_filter")
        if category_filter != "전체" and '카테고리' in df.columns:
            filtered_df = filtered_df[filtered_df['카테고리'] == category_filter]
        
        # 상태 필터
        status_filter = self._get_session_value("status_filter")
        if status_filter != "전체" and '상태' in df.columns:
            filtered_df = filtered_df[filtered_df['상태'] == status_filter]
        
        # 매력도 점수 범위 필터
        if '매력도_점수' in df.columns:
            score_range = self._get_session_value("score_range")
            min_score, max_score = score_range
            filtered_df = filtered_df[
                (filtered_df['매력도_점수'] >= min_score) & 
                (filtered_df['매력도_점수'] <= max_score)
            ]
        
        return filtered_df
    
    def _apply_sorting(self, df: pd.DataFrame) -> pd.DataFrame:
        """정렬 적용"""
        sort_column = self._get_session_value("sort_column")
        sort_ascending = self._get_session_value("sort_ascending")
        
        if sort_column in df.columns:
            # 특별한 정렬 처리가 필요한 컬럼들
            if sort_column == "업로드_날짜":
                # 날짜 문자열을 datetime으로 변환하여 정렬
                df_sorted = df.copy()
                df_sorted['_temp_date'] = pd.to_datetime(df_sorted[sort_column], errors='coerce')
                df_sorted = df_sorted.sort_values('_temp_date', ascending=sort_ascending, na_position='last')
                df_sorted = df_sorted.drop('_temp_date', axis=1)
                return df_sorted
            elif sort_column == "예상_가격":
                # 가격 문자열에서 숫자만 추출하여 정렬
                df_sorted = df.copy()
                df_sorted['_temp_price'] = df_sorted[sort_column].str.replace(',', '').str.replace('원', '').astype(int)
                df_sorted = df_sorted.sort_values('_temp_price', ascending=sort_ascending, na_position='last')
                df_sorted = df_sorted.drop('_temp_price', axis=1)
                return df_sorted
            else:
                # 기본 정렬
                return df.sort_values(sort_column, ascending=sort_ascending, na_position='last')
        
        return df
    
    def _render_search_and_filters(self):
        """검색 및 필터 UI 렌더링"""
        st.markdown("### 🔍 필터 및 검색")
        
        # 검색어 입력
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            search_term = st.text_input(
                "검색 (채널명, 제품명, 영상 제목)",
                value=self._get_session_value("search_term"),
                placeholder="검색어를 입력하세요...",
                key=f"{self.session_key_prefix}search_input"
            )
            if search_term != self._get_session_value("search_term"):
                self._set_session_value("search_term", search_term)
                self._set_session_value("current_page", 1)  # 검색 시 첫 페이지로
        
        # 카테고리 필터
        with col2:
            if '카테고리' in self.data.columns:
                categories = ["전체"] + sorted(self.data['카테고리'].unique().tolist())
                category_filter = st.selectbox(
                    "카테고리",
                    categories,
                    index=categories.index(self._get_session_value("category_filter")) 
                          if self._get_session_value("category_filter") in categories else 0,
                    key=f"{self.session_key_prefix}category_input"
                )
                if category_filter != self._get_session_value("category_filter"):
                    self._set_session_value("category_filter", category_filter)
                    self._set_session_value("current_page", 1)
        
        # 상태 필터
        with col3:
            if '상태' in self.data.columns:
                statuses = ["전체"] + sorted(self.data['상태'].unique().tolist())
                status_filter = st.selectbox(
                    "상태",
                    statuses,
                    index=statuses.index(self._get_session_value("status_filter"))
                          if self._get_session_value("status_filter") in statuses else 0,
                    key=f"{self.session_key_prefix}status_input"
                )
                if status_filter != self._get_session_value("status_filter"):
                    self._set_session_value("status_filter", status_filter)
                    self._set_session_value("current_page", 1)
        
        # 매력도 점수 범위
        with col4:
            if '매력도_점수' in self.data.columns:
                score_range = st.slider(
                    "매력도 점수 범위",
                    min_value=int(self.data['매력도_점수'].min()),
                    max_value=int(self.data['매력도_점수'].max()),
                    value=self._get_session_value("score_range"),
                    step=5,
                    key=f"{self.session_key_prefix}score_range_input"
                )
                if score_range != self._get_session_value("score_range"):
                    self._set_session_value("score_range", score_range)
                    self._set_session_value("current_page", 1)
    
    def _render_sorting_controls(self, filtered_df: pd.DataFrame):
        """정렬 컨트롤 UI 렌더링"""
        st.markdown("### 📊 정렬 옵션")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # 정렬 가능한 컬럼 옵션
            sort_options = {}
            if '매력도_점수' in filtered_df.columns:
                sort_options["매력도_점수"] = "🎯 매력도 점수"
            if '업로드_날짜' in filtered_df.columns:
                sort_options["업로드_날짜"] = "📅 업로드 날짜"
            if '감성_강도' in filtered_df.columns:
                sort_options["감성_강도"] = "❤️ 감성 강도"
            if '실사용_인증' in filtered_df.columns:
                sort_options["실사용_인증"] = "✅ 실사용 인증"
            if '인플루언서_신뢰도' in filtered_df.columns:
                sort_options["인플루언서_신뢰도"] = "⭐ 인플루언서 신뢰도"
            if '채널명' in filtered_df.columns:
                sort_options["채널명"] = "📺 채널명"
            if '제품명' in filtered_df.columns:
                sort_options["제품명"] = "🛍️ 제품명"
            if '예상_가격' in filtered_df.columns:
                sort_options["예상_가격"] = "💰 예상 가격"
            
            current_sort = self._get_session_value("sort_column")
            if current_sort not in sort_options:
                current_sort = list(sort_options.keys())[0] if sort_options else None
            
            sort_column = st.selectbox(
                "정렬 기준",
                options=list(sort_options.keys()),
                format_func=lambda x: sort_options[x],
                index=list(sort_options.keys()).index(current_sort) if current_sort in sort_options else 0,
                key=f"{self.session_key_prefix}sort_column_input"
            )
            if sort_column != self._get_session_value("sort_column"):
                self._set_session_value("sort_column", sort_column)
        
        with col2:
            # 정렬 방향
            sort_order = st.selectbox(
                "정렬 순서",
                ["내림차순 ⬇️", "오름차순 ⬆️"],
                index=1 if self._get_session_value("sort_ascending") else 0,
                key=f"{self.session_key_prefix}sort_order_input"
            )
            sort_ascending = (sort_order == "오름차순 ⬆️")
            if sort_ascending != self._get_session_value("sort_ascending"):
                self._set_session_value("sort_ascending", sort_ascending)
        
        with col3:
            # 필터 초기화 버튼
            if st.button("🔄 필터 초기화", key=f"{self.session_key_prefix}reset_filters"):
                self._set_session_value("search_term", "")
                self._set_session_value("category_filter", "전체")
                self._set_session_value("status_filter", "전체")
                self._set_session_value("score_range", (0, 100))
                self._set_session_value("current_page", 1)
                st.rerun()
    
    def _render_pagination_controls(self, total_rows: int) -> Tuple[int, int]:
        """페이지네이션 컨트롤 렌더링"""
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            # 페이지당 항목 수
            items_per_page = st.selectbox(
                "페이지당 항목 수",
                [10, 20, 50, 100],
                index=[10, 20, 50, 100].index(self._get_session_value("items_per_page")),
                key=f"{self.session_key_prefix}items_per_page_input"
            )
            if items_per_page != self._get_session_value("items_per_page"):
                self._set_session_value("items_per_page", items_per_page)
                self._set_session_value("current_page", 1)
        
        # 총 페이지 수 계산
        total_pages = max(1, (total_rows - 1) // items_per_page + 1)
        current_page = min(self._get_session_value("current_page"), total_pages)
        
        with col2:
            if total_pages > 1:
                # 페이지 선택
                page_number = st.number_input(
                    f"페이지 (1-{total_pages})",
                    min_value=1,
                    max_value=total_pages,
                    value=current_page,
                    key=f"{self.session_key_prefix}page_input"
                )
                if page_number != self._get_session_value("current_page"):
                    self._set_session_value("current_page", page_number)
            else:
                st.write("페이지 1/1")
        
        with col3:
            if total_pages > 1:
                # 페이지 네비게이션 버튼
                nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)
                
                with nav_col1:
                    if st.button("⏮️ 처음", disabled=current_page <= 1, key=f"{self.session_key_prefix}first"):
                        self._set_session_value("current_page", 1)
                        st.rerun()
                
                with nav_col2:
                    if st.button("⬅️ 이전", disabled=current_page <= 1, key=f"{self.session_key_prefix}prev"):
                        self._set_session_value("current_page", current_page - 1)
                        st.rerun()
                
                with nav_col3:
                    if st.button("➡️ 다음", disabled=current_page >= total_pages, key=f"{self.session_key_prefix}next"):
                        self._set_session_value("current_page", current_page + 1)
                        st.rerun()
                
                with nav_col4:
                    if st.button("⏭️ 마지막", disabled=current_page >= total_pages, key=f"{self.session_key_prefix}last"):
                        self._set_session_value("current_page", total_pages)
                        st.rerun()
        
        # 시작 및 끝 인덱스 계산
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, total_rows)
        
        return start_idx, end_idx
    
    def _render_statistics(self, original_count: int, filtered_count: int, filtered_df: pd.DataFrame):
        """통계 정보 렌더링"""
        st.markdown("### 📊 현황 요약")
        
        cols = st.columns(5)
        
        with cols[0]:
            st.metric("전체 후보", original_count)
        
        with cols[1]:
            st.metric("필터링 결과", filtered_count)
        
        with cols[2]:
            if '매력도_점수' in filtered_df.columns and len(filtered_df) > 0:
                avg_score = filtered_df['매력도_점수'].mean()
                st.metric("평균 점수", f"{avg_score:.1f}")
            else:
                st.metric("평균 점수", "N/A")
        
        with cols[3]:
            if '상태' in filtered_df.columns:
                approved = len(filtered_df[filtered_df['상태'] == '승인됨'])
                st.metric("승인됨", approved)
            else:
                st.metric("승인됨", "N/A")
        
        with cols[4]:
            if '상태' in filtered_df.columns:
                pending = len(filtered_df[filtered_df['상태'] == '대기중'])
                st.metric("대기중", pending)
            else:
                st.metric("대기중", "N/A")
    
    def render(self) -> Optional[pd.Series]:
        """
        데이터 테이블 렌더링
        
        Returns:
            선택된 행의 데이터 (pd.Series) 또는 None
        """
        # 성능 측정 시작
        start_time = time.time()
        
        # 필터 및 검색 UI
        self._render_search_and_filters()
        
        # 필터 적용
        filtered_df = self._apply_filters(self.data)
        
        # 통계 정보 표시
        self._render_statistics(len(self.data), len(filtered_df), filtered_df)
        
        # 결과가 없는 경우
        if len(filtered_df) == 0:
            st.markdown("### 🔍 검색 결과가 없습니다")
            st.info("""
            현재 설정된 필터 조건에 맞는 후보가 없습니다.
            
            **💡 해결 방법:**
            - 검색어를 다시 확인해주세요
            - 필터 조건을 완화해보세요
            - '필터 초기화' 버튼을 클릭해보세요
            """)
            return None
        
        # 정렬 컨트롤
        self._render_sorting_controls(filtered_df)
        
        # 정렬 적용
        sorted_df = self._apply_sorting(filtered_df)
        
        # 페이지네이션
        start_idx, end_idx = self._render_pagination_controls(len(sorted_df))
        current_page_df = sorted_df.iloc[start_idx:end_idx]
        
        # 테이블 헤더
        st.markdown("### 📋 데이터 목록")
        st.markdown(f"**{start_idx + 1}-{end_idx} / {len(sorted_df)} 항목** "
                   f"(전체 {len(self.data)}개 중 {len(sorted_df)}개 표시)")
        
        # 테이블 표시용 컬럼 선택
        display_columns = []
        column_names = []
        
        # 필수 컬럼들
        if '매력도_점수' in current_page_df.columns:
            display_columns.append('매력도_점수')
            column_names.append('점수')
        
        if '채널명' in current_page_df.columns:
            display_columns.append('채널명')
            column_names.append('채널명')
        
        if '제품명' in current_page_df.columns:
            display_columns.append('제품명')
            column_names.append('제품명')
        
        if '상태' in current_page_df.columns:
            display_columns.append('상태')
            column_names.append('상태')
        
        if '업로드_날짜' in current_page_df.columns:
            display_columns.append('업로드_날짜')
            column_names.append('업로드일')
        
        # 테이블 데이터 준비
        if display_columns:
            table_df = current_page_df[display_columns].copy()
            table_df.columns = column_names
            
            # 선택 가능한 테이블 렌더링
            selected_rows = st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"{self.session_key_prefix}main_table"
            )
            
            # 성능 정보 표시
            end_time = time.time()
            processing_time = end_time - start_time
            
            if processing_time > 2.0:
                st.warning(f"⚠️ 처리 시간: {processing_time:.2f}초 (2초 초과)")
            else:
                st.success(f"✅ 처리 시간: {processing_time:.2f}초")
            
            # 선택된 행 반환
            if selected_rows and len(selected_rows.selection.rows) > 0:
                selected_idx = selected_rows.selection.rows[0]
                return current_page_df.iloc[selected_idx]
        
        return None


def create_sample_data_for_table() -> pd.DataFrame:
    """테이블 테스트용 샘플 데이터 생성"""
    np.random.seed(42)
    
    channels = ["홍지윤 Yoon", "아이유IU", "이사배(RISABAE)", "다영 DAYOUNG", "소이와여니"]
    categories = ["스킨케어", "메이크업", "헤어케어", "패션", "향수"]
    statuses = ["대기중", "검토중", "승인됨", "반려됨"]
    
    data = []
    for i in range(120):  # 100개 이상 데이터로 성능 테스트
        score = min(100, max(20, np.random.normal(75, 15)))
        upload_date = datetime.now() - timedelta(days=np.random.randint(1, 30))
        
        data.append({
            "id": f"PROD_{i+1:03d}",
            "매력도_점수": round(score, 1),
            "채널명": np.random.choice(channels),
            "영상_제목": f"[일상VLOG] {np.random.choice(categories)} 추천 솔직 후기",
            "제품명": f"{np.random.choice(['프리미엄', '에센셜', '럭셔리'])} {np.random.choice(categories)} 제품",
            "카테고리": np.random.choice(categories),
            "예상_가격": f"{np.random.randint(10000, 100000):,}원",
            "감성_강도": round(np.random.uniform(0.6, 0.95), 2),
            "실사용_인증": round(np.random.uniform(0.4, 0.9), 2),
            "인플루언서_신뢰도": round(np.random.uniform(0.7, 1.0), 2),
            "상태": np.random.choice(statuses),
            "업로드_날짜": upload_date.strftime("%Y-%m-%d"),
        })
    
    return pd.DataFrame(data)


# 테스트 함수
def test_advanced_data_table():
    """고급 데이터 테이블 테스트"""
    st.title("🧪 Advanced Data Table Component Test")
    
    # 샘플 데이터 생성
    sample_data = create_sample_data_for_table()
    
    # 데이터 테이블 컴포넌트 생성
    data_table = AdvancedDataTable(sample_data, "test_table")
    
    # 테이블 렌더링
    selected_row = data_table.render()
    
    # 선택된 행 표시
    if selected_row is not None:
        st.markdown("---")
        st.markdown("### 🎯 선택된 항목")
        st.json(selected_row.to_dict())


if __name__ == "__main__":
    test_advanced_data_table()