"""
Gemini 분석 모델 테스트
"""

import pytest
from pydantic import ValidationError

from src.gemini_analyzer.models import (
    SourceInfo, ScoreDetails, CandidateInfo, MonetizationInfo, 
    StatusInfo, ProductAnalysisResult
)


class TestSourceInfo:
    """SourceInfo 모델 테스트"""

    def test_valid_source_info(self):
        """유효한 소스 정보 테스트"""
        data = {
            "celebrity_name": "아이유",
            "channel_name": "IU Official",
            "video_title": "아이유의 일상 VLOG",
            "video_url": "https://youtube.com/watch?v=test",
            "upload_date": "2025-06-22"
        }
        
        source = SourceInfo(**data)
        assert source.celebrity_name == "아이유"
        assert source.upload_date == "2025-06-22"

    def test_invalid_date_format(self):
        """잘못된 날짜 형식 테스트"""
        data = {
            "celebrity_name": "아이유",
            "channel_name": "IU Official", 
            "video_title": "테스트",
            "video_url": "https://youtube.com/test",
            "upload_date": "2025/06/22"  # 잘못된 형식
        }
        
        with pytest.raises(ValidationError):
            SourceInfo(**data)


class TestScoreDetails:
    """ScoreDetails 모델 테스트"""

    def test_valid_score_details(self):
        """유효한 점수 상세 테스트"""
        data = {
            "total": 85,
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        score = ScoreDetails(**data)
        assert score.total == 85
        assert score.sentiment_score == 0.9

    def test_score_calculation_validation(self):
        """점수 계산 검증 테스트"""
        # 올바른 계산
        data = {
            "total": 87,  # (0.5*0.9 + 0.35*0.85 + 0.15*0.9) * 100 = 86.75 ≈ 87
            "sentiment_score": 0.9,
            "endorsement_score": 0.85,
            "influencer_score": 0.9
        }
        
        score = ScoreDetails(**data)
        assert score.total == 87

    def test_invalid_score_range(self):
        """점수 범위 초과 테스트"""
        data = {
            "total": 150,  # 100 초과
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        with pytest.raises(ValidationError):
            ScoreDetails(**data)

    def test_negative_scores(self):
        """음수 점수 테스트"""
        data = {
            "total": 85,
            "sentiment_score": -0.1,  # 음수
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        with pytest.raises(ValidationError):
            ScoreDetails(**data)


class TestCandidateInfo:
    """CandidateInfo 모델 테스트"""

    def test_valid_candidate_info(self):
        """유효한 후보 정보 테스트"""
        score_data = {
            "total": 85,
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        data = {
            "product_name_ai": "하이드라 세럼",
            "clip_start_time": 120,
            "clip_end_time": 180,
            "category_path": ["뷰티", "스킨케어", "세럼"],
            "features": ["고보습", "빠른흡수"],
            "score_details": score_data,
            "hook_sentence": "아이유가 쓰는 세럼",
            "summary_for_caption": "보습 세럼 추천",
            "target_audience": ["20대 여성"],
            "price_point": "중가",
            "endorsement_type": "일상 사용",
            "recommended_titles": ["제목1", "제목2", "제목3"],
            "recommended_hashtags": ["#아이유", "#세럼", "#뷰티", "#스킨케어", "#보습", "#추천", "#연예인", "#데일리"]
        }
        
        candidate = CandidateInfo(**data)
        assert candidate.product_name_ai == "하이드라 세럼"
        assert candidate.clip_start_time == 120
        assert candidate.clip_end_time == 180
        assert len(candidate.recommended_titles) == 3
        assert len(candidate.recommended_hashtags) == 8

    def test_invalid_clip_time(self):
        """잘못된 클립 시간 테스트"""
        score_data = {
            "total": 85,
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        data = {
            "product_name_ai": "테스트 제품",
            "clip_start_time": 180,
            "clip_end_time": 120,  # 시작 시간보다 빠름
            "category_path": ["뷰티"],
            "score_details": score_data,
            "hook_sentence": "테스트",
            "summary_for_caption": "테스트",
            "price_point": "중가",
            "endorsement_type": "테스트",
            "recommended_titles": ["제목1", "제목2", "제목3"],
            "recommended_hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5", "#태그6", "#태그7", "#태그8"]
        }
        
        with pytest.raises(ValidationError):
            CandidateInfo(**data)

    def test_invalid_price_point(self):
        """잘못된 가격대 테스트"""
        score_data = {
            "total": 85,
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        data = {
            "product_name_ai": "테스트 제품",
            "clip_start_time": 120,
            "clip_end_time": 180,
            "category_path": ["뷰티"],
            "score_details": score_data,
            "hook_sentence": "테스트",
            "summary_for_caption": "테스트",
            "price_point": "잘못된가격대",  # 유효하지 않은 가격대
            "endorsement_type": "테스트",
            "recommended_titles": ["제목1", "제목2", "제목3"],
            "recommended_hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5", "#태그6", "#태그7", "#태그8"]
        }
        
        with pytest.raises(ValidationError):
            CandidateInfo(**data)

    def test_insufficient_titles(self):
        """제목 개수 부족 테스트"""
        score_data = {
            "total": 85,
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        data = {
            "product_name_ai": "테스트 제품",
            "clip_start_time": 120,
            "clip_end_time": 180,
            "category_path": ["뷰티"],
            "score_details": score_data,
            "hook_sentence": "테스트",
            "summary_for_caption": "테스트",
            "price_point": "중가",
            "endorsement_type": "테스트",
            "recommended_titles": ["제목1", "제목2"],  # 3개 미만
            "recommended_hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5", "#태그6", "#태그7", "#태그8"]
        }
        
        with pytest.raises(ValidationError):
            CandidateInfo(**data)

    def test_insufficient_hashtags(self):
        """해시태그 개수 부족 테스트"""
        score_data = {
            "total": 85,
            "sentiment_score": 0.9,
            "endorsement_score": 0.8,
            "influencer_score": 0.85
        }
        
        data = {
            "product_name_ai": "테스트 제품",
            "clip_start_time": 120,
            "clip_end_time": 180,
            "category_path": ["뷰티"],
            "score_details": score_data,
            "hook_sentence": "테스트",
            "summary_for_caption": "테스트",
            "price_point": "중가",
            "endorsement_type": "테스트",
            "recommended_titles": ["제목1", "제목2", "제목3"],
            "recommended_hashtags": ["#태그1", "#태그2"]  # 8개 미만
        }
        
        with pytest.raises(ValidationError):
            CandidateInfo(**data)


class TestStatusInfo:
    """StatusInfo 모델 테스트"""

    def test_valid_status_info(self):
        """유효한 상태 정보 테스트"""
        data = {
            "current_status": "needs_review",
            "is_ppl": False,
            "ppl_confidence": 0.2
        }
        
        status = StatusInfo(**data)
        assert status.current_status == "needs_review"
        assert status.is_ppl == False
        assert status.ppl_confidence == 0.2

    def test_invalid_status(self):
        """잘못된 상태 테스트"""
        data = {
            "current_status": "잘못된상태",
            "is_ppl": False,
            "ppl_confidence": 0.2
        }
        
        with pytest.raises(ValidationError):
            StatusInfo(**data)

    def test_invalid_ppl_confidence(self):
        """잘못된 PPL 확률 테스트"""
        data = {
            "current_status": "needs_review",
            "is_ppl": False,
            "ppl_confidence": 1.5  # 1.0 초과
        }
        
        with pytest.raises(ValidationError):
            StatusInfo(**data)


class TestProductAnalysisResult:
    """ProductAnalysisResult 모델 테스트"""

    def test_complete_analysis_result(self):
        """완전한 분석 결과 테스트"""
        data = {
            "source_info": {
                "celebrity_name": "아이유",
                "channel_name": "IU Official",
                "video_title": "아이유의 일상 VLOG",
                "video_url": "https://youtube.com/watch?v=test",
                "upload_date": "2025-06-22"
            },
            "candidate_info": {
                "product_name_ai": "하이드라 세럼",
                "clip_start_time": 120,
                "clip_end_time": 180,
                "category_path": ["뷰티", "스킨케어"],
                "features": ["고보습"],
                "score_details": {
                    "total": 85,
                    "sentiment_score": 0.9,
                    "endorsement_score": 0.8,
                    "influencer_score": 0.85
                },
                "hook_sentence": "아이유가 쓰는 세럼",
                "summary_for_caption": "보습 세럼 추천",
                "price_point": "중가",
                "endorsement_type": "일상 사용",
                "recommended_titles": ["제목1", "제목2", "제목3"],
                "recommended_hashtags": ["#아이유", "#세럼", "#뷰티", "#스킨케어", "#보습", "#추천", "#연예인", "#데일리"]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/test"
            },
            "status_info": {
                "current_status": "needs_review",
                "is_ppl": False,
                "ppl_confidence": 0.2
            }
        }
        
        result = ProductAnalysisResult(**data)
        assert result.source_info.celebrity_name == "아이유"
        assert result.candidate_info.product_name_ai == "하이드라 세럼"
        assert result.monetization_info.is_coupang_product == True
        assert result.status_info.current_status == "needs_review"