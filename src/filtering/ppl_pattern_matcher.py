"""
PPL 패턴 매칭 엔진

정규식, 퍼지 매칭, 형태소 분석을 활용한 유연하고 정확한 PPL 패턴 탐지 엔진
"""

import re
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
import logging

from .pattern_definitions import ppl_patterns, PPLPattern


@dataclass
class PatternMatch:
    """패턴 매칭 결과를 담는 데이터 클래스"""
    pattern: PPLPattern
    matched_text: str
    start_position: int
    end_position: int
    confidence: float
    match_type: str  # 'exact', 'fuzzy', 'regex'


class PPLPatternMatcher:
    """PPL 패턴 매칭 엔진"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: PPL 패턴 설정 파일 경로
        """
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.patterns = ppl_patterns
        self._compiled_patterns = self._compile_patterns()
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """설정 파일 로드"""
        default_config_path = "config/ppl_patterns.json"
        try:
            with open(config_path or default_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"설정 파일을 찾을 수 없습니다: {config_path or default_config_path}")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"설정 파일 파싱 오류: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """기본 설정 반환"""
        return {
            "thresholds": {
                "pattern_match_minimum": 0.7,
                "high_ppl_probability": 0.8,
                "medium_ppl_probability": 0.5,
                "low_ppl_probability": 0.2
            },
            "fuzzy_matching": {
                "enabled": True,
                "edit_distance_threshold": 2,
                "similarity_threshold": 0.8
            },
            "performance_settings": {
                "timeout_seconds": 5
            }
        }
    
    def _compile_patterns(self) -> Dict[str, List[Tuple[PPLPattern, re.Pattern]]]:
        """정규식 패턴 컴파일 - 유연한 매칭을 위한 개선"""
        compiled = {}
        
        for category, pattern_list in self.patterns.get_all_patterns().items():
            compiled[category] = []
            for pattern in pattern_list:
                try:
                    # 패턴 타입에 따른 다양한 정규식 생성
                    patterns_to_compile = []
                    
                    # 1. 정확한 매칭 (단어 경계 있음)
                    exact_pattern = rf'\b{re.escape(pattern.pattern)}\b'
                    patterns_to_compile.append(exact_pattern)
                    
                    # 2. 부분 매칭 (단어 경계 없음) - 더 유연한 매칭
                    partial_pattern = re.escape(pattern.pattern)
                    patterns_to_compile.append(partial_pattern)
                    
                    # 3. 해시태그 패턴인 경우 해시태그 없는 버전도 추가
                    if pattern.pattern.startswith('#'):
                        no_hash_pattern = rf'\b{re.escape(pattern.pattern[1:])}\b'
                        patterns_to_compile.append(no_hash_pattern)
                    
                    # 모든 패턴을 OR로 결합
                    combined_pattern = '|'.join(f'({p})' for p in patterns_to_compile)
                    compiled_regex = re.compile(combined_pattern, re.IGNORECASE)
                    compiled[category].append((pattern, compiled_regex))
                    
                except re.error as e:
                    self.logger.warning(f"정규식 컴파일 실패: {pattern.pattern}, 오류: {e}")
        
        return compiled
    
    def analyze_explicit_patterns(self, text: str) -> List[PatternMatch]:
        """명시적 PPL 패턴 분석"""
        matches = []
        
        for category in ['direct_disclosure', 'hashtag_disclosure', 'description_patterns']:
            if category in self._compiled_patterns:
                category_matches = self._find_pattern_matches(text, category)
                matches.extend(category_matches)
        
        return matches
    
    def analyze_implicit_patterns(self, text: str) -> List[PatternMatch]:
        """암시적 PPL 패턴 분석"""
        matches = []
        
        for category in ['promotional_language', 'commercial_context', 'purchase_guidance', 'timing_patterns']:
            if category in self._compiled_patterns:
                category_matches = self._find_pattern_matches(text, category)
                matches.extend(category_matches)
        
        return matches
    
    def _find_pattern_matches(self, text: str, category: str) -> List[PatternMatch]:
        """특정 카테고리의 패턴 매칭 수행 - 중복 제거 및 정확도 개선"""
        matches = []
        matched_positions = set()  # 중복 매칭 방지
        
        if category not in self._compiled_patterns:
            return matches
        
        # 패턴을 가중치 순으로 정렬하여 높은 가중치 패턴을 우선 매칭
        sorted_patterns = sorted(
            self._compiled_patterns[category],
            key=lambda x: x[0].weight,
            reverse=True
        )
        
        for pattern, compiled_regex in sorted_patterns:
            # 정확 매칭 시도
            exact_matches = self._find_exact_matches(text, pattern, compiled_regex)
            
            # 중복되지 않는 매칭만 추가
            for match in exact_matches:
                position_range = range(match.start_position, match.end_position)
                if not any(pos in matched_positions for pos in position_range):
                    matches.append(match)
                    matched_positions.update(position_range)
            
            # 퍼지 매칭 시도 (정확 매칭이 없고 설정이 활성화된 경우)
            if not exact_matches and self.config.get("fuzzy_matching", {}).get("enabled", True):
                fuzzy_matches = self._find_fuzzy_matches(text, pattern)
                for match in fuzzy_matches:
                    position_range = range(match.start_position, match.end_position)
                    if not any(pos in matched_positions for pos in position_range):
                        matches.append(match)
                        matched_positions.update(position_range)
        
        return matches
    
    def _find_exact_matches(self, text: str, pattern: PPLPattern, compiled_regex: re.Pattern) -> List[PatternMatch]:
        """정확한 패턴 매칭"""
        matches = []
        
        for match in compiled_regex.finditer(text):
            confidence = self._calculate_exact_match_confidence(pattern, match.group())
            if confidence >= self.config.get("thresholds", {}).get("pattern_match_minimum", 0.7):
                matches.append(PatternMatch(
                    pattern=pattern,
                    matched_text=match.group(),
                    start_position=match.start(),
                    end_position=match.end(),
                    confidence=confidence,
                    match_type='exact'
                ))
        
        return matches
    
    def _find_fuzzy_matches(self, text: str, pattern: PPLPattern) -> List[PatternMatch]:
        """퍼지 매칭 (유사한 패턴 탐지)"""
        matches = []
        words = text.split()
        pattern_words = pattern.pattern.split()
        
        # 단어 단위 퍼지 매칭
        for i, word in enumerate(words):
            for pattern_word in pattern_words:
                similarity = self._calculate_similarity(word.lower(), pattern_word.lower())
                
                if similarity >= self.config.get("fuzzy_matching", {}).get("similarity_threshold", 0.8):
                    confidence = self._calculate_fuzzy_match_confidence(pattern, similarity)
                    if confidence >= self.config.get("thresholds", {}).get("pattern_match_minimum", 0.7):
                        # 대략적인 위치 계산
                        start_pos = sum(len(words[j]) + 1 for j in range(i))
                        end_pos = start_pos + len(word)
                        
                        matches.append(PatternMatch(
                            pattern=pattern,
                            matched_text=word,
                            start_position=start_pos,
                            end_position=end_pos,
                            confidence=confidence,
                            match_type='fuzzy'
                        ))
        
        return matches
    
    def _find_substring_matches(self, text: str, pattern: PPLPattern) -> List[PatternMatch]:
        """부분 문자열 매칭 (더 유연한 매칭)"""
        matches = []
        pattern_text = pattern.pattern.lower()
        text_lower = text.lower()
        
        # 부분 문자열 포함 검사
        if pattern_text in text_lower:
            start_pos = text_lower.find(pattern_text)
            end_pos = start_pos + len(pattern_text)
            confidence = self._calculate_substring_match_confidence(pattern)
            
            if confidence >= self.config.get("thresholds", {}).get("pattern_match_minimum", 0.7):
                matches.append(PatternMatch(
                    pattern=pattern,
                    matched_text=text[start_pos:end_pos],
                    start_position=start_pos,
                    end_position=end_pos,
                    confidence=confidence,
                    match_type='substring'
                ))
        
        return matches
    
    def _calculate_substring_match_confidence(self, pattern: PPLPattern) -> float:
        """부분 문자열 매칭 신뢰도 계산"""
        return pattern.weight * 0.9  # 부분 문자열 매칭은 약간 낮은 신뢰도
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """두 텍스트 간 유사도 계산"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _calculate_exact_match_confidence(self, pattern: PPLPattern, matched_text: str) -> float:
        """정확 매칭의 신뢰도 계산 - 개선된 버전"""
        base_confidence = pattern.weight
        
        # 매칭된 텍스트 길이에 따른 보정
        length_factor = min(1.0, len(matched_text) / len(pattern.pattern))
        
        # 명시적 패턴에 대한 추가 보너스
        explicit_bonus = 1.1 if pattern.category in ['direct_disclosure', 'hashtag_disclosure'] else 1.0
        
        # 높은 가중치 패턴에 대한 추가 보너스
        weight_bonus = 1.05 if pattern.weight >= 0.9 else 1.0
        
        confidence = base_confidence * length_factor * explicit_bonus * weight_bonus
        return min(1.0, confidence)
    
    def _calculate_fuzzy_match_confidence(self, pattern: PPLPattern, similarity: float) -> float:
        """퍼지 매칭의 신뢰도 계산"""
        base_confidence = pattern.weight * 0.8  # 퍼지 매칭은 기본적으로 신뢰도 감소
        
        # 유사도에 따른 보정
        similarity_factor = similarity
        
        return base_confidence * similarity_factor
    
    def get_pattern_statistics(self, matches: List[PatternMatch]) -> Dict:
        """패턴 매칭 통계 생성"""
        stats = {
            'total_matches': len(matches),
            'by_category': {},
            'by_match_type': {},
            'confidence_distribution': {
                'high': 0,  # >= 0.8
                'medium': 0,  # >= 0.5
                'low': 0  # < 0.5
            }
        }
        
        for match in matches:
            # 카테고리별 통계
            category = match.pattern.category
            if category not in stats['by_category']:
                stats['by_category'][category] = 0
            stats['by_category'][category] += 1
            
            # 매칭 타입별 통계
            match_type = match.match_type
            if match_type not in stats['by_match_type']:
                stats['by_match_type'][match_type] = 0
            stats['by_match_type'][match_type] += 1
            
            # 신뢰도 분포
            if match.confidence >= 0.8:
                stats['confidence_distribution']['high'] += 1
            elif match.confidence >= 0.5:
                stats['confidence_distribution']['medium'] += 1
            else:
                stats['confidence_distribution']['low'] += 1
        
        return stats
    
    def filter_overlapping_matches(self, matches: List[PatternMatch]) -> List[PatternMatch]:
        """중복된 매칭 결과 필터링 (높은 신뢰도 우선)"""
        if not matches:
            return matches
        
        # 신뢰도 순으로 정렬 (높은 순)
        sorted_matches = sorted(matches, key=lambda x: x.confidence, reverse=True)
        filtered_matches = []
        
        for match in sorted_matches:
            # 기존 매칭과 겹치지 않는지 확인
            is_overlapping = False
            for existing_match in filtered_matches:
                if self._is_overlapping(match, existing_match):
                    is_overlapping = True
                    break
            
            if not is_overlapping:
                filtered_matches.append(match)
        
        return filtered_matches
    
    def _is_overlapping(self, match1: PatternMatch, match2: PatternMatch) -> bool:
        """두 매칭이 겹치는지 확인"""
        return not (match1.end_position <= match2.start_position or 
                   match2.end_position <= match1.start_position)