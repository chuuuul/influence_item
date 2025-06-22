"""
실사용 인증 강도 분석 모듈

구체적 사용법, 시연, 효과 언급을 분석하여 실사용 인증 강도를 계산합니다.
0.0-1.0 범위의 점수를 반환합니다.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EndorsementPattern:
    """실사용 인증 패턴 정의"""
    usage_patterns: List[str]
    demonstration_patterns: List[str]
    effect_patterns: List[str]
    experience_patterns: List[str]
    possession_patterns: List[str]


class EndorsementAnalyzer:
    """실사용 인증 강도 분석기"""
    
    def __init__(self):
        """실사용 인증 분석기 초기화"""
        self.endorsement_patterns = self._load_endorsement_patterns()
        logger.info("실사용 인증 강도 분석기 초기화 완료")
    
    def _load_endorsement_patterns(self) -> EndorsementPattern:
        """실사용 인증 패턴 로드"""
        return EndorsementPattern(
            usage_patterns=[
                # 직접적 사용 표현
                "써봤는데", "써보니", "써보면", "사용해봤", "사용해보니",
                "사용하면", "써보셨", "쓰고있", "사용중", "쓰고나서",
                "발라봤", "발라보니", "발라보면", "발랐는데", "발라서",
                
                # 구체적 사용법
                "이렇게 써", "이렇게 바르", "이렇게 사용", "방법은",
                "사용법", "바르는법", "쓰는법", "어떻게 써", "어떻게 바르",
                "몇 번", "얼마나", "언제", "어디에", "어떤 부위",
                
                # 사용 과정 설명
                "먼저", "그다음", "그리고", "마지막으로", "단계",
                "순서", "과정", "절차", "방식", "팁"
            ],
            
            demonstration_patterns=[
                # 시연 관련 표현
                "보여드릴", "보여줄", "시연", "테스트", "실험",
                "직접", "실제로", "지금", "바로", "여기서",
                "카메라", "영상", "화면", "보시면", "보세요",
                
                # 비교 시연
                "비교", "차이", "전후", "before", "after",
                "vs", "대비", "달라", "변화", "개선",
                
                # 실시간 설명
                "지금", "현재", "이순간", "실시간", "라이브",
                "바로", "즉석", "당장", "그 자리에서"
            ],
            
            effect_patterns=[
                # 효과 설명
                "효과", "변화", "달라", "개선", "좋아", "나아",
                "결과", "성과", "영향", "도움", "유용", "유효",
                "신기하게", "놀랍게", "확실히", "분명히",
                
                # 구체적 효과
                "촉촉", "부드러", "매끄러", "깔끔", "깨끗",
                "하얗", "밝아", "윤기", "탄력", "볼륨",
                "진정", "안정", "편안", "시원", "따뜻",
                
                # 시간별 효과
                "바로", "즉시", "금세", "곧바로", "순식간",
                "하루", "일주일", "한달", "꾸준히", "계속",
                "지속", "오래", "오랫동안", "장기간"
            ],
            
            experience_patterns=[
                # 개인 경험
                "경험", "체험", "느낌", "인상", "생각", "의견",
                "후기", "리뷰", "평가", "솔직히", "정말로",
                "실제로", "진짜로", "사실", "정말",
                
                # 감각적 경험
                "느껴", "만져", "보니", "향이", "냄새", "질감",
                "텍스처", "무게", "크기", "모양", "색깔",
                
                # 비교 경험
                "다른 것과", "기존에", "평소에", "이전에",
                "원래", "전에 쓰던", "다른 브랜드", "타사"
            ],
            
            possession_patterns=[
                # 소유/보유 표현
                "가지고", "있어요", "구매", "샀어", "산지",
                "구입", "주문", "받았", "도착", "배송",
                "파우치", "화장대", "서랍", "집에", "방에",
                
                # 애착 표현
                "애정템", "찐템", "필수템", "없으면 안되", "꼭 필요",
                "항상", "언제나", "매일", "자주", "계속",
                "단골", "리피트", "재구매", "또 샀", "다시",
                
                # 추천 의도
                "추천", "강추", "소개", "알려드리", "공유",
                "말씀드리", "보여드리", "설명드리"
            ]
        )
    
    def analyze_usage_authenticity(
        self, 
        usage_patterns: List[str], 
        demonstration_level: int
    ) -> float:
        """
        실사용 인증 강도 분석
        
        Args:
            usage_patterns: 사용 패턴 텍스트 리스트
            demonstration_level: 시연 레벨 (0-3)
            
        Returns:
            실사용 인증 강도 점수 (0.0-1.0)
        """
        try:
            if not usage_patterns:
                return 0.0
            
            # 전체 텍스트 결합
            combined_text = " ".join(usage_patterns).lower()
            
            # 개별 분석 수행
            usage_score = self._calculate_usage_score(combined_text)
            demonstration_score = self._calculate_demonstration_score(
                combined_text, demonstration_level
            )
            effect_score = self._calculate_effect_score(combined_text)
            experience_score = self._calculate_experience_score(combined_text)
            possession_score = self._calculate_possession_score(combined_text)
            
            # 가중 평균 계산
            endorsement_score = (
                usage_score * 0.30 +
                demonstration_score * 0.25 +
                effect_score * 0.20 +
                experience_score * 0.15 +
                possession_score * 0.10
            )
            
            # 0.0-1.0 범위로 정규화
            endorsement_score = max(0.0, min(1.0, endorsement_score))
            
            logger.debug(f"실사용 인증 강도 분석 완료 - 점수: {endorsement_score:.3f}")
            return endorsement_score
            
        except Exception as e:
            logger.error(f"실사용 인증 강도 분석 실패: {str(e)}")
            return 0.5  # 기본값 반환
    
    def _calculate_usage_score(self, text: str) -> float:
        """사용 패턴 점수 계산"""
        usage_count = 0
        total_words = len(text.split())
        
        for pattern in self.endorsement_patterns.usage_patterns:
            count = text.count(pattern)
            if count > 0:
                # 구체적 사용법 설명은 더 높은 점수
                weight = 2.0 if any(keyword in pattern for keyword in [
                    "이렇게", "방법", "법", "어떻게", "단계", "순서"
                ]) else 1.0
                usage_count += count * weight
        
        if total_words == 0:
            return 0.0
        
        score = usage_count / total_words
        return min(1.0, score * 3)
    
    def _calculate_demonstration_score(self, text: str, demonstration_level: int) -> float:
        """시연 점수 계산"""
        demo_count = 0
        
        for pattern in self.endorsement_patterns.demonstration_patterns:
            count = text.count(pattern)
            demo_count += count
        
        # 텍스트 기반 점수
        text_score = min(1.0, demo_count / 10)
        
        # 시연 레벨 기반 점수 (0-3)
        level_score = demonstration_level / 3.0
        
        # 두 점수의 가중 평균
        return text_score * 0.4 + level_score * 0.6
    
    def _calculate_effect_score(self, text: str) -> float:
        """효과 언급 점수 계산"""
        effect_count = 0
        total_words = len(text.split())
        
        for pattern in self.endorsement_patterns.effect_patterns:
            count = text.count(pattern)
            if count > 0:
                # 구체적 효과 설명은 더 높은 점수
                weight = 2.0 if len(pattern) > 3 else 1.0
                effect_count += count * weight
        
        if total_words == 0:
            return 0.0
        
        score = effect_count / total_words
        return min(1.0, score * 4)
    
    def _calculate_experience_score(self, text: str) -> float:
        """개인 경험 점수 계산"""
        experience_count = 0
        
        for pattern in self.endorsement_patterns.experience_patterns:
            count = text.count(pattern)
            experience_count += count
        
        # 문장 수 대비 정규화
        sentence_count = len(re.split(r'[.!?]', text))
        if sentence_count == 0:
            return 0.0
        
        score = experience_count / sentence_count
        return min(1.0, score)
    
    def _calculate_possession_score(self, text: str) -> float:
        """소유/애착 점수 계산"""
        possession_count = 0
        
        for pattern in self.endorsement_patterns.possession_patterns:
            count = text.count(pattern)
            if count > 0:
                # 애착 표현은 더 높은 점수
                weight = 3.0 if any(keyword in pattern for keyword in [
                    "애정", "찐", "필수", "없으면", "항상", "매일"
                ]) else 1.0
                possession_count += count * weight
        
        total_words = len(text.split())
        if total_words == 0:
            return 0.0
        
        score = possession_count / total_words
        return min(1.0, score * 2)
    
    def get_endorsement_breakdown(self, usage_patterns: List[str], demonstration_level: int = 0) -> Dict[str, float]:
        """실사용 인증 분석 세부 내역 반환"""
        if not usage_patterns:
            return {
                "usage_score": 0.0,
                "demonstration_score": 0.0,
                "effect_score": 0.0,
                "experience_score": 0.0,
                "possession_score": 0.0,
                "total_endorsement": 0.0
            }
        
        combined_text = " ".join(usage_patterns).lower()
        
        usage_score = self._calculate_usage_score(combined_text)
        demonstration_score = self._calculate_demonstration_score(combined_text, demonstration_level)
        effect_score = self._calculate_effect_score(combined_text)
        experience_score = self._calculate_experience_score(combined_text)
        possession_score = self._calculate_possession_score(combined_text)
        
        total_endorsement = self.analyze_usage_authenticity(usage_patterns, demonstration_level)
        
        return {
            "usage_score": usage_score,
            "demonstration_score": demonstration_score,
            "effect_score": effect_score,
            "experience_score": experience_score,
            "possession_score": possession_score,
            "total_endorsement": total_endorsement
        }
    
    def extract_usage_evidence(self, text: str) -> List[str]:
        """사용 증거 추출"""
        evidence = []
        
        # 사용 패턴별 매칭된 구문 추출
        for pattern in self.endorsement_patterns.usage_patterns:
            if pattern in text.lower():
                # 패턴 주변 문맥 추출
                pattern_index = text.lower().find(pattern)
                start = max(0, pattern_index - 20)
                end = min(len(text), pattern_index + len(pattern) + 20)
                context = text[start:end].strip()
                if context and context not in evidence:
                    evidence.append(context)
        
        return evidence[:5]  # 최대 5개까지만 반환