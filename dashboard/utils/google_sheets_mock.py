"""
Google Sheets Mock 클라이언트
실제 API 키가 없을 때 테스트용으로 사용
"""

import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)

class MockGoogleSheetsClient:
    def __init__(self):
        self.connected = False
        self.sheet_data = []
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL')
        
        # 테스트용 더미 데이터
        self.sheet_data = [
            {
                '채널명': '아이유 IU',
                'Channel Name': 'IU Official',
                '채널 ID': 'UC3SyT4_WLHzN7JmHQwKQZww',
                'Channel ID': 'UC3SyT4_WLHzN7JmHQwKQZww',
                '카테고리': '음악',
                'Category': 'Music',
                '구독자수': 5200000,
                'Subscribers': 5200000,
                '상태': '활성',
                'Status': 'Active',
                '마지막 업데이트': '2025-06-27 18:00:00',
                'Last Updated': '2025-06-27 18:00:00'
            },
            {
                '채널명': '올리비아 로드리고',
                'Channel Name': 'Olivia Rodrigo',
                '채널 ID': 'UCBVjMGOIkavEAhyqpxJ73Dw',
                'Channel ID': 'UCBVjMGOIkavEAhyqpxJ73Dw',
                '카테고리': '음악',
                'Category': 'Music',
                '구독자수': 3100000,
                'Subscribers': 3100000,
                '상태': '활성',
                'Status': 'Active',
                '마지막 업데이트': '2025-06-27 17:30:00',
                'Last Updated': '2025-06-27 17:30:00'
            }
        ]
        
    def authenticate(self):
        """Mock 인증"""
        logger.info("Mock Google Sheets API 인증 시뮬레이션")
        return True
    
    def connect_to_sheet(self, worksheet_name='Sheet1'):
        """Mock 시트 연결"""
        logger.info(f"Mock Google Sheets 연결 시뮬레이션: {worksheet_name}")
        self.connected = True
        return True
    
    def create_channel_headers(self):
        """Mock 헤더 생성"""
        logger.info("Mock 채널 관리 헤더 생성 시뮬레이션")
        return True
    
    def add_channel(self, channel_name, category, channel_id=None, subscribers=None):
        """Mock 채널 추가"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        new_channel = {
            '채널명': channel_name,
            'Channel Name': channel_name,
            '채널 ID': channel_id or f'UC_{channel_name.replace(" ", "")}_{len(self.sheet_data)}',
            'Channel ID': channel_id or f'UC_{channel_name.replace(" ", "")}_{len(self.sheet_data)}',
            '카테고리': category,
            'Category': category,
            '구독자수': subscribers or 0,
            'Subscribers': subscribers or 0,
            '상태': '활성',
            'Status': 'Active',
            '마지막 업데이트': current_time,
            'Last Updated': current_time
        }
        
        self.sheet_data.append(new_channel)
        logger.info(f"Mock 새 채널 추가 시뮬레이션: {channel_name}")
        return True
    
    def get_channels(self):
        """Mock 채널 데이터 가져오기"""
        logger.info(f"Mock 채널 데이터 {len(self.sheet_data)}개 가져오기 시뮬레이션")
        return self.sheet_data
    
    def update_channel_status(self, channel_name, status):
        """Mock 채널 상태 업데이트"""
        for channel in self.sheet_data:
            if channel['채널명'] == channel_name:
                channel['상태'] = status
                channel['Status'] = status
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                channel['마지막 업데이트'] = current_time
                channel['Last Updated'] = current_time
                logger.info(f"Mock 채널 상태 업데이트 시뮬레이션: {channel_name} -> {status}")
                return True
        
        logger.warning(f"Mock 채널을 찾을 수 없음: {channel_name}")
        return False
    
    def export_to_csv(self, filename=None):
        """Mock CSV 내보내기"""
        try:
            df = pd.DataFrame(self.sheet_data)
            
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'mock_google_sheets_export_{timestamp}.csv'
            
            export_path = Path(__file__).parent.parent.parent / 'data' / 'exports' / filename
            export_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"Mock CSV 내보내기 시뮬레이션: {export_path}")
            return str(export_path)
            
        except Exception as e:
            logger.error(f"Mock CSV 내보내기 실패: {e}")
            return None
    
    def sync_data(self):
        """Mock 데이터 동기화"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for channel in self.sheet_data:
            channel['마지막 업데이트'] = current_time
            channel['Last Updated'] = current_time
        
        logger.info(f"Mock 데이터 동기화 시뮬레이션: {len(self.sheet_data)}개 항목")
        return True
    
    def get_connection_status(self):
        """Mock 연결 상태 확인"""
        if self.sheet_id and self.sheet_url:
            sheet_info = {
                'title': 'Mock Influence Item Channels',
                'sheet_id': self.sheet_id,
                'url': self.sheet_url,
                'worksheet_count': 1,
                'note': 'Mock 클라이언트 - 실제 Google Sheets API 연결 아님'
            }
            return True, sheet_info
        else:
            return False, "Mock 연결 정보 부족"

# Mock 클라이언트가 실제 클라이언트를 대체할지 결정하는 함수
def should_use_mock():
    """실제 Google Service Account 키 파일이 없으면 Mock 사용"""
    key_file_path = Path(__file__).parent.parent.parent / 'config' / 'google_service_account.json'
    return not key_file_path.exists()

def get_google_sheets_client():
    """
    적절한 Google Sheets 클라이언트 반환 (실제 또는 Mock)
    """
    if should_use_mock():
        logger.info("Google Service Account 키 파일이 없음. Mock 클라이언트 사용")
        return MockGoogleSheetsClient()
    else:
        try:
            from dashboard.utils.google_sheets_client import GoogleSheetsClient
            logger.info("실제 Google Sheets 클라이언트 사용")
            return GoogleSheetsClient()
        except ImportError:
            logger.warning("실제 Google Sheets 클라이언트 import 실패. Mock 클라이언트 사용")
            return MockGoogleSheetsClient()