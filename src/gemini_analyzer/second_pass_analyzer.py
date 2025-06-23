"""
Gemini 2차 분석 모듈

1차 분석에서 탐지된 후보 구간의 상세한 제품 정보를 추출합니다.
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
from .models import ProductAnalysisResult, SourceInfo, CandidateInfo, MonetizationInfo, StatusInfo, ScoreDetails


class GeminiSecondPassAnalyzer:
    """Gemini 2.5 Flash를 활용한 2차 분석 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Gemini 2차 분석기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        self.model = None
        self._setup_client()
        
        # 프롬프트 시스템 초기화
        self.system_prompt = self._get_system_prompt()
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
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
        return """너는 지금부터 소비자의 구매 심리를 꿰뚫는 **'탑티어 커머스 콘텐츠 크리에이터'** 역할을 맡는다. 너의 임무는 주어진 음성 정보를 바탕으로, 즉시 바이럴될 수 있는 인스타그램 릴스 콘텐츠의 모든 구성 요소를 완벽하게 생성하는 것이다.

**핵심 역량:**
1. **제품 정보 추출**: 음성에서 제품명, 카테고리, 특징을 정확히 파악
2. **매력도 평가**: 감성 강도, 실사용 인증 강도, 인플루언서 신뢰도를 0-1 척도로 측정
3. **콘텐츠 생성**: 바이럴 가능한 제목, 해시태그, 캡션 생성
4. **PPL 탐지**: 유료 광고 확률을 정확히 분석

**매력도 스코어링 공식:**
총점 = (0.50 × 감성 강도) + (0.35 × 실사용 인증 강도) + (0.15 × 인플루언서 신뢰도) × 100

**PPL 탐지 기준:**
- 명시적 광고 표현: "협찬", "제품 제공", "PR", "광고" 등
- 과도한 칭찬: 부자연스럽게 긍정적인 표현
- 상업적 맥락: 할인, 이벤트, 구매 링크 언급

**Instagram 콘텐츠 전략:**
- 제목: 호기심 유발 + 명확한 정보 전달
- 해시태그: 연예인명 + 제품명 + 카테고리 + 트렌드 키워드
- 캡션: 친근한 톤 + 핵심 정보 + 구매 욕구 자극

**중요 원칙:**
- 정보가 부족하면 절대 지어내지 말고 null 또는 빈 배열로 반환
- 모든 출력은 정확한 JSON 스키마를 준수해야 함
- 한국어 콘텐츠에 최적화된 자연스러운 표현 사용"""

    def _get_user_prompt(self, candidate_data: Dict[str, Any], source_info: Dict[str, Any]) -> str:
        """사용자 프롬프트 생성"""
        return f"""아래 [분석할 데이터]를 기반으로, 다음 [지시사항]에 따라 콘텐츠 패키지를 생성하고, 최종 결과는 **아래 [JSON 스키마]**에 맞춰 완벽하게 출력해줘. 정보가 부족하면, 절대 지어내지 말고 `null` 또는 빈 배열 `[]`로 반환해야 한다.

**[분석할 데이터]**
영상 정보:
- 연예인명: {source_info.get('celebrity_name', '알 수 없음')}
- 채널명: {source_info.get('channel_name', '알 수 없음')}
- 영상 제목: {source_info.get('video_title', '알 수 없음')}
- 영상 URL: {source_info.get('video_url', '알 수 없음')}

후보 구간 정보:
- 시작 시간: {candidate_data.get('start_time', 0)}초
- 종료 시간: {candidate_data.get('end_time', 0)}초
- 탐지 이유: {candidate_data.get('reason', '알 수 없음')}
- 신뢰도: {candidate_data.get('confidence_score', 0)}

음성 스크립트:
{json.dumps(candidate_data.get('script_segments', []), ensure_ascii=False, indent=2)}

**[지시사항]**

1. **제품 정보 추출**:
   - 제품명을 정확히 파악 (브랜드명 + 제품명 + 색상/옵션)
   - 카테고리를 대분류 → 중분류 → 소분류 순으로 분류
   - 화자가 언급한 제품 특징들을 모두 추출

2. **매력도 스코어링**:
   - 감성 강도: 화자의 감정적 표현 강도 (0-1)
   - 실사용 인증 강도: 실제 사용 경험의 신뢰도 (0-1)
   - 인플루언서 신뢰도: 화자/채널의 영향력 평가 (0-1)

3. **PPL 확률 분석**:
   - 광고성 표현, 과도한 칭찬, 상업적 맥락 종합 평가
   - 0-1 척도로 PPL 확률 측정

4. **Instagram 콘텐츠 생성**:
   - 호기심을 유발하는 제목 3개 (각 50자 이내)
   - 관련 해시태그 8개 이상
   - 친근한 톤의 캡션용 요약

**[JSON 스키마]**
```json
{{
  "source_info": {{
    "celebrity_name": "string",
    "channel_name": "string", 
    "video_title": "string",
    "video_url": "string",
    "upload_date": "YYYY-MM-DD"
  }},
  "candidate_info": {{
    "product_name_ai": "string",
    "product_name_manual": null,
    "clip_start_time": number,
    "clip_end_time": number,
    "category_path": ["대분류", "중분류", "소분류"],
    "features": ["특징1", "특징2", ...],
    "score_details": {{
      "total": number,
      "sentiment_score": number,
      "endorsement_score": number,
      "influencer_score": number
    }},
    "hook_sentence": "string",
    "summary_for_caption": "string",
    "target_audience": ["타겟1", "타겟2", ...],
    "price_point": "저가|중가|프리미엄|럭셔리",
    "endorsement_type": "string",
    "recommended_titles": ["제목1", "제목2", "제목3"],
    "recommended_hashtags": ["#태그1", "#태그2", ...]
  }},
  "monetization_info": {{
    "is_coupang_product": false,
    "coupang_url_ai": null,
    "coupang_url_manual": null
  }},
  "status_info": {{
    "current_status": "needs_review",
    "is_ppl": boolean,
    "ppl_confidence": number
  }}
}}
```

**중요 주의사항:**
- 제품명이 불분명하면 "확인 필요"로 설정
- 카테고리는 반드시 1-3개 단계로 구성
- 특징은 화자가 실제 언급한 내용만 포함
- 해시태그는 '#' 포함하여 작성
- 모든 숫자는 소수점 둘째 자리까지만
- JSON 형식을 정확히 준수하여 출력"""

    def extract_product_info(self, candidate_data: Dict[str, Any], source_info: Dict[str, Any]) -> ProductAnalysisResult:
        """
        후보 구간의 상세 제품 정보 추출
        
        Args:
            candidate_data: 1차 분석에서 탐지된 후보 구간 데이터
            source_info: 영상 소스 정보
            
        Returns:
            완전한 제품 분석 결과
        """
        if self.model is None:
            self.logger.warning("Gemini 모델이 초기화되지 않았습니다. 테스트 데이터를 반환합니다.")
            return self._get_test_result(candidate_data, source_info)
            
        try:
            self.logger.info(f"Gemini 2차 분석 시작 - 후보 구간: {candidate_data.get('start_time', 0)}-{candidate_data.get('end_time', 0)}초")
            start_time = time.time()
            
            # 프롬프트 생성
            user_prompt = self._get_user_prompt(candidate_data, source_info)
            
            # Gemini API 호출
            response = self._call_gemini_api(user_prompt)
            
            # 응답 파싱
            result_data = self._parse_response(response)
            
            # Pydantic 모델로 검증
            result = ProductAnalysisResult(**result_data)
            
            process_time = time.time() - start_time
            self.logger.info(f"Gemini 2차 분석 완료 - 제품: {result.candidate_info.product_name_ai}, 소요시간: {process_time:.2f}초")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Gemini 2차 분석 실패: {str(e)}")
            return self._get_test_result(candidate_data, source_info)
    
    def _call_gemini_api(self, user_prompt: str, max_retries: int = 3) -> str:
        """
        Gemini API 호출 (재시도 로직 포함)
        
        Args:
            user_prompt: 사용자 프롬프트
            max_retries: 최대 재시도 횟수
            
        Returns:
            API 응답 텍스트
        """
        for attempt in range(max_retries):
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
                    return response.text
                else:
                    raise ValueError("빈 응답 받음")
                    
            except Exception as e:
                self.logger.warning(f"Gemini API 호출 실패 (시도 {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    raise
                
                # 지수 백오프
                wait_time = (2 ** attempt) + 1
                self.logger.debug(f"{wait_time}초 대기 후 재시도")
                time.sleep(wait_time)
        
        raise Exception("모든 재시도 실패")
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Gemini 응답을 파싱하여 구조화된 데이터로 변환
        
        Args:
            response_text: Gemini 응답 텍스트
            
        Returns:
            파싱된 제품 분석 데이터
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
            result_data = json.loads(cleaned_text)
            
            self.logger.debug("응답 파싱 완료")
            return result_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 실패: {str(e)}")
            self.logger.debug(f"원본 응답: {response_text}")
            raise ValueError(f"유효하지 않은 JSON 응답: {str(e)}")
        except Exception as e:
            self.logger.error(f"응답 파싱 오류: {str(e)}")
            raise
    
    def calculate_attractiveness_score(self, sentiment: float, endorsement: float, influencer: float) -> int:
        """
        매력도 스코어링 공식 적용
        
        Args:
            sentiment: 감성 강도 (0-1)
            endorsement: 실사용 인증 강도 (0-1)  
            influencer: 인플루언서 신뢰도 (0-1)
            
        Returns:
            총 매력도 점수 (0-100)
        """
        # PRD 공식: (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
        total_score = (0.50 * sentiment + 0.35 * endorsement + 0.15 * influencer) * 100
        return int(round(total_score))
    
    def _get_test_result(self, candidate_data: Dict[str, Any], source_info: Dict[str, Any]) -> ProductAnalysisResult:
        """테스트용 더미 분석 결과 반환"""
        # 매력도 점수 계산
        sentiment_score = 0.85
        endorsement_score = 0.90
        influencer_score = 0.80
        total_score = self.calculate_attractiveness_score(sentiment_score, endorsement_score, influencer_score)
        
        return ProductAnalysisResult(
            source_info=SourceInfo(
                celebrity_name='테스트 연예인',
                channel_name=source_info.get('channel_name', '테스트 채널'),
                video_title=source_info.get('video_title', '테스트 영상'),
                video_url=source_info.get('video_url', 'https://youtube.com/test'),
                upload_date="2025-06-22"
            ),
            candidate_info=CandidateInfo(
                product_name_ai="테스트 뷰티 제품",
                product_name_manual=None,
                clip_start_time=candidate_data.get('start_time', 120),
                clip_end_time=candidate_data.get('end_time', 180),
                category_path=["뷰티", "스킨케어", "세럼"],
                features=["보습력이 뛰어남", "빠른 흡수", "끈적이지 않음"],
                score_details=ScoreDetails(
                    total=total_score,
                    sentiment_score=sentiment_score,
                    endorsement_score=endorsement_score,
                    influencer_score=influencer_score
                ),
                hook_sentence="연예인이 매일 쓴다는 그 세럼의 정체는?",
                summary_for_caption="연예인이 추천하는 보습 세럼! 끈적이지 않으면서도 보습력이 뛰어나다고 해요.",
                target_audience=["20대 여성", "스킨케어 관심층", "건성 피부"],
                price_point="중가",
                endorsement_type="일상적 사용",
                recommended_titles=[
                    "연예인이 매일 쓰는 '그 세럼' 정보 공개!",
                    "보습력 끝판왕! 연예인 추천 세럼",
                    "끈적이지 않는 보습 세럼 찾는다면?"
                ],
                recommended_hashtags=[
                    "#연예인추천", "#보습세럼", "#스킨케어", "#뷰티",
                    "#세럼추천", "#보습관리", "#건성피부", "#데일리케어"
                ]
            ),
            monetization_info=MonetizationInfo(
                is_coupang_product=False,
                coupang_url_ai=None,
                coupang_url_manual=None
            ),
            status_info=StatusInfo(
                current_status="needs_review",
                is_ppl=False,
                ppl_confidence=0.15
            )
        )
    
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