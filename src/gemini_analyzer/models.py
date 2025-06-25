"""
Gemini 분석 데이터 모델

PRD JSON 스키마를 기반으로 한 Pydantic 데이터 모델들입니다.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime
import numpy as np


class SourceInfo(BaseModel):
    """영상 소스 정보"""
    celebrity_name: str = Field(..., description="연예인 이름")
    channel_name: str = Field(..., description="채널명")
    video_title: str = Field(..., description="영상 제목")
    video_url: str = Field(..., description="영상 URL")
    upload_date: str = Field(..., description="업로드 날짜 (YYYY-MM-DD)")

    @validator('upload_date')
    def validate_upload_date(cls, v):
        """날짜 형식 검증"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('날짜 형식은 YYYY-MM-DD 이어야 합니다')


class ScoreDetails(BaseModel):
    """매력도 점수 상세"""
    total: int = Field(..., ge=0, le=100, description="총점 (0-100)")
    sentiment_score: float = Field(..., ge=0, le=1, description="감성 강도 점수 (0-1)")
    endorsement_score: float = Field(..., ge=0, le=1, description="실사용 인증 강도 점수 (0-1)")
    influencer_score: float = Field(..., ge=0, le=1, description="인플루언서 신뢰도 점수 (0-1)")

    @validator('total')
    def validate_total_score(cls, v, values):
        """총점이 세부 점수와 일치하는지 검증"""
        if all(key in values for key in ['sentiment_score', 'endorsement_score', 'influencer_score']):
            calculated_total = int(
                (0.50 * values['sentiment_score'] + 
                 0.35 * values['endorsement_score'] + 
                 0.15 * values['influencer_score']) * 100
            )
            if abs(v - calculated_total) > 1:  # 1점 오차 허용
                raise ValueError(f'총점 {v}가 계산된 점수 {calculated_total}와 일치하지 않습니다')
        return v


class CandidateInfo(BaseModel):
    """후보 구간 정보"""
    product_name_ai: str = Field(..., description="AI가 추출한 제품명")
    product_name_manual: Optional[str] = Field(None, description="수동으로 수정된 제품명")
    clip_start_time: int = Field(..., ge=0, description="클립 시작 시간 (초)")
    clip_end_time: int = Field(..., gt=0, description="클립 종료 시간 (초)")
    category_path: List[str] = Field(..., min_items=1, max_items=3, description="카테고리 경로")
    features: List[str] = Field(default_factory=list, description="제품 특징 목록")
    score_details: ScoreDetails = Field(..., description="매력도 점수 상세")
    hook_sentence: str = Field(..., description="관심 유발 문장")
    summary_for_caption: str = Field(..., description="캡션용 요약")
    target_audience: List[str] = Field(default_factory=list, description="타겟 오디언스")
    price_point: str = Field(..., description="가격대 (저가, 중가, 프리미엄 등)")
    endorsement_type: str = Field(..., description="추천 유형")
    recommended_titles: List[str] = Field(..., min_items=3, max_items=3, description="추천 제목 3개")
    recommended_hashtags: List[str] = Field(..., min_items=8, description="추천 해시태그 8개 이상")

    @validator('clip_end_time')
    def validate_clip_time(cls, v, values):
        """클립 종료 시간이 시작 시간보다 늦은지 검증"""
        if 'clip_start_time' in values and v <= values['clip_start_time']:
            raise ValueError('클립 종료 시간은 시작 시간보다 늦어야 합니다')
        return v

    @validator('category_path')
    def validate_category_path(cls, v):
        """카테고리 경로 검증"""
        if not all(isinstance(cat, str) and cat.strip() for cat in v):
            raise ValueError('카테고리는 모두 비어있지 않은 문자열이어야 합니다')
        return v

    @validator('price_point')
    def validate_price_point(cls, v):
        """가격대 검증"""
        valid_price_points = ['저가', '중가', '프리미엄', '럭셔리']
        if v not in valid_price_points:
            raise ValueError(f'가격대는 {valid_price_points} 중 하나여야 합니다')
        return v


class MonetizationInfo(BaseModel):
    """수익화 정보"""
    is_coupang_product: bool = Field(..., description="쿠팡 상품 여부")
    coupang_url_ai: Optional[str] = Field(None, description="AI가 찾은 쿠팡 URL")
    coupang_url_manual: Optional[str] = Field(None, description="수동으로 설정한 쿠팡 URL")
    # 추가된 필드들
    search_keywords_used: List[str] = Field(default_factory=list, description="사용된 검색 키워드들")
    product_match_confidence: Optional[float] = Field(None, ge=0, le=1, description="제품 매칭 신뢰도")
    commission_rate: Optional[float] = Field(None, ge=0, description="커미션율 (%)")
    coupang_price: Optional[int] = Field(None, ge=0, description="쿠팡 판매가격")
    verification_timestamp: Optional[str] = Field(None, description="수익화 검증 시각")


class StatusInfo(BaseModel):
    """상태 정보"""
    current_status: str = Field(..., description="현재 상태")
    is_ppl: bool = Field(..., description="PPL 여부")
    ppl_confidence: float = Field(..., ge=0, le=1, description="PPL 확률 (0-1)")

    @validator('current_status')
    def validate_status(cls, v):
        """상태 검증"""
        valid_statuses = ['needs_review', 'approved', 'rejected', 'filtered_no_coupang', 'published']
        if v not in valid_statuses:
            raise ValueError(f'상태는 {valid_statuses} 중 하나여야 합니다')
        return v


# Audio-Visual Fusion 관련 모델들

class OCRResult(BaseModel):
    """OCR 텍스트 인식 결과"""
    text: str = Field(..., description="인식된 텍스트")
    confidence: float = Field(..., ge=0, le=1, description="인식 신뢰도")
    bbox: List[List[int]] = Field(..., description="바운딩 박스 좌표")
    language: str = Field(..., description="인식된 언어")
    area: int = Field(..., ge=0, description="바운딩 박스 면적")


class ObjectDetectionResult(BaseModel):
    """객체 탐지 결과"""
    class_name: str = Field(..., description="탐지된 객체 클래스")
    confidence: float = Field(..., ge=0, le=1, description="탐지 신뢰도")
    bbox: List[int] = Field(..., description="바운딩 박스 [x1, y1, x2, y2]")
    area: int = Field(..., ge=0, description="바운딩 박스 면적")


class VisualAnalysisResult(BaseModel):
    """시각 분석 결과"""
    frame_timestamp: float = Field(..., description="프레임 타임스탬프 (초)")
    ocr_results: List[OCRResult] = Field(default_factory=list, description="OCR 결과 리스트")
    object_detection_results: List[ObjectDetectionResult] = Field(default_factory=list, description="객체 탐지 결과")
    frame_path: Optional[str] = Field(None, description="프레임 이미지 경로")


class WhisperSegment(BaseModel):
    """Whisper 음성 인식 세그먼트"""
    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")
    text: str = Field(..., description="인식된 텍스트")
    confidence: Optional[float] = Field(None, description="인식 신뢰도")


class AudioAnalysisResult(BaseModel):
    """음성 분석 결과"""
    timeframe_start: float = Field(..., description="분석 구간 시작 시간")
    timeframe_end: float = Field(..., description="분석 구간 종료 시간")
    segments: List[WhisperSegment] = Field(..., description="해당 구간 음성 세그먼트")
    full_text: str = Field(..., description="전체 텍스트")


class FusionConfidence(BaseModel):
    """융합 신뢰도 점수"""
    text_matching_score: float = Field(..., ge=0, le=1, description="텍스트 매칭 점수")
    temporal_alignment_score: float = Field(..., ge=0, le=1, description="시간 정렬 점수")
    semantic_coherence_score: float = Field(..., ge=0, le=1, description="의미적 일관성 점수")
    overall_confidence: float = Field(..., ge=0, le=1, description="전체 융합 신뢰도")

    @validator('overall_confidence')
    def validate_overall_confidence(cls, v, values):
        """전체 신뢰도가 개별 점수와 일치하는지 검증"""
        if all(key in values for key in ['text_matching_score', 'temporal_alignment_score', 'semantic_coherence_score']):
            calculated = (
                values['text_matching_score'] * 0.4 +
                values['temporal_alignment_score'] * 0.3 +
                values['semantic_coherence_score'] * 0.3
            )
            if abs(v - calculated) > 0.05:  # 5% 오차 허용
                raise ValueError(f'전체 신뢰도 {v}가 계산된 값 {calculated:.3f}와 일치하지 않습니다')
        return v


class FusedAnalysisResult(BaseModel):
    """음성+시각 융합 분석 결과"""
    timeframe_start: float = Field(..., description="분석 구간 시작 시간")
    timeframe_end: float = Field(..., description="분석 구간 종료 시간")
    audio_analysis: AudioAnalysisResult = Field(..., description="음성 분석 결과")
    visual_analysis: List[VisualAnalysisResult] = Field(default_factory=list, description="시각 분석 결과 리스트")
    fusion_confidence: FusionConfidence = Field(..., description="융합 신뢰도")
    product_mentions: List[str] = Field(default_factory=list, description="발견된 제품 언급")
    visual_confirmations: List[str] = Field(default_factory=list, description="시각적으로 확인된 제품명")
    consistency_check: bool = Field(..., description="음성-시각 일치성 여부")
    fusion_summary: str = Field(..., description="융합 분석 요약")


class ProductAnalysisResult(BaseModel):
    """완전한 제품 분석 결과"""
    source_info: SourceInfo = Field(..., description="영상 소스 정보")
    candidate_info: CandidateInfo = Field(..., description="후보 구간 정보")
    monetization_info: MonetizationInfo = Field(..., description="수익화 정보")
    status_info: StatusInfo = Field(..., description="상태 정보")

    class Config:
        """Pydantic 설정"""
        json_schema_extra = {
            "example": {
                "source_info": {
                    "celebrity_name": "강민경",
                    "channel_name": "걍밍경",
                    "video_title": "파리 출장 다녀왔습니다 VLOG",
                    "video_url": "https://www.youtube.com/watch?v=example",
                    "upload_date": "2025-06-22"
                },
                "candidate_info": {
                    "product_name_ai": "아비에무아 숄더백 (베이지)",
                    "product_name_manual": None,
                    "clip_start_time": 315,
                    "clip_end_time": 340,
                    "category_path": ["패션잡화", "여성가방", "숄더백"],
                    "features": ["수납이 넉넉해요", "가죽이 부드러워요"],
                    "score_details": {
                        "total": 88,
                        "sentiment_score": 0.9,
                        "endorsement_score": 0.85,
                        "influencer_score": 0.9
                    },
                    "hook_sentence": "강민경이 '이것만 쓴다'고 말한 바로 그 숄더백?",
                    "summary_for_caption": "사복 장인 강민경 님의 데일리백 정보!",
                    "target_audience": ["20대 후반 여성", "30대 직장인", "미니멀룩 선호자"],
                    "price_point": "프리미엄",
                    "endorsement_type": "습관적 사용",
                    "recommended_titles": [
                        "요즘 강민경이 매일 드는 '그 가방' 정보 (바로가기)",
                        "사복 장인 강민경의 찐 애정템! 아비에무아 숄더백",
                        "여름 데일리백 고민 끝! 강민경 PICK 가방 추천"
                    ],
                    "recommended_hashtags": [
                        "#강민경", "#걍밍경", "#강민경패션", "#아비에무아",
                        "#숄더백추천", "#여름가방", "#데일리백", "#연예인패션"
                    ]
                },
                "monetization_info": {
                    "is_coupang_product": True,
                    "coupang_url_ai": "https://link.coupang.com/example",
                    "coupang_url_manual": None
                },
                "status_info": {
                    "current_status": "needs_review",
                    "is_ppl": False,
                    "ppl_confidence": 0.1
                }
            }
        }


# =============================================================================
# 타겟 프레임 분석 모델들 (T05_S02)
# =============================================================================

class TargetTimeframe(BaseModel):
    """1차 분석에서 탐지된 타겟 시간대"""
    start_time: float = Field(..., description="후보 구간 시작 시간(초)")
    end_time: float = Field(..., description="후보 구간 종료 시간(초)")
    reason: str = Field(..., description="후보로 선정된 이유")
    confidence_score: float = Field(..., ge=0, le=1, description="신뢰도 점수")

    @validator('end_time')
    def validate_time_order(cls, v, values):
        """종료 시간이 시작 시간보다 늦은지 검증"""
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('종료 시간이 시작 시간보다 늦어야 합니다')
        return v


class ExtractedFrame(BaseModel):
    """추출된 프레임 정보"""
    timestamp: float = Field(..., description="프레임 타임스탬프(초)")
    frame_index: int = Field(..., description="프레임 인덱스")
    frame_path: Optional[str] = Field(None, description="프레임 이미지 파일 경로")
    frame_data: Optional[Any] = Field(None, description="프레임 이미지 데이터 (numpy array)")
    quality_score: float = Field(..., ge=0, le=1, description="프레임 품질 점수")
    width: int = Field(..., description="프레임 너비")
    height: int = Field(..., description="프레임 높이")
    is_keyframe: bool = Field(default=False, description="키프레임 여부")

    class Config:
        arbitrary_types_allowed = True  # numpy array 허용


class FrameAnalysisResult(BaseModel):
    """개별 프레임 분석 결과"""
    frame: ExtractedFrame = Field(..., description="분석된 프레임 정보")
    ocr_results: List[Dict[str, Any]] = Field(default_factory=list, description="OCR 텍스트 인식 결과")
    object_detection_results: List[Dict[str, Any]] = Field(default_factory=list, description="객체 인식 결과")
    detected_texts: List[str] = Field(default_factory=list, description="인식된 텍스트들")
    detected_objects: List[str] = Field(default_factory=list, description="인식된 객체들")
    analysis_timestamp: float = Field(..., description="분석 수행 시간")
    processing_time_ms: float = Field(..., description="처리 소요 시간(밀리초)")


class TargetFrameAnalysisResult(BaseModel):
    """타겟 시간대 전체 분석 결과"""
    target_timeframe: TargetTimeframe = Field(..., description="분석 대상 시간대")
    video_file_path: str = Field(..., description="분석된 영상 파일 경로")
    total_frames_extracted: int = Field(..., description="추출된 총 프레임 수")
    successful_analyses: int = Field(..., description="성공적으로 분석된 프레임 수")
    frame_results: List[FrameAnalysisResult] = Field(..., description="개별 프레임 분석 결과들")
    summary_texts: List[str] = Field(default_factory=list, description="전체 구간에서 발견된 텍스트 요약")
    summary_objects: List[str] = Field(default_factory=list, description="전체 구간에서 발견된 객체 요약")
    processing_stats: Dict[str, Any] = Field(default_factory=dict, description="처리 통계 정보")
    
    # 메타데이터
    analysis_start_time: float = Field(..., description="분석 시작 시간")
    analysis_end_time: float = Field(..., description="분석 완료 시간")
    total_processing_time: float = Field(..., description="총 처리 시간(초)")
    
    @validator('successful_analyses')
    def validate_success_count(cls, v, values):
        """성공 분석 수가 총 프레임 수를 초과하지 않는지 검증"""
        if 'total_frames_extracted' in values and v > values['total_frames_extracted']:
            raise ValueError('성공 분석 수가 총 프레임 수를 초과할 수 없습니다')
        return v


class VideoMetadata(BaseModel):
    """영상 메타데이터"""
    file_path: str = Field(..., description="영상 파일 경로")
    duration_seconds: float = Field(..., description="영상 총 길이(초)")
    fps: float = Field(..., description="초당 프레임 수")
    total_frames: int = Field(..., description="총 프레임 수")
    width: int = Field(..., description="영상 너비")
    height: int = Field(..., description="영상 높이")
    codec: Optional[str] = Field(None, description="코덱 정보")
    bitrate: Optional[int] = Field(None, description="비트레이트")
    
    @validator('total_frames')
    def validate_frame_count(cls, v, values):
        """총 프레임 수가 duration과 fps에 맞는지 검증"""
        if all(key in values for key in ['duration_seconds', 'fps']):
            expected_frames = int(values['duration_seconds'] * values['fps'])
            if abs(v - expected_frames) > values['fps']:  # 1초 오차 허용
                raise ValueError(f'총 프레임 수 {v}가 예상값 {expected_frames}와 차이가 큽니다')
        return v


class FrameExtractionConfig(BaseModel):
    """프레임 추출 설정"""
    sampling_interval: float = Field(default=1.0, description="프레임 샘플링 간격(초)")
    max_frames_per_timeframe: int = Field(default=30, description="시간대당 최대 프레임 수")
    min_quality_threshold: float = Field(default=0.5, description="최소 품질 임계값")
    prefer_keyframes: bool = Field(default=True, description="키프레임 우선 추출 여부")
    quality_assessment_method: str = Field(default="laplacian", description="품질 평가 방법")
    
    @validator('sampling_interval')
    def validate_sampling_interval(cls, v):
        """샘플링 간격이 유효한지 검증"""
        if v <= 0:
            raise ValueError('샘플링 간격은 0보다 커야 합니다')
        if v > 10:
            raise ValueError('샘플링 간격이 너무 큽니다 (최대 10초)')
        return v