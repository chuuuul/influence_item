"""
Google Sheets 클라이언트
실제 Google Sheets API를 사용하여 데이터를 읽고 쓰는 기능
"""

import os
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.worksheet = None
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL')
        
    def authenticate(self):
        """
        Google Sheets API 인증
        서비스 계정 키 파일을 사용하여 인증
        """
        try:
            # 서비스 계정 키 파일 경로
            key_file_path = Path(__file__).parent.parent.parent / 'config' / 'google_service_account.json'
            
            if not key_file_path.exists():
                logger.warning(f"Google 서비스 계정 키 파일을 찾을 수 없습니다: {key_file_path}")
                return False
            
            # 인증 스코프 설정
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 인증
            credentials = Credentials.from_service_account_file(key_file_path, scopes=scopes)
            self.client = gspread.authorize(credentials)
            
            logger.info("Google Sheets API 인증 성공")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets API 인증 실패: {e}")
            return False
    
    def connect_to_sheet(self, worksheet_name='Sheet1'):
        """
        Google Sheets에 연결
        """
        if not self.client:
            if not self.authenticate():
                return False
        
        try:
            # 시트 열기
            self.sheet = self.client.open_by_key(self.sheet_id)
            self.worksheet = self.sheet.worksheet(worksheet_name)
            
            logger.info(f"Google Sheets 연결 성공: {self.sheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 연결 실패: {e}")
            return False
    
    def create_channel_headers(self):
        """
        채널 관리용 헤더 생성
        """
        headers = [
            '채널명', 'Channel Name', '채널 ID', 'Channel ID', 
            '카테고리', 'Category', '구독자수', 'Subscribers',
            '상태', 'Status', '마지막 업데이트', 'Last Updated'
        ]
        
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 첫 번째 행에 헤더 추가
            self.worksheet.update('A1:L1', [headers])
            logger.info("채널 관리 헤더 생성 완료")
            return True
            
        except Exception as e:
            logger.error(f"헤더 생성 실패: {e}")
            return False
    
    def add_channel(self, channel_name, category, channel_id=None, subscribers=None):
        """
        새 채널 추가
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 현재 시간
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 새 행 데이터
            new_row = [
                channel_name,           # 채널명
                channel_name,           # Channel Name (영문)
                channel_id or '',       # 채널 ID
                channel_id or '',       # Channel ID
                category,               # 카테고리
                category,               # Category (영문)
                subscribers or 0,       # 구독자수
                subscribers or 0,       # Subscribers
                '활성',                  # 상태
                'Active',               # Status
                current_time,           # 마지막 업데이트
                current_time            # Last Updated
            ]
            
            # 마지막 행에 추가
            self.worksheet.append_row(new_row)
            logger.info(f"새 채널 추가 완료: {channel_name}")
            return True
            
        except Exception as e:
            logger.error(f"채널 추가 실패: {e}")
            return False
    
    def get_channels(self):
        """
        모든 채널 데이터 가져오기
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return []
            
            # 모든 데이터 가져오기
            data = self.worksheet.get_all_records()
            logger.info(f"채널 데이터 {len(data)}개 가져오기 완료")
            return data
            
        except Exception as e:
            logger.error(f"채널 데이터 가져오기 실패: {e}")
            return []
    
    def update_channel_status(self, channel_name, status):
        """
        채널 상태 업데이트
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 채널명으로 행 찾기
            cell = self.worksheet.find(channel_name)
            if cell:
                row = cell.row
                # 상태 컬럼 업데이트 (I열: 상태, J열: Status)
                self.worksheet.update(f'I{row}:J{row}', [[status, status]])
                # 마지막 업데이트 시간 업데이트 (K열, L열)
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.worksheet.update(f'K{row}:L{row}', [[current_time, current_time]])
                
                logger.info(f"채널 상태 업데이트 완료: {channel_name} -> {status}")
                return True
            else:
                logger.warning(f"채널을 찾을 수 없습니다: {channel_name}")
                return False
                
        except Exception as e:
            logger.error(f"채널 상태 업데이트 실패: {e}")
            return False
    
    def export_to_csv(self, filename=None):
        """
        Google Sheets 데이터를 CSV로 내보내기
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return None
            
            # 데이터를 DataFrame으로 변환
            data = self.worksheet.get_all_records()
            df = pd.DataFrame(data)
            
            # 파일명 생성
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'google_sheets_export_{timestamp}.csv'
            
            # CSV 파일로 저장
            export_path = Path(__file__).parent.parent.parent / 'data' / 'exports' / filename
            export_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"CSV 내보내기 완료: {export_path}")
            return str(export_path)
            
        except Exception as e:
            logger.error(f"CSV 내보내기 실패: {e}")
            return None
    
    def sync_data(self):
        """
        데이터 동기화 - 양방향 동기화
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 현재 시트의 데이터 가져오기
            data = self.get_channels()
            
            # 동기화 로직 구현 (예: 로컬 DB와 동기화)
            # 여기서는 단순히 마지막 업데이트 시간만 갱신
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 모든 행의 마지막 업데이트 시간 갱신
            if data:
                num_rows = len(data) + 1  # 헤더 포함
                for i in range(2, num_rows + 1):  # 2번째 행부터 (헤더 제외)
                    self.worksheet.update(f'K{i}:L{i}', [[current_time, current_time]])
            
            logger.info(f"데이터 동기화 완료: {len(data)}개 항목")
            return True
            
        except Exception as e:
            logger.error(f"데이터 동기화 실패: {e}")
            return False
    
    def get_connection_status(self):
        """
        연결 상태 확인
        """
        try:
            if not self.client:
                if not self.authenticate():
                    return False, "인증 실패"
            
            if not self.sheet:
                if not self.connect_to_sheet():
                    return False, "시트 연결 실패"
            
            # 시트 정보 가져오기 시도
            sheet_info = {
                'title': self.sheet.title,
                'sheet_id': self.sheet.id,
                'url': self.sheet.url,
                'worksheet_count': len(self.sheet.worksheets())
            }
            
            return True, sheet_info
            
        except Exception as e:
            return False, f"연결 오류: {e}"

# 전역 클라이언트 인스턴스
_google_sheets_client = None

def get_google_sheets_client():
    """
    Google Sheets 클라이언트 싱글톤 인스턴스 반환
    """
    global _google_sheets_client
    if _google_sheets_client is None:
        _google_sheets_client = GoogleSheetsClient()
    return _google_sheets_client