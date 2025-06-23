"""
제품 이미지 갤러리 컴포넌트

타겟 시간대에서 자동 추출된 제품 이미지들을 갤러리 형태로 표시하고,
이미지 선택/제외, 확대 보기 등의 기능을 제공합니다.
"""

import streamlit as st
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import base64
import io


class ProductImageGallery:
    """제품 이미지 갤러리 클래스"""
    
    def __init__(self):
        """갤러리 초기화"""
        pass
    
    @staticmethod
    def _load_image_as_base64(image_path: str) -> Optional[str]:
        """이미지를 Base64로 인코딩하여 로드"""
        try:
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                return None
                
            with open(image_path_obj, "rb") as f:
                image_bytes = f.read()
            
            # Base64 인코딩
            base64_string = base64.b64encode(image_bytes).decode()
            return f"data:image/jpeg;base64,{base64_string}"
            
        except Exception as e:
            st.error(f"이미지 로드 실패: {e}")
            return None
    
    @staticmethod
    def _create_image_info_card(image_metadata: Dict[str, Any], is_selected: bool = True) -> str:
        """이미지 정보 카드 HTML 생성"""
        
        # 품질 점수 색상 결정
        composite_score = image_metadata.get("composite_score", 0)
        if composite_score >= 0.8:
            score_color = "#28a745"  # 녹색
        elif composite_score >= 0.6:
            score_color = "#ffc107"  # 노란색
        else:
            score_color = "#dc3545"  # 빨간색
        
        # 선택 상태 스타일
        border_color = "#007bff" if is_selected else "#dee2e6"
        opacity = "1.0" if is_selected else "0.7"
        
        return f"""
        <div style="
            border: 2px solid {border_color};
            border-radius: 8px;
            padding: 10px;
            margin: 5px;
            background: white;
            opacity: {opacity};
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: bold; font-size: 14px;">
                    품질 점수: <span style="color: {score_color};">{composite_score:.3f}</span>
                </span>
                <span style="font-size: 12px; color: #6c757d;">
                    {image_metadata.get('timestamp', 0):.1f}초
                </span>
            </div>
            
            <div style="font-size: 12px; color: #6c757d; line-height: 1.4;">
                <div>크기: {image_metadata.get('image_dimensions', {}).get('width', 0)} × {image_metadata.get('image_dimensions', {}).get('height', 0)}</div>
                <div>선명도: {image_metadata.get('quality_scores', {}).get('sharpness', 0):.3f}</div>
                <div>객체 신뢰도: {image_metadata.get('object_confidence', 0):.3f}</div>
                <div>파일 크기: {image_metadata.get('file_sizes', {}).get('original', 0) // 1024} KB</div>
            </div>
        </div>
        """
    
    @staticmethod
    def display_gallery(
        product_images: List[Dict[str, Any]], 
        key_prefix: str = "gallery",
        columns: int = 3,
        show_selection: bool = True,
        show_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        제품 이미지 갤러리 표시
        
        Args:
            product_images: 제품 이미지 메타데이터 리스트
            key_prefix: Streamlit 위젯 키 접두사
            columns: 열 개수
            show_selection: 선택 기능 표시 여부
            show_metadata: 메타데이터 표시 여부
            
        Returns:
            List[Dict[str, Any]]: 선택된 이미지 메타데이터 리스트
        """
        if not product_images:
            st.info("추출된 제품 이미지가 없습니다.")
            return []
        
        st.subheader(f"🖼️ 제품 이미지 갤러리 ({len(product_images)}개)")
        
        # 전체 선택/해제 버튼
        selected_images = []
        if show_selection:
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("전체 선택", key=f"{key_prefix}_select_all"):
                    for i in range(len(product_images)):
                        st.session_state[f"{key_prefix}_img_{i}"] = True
            
            with col2:
                if st.button("전체 해제", key=f"{key_prefix}_deselect_all"):
                    for i in range(len(product_images)):
                        st.session_state[f"{key_prefix}_img_{i}"] = False
        
        # 이미지 그리드 표시
        num_rows = (len(product_images) + columns - 1) // columns
        
        for row in range(num_rows):
            cols = st.columns(columns)
            
            for col_idx in range(columns):
                img_idx = row * columns + col_idx
                if img_idx >= len(product_images):
                    break
                
                image_metadata = product_images[img_idx]
                
                with cols[col_idx]:
                    # 썸네일 이미지 로드
                    thumbnail_path = image_metadata.get("file_paths", {}).get("thumbnail_300", "")
                    
                    if thumbnail_path:
                        base64_image = ProductImageGallery._load_image_as_base64(thumbnail_path)
                        
                        if base64_image:
                            # 이미지 표시
                            st.image(
                                base64_image, 
                                caption=f"이미지 {img_idx + 1}",
                                use_column_width=True
                            )
                            
                            # 선택 체크박스
                            is_selected = True
                            if show_selection:
                                checkbox_key = f"{key_prefix}_img_{img_idx}"
                                # 기본값 설정 (처음 로드 시)
                                if checkbox_key not in st.session_state:
                                    st.session_state[checkbox_key] = True
                                
                                is_selected = st.checkbox(
                                    "선택", 
                                    value=st.session_state[checkbox_key],
                                    key=checkbox_key
                                )
                            
                            # 메타데이터 표시
                            if show_metadata:
                                info_card_html = ProductImageGallery._create_image_info_card(
                                    image_metadata, is_selected
                                )
                                st.markdown(info_card_html, unsafe_allow_html=True)
                            
                            # 확대 보기 버튼
                            if st.button(f"🔍 확대 보기", key=f"{key_prefix}_zoom_{img_idx}"):
                                ProductImageGallery._show_enlarged_image(image_metadata, img_idx + 1)
                            
                            # 선택된 이미지 수집
                            if is_selected:
                                selected_images.append(image_metadata)
                        
                        else:
                            st.error(f"이미지 {img_idx + 1} 로드 실패")
                    else:
                        st.warning(f"이미지 {img_idx + 1} 경로 없음")
        
        # 선택 요약
        if show_selection:
            st.info(f"선택된 이미지: {len(selected_images)}개 / {len(product_images)}개")
        
        return selected_images
    
    @staticmethod
    def _show_enlarged_image(image_metadata: Dict[str, Any], image_number: int):
        """이미지 확대 보기"""
        original_path = image_metadata.get("file_paths", {}).get("original", "")
        
        if not original_path:
            st.error("원본 이미지 경로를 찾을 수 없습니다.")
            return
        
        base64_image = ProductImageGallery._load_image_as_base64(original_path)
        
        if base64_image:
            st.image(
                base64_image,
                caption=f"제품 이미지 {image_number} - 원본",
                use_column_width=True
            )
            
            # 상세 메타데이터 표시
            with st.expander("📊 상세 정보", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**기본 정보**")
                    st.write(f"• 타임스탬프: {image_metadata.get('timestamp', 0):.1f}초")
                    st.write(f"• 종합 품질 점수: {image_metadata.get('composite_score', 0):.3f}")
                    st.write(f"• 객체 탐지 신뢰도: {image_metadata.get('object_confidence', 0):.3f}")
                    
                    dimensions = image_metadata.get('image_dimensions', {})
                    st.write(f"• 해상도: {dimensions.get('width', 0)} × {dimensions.get('height', 0)}")
                
                with col2:
                    st.write("**품질 세부 점수**")
                    quality_scores = image_metadata.get('quality_scores', {})
                    st.write(f"• 선명도: {quality_scores.get('sharpness', 0):.3f}")
                    st.write(f"• 크기: {quality_scores.get('size', 0):.3f}")
                    st.write(f"• 밝기: {quality_scores.get('brightness', 0):.3f}")
                    st.write(f"• 대비: {quality_scores.get('contrast', 0):.3f}")
        else:
            st.error("원본 이미지를 로드할 수 없습니다.")
    
    @staticmethod
    def display_compact_gallery(
        product_images: List[Dict[str, Any]], 
        max_display: int = 5,
        key_prefix: str = "compact_gallery"
    ) -> None:
        """
        컴팩트 이미지 갤러리 표시 (상세 뷰용)
        
        Args:
            product_images: 제품 이미지 메타데이터 리스트
            max_display: 최대 표시 개수
            key_prefix: Streamlit 위젯 키 접두사
        """
        if not product_images:
            st.info("추출된 제품 이미지가 없습니다.")
            return
        
        # 최고 품질 이미지만 표시
        display_images = product_images[:max_display]
        
        st.write(f"**🖼️ 제품 이미지 ({len(display_images)}개)**")
        
        # 가로 스크롤 가능한 이미지 행
        cols = st.columns(len(display_images))
        
        for idx, image_metadata in enumerate(display_images):
            with cols[idx]:
                thumbnail_path = image_metadata.get("file_paths", {}).get("thumbnail_150", "")
                
                if thumbnail_path:
                    base64_image = ProductImageGallery._load_image_as_base64(thumbnail_path)
                    
                    if base64_image:
                        st.image(
                            base64_image,
                            caption=f"품질: {image_metadata.get('composite_score', 0):.2f}",
                            use_column_width=True
                        )
                        
                        # 클릭 시 확대 보기
                        if st.button(f"확대", key=f"{key_prefix}_view_{idx}"):
                            ProductImageGallery._show_enlarged_image(image_metadata, idx + 1)
    
    @staticmethod
    def export_selected_images_info(selected_images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        선택된 이미지 정보 내보내기
        
        Args:
            selected_images: 선택된 이미지 메타데이터 리스트
            
        Returns:
            Dict[str, Any]: 내보내기용 정보
        """
        if not selected_images:
            return {"message": "선택된 이미지가 없습니다."}
        
        export_data = {
            "total_selected": len(selected_images),
            "average_quality": sum(img.get("composite_score", 0) for img in selected_images) / len(selected_images),
            "images": []
        }
        
        for idx, image_metadata in enumerate(selected_images):
            image_info = {
                "index": idx + 1,
                "hash": image_metadata.get("hash", ""),
                "timestamp": image_metadata.get("timestamp", 0),
                "composite_score": image_metadata.get("composite_score", 0),
                "object_confidence": image_metadata.get("object_confidence", 0),
                "dimensions": image_metadata.get("image_dimensions", {}),
                "file_paths": image_metadata.get("file_paths", {})
            }
            export_data["images"].append(image_info)
        
        return export_data


def main():
    """테스트용 메인 함수"""
    st.title("제품 이미지 갤러리 테스트")
    
    # 샘플 데이터 생성
    sample_images = []
    for i in range(8):
        sample_image = {
            "hash": f"sample_hash_{i}",
            "timestamp": 10.5 + i * 5,
            "composite_score": 0.3 + (i * 0.1),
            "object_confidence": 0.2 + (i * 0.08),
            "quality_scores": {
                "sharpness": 0.4 + (i * 0.05),
                "size": 0.5 + (i * 0.04),
                "brightness": 0.6 + (i * 0.03),
                "contrast": 0.7 + (i * 0.02)
            },
            "image_dimensions": {
                "width": 800 + i * 100,
                "height": 600 + i * 75
            },
            "file_paths": {
                "original": f"/path/to/original_{i}.jpg",
                "thumbnail_150": f"/path/to/thumb_150_{i}.jpg",
                "thumbnail_300": f"/path/to/thumb_300_{i}.jpg"
            },
            "file_sizes": {
                "original": 150000 + i * 20000,
                "thumbnail_150": 8000 + i * 1000,
                "thumbnail_300": 25000 + i * 3000
            }
        }
        sample_images.append(sample_image)
    
    # 갤러리 표시
    gallery = ProductImageGallery()
    selected = gallery.display_gallery(sample_images, "test")
    
    if selected:
        st.write("### 선택된 이미지 정보")
        export_info = gallery.export_selected_images_info(selected)
        st.json(export_info)


if __name__ == "__main__":
    main()