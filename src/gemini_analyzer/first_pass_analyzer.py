"""
Gemini 1차 분석 모듈

Whisper로 추출된 전체 영상 스크립트에서 제품 추천의 맥락을 가진 후보 구간을 탐지합니다.
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional
try:
    import google.generativeai as genai
except ImportError:
    # 테스트 환경에서 genai 모듈이 없을 경우를 위한 처리
    genai = None

from config.config import Config

# API 사용량 추적을 위한 임포트
try:
    from src.api.usage_tracker import get_tracker
except ImportError:
    # 추적기가 없는 경우 더미 함수
    def get_tracker():
        return None


class GeminiFirstPassAnalyzer:
    """Gemini 2.5 Flash를 활용한 1차 분석 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Gemini 1차 분석기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        self.model = None
        self._setup_client()
        
        # 프롬프트 시스템 초기화
        self.system_prompt = self._get_system_prompt()
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        
        # 안전한 로그 레벨 설정
        try:
            if hasattr(self.config, 'LOG_LEVEL') and isinstance(self.config.LOG_LEVEL, str):
                level_str = self.config.LOG_LEVEL.upper()
                if level_str == 'DEBUG':
                    logger.setLevel(logging.DEBUG)
                elif level_str == 'INFO':
                    logger.setLevel(logging.INFO)
                elif level_str == 'WARNING':
                    logger.setLevel(logging.WARNING)
                elif level_str == 'ERROR':
                    logger.setLevel(logging.ERROR)
                elif level_str == 'CRITICAL':
                    logger.setLevel(logging.CRITICAL)
                else:
                    logger.setLevel(logging.INFO)
            else:
                logger.setLevel(logging.INFO)
        except (AttributeError, TypeError):
            logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    def _setup_client(self) -> None:
        """Gemini 클라이언트 초기화"""
        if genai is None:
            self.logger.warning("Google GenAI 모듈이 설치되지 않았습니다. 테스트 모드로 실행됩니다.")
            return
            
        try:
            if not self.config.GOOGLE_API_KEY:
                self.logger.error("GOOGLE_API_KEY가 설정되지 않았습니다.")
                return
                
            genai.configure(api_key=self.config.GOOGLE_API_KEY)
            self.model = genai.GenerativeModel(self.config.GEMINI_MODEL)
            self.logger.info("Gemini 클라이언트 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"Gemini 클라이언트 초기화 실패: {str(e)}")
            
    def _get_system_prompt(self) -> str:
        """토큰 최적화된 정밀 프롬프트 시스템"""
        return """You are an AI product recommendation detector with 95%+ accuracy.

**PRIORITY DETECTION PATTERNS:**

HIGH (0.8-1.0): "오늘 소개", "제가 쓰는", "써보니까", "진짜 좋아요"
MEDIUM (0.6-0.8): "요즘 사용하는", "텍스처가", "다른 제품보다"
LOW (0.4-0.6): "이런 제품", "친구가 추천"

**EXCLUDE:** 단순 브랜드명, 뉴스 정보, 부정적 경험, 일반 카테고리

**CONTEXT RULES:**
- 앞뒤 3문장 분석
- 30초-3분 지속성 확인
- 중복 제거
- 감정 강도 측정"""

    def _get_user_prompt(self, script_data: List[Dict[str, Any]]) -> str:
        """토큰 최적화된 핵심 프롬프트 생성"""
        # 스크립트 핵심 정보만 추출 (토큰 절약)
        total_duration = max([seg.get('end', 0) for seg in script_data], default=0)
        segment_count = len(script_data)
        
        # 스크립트를 압축된 형태로 변환
        compressed_script = self._compress_script_data(script_data)
        
        return f"""Analyze this script for product recommendation segments. Return JSON only.

**SCRIPT:** {compressed_script}

**REQUIREMENTS:**
- Duration: {total_duration:.0f}s, Segments: {segment_count}
- Min 15s, Max 300s per segment
- Confidence ≥ 0.4
- No duplicates

**SCORING:**
Direct intro (+0.3), Personal use (+0.25), Effect mention (+0.2), Emotion (+0.15), Context (+0.1), Base (0.3)

**OUTPUT:**
```json
[{{"start_time": N, "end_time": N, "reason": "pattern_evidence", "confidence_score": 0.XX}}]
```

Empty array [] if no recommendations found."""

    def analyze_script(self, script_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        스크립트를 분석하여 제품 추천 후보 구간 탐지
        
        Args:
            script_data: Whisper에서 추출된 스크립트 데이터
            
        Returns:
            후보 구간 리스트
        """
        if self.model is None:
            self.logger.warning("Gemini 모델이 초기화되지 않았습니다. 테스트 데이터를 반환합니다.")
            return self._get_test_candidates()
            
        try:
            self.logger.info(f"Gemini 1차 분석 시작 - 스크립트 길이: {len(script_data)}개 세그먼트")
            start_time = time.time()
            
            # 프롬프트 생성
            user_prompt = self._get_user_prompt(script_data)
            
            # Gemini API 호출
            response = self._call_gemini_api(user_prompt)
            
            # 응답 파싱
            candidates = self._parse_response(response)
            
            process_time = time.time() - start_time
            self.logger.info(f"Gemini 1차 분석 완료 - {len(candidates)}개 후보 구간 탐지, 소요시간: {process_time:.2f}초")
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Gemini 1차 분석 실패: {str(e)}")
            return []
    
    def _compress_script_data(self, script_data: List[Dict[str, Any]]) -> str:
        """스크립트 데이터를 토큰 효율적으로 압축"""
        compressed_segments = []
        for seg in script_data:
            # 핵심 정보만 추출
            start = seg.get('start', 0)
            end = seg.get('end', 0) 
            text = seg.get('text', '').strip()
            
            # 불필요한 내용 제거
            if len(text) > 100:  # 긴 텍스트는 요약
                text = text[:100] + "..."
            
            compressed_segments.append(f"{start:.0f}-{end:.0f}s: {text}")
        
        return " | ".join(compressed_segments)
    
    def _call_gemini_api(self, user_prompt: str, max_retries: int = 3) -> str:
        """
        Gemini API 호출 (재시도 로직 포함)
        
        Args:
            user_prompt: 사용자 프롬프트
            max_retries: 최대 재시도 횟수
            
        Returns:
            API 응답 텍스트
        """
        # API 사용량 추적 시작
        tracker = get_tracker()
        
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                self.logger.debug(f"Gemini API 호출 시도 {attempt + 1}/{max_retries}")
                
                response = self.model.generate_content(
                    user_prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=min(self.config.GEMINI_MAX_TOKENS, 1024),  # 토큰 제한
                        temperature=max(0.1, self.config.GEMINI_TEMPERATURE - 0.2),  # 낮은 temperature로 일관성 향상
                        top_p=0.8,  # 추가 최적화
                        top_k=20
                    ),
                )
                
                if response and response.text:
                    self.logger.debug("Gemini API 호출 성공")
                    
                    # 사용량 추적 - 성공
                    if tracker:
                        response_time = (time.time() - start_time) * 1000
                        # 토큰 수 추정 (실제 토큰 수는 response 객체에서 가져와야 함)
                        estimated_tokens = len(user_prompt) // 4 + len(response.text) // 4  # 대략적 추정
                        tracker.track_api_call(
                            api_name="gemini",
                            endpoint="/v1/generate_content",
                            method="POST",
                            tokens_used=estimated_tokens,
                            status_code=200,
                            response_time_ms=response_time,
                            metadata={
                                "model": self.config.GEMINI_MODEL,
                                "max_tokens": self.config.GEMINI_MAX_TOKENS,
                                "temperature": self.config.GEMINI_TEMPERATURE,
                                "attempt": attempt + 1
                            }
                        )
                    
                    return response.text
                else:
                    raise ValueError("빈 응답 받음")
                    
            except Exception as e:
                self.logger.warning(f"Gemini API 호출 실패 (시도 {attempt + 1}): {str(e)}")
                
                # 사용량 추적 - 실패
                if tracker:
                    response_time = (time.time() - start_time) * 1000
                    tracker.track_api_call(
                        api_name="gemini",
                        endpoint="/v1/generate_content",
                        method="POST",
                        tokens_used=0,
                        status_code=500,
                        response_time_ms=response_time,
                        error_message=str(e),
                        metadata={
                            "model": self.config.GEMINI_MODEL,
                            "attempt": attempt + 1,
                            "max_retries": max_retries
                        }
                    )
                
                if attempt == max_retries - 1:
                    raise
                
                # 지수 백오프
                wait_time = (2 ** attempt) + 1
                self.logger.debug(f"{wait_time}초 대기 후 재시도")
                time.sleep(wait_time)
        
        raise Exception("모든 재시도 실패")
    
    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Gemini 응답을 파싱하여 구조화된 데이터로 변환
        
        Args:
            response_text: Gemini 응답 텍스트
            
        Returns:
            파싱된 후보 구간 리스트
        """
        try:
            # JSON 코드 블록 제거
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:].strip()
            elif cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:].strip()
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3].strip()
            
            # JSON 파싱
            candidates = json.loads(cleaned_text)
            
            # 데이터 검증
            validated_candidates = []
            for candidate in candidates:
                if self._validate_candidate(candidate):
                    validated_candidates.append(candidate)
                else:
                    self.logger.warning(f"잘못된 후보 데이터 무시: {candidate}")
            
            self.logger.debug(f"응답 파싱 완료 - {len(validated_candidates)}개 유효한 후보")
            return validated_candidates
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 실패: {str(e)}")
            self.logger.debug(f"원본 응답: {response_text}")
            return []
        except Exception as e:
            self.logger.error(f"응답 파싱 오류: {str(e)}")
            return []
    
    def _validate_candidate(self, candidate: Dict[str, Any]) -> bool:
        """
        강화된 후보 데이터 유효성 검증
        
        Args:
            candidate: 후보 구간 데이터
            
        Returns:
            유효성 여부
        """
        required_fields = ['start_time', 'end_time', 'reason', 'confidence_score']
        
        # 필수 필드 확인
        for field in required_fields:
            if field not in candidate:
                return False
        
        # 타입 검증
        try:
            start_time = float(candidate['start_time'])
            end_time = float(candidate['end_time'])
            confidence_score = float(candidate['confidence_score'])
            reason = str(candidate['reason'])
            
            # 기본 논리적 유효성 검증
            if start_time < 0 or end_time < 0:
                return False
            if start_time >= end_time:
                return False
            if confidence_score < 0 or confidence_score > 1:
                return False
            if not reason.strip():
                return False
            
            # 강화된 품질 검증
            duration = end_time - start_time
            
            # 최소/최대 지속 시간 검증
            if duration < 10:  # 10초 미만은 너무 짧음
                self.logger.warning(f"구간이 너무 짧음: {duration:.1f}초")
                return False
            if duration > 300:  # 5분 초과는 너무 김
                self.logger.warning(f"구간이 너무 김: {duration:.1f}초")
                return False
            
            # 신뢰도 임계값 검증
            if confidence_score < 0.4:  # 너무 낮은 신뢰도는 제외
                self.logger.debug(f"신뢰도가 너무 낮음: {confidence_score:.2f}")
                return False
            
            # 이유 품질 검증
            reason_lower = reason.lower()
            valid_patterns = ['직접', '소개', '추천', '사용', '경험', '효과', '애용', '선호', '만족']
            if not any(pattern in reason_lower for pattern in valid_patterns):
                self.logger.debug(f"유효한 패턴이 포함되지 않은 이유: {reason}")
                return False
                
            return True
            
        except (ValueError, TypeError):
            return False
    
    def _get_test_candidates(self) -> List[Dict[str, Any]]:
        """테스트용 더미 후보 데이터 반환"""
        return [
            {
                "start_time": 120.5,
                "end_time": 185.2,
                "reason": "지칭 패턴 탐지 - '제가 요즘 정말 잘 쓰는 제품이' 표현 발견",
                "confidence_score": 0.88
            },
            {
                "start_time": 245.1,
                "end_time": 290.3,
                "reason": "경험 패턴 탐지 - '이거 쓰고 나서 완전 달라졌어요' 효과 언급",
                "confidence_score": 0.82
            }
        ]
    
    def get_analyzer_info(self) -> Dict[str, Any]:
        """
        분석기 정보 반환
        
        Returns:
            분석기 정보 딕셔너리
        """
        return {
            'model': self.config.GEMINI_MODEL,
            'max_tokens': self.config.GEMINI_MAX_TOKENS,
            'temperature': self.config.GEMINI_TEMPERATURE,
            'timeout': self.config.GEMINI_TIMEOUT,
            'model_status': 'initialized' if self.model else 'not_initialized',
            'api_key_configured': bool(self.config.GOOGLE_API_KEY)
        }