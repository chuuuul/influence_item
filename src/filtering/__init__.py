"""
PPL 필터링 모듈

연예인 YouTube 콘텐츠에서 PPL(Product Placement) 탐지 및 분석을 위한 모듈
"""

from .pattern_definitions import ppl_patterns, PPLPattern
from .ppl_pattern_matcher import PPLPatternMatcher, PatternMatch
from .pattern_scorer import PatternScorer, PPLScore

__version__ = "1.0.0"
__all__ = [
    "ppl_patterns",
    "PPLPattern", 
    "PPLPatternMatcher",
    "PatternMatch",
    "PatternScorer",
    "PPLScore"
]