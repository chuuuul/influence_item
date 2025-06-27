"""
Google Sheets OAuth 클라이언트
실제 OAuth 인증을 사용하여 구글 시트에 연결
"""

import os
import gspread
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
import streamlit as st
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

class GoogleSheetsOAuthClient:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.worksheet = None
        # 환경변수가 없을 경우 기본값 사용
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID', '1hPkWFJ_FJ6YTwAIOpEbkHhs6bEAFIx2AuWfKaEA7LTY')
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL')
        
    def authenticate(self):
        """
        서비스 계정 인증을 사용하여 Google Sheets API에 연결
        """
        try:
            # 서비스 계정 인증 파일 경로
            cred_path = "/Users/chul/.config/gspread/credentials.json"
            
            # 필요한 스코프 설정
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 서비스 계정 인증
            credentials = Credentials.from_service_account_file(cred_path, scopes=scope)
            self.client = gspread.authorize(credentials)
            
            logger.info("Google Sheets 서비스 계정 인증 성공")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 인증 실패: {e}")
            return False
    
    def connect_to_sheet(self, worksheet_name='시트1'):
        """
        Google Sheets에 연결
        """
        if not self.client:
            if not self.authenticate():
                return False
        
        try:
            # 시트 열기
            self.sheet = self.client.open_by_key(self.sheet_id)
            
            # 워크시트 선택
            try:
                self.worksheet = self.sheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                # 워크시트가 없으면 첫 번째 워크시트 사용
                self.worksheet = self.sheet.sheet1
                logger.info(f"워크시트 '{worksheet_name}' 없음, 첫 번째 워크시트 사용: {self.worksheet.title}")
            
            logger.info(f"Google Sheets 연결 성공: {self.sheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 연결 실패: {e}")
            return False
    
    def setup_channel_headers(self):
        """
        채널 관리용 헤더 설정
        """
        headers = [
            '채널명', '채널 ID', '카테고리', '구독자수', '상태', '마지막 업데이트'
        ]
        
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 첫 번째 행에 헤더가 있는지 확인
            existing_headers = self.worksheet.row_values(1)
            
            if not existing_headers or existing_headers != headers:
                # 헤더 추가
                self.worksheet.update('A1:F1', [headers])
                
                # 헤더 포맷팅
                self.worksheet.format('A1:F1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
                
                logger.info("채널 관리 헤더 설정 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"헤더 설정 실패: {e}")
            return False
    
    def add_channel(self, channel_name, category, channel_id=None, subscribers=None):
        """
        새 채널 추가
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 헤더 설정
            if not self.setup_channel_headers():
                return False
            
            # 현재 시간
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 새 행 데이터
            new_row = [
                channel_name,
                channel_id or f'UC_{channel_name.replace(" ", "")}',
                category,
                subscribers or 0,
                '활성',
                current_time
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
            
            # 모든 데이터 가져오기 (헤더 포함)
            all_values = self.worksheet.get_all_values()
            
            if not all_values:
                return []
            
            # 첫 번째 행을 헤더로 사용하여 딕셔너리 리스트 생성
            headers = all_values[0]
            data = []
            
            for row in all_values[1:]:  # 헤더 제외
                if any(row):  # 빈 행 제외
                    # 행 길이가 헤더보다 짧으면 빈 문자열로 패딩
                    padded_row = row + [''] * (len(headers) - len(row))
                    channel_data = dict(zip(headers, padded_row))
                    data.append(channel_data)
            
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
            try:
                cell = self.worksheet.find(channel_name)
                if cell:
                    row = cell.row
                    # 상태 컬럼 업데이트 (E열)
                    self.worksheet.update(f'E{row}', [[status]])
                    # 마지막 업데이트 시간 업데이트 (F열)
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.worksheet.update(f'F{row}', [[current_time]])
                    
                    logger.info(f"채널 상태 업데이트 완료: {channel_name} -> {status}")
                    return True
                else:
                    logger.warning(f"채널을 찾을 수 없습니다: {channel_name}")
                    return False
            except gspread.exceptions.CellNotFound:
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
            channels = self.get_channels()
            if not channels:
                return None
            
            df = pd.DataFrame(channels)
            
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
        데이터 동기화
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return False
            
            # 현재 시트의 데이터 가져오기
            channels = self.get_channels()
            
            # 동기화 시간 업데이트
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 모든 행의 마지막 업데이트 시간 갱신
            if channels:
                num_rows = len(channels) + 1  # 헤더 포함
                for i in range(2, num_rows + 1):  # 2번째 행부터 (헤더 제외)
                    self.worksheet.update(f'F{i}', [[current_time]])
            
            logger.info(f"데이터 동기화 완료: {len(channels)}개 항목")
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
                    return False, "OAuth 인증 실패"
            
            if not self.sheet:
                if not self.connect_to_sheet():
                    return False, "시트 연결 실패"
            
            # 시트 정보 가져오기
            try:
                last_update = self.sheet.get_lastUpdateTime()
                # last_update가 이미 문자열인 경우 그대로 사용
                if isinstance(last_update, str):
                    last_update_str = last_update
                else:
                    last_update_str = last_update.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                last_update_str = "알 수 없음"
                
            sheet_info = {
                'title': self.sheet.title,
                'sheet_id': self.sheet.id,
                'url': self.sheet.url,
                'worksheet_count': len(self.sheet.worksheets()),
                'last_update': last_update_str
            }
            
            return True, sheet_info
            
        except Exception as e:
            return False, f"연결 오류: {e}"

# 전역 클라이언트 인스턴스
_oauth_client = None

def get_google_sheets_oauth_client():
    """
    Google Sheets OAuth 클라이언트 싱글톤 인스턴스 반환
    """
    global _oauth_client
    if _oauth_client is None:
        _oauth_client = GoogleSheetsOAuthClient()
    return _oauth_client

def test_connection():
    """
    연결 테스트
    """
    client = get_google_sheets_oauth_client()
    success, info = client.get_connection_status()
    
    if success:
        st.success(f"✅ 구글 시트 연결 성공!")
        st.json(info)
    else:
        st.error(f"❌ 구글 시트 연결 실패: {info}")
    
    return success