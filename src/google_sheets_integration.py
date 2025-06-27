"""
Google Sheets 통합 모듈
PRD v1.0 - 채널 목록 관리 및 결과 저장
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import time
from pathlib import Path

# Google Sheets API imports
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

logger = logging.getLogger(__name__)


class GoogleSheetsManager:
    """Google Sheets 관리자"""
    
    def __init__(self, credentials_path: str = None, sheet_id: str = None):
        """
        Args:
            credentials_path: Google 서비스 계정 인증 파일 경로
            sheet_id: Google Sheets ID
        """
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH')
        self.sheet_id = sheet_id or os.getenv('GOOGLE_SHEET_ID')
        self.client = None
        self.workbook = None
        
        # 재시도 설정
        self.max_retries = 3
        self.retry_delay = 1.0
        
        self._init_client()
    
    def _init_client(self):
        """Google Sheets 클라이언트 초기화"""
        try:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                logger.warning("Google 인증 파일이 없습니다. 환경변수나 서비스 계정 설정을 확인하세요.")
                return
            
            if not self.sheet_id:
                logger.warning("Google Sheets ID가 설정되지 않았습니다.")
                return
            
            # 인증 스코프 설정
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 서비스 계정 인증
            credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            
            self.client = gspread.authorize(credentials)
            self.workbook = self.client.open_by_key(self.sheet_id)
            
            logger.info("Google Sheets 클라이언트 초기화 완료")
            
        except Exception as e:
            logger.error(f"Google Sheets 초기화 실패: {e}")
    
    def _retry_operation(self, operation, *args, **kwargs):
        """재시도 로직이 있는 작업 실행"""
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                logger.warning(f"작업 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
                time.sleep(self.retry_delay * (attempt + 1))
    
    def get_or_create_worksheet(self, worksheet_name: str) -> Optional[Any]:
        """워크시트 가져오기 또는 생성"""
        if not self.workbook:
            logger.error("Google Sheets가 초기화되지 않았습니다.")
            return None
        
        try:
            # 기존 워크시트 찾기
            try:
                worksheet = self.workbook.worksheet(worksheet_name)
                logger.info(f"기존 워크시트 발견: {worksheet_name}")
                return worksheet
            except gspread.WorksheetNotFound:
                pass
            
            # 새 워크시트 생성
            worksheet = self.workbook.add_worksheet(
                title=worksheet_name, rows=1000, cols=20
            )
            logger.info(f"새 워크시트 생성: {worksheet_name}")
            return worksheet
            
        except Exception as e:
            logger.error(f"워크시트 처리 실패: {e}")
            return None
    
    def setup_channels_worksheet(self) -> bool:
        """채널 관리 워크시트 설정"""
        try:
            worksheet = self.get_or_create_worksheet("Channels")
            if not worksheet:
                return False
            
            # 헤더 설정
            headers = [
                "Channel Name", "Channel ID", "Category", "Subscribers", 
                "Status", "Last Updated", "RSS URL", "Notes"
            ]
            
            # 첫 번째 행이 비어있거나 헤더가 다르면 헤더 설정
            try:
                existing_headers = worksheet.row_values(1)
                if not existing_headers or existing_headers != headers:
                    self._retry_operation(worksheet.update, "A1:H1", [headers])
                    logger.info("채널 워크시트 헤더 설정 완료")
            except Exception as e:
                logger.warning(f"헤더 확인/설정 중 오류: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"채널 워크시트 설정 실패: {e}")
            return False
    
    def setup_results_worksheet(self) -> bool:
        """분석 결과 워크시트 설정"""
        try:
            worksheet = self.get_or_create_worksheet("Analysis Results")
            if not worksheet:
                return False
            
            # 헤더 설정
            headers = [
                "Timestamp", "Channel Name", "Celebrity", "Video Title", 
                "Video URL", "Product Name", "Brand", "Category", 
                "Confidence Score", "Sentiment", "PPL Probability", 
                "Status", "Hook Sentence", "Summary", "Target Audience", 
                "Price Point", "Hashtags", "Notes"
            ]
            
            # 첫 번째 행이 비어있거나 헤더가 다르면 헤더 설정
            try:
                existing_headers = worksheet.row_values(1)
                if not existing_headers or len(existing_headers) < len(headers):
                    self._retry_operation(worksheet.update, f"A1:{chr(65 + len(headers) - 1)}1", [headers])
                    logger.info("분석 결과 워크시트 헤더 설정 완료")
            except Exception as e:
                logger.warning(f"헤더 확인/설정 중 오류: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"분석 결과 워크시트 설정 실패: {e}")
            return False
    
    def get_channels_list(self) -> List[Dict[str, Any]]:
        """채널 목록 조회"""
        try:
            worksheet = self.get_or_create_worksheet("Channels")
            if not worksheet:
                return []
            
            # 모든 데이터 가져오기
            records = self._retry_operation(worksheet.get_all_records)
            
            # 활성 채널만 필터링
            active_channels = []
            for record in records:
                if record.get('Status', '').lower() in ['active', '활성', 'enabled']:
                    active_channels.append({
                        'channel_name': record.get('Channel Name', ''),
                        'channel_id': record.get('Channel ID', ''),
                        'category': record.get('Category', ''),
                        'subscribers': record.get('Subscribers', ''),
                        'rss_url': record.get('RSS URL', ''),
                        'notes': record.get('Notes', ''),
                        'last_updated': record.get('Last Updated', '')
                    })
            
            logger.info(f"활성 채널 {len(active_channels)}개 조회 완료")
            return active_channels
            
        except Exception as e:
            logger.error(f"채널 목록 조회 실패: {e}")
            return []
    
    def add_channel(self, channel_data: Dict[str, Any]) -> bool:
        """새 채널 추가"""
        try:
            worksheet = self.get_or_create_worksheet("Channels")
            if not worksheet:
                return False
            
            # 새 행 데이터 준비
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            row_data = [
                channel_data.get('channel_name', ''),
                channel_data.get('channel_id', ''),
                channel_data.get('category', ''),
                channel_data.get('subscribers', ''),
                channel_data.get('status', 'Active'),
                now,
                channel_data.get('rss_url', ''),
                channel_data.get('notes', '')
            ]
            
            # 행 추가
            self._retry_operation(worksheet.append_row, row_data)
            logger.info(f"채널 추가 완료: {channel_data.get('channel_name', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"채널 추가 실패: {e}")
            return False
    
    def save_analysis_result(self, result_data: Dict[str, Any]) -> bool:
        """분석 결과 저장"""
        try:
            worksheet = self.get_or_create_worksheet("Analysis Results")
            if not worksheet:
                return False
            
            # 결과 데이터 추출
            source_info = result_data.get('source_info', {})
            candidate_info = result_data.get('candidate_info', {})
            score_details = candidate_info.get('score_details', {})
            monetization_info = result_data.get('monetization_info', {})
            status_info = result_data.get('status_info', {})
            
            # 새 행 데이터 준비
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            row_data = [
                now,  # Timestamp
                source_info.get('channel_name', ''),  # Channel Name
                source_info.get('celebrity_name', ''),  # Celebrity
                source_info.get('video_title', ''),  # Video Title
                source_info.get('video_url', ''),  # Video URL
                candidate_info.get('product_name_ai', ''),  # Product Name
                '',  # Brand (추후 추출)
                ', '.join(candidate_info.get('category_path', [])),  # Category
                score_details.get('total', 0),  # Confidence Score
                '',  # Sentiment (추후 분석)
                status_info.get('ppl_confidence', 0),  # PPL Probability
                status_info.get('current_status', ''),  # Status
                candidate_info.get('hook_sentence', ''),  # Hook Sentence
                candidate_info.get('summary_for_caption', ''),  # Summary
                ', '.join(candidate_info.get('target_audience', [])),  # Target Audience
                candidate_info.get('price_point', ''),  # Price Point
                ', '.join(candidate_info.get('recommended_hashtags', [])),  # Hashtags
                f"AI Generated at {now}"  # Notes
            ]
            
            # 행 추가
            self._retry_operation(worksheet.append_row, row_data)
            logger.info(f"분석 결과 저장 완료: {candidate_info.get('product_name_ai', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"분석 결과 저장 실패: {e}")
            return False
    
    def get_recent_results(self, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 분석 결과 조회"""
        try:
            worksheet = self.get_or_create_worksheet("Analysis Results")
            if not worksheet:
                return []
            
            # 모든 레코드 가져오기
            records = self._retry_operation(worksheet.get_all_records)
            
            # 시간순 정렬 (최신순)
            sorted_records = sorted(
                records,
                key=lambda x: x.get('Timestamp', ''),
                reverse=True
            )
            
            # 제한 개수만큼 반환
            return sorted_records[:limit]
            
        except Exception as e:
            logger.error(f"최근 결과 조회 실패: {e}")
            return []
    
    def update_channel_status(self, channel_name: str, new_status: str) -> bool:
        """채널 상태 업데이트"""
        try:
            worksheet = self.get_or_create_worksheet("Channels")
            if not worksheet:
                return False
            
            # 채널 찾기
            cell = worksheet.find(channel_name)
            if not cell:
                logger.warning(f"채널을 찾을 수 없습니다: {channel_name}")
                return False
            
            # 상태 컬럼 (E) 업데이트
            status_cell = f"E{cell.row}"
            self._retry_operation(worksheet.update, status_cell, new_status)
            
            # 업데이트 시간 컬럼 (F) 업데이트
            timestamp_cell = f"F{cell.row}"
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            self._retry_operation(worksheet.update, timestamp_cell, now)
            
            logger.info(f"채널 상태 업데이트 완료: {channel_name} -> {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"채널 상태 업데이트 실패: {e}")
            return False
    
    def export_to_csv(self, worksheet_name: str, output_path: str) -> bool:
        """워크시트를 CSV로 내보내기"""
        try:
            worksheet = self.get_or_create_worksheet(worksheet_name)
            if not worksheet:
                return False
            
            # 모든 데이터 가져오기
            records = self._retry_operation(worksheet.get_all_records)
            
            # DataFrame으로 변환 후 CSV 저장
            df = pd.DataFrame(records)
            df.to_csv(output_path, index=False, encoding='utf-8')
            
            logger.info(f"CSV 내보내기 완료: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"CSV 내보내기 실패: {e}")
            return False
    
    def get_sheet_url(self) -> str:
        """Google Sheets URL 반환"""
        if self.sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit"
        return ""
    
    def test_connection(self) -> Dict[str, Any]:
        """연결 테스트"""
        test_result = {
            'connected': False,
            'workbook_title': '',
            'worksheets': [],
            'error': None
        }
        
        try:
            if not self.workbook:
                test_result['error'] = "Google Sheets가 초기화되지 않았습니다."
                return test_result
            
            # 워크북 정보
            test_result['workbook_title'] = self.workbook.title
            test_result['worksheets'] = [ws.title for ws in self.workbook.worksheets()]
            test_result['connected'] = True
            
            logger.info(f"Google Sheets 연결 테스트 성공: {test_result['workbook_title']}")
            
        except Exception as e:
            test_result['error'] = str(e)
            logger.error(f"Google Sheets 연결 테스트 실패: {e}")
        
        return test_result


def create_google_sheets_manager(
    credentials_path: str = None,
    sheet_id: str = None
) -> GoogleSheetsManager:
    """Google Sheets 관리자 생성"""
    return GoogleSheetsManager(credentials_path, sheet_id)


def setup_default_sheets() -> bool:
    """기본 워크시트 설정"""
    try:
        manager = create_google_sheets_manager()
        
        if not manager.client:
            logger.error("Google Sheets 클라이언트가 초기화되지 않았습니다.")
            return False
        
        # 기본 워크시트들 설정
        channels_setup = manager.setup_channels_worksheet()
        results_setup = manager.setup_results_worksheet()
        
        return channels_setup and results_setup
        
    except Exception as e:
        logger.error(f"기본 시트 설정 실패: {e}")
        return False


if __name__ == "__main__":
    # 테스트 코드
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Google Sheets 매니저 테스트
    manager = create_google_sheets_manager()
    
    # 연결 테스트
    test_result = manager.test_connection()
    print(f"연결 테스트 결과: {test_result}")
    
    if test_result['connected']:
        print("Google Sheets 연결 성공!")
        
        # 기본 워크시트 설정
        setup_success = setup_default_sheets()
        print(f"워크시트 설정 결과: {setup_success}")
        
        # 채널 목록 조회 테스트
        channels = manager.get_channels_list()
        print(f"등록된 채널 수: {len(channels)}")
        
    else:
        print(f"Google Sheets 연결 실패: {test_result.get('error', 'Unknown error')}")