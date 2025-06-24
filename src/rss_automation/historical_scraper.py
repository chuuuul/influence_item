"""
과거 영상 수집기 (Playwright 기반)

PRD 2.2 요구사항:
- 운영자가 관리 대시보드에서 채널 및 분석 기간을 선택하여 과거 영상 수집
- Playwright 웹 스크래핑을 통한 YouTube 채널 페이지 크롤링
- 선택된 기간 내의 모든 영상 정보 수집
"""

import asyncio
import sqlite3
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError

from .content_filter import ContentFilter


@dataclass
class ScrapingConfig:
    """스크래핑 설정"""
    headless: bool = True
    timeout: int = 30000  # 30초
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    max_videos_per_channel: int = 500
    scroll_delay: float = 2.0
    click_delay: float = 1.0


@dataclass
class ScrapingResult:
    """스크래핑 결과"""
    channel_id: str
    channel_name: str
    success: bool
    total_found: int
    collected_count: int
    filtered_count: int
    error_count: int
    errors: List[str]
    execution_time: float
    date_range: Tuple[datetime, datetime]


@dataclass
class VideoMetadata:
    """스크래핑된 비디오 메타데이터"""
    video_id: str
    title: str
    url: str
    thumbnail_url: str
    upload_date: datetime
    view_count: Optional[int] = None
    duration: Optional[str] = None
    description: Optional[str] = None


class HistoricalScraper:
    """과거 영상 수집기"""
    
    def __init__(self, db_path: str = "influence_item.db", config: Optional[ScrapingConfig] = None):
        self.db_path = db_path
        self.config = config or ScrapingConfig()
        self.logger = logging.getLogger(__name__)
        self.content_filter = ContentFilter()
        self._setup_database()
    
    def _setup_database(self) -> None:
        """데이터베이스 테이블 설정"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 스크래핑 작업 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraping_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
                    total_found INTEGER DEFAULT 0,
                    collected_count INTEGER DEFAULT 0,
                    filtered_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    error_messages TEXT,  -- JSON array
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 스크래핑된 비디오 메타데이터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraped_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT,
                    url TEXT,
                    thumbnail_url TEXT,
                    upload_date DATE,
                    view_count INTEGER,
                    duration TEXT,
                    description TEXT,
                    scraping_status TEXT DEFAULT 'scraped' CHECK (scraping_status IN ('scraped', 'processed', 'filtered')),
                    filter_reason TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES scraping_jobs (job_id),
                    UNIQUE(job_id, video_id)
                )
            """)
            
            conn.commit()
    
    async def create_scraping_job(self, channel_id: str, channel_name: str, 
                                start_date: datetime, end_date: datetime) -> str:
        """스크래핑 작업 생성"""
        job_id = f"scrape_{channel_id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{int(datetime.now().timestamp())}"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scraping_jobs 
                    (job_id, channel_id, channel_name, start_date, end_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (job_id, channel_id, channel_name, start_date.date(), end_date.date()))
                conn.commit()
                
                self.logger.info(f"스크래핑 작업 생성됨: {job_id}")
                return job_id
                
        except Exception as e:
            self.logger.error(f"스크래핑 작업 생성 실패: {str(e)}")
            raise
    
    async def scrape_channel_videos(self, channel_id: str, channel_name: str,
                                  start_date: datetime, end_date: datetime) -> ScrapingResult:
        """채널의 과거 영상 스크래핑"""
        job_id = await self.create_scraping_job(channel_id, channel_name, start_date, end_date)
        start_time = datetime.now()
        
        result = ScrapingResult(
            channel_id=channel_id,
            channel_name=channel_name,
            success=False,
            total_found=0,
            collected_count=0,
            filtered_count=0,
            error_count=0,
            errors=[],
            execution_time=0.0,
            date_range=(start_date, end_date)
        )
        
        try:
            # 작업 상태를 running으로 업데이트
            await self._update_job_status(job_id, 'running', started_at=start_time)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.config.headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                context = await browser.new_context(
                    viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
                    user_agent=self.config.user_agent
                )
                
                page = await context.new_page()
                
                try:
                    # YouTube 채널 페이지 접속
                    channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
                    self.logger.info(f"채널 페이지 접속: {channel_url}")
                    
                    await page.goto(channel_url, timeout=self.config.timeout)
                    await page.wait_for_load_state('networkidle', timeout=self.config.timeout)
                    
                    # 동의 팝업 처리
                    await self._handle_consent_popup(page)
                    
                    # 비디오 리스트 로드
                    videos = await self._load_channel_videos(page, start_date, end_date)
                    result.total_found = len(videos)
                    
                    self.logger.info(f"총 {len(videos)}개 비디오 발견")
                    
                    # 각 비디오 처리
                    for video in videos:
                        try:
                            # 필터링 검사
                            filter_result = self.content_filter.comprehensive_filter(
                                video.title, video.description or "", "personal"
                            )
                            
                            if filter_result.passed:
                                # 비디오 저장
                                await self._save_scraped_video(job_id, video, 'scraped')
                                result.collected_count += 1
                            else:
                                # 필터링된 비디오 저장
                                await self._save_scraped_video(job_id, video, 'filtered', filter_result.reason)
                                result.filtered_count += 1
                                
                        except Exception as e:
                            error_msg = f"비디오 처리 실패 {video.video_id}: {str(e)}"
                            self.logger.error(error_msg)
                            result.errors.append(error_msg)
                            result.error_count += 1
                    
                    result.success = True
                    
                except Exception as e:
                    error_msg = f"스크래핑 실행 실패: {str(e)}"
                    self.logger.error(error_msg)
                    result.errors.append(error_msg)
                    result.error_count += 1
                
                finally:
                    await browser.close()
            
            # 실행 시간 계산
            result.execution_time = (datetime.now() - start_time).total_seconds()
            
            # 작업 완료 상태 업데이트
            status = 'completed' if result.success else 'failed'
            await self._update_job_status(
                job_id, status, 
                completed_at=datetime.now(),
                total_found=result.total_found,
                collected_count=result.collected_count,
                filtered_count=result.filtered_count,
                error_count=result.error_count,
                error_messages=result.errors
            )
            
            self.logger.info(
                f"스크래핑 완료: {channel_name} - "
                f"수집 {result.collected_count}개, 필터링 {result.filtered_count}개, "
                f"오류 {result.error_count}개"
            )
            
        except Exception as e:
            error_msg = f"스크래핑 작업 실패: {str(e)}"
            self.logger.error(error_msg)
            result.errors.append(error_msg)
            result.execution_time = (datetime.now() - start_time).total_seconds()
            
            # 실패 상태 업데이트
            await self._update_job_status(job_id, 'failed', error_messages=result.errors)
        
        return result
    
    async def _handle_consent_popup(self, page: Page) -> None:
        """YouTube 동의 팝업 처리"""
        try:
            # 동의 버튼 찾기 및 클릭
            consent_selectors = [
                'button[aria-label*="Accept"]',
                'button[aria-label*="Accept all"]',
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                '#yDmH0d button:has-text("Accept")',
                'button[jsname="V67aGc"]'
            ]
            
            for selector in consent_selectors:
                try:
                    consent_button = await page.wait_for_selector(selector, timeout=3000)
                    if consent_button:
                        await consent_button.click()
                        await page.wait_for_timeout(2000)
                        self.logger.info("동의 팝업 처리됨")
                        return
                except PlaywrightTimeoutError:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"동의 팝업 처리 중 오류 (무시): {str(e)}")
    
    async def _load_channel_videos(self, page: Page, start_date: datetime, 
                                 end_date: datetime) -> List[VideoMetadata]:
        """채널의 비디오 목록 로드"""
        videos = []
        previous_count = 0
        no_new_videos_count = 0
        max_scrolls = 50  # 최대 스크롤 횟수
        
        try:
            # 초기 비디오 로드 대기
            await page.wait_for_selector('div#contents', timeout=self.config.timeout)
            await page.wait_for_timeout(3000)
            
            for scroll_count in range(max_scrolls):
                try:
                    # 현재 페이지의 비디오 정보 추출
                    current_videos = await self._extract_video_info(page)
                    
                    # 새로운 비디오 추가
                    for video in current_videos:
                        if video.video_id not in [v.video_id for v in videos]:
                            # 날짜 범위 체크
                            if start_date <= video.upload_date <= end_date:
                                videos.append(video)
                            elif video.upload_date < start_date:
                                # 더 오래된 비디오에 도달하면 스크롤 중단
                                self.logger.info(f"날짜 범위를 벗어난 비디오에 도달: {video.upload_date}")
                                return videos
                    
                    # 진행 상황 확인
                    current_count = len(videos)
                    if current_count == previous_count:
                        no_new_videos_count += 1
                        if no_new_videos_count >= 3:  # 3번 연속 새 비디오가 없으면 중단
                            self.logger.info("더 이상 새로운 비디오가 없음")
                            break
                    else:
                        no_new_videos_count = 0
                        previous_count = current_count
                    
                    # 최대 비디오 수 확인
                    if len(videos) >= self.config.max_videos_per_channel:
                        self.logger.info(f"최대 비디오 수에 도달: {len(videos)}")
                        break
                    
                    # 페이지 스크롤
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(int(self.config.scroll_delay * 1000))
                    
                    # 로딩 확인
                    await page.wait_for_load_state('networkidle', timeout=5000)
                    
                    if scroll_count % 10 == 0:
                        self.logger.info(f"스크롤 진행: {scroll_count}회, 발견된 비디오: {len(videos)}개")
                
                except PlaywrightTimeoutError:
                    self.logger.warning(f"스크롤 {scroll_count}에서 타임아웃")
                    continue
                except Exception as e:
                    self.logger.error(f"스크롤 중 오류: {str(e)}")
                    break
            
            self.logger.info(f"총 {len(videos)}개 비디오 로드 완료")
            
        except Exception as e:
            self.logger.error(f"비디오 로드 실패: {str(e)}")
        
        return videos
    
    async def _extract_video_info(self, page: Page) -> List[VideoMetadata]:
        """페이지에서 비디오 정보 추출"""
        videos = []
        
        try:
            # 비디오 컨테이너 선택자들
            video_selectors = [
                'div#contents ytd-rich-item-renderer',
                'div#contents ytd-grid-video-renderer',
                'div#contents ytd-video-renderer'
            ]
            
            video_elements = []
            for selector in video_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    video_elements = elements
                    break
            
            if not video_elements:
                self.logger.warning("비디오 요소를 찾을 수 없음")
                return videos
            
            for element in video_elements:
                try:
                    video_info = await self._extract_single_video_info(element)
                    if video_info:
                        videos.append(video_info)
                except Exception as e:
                    self.logger.debug(f"단일 비디오 정보 추출 실패: {str(e)}")
                    continue
            
        except Exception as e:
            self.logger.error(f"비디오 정보 추출 실패: {str(e)}")
        
        return videos
    
    async def _extract_single_video_info(self, element) -> Optional[VideoMetadata]:
        """단일 비디오 정보 추출"""
        try:
            # 제목과 URL 추출
            title_element = await element.query_selector('a#video-title')
            if not title_element:
                title_element = await element.query_selector('h3 a')
            
            if not title_element:
                return None
            
            title = await title_element.get_attribute('title')
            if not title:
                title = await title_element.inner_text()
            
            url = await title_element.get_attribute('href')
            if not url:
                return None
            
            # 비디오 ID 추출
            video_id = self._extract_video_id_from_url(url)
            if not video_id:
                return None
            
            # 전체 URL 생성
            if url.startswith('/'):
                url = f"https://www.youtube.com{url}"
            
            # 썸네일 URL 추출
            thumbnail_element = await element.query_selector('img')
            thumbnail_url = None
            if thumbnail_element:
                thumbnail_url = await thumbnail_element.get_attribute('src')
                if not thumbnail_url:
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            
            # 업로드 날짜 추출
            upload_date = await self._extract_upload_date(element)
            if not upload_date:
                upload_date = datetime.now()  # 기본값
            
            # 조회수 추출
            view_count = await self._extract_view_count(element)
            
            # 비디오 길이 추출
            duration = await self._extract_duration(element)
            
            return VideoMetadata(
                video_id=video_id,
                title=title.strip(),
                url=url,
                thumbnail_url=thumbnail_url,
                upload_date=upload_date,
                view_count=view_count,
                duration=duration
            )
            
        except Exception as e:
            self.logger.debug(f"비디오 정보 추출 실패: {str(e)}")
            return None
    
    def _extract_video_id_from_url(self, url: str) -> Optional[str]:
        """URL에서 비디오 ID 추출"""
        try:
            patterns = [
                r'watch\?v=([^&]+)',
                r'/v/([^?]+)',
                r'/embed/([^?]+)',
                r'youtu\.be/([^?]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
        except Exception:
            return None
    
    async def _extract_upload_date(self, element) -> Optional[datetime]:
        """업로드 날짜 추출"""
        try:
            # 메타데이터에서 날짜 찾기
            date_selectors = [
                'div#metadata-line span:nth-child(2)',
                'span.style-scope.ytd-video-meta-block:nth-child(2)',
                'div.ytd-video-meta-block span:last-child'
            ]
            
            for selector in date_selectors:
                date_element = await element.query_selector(selector)
                if date_element:
                    date_text = await date_element.inner_text()
                    parsed_date = self._parse_relative_date(date_text.strip())
                    if parsed_date:
                        return parsed_date
            
            return None
        except Exception:
            return None
    
    def _parse_relative_date(self, date_text: str) -> Optional[datetime]:
        """상대적 날짜 텍스트를 datetime으로 변환"""
        try:
            now = datetime.now()
            date_text = date_text.lower()
            
            # 시간 단위별 매핑
            if 'minute' in date_text or '분' in date_text:
                minutes = int(re.search(r'(\d+)', date_text).group(1))
                return now - timedelta(minutes=minutes)
            elif 'hour' in date_text or '시간' in date_text:
                hours = int(re.search(r'(\d+)', date_text).group(1))
                return now - timedelta(hours=hours)
            elif 'day' in date_text or '일' in date_text:
                days = int(re.search(r'(\d+)', date_text).group(1))
                return now - timedelta(days=days)
            elif 'week' in date_text or '주' in date_text:
                weeks = int(re.search(r'(\d+)', date_text).group(1))
                return now - timedelta(weeks=weeks)
            elif 'month' in date_text or '개월' in date_text:
                months = int(re.search(r'(\d+)', date_text).group(1))
                return now - timedelta(days=months * 30)
            elif 'year' in date_text or '년' in date_text:
                years = int(re.search(r'(\d+)', date_text).group(1))
                return now - timedelta(days=years * 365)
            
            return None
        except Exception:
            return None
    
    async def _extract_view_count(self, element) -> Optional[int]:
        """조회수 추출"""
        try:
            view_selectors = [
                'div#metadata-line span:first-child',
                'span.style-scope.ytd-video-meta-block:first-child'
            ]
            
            for selector in view_selectors:
                view_element = await element.query_selector(selector)
                if view_element:
                    view_text = await view_element.inner_text()
                    return self._parse_view_count(view_text)
            
            return None
        except Exception:
            return None
    
    def _parse_view_count(self, view_text: str) -> Optional[int]:
        """조회수 텍스트를 숫자로 변환"""
        try:
            # 숫자와 단위 추출
            view_text = view_text.lower().replace(',', '').replace(' ', '')
            match = re.search(r'([\d.]+)([kmb])?', view_text)
            
            if match:
                number = float(match.group(1))
                unit = match.group(2)
                
                if unit == 'k':
                    return int(number * 1000)
                elif unit == 'm':
                    return int(number * 1000000)
                elif unit == 'b':
                    return int(number * 1000000000)
                else:
                    return int(number)
            
            return None
        except Exception:
            return None
    
    async def _extract_duration(self, element) -> Optional[str]:
        """비디오 길이 추출"""
        try:
            duration_selectors = [
                'span.ytd-thumbnail-overlay-time-status-renderer',
                'div.ytd-thumbnail-overlay-time-status-renderer'
            ]
            
            for selector in duration_selectors:
                duration_element = await element.query_selector(selector)
                if duration_element:
                    duration_text = await duration_element.inner_text()
                    return duration_text.strip()
            
            return None
        except Exception:
            return None
    
    async def _save_scraped_video(self, job_id: str, video: VideoMetadata, 
                                status: str, filter_reason: Optional[str] = None) -> None:
        """스크래핑된 비디오 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO scraped_videos
                    (job_id, video_id, title, url, thumbnail_url, upload_date, 
                     view_count, duration, description, scraping_status, filter_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id, video.video_id, video.title, video.url, video.thumbnail_url,
                    video.upload_date.date(), video.view_count, video.duration,
                    video.description, status, filter_reason
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"스크래핑된 비디오 저장 실패: {str(e)}")
    
    async def _update_job_status(self, job_id: str, status: str, **kwargs) -> None:
        """작업 상태 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 업데이트할 필드들 준비
                fields = ['status = ?']
                values = [status]
                
                for key, value in kwargs.items():
                    if value is not None:
                        if key == 'error_messages' and isinstance(value, list):
                            fields.append(f'{key} = ?')
                            values.append(json.dumps(value))
                        elif key in ['started_at', 'completed_at'] and isinstance(value, datetime):
                            fields.append(f'{key} = ?')
                            values.append(value.isoformat())
                        else:
                            fields.append(f'{key} = ?')
                            values.append(value)
                
                values.append(job_id)
                
                query = f"UPDATE scraping_jobs SET {', '.join(fields)} WHERE job_id = ?"
                cursor.execute(query, values)
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"작업 상태 업데이트 실패: {str(e)}")
    
    def get_scraping_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """스크래핑 작업 목록 조회"""
        jobs = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT job_id, channel_id, channel_name, start_date, end_date,
                           status, total_found, collected_count, filtered_count, 
                           error_count, started_at, completed_at, created_at
                    FROM scraping_jobs
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                
                for row in cursor.fetchall():
                    jobs.append({
                        'job_id': row[0],
                        'channel_id': row[1],
                        'channel_name': row[2],
                        'start_date': row[3],
                        'end_date': row[4],
                        'status': row[5],
                        'total_found': row[6],
                        'collected_count': row[7],
                        'filtered_count': row[8],
                        'error_count': row[9],
                        'started_at': row[10],
                        'completed_at': row[11],
                        'created_at': row[12]
                    })
                    
        except Exception as e:
            self.logger.error(f"스크래핑 작업 조회 실패: {str(e)}")
        
        return jobs
    
    def get_scraped_videos(self, job_id: str) -> List[Dict[str, Any]]:
        """특정 작업의 스크래핑된 비디오 목록 조회"""
        videos = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT video_id, title, url, thumbnail_url, upload_date,
                           view_count, duration, scraping_status, filter_reason
                    FROM scraped_videos
                    WHERE job_id = ?
                    ORDER BY upload_date DESC
                """, (job_id,))
                
                for row in cursor.fetchall():
                    videos.append({
                        'video_id': row[0],
                        'title': row[1],
                        'url': row[2],
                        'thumbnail_url': row[3],
                        'upload_date': row[4],
                        'view_count': row[5],
                        'duration': row[6],
                        'status': row[7],
                        'filter_reason': row[8]
                    })
                    
        except Exception as e:
            self.logger.error(f"스크래핑된 비디오 조회 실패: {str(e)}")
        
        return videos