"""
채널 탐색 시스템 데이터 모델

채널 후보, 탐색 설정, 매칭 결과 등의 데이터 구조 정의
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from enum import Enum


class ChannelType(Enum):
    """채널 유형"""
    CELEBRITY_PERSONAL = "celebrity_personal"  # 연예인 개인 채널
    MEDIA_CHANNEL = "media_channel"           # 미디어 채널 (Vogue, 피식대학 등)
    BEAUTY_INFLUENCER = "beauty_influencer"   # 뷰티 인플루언서
    FASHION_INFLUENCER = "fashion_influencer" # 패션 인플루언서
    LIFESTYLE_INFLUENCER = "lifestyle_influencer" # 라이프스타일 인플루언서
    OTHER = "other"                          # 기타


class ChannelStatus(Enum):
    """채널 후보 상태"""
    DISCOVERED = "discovered"      # 새로 발견됨
    UNDER_REVIEW = "under_review"  # 검토 중
    APPROVED = "approved"          # 승인됨
    REJECTED = "rejected"          # 거부됨
    NEEDS_INFO = "needs_info"      # 추가 정보 필요


@dataclass
class ChannelCandidate:
    """채널 후보 정보"""
    channel_id: str
    channel_name: str
    channel_handle: Optional[str] = None
    channel_url: str = ""
    description: str = ""
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0
    published_at: Optional[datetime] = None
    thumbnail_url: str = ""
    country: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    verified: bool = False
    
    # 탐색 관련 정보
    discovered_at: datetime = field(default_factory=datetime.now)
    discovery_method: str = ""  # search, related, recommendation 등
    discovery_query: str = ""   # 탐색에 사용된 쿼리
    
    # 매칭 점수
    matching_scores: Dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    
    # 분류 및 상태
    channel_type: ChannelType = ChannelType.OTHER
    status: ChannelStatus = ChannelStatus.DISCOVERED
    
    # 검토 정보
    review_notes: str = ""
    reviewed_by: str = ""
    reviewed_at: Optional[datetime] = None
    
    # 추가 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveryConfig:
    """채널 탐색 설정"""
    # 기간 설정
    start_date: date
    end_date: date
    
    # 탐색 대상
    target_keywords: List[str] = field(default_factory=list)
    target_categories: List[str] = field(default_factory=list)
    target_channel_types: List[ChannelType] = field(default_factory=list)
    
    # 필터링 조건
    min_subscriber_count: int = 1000
    max_subscriber_count: int = 10000000
    min_video_count: int = 5
    min_avg_view_count: int = 100
    
    # 언어 및 지역
    target_language: str = "ko"
    target_country: str = "KR"
    
    # 탐색 범위
    max_results_per_query: int = 50
    max_total_candidates: int = 500
    
    # 점수 임계값
    min_matching_score: float = 0.3
    
    # 탐색 방법
    search_methods: List[str] = field(default_factory=lambda: ["keyword_search", "related_channels", "trending"])
    
    # 제외 조건
    exclude_channels: List[str] = field(default_factory=list)  # 채널 ID 목록
    exclude_keywords: List[str] = field(default_factory=list)
    
    # Google Sheets 설정
    sheets_url: str = ""
    worksheet_name: str = "채널 후보"


@dataclass
class MatchingResult:
    """매칭 결과 정보"""
    channel_id: str
    query: str
    method: str
    
    # 개별 매칭 점수
    name_similarity: float = 0.0
    description_relevance: float = 0.0
    keyword_match: float = 0.0
    category_match: float = 0.0
    handle_match: float = 0.0
    content_quality: float = 0.0
    audience_fit: float = 0.0
    
    # 종합 점수
    total_score: float = 0.0
    confidence: float = 0.0
    
    # 매칭 세부사항
    matched_keywords: List[str] = field(default_factory=list)
    matched_phrases: List[str] = field(default_factory=list)
    similarity_details: Dict[str, Any] = field(default_factory=dict)
    
    # 메타데이터
    processed_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: int = 0


@dataclass
class DiscoverySession:
    """탐색 세션 정보"""
    session_id: str
    config: DiscoveryConfig
    started_at: datetime
    ended_at: Optional[datetime] = None
    
    # 진행 상태
    status: str = "running"  # running, completed, failed, cancelled
    current_step: str = ""
    progress_percentage: float = 0.0
    
    # 결과 통계
    total_candidates_found: int = 0
    candidates_after_filtering: int = 0
    high_score_candidates: int = 0
    approved_candidates: int = 0
    
    # 처리 통계
    queries_processed: int = 0
    api_calls_made: int = 0
    processing_errors: int = 0
    
    # 오류 정보
    error_messages: List[str] = field(default_factory=list)
    
    # 결과 파일 경로
    results_file_path: str = ""
    sheets_url: str = ""


@dataclass
class ChannelMetrics:
    """채널 성과 지표"""
    channel_id: str
    
    # 기본 지표
    subscriber_growth_rate: float = 0.0  # 월 구독자 증가율
    avg_view_count: float = 0.0
    engagement_rate: float = 0.0  # (좋아요 + 댓글) / 조회수
    upload_frequency: float = 0.0  # 주당 업로드 수
    
    # 콘텐츠 품질 지표
    video_retention_rate: float = 0.0
    comment_sentiment: float = 0.0  # -1 ~ 1
    content_consistency: float = 0.0
    
    # 수익화 가능성
    product_mention_frequency: float = 0.0
    brand_collaboration_count: int = 0
    monetization_potential: float = 0.0
    
    # 계산 시점
    calculated_at: datetime = field(default_factory=datetime.now)
    data_period_days: int = 30


@dataclass
class ScoringWeights:
    """점수 계산 가중치"""
    # 매칭 점수 가중치
    name_similarity_weight: float = 0.15
    description_relevance_weight: float = 0.20
    keyword_match_weight: float = 0.25
    category_match_weight: float = 0.15
    handle_match_weight: float = 0.10
    content_quality_weight: float = 0.10
    audience_fit_weight: float = 0.05
    
    # 채널 품질 가중치
    subscriber_count_weight: float = 0.30
    engagement_rate_weight: float = 0.25
    content_consistency_weight: float = 0.20
    growth_rate_weight: float = 0.15
    monetization_potential_weight: float = 0.10
    
    def normalize(self):
        """가중치 정규화 (합이 1이 되도록)"""
        matching_total = (self.name_similarity_weight + self.description_relevance_weight + 
                         self.keyword_match_weight + self.category_match_weight +
                         self.handle_match_weight + self.content_quality_weight + 
                         self.audience_fit_weight)
        
        if matching_total > 0:
            self.name_similarity_weight /= matching_total
            self.description_relevance_weight /= matching_total
            self.keyword_match_weight /= matching_total
            self.category_match_weight /= matching_total
            self.handle_match_weight /= matching_total
            self.content_quality_weight /= matching_total
            self.audience_fit_weight /= matching_total
        
        quality_total = (self.subscriber_count_weight + self.engagement_rate_weight +
                        self.content_consistency_weight + self.growth_rate_weight +
                        self.monetization_potential_weight)
        
        if quality_total > 0:
            self.subscriber_count_weight /= quality_total
            self.engagement_rate_weight /= quality_total
            self.content_consistency_weight /= quality_total
            self.growth_rate_weight /= quality_total
            self.monetization_potential_weight /= quality_total


# 기본 설정 상수
DEFAULT_CELEBRITY_KEYWORDS = [
    "연예인", "배우", "가수", "아이돌", "셀럽", "스타",
    "뷰티", "패션", "메이크업", "스타일", "코디",
    "일상", "브이로그", "vlog", "루틴", "추천"
]

DEFAULT_MEDIA_CHANNELS = [
    "보그코리아", "Vogue Korea", "피식대학", "ELLE", "마리끌레르",
    "더블유", "하퍼스바자", "코스모폴리탄", "얼루어"
]

DEFAULT_SCORING_WEIGHTS = ScoringWeights()