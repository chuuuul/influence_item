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
        """토큰 최적화된 2차 분석 시스템 프롬프트"""
        return """You are a product analysis expert creating viral Instagram content.

**CORE TASKS:**
1. Extract: Product name, category, features
2. Score: Sentiment (0-1), Usage proof (0-1), Influencer trust (0-1)
3. Generate: Titles, hashtags, captions
4. Detect: PPL probability

**SCORING FORMULA:**
Total = (0.50 × sentiment) + (0.35 × usage_proof) + (0.15 × influencer_trust) × 100

**PPL INDICATORS:** "협찬", "제품 제공", "PR", 과도한 칭찬, 상업적 맥락

**CONTENT STRATEGY:** 호기심 + 명확한 정보, 연예인명 + 제품명 + 카테고리 태그

**RULE:** Unknown info = null/[], accurate JSON only, natural Korean"""

    def _get_user_prompt(self, candidate_data: Dict[str, Any], source_info: Dict[str, Any]) -> str:
        """토큰 최적화된 2차 분석 프롬프트"""
        # 핵심 정보만 추출
        script_text = self._extract_script_text(candidate_data.get('script_segments', []))
        
        return f"""Analyze and create Instagram content package. Return JSON only.

**DATA:**
Channel: {source_info.get('channel_name', 'Unknown')}
Time: {candidate_data.get('start_time', 0)}-{candidate_data.get('end_time', 0)}s
Script: {script_text[:500]}...

**TASKS:**
1. Extract product name, category [대-중-소], features
2. Score sentiment/usage/influence (0-1)
3. Calculate total = (0.5×sentiment + 0.35×usage + 0.15×influence) × 100
4. Detect PPL probability
5. Generate 3 titles (50 chars), 8+ hashtags, caption

**JSON:**
```json
{{
  "source_info": {{"celebrity_name": "{source_info.get('channel_name', '')}", "channel_name": "{source_info.get('channel_name', '')}", "video_title": "{source_info.get('video_title', '')}", "video_url": "{source_info.get('video_url', '')}", "upload_date": "2025-06-25"}},
  "candidate_info": {{"product_name_ai": "string", "product_name_manual": null, "clip_start_time": {candidate_data.get('start_time', 0)}, "clip_end_time": {candidate_data.get('end_time', 0)}, "category_path": [], "features": [], "score_details": {{"total": 0, "sentiment_score": 0.0, "endorsement_score": 0.0, "influencer_score": 0.0}}, "hook_sentence": "", "summary_for_caption": "", "target_audience": [], "price_point": "중가", "endorsement_type": "", "recommended_titles": [], "recommended_hashtags": []}},
  "monetization_info": {{"is_coupang_product": false, "coupang_url_ai": null, "coupang_url_manual": null}},
  "status_info": {{"current_status": "needs_review", "is_ppl": false, "ppl_confidence": 0.0}}
}}
```

Unknown = null/[]. Accurate JSON only."""

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
    
    def _extract_script_text(self, script_segments: List[Dict[str, Any]]) -> str:
        """스크립트 세그먼트에서 텍스트만 추출하여 압축"""
        texts = []
        for seg in script_segments[:10]:  # 최대 10개 세그먼트만 사용
            text = seg.get('text', '').strip()
            if text and len(text) > 20:  # 의미있는 텍스트만
                texts.append(text[:100])  # 100자로 제한
        
        return " ".join(texts)[:400]  # 전체 400자로 제한
    
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
                        max_output_tokens=min(self.config.GEMINI_MAX_TOKENS, 2048),  # 2차 분석용 토큰 제한
                        temperature=max(0.1, self.config.GEMINI_TEMPERATURE - 0.1),  # 일관성 향상
                        top_p=0.9,
                        top_k=40
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