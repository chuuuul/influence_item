"""
완전한 Pydantic 데이터 모델

PRD 명세에 정의된 JSON 스키마를 정확히 구현합니다.
"""

from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum
import re


class ValidationError(Exception):
    """스키마 검증 오류"""
    pass


class CandidateStatus(str, Enum):
    """후보 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    ANALYSIS_COMPLETE = "analysis_complete"
    NEEDS_REVIEW = "needs_review"
    HIGH_PPL_RISK = "high_ppl_risk"
    PPL_REVIEW_REQUIRED = "ppl_review_required"
    FILTERED_NO_COUPANG = "filtered_no_coupang"
    LOW_SCORE_FILTERED = "low_score_filtered"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_REVISION = "under_revision"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    ERROR = "error"


class PricePoint(str, Enum):
    """가격대"""
    BUDGET = "저가"
    STANDARD = "일반"
    PREMIUM = "프리미엄"
    LUXURY = "럭셔리"


class EndorsementType(str, Enum):
    """추천 유형"""
    EXPLICIT_RECOMMENDATION = "명시적 추천"
    CASUAL_MENTION = "자연스러운 언급"
    HABITUAL_USE = "습관적 사용"
    COMPARISON_REVIEW = "비교 리뷰"
    TUTORIAL_DEMO = "튜토리얼 시연"


class SourceInfo(BaseModel):
    """소스 정보 (PRD 명세 section 3.3)"""
    celebrity_name: str = Field(..., description="연예인 이름")
    channel_name: str = Field(..., description="채널 이름")
    video_title: str = Field(..., description="영상 제목")
    video_url: str = Field(..., description="영상 URL")
    upload_date: str = Field(..., description="업로드 날짜 (YYYY-MM-DD)")
    
    @validator('video_url')
    def validate_video_url(cls, v):
        """YouTube URL 형식 검증"""
        youtube_pattern = r'^https://www\.youtube\.com/watch\?v=[\w-]+$'
        if not re.match(youtube_pattern, v):
            raise ValueError('Invalid YouTube URL format')
        return v
        
    @validator('upload_date')
    def validate_upload_date(cls, v):
        """날짜 형식 검증"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class ScoreDetails(BaseModel):
    """점수 세부사항 (PRD 매력도 스코어링 공식)"""
    total: int = Field(..., ge=0, le=100, description="총점 (0-100)")
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="감성 강도 (0.0-1.0)")
    endorsement_score: float = Field(..., ge=0.0, le=1.0, description="실사용 인증 강도 (0.0-1.0)")
    influencer_score: float = Field(..., ge=0.0, le=1.0, description="인플루언서 신뢰도 (0.0-1.0)")
    
    @model_validator(mode='after')
    def validate_prd_formula(self):
        """PRD 매력도 스코어링 공식 검증"""
        sentiment = self.sentiment_score
        endorsement = self.endorsement_score
        influencer = self.influencer_score
        total = self.total
        
        # PRD 공식: 총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
        calculated_score = (0.50 * sentiment + 0.35 * endorsement + 0.15 * influencer) * 100
        
        # 허용 오차 ±5점
        if abs(total - calculated_score) > 5:
            raise ValueError(
                f'Total score {total} does not match PRD formula calculation {calculated_score:.1f} '
                f'(sentiment={sentiment}, endorsement={endorsement}, influencer={influencer})'
            )
        
        return self


class CandidateInfo(BaseModel):
    """후보 정보 (PRD 명세 section 3.3)"""
    product_name_ai: str = Field(..., description="AI 추출 제품명")
    product_name_manual: Optional[str] = Field(None, description="수동 수정 제품명")
    clip_start_time: int = Field(..., ge=0, description="클립 시작 시간 (초)")
    clip_end_time: int = Field(..., ge=0, description="클립 종료 시간 (초)")
    category_path: List[str] = Field(..., min_items=1, description="카테고리 경로")
    features: List[str] = Field(default_factory=list, description="제품 특징")
    score_details: ScoreDetails = Field(..., description="점수 세부사항")
    hook_sentence: str = Field(..., description="훅 문장")
    summary_for_caption: str = Field(..., description="캡션용 요약")
    target_audience: List[str] = Field(default_factory=list, description="타겟 오디언스")
    price_point: PricePoint = Field(..., description="가격대")
    endorsement_type: EndorsementType = Field(..., description="추천 유형")
    recommended_titles: List[str] = Field(default_factory=list, max_items=5, description="추천 제목")
    recommended_hashtags: List[str] = Field(default_factory=list, max_items=20, description="추천 해시태그")
    
    @validator('clip_end_time')
    def validate_clip_duration(cls, v, values):
        """클립 지속 시간 검증"""
        start_time = values.get('clip_start_time', 0)
        if v <= start_time:
            raise ValueError('clip_end_time must be greater than clip_start_time')
        if v - start_time > 300:  # 5분 초과 방지
            raise ValueError('Clip duration cannot exceed 300 seconds')
        return v
        
    @validator('recommended_hashtags')
    def validate_hashtags(cls, v):
        """해시태그 형식 검증"""
        for hashtag in v:
            if not hashtag.startswith('#'):
                raise ValueError(f'Hashtag must start with #: {hashtag}')
            if len(hashtag) < 2:
                raise ValueError(f'Hashtag too short: {hashtag}')
        return v


class MonetizationInfo(BaseModel):
    """수익화 정보 (PRD 명세 section 3.3)"""
    is_coupang_product: bool = Field(..., description="쿠팡 파트너스 제품 여부")
    coupang_url_ai: Optional[str] = Field(None, description="AI 생성 쿠팡 링크")
    coupang_url_manual: Optional[str] = Field(None, description="수동 설정 쿠팡 링크")
    
    @validator('coupang_url_ai', 'coupang_url_manual')
    def validate_coupang_url(cls, v):
        """쿠팡 URL 형식 검증"""
        if v is not None:
            if not v.startswith('https://link.coupang.com/'):
                raise ValueError('Coupang URL must start with https://link.coupang.com/')
        return v
        
    @model_validator(mode='after')
    def validate_coupang_consistency(self):
        """쿠팡 URL 일관성 검증"""
        is_product = self.is_coupang_product
        ai_url = self.coupang_url_ai
        manual_url = self.coupang_url_manual
        
        if is_product and not ai_url and not manual_url:
            raise ValueError('At least one coupang URL must be provided when is_coupang_product is True')
            
        if not is_product and (ai_url or manual_url):
            raise ValueError('Coupang URLs should not be provided when is_coupang_product is False')
            
        return self


class StatusInfo(BaseModel):
    """상태 정보 (PRD 명세 section 3.3)"""
    current_status: CandidateStatus = Field(..., description="현재 상태")
    is_ppl: bool = Field(..., description="PPL(유료광고) 여부")
    ppl_confidence: float = Field(..., ge=0.0, le=1.0, description="PPL 확률 (0.0-1.0)")
    last_updated: Optional[str] = Field(None, description="마지막 업데이트 시간")
    
    @validator('last_updated')
    def validate_last_updated(cls, v):
        """업데이트 시간 형식 검증"""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('last_updated must be in ISO format')
        return v
        
    @model_validator(mode='after')
    def validate_ppl_consistency(self):
        """PPL 일관성 검증"""
        is_ppl = self.is_ppl
        confidence = self.ppl_confidence
        
        # PPL이 확실한 경우 confidence가 높아야 함
        if is_ppl and confidence < 0.7:
            raise ValueError('PPL confidence should be >= 0.7 when is_ppl is True')
            
        # PPL이 아닌 경우 confidence가 낮아야 함
        if not is_ppl and confidence > 0.3:
            raise ValueError('PPL confidence should be <= 0.3 when is_ppl is False')
            
        return self


class ProductRecommendationCandidate(BaseModel):
    """제품 추천 후보 전체 스키마 (PRD 명세 section 3.3)"""
    source_info: SourceInfo = Field(..., description="소스 정보")
    candidate_info: CandidateInfo = Field(..., description="후보 정보")
    monetization_info: MonetizationInfo = Field(..., description="수익화 정보")
    status_info: StatusInfo = Field(..., description="상태 정보")
    
    # 메타데이터
    schema_version: str = Field(default="1.0", description="스키마 버전")
    created_at: Optional[str] = Field(None, description="생성 시간")
    updated_at: Optional[str] = Field(None, description="수정 시간")
    
    class Config:
        """Pydantic 설정"""
        validate_assignment = True
        extra = "forbid"  # 추가 필드 금지
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    @validator('created_at', 'updated_at')
    def validate_timestamps(cls, v):
        """타임스탬프 형식 검증"""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('Timestamp must be in ISO format')
        return v
        
    def to_api_response(self) -> Dict[str, Any]:
        """API 응답 형식으로 변환"""
        return {
            "success": True,
            "data": self.dict(),
            "schema_version": self.schema_version,
            "timestamp": datetime.now().isoformat()
        }
        
    def get_final_product_name(self) -> str:
        """최종 제품명 반환 (수동 > AI)"""
        return self.candidate_info.product_name_manual or self.candidate_info.product_name_ai
        
    def get_final_coupang_url(self) -> Optional[str]:
        """최종 쿠팡 URL 반환 (수동 > AI)"""
        if not self.monetization_info.is_coupang_product:
            return None
        return (
            self.monetization_info.coupang_url_manual or 
            self.monetization_info.coupang_url_ai
        )
        
    def calculate_priority_score(self) -> float:
        """우선순위 점수 계산 (워크플로우 모듈과 연동)"""
        score_details = self.candidate_info.score_details
        ppl_safety = 1.0 - self.status_info.ppl_confidence
        
        # PRD 기반 매력도 점수
        attractiveness = (
            0.50 * score_details.sentiment_score +
            0.35 * score_details.endorsement_score +
            0.15 * score_details.influencer_score
        ) * 100
        
        # 우선순위 가중 계산
        priority_score = (
            0.7 * attractiveness +
            0.2 * (ppl_safety * 100) +
            0.1 * 50  # 시급성 기본값
        )
        
        return min(100.0, max(0.0, priority_score))
        
    def is_high_priority(self) -> bool:
        """고우선순위 후보 여부"""
        return self.calculate_priority_score() >= 80
        
    def get_validation_errors(self) -> List[str]:
        """검증 오류 목록 반환"""
        errors = []
        
        try:
            self.dict()  # 전체 검증 실행
        except Exception as e:
            errors.append(str(e))
            
        return errors