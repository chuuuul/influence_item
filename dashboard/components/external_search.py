"""
T03_S02_M02: 외부 검색 연동 기능 - 검색 버튼 UI 컴포넌트
Google/네이버 검색을 위한 사용자 인터페이스 컴포넌트
"""

import streamlit as st
import base64
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
import io
from PIL import Image
import json
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dashboard.utils.search_query_builder import SearchQueryBuilder
    from dashboard.utils.database_manager import get_database_manager
except ImportError as e:
    st.error(f"모듈 import 오류: {e}")
    SearchQueryBuilder = None
    get_database_manager = None


class ExternalSearchComponent:
    """외부 검색 연동 UI 컴포넌트"""
    
    def __init__(self):
        self.query_builder = SearchQueryBuilder() if SearchQueryBuilder else None
        
        # 검색 엔진 정보
        self.search_engines = {
            'google': {
                'name': 'Google',
                'icon': '🔍',
                'color': '#4285F4'
            },
            'naver': {
                'name': '네이버',
                'icon': '🟢',
                'color': '#03C75A'
            }
        }
    
    def render_search_section(
        self, 
        candidate_data: Dict, 
        key_prefix: str = "search"
    ) -> Optional[Dict]:
        """
        외부 검색 섹션 렌더링
        
        Args:
            candidate_data: 후보 데이터
            key_prefix: Streamlit 키 접두사
            
        Returns:
            검색 이벤트 정보 (클릭된 경우)
        """
        if not self.query_builder:
            st.error("❌ 검색 쿼리 빌더를 로드할 수 없습니다.")
            return None
        
        st.markdown("### 🔎 외부 검색 도구")
        st.markdown("제품 정보를 더 자세히 확인하거나 정확한 모델명을 찾아보세요.")
        
        # 후보 정보 추출
        candidate_info = candidate_data.get('candidate_info', {})
        source_info = candidate_data.get('source_info', {})
        
        if not candidate_info.get('product_name_ai'):
            st.warning("⚠️ 제품 정보가 불충분하여 검색 쿼리를 생성할 수 없습니다.")
            return None
        
        # 검색 URL 생성
        try:
            search_urls = self.query_builder.build_search_urls(candidate_info, source_info)
        except Exception as e:
            st.error(f"검색 URL 생성 중 오류: {str(e)}")
            return None
        
        # 탭으로 검색 엔진 분리
        tab1, tab2, tab3 = st.tabs(["🔍 텍스트 검색", "🖼️ 이미지 검색", "📊 검색 설정"])
        
        search_event = None
        
        with tab1:
            search_event = self._render_text_search_buttons(
                search_urls, candidate_info, f"{key_prefix}_text"
            )
        
        with tab2:
            search_event = self._render_image_search_section(
                candidate_data, f"{key_prefix}_image"
            ) or search_event
        
        with tab3:
            self._render_search_settings(candidate_info, f"{key_prefix}_settings")
        
        return search_event
    
    def _render_text_search_buttons(
        self, 
        search_urls: Dict, 
        candidate_info: Dict, 
        key_prefix: str
    ) -> Optional[Dict]:
        """텍스트 검색 버튼들 렌더링"""
        
        # 검색 쿼리 미리보기
        with st.expander("🎯 생성된 검색 쿼리 미리보기", expanded=False):
            queries = self.query_builder.generate_search_queries(candidate_info)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Google 검색 쿼리**")
                for i, query in enumerate(queries.get('google', []), 1):
                    st.markdown(f"{i}. `{query}`")
            
            with col2:
                st.markdown("**네이버 검색 쿼리**")
                for i, query in enumerate(queries.get('naver', []), 1):
                    st.markdown(f"{i}. `{query}`")
        
        # 검색 버튼 그룹
        search_event = None
        
        # Google 검색 버튼들
        st.markdown("#### 🔍 Google 검색")
        google_urls = [url for url in search_urls.get('google', []) if url['type'] == 'text']
        
        if google_urls:
            cols = st.columns(min(3, len(google_urls)))
            for i, url_info in enumerate(google_urls):
                with cols[i % len(cols)]:
                    button_key = f"{key_prefix}_google_{i}"
                    
                    if st.button(
                        f"🔍 {url_info['label']}", 
                        key=button_key,
                        use_container_width=True,
                        help=f"쿼리: {url_info['query']}"
                    ):
                        search_event = {
                            'engine': 'google',
                            'query': url_info['query'],
                            'url': url_info['url'],
                            'type': 'text',
                            'timestamp': datetime.now()
                        }
                        
                        # 새 탭에서 열기 (JavaScript)
                        st.components.v1.html(
                            f'<script>window.open("{url_info["url"]}", "_blank");</script>',
                            height=0
                        )
                        
                        st.success(f"✅ Google에서 '{url_info['query']}' 검색을 시작했습니다!")
        
        # 네이버 검색 버튼들
        st.markdown("#### 🟢 네이버 검색")
        naver_urls = [url for url in search_urls.get('naver', []) if url['type'] == 'text']
        
        if naver_urls:
            cols = st.columns(min(3, len(naver_urls)))
            for i, url_info in enumerate(naver_urls):
                with cols[i % len(cols)]:
                    button_key = f"{key_prefix}_naver_{i}"
                    
                    if st.button(
                        f"🟢 {url_info['label']}", 
                        key=button_key,
                        use_container_width=True,
                        help=f"쿼리: {url_info['query']}"
                    ):
                        search_event = {
                            'engine': 'naver',
                            'query': url_info['query'],
                            'url': url_info['url'],
                            'type': 'text',
                            'timestamp': datetime.now()
                        }
                        
                        # 새 탭에서 열기
                        st.components.v1.html(
                            f'<script>window.open("{url_info["url"]}", "_blank");</script>',
                            height=0
                        )
                        
                        st.success(f"✅ 네이버에서 '{url_info['query']}' 검색을 시작했습니다!")
        
        # 네이버 쇼핑 검색
        shopping_urls = [url for url in search_urls.get('naver', []) if url['type'] == 'shopping']
        if shopping_urls:
            st.markdown("#### 🛍️ 네이버 쇼핑 검색")
            cols = st.columns(min(2, len(shopping_urls)))
            for i, url_info in enumerate(shopping_urls):
                with cols[i % len(cols)]:
                    button_key = f"{key_prefix}_shopping_{i}"
                    
                    if st.button(
                        f"🛍️ {url_info['label']}", 
                        key=button_key,
                        use_container_width=True,
                        help=f"쿼리: {url_info['query']}"
                    ):
                        search_event = {
                            'engine': 'naver',
                            'query': url_info['query'],
                            'url': url_info['url'],
                            'type': 'shopping',
                            'timestamp': datetime.now()
                        }
                        
                        st.components.v1.html(
                            f'<script>window.open("{url_info["url"]}", "_blank");</script>',
                            height=0
                        )
                        
                        st.success(f"✅ 네이버 쇼핑에서 '{url_info['query']}' 검색을 시작했습니다!")
        
        return search_event
    
    def _render_image_search_section(
        self, 
        candidate_data: Dict, 
        key_prefix: str
    ) -> Optional[Dict]:
        """이미지 검색 섹션 렌더링"""
        
        st.markdown("#### 🖼️ 이미지 기반 검색")
        st.info("제품 이미지를 사용하여 더 정확한 검색 결과를 얻을 수 있습니다.")
        
        # 추출된 제품 이미지 확인
        product_images = self._get_product_images(candidate_data)
        search_event = None
        
        if product_images:
            st.markdown("**추출된 제품 이미지 활용**")
            
            # 이미지 선택
            num_images = min(4, len(product_images))
            if num_images > 1:
                cols = st.columns(num_images)
                selected_image = None
                
                for i, image_data in enumerate(product_images[:num_images]):
                    with cols[i]:
                        # 이미지 표시 (썸네일 경로가 있는 경우)
                        thumbnail_path = image_data.get('file_paths', {}).get('thumbnail_150')
                        if thumbnail_path and Path(thumbnail_path).exists():
                            st.image(thumbnail_path, caption=f"이미지 {i+1}")
                        else:
                            st.markdown(f"🖼️ 이미지 {i+1}")
                            st.caption(f"점수: {image_data.get('composite_score', 0):.3f}")
                        
                        if st.button(f"선택", key=f"{key_prefix}_img_select_{i}"):
                            selected_image = image_data
                            st.session_state[f'{key_prefix}_selected_image'] = selected_image
            else:
                selected_image = product_images[0]
                st.session_state[f'{key_prefix}_selected_image'] = selected_image
            
            # 선택된 이미지로 검색
            if f'{key_prefix}_selected_image' in st.session_state:
                selected_image = st.session_state[f'{key_prefix}_selected_image']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔍 Google Lens로 검색", use_container_width=True, key=f"{key_prefix}_google_lens"):
                        search_event = {
                            'engine': 'google',
                            'query': 'image_search',
                            'url': 'https://lens.google.com/',
                            'type': 'image',
                            'image_data': selected_image,
                            'timestamp': datetime.now()
                        }
                        
                        st.components.v1.html(
                            '<script>window.open("https://lens.google.com/", "_blank");</script>',
                            height=0
                        )
                        
                        st.success("✅ Google Lens가 열렸습니다. 이미지를 업로드하여 검색하세요!")
                        st.info("💡 이미지 파일을 Google Lens에 드래그하여 업로드할 수 있습니다.")
                
                with col2:
                    # 제품명 기반 이미지 검색
                    candidate_info = candidate_data.get('candidate_info', {})
                    product_name = candidate_info.get('product_name_ai', '')
                    
                    if product_name and st.button("🖼️ 네이버 이미지 검색", use_container_width=True, key=f"{key_prefix}_naver_image"):
                        if self.query_builder:
                            image_urls = self.query_builder.get_image_search_urls(candidate_info)
                            naver_url = image_urls.get('naver_images')
                            
                            if naver_url:
                                search_event = {
                                    'engine': 'naver',
                                    'query': product_name,
                                    'url': naver_url,
                                    'type': 'image',
                                    'timestamp': datetime.now()
                                }
                                
                                st.components.v1.html(
                                    f'<script>window.open("{naver_url}", "_blank");</script>',
                                    height=0
                                )
                                
                                st.success(f"✅ 네이버에서 '{product_name}' 이미지 검색을 시작했습니다!")
        
        else:
            st.info("📭 추출된 제품 이미지가 없습니다.")
            
            # 수동 이미지 업로드 옵션
            with st.expander("📤 이미지 직접 업로드", expanded=False):
                uploaded_file = st.file_uploader(
                    "제품 이미지를 업로드하세요",
                    type=['jpg', 'jpeg', 'png'],
                    key=f"{key_prefix}_upload"
                )
                
                if uploaded_file:
                    # 이미지 미리보기
                    image = Image.open(uploaded_file)
                    st.image(image, caption="업로드된 이미지", width=200)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🔍 Google Lens 검색", key=f"{key_prefix}_upload_google"):
                            search_event = {
                                'engine': 'google',
                                'query': 'uploaded_image_search',
                                'url': 'https://lens.google.com/',
                                'type': 'image',
                                'uploaded_image': uploaded_file,
                                'timestamp': datetime.now()
                            }
                            
                            st.components.v1.html(
                                '<script>window.open("https://lens.google.com/", "_blank");</script>',
                                height=0
                            )
                            
                            st.success("✅ Google Lens가 열렸습니다!")
                    
                    with col2:
                        candidate_info = candidate_data.get('candidate_info', {})
                        product_name = candidate_info.get('product_name_ai', '제품')
                        
                        if st.button("🖼️ 네이버 이미지 검색", key=f"{key_prefix}_upload_naver"):
                            if self.query_builder:
                                image_urls = self.query_builder.get_image_search_urls(candidate_info)
                                naver_url = image_urls.get('naver_images')
                                
                                if naver_url:
                                    search_event = {
                                        'engine': 'naver',
                                        'query': product_name,
                                        'url': naver_url,
                                        'type': 'image',
                                        'uploaded_image': uploaded_file,
                                        'timestamp': datetime.now()
                                    }
                                    
                                    st.components.v1.html(
                                        f'<script>window.open("{naver_url}", "_blank");</script>',
                                        height=0
                                    )
                                    
                                    st.success(f"✅ 네이버에서 '{product_name}' 이미지 검색을 시작했습니다!")
        
        return search_event
    
    def _render_search_settings(self, candidate_info: Dict, key_prefix: str):
        """검색 설정 섹션 렌더링"""
        
        st.markdown("#### ⚙️ 검색 설정")
        
        # 수동 쿼리 입력
        with st.expander("✏️ 수동 검색 쿼리 입력", expanded=False):
            current_product = candidate_info.get('product_name_ai', '')
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                manual_query = st.text_input(
                    "검색어를 직접 입력하세요",
                    value=current_product,
                    key=f"{key_prefix}_manual_query",
                    help="원하는 검색어를 직접 입력하여 더 정확한 검색을 할 수 있습니다."
                )
            
            with col2:
                search_engine = st.selectbox(
                    "검색 엔진",
                    ["Google", "네이버"],
                    key=f"{key_prefix}_manual_engine"
                )
            
            if manual_query and st.button("🔍 수동 검색 실행", key=f"{key_prefix}_manual_search"):
                if search_engine == "Google":
                    from urllib.parse import quote_plus
                    url = f"https://www.google.com/search?q={quote_plus(manual_query)}&hl=ko&gl=KR"
                else:
                    from urllib.parse import quote_plus
                    url = f"https://search.naver.com/search.naver?query={quote_plus(manual_query)}"
                
                st.components.v1.html(
                    f'<script>window.open("{url}", "_blank");</script>',
                    height=0
                )
                
                st.success(f"✅ {search_engine}에서 '{manual_query}' 검색을 시작했습니다!")
        
        # 검색 결과 피드백
        with st.expander("💬 검색 결과 피드백", expanded=False):
            st.markdown("마지막 검색이 도움이 되었나요?")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("👍 매우 유용함", key=f"{key_prefix}_feedback_good"):
                    self._save_search_feedback('positive', candidate_info, key_prefix)
                    st.success("피드백이 저장되었습니다!")
            
            with col2:
                if st.button("👌 보통", key=f"{key_prefix}_feedback_neutral"):
                    self._save_search_feedback('neutral', candidate_info, key_prefix)
                    st.info("피드백이 저장되었습니다!")
            
            with col3:
                if st.button("👎 도움안됨", key=f"{key_prefix}_feedback_bad"):
                    self._save_search_feedback('negative', candidate_info, key_prefix)
                    st.warning("피드백이 저장되었습니다!")
    
    def _get_product_images(self, candidate_data: Dict) -> List[Dict]:
        """후보 데이터에서 제품 이미지 추출"""
        product_images = []
        
        # 다양한 경로에서 이미지 데이터 시도
        if 'selected_product_images' in candidate_data:
            product_images = candidate_data['selected_product_images']
        elif 'all_product_images' in candidate_data:
            product_images = candidate_data['all_product_images']
        
        # 분석 결과에서 추출 시도
        analysis_results = candidate_data.get('analysis_results', {})
        if not product_images and 'frame_analysis' in analysis_results:
            frame_analysis = analysis_results['frame_analysis']
            if hasattr(frame_analysis, 'selected_product_images'):
                product_images = frame_analysis.selected_product_images
            elif hasattr(frame_analysis, 'all_product_images'):
                product_images = frame_analysis.all_product_images
        
        return product_images if isinstance(product_images, list) else []
    
    def _save_search_feedback(self, feedback_type: str, candidate_info: Dict, key_prefix: str):
        """검색 결과 피드백 저장"""
        try:
            if not get_database_manager:
                return
            
            db_manager = get_database_manager()
            
            feedback_data = {
                'product_name': candidate_info.get('product_name_ai', ''),
                'feedback_type': feedback_type,
                'timestamp': datetime.now().isoformat(),
                'session_key': key_prefix
            }
            
            # 피드백 데이터 저장 (실제 구현에서는 별도 테이블 사용)
            # 여기서는 세션 상태에 임시 저장
            feedback_key = f'search_feedback_{key_prefix}'
            if feedback_key not in st.session_state:
                st.session_state[feedback_key] = []
            
            st.session_state[feedback_key].append(feedback_data)
            
        except Exception as e:
            st.error(f"피드백 저장 중 오류: {str(e)}")
    
    def render_search_history(self, key_prefix: str = "history"):
        """검색 이력 표시"""
        
        st.markdown("### 📊 검색 이력")
        
        # 세션에서 검색 이력 확인
        history_key = f'search_history_{key_prefix}'
        
        if history_key in st.session_state and st.session_state[history_key]:
            history = st.session_state[history_key]
            
            # 최근 검색어들 표시
            st.markdown("**최근 검색어**")
            for i, search in enumerate(reversed(history[-5:])):  # 최근 5개
                engine_icon = self.search_engines.get(search['engine'], {}).get('icon', '🔍')
                st.markdown(f"{i+1}. {engine_icon} {search['query']} ({search['engine']})")
            
            # 전체 이력 보기
            with st.expander("📜 전체 검색 이력", expanded=False):
                for search in reversed(history):
                    timestamp = search.get('timestamp', 'Unknown')
                    if hasattr(timestamp, 'strftime'):
                        timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    
                    st.markdown(f"- **{search['query']}** ({search['engine']}) - {timestamp}")
        
        else:
            st.info("📭 검색 이력이 없습니다.")


def test_external_search_component():
    """외부 검색 컴포넌트 테스트"""
    st.title("🧪 외부 검색 컴포넌트 테스트")
    
    # 테스트 데이터
    test_data = {
        "source_info": {
            "celebrity_name": "아이유",
            "channel_name": "아이유 공식 채널",
            "video_title": "[일상] 아이유의 스킨케어 루틴",
            "video_url": "https://www.youtube.com/watch?v=sample"
        },
        "candidate_info": {
            "product_name_ai": "라네즈 - 수분크림 에센셜",
            "category_path": ["스킨케어", "크림", "수분크림"],
            "features": ["높은 보습력", "빠른 흡수"],
            "score_details": {
                "total": 85.0
            }
        }
    }
    
    # 컴포넌트 렌더링
    search_component = ExternalSearchComponent()
    search_event = search_component.render_search_section(test_data, "test")
    
    # 검색 이벤트 표시
    if search_event:
        st.markdown("---")
        st.markdown("### 🎯 검색 이벤트")
        st.json(search_event)
    
    # 검색 이력 표시
    st.markdown("---")
    search_component.render_search_history("test")


if __name__ == "__main__":
    test_external_search_component()