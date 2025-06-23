"""
Gemini 1차 분석기 테스트
"""

import pytest
import json
from unittest.mock import Mock, patch
from src.gemini_analyzer.first_pass_analyzer import GeminiFirstPassAnalyzer
from config.config import Config


class TestGeminiFirstPassAnalyzer:
    """GeminiFirstPassAnalyzer 테스트 클래스"""
    
    @pytest.fixture
    def analyzer(self):
        """테스트용 분석기 인스턴스"""
        config = Config()
        config.GOOGLE_API_KEY = "test_api_key"
        return GeminiFirstPassAnalyzer(config)
    
    @pytest.fixture
    def sample_script(self):
        """테스트용 샘플 스크립트"""
        return [
            {"start": 10.0, "end": 15.0, "text": "안녕하세요 여러분!"},
            {"start": 15.0, "end": 25.0, "text": "제가 요즘 진짜 잘 쓰는 게 있는데요"},
            {"start": 25.0, "end": 35.0, "text": "이 제품 정말 좋아서 소개해드리고 싶어요"},
            {"start": 35.0, "end": 45.0, "text": "발라보면 제형이 진짜 꾸덕해요"},
            {"start": 45.0, "end": 55.0, "text": "오늘도 시청해주셔서 감사합니다"}
        ]
    
    def test_analyzer_initialization(self, analyzer):
        """분석기 초기화 테스트"""
        assert analyzer.config is not None
        assert analyzer.logger is not None
        assert analyzer.system_prompt is not None
        assert "베테랑 유튜브 콘텐츠 큐레이터" in analyzer.system_prompt
    
    def test_get_user_prompt(self, analyzer, sample_script):
        """사용자 프롬프트 생성 테스트"""
        prompt = analyzer._get_user_prompt(sample_script)
        
        assert "[전체 스크립트]" in prompt
        assert "[지시사항]" in prompt
        assert "[출력 형식]" in prompt
        assert "start_time" in prompt
        assert "confidence_score" in prompt
        
        # 스크립트 데이터가 포함되어 있는지 확인
        assert "제가 요즘 진짜 잘 쓰는 게" in prompt
    
    def test_validate_candidate_valid(self, analyzer):
        """유효한 후보 데이터 검증 테스트"""
        valid_candidate = {
            "start_time": 10.5,
            "end_time": 25.8,
            "reason": "지칭 패턴 탐지",
            "confidence_score": 0.85
        }
        
        assert analyzer._validate_candidate(valid_candidate) is True
    
    def test_validate_candidate_invalid(self, analyzer):
        """잘못된 후보 데이터 검증 테스트"""
        # 필수 필드 누락
        invalid_candidate1 = {
            "start_time": 10.5,
            "end_time": 25.8,
            "reason": "지칭 패턴 탐지"
            # confidence_score 누락
        }
        
        # 논리적 오류 (시작시간 > 종료시간)
        invalid_candidate2 = {
            "start_time": 25.8,
            "end_time": 10.5,
            "reason": "지칭 패턴 탐지",
            "confidence_score": 0.85
        }
        
        # 신뢰도 범위 오류
        invalid_candidate3 = {
            "start_time": 10.5,
            "end_time": 25.8,
            "reason": "지칭 패턴 탐지",
            "confidence_score": 1.5  # > 1
        }
        
        assert analyzer._validate_candidate(invalid_candidate1) is False
        assert analyzer._validate_candidate(invalid_candidate2) is False
        assert analyzer._validate_candidate(invalid_candidate3) is False
    
    def test_parse_response_valid_json(self, analyzer):
        """유효한 JSON 응답 파싱 테스트"""
        json_response = '''```json
        [
            {
                "start_time": 15.0,
                "end_time": 35.0,
                "reason": "지칭 패턴 탐지 - '제가 요즘 진짜 잘 쓰는 게' 표현 발견",
                "confidence_score": 0.88
            }
        ]
        ```'''
        
        candidates = analyzer._parse_response(json_response)
        
        assert len(candidates) == 1
        assert candidates[0]["start_time"] == 15.0
        assert candidates[0]["end_time"] == 35.0
        assert candidates[0]["confidence_score"] == 0.88
    
    def test_parse_response_empty_list(self, analyzer):
        """빈 리스트 응답 파싱 테스트"""
        json_response = "```json\n[]\n```"
        
        candidates = analyzer._parse_response(json_response)
        
        assert candidates == []
    
    def test_parse_response_invalid_json(self, analyzer):
        """잘못된 JSON 응답 파싱 테스트"""
        invalid_response = "이것은 JSON이 아닙니다"
        
        candidates = analyzer._parse_response(invalid_response)
        
        assert candidates == []
    
    def test_get_test_candidates(self, analyzer):
        """테스트 후보 데이터 반환 테스트"""
        candidates = analyzer._get_test_candidates()
        
        assert len(candidates) >= 1
        for candidate in candidates:
            assert analyzer._validate_candidate(candidate) is True
    
    def test_analyze_script_no_client(self, analyzer):
        """모델 없이 스크립트 분석 테스트 (테스트 모드)"""
        analyzer.model = None  # 모델 비활성화
        
        candidates = analyzer.analyze_script([])
        
        # 테스트 데이터가 반환되어야 함
        assert len(candidates) >= 1
        for candidate in candidates:
            assert analyzer._validate_candidate(candidate) is True
    
    @patch('src.gemini_analyzer.first_pass_analyzer.genai')
    def test_analyze_script_with_mock_client(self, mock_genai, sample_script):
        """Mock 모델을 사용한 스크립트 분석 테스트"""
        # Mock 설정
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '''[
            {
                "start_time": 15.0,
                "end_time": 35.0,
                "reason": "지칭 패턴 탐지",
                "confidence_score": 0.85
            }
        ]'''
        
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        # 분석기 생성 및 테스트
        config = Config()
        config.GOOGLE_API_KEY = "test_api_key"
        analyzer = GeminiFirstPassAnalyzer(config)
        analyzer.model = mock_model
        
        candidates = analyzer.analyze_script(sample_script)
        
        assert len(candidates) == 1
        assert candidates[0]["start_time"] == 15.0
        assert candidates[0]["confidence_score"] == 0.85
        
        # API 호출 확인
        mock_model.generate_content.assert_called_once()
    
    def test_get_analyzer_info(self, analyzer):
        """분석기 정보 반환 테스트"""
        info = analyzer.get_analyzer_info()
        
        required_keys = [
            'model', 'max_tokens', 'temperature', 'timeout',
            'model_status', 'api_key_configured'
        ]
        
        for key in required_keys:
            assert key in info
        
        assert info['model'] == analyzer.config.GEMINI_MODEL
        assert info['api_key_configured'] is True
    
    def test_prompt_pattern_detection(self, analyzer):
        """프롬프트에 PRD 패턴이 포함되어 있는지 테스트"""
        system_prompt = analyzer.system_prompt
        
        # 4가지 핵심 패턴 확인
        patterns = [
            "지칭 및 소개 패턴",
            "상세 묘사 패턴", 
            "경험 및 효과 공유 패턴",
            "소유 및 애착 표현 패턴"
        ]
        
        for pattern in patterns:
            assert pattern in system_prompt
        
        # 구체적인 예시 문구 확인
        example_phrases = [
            "제가 요즘 진짜 잘 쓰는 게",
            "발라보면 제형이 진짜 꾸덕해요",
            "이거 쓰고 나서",
            "제 파우치에 항상"
        ]
        
        user_prompt = analyzer._get_user_prompt([])
        for phrase in example_phrases:
            assert phrase in user_prompt