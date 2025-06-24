"""
YouTube 검색 API 통합 모듈

YouTube Data API v3를 활용한 고급 채널 검색 기능:
- 다양한 검색 전략 (키워드, 트렌드, 관련 채널)
- 검색 결과 최적화 및 필터링
- API 할당량 효율적 관리
- 검색 성능 모니터링
"""

import logging
import asyncio
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

from ..youtube_api.youtube_client import YouTubeAPIClient, ChannelInfo, YouTubeAPIError


@dataclass
class SearchStrategy:
    """검색 전략 설정"""
    name: str
    query_templates: List[str]
    filters: Dict[str, any]
    max_results: int = 50
    priority: int = 1  # 1=높음, 2=중간, 3=낮음


class AdvancedYouTubeSearcher:
    """고급 YouTube 채널 검색기"""
    
    def __init__(self, youtube_client: YouTubeAPIClient):
        self.youtube_client = youtube_client
        self.logger = logging.getLogger(__name__)
        
        # 검색 전략 정의
        self.search_strategies = self._initialize_search_strategies()
        
        # 검색 성능 통계
        self.search_stats = {
            'queries_executed': 0,
            'channels_found': 0,
            'api_calls_made': 0,
            'errors_encountered': 0,
            'average_response_time': 0.0
        }
    
    def _initialize_search_strategies(self) -> List[SearchStrategy]:
        """검색 전략 초기화"""
        
        strategies = [
            # 1. 연예인 개인 채널 검색
            SearchStrategy(
                name="celebrity_personal",
                query_templates=[
                    "{celebrity_name}",
                    "{celebrity_name} 공식",
                    "{celebrity_name} official",
                    "{celebrity_name} vlog",
                    "{celebrity_name} 일상"
                ],
                filters={
                    'type': 'channel',
                    'relevanceLanguage': 'ko',
                    'regionCode': 'KR'
                },
                max_results=20,
                priority=1
            ),
            
            # 2. 뷰티 인플루언서 검색
            SearchStrategy(
                name="beauty_influencer",
                query_templates=[
                    "뷰티 유튜버",
                    "메이크업 아티스트",
                    "화장품 리뷰",
                    "스킨케어 루틴",
                    "뷰티 크리에이터",
                    "코스메틱 추천"
                ],
                filters={
                    'type': 'channel',
                    'relevanceLanguage': 'ko',
                    'regionCode': 'KR',
                    'order': 'relevance'
                },
                max_results=30,
                priority=1
            ),
            
            # 3. 패션 인플루언서 검색
            SearchStrategy(
                name="fashion_influencer",
                query_templates=[
                    "패션 유튜버",
                    "스타일리스트",
                    "옷 코디",
                    "패션 하울",
                    "룩북",
                    "스타일링"
                ],
                filters={
                    'type': 'channel',
                    'relevanceLanguage': 'ko',
                    'regionCode': 'KR',
                    'order': 'relevance'
                },
                max_results=30,
                priority=1
            ),
            
            # 4. 라이프스타일 채널 검색
            SearchStrategy(
                name="lifestyle",
                query_templates=[
                    "라이프스타일 vlog",
                    "일상 브이로그",
                    "데일리 루틴",
                    "힐링 영상",
                    "소확행"
                ],
                filters={
                    'type': 'channel',
                    'relevanceLanguage': 'ko',
                    'regionCode': 'KR',
                    'order': 'relevance'
                },
                max_results=25,
                priority=2
            ),
            
            # 5. 미디어 채널 검색
            SearchStrategy(
                name="media_channels",
                query_templates=[
                    "연예인 인터뷰",
                    "셀럽 화보",
                    "매거진 채널",
                    "엔터테인먼트 뉴스",
                    "스타 인터뷰"
                ],
                filters={
                    'type': 'channel',
                    'relevanceLanguage': 'ko',
                    'regionCode': 'KR',
                    'order': 'relevance'
                },
                max_results=20,
                priority=2
            ),
            
            # 6. 트렌딩 채널 검색
            SearchStrategy(
                name="trending",
                query_templates=[
                    "인기 유튜버",
                    "구독자 많은 채널",
                    "화제의 크리에이터",
                    "신인 유튜버"
                ],
                filters={
                    'type': 'channel',
                    'relevanceLanguage': 'ko',
                    'regionCode': 'KR',
                    'order': 'viewCount'
                },
                max_results=15,
                priority=3
            )
        ]
        
        return strategies
    
    async def comprehensive_channel_search(self, target_keywords: List[str],
                                         celebrity_names: List[str] = None,
                                         max_total_results: int = 200) -> List[ChannelInfo]:
        """종합적인 채널 검색"""
        
        self.logger.info(f"종합 채널 검색 시작: 키워드 {len(target_keywords)}개")
        
        all_channels = []
        channel_ids_seen = set()
        
        # 우선순위별로 검색 전략 실행
        strategies_by_priority = sorted(self.search_strategies, key=lambda x: x.priority)
        
        for strategy in strategies_by_priority:
            if len(all_channels) >= max_total_results:
                break
            
            try:
                strategy_channels = await self._execute_search_strategy(
                    strategy, target_keywords, celebrity_names
                )
                
                # 중복 제거
                for channel in strategy_channels:
                    if (channel.channel_id not in channel_ids_seen and 
                        len(all_channels) < max_total_results):
                        all_channels.append(channel)
                        channel_ids_seen.add(channel.channel_id)
                
                self.logger.info(f"전략 '{strategy.name}' 완료: {len(strategy_channels)}개 채널")
                
            except Exception as e:
                self.logger.error(f"검색 전략 '{strategy.name}' 실패: {str(e)}")
                self.search_stats['errors_encountered'] += 1
                continue
        
        self.search_stats['channels_found'] = len(all_channels)
        
        self.logger.info(f"종합 채널 검색 완료: {len(all_channels)}개 채널 발견")
        return all_channels
    
    async def _execute_search_strategy(self, strategy: SearchStrategy,
                                     target_keywords: List[str],
                                     celebrity_names: List[str] = None) -> List[ChannelInfo]:
        """개별 검색 전략 실행"""
        
        channels = []
        
        # 쿼리 생성
        queries = self._generate_queries(strategy, target_keywords, celebrity_names)
        
        for query in queries:
            try:
                start_time = datetime.now()
                
                # YouTube 검색 실행
                search_channels = await self._search_channels_with_filters(
                    query, strategy.filters, strategy.max_results // len(queries)
                )
                
                channels.extend(search_channels)
                
                # 성능 통계 업데이트
                response_time = (datetime.now() - start_time).total_seconds()
                self._update_search_stats(response_time)
                
                # API 할당량 관리를 위한 지연
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.warning(f"쿼리 '{query}' 검색 실패: {str(e)}")
                continue
        
        return channels
    
    def _generate_queries(self, strategy: SearchStrategy, target_keywords: List[str],
                         celebrity_names: List[str] = None) -> List[str]:
        """검색 쿼리 생성"""
        
        queries = []
        
        # 기본 쿼리 템플릿 사용
        for template in strategy.query_templates:
            if "{celebrity_name}" in template and celebrity_names:
                # 연예인 이름 기반 쿼리
                for name in celebrity_names[:5]:  # 최대 5명만 처리
                    query = template.format(celebrity_name=name)
                    queries.append(query)
            else:
                # 일반 쿼리
                queries.append(template)
        
        # 타겟 키워드와 조합
        for keyword in target_keywords[:3]:  # 상위 3개 키워드만
            if len(queries) < 10:  # 쿼리 수 제한
                queries.append(keyword)
        
        return queries[:10]  # 최대 10개 쿼리
    
    async def _search_channels_with_filters(self, query: str, filters: Dict[str, any],
                                          max_results: int) -> List[ChannelInfo]:
        """필터 적용된 채널 검색"""
        
        try:
            # YouTube Search API 파라미터 구성
            search_params = {
                'part': 'snippet',
                'q': query,
                'maxResults': min(max_results, 50),  # API 제한
                **filters
            }
            
            # API 요청 실행
            def _search_request():
                return self.youtube_client.youtube.search().list(**search_params).execute()
            
            search_response = await self.youtube_client._retry_request(_search_request)
            
            if not search_response.get('items'):
                return []
            
            # 채널 ID 추출
            channel_ids = []
            for item in search_response['items']:
                if item['id'].get('kind') == 'youtube#channel':
                    channel_ids.append(item['id']['channelId'])
                elif 'channelId' in item['snippet']:
                    channel_ids.append(item['snippet']['channelId'])
            
            if not channel_ids:
                return []
            
            # 채널 상세 정보 조회
            channels = await self.youtube_client.batch_get_channel_info(channel_ids)
            
            self.search_stats['queries_executed'] += 1
            self.search_stats['api_calls_made'] += 2  # search + channels
            
            return channels
            
        except YouTubeAPIError as e:
            self.logger.error(f"YouTube API 검색 실패: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"채널 검색 실패: {str(e)}")
            return []
    
    def _update_search_stats(self, response_time: float):
        """검색 통계 업데이트"""
        
        # 평균 응답 시간 계산
        total_time = (self.search_stats['average_response_time'] * 
                     self.search_stats['queries_executed'] + response_time)
        self.search_stats['queries_executed'] += 1
        self.search_stats['average_response_time'] = total_time / self.search_stats['queries_executed']
    
    async def search_related_channels_advanced(self, base_channel_ids: List[str],
                                             similarity_threshold: float = 0.3) -> List[ChannelInfo]:
        """고급 관련 채널 검색"""
        
        self.logger.info(f"고급 관련 채널 검색: {len(base_channel_ids)}개 기준 채널")
        
        all_related = []
        channel_ids_seen = set(base_channel_ids)  # 기준 채널 제외
        
        for base_channel_id in base_channel_ids:
            try:
                # 기준 채널 정보 조회
                base_channel = await self.youtube_client.get_channel_info(base_channel_id)
                
                # 키워드 기반 유사 채널 검색
                related_channels = await self._find_similar_channels_by_keywords(
                    base_channel, similarity_threshold
                )
                
                # 중복 제거
                for channel in related_channels:
                    if channel.channel_id not in channel_ids_seen:
                        all_related.append(channel)
                        channel_ids_seen.add(channel.channel_id)
                
                # API 할당량 관리
                await asyncio.sleep(0.2)
                
            except Exception as e:
                self.logger.warning(f"관련 채널 검색 실패 {base_channel_id}: {str(e)}")
                continue
        
        self.logger.info(f"고급 관련 채널 검색 완료: {len(all_related)}개 발견")
        return all_related
    
    async def _find_similar_channels_by_keywords(self, base_channel: ChannelInfo,
                                               similarity_threshold: float) -> List[ChannelInfo]:
        """키워드 기반 유사 채널 검색"""
        
        # 기준 채널의 키워드 추출
        search_keywords = []
        
        if base_channel.keywords:
            search_keywords.extend(base_channel.keywords[:3])
        
        # 채널명에서 키워드 추출
        name_keywords = self._extract_keywords_from_text(base_channel.channel_name)
        search_keywords.extend(name_keywords[:2])
        
        # 설명에서 키워드 추출
        if base_channel.description:
            desc_keywords = self._extract_keywords_from_text(base_channel.description)
            search_keywords.extend(desc_keywords[:2])
        
        if not search_keywords:
            return []
        
        # 유사 채널 검색
        similar_channels = []
        
        for keyword in search_keywords[:5]:  # 최대 5개 키워드
            try:
                channels = await self._search_channels_with_filters(
                    keyword,
                    {
                        'type': 'channel',
                        'relevanceLanguage': 'ko',
                        'regionCode': 'KR',
                        'order': 'relevance'
                    },
                    10
                )
                
                similar_channels.extend(channels)
                
            except Exception as e:
                self.logger.debug(f"키워드 '{keyword}' 검색 실패: {str(e)}")
                continue
        
        return similar_channels
    
    def _extract_keywords_from_text(self, text: str, max_keywords: int = 5) -> List[str]:
        """텍스트에서 키워드 추출"""
        
        if not text:
            return []
        
        # 한글, 영문 단어만 추출
        words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text.lower())
        
        # 불용어 제거
        stop_words = {
            '공식', 'official', '채널', 'channel', '유튜브', 'youtube',
            '구독', 'subscribe', '좋아요', 'like', '영상', 'video'
        }
        
        keywords = [word for word in words if word not in stop_words]
        
        # 빈도 기반 정렬 (간단한 구현)
        keyword_count = {}
        for keyword in keywords:
            keyword_count[keyword] = keyword_count.get(keyword, 0) + 1
        
        sorted_keywords = sorted(keyword_count.keys(), 
                               key=lambda x: keyword_count[x], reverse=True)
        
        return sorted_keywords[:max_keywords]
    
    async def search_trending_channels_by_category(self, categories: List[str] = None) -> List[ChannelInfo]:
        """카테고리별 트렌딩 채널 검색"""
        
        if not categories:
            categories = ['22', '24', '26']  # Entertainment, Music, Howto & Style
        
        self.logger.info(f"카테고리별 트렌딩 채널 검색: {len(categories)}개 카테고리")
        
        trending_channels = []
        channel_ids_seen = set()
        
        for category_id in categories:
            try:
                # 해당 카테고리의 인기 동영상 검색
                def _get_trending_videos():
                    return self.youtube_client.youtube.videos().list(
                        part='snippet',
                        chart='mostPopular',
                        maxResults=50,
                        regionCode='KR',
                        videoCategoryId=category_id
                    ).execute()
                
                trending_response = await self.youtube_client._retry_request(_get_trending_videos)
                
                if trending_response.get('items'):
                    # 채널 ID 추출
                    category_channel_ids = []
                    for video in trending_response['items']:
                        channel_id = video['snippet']['channelId']
                        if channel_id not in channel_ids_seen:
                            category_channel_ids.append(channel_id)
                            channel_ids_seen.add(channel_id)
                    
                    # 채널 정보 조회
                    if category_channel_ids:
                        channels = await self.youtube_client.batch_get_channel_info(
                            category_channel_ids[:20]  # 카테고리당 최대 20개
                        )
                        trending_channels.extend(channels)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.warning(f"카테고리 {category_id} 트렌딩 검색 실패: {str(e)}")
                continue
        
        self.logger.info(f"트렌딩 채널 검색 완료: {len(trending_channels)}개 발견")
        return trending_channels
    
    def get_search_performance_stats(self) -> Dict[str, any]:
        """검색 성능 통계 반환"""
        
        return {
            **self.search_stats,
            'efficiency_ratio': (
                self.search_stats['channels_found'] / max(self.search_stats['api_calls_made'], 1)
            ),
            'error_rate': (
                self.search_stats['errors_encountered'] / 
                max(self.search_stats['queries_executed'], 1) * 100
            )
        }
    
    def reset_search_stats(self):
        """검색 통계 초기화"""
        
        self.search_stats = {
            'queries_executed': 0,
            'channels_found': 0,
            'api_calls_made': 0,
            'errors_encountered': 0,
            'average_response_time': 0.0
        }