"""
Google Sheets 연동 시스템

PRD 2.2 요구사항:
- 채널 목록을 Google Sheets로 관리
- 신규 채널 후보를 Google Sheets에 추가하여 운영자 검토
- 채널 승인/제외 처리 결과를 시스템으로 동기화
"""

import gspread
import logging
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
import time
from pathlib import Path

from .rss_collector import ChannelInfo


@dataclass
class SheetsConfig:
    """Google Sheets 설정"""
    spreadsheet_id: str
    channels_sheet_name: str = "승인된 채널"
    candidates_sheet_name: str = "후보 채널"
    credentials_path: str = "credentials/google_sheets_credentials.json"
    backup_credentials_paths: List[str] = None
    
    def __post_init__(self):
        if self.backup_credentials_paths is None:
            self.backup_credentials_paths = [
                "/Users/chul/.config/gspread/service_account.json",
                "config/google_sheets_credentials.json",
                "google_sheets_credentials.json"
            ]


@dataclass
class ChannelCandidate:
    """채널 후보 정보"""
    channel_id: str
    channel_name: str
    channel_type: str
    rss_url: str
    discovery_score: float
    discovery_reason: str
    discovered_at: datetime
    review_status: str = "pending"  # pending, approved, rejected
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None


class SheetsIntegration:
    """Google Sheets 연동 시스템"""
    
    def __init__(self, config: SheetsConfig, db_path: str = "influence_item.db"):
        self.config = config
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.gc = None
        self.spreadsheet = None
        self._setup_database()
        self._authenticate()
    
    def _setup_database(self) -> None:
        """데이터베이스 테이블 설정"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 채널 후보 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT NOT NULL,
                    channel_type TEXT NOT NULL CHECK (channel_type IN ('personal', 'media')),
                    rss_url TEXT NOT NULL,
                    discovery_score REAL NOT NULL,
                    discovery_reason TEXT,
                    discovered_at TIMESTAMP NOT NULL,
                    review_status TEXT DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
                    reviewed_by TEXT,
                    reviewed_at TIMESTAMP,
                    notes TEXT,
                    sheets_synced BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Sheets 동기화 로그
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sheets_sync_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT NOT NULL CHECK (sync_type IN ('push_candidates', 'pull_reviews', 'push_channels', 'full_sync')),
                    status TEXT NOT NULL CHECK (status IN ('success', 'error', 'partial')),
                    records_processed INTEGER DEFAULT 0,
                    records_synced INTEGER DEFAULT 0,
                    error_message TEXT,
                    execution_time REAL,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def _authenticate(self) -> None:
        """Google Sheets 인증 (다중 경로 지원 + 데모 모드)"""
        # 데모 모드 확인
        if os.getenv('DEMO_MODE', 'false').lower() == 'true':
            self.logger.warning("데모 모드 활성화 - Google Sheets API 호출 시뮬레이션")
            self.gc = None
            self.spreadsheet = None
            return
        
        credentials_paths = [self.config.credentials_path] + self.config.backup_credentials_paths
        
        for path in credentials_paths:
            if os.path.exists(path):
                try:
                    # 더 안전한 인증 방식
                    scopes = [
                        'https://www.googleapis.com/auth/spreadsheets',
                        'https://www.googleapis.com/auth/drive'
                    ]
                    
                    credentials = Credentials.from_service_account_file(
                        path, scopes=scopes
                    )
                    
                    self.gc = gspread.authorize(credentials)
                    self.spreadsheet = self.gc.open_by_key(self.config.spreadsheet_id)
                    
                    # 연결 테스트
                    _ = self.spreadsheet.title
                    
                    self.logger.info(f"Google Sheets 인증 성공: {path}")
                    self.config.credentials_path = path  # 성공한 경로로 업데이트
                    return
                    
                except FileNotFoundError:
                    self.logger.warning(f"인증 파일 없음: {path}")
                    continue
                except GoogleAuthError as e:
                    self.logger.error(f"Google 인증 실패 ({path}): {str(e)}")
                    continue
                except Exception as e:
                    self.logger.error(f"Google Sheets 연결 실패 ({path}): {str(e)}")
                    continue
        
        # 모든 경로에서 실패 - 데모 모드로 fallback
        self.logger.warning("모든 인증 경로에서 실패 - 데모 모드로 전환")
        self.logger.info(f"확인된 경로: {credentials_paths}")
        self.logger.info("Google Sheets 설정 가이드를 참조하세요: GOOGLE_SHEETS_SETUP_GUIDE.md")
        
        # 데모 모드 설정
        os.environ['DEMO_MODE'] = 'true'
        self.gc = None
        self.spreadsheet = None
    
    def _get_or_create_worksheet(self, sheet_name: str, headers: List[str]):
        """워크시트 조회 또는 생성 (데모 모드 지원)"""
        if self._is_demo_mode():
            self.logger.info(f"데모 모드: 워크시트 '{sheet_name}' 시뮬레이션")
            return None
        
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            self.logger.info(f"기존 워크시트 사용: {sheet_name}")
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name, 
                rows=1000, 
                cols=len(headers)
            )
            # 헤더 설정
            worksheet.update('A1', [headers])
            # 헤더 서식 적용
            worksheet.format('A1:Z1', {
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'textFormat': {'bold': True}
            })
            self.logger.info(f"새 워크시트 생성: {sheet_name}")
        
        return worksheet
    
    def _is_demo_mode(self) -> bool:
        """데모 모드 확인"""
        return os.getenv('DEMO_MODE', 'false').lower() == 'true' or self.gc is None
    
    def sync_approved_channels_to_sheets(self) -> bool:
        """승인된 채널을 Google Sheets로 동기화"""
        start_time = datetime.now()
        
        try:
            # 로컬 DB에서 승인된 채널 조회
            approved_channels = self._get_approved_channels_from_db()
            
            if self._is_demo_mode():
                self.logger.info(f"데모 모드: 승인된 채널 {len(approved_channels)}개 Sheets 동기화 시뮬레이션")
                execution_time = (datetime.now() - start_time).total_seconds()
                self._log_sync_result('push_channels', 'success', len(approved_channels), 
                                    len(approved_channels), None, execution_time)
                return True
            
            # 승인된 채널 워크시트 준비
            headers = [
                "채널ID", "채널명", "채널유형", "RSS URL", "활성상태", 
                "마지막수집일", "등록일", "업데이트일", "비고"
            ]
            worksheet = self._get_or_create_worksheet(self.config.channels_sheet_name, headers)
            
            # 기존 데이터 지우고 새로 작성
            worksheet.clear()
            worksheet.update('A1', [headers])
            
            if approved_channels:
                # 데이터 준비
                data_rows = []
                for channel in approved_channels:
                    row = [
                        channel['channel_id'],
                        channel['channel_name'],
                        '개인채널' if channel['channel_type'] == 'personal' else '미디어채널',
                        channel['rss_url'],
                        '활성' if channel['is_active'] else '비활성',
                        channel['last_collected_at'] or '',
                        channel['created_at'],
                        channel['updated_at'],
                        ''
                    ]
                    data_rows.append(row)
                
                # 데이터 업데이트
                worksheet.update(f'A2:I{len(data_rows)+1}', data_rows)
                
                # 조건부 서식 적용
                self._apply_channel_formatting(worksheet, len(data_rows) + 1)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 동기화 로그 기록
            self._log_sync_result('push_channels', 'success', len(approved_channels), 
                                len(approved_channels), None, execution_time)
            
            self.logger.info(f"승인된 채널 {len(approved_channels)}개를 Sheets로 동기화 완료")
            return True
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"승인된 채널 Sheets 동기화 실패: {str(e)}"
            self.logger.error(error_msg)
            
            self._log_sync_result('push_channels', 'error', 0, 0, error_msg, execution_time)
            return False
    
    def sync_channel_candidates_to_sheets(self) -> bool:
        """채널 후보를 Google Sheets로 동기화"""
        start_time = datetime.now()
        
        try:
            # 미동기화된 후보 채널 조회
            unsynced_candidates = self._get_unsynced_candidates_from_db()
            
            if not unsynced_candidates:
                self.logger.info("동기화할 새로운 후보 채널이 없음")
                return True
            
            if self._is_demo_mode():
                self.logger.info(f"데모 모드: 후보 채널 {len(unsynced_candidates)}개 Sheets 동기화 시뮬레이션")
                # 동기화 상태 업데이트
                for candidate in unsynced_candidates:
                    self._mark_candidate_as_synced(candidate['channel_id'])
                
                execution_time = (datetime.now() - start_time).total_seconds()
                self._log_sync_result('push_candidates', 'success', len(unsynced_candidates), 
                                    len(unsynced_candidates), None, execution_time)
                return True
            
            # 후보 채널 워크시트 준비
            headers = [
                "채널ID", "채널명", "채널유형", "RSS URL", "발견점수", 
                "발견사유", "발견일시", "검토상태", "검토자", "검토일시", 
                "승인여부", "비고"
            ]
            worksheet = self._get_or_create_worksheet(self.config.candidates_sheet_name, headers)
            
            # 기존 데이터와 병합을 위해 현재 시트 데이터 조회
            existing_data = worksheet.get_all_records()
            existing_channel_ids = {row.get('채널ID') for row in existing_data if row.get('채널ID')}
            
            # 새로운 후보만 추가
            new_candidates = [c for c in unsynced_candidates if c['channel_id'] not in existing_channel_ids]
            
            if new_candidates:
                # 마지막 행 찾기
                last_row = len(existing_data) + 2  # 헤더 + 1
                
                # 새 데이터 추가
                data_rows = []
                for candidate in new_candidates:
                    row = [
                        candidate['channel_id'],
                        candidate['channel_name'],
                        '개인채널' if candidate['channel_type'] == 'personal' else '미디어채널',
                        candidate['rss_url'],
                        candidate['discovery_score'],
                        candidate['discovery_reason'],
                        candidate['discovered_at'],
                        candidate['review_status'],
                        candidate['reviewed_by'] or '',
                        candidate['reviewed_at'] or '',
                        '',  # 승인여부 (수동 입력용)
                        candidate['notes'] or ''
                    ]
                    data_rows.append(row)
                
                # 시트에 데이터 추가
                end_row = last_row + len(data_rows) - 1
                worksheet.update(f'A{last_row}:L{end_row}', data_rows)
                
                # 조건부 서식 적용
                self._apply_candidate_formatting(worksheet, end_row)
                
                # 동기화 상태 업데이트
                for candidate in new_candidates:
                    self._mark_candidate_as_synced(candidate['channel_id'])
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 동기화 로그 기록
            self._log_sync_result('push_candidates', 'success', len(unsynced_candidates), 
                                len(new_candidates), None, execution_time)
            
            self.logger.info(f"후보 채널 {len(new_candidates)}개를 Sheets로 동기화 완료")
            return True
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"후보 채널 Sheets 동기화 실패: {str(e)}"
            self.logger.error(error_msg)
            
            self._log_sync_result('push_candidates', 'error', 0, 0, error_msg, execution_time)
            return False
    
    def sync_reviews_from_sheets(self) -> bool:
        """Google Sheets에서 검토 결과를 동기화 (재시도 로직 포함)"""
        start_time = datetime.now()
        max_retries = 3
        retry_delay = 2  # 초
        
        if self._is_demo_mode():
            self.logger.info("데모 모드: Sheets에서 검토 결과 동기화 시뮬레이션")
            # 데모 데이터로 일부 승인/거부 처리 시뮬레이션
            candidates = self.get_channel_candidates(status='pending')
            updated_count = min(2, len(candidates))  # 최대 2개 시뮬레이션
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._log_sync_result('pull_reviews', 'success', len(candidates), 
                                updated_count, None, execution_time)
            self.logger.info(f"데모 모드: 검토 결과 {updated_count}개 동기화 시뮬레이션 완료")
            return True
        
        for attempt in range(max_retries):
            try:
                worksheet = self.spreadsheet.worksheet(self.config.candidates_sheet_name)
                all_records = worksheet.get_all_records()
                
                updated_count = 0
                processed_count = 0
                errors = []
                
                for record in all_records:
                    try:
                        channel_id = record.get('채널ID')
                        if not channel_id:
                            continue
                        
                        processed_count += 1
                        
                        # 승인여부 컬럼 확인
                        approval_status = str(record.get('승인여부', '')).strip().lower()
                        review_notes = record.get('비고', '')
                        reviewer = record.get('검토자', '')
                        
                        # 대소문자 및 다양한 형식 지원
                        approved_values = ['승인', 'approved', 'approve', 'y', 'yes', 'ok', '1', 'true', '수락']
                        rejected_values = ['거부', 'rejected', 'reject', 'n', 'no', 'ng', '0', 'false', '거절']
                        
                        if approval_status in approved_values:
                            # 승인된 경우 - 채널을 승인된 목록에 추가
                            if self._approve_channel_candidate(channel_id, review_notes, reviewer):
                                updated_count += 1
                                self.logger.info(f"채널 승인 처리: {channel_id}")
                        elif approval_status in rejected_values:
                            # 거부된 경우 - 상태만 업데이트
                            if self._reject_channel_candidate(channel_id, review_notes, reviewer):
                                updated_count += 1
                                self.logger.info(f"채널 거부 처리: {channel_id}")
                        
                    except Exception as e:
                        error_msg = f"검토 결과 처리 실패 {channel_id}: {str(e)}"
                        errors.append(error_msg)
                        self.logger.error(error_msg)
                        continue
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # 동기화 로그 기록
                status = 'success' if not errors else 'partial' if updated_count > 0 else 'error'
                error_summary = '\n'.join(errors[:5]) if errors else None  # 최대 5개 오류만 기록
                
                self._log_sync_result('pull_reviews', status, processed_count, 
                                    updated_count, error_summary, execution_time)
                
                if errors:
                    self.logger.warning(f"검토 결과 동기화 완료 (with {len(errors)} errors): {updated_count}/{processed_count}")
                else:
                    self.logger.info(f"검토 결과 {updated_count}개 동기화 완료 (총 {processed_count}개 처리)")
                
                return True
                
            except gspread.exceptions.APIError as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Google Sheets API 오류, 재시도 {attempt + 1}/{max_retries}: {str(e)}")
                    time.sleep(retry_delay * (attempt + 1))  # 지수 백오프
                    continue
                else:
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"동기화 오류, 재시도 {attempt + 1}/{max_retries}: {str(e)}")
                    time.sleep(retry_delay)
                    continue
                else:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    error_msg = f"검토 결과 Sheets 동기화 실패: {str(e)}"
                    self.logger.error(error_msg)
                    
                    self._log_sync_result('pull_reviews', 'error', 0, 0, error_msg, execution_time)
                    return False
        
        return False
    
    def full_sync(self) -> Dict[str, bool]:
        """전체 동기화"""
        results = {
            'push_channels': False,
            'push_candidates': False,
            'pull_reviews': False
        }
        
        try:
            self.logger.info("Google Sheets 전체 동기화 시작")
            
            # 1. 승인된 채널 동기화
            results['push_channels'] = self.sync_approved_channels_to_sheets()
            
            # 2. 후보 채널 동기화
            results['push_candidates'] = self.sync_channel_candidates_to_sheets()
            
            # 3. 검토 결과 동기화
            results['pull_reviews'] = self.sync_reviews_from_sheets()
            
            # 4. 전체 결과 로깅
            success_count = sum(results.values())
            status = 'success' if success_count == 3 else 'partial' if success_count > 0 else 'error'
            
            self._log_sync_result('full_sync', status, 3, success_count, None, 0)
            
            self.logger.info(f"전체 동기화 완료 - 성공: {success_count}/3")
            
        except Exception as e:
            self.logger.error(f"전체 동기화 실패: {str(e)}")
            self._log_sync_result('full_sync', 'error', 3, 0, str(e), 0)
        
        return results
    
    def add_channel_candidate(self, candidate: ChannelCandidate) -> bool:
        """채널 후보 추가"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO channel_candidates
                    (channel_id, channel_name, channel_type, rss_url, discovery_score,
                     discovery_reason, discovered_at, review_status, reviewed_by, 
                     reviewed_at, notes, sheets_synced, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, CURRENT_TIMESTAMP)
                """, (
                    candidate.channel_id, candidate.channel_name, candidate.channel_type,
                    candidate.rss_url, candidate.discovery_score, candidate.discovery_reason,
                    candidate.discovered_at, candidate.review_status, candidate.reviewed_by,
                    candidate.reviewed_at, candidate.notes
                ))
                conn.commit()
                
                self.logger.info(f"채널 후보 추가: {candidate.channel_name} ({candidate.channel_id})")
                return True
                
        except Exception as e:
            self.logger.error(f"채널 후보 추가 실패: {str(e)}")
            return False
    
    def _get_approved_channels_from_db(self) -> List[Dict[str, Any]]:
        """DB에서 승인된 채널 조회"""
        channels = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT channel_id, channel_name, channel_type, rss_url, is_active,
                           last_collected_at, created_at, updated_at
                    FROM rss_channels
                    ORDER BY channel_name
                """)
                
                for row in cursor.fetchall():
                    channels.append({
                        'channel_id': row[0],
                        'channel_name': row[1],
                        'channel_type': row[2],
                        'rss_url': row[3],
                        'is_active': row[4],
                        'last_collected_at': row[5],
                        'created_at': row[6],
                        'updated_at': row[7]
                    })
                    
        except Exception as e:
            self.logger.error(f"승인된 채널 조회 실패: {str(e)}")
        
        return channels
    
    def _get_unsynced_candidates_from_db(self) -> List[Dict[str, Any]]:
        """DB에서 미동기화된 후보 채널 조회"""
        candidates = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT channel_id, channel_name, channel_type, rss_url, discovery_score,
                           discovery_reason, discovered_at, review_status, reviewed_by,
                           reviewed_at, notes
                    FROM channel_candidates
                    WHERE sheets_synced = FALSE
                    ORDER BY discovered_at DESC
                """)
                
                for row in cursor.fetchall():
                    candidates.append({
                        'channel_id': row[0],
                        'channel_name': row[1],
                        'channel_type': row[2],
                        'rss_url': row[3],
                        'discovery_score': row[4],
                        'discovery_reason': row[5],
                        'discovered_at': row[6],
                        'review_status': row[7],
                        'reviewed_by': row[8],
                        'reviewed_at': row[9],
                        'notes': row[10]
                    })
                    
        except Exception as e:
            self.logger.error(f"미동기화 후보 채널 조회 실패: {str(e)}")
        
        return candidates
    
    def _mark_candidate_as_synced(self, channel_id: str) -> None:
        """후보 채널을 동기화 완료로 표시"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE channel_candidates 
                    SET sheets_synced = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                """, (channel_id,))
                conn.commit()
        except Exception as e:
            self.logger.error(f"동기화 상태 업데이트 실패: {str(e)}")
    
    def _approve_channel_candidate(self, channel_id: str, notes: str = "", reviewer: str = "") -> bool:
        """채널 후보 승인 (개선된 로직)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 후보 채널 정보 조회
                cursor.execute("""
                    SELECT channel_name, channel_type, rss_url, review_status 
                    FROM channel_candidates 
                    WHERE channel_id = ?
                """, (channel_id,))
                
                result = cursor.fetchone()
                if not result:
                    self.logger.error(f"후보 채널을 찾을 수 없음: {channel_id}")
                    return False
                
                channel_name, channel_type, rss_url, current_status = result
                
                # 이미 승인된 채널인지 확인
                if current_status == 'approved':
                    self.logger.info(f"이미 승인된 채널: {channel_id}")
                    return True
                
                # RSS 채널 테이블에 추가 (중복 방지)
                cursor.execute("""
                    INSERT OR REPLACE INTO rss_channels
                    (channel_id, channel_name, channel_type, rss_url, is_active, 
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, TRUE, 
                           COALESCE((SELECT created_at FROM rss_channels WHERE channel_id = ?), CURRENT_TIMESTAMP),
                           CURRENT_TIMESTAMP)
                """, (channel_id, channel_name, channel_type, rss_url, channel_id))
                
                # 후보 채널 상태 업데이트
                cursor.execute("""
                    UPDATE channel_candidates
                    SET review_status = 'approved', 
                        reviewed_at = CURRENT_TIMESTAMP, 
                        reviewed_by = ?,
                        notes = ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                """, (reviewer, notes, channel_id))
                
                conn.commit()
                self.logger.info(f"채널 후보 승인: {channel_name} ({channel_id}) by {reviewer}")
                return True
                
        except sqlite3.IntegrityError as e:
            self.logger.error(f"채널 승인 중 데이터베이스 제약 위반: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"채널 후보 승인 실패: {str(e)}")
            return False
    
    def _reject_channel_candidate(self, channel_id: str, notes: str = "", reviewer: str = "") -> bool:
        """채널 후보 거부 (개선된 로직)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 후보 채널 존재 확인
                cursor.execute("""
                    SELECT channel_name, review_status FROM channel_candidates 
                    WHERE channel_id = ?
                """, (channel_id,))
                
                result = cursor.fetchone()
                if not result:
                    self.logger.error(f"후보 채널을 찾을 수 없음: {channel_id}")
                    return False
                
                channel_name, current_status = result
                
                # 이미 거부된 채널인지 확인
                if current_status == 'rejected':
                    self.logger.info(f"이미 거부된 채널: {channel_id}")
                    return True
                
                # 승인된 채널을 거부하는 경우 RSS 채널에서 비활성화
                if current_status == 'approved':
                    cursor.execute("""
                        UPDATE rss_channels 
                        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE channel_id = ?
                    """, (channel_id,))
                    self.logger.info(f"승인된 채널을 비활성화: {channel_id}")
                
                # 후보 채널 상태 업데이트
                cursor.execute("""
                    UPDATE channel_candidates
                    SET review_status = 'rejected', 
                        reviewed_at = CURRENT_TIMESTAMP,
                        reviewed_by = ?,
                        notes = ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                """, (reviewer, notes, channel_id))
                
                conn.commit()
                self.logger.info(f"채널 후보 거부: {channel_name} ({channel_id}) by {reviewer}")
                return True
                
        except Exception as e:
            self.logger.error(f"채널 후보 거부 실패: {str(e)}")
            return False
    
    def _apply_channel_formatting(self, worksheet: gspread.Worksheet, last_row: int) -> None:
        """승인된 채널 시트 서식 적용"""
        try:
            # 헤더 서식
            worksheet.format('A1:I1', {
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.8},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            # 활성 상태별 조건부 서식
            worksheet.format(f'E2:E{last_row}', {
                'backgroundColor': {'red': 0.9, 'green': 1, 'blue': 0.9}
            })
            
        except Exception as e:
            self.logger.error(f"채널 시트 서식 적용 실패: {str(e)}")
    
    def _apply_candidate_formatting(self, worksheet: gspread.Worksheet, last_row: int) -> None:
        """후보 채널 시트 서식 적용"""
        try:
            # 헤더 서식
            worksheet.format('A1:L1', {
                'backgroundColor': {'red': 0.8, 'green': 0.6, 'blue': 0.2},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            # 데이터 검증 추가 (승인여부 컬럼)
            worksheet.add_validation(
                f'K2:K{last_row}',
                'ONE_OF_LIST',
                ['승인', '거부', ''],
                showCustomUi=True
            )
            
        except Exception as e:
            self.logger.error(f"후보 시트 서식 적용 실패: {str(e)}")
    
    def _log_sync_result(self, sync_type: str, status: str, processed: int, 
                        synced: int, error_msg: Optional[str], execution_time: float) -> None:
        """동기화 결과 로그 기록"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sheets_sync_logs
                    (sync_type, status, records_processed, records_synced, 
                     error_message, execution_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sync_type, status, processed, synced, error_msg, execution_time))
                conn.commit()
        except Exception as e:
            self.logger.error(f"동기화 로그 기록 실패: {str(e)}")
    
    def get_sync_statistics(self, days: int = 7) -> Dict[str, Any]:
        """동기화 통계 조회"""
        stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'sync_breakdown': {},
            'recent_errors': [],
            'daily_stats': []
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 동기화 통계
                cursor.execute("""
                    SELECT sync_type, status, COUNT(*) as count,
                           SUM(records_processed) as processed,
                           SUM(records_synced) as synced
                    FROM sheets_sync_logs
                    WHERE DATE(synced_at) >= DATE('now', '-{} days')
                    GROUP BY sync_type, status
                """.format(days))
                
                for row in cursor.fetchall():
                    sync_type, status, count, processed, synced = row
                    if sync_type not in stats['sync_breakdown']:
                        stats['sync_breakdown'][sync_type] = {}
                    stats['sync_breakdown'][sync_type][status] = {
                        'count': count,
                        'processed': processed or 0,
                        'synced': synced or 0
                    }
                    
                    stats['total_syncs'] += count
                    if status == 'success':
                        stats['successful_syncs'] += count
                
                # 최근 오류
                cursor.execute("""
                    SELECT sync_type, error_message, synced_at
                    FROM sheets_sync_logs
                    WHERE status = 'error' AND DATE(synced_at) >= DATE('now', '-{} days')
                    ORDER BY synced_at DESC
                    LIMIT 10
                """.format(days))
                
                for row in cursor.fetchall():
                    stats['recent_errors'].append({
                        'sync_type': row[0],
                        'error_message': row[1],
                        'synced_at': row[2]
                    })
                    
        except Exception as e:
            self.logger.error(f"동기화 통계 조회 실패: {str(e)}")
        
        return stats
    
    def get_channel_candidates(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """채널 후보 목록 조회"""
        candidates = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                where_clause = ""
                params = []
                if status:
                    where_clause = "WHERE review_status = ?"
                    params.append(status)
                
                cursor.execute(f"""
                    SELECT channel_id, channel_name, channel_type, rss_url, discovery_score,
                           discovery_reason, discovered_at, review_status, reviewed_by,
                           reviewed_at, notes, sheets_synced
                    FROM channel_candidates
                    {where_clause}
                    ORDER BY discovered_at DESC
                """, params)
                
                for row in cursor.fetchall():
                    candidates.append({
                        'channel_id': row[0],
                        'channel_name': row[1],
                        'channel_type': row[2],
                        'rss_url': row[3],
                        'discovery_score': row[4],
                        'discovery_reason': row[5],
                        'discovered_at': row[6],
                        'review_status': row[7],
                        'reviewed_by': row[8],
                        'reviewed_at': row[9],
                        'notes': row[10],
                        'sheets_synced': row[11]
                    })
                    
        except Exception as e:
            self.logger.error(f"채널 후보 조회 실패: {str(e)}")
        
        return candidates
    
    def real_time_sync(self, sync_interval_minutes: int = 5) -> bool:
        """실시간 동기화 (주기적 실행)"""
        try:
            self.logger.info(f"실시간 동기화 시작 (interval: {sync_interval_minutes}분)")
            
            # 1. 신규 후보 채널 업로드
            candidates_result = self.sync_channel_candidates_to_sheets()
            
            # 2. 검토 결과 다운로드
            reviews_result = self.sync_reviews_from_sheets()
            
            # 3. 승인된 채널 업데이트
            channels_result = self.sync_approved_channels_to_sheets()
            
            success_count = sum([candidates_result, reviews_result, channels_result])
            
            if success_count >= 2:
                self.logger.info(f"실시간 동기화 성공: {success_count}/3")
                return True
            else:
                self.logger.warning(f"실시간 동기화 부분 실패: {success_count}/3")
                return False
                
        except Exception as e:
            self.logger.error(f"실시간 동기화 실패: {str(e)}")
            return False
    
    def monitor_sheets_changes(self, last_check: Optional[datetime] = None) -> Dict[str, Any]:
        """채널 후보 시트의 변경사항 모니터링 (데모 모드 지원)"""
        changes = {
            'new_approvals': [],
            'new_rejections': [],
            'pending_reviews': 0,
            'last_updated': datetime.now()
        }
        
        if self._is_demo_mode():
            self.logger.info("데모 모드: 변경사항 모니터링 시뮬레이션")
            # 데모 데이터 생성
            candidates = self.get_channel_candidates()
            changes.update({
                'new_approvals': candidates[:1] if candidates else [],  # 첫 번째만 승인으로 시뮬레이션
                'new_rejections': candidates[1:2] if len(candidates) > 1 else [],  # 두 번째만 거부로 시뮬레이션
                'pending_reviews': max(0, len(candidates) - 2)
            })
            return changes
        
        try:
            worksheet = self.spreadsheet.worksheet(self.config.candidates_sheet_name)
            all_records = worksheet.get_all_records()
            
            for record in all_records:
                channel_id = record.get('채널ID')
                if not channel_id:
                    continue
                
                approval_status = str(record.get('승인여부', '')).strip().lower()
                channel_name = record.get('채널명', '')
                
                if approval_status in ['승인', 'approved', 'y', 'yes', '1']:
                    changes['new_approvals'].append({
                        'channel_id': channel_id,
                        'channel_name': channel_name,
                        'notes': record.get('비고', ''),
                        'reviewer': record.get('검토자', '')
                    })
                elif approval_status in ['거부', 'rejected', 'n', 'no', '0']:
                    changes['new_rejections'].append({
                        'channel_id': channel_id,
                        'channel_name': channel_name,
                        'notes': record.get('비고', ''),
                        'reviewer': record.get('검토자', '')
                    })
                elif not approval_status:
                    changes['pending_reviews'] += 1
            
            self.logger.info(f"변경사항 모니터링 완료: 승인 {len(changes['new_approvals'])}, 거부 {len(changes['new_rejections'])}, 대기 {changes['pending_reviews']}")
            
        except Exception as e:
            self.logger.error(f"변경사항 모니터링 실패: {str(e)}")
        
        return changes
    
    def validate_connection(self) -> Dict[str, Any]:
        """연결 상태 및 권한 검증 (데모 모드 지원)"""
        validation_result = {
            'connection_status': False,
            'spreadsheet_access': False,
            'sheets_accessible': [],
            'credentials_path': self.config.credentials_path,
            'error_message': None
        }
        
        if self._is_demo_mode():
            self.logger.info("데모 모드: 연결 검증 시뮬레이션")
            validation_result.update({
                'connection_status': True,
                'spreadsheet_access': True,
                'spreadsheet_title': f'데모 스프레드시트 ({self.config.spreadsheet_id[:10]}...)',
                'read_permission': True,
                'write_permission': True,
                'sheets_accessible': [
                    {'title': self.config.channels_sheet_name, 'id': 1, 'rows': 100, 'cols': 10},
                    {'title': self.config.candidates_sheet_name, 'id': 2, 'rows': 100, 'cols': 12}
                ],
                'demo_mode': True
            })
            return validation_result
        
        try:
            # 기본 인증 테스트
            if self.gc is None:
                raise Exception("인증 객체가 없음")
            
            validation_result['connection_status'] = True
            
            # 스프레드시트 접근 테스트
            spreadsheet_title = self.spreadsheet.title
            validation_result['spreadsheet_access'] = True
            validation_result['spreadsheet_title'] = spreadsheet_title
            
            # 워크시트 접근 테스트
            worksheets = self.spreadsheet.worksheets()
            for sheet in worksheets:
                validation_result['sheets_accessible'].append({
                    'title': sheet.title,
                    'id': sheet.id,
                    'rows': sheet.row_count,
                    'cols': sheet.col_count
                })
            
            # 읽기/쓰기 권한 테스트
            try:
                test_sheet = self.spreadsheet.sheet1
                test_value = test_sheet.acell('A1').value
                validation_result['read_permission'] = True
                
                # 비어있는 셀에 테스트 쓰기
                test_sheet.update_acell('Z1000', f'test_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
                validation_result['write_permission'] = True
                
                # 테스트 데이터 삭제
                test_sheet.update_acell('Z1000', '')
                
            except Exception as e:
                validation_result['write_permission'] = False
                validation_result['permission_error'] = str(e)
            
            self.logger.info(f"연결 검증 성공: {spreadsheet_title}")
            
        except Exception as e:
            validation_result['error_message'] = str(e)
            self.logger.error(f"연결 검증 실패: {str(e)}")
        
        return validation_result