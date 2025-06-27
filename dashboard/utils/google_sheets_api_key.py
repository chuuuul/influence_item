"""
Google Sheets API 키 클라이언트
공개 시트에 API 키로 접근
"""

import os
import gspread
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
import streamlit as st

logger = logging.getLogger(__name__)

class GoogleSheetsAPIKeyClient:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.worksheet = None
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL')
        self.api_key = os.getenv('YOUTUBE_API_KEY')  # YouTube API 키를 Google Sheets API 키로도 사용
        
    def authenticate(self):
        """
        API 키를 사용하여 Google Sheets API에 연결
        """
        try:
            if not self.api_key:
                logger.error("Google API 키가 설정되지 않았습니다")
                return False
                
            # API 키 인증
            self.client = gspread.api_key(self.api_key)
            logger.info("Google Sheets API 키 인증 성공")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets API 키 인증 실패: {e}")
            return False
    
    def connect_to_sheet(self, worksheet_name='Sheet1'):
        """
        공개 Google Sheets에 연결
        """
        if not self.client:
            if not self.authenticate():
                return False
        
        try:
            # 시트 열기 (공개 시트만 가능)
            self.sheet = self.client.open_by_key(self.sheet_id)
            
            # 워크시트 선택
            try:
                self.worksheet = self.sheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                # 첫 번째 워크시트 사용
                self.worksheet = self.sheet.sheet1
                logger.info(f"기본 워크시트 사용: {self.worksheet.title}")
            
            logger.info(f"Google Sheets 연결 성공: {self.sheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 연결 실패: {e}")
            return False
    
    def get_channels(self):
        """
        모든 채널 데이터 가져오기 (읽기 전용)
        """
        try:
            if not self.worksheet:
                if not self.connect_to_sheet():
                    return []
            
            # 모든 데이터 가져오기
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
    
    def get_connection_status(self):
        """
        연결 상태 확인
        """
        try:
            if not self.client:
                if not self.authenticate():
                    return False, "API 키 인증 실패"
            
            if not self.sheet:
                if not self.connect_to_sheet():
                    return False, "시트 연결 실패"
            
            # 시트 정보 가져오기
            sheet_info = {
                'title': self.sheet.title,
                'sheet_id': self.sheet.id,
                'url': self.sheet.url,
                'worksheet_count': len(self.sheet.worksheets()),
                'access_type': 'API Key (Read-Only)',
                'note': '공개 시트만 접근 가능, 읽기 전용'
            }
            
            return True, sheet_info
            
        except Exception as e:
            return False, f"연결 오류: {e}"
    
    # 읽기 전용이므로 쓰기 기능들은 에러 반환
    def add_channel(self, channel_name, category, channel_id=None, subscribers=None):
        return False
    
    def update_channel_status(self, channel_name, status):
        return False
    
    def sync_data(self):
        return False
    
    def setup_channel_headers(self):
        return False

# 전역 클라이언트 인스턴스
_api_key_client = None

def get_google_sheets_api_key_client():
    """
    Google Sheets API 키 클라이언트 싱글톤 인스턴스 반환
    """
    global _api_key_client
    if _api_key_client is None:
        _api_key_client = GoogleSheetsAPIKeyClient()
    return _api_key_client

def test_api_key_connection():
    """
    API 키 연결 테스트
    """
    client = get_google_sheets_api_key_client()
    success, info = client.get_connection_status()
    
    if success:
        st.success(f"✅ 구글 시트 API 키 연결 성공!")
        st.json(info)
        
        # 데이터 읽기 테스트
        channels = client.get_channels()
        if channels:
            st.success(f"📊 데이터 읽기 성공: {len(channels)}개 항목")
            st.dataframe(pd.DataFrame(channels))
        else:
            st.info("📋 시트가 비어있거나 데이터를 읽을 수 없습니다.")
    else:
        st.error(f"❌ 구글 시트 연결 실패: {info}")
    
    return success