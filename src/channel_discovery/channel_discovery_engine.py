"""
채널 탐색 엔진

PRD 요구사항에 따른 신규 채널 자동 탐색 시스템:
- 관리 대시보드에서 탐색 기간 설정하여 실행
- YouTube API를 통한 채널 검색 및 발굴
- 정밀 매칭 알고리즘으로 후보 평가
- 점수화 시스템으로 순위화
- Google Sheets 연동으로 결과 저장
"""

import logging
import asyncio
import json
import uuid
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, date, timedelta
from dataclasses import asdict
import os
from pathlib import Path

from .models import (
    ChannelCandidate, DiscoveryConfig, DiscoverySession, MatchingResult,
    ChannelType, ChannelStatus, DEFAULT_CELEBRITY_KEYWORDS, DEFAULT_MEDIA_CHANNELS
)
from .matching_algorithm import ChannelMatcher
from .scoring_system import ChannelScorer, ChannelScore
from ..youtube_api.youtube_client import YouTubeAPIClient, ChannelInfo


class YouTubeChannelSearcher:
    """YouTube API를 사용한 채널 검색기"""
    
    def __init__(self, youtube_client: YouTubeAPIClient):
        self.youtube_client = youtube_client
        self.logger = logging.getLogger(__name__)
    
    async def search_channels_by_keyword(self, keyword: str, max_results: int = 50,
                                       region_code: str = "KR") -> List[ChannelInfo]:
        """키워드로 채널 검색"""
        
        self.logger.info(f"키워드 채널 검색: '{keyword}' (최대 {max_results}개)")
        
        try:
            # YouTube Search API 사용
            def _search_channels():
                return self.youtube_client.youtube.search().list(
                    part='snippet',
                    q=keyword,
                    type='channel',
                    maxResults=min(max_results, 50),  # API 제한
                    regionCode=region_code,
                    relevanceLanguage='ko'
                ).execute()
            
            search_response = await self.youtube_client._retry_request(_search_channels)
            
            if not search_response.get('items'):
                self.logger.warning(f"키워드 '{keyword}'로 검색된 채널 없음")
                return []
            
            # 채널 ID 추출
            channel_ids = [item['snippet']['channelId'] for item in search_response['items']]
            
            # 채널 상세 정보 배치 조회
            channels_info = await self.youtube_client.batch_get_channel_info(channel_ids)
            
            self.logger.info(f"키워드 '{keyword}' 검색 완료: {len(channels_info)}개 채널")
            return channels_info
            
        except Exception as e:
            self.logger.error(f"키워드 채널 검색 실패 '{keyword}': {str(e)}")
            return []
    
    async def search_trending_channels(self, category_id: Optional[str] = None,
                                     max_results: int = 50) -> List[ChannelInfo]:
        """트렌딩 채널 검색"""
        
        self.logger.info(f"트렌딩 채널 검색 (카테고리: {category_id or 'ALL'})")
        
        try:
            # 인기 동영상 검색 후 채널 추출
            def _search_trending():
                params = {
                    'part': 'snippet',
                    'chart': 'mostPopular',
                    'maxResults': min(max_results, 50),
                    'regionCode': 'KR'
                }
                if category_id:
                    params['videoCategoryId'] = category_id
                
                return self.youtube_client.youtube.videos().list(**params).execute()
            
            trending_response = await self.youtube_client._retry_request(_search_trending)
            
            if not trending_response.get('items'):
                return []
            
            # 채널 ID 중복 제거
            channel_ids = list(set([
                item['snippet']['channelId'] 
                for item in trending_response['items']
            ]))
            
            # 채널 정보 배치 조회
            channels_info = await self.youtube_client.batch_get_channel_info(channel_ids)
            
            self.logger.info(f"트렌딩 채널 검색 완료: {len(channels_info)}개 채널")
            return channels_info
            
        except Exception as e:
            self.logger.error(f"트렌딩 채널 검색 실패: {str(e)}")
            return []
    
    async def get_related_channels(self, base_channel_id: str, max_results: int = 20) -> List[ChannelInfo]:
        """관련 채널 검색 (구독자나 시청자가 함께 보는 채널)"""
        
        self.logger.info(f"관련 채널 검색: {base_channel_id}")
        
        try:
            # 기본 채널의 최근 동영상들 가져오기
            def _get_channel_videos():
                return self.youtube_client.youtube.search().list(
                    part='snippet',
                    channelId=base_channel_id,
                    maxResults=10,
                    order='relevance',
                    type='video'
                ).execute()
            
            videos_response = await self.youtube_client._retry_request(_get_channel_videos)
            
            if not videos_response.get('items'):
                return []
            
            # 각 동영상의 관련 동영상에서 채널 추출
            related_channel_ids = set()
            
            for video in videos_response['items'][:5]:  # 최대 5개 동영상만 처리
                video_id = video['id']['videoId']
                
                # 해당 동영상과 관련된 동영상들 검색
                def _search_related():
                    return self.youtube_client.youtube.search().list(
                        part='snippet',
                        relatedToVideoId=video_id,  # deprecated, 대안 필요
                        type='video',
                        maxResults=10
                    ).execute()
                
                try:
                    # relatedToVideoId가 deprecated되어 키워드 기반 검색으로 대체
                    video_title = video['snippet']['title']
                    keywords = video_title.split()[:3]  # 제목의 첫 3단어 사용
                    
                    def _search_similar():
                        return self.youtube_client.youtube.search().list(
                            part='snippet',
                            q=' '.join(keywords),
                            type='video',
                            maxResults=10,
                            order='relevance'
                        ).execute()
                    
                    related_response = await self.youtube_client._retry_request(_search_similar)
                    
                    if related_response.get('items'):
                        for related_video in related_response['items']:
                            channel_id = related_video['snippet']['channelId']
                            if channel_id != base_channel_id:
                                related_channel_ids.add(channel_id)
                                
                except Exception as e:
                    self.logger.debug(f"관련 동영상 검색 실패: {str(e)}")
                    continue
            
            # 관련 채널 정보 조회
            if related_channel_ids:
                related_channels = await self.youtube_client.batch_get_channel_info(
                    list(related_channel_ids)[:max_results]
                )
                
                self.logger.info(f"관련 채널 검색 완료: {len(related_channels)}개 채널")
                return related_channels
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"관련 채널 검색 실패: {str(e)}")
            return []


class ChannelDiscoveryEngine:
    """채널 탐색 메인 엔진"""
    
    def __init__(self, youtube_api_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # YouTube API 클라이언트 초기화
        self.youtube_client = YouTubeAPIClient(api_key=youtube_api_key)
        self.searcher = YouTubeChannelSearcher(self.youtube_client)
        
        # 매칭 및 점수 계산기
        self.matcher = ChannelMatcher()
        self.scorer = ChannelScorer()
        
        # 세션 관리
        self.current_session: Optional[DiscoverySession] = None
        
        # 결과 저장 경로
        self.results_dir = Path("channel_discovery_results")
        self.results_dir.mkdir(exist_ok=True)
    
    def create_discovery_session(self, config: DiscoveryConfig) -> str:
        """새로운 탐색 세션 생성"""
        
        session_id = str(uuid.uuid4())
        
        self.current_session = DiscoverySession(
            session_id=session_id,
            config=config,
            started_at=datetime.now(),
            results_file_path=str(self.results_dir / f"session_{session_id}.json")
        )
        
        self.logger.info(f"새로운 탐색 세션 생성: {session_id}")
        return session_id
    
    async def discover_channels(self, config: DiscoveryConfig, 
                              progress_callback: Optional[callable] = None) -> List[ChannelCandidate]:
        """채널 탐색 실행"""
        
        session_id = self.create_discovery_session(config)
        
        try:
            self.current_session.status = "running"
            self.current_session.current_step = "초기화"
            
            if progress_callback:
                progress_callback(0, "탐색 세션 시작")
            
            # 1단계: 채널 검색
            self.current_session.current_step = "채널 검색"
            raw_channels = await self._search_channels(config, progress_callback)
            
            self.current_session.total_candidates_found = len(raw_channels)
            
            if progress_callback:
                progress_callback(30, f"채널 검색 완료: {len(raw_channels)}개")
            
            # 2단계: 중복 제거 및 필터링
            self.current_session.current_step = "필터링"
            filtered_channels = self._filter_channels(raw_channels, config)
            
            self.current_session.candidates_after_filtering = len(filtered_channels)
            
            if progress_callback:
                progress_callback(50, f"필터링 완료: {len(filtered_channels)}개")
            
            # 3단계: 매칭 분석
            self.current_session.current_step = "매칭 분석"
            matching_results = await self._analyze_matching(filtered_channels, config, progress_callback)
            
            if progress_callback:
                progress_callback(70, f"매칭 분석 완료")
            
            # 4단계: 점수 계산
            self.current_session.current_step = "점수 계산"
            candidates = await self._calculate_scores(filtered_channels, matching_results, config)
            
            if progress_callback:
                progress_callback(85, f"점수 계산 완료")
            
            # 5단계: 결과 정리
            self.current_session.current_step = "결과 정리"
            final_candidates = self._finalize_candidates(candidates, config)
            
            self.current_session.high_score_candidates = len([
                c for c in final_candidates if c.total_score >= 70
            ])
            
            # 세션 완료
            self.current_session.status = "completed"
            self.current_session.ended_at = datetime.now()
            self.current_session.progress_percentage = 100.0
            
            # 결과 저장
            await self._save_results(final_candidates)
            
            if progress_callback:
                progress_callback(100, f"탐색 완료: {len(final_candidates)}개 후보")
            
            self.logger.info(f"채널 탐색 완료: {len(final_candidates)}개 후보 발견")
            return final_candidates
            
        except Exception as e:
            self.current_session.status = "failed"
            self.current_session.error_messages.append(str(e))
            self.logger.error(f"채널 탐색 실패: {str(e)}")
            raise
    
    async def _search_channels(self, config: DiscoveryConfig, 
                             progress_callback: Optional[callable] = None) -> List[ChannelInfo]:
        """채널 검색 실행"""
        
        all_channels = []
        search_methods = config.search_methods
        
        for i, method in enumerate(search_methods):
            try:
                method_channels = []
                
                if method == "keyword_search":
                    # 키워드 기반 검색
                    for keyword in config.target_keywords:
                        channels = await self.searcher.search_channels_by_keyword(
                            keyword, config.max_results_per_query
                        )
                        method_channels.extend(channels)
                        self.current_session.queries_processed += 1
                
                elif method == "trending":
                    # 트렌딩 채널 검색
                    channels = await self.searcher.search_trending_channels(
                        max_results=config.max_results_per_query
                    )
                    method_channels.extend(channels)
                    self.current_session.queries_processed += 1
                
                elif method == "related_channels":
                    # 관련 채널 검색 (기존 채널 목록 필요)
                    base_channels = DEFAULT_MEDIA_CHANNELS[:5]  # 상위 5개 미디어 채널
                    
                    for base_channel in base_channels:
                        try:
                            # 채널명으로 ID 찾기
                            base_info = await self.youtube_client.get_channel_info(base_channel)
                            related = await self.searcher.get_related_channels(
                                base_info.channel_id, max_results=10
                            )
                            method_channels.extend(related)
                        except:
                            continue
                
                all_channels.extend(method_channels)
                
                # 진행률 업데이트
                if progress_callback:
                    progress = 10 + (i + 1) / len(search_methods) * 20
                    progress_callback(progress, f"{method} 검색 완료")
                
                self.logger.info(f"{method} 검색 완료: {len(method_channels)}개 채널")
                
            except Exception as e:
                self.logger.error(f"{method} 검색 실패: {str(e)}")
                self.current_session.processing_errors += 1
                continue
        
        # 중복 제거
        unique_channels = []
        seen_ids = set()
        
        for channel in all_channels:
            if channel.channel_id not in seen_ids:
                unique_channels.append(channel)
                seen_ids.add(channel.channel_id)
        
        return unique_channels
    
    def _filter_channels(self, channels: List[ChannelInfo], config: DiscoveryConfig) -> List[ChannelInfo]:
        """채널 필터링"""
        
        filtered = []
        
        for channel in channels:
            # 제외 채널 확인
            if channel.channel_id in config.exclude_channels:
                continue
            
            # 구독자 수 필터링
            if (channel.subscriber_count < config.min_subscriber_count or
                channel.subscriber_count > config.max_subscriber_count):
                continue
            
            # 영상 수 필터링
            if channel.video_count < config.min_video_count:
                continue
            
            # 국가 필터링
            if config.target_country and channel.country != config.target_country:
                # 국가 정보가 없으면 통과 (개인 채널의 경우 국가 정보가 없을 수 있음)
                if channel.country is not None:
                    continue
            
            # 제외 키워드 확인
            text_to_check = f"{channel.channel_name} {channel.description}".lower()
            if any(exclude_kw.lower() in text_to_check for exclude_kw in config.exclude_keywords):
                continue
            
            filtered.append(channel)
        
        self.logger.info(f"채널 필터링 완료: {len(channels)} -> {len(filtered)}")
        return filtered
    
    async def _analyze_matching(self, channels: List[ChannelInfo], config: DiscoveryConfig,
                              progress_callback: Optional[callable] = None) -> List[MatchingResult]:
        """매칭 분석 실행"""
        
        # 타겟 채널 타입 결정
        target_type = ChannelType.OTHER
        if config.target_channel_types:
            target_type = config.target_channel_types[0]
        
        # 배치 매칭 실행
        matching_results = self.matcher.batch_match_channels(
            channels, 
            config.target_keywords,
            config.target_categories,
            target_type
        )
        
        # 최소 점수 필터링
        filtered_results = [
            result for result in matching_results 
            if result.total_score >= config.min_matching_score
        ]
        
        self.logger.info(f"매칭 분석 완료: {len(matching_results)} -> {len(filtered_results)}")
        return filtered_results
    
    async def _calculate_scores(self, channels: List[ChannelInfo], 
                              matching_results: List[MatchingResult],
                              config: DiscoveryConfig) -> List[Tuple[ChannelInfo, MatchingResult, ChannelScore]]:
        """점수 계산"""
        
        results = []
        
        # 매칭 결과와 채널 정보 매핑
        matching_map = {result.channel_id: result for result in matching_results}
        
        for channel in channels:
            if channel.channel_id not in matching_map:
                continue
            
            matching_result = matching_map[channel.channel_id]
            
            # 채널 후보 객체 생성
            candidate = ChannelCandidate(
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                channel_handle=getattr(channel, 'custom_url', None),
                channel_url=f"https://www.youtube.com/channel/{channel.channel_id}",
                description=channel.description,
                subscriber_count=channel.subscriber_count,
                video_count=channel.video_count,
                view_count=channel.view_count,
                published_at=datetime.fromisoformat(channel.published_at.replace('Z', '+00:00')) if channel.published_at else None,
                thumbnail_url=channel.thumbnail_url,
                country=channel.country,
                keywords=channel.keywords or [],
                verified=channel.verified,
                discovery_method="api_search",
                discovery_query=' '.join(config.target_keywords),
                matching_scores={
                    'total': matching_result.total_score,
                    'confidence': matching_result.confidence
                }
            )
            
            # 점수 계산
            channel_score = self.scorer.calculate_channel_score(
                candidate, matching_result, channel
            )
            
            # 총 점수 업데이트
            candidate.total_score = channel_score.total_score
            
            results.append((channel, matching_result, channel_score))
        
        return results
    
    def _finalize_candidates(self, scored_results: List[Tuple[ChannelInfo, MatchingResult, ChannelScore]],
                           config: DiscoveryConfig) -> List[ChannelCandidate]:
        """최종 후보 정리"""
        
        candidates = []
        
        # 점수 순으로 정렬
        scored_results.sort(key=lambda x: x[2].total_score, reverse=True)
        
        # 최대 후보 수 제한
        limited_results = scored_results[:config.max_total_candidates]
        
        for channel, matching_result, channel_score in limited_results:
            candidate = ChannelCandidate(
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                channel_handle=getattr(channel, 'custom_url', None),
                channel_url=f"https://www.youtube.com/channel/{channel.channel_id}",
                description=channel.description,
                subscriber_count=channel.subscriber_count,
                video_count=channel.video_count,
                view_count=channel.view_count,
                published_at=datetime.fromisoformat(channel.published_at.replace('Z', '+00:00')) if channel.published_at else None,
                thumbnail_url=channel.thumbnail_url,
                country=channel.country,
                keywords=channel.keywords or [],
                verified=channel.verified,
                discovery_method="api_search",
                discovery_query=' '.join(config.target_keywords),
                matching_scores={
                    'matching': matching_result.total_score,
                    'quality': channel_score.quality_score,
                    'potential': channel_score.potential_score,
                    'monetization': channel_score.monetization_score,
                    'confidence': matching_result.confidence
                },
                total_score=channel_score.total_score,
                metadata={
                    'grade': channel_score.grade,
                    'strengths': channel_score.strengths,
                    'weaknesses': channel_score.weaknesses,
                    'score_breakdown': channel_score.score_breakdown
                }
            )
            
            candidates.append(candidate)
        
        return candidates
    
    async def _save_results(self, candidates: List[ChannelCandidate]):
        """결과 저장"""
        
        if not self.current_session:
            return
        
        # JSON 형태로 저장
        results_data = {
            'session_info': asdict(self.current_session),
            'candidates': [asdict(candidate) for candidate in candidates],
            'summary': {
                'total_candidates': len(candidates),
                'high_score_count': len([c for c in candidates if c.total_score >= 70]),
                'recommended_count': len([c for c in candidates if c.total_score >= 60]),
                'grade_distribution': {
                    grade: len([c for c in candidates if c.metadata.get('grade') == grade])
                    for grade in ['S', 'A', 'B', 'C', 'D', 'F']
                }
            }
        }
        
        # 파일 저장
        with open(self.current_session.results_file_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2, default=str)
        
        self.logger.info(f"결과 저장 완료: {self.current_session.results_file_path}")
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 상태 조회"""
        
        if self.current_session and self.current_session.session_id == session_id:
            return {
                'session_id': session_id,
                'status': self.current_session.status,
                'current_step': self.current_session.current_step,
                'progress_percentage': self.current_session.progress_percentage,
                'total_candidates_found': self.current_session.total_candidates_found,
                'high_score_candidates': self.current_session.high_score_candidates,
                'processing_errors': self.current_session.processing_errors,
                'error_messages': self.current_session.error_messages
            }
        
        return None
    
    def load_session_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """저장된 세션 결과 로드"""
        
        results_file = self.results_dir / f"session_{session_id}.json"
        
        if results_file.exists():
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"세션 결과 로드 실패: {str(e)}")
        
        return None
    
    def create_default_config(self, start_date: date = None, end_date: date = None) -> DiscoveryConfig:
        """기본 탐색 설정 생성"""
        
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        return DiscoveryConfig(
            start_date=start_date,
            end_date=end_date,
            target_keywords=DEFAULT_CELEBRITY_KEYWORDS,
            target_categories=['Entertainment', 'People & Blogs', 'Howto & Style'],
            target_channel_types=[ChannelType.CELEBRITY_PERSONAL, ChannelType.BEAUTY_INFLUENCER],
            min_subscriber_count=1000,
            max_subscriber_count=1000000,
            min_video_count=10,
            target_language="ko",
            target_country="KR",
            max_results_per_query=20,
            max_total_candidates=100,
            min_matching_score=0.3,
            search_methods=["keyword_search", "trending", "related_channels"]
        )