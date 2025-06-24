"""
신규 채널 탐색 시스템

PRD 2.1 요구사항에 따른 신규 채널 자동 탐색 및 평가 시스템
- 정밀 매칭 알고리즘 (핸들, 설명, 제목 등 다중 신호 기반)
- 점수화 시스템으로 후보 채널 평가 및 순위화
- Google Sheets 연동으로 검토 목록 자동 추가
"""

from .channel_discovery_engine import ChannelDiscoveryEngine
from .matching_algorithm import ChannelMatcher
from .scoring_system import ChannelScorer
from .models import (
    ChannelCandidate, DiscoveryConfig, MatchingResult, 
    ChannelType, ChannelStatus, DEFAULT_CELEBRITY_KEYWORDS
)

__all__ = [
    'ChannelDiscoveryEngine',
    'ChannelMatcher', 
    'ChannelScorer',
    'ChannelCandidate',
    'DiscoveryConfig',
    'MatchingResult',
    'ChannelType',
    'ChannelStatus',
    'DEFAULT_CELEBRITY_KEYWORDS'
]