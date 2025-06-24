"""
정밀 채널 매칭 알고리즘

PRD 요구사항에 따른 다중 신호 기반 채널 매칭:
- 핸들명 유사도 분석
- 설명 텍스트 관련성 분석
- 제목 패턴 매칭
- 키워드 매칭
- 카테고리 적합성 분석
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import math

# 텍스트 유사도 계산용
from difflib import SequenceMatcher
import unicodedata

from .models import ChannelCandidate, MatchingResult, ChannelType, ScoringWeights
from ..youtube_api.youtube_client import ChannelInfo


class TextSimilarity:
    """텍스트 유사도 계산 유틸리티"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """텍스트 정규화 (한글, 영문 처리)"""
        if not text:
            return ""
        
        # 유니코드 정규화
        text = unicodedata.normalize('NFKC', text)
        
        # 소문자 변환
        text = text.lower()
        
        # 특수문자 제거 (한글, 영문, 숫자, 공백만 남김)
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        
        # 연속 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
        """자카드 유사도 계산"""
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def sequence_similarity(text1: str, text2: str) -> float:
        """시퀀스 매칭 유사도"""
        if not text1 or not text2:
            return 0.0
        
        normalized1 = TextSimilarity.normalize_text(text1)
        normalized2 = TextSimilarity.normalize_text(text2)
        
        return SequenceMatcher(None, normalized1, normalized2).ratio()
    
    @staticmethod
    def token_overlap_ratio(text1: str, text2: str) -> float:
        """토큰 중복 비율 계산"""
        if not text1 or not text2:
            return 0.0
        
        tokens1 = set(TextSimilarity.normalize_text(text1).split())
        tokens2 = set(TextSimilarity.normalize_text(text2).split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        return len(tokens1.intersection(tokens2)) / min(len(tokens1), len(tokens2))
    
    @staticmethod
    def korean_jamo_similarity(text1: str, text2: str) -> float:
        """한글 자모 단위 유사도 (초성 검색 등)"""
        if not text1 or not text2:
            return 0.0
        
        # 간단한 초성 추출 (ㄱ-ㅎ)
        def extract_chosung(text):
            chosung_map = {
                'ㄱ': 'ㄱ', 'ㄲ': 'ㄱ', 'ㄴ': 'ㄴ', 'ㄷ': 'ㄷ', 'ㄸ': 'ㄷ',
                'ㄹ': 'ㄹ', 'ㅁ': 'ㅁ', 'ㅂ': 'ㅂ', 'ㅃ': 'ㅂ', 'ㅅ': 'ㅅ',
                'ㅆ': 'ㅅ', 'ㅇ': 'ㅇ', 'ㅈ': 'ㅈ', 'ㅉ': 'ㅈ', 'ㅊ': 'ㅊ',
                'ㅋ': 'ㅋ', 'ㅌ': 'ㅌ', 'ㅍ': 'ㅍ', 'ㅎ': 'ㅎ'
            }
            
            chosung = ""
            for char in text:
                if '가' <= char <= '힣':
                    # 한글 유니코드에서 초성 추출
                    chosung_index = (ord(char) - ord('가')) // 588
                    chosung_char = chr(ord('ㄱ') + chosung_index)
                    chosung += chosung_map.get(chosung_char, chosung_char)
                elif char in chosung_map.values():
                    chosung += char
            
            return chosung
        
        chosung1 = extract_chosung(text1)
        chosung2 = extract_chosung(text2)
        
        return TextSimilarity.sequence_similarity(chosung1, chosung2)


class KeywordMatcher:
    """키워드 매칭 엔진"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 연예인 관련 키워드 패턴
        self.celebrity_patterns = [
            r'(배우|가수|아이돌|연예인|셀럽|스타)',
            r'(뷰티|메이크업|화장|스킨케어)',
            r'(패션|스타일|코디|옷|룩)',
            r'(일상|브이로그|vlog|데일리)',
            r'(추천|리뷰|사용후기|픽)',
            r'(루틴|모닝|나이트)'
        ]
        
        # 미디어 채널 패턴
        self.media_patterns = [
            r'(보그|vogue|엘르|elle|마리끌레르)',
            r'(하퍼스바자|코스모폴리탄|얼루어)',
            r'(더블유|w|그라치아|marie claire)',
            r'(인터뷰|화보|매거진|팝)'
        ]
        
        # 영향력 지표 키워드
        self.influence_keywords = [
            '인플루언서', '크리에이터', '유튜버', '블로거',
            '모델', '배우', '가수', '아이돌', '연예인',
            '뷰티구루', '스타일리스트', '에디터'
        ]
    
    def extract_keywords(self, text: str) -> Set[str]:
        """텍스트에서 키워드 추출"""
        if not text:
            return set()
        
        # 텍스트 정규화
        normalized = TextSimilarity.normalize_text(text)
        
        # 단어 단위로 분할
        words = set(normalized.split())
        
        # 2-gram, 3-gram 추가
        tokens = normalized.split()
        for i in range(len(tokens) - 1):
            words.add(' '.join(tokens[i:i+2]))
        for i in range(len(tokens) - 2):
            words.add(' '.join(tokens[i:i+3]))
        
        return words
    
    def match_celebrity_patterns(self, text: str) -> Tuple[float, List[str]]:
        """연예인 관련 패턴 매칭"""
        if not text:
            return 0.0, []
        
        normalized = TextSimilarity.normalize_text(text)
        matches = []
        total_score = 0.0
        
        for pattern in self.celebrity_patterns:
            matches_found = re.findall(pattern, normalized)
            if matches_found:
                matches.extend(matches_found)
                # 패턴별 가중치 적용
                total_score += len(matches_found) * 0.2
        
        # 정규화 (0-1 범위)
        total_score = min(total_score, 1.0)
        
        return total_score, matches
    
    def match_media_patterns(self, text: str) -> Tuple[float, List[str]]:
        """미디어 채널 패턴 매칭"""
        if not text:
            return 0.0, []
        
        normalized = TextSimilarity.normalize_text(text)
        matches = []
        total_score = 0.0
        
        for pattern in self.media_patterns:
            matches_found = re.findall(pattern, normalized)
            if matches_found:
                matches.extend(matches_found)
                total_score += len(matches_found) * 0.3
        
        total_score = min(total_score, 1.0)
        
        return total_score, matches
    
    def calculate_keyword_relevance(self, text: str, target_keywords: List[str]) -> float:
        """타겟 키워드와의 관련성 계산"""
        if not text or not target_keywords:
            return 0.0
        
        text_keywords = self.extract_keywords(text)
        target_set = set(TextSimilarity.normalize_text(kw) for kw in target_keywords)
        
        # 직접 매칭
        direct_matches = len(text_keywords.intersection(target_set))
        
        # 유사 매칭 (편집 거리 기반)
        similar_matches = 0
        for text_kw in text_keywords:
            for target_kw in target_set:
                if TextSimilarity.sequence_similarity(text_kw, target_kw) > 0.8:
                    similar_matches += 1
                    break
        
        total_matches = direct_matches + similar_matches * 0.7
        max_possible = len(target_set)
        
        return min(total_matches / max_possible, 1.0) if max_possible > 0 else 0.0


class ChannelMatcher:
    """채널 매칭 메인 클래스"""
    
    def __init__(self, scoring_weights: Optional[ScoringWeights] = None):
        self.logger = logging.getLogger(__name__)
        self.text_similarity = TextSimilarity()
        self.keyword_matcher = KeywordMatcher()
        self.weights = scoring_weights or ScoringWeights()
        
        # 카테고리 매핑
        self.category_mapping = {
            'Entertainment': ['연예인', '셀럽', '엔터테인먼트'],
            'People & Blogs': ['개인', '블로그', '일상', 'vlog'],
            'Howto & Style': ['뷰티', '패션', '스타일', '메이크업'],
            'Education': ['교육', '튜토리얼', '강의'],
            'Music': ['음악', '가수', '뮤직'],
            'Film & Animation': ['영화', '애니메이션']
        }
    
    def analyze_channel_handle(self, handle: str, target_keywords: List[str]) -> float:
        """채널 핸들명 분석"""
        if not handle:
            return 0.0
        
        # 핸들에서 특수문자 제거 후 분석
        clean_handle = re.sub(r'[@#]', '', handle)
        
        # 타겟 키워드와 유사도 계산
        keyword_scores = []
        for keyword in target_keywords:
            similarity = self.text_similarity.sequence_similarity(clean_handle, keyword)
            keyword_scores.append(similarity)
        
        # 연예인 패턴 매칭
        celebrity_score, _ = self.keyword_matcher.match_celebrity_patterns(clean_handle)
        
        # 종합 점수
        max_keyword_score = max(keyword_scores) if keyword_scores else 0.0
        final_score = (max_keyword_score * 0.7) + (celebrity_score * 0.3)
        
        return min(final_score, 1.0)
    
    def analyze_channel_description(self, description: str, target_keywords: List[str]) -> Tuple[float, Dict[str, float]]:
        """채널 설명 분석"""
        if not description:
            return 0.0, {}
        
        details = {}
        
        # 키워드 관련성
        keyword_relevance = self.keyword_matcher.calculate_keyword_relevance(description, target_keywords)
        details['keyword_relevance'] = keyword_relevance
        
        # 연예인 패턴 매칭
        celebrity_score, celebrity_matches = self.keyword_matcher.match_celebrity_patterns(description)
        details['celebrity_patterns'] = celebrity_score
        details['celebrity_matches'] = celebrity_matches
        
        # 미디어 패턴 매칭
        media_score, media_matches = self.keyword_matcher.match_media_patterns(description)
        details['media_patterns'] = media_score
        details['media_matches'] = media_matches
        
        # 영향력 지표 분석
        influence_keywords = self.keyword_matcher.influence_keywords
        influence_score = self.keyword_matcher.calculate_keyword_relevance(description, influence_keywords)
        details['influence_indicators'] = influence_score
        
        # 종합 점수 계산
        final_score = (
            keyword_relevance * 0.4 +
            celebrity_score * 0.3 +
            media_score * 0.2 +
            influence_score * 0.1
        )
        
        return min(final_score, 1.0), details
    
    def analyze_content_quality(self, channel_info: ChannelInfo) -> float:
        """채널 콘텐츠 품질 분석"""
        score = 0.0
        
        # 구독자 수 기반 점수 (로그 스케일)
        if channel_info.subscriber_count > 0:
            # 1K~1M 구독자를 0.1~1.0으로 매핑
            log_subs = math.log10(max(channel_info.subscriber_count, 1000))
            subscriber_score = min((log_subs - 3) / 3, 1.0)  # 3=log10(1000), 6=log10(1000000)
            score += subscriber_score * 0.4
        
        # 영상 수 기반 활성도
        if channel_info.video_count > 0:
            # 10~1000개 영상을 0.1~1.0으로 매핑
            video_score = min(math.log10(max(channel_info.video_count, 10)) / 3, 1.0)
            score += video_score * 0.3
        
        # 채널 연령 (오래된 채널일수록 신뢰도 높음)
        if channel_info.published_at:
            try:
                published_date = datetime.fromisoformat(channel_info.published_at.replace('Z', '+00:00'))
                days_old = (datetime.now().replace(tzinfo=None) - published_date.replace(tzinfo=None)).days
                age_score = min(days_old / 365, 1.0)  # 1년 이상이면 만점
                score += age_score * 0.2
            except:
                pass
        
        # 인증 여부
        if channel_info.verified:
            score += 0.1
        
        return min(score, 1.0)
    
    def analyze_audience_fit(self, channel_info: ChannelInfo, target_channel_type: ChannelType) -> float:
        """타겟 오디언스 적합성 분석"""
        score = 0.0
        
        # 국가 매칭
        if channel_info.country == 'KR':
            score += 0.3
        
        # 키워드 매칭
        if channel_info.keywords:
            target_keywords_by_type = {
                ChannelType.CELEBRITY_PERSONAL: ['연예인', '셀럽', '배우', '가수', '아이돌'],
                ChannelType.BEAUTY_INFLUENCER: ['뷰티', '메이크업', '화장', '스킨케어'],
                ChannelType.FASHION_INFLUENCER: ['패션', '스타일', '코디', '옷'],
                ChannelType.LIFESTYLE_INFLUENCER: ['라이프스타일', '일상', 'vlog', '브이로그'],
                ChannelType.MEDIA_CHANNEL: ['매거진', '미디어', '인터뷰', '화보']
            }
            
            target_keywords = target_keywords_by_type.get(target_channel_type, [])
            if target_keywords:
                keyword_match = self.keyword_matcher.calculate_keyword_relevance(
                    ' '.join(channel_info.keywords), target_keywords
                )
                score += keyword_match * 0.5
        
        # 설명 텍스트 분석
        if channel_info.description:
            description_keywords = ['한국', '코리아', 'korea', 'korean']
            korea_relevance = self.keyword_matcher.calculate_keyword_relevance(
                channel_info.description, description_keywords
            )
            score += korea_relevance * 0.2
        
        return min(score, 1.0)
    
    def calculate_category_match(self, channel_category: str, target_categories: List[str]) -> float:
        """카테고리 매칭 점수 계산"""
        if not channel_category or not target_categories:
            return 0.0
        
        # 직접 매칭
        if channel_category in target_categories:
            return 1.0
        
        # 카테고리 매핑을 통한 매칭
        for target_cat in target_categories:
            if target_cat in self.category_mapping.get(channel_category, []):
                return 0.8
        
        return 0.0
    
    def match_channel(self, channel_info: ChannelInfo, target_keywords: List[str], 
                     target_categories: List[str] = None,
                     target_channel_type: ChannelType = ChannelType.OTHER) -> MatchingResult:
        """채널 종합 매칭 분석"""
        start_time = datetime.now()
        
        # 개별 점수 계산
        handle_score = self.analyze_channel_handle(
            channel_info.channel_name, target_keywords
        )
        
        description_score, desc_details = self.analyze_channel_description(
            channel_info.description, target_keywords
        )
        
        # 채널명 키워드 매칭
        name_keywords = self.keyword_matcher.extract_keywords(channel_info.channel_name)
        target_set = set(TextSimilarity.normalize_text(kw) for kw in target_keywords)
        keyword_match_score = self.text_similarity.jaccard_similarity(name_keywords, target_set)
        
        # 카테고리 매칭 (YouTube API에서 category_id 필요)
        category_score = self.calculate_category_match("", target_categories or [])
        
        # 콘텐츠 품질
        content_quality_score = self.analyze_content_quality(channel_info)
        
        # 오디언스 적합성
        audience_fit_score = self.analyze_audience_fit(channel_info, target_channel_type)
        
        # 가중 평균으로 종합 점수 계산
        total_score = (
            handle_score * self.weights.handle_match_weight +
            description_score * self.weights.description_relevance_weight +
            keyword_match_score * self.weights.keyword_match_weight +
            category_score * self.weights.category_match_weight +
            content_quality_score * self.weights.content_quality_weight +
            audience_fit_score * self.weights.audience_fit_weight
        )
        
        # 신뢰도 계산 (정보 완성도 기반)
        confidence_factors = [
            1.0 if channel_info.description else 0.0,
            1.0 if channel_info.subscriber_count > 1000 else 0.5,
            1.0 if channel_info.video_count > 10 else 0.5,
            1.0 if channel_info.verified else 0.0
        ]
        confidence = sum(confidence_factors) / len(confidence_factors)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # 매칭된 키워드 추출
        matched_keywords = []
        for keyword in target_keywords:
            if keyword.lower() in channel_info.description.lower():
                matched_keywords.append(keyword)
            elif keyword.lower() in channel_info.channel_name.lower():
                matched_keywords.append(keyword)
        
        return MatchingResult(
            channel_id=channel_info.channel_id,
            query=' '.join(target_keywords),
            method="comprehensive_matching",
            name_similarity=self.text_similarity.sequence_similarity(
                channel_info.channel_name, ' '.join(target_keywords)
            ),
            description_relevance=description_score,
            keyword_match=keyword_match_score,
            category_match=category_score,
            handle_match=handle_score,
            content_quality=content_quality_score,
            audience_fit=audience_fit_score,
            total_score=total_score,
            confidence=confidence,
            matched_keywords=matched_keywords,
            matched_phrases=desc_details.get('celebrity_matches', []) + 
                           desc_details.get('media_matches', []),
            similarity_details=desc_details,
            processing_time_ms=int(processing_time)
        )
    
    def batch_match_channels(self, channels: List[ChannelInfo], target_keywords: List[str],
                           target_categories: List[str] = None,
                           target_channel_type: ChannelType = ChannelType.OTHER) -> List[MatchingResult]:
        """여러 채널 배치 매칭"""
        results = []
        
        self.logger.info(f"배치 채널 매칭 시작: {len(channels)}개 채널")
        
        for i, channel in enumerate(channels):
            try:
                result = self.match_channel(
                    channel, target_keywords, target_categories, target_channel_type
                )
                results.append(result)
                
                if (i + 1) % 10 == 0:
                    self.logger.info(f"매칭 진행률: {i + 1}/{len(channels)}")
                    
            except Exception as e:
                self.logger.error(f"채널 매칭 실패 {channel.channel_id}: {str(e)}")
                continue
        
        # 점수 순으로 정렬
        results.sort(key=lambda x: x.total_score, reverse=True)
        
        self.logger.info(f"배치 매칭 완료: {len(results)}개 결과")
        return results