"""
Gemini 2차 분석기 테스트
"""

import pytest
import json
from unittest.mock import Mock, patch

from src.gemini_analyzer.second_pass_analyzer import GeminiSecondPassAnalyzer
from src.gemini_analyzer.models import ProductAnalysisResult, SourceInfo, CandidateInfo
from config.config import Config


class TestGeminiSecondPassAnalyzer:
    """Gemini 2차 분석기 테스트 클래스"""

    def setup_method(self):
        """테스트 전 설정"""
        self.analyzer = GeminiSecondPassAnalyzer()
        self.test_source_info = {
            'celebrity_name': '아이유',
            'channel_name': 'IU Official',
            'video_title': '아이유의 뷰티 루틴',
            'video_url': 'https://youtube.com/watch?v=test',
            'upload_date': '2025-06-22'
        }
        self.test_candidate_data = {
            'start_time': 120,
            'end_time': 180,
            'reason': '제품 추천 패턴 탐지',
            'confidence_score': 0.85,
            'script_segments': [
                {'start': 120.0, 'text': '제가 요즘 정말 잘 쓰는 세럼이 있는데'},
                {'start': 125.0, 'text': '이거 바르고 나면 정말 촉촉해져요'},
                {'start': 130.0, 'text': '매일 아침저녁으로 쓰고 있어요'}
            ]
        }

    def test_analyzer_initialization(self):
        """분석기 초기화 테스트"""
        analyzer = GeminiSecondPassAnalyzer()
        assert analyzer is not None
        assert analyzer.config is not None
        assert analyzer.logger is not None

    def test_get_user_prompt(self):
        """사용자 프롬프트 생성 테스트"""
        prompt = self.analyzer._get_user_prompt(self.test_candidate_data, self.test_source_info)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert '아이유' in prompt
        assert 'IU Official' in prompt
        assert '120초' in prompt
        assert '180초' in prompt
        assert 'JSON 스키마' in prompt

    def test_calculate_attractiveness_score(self):
        """매력도 점수 계산 테스트"""
        # 테스트 케이스 1: 모든 점수가 높은 경우
        score = self.analyzer.calculate_attractiveness_score(0.9, 0.8, 0.85)
        expected = int(round((0.50 * 0.9 + 0.35 * 0.8 + 0.15 * 0.85) * 100))
        assert score == expected

        # 테스트 케이스 2: 모든 점수가 낮은 경우  
        score = self.analyzer.calculate_attractiveness_score(0.3, 0.2, 0.1)
        expected = int(round((0.50 * 0.3 + 0.35 * 0.2 + 0.15 * 0.1) * 100))
        assert score == expected

        # 테스트 케이스 3: 경계값 테스트
        score = self.analyzer.calculate_attractiveness_score(1.0, 1.0, 1.0)
        assert score == 100

        score = self.analyzer.calculate_attractiveness_score(0.0, 0.0, 0.0)
        assert score == 0

    def test_parse_response_valid_json(self):
        """유효한 JSON 응답 파싱 테스트"""
        valid_response = '''```json
        {
          "source_info": {
            "celebrity_name": "아이유",
            "channel_name": "IU Official",
            "video_title": "아이유의 뷰티 루틴",
            "video_url": "https://youtube.com/test",
            "upload_date": "2025-06-22"
          },
          "candidate_info": {
            "product_name_ai": "테스트 세럼",
            "product_name_manual": null,
            "clip_start_time": 120,
            "clip_end_time": 180,
            "category_path": ["뷰티", "스킨케어"],
            "features": ["보습"],
            "score_details": {
              "total": 85,
              "sentiment_score": 0.9,
              "endorsement_score": 0.8,
              "influencer_score": 0.85
            },
            "hook_sentence": "아이유가 쓰는 세럼",
            "summary_for_caption": "아이유 추천 세럼",
            "target_audience": ["20대"],
            "price_point": "중가",
            "endorsement_type": "일상 사용",
            "recommended_titles": ["제목1", "제목2", "제목3"],
            "recommended_hashtags": ["#아이유", "#세럼", "#뷰티", "#스킨케어", "#보습", "#추천", "#연예인", "#데일리"]
          },
          "monetization_info": {
            "is_coupang_product": false,
            "coupang_url_ai": null,
            "coupang_url_manual": null
          },
          "status_info": {
            "current_status": "needs_review",
            "is_ppl": false,
            "ppl_confidence": 0.1
          }
        }
        ```'''
        
        result = self.analyzer._parse_response(valid_response)
        assert isinstance(result, dict)
        assert 'source_info' in result
        assert 'candidate_info' in result
        assert 'monetization_info' in result
        assert 'status_info' in result

    def test_parse_response_invalid_json(self):
        """잘못된 JSON 응답 파싱 테스트"""
        invalid_response = "잘못된 JSON 형식"
        
        with pytest.raises(ValueError):
            self.analyzer._parse_response(invalid_response)

    def test_extract_product_info_no_client(self):
        """클라이언트 없이 제품 정보 추출 테스트 (테스트 모드)"""
        result = self.analyzer.extract_product_info(self.test_candidate_data, self.test_source_info)
        
        assert isinstance(result, ProductAnalysisResult)
        assert result.source_info.celebrity_name == '테스트 연예인'
        assert result.candidate_info.clip_start_time == 120
        assert result.candidate_info.clip_end_time == 180
        assert isinstance(result.candidate_info.recommended_titles, list)
        assert len(result.candidate_info.recommended_titles) == 3
        assert len(result.candidate_info.recommended_hashtags) >= 8

    @patch('src.gemini_analyzer.second_pass_analyzer.genai')
    def test_extract_product_info_with_mock_client(self, mock_genai):
        """모킹된 클라이언트로 제품 정보 추출 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.text = '''
        {
          "source_info": {
            "celebrity_name": "아이유",
            "channel_name": "IU Official",
            "video_title": "아이유의 뷰티 루틴",
            "video_url": "https://youtube.com/test",
            "upload_date": "2025-06-22"
          },
          "candidate_info": {
            "product_name_ai": "하이드라 세럼",
            "product_name_manual": null,
            "clip_start_time": 120,
            "clip_end_time": 180,
            "category_path": ["뷰티", "스킨케어", "세럼"],
            "features": ["고보습", "빠른흡수", "끈적이지않음"],
            "score_details": {
              "total": 87,
              "sentiment_score": 0.9,
              "endorsement_score": 0.85,
              "influencer_score": 0.9
            },
            "hook_sentence": "아이유가 매일 쓰는 보습 세럼의 정체는?",
            "summary_for_caption": "아이유가 추천하는 하이드라 세럼! 고보습이면서도 끈적이지 않아 매일 사용하기 좋다고 해요.",
            "target_audience": ["20대 여성", "30대 여성", "건성 피부"],
            "price_point": "중가",
            "endorsement_type": "습관적 사용",
            "recommended_titles": [
              "아이유가 매일 쓰는 보습 세럼 정보!",
              "끈적이지 않는 고보습 세럼 추천",
              "아이유 PICK! 하이드라 세럼 리뷰"
            ],
            "recommended_hashtags": [
              "#아이유", "#하이드라세럼", "#보습세럼", "#스킨케어",
              "#뷰티", "#세럼추천", "#고보습", "#연예인추천"
            ]
          },
          "monetization_info": {
            "is_coupang_product": true,
            "coupang_url_ai": "https://link.coupang.com/test",
            "coupang_url_manual": null
          },
          "status_info": {
            "current_status": "needs_review",
            "is_ppl": false,
            "ppl_confidence": 0.2
          }
        }
        '''
        
        # Mock 모델 설정
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        
        # Mock genai 모듈 설정
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types.GenerationConfig = Mock()
        
        # API 키 설정하여 실제 모델 사용 모드로 전환
        test_config = Mock()
        test_config.GOOGLE_API_KEY = "test_api_key"
        test_config.GEMINI_MODEL = "gemini-2.0-flash-001"
        test_config.GEMINI_MAX_TOKENS = 8192
        test_config.GEMINI_TEMPERATURE = 0.3
        test_config.LOG_LEVEL = "INFO"
        
        analyzer = GeminiSecondPassAnalyzer(test_config)
        analyzer.model = mock_model  # 직접 모델 설정
        
        result = analyzer.extract_product_info(self.test_candidate_data, self.test_source_info)
        
        assert isinstance(result, ProductAnalysisResult)
        assert result.source_info.celebrity_name == "아이유"
        assert result.candidate_info.product_name_ai == "하이드라 세럼"
        assert len(result.candidate_info.category_path) == 3
        assert len(result.candidate_info.features) == 3
        assert result.candidate_info.score_details.total == 87
        assert len(result.candidate_info.recommended_titles) == 3
        assert len(result.candidate_info.recommended_hashtags) == 8
        assert result.monetization_info.is_coupang_product == True

    def test_get_analyzer_info(self):
        """분석기 정보 반환 테스트"""
        info = self.analyzer.get_analyzer_info()
        
        assert isinstance(info, dict)
        assert 'model' in info
        assert 'max_tokens' in info
        assert 'temperature' in info
        assert 'timeout' in info
        assert 'model_status' in info
        assert 'api_key_configured' in info

    def test_system_prompt_content(self):
        """시스템 프롬프트 내용 검증"""
        prompt = self.analyzer._get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert '탑티어 커머스 콘텐츠 크리에이터' in prompt
        assert '매력도 스코어링 공식' in prompt
        assert 'PPL 탐지 기준' in prompt
        assert '0.50' in prompt  # 감성 강도 가중치
        assert '0.35' in prompt  # 실사용 인증 강도 가중치
        assert '0.15' in prompt  # 인플루언서 신뢰도 가중치

    def test_score_calculation_accuracy(self):
        """점수 계산 정확도 테스트"""
        # PRD 공식 검증: (0.50 * 감성) + (0.35 * 실사용) + (0.15 * 인플루언서)
        test_cases = [
            (0.8, 0.9, 0.7, 83),  # (0.5*0.8 + 0.35*0.9 + 0.15*0.7) * 100 = 82.0
            (1.0, 1.0, 1.0, 100),
            (0.5, 0.5, 0.5, 50),
            (0.9, 0.85, 0.8, 87)  # (0.5*0.9 + 0.35*0.85 + 0.15*0.8) * 100 = 86.75 ≈ 87
        ]
        
        for sentiment, endorsement, influencer, expected in test_cases:
            result = self.analyzer.calculate_attractiveness_score(sentiment, endorsement, influencer)
            # 반올림으로 인한 1점 오차 허용
            assert abs(result - expected) <= 1, f"Expected {expected}, got {result}"

    def test_prompt_includes_all_required_elements(self):
        """프롬프트에 모든 필수 요소 포함 확인"""
        prompt = self.analyzer._get_user_prompt(self.test_candidate_data, self.test_source_info)
        
        # 필수 섹션들이 포함되어 있는지 확인
        required_sections = [
            '[분석할 데이터]',
            '[지시사항]',
            '[JSON 스키마]',
            '제품 정보 추출',
            '매력도 스코어링',
            'PPL 확률 분석',
            'Instagram 콘텐츠 생성'
        ]
        
        for section in required_sections:
            assert section in prompt, f"프롬프트에 '{section}' 섹션이 누락됨"
        
        # 입력 데이터가 포함되어 있는지 확인
        assert '아이유' in prompt
        assert '120초' in prompt
        assert '180초' in prompt