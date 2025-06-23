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
        try:
            logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        except (AttributeError, TypeError):
            logger.setLevel(logging.INFO)  # 기본값 사용
        
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
        """PRD 기반 시스템 프롬프트 반환"""
        return """너는 지금부터 **'베테랑 유튜브 콘텐츠 큐레이터'** 역할을 수행한다. 너의 임무는 긴 영상 스크립트에서 시청자의 구매 욕구를 자극할 만한 '진짜 제품 추천' 구간만을 정확히 골라내는 것이다. 너는 단순 키워드 검색을 초월하여, 화자의 뉘앙스, 문장의 구조, 대화의 흐름 등 미묘한 '맥락적 신호'를 포착하는 최고의 전문가다.

**중요한 패턴들:**

1. **지칭 및 소개 패턴:** "제가 요즘 진짜 잘 쓰는 게 있는데...", "짠! 오늘 보여드릴 건 바로 이거예요."
2. **상세 묘사 패턴:** "딱 열면 향이 확 나는데...", "발라보면 제형이 진짜 꾸덕해요."
3. **경험 및 효과 공유 패턴:** "이거 쓰고 나서 피부가 완전 달라졌어요.", "아침에 화장이 진짜 잘 받아요."
4. **소유 및 애착 표현 패턴:** "이건 제 파우치에 항상 들어있는 거예요.", "해외 나갈 때 없으면 불안한 아이템이에요."

**주의사항:**
- 제품명이 직접 언급되지 않아도 위 패턴이 나타나면 '추천의 시작'을 알리는 강력한 신호로 인지해야 한다.
- 단순한 브랜드명 언급은 제외한다.
- PPL이나 광고성 멘트는 신중하게 판단한다."""

    def _get_user_prompt(self, script_data: List[Dict[str, Any]]) -> str:
        """사용자 프롬프트 생성"""
        # 스크립트를 문자열로 변환
        script_json = json.dumps(script_data, ensure_ascii=False, indent=2)
        
        return f"""아래 [전체 스크립트]를 분석하여, 다음 [지시사항]과 [판단 기준]을 완벽하게 준수하여 결과를 출력해줘.

**[전체 스크립트]**
{script_json}

**[지시사항]**

1. 스크립트 전체를 읽고, 아래 **[판단 기준]**에 부합하는 모든 '제품 추천 의심 구간'을 찾아라.
2. 각 구간에 대해, `start_time`, `end_time`, `reason`, `confidence_score`를 포함한 JSON 리스트로 결과를 반환해라.
3. 추천 구간이 없다면, 빈 리스트 `[]`를 반환하고 다른 어떤 설명도 추가하지 마라.

**[출력 형식]**
다음과 같은 JSON 형식으로만 출력하라:
```json
[
  {{
    "start_time": 91.2,
    "end_time": 125.8,
    "reason": "지칭 패턴 탐지 - '제가 요즘 진짜 잘 쓰는 게' 표현 발견",
    "confidence_score": 0.85
  }}
]
```

**[판단 기준]**

제품명이 직접 언급되지 않아도, 아래와 같은 패턴이 나타나면 '추천의 시작'을 알리는 강력한 신호로 인지해야 한다:

1. **지칭 패턴:** "제가 요즘 진짜 잘 쓰는 게 있는데...", "짠! 오늘 보여드릴 건 바로 이거예요."
2. **묘사 패턴:** "딱 열면 향이 확 나는데...", "발라보면 제형이 진짜 꾸덕해요."
3. **경험 패턴:** "이거 쓰고 나서 피부가 완전 달라졌어요.", "아침에 화장이 진짜 잘 받아요."
4. **소유 패턴:** "이건 제 파우치에 항상 들어있는 거예요.", "해외 나갈 때 없으면 불안한 아이템이에요."

**중요:** 단순한 브랜드명 언급이나 일반적인 대화는 제외하고, 명확한 추천 의도가 있는 구간만 선별하라."""

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
                        max_output_tokens=self.config.GEMINI_MAX_TOKENS,
                        temperature=self.config.GEMINI_TEMPERATURE,
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
        후보 데이터 유효성 검증
        
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
            
            # 논리적 유효성 검증
            if start_time < 0 or end_time < 0:
                return False
            if start_time >= end_time:
                return False
            if confidence_score < 0 or confidence_score > 1:
                return False
            if not reason.strip():
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