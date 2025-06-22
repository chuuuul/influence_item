"""
PPL 컨텍스트 분석기

Gemini API를 활용하여 영상의 컨텍스트를 분석하고 
상업적 목적성을 평가하는 모듈입니다.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from ..gemini_analyzer.state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class ContextAnalysisResult:
    """컨텍스트 분석 결과"""
    commercial_likelihood: float
    reasoning: str
    key_indicators: List[str]
    confidence: float
    raw_response: Dict[str, Any]


class PPLContextAnalyzer:
    """Gemini API 기반 PPL 컨텍스트 분석기"""
    
    def __init__(self, state_manager: StateManager):
        """
        Args:
            state_manager: Gemini API 호출을 위한 상태 관리자
        """
        self.state_manager = state_manager
        self.logger = logging.getLogger(__name__)
        
        # PPL 컨텍스트 분석용 프롬프트 템플릿
        self.PPL_CONTEXT_ANALYSIS_PROMPT = """
당신은 YouTube 콘텐츠의 PPL(유료광고) 여부를 판단하는 전문가입니다.
아래 정보를 종합적으로 분석하여 이 콘텐츠의 상업적 목적성을 평가해주세요.

**분석 데이터:**
- 영상 제목: {video_title}
- 영상 설명: {video_description}
- 음성 스크립트 구간: {transcript_excerpt}
- 패턴 분석 결과: {pattern_analysis_result}

**분석 관점:**
1. **언어 톤앤매너의 상업성**: 마케팅적 표현, 과도한 칭찬, 판매 유도 언어 사용
2. **제품 소개의 편향성**: 객관적 리뷰 vs 일방적 추천, 단점 언급 부재
3. **구매 유도 의도**: 할인 정보, 구매 링크 언급, 긴급성 조성
4. **브랜드 관계 암시**: 협찬 감사, 브랜드와의 특별한 관계 언급
5. **전반적인 컨텍스트**: 자연스러운 사용 vs 의도적 노출

**중요 지침:**
- 단순한 제품 언급은 PPL이 아닙니다
- 진정성 있는 개인적 경험 공유는 유기적 콘텐츠입니다
- 명시적 광고 표시가 없어도 상업적 의도를 파악해야 합니다
- 맥락과 톤을 종합적으로 고려해야 합니다

**출력 형식 (반드시 JSON으로만 응답):**
{{
  "commercial_likelihood": 0.0-1.0 사이의 값,
  "reasoning": "구체적 분석 근거와 판단 이유",
  "key_indicators": ["발견된 상업적 신호들의 리스트"],
  "confidence": 0.0-1.0 사이의 분석 확신도
}}
"""

    async def analyze_context(
        self,
        video_title: str,
        video_description: str,
        transcript_excerpt: str,
        pattern_analysis_result: Dict[str, Any]
    ) -> ContextAnalysisResult:
        """
        영상 컨텍스트를 분석하여 상업적 목적성 평가
        
        Args:
            video_title: 영상 제목
            video_description: 영상 설명
            transcript_excerpt: 분석 대상 음성 스크립트 구간
            pattern_analysis_result: 패턴 분석 결과
            
        Returns:
            ContextAnalysisResult: 컨텍스트 분석 결과
        """
        try:
            self.logger.info("PPL 컨텍스트 분석 시작")
            
            # 프롬프트 생성
            prompt = self.PPL_CONTEXT_ANALYSIS_PROMPT.format(
                video_title=video_title,
                video_description=video_description[:500],  # 설명 길이 제한
                transcript_excerpt=transcript_excerpt,
                pattern_analysis_result=json.dumps(pattern_analysis_result, ensure_ascii=False, indent=2)
            )
            
            # Gemini API 호출
            response = await self.state_manager.call_gemini_api(
                prompt=prompt,
                temperature=0.1,  # 낮은 temperature로 일관성 있는 분석
                max_tokens=1000
            )
            
            # JSON 응답 파싱
            analysis_result = self._parse_gemini_response(response)
            
            self.logger.info(
                f"PPL 컨텍스트 분석 완료 - 상업적 가능성: {analysis_result.commercial_likelihood:.3f}, "
                f"확신도: {analysis_result.confidence:.3f}"
            )
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"PPL 컨텍스트 분석 오류: {str(e)}")
            # 기본값 반환 (오류 시 중립적 판단)
            return ContextAnalysisResult(
                commercial_likelihood=0.5,
                reasoning=f"분석 중 오류 발생: {str(e)}",
                key_indicators=[],
                confidence=0.0,
                raw_response={}
            )

    def _parse_gemini_response(self, response: str) -> ContextAnalysisResult:
        """
        Gemini API 응답을 파싱하여 구조화된 결과로 변환
        
        Args:
            response: Gemini API 원시 응답
            
        Returns:
            ContextAnalysisResult: 파싱된 분석 결과
        """
        try:
            # JSON 부분만 추출 (마크다운 코드 블록 제거)
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]
            
            # JSON 파싱
            parsed_data = json.loads(json_str.strip())
            
            # 데이터 검증 및 정규화
            commercial_likelihood = self._validate_score(
                parsed_data.get("commercial_likelihood", 0.5)
            )
            confidence = self._validate_score(
                parsed_data.get("confidence", 0.5)
            )
            
            return ContextAnalysisResult(
                commercial_likelihood=commercial_likelihood,
                reasoning=parsed_data.get("reasoning", "분석 근거 없음"),
                key_indicators=parsed_data.get("key_indicators", []),
                confidence=confidence,
                raw_response=parsed_data
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"Gemini 응답 파싱 실패: {str(e)}")
            # 파싱 실패 시 텍스트 분석으로 대체
            return self._fallback_text_analysis(response)

    def _fallback_text_analysis(self, response: str) -> ContextAnalysisResult:
        """
        JSON 파싱 실패 시 텍스트 기반 분석으로 대체
        
        Args:
            response: Gemini API 원시 응답
            
        Returns:
            ContextAnalysisResult: 텍스트 기반 분석 결과
        """
        # 간단한 키워드 기반 분석
        commercial_keywords = [
            "협찬", "광고", "후원", "제공", "할인", "이벤트",
            "구매", "링크", "코드", "쿠폰", "프로모션"
        ]
        
        response_lower = response.lower()
        found_keywords = [kw for kw in commercial_keywords if kw in response_lower]
        
        # 키워드 수에 따른 점수 계산
        commercial_likelihood = min(0.8, len(found_keywords) * 0.2)
        
        return ContextAnalysisResult(
            commercial_likelihood=commercial_likelihood,
            reasoning=f"텍스트 기반 분석 - 발견된 상업적 키워드: {found_keywords}",
            key_indicators=found_keywords,
            confidence=0.3,  # 낮은 확신도
            raw_response={"fallback": True, "original_response": response}
        )

    @staticmethod
    def _validate_score(score: Any) -> float:
        """
        점수 값을 0.0-1.0 범위로 검증 및 정규화
        
        Args:
            score: 검증할 점수 값
            
        Returns:
            float: 정규화된 점수 (0.0-1.0)
        """
        try:
            score_float = float(score)
            return max(0.0, min(1.0, score_float))
        except (ValueError, TypeError):
            return 0.5  # 기본값

    def get_commercial_indicators(self) -> List[str]:
        """
        상업적 지표 키워드 목록 반환
        
        Returns:
            List[str]: 상업적 지표 키워드들
        """
        return [
            "협찬", "광고", "후원", "제공받은", "무료로",
            "할인", "쿠폰", "이벤트", "프로모션", "특가",
            "구매 링크", "할인 코드", "지금 주문하면",
            "브랜드 앰버서더", "공식 파트너"
        ]