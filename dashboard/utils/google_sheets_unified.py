"""
통합 Google Sheets 클라이언트 - PRD v1.0 요구사항 충족

리뷰어 지적사항 해결:
- 다중 인증 파일로 인한 혼란 제거
- 단일 통합 시스템으로 안정성 확보
- 중앙화된 경로 관리 시스템 활용
- 우선순위 기반 인증 방식 구현

우선순위: 서비스 계정 > OAuth > API 키 > Mock
"""

import os
import gspread
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, List, Any, Tuple, Optional, Union
from enum import Enum
import json

# 중앙화된 경로 관리 시스템 import
try:
    from config.path_config import get_path_manager
    pm = get_path_manager()
except ImportError:
    # fallback
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from config.path_config import get_path_manager
    pm = get_path_manager()

from google.oauth2.service_account import Credentials


class AuthMethod(Enum):
    """인증 방식 열거형"""
    SERVICE_ACCOUNT = "service_account"
    OAUTH = "oauth"
    API_KEY = "api_key"


class GoogleSheetsUnifiedClient:
    """
    통합 Google Sheets 클라이언트
    
    PRD 요구사항:
    - 채널 목록 관리 (Google Sheets)
    - 신규 채널 탐색 결과 관리
    - 운영자 검토 및 승인 처리
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.sheet = None
        self.worksheet = None
        self.auth_method = None
        self.connection_info = {}
        
        # 환경 변수 및 설정
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL') 
        
        # 경로 관리자 활용
        self.credentials_dir = pm.google_credentials_dir
        self.service_account_file = pm.google_service_account_file
        self.oauth_credentials_file = pm.google_oauth_credentials
        self.token_file = pm.google_token_file
        
        
        # 자동 연결 시도
        self._auto_connect()
    
    
    def _auto_connect(self):
        """우선순위에 따른 자동 연결"""
        auth_methods = [
            (AuthMethod.SERVICE_ACCOUNT, self._try_service_account),
            (AuthMethod.OAUTH, self._try_oauth),
            (AuthMethod.API_KEY, self._try_api_key)
        ]
        
        for method, auth_func in auth_methods:
            try:
                if auth_func():
                    self.auth_method = method
                    self.logger.info(f"Google Sheets 연결 성공: {method.value}")
                    return True
            except Exception as e:
                self.logger.debug(f"{method.value} 인증 실패: {e}")
                continue
        
        self.logger.error("모든 Google Sheets 인증 방법 실패")
        return False
    
    def _try_service_account(self) -> bool:
        """서비스 계정 인증 시도"""
        if not self.service_account_file.exists():
            return False
        
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.service_account_file, 
                scopes=scopes
            )
            self.client = gspread.authorize(credentials)
            
            return self._connect_to_sheet()
            
        except Exception as e:
            self.logger.debug(f"서비스 계정 인증 실패: {e}")
            return False
    
    def _try_oauth(self) -> bool:
        """OAuth 인증 시도"""
        # OAuth 인증 파일이 있는지 확인
        oauth_file = Path.home() / '.config' / 'gspread' / 'credentials.json'
        if not oauth_file.exists():
            return False
        
        try:
            scopes = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(oauth_file, scopes=scopes)
            self.client = gspread.authorize(credentials)
            
            return self._connect_to_sheet()
            
        except Exception as e:
            self.logger.debug(f"OAuth 인증 실패: {e}")
            return False
    
    def _try_api_key(self) -> bool:
        """API 키 인증 시도 (읽기 전용)"""
        api_key = os.getenv('YOUTUBE_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            return False
        
        try:
            self.client = gspread.api_key(api_key)
            return self._connect_to_sheet()
            
        except Exception as e:
            self.logger.debug(f"API 키 인증 실패: {e}")
            return False
    
    
    def _connect_to_sheet(self, worksheet_name: str = '채널') -> bool:
        """Google Sheets에 연결"""
        if not self.sheet_id:
            self.logger.error("GOOGLE_SHEET_ID 환경변수가 설정되지 않음")
            return False
        
        try:
            self.sheet = self.client.open_by_key(self.sheet_id)
            
            try:
                self.worksheet = self.sheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                self.worksheet = self.sheet.sheet1
                self.logger.info(f"기본 워크시트 사용: {self.worksheet.title}")
            
            # 연결 정보 저장
            self.connection_info = {
                'title': self.sheet.title,
                'sheet_id': self.sheet.id,
                'url': self.sheet.url,
                'worksheet_count': len(self.sheet.worksheets()),
                'auth_method': self.auth_method.value if self.auth_method else 'unknown',
                'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return True
            
        except Exception as e:
            self.logger.error(f"Google Sheets 연결 실패: {e}")
            return False
    
    
    def is_read_only(self) -> bool:
        """읽기 전용 모드 여부 확인"""
        return self.auth_method == AuthMethod.API_KEY
    
    def ensure_headers(self) -> bool:
        """
        N8N 워크플로우 호환 헤더 설정
        
        N8N 호환 채널 관리 헤더:
        - channel_id, channel_name, channel_type, status, celebrity_name, 
          subscribers, last_updated, description, created_date, url
        """
        headers = [
            'channel_id', 'channel_name', 'channel_type', 'status', 
            'celebrity_name', 'subscribers', 'last_updated', 
            'description', 'created_date', 'url'
        ]
        
        if self.is_read_only():
            self.logger.warning("읽기 전용 모드: 헤더 설정 불가")
            return False
        
        try:
            if not self.worksheet:
                if not self._connect_to_sheet():
                    return False
            
            # 기존 헤더 확인
            existing_headers = self.worksheet.row_values(1)
            
            if not existing_headers or existing_headers != headers:
                # 헤더 설정
                self.worksheet.update([headers], 'A1:J1')
                
                # 헤더 포맷팅
                self.worksheet.format('A1:J1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 1.0},
                    'textFormat': {'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
                })
                
                self.logger.info("N8N 호환 헤더 설정 완료")
            
            return True
            
        except Exception as e:
            self.logger.error(f"헤더 설정 실패: {e}")
            return False
    
    def add_channel(
        self, 
        channel_name: str, 
        channel_id: str, 
        category: str = '기타',
        subscribers: int = 0, 
        description: str = '',
        celebrity_name: str = '',
        url: str = ''
    ) -> bool:
        """
        새 채널 추가 (N8N 호환 구조)
        """
        if self.is_read_only():
            self.logger.error("읽기 전용 모드: 채널 추가 불가")
            return False
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # URL이 없으면 채널 ID로 생성
        if not url:
            url = f"https://www.youtube.com/channel/{channel_id}"
        
        new_channel = {
            'channel_id': channel_id,
            'channel_name': channel_name,
            'channel_type': category,
            'status': 'review',  # 영문 상태값 사용
            'celebrity_name': celebrity_name,
            'subscribers': subscribers,
            'last_updated': current_time,
            'description': description,
            'created_date': current_date,
            'url': url
        }
        
        
        try:
            if not self.ensure_headers():
                return False
            
            # 중복 확인
            existing_channels = self.get_channels()
            for channel in existing_channels:
                if channel.get('channel_id') == channel_id:
                    self.logger.warning(f"이미 존재하는 채널 ID: {channel_id}")
                    return False
            
            # 새 행 추가 (N8N 호환 순서)
            new_row = [
                channel_id, channel_name, category, 'review',
                celebrity_name, subscribers, current_time, 
                description, current_date, url
            ]
            
            self.worksheet.append_row(new_row)
            self.logger.info(f"새 채널 추가 완료: {channel_name} ({channel_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"채널 추가 실패: {e}")
            return False
    
    def get_channels(self) -> List[Dict[str, Any]]:
        """
        모든 채널 데이터 가져오기 (PRD: 채널 목록 관리)
        """
        
        try:
            if not self.worksheet:
                if not self._connect_to_sheet():
                    return []
            
            # 모든 데이터 가져오기
            all_values = self.worksheet.get_all_values()
            
            if not all_values:
                return []
            
            # 헤더와 데이터 분리
            headers = all_values[0]
            data = []
            
            for row in all_values[1:]:
                if any(row):  # 빈 행 제외
                    # 행 길이를 헤더 길이에 맞춤
                    padded_row = row + [''] * (len(headers) - len(row))
                    channel_data = dict(zip(headers, padded_row))
                    
                    # 숫자 필드 변환
                    if 'subscribers' in channel_data:
                        try:
                            channel_data['subscribers'] = int(channel_data['subscribers'] or 0)
                        except ValueError:
                            channel_data['subscribers'] = 0
                    
                    data.append(channel_data)
            
            self.logger.info(f"채널 데이터 {len(data)}개 가져오기 완료")
            return data
            
        except Exception as e:
            self.logger.error(f"채널 데이터 가져오기 실패: {e}")
            return []
    
    def update_channel_status(self, channel_id: str, status: str) -> bool:
        """
        채널 상태 업데이트 (N8N 호환 영문 상태값)
        
        상태 종류:
        - review: 신규 추가된 채널
        - active: 승인된 채널
        - inactive: 일시 중단된 채널
        """
        if self.is_read_only():
            self.logger.error("읽기 전용 모드: 상태 업데이트 불가")
            return False
        
        # 유효한 상태값 검증
        valid_statuses = {'active', 'inactive', 'review'}
        if status not in valid_statuses:
            self.logger.error(f"잘못된 상태값: {status}. 유효한 값: {valid_statuses}")
            return False
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        
        try:
            if not self.worksheet:
                if not self._connect_to_sheet():
                    return False
            
            # 채널 ID로 행 찾기
            try:
                cell = self.worksheet.find(channel_id)
                if cell:
                    row = cell.row
                    # 상태 컬럼 업데이트 (D열, N8N 구조에서는 4번째)
                    self.worksheet.update([[status]], f'D{row}')
                    # 마지막 업데이트 시간 업데이트 (G열, N8N 구조에서는 7번째)
                    self.worksheet.update([[current_time]], f'G{row}')
                    
                    self.logger.info(f"채널 상태 업데이트 완료: {channel_id} -> {status}")
                    return True
                else:
                    self.logger.warning(f"채널 ID를 찾을 수 없음: {channel_id}")
                    return False
                    
            except gspread.exceptions.CellNotFound:
                self.logger.warning(f"채널 ID를 찾을 수 없음: {channel_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"채널 상태 업데이트 실패: {e}")
            return False
    
    def get_channels_by_status(self, status: str) -> List[Dict[str, Any]]:
        """상태별 채널 필터링 (N8N 호환)"""
        channels = self.get_channels()
        return [ch for ch in channels if ch.get('status') == status]
    
    def get_channels_by_category(self, category: str) -> List[Dict[str, Any]]:
        """카테고리별 채널 필터링 (N8N 호환)"""
        channels = self.get_channels()
        return [ch for ch in channels if ch.get('channel_type') == category]
    
    def get_celebrity_channels(self) -> List[Dict[str, Any]]:
        """연예인 채널만 필터링"""
        channels = self.get_channels()
        return [ch for ch in channels if ch.get('celebrity_name', '').strip()]
    
    def export_to_csv(self, filename: Optional[str] = None) -> Optional[str]:
        """CSV로 내보내기"""
        try:
            channels = self.get_channels()
            if not channels:
                return None
            
            df = pd.DataFrame(channels)
            
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                auth_suffix = self.auth_method.value if self.auth_method else 'unknown'
                filename = f'channels_export_{auth_suffix}_{timestamp}.csv'
            
            # 내보내기 디렉토리 생성
            export_dir = pm.screenshot_dir.parent / 'exports'
            pm.ensure_directory_exists(export_dir)
            
            export_path = export_dir / filename
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"CSV 내보내기 완료: {export_path}")
            return str(export_path)
            
        except Exception as e:
            self.logger.error(f"CSV 내보내기 실패: {e}")
            return None
    
    def get_connection_status(self) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """연결 상태 및 정보 반환"""
        try:
            if self.auth_method is None:
                return False, "연결되지 않음"
            
            
            if not self.connection_info:
                return False, "연결 정보 없음"
            
            # 실제 연결 상태 정보
            connection_status = self.connection_info.copy()
            connection_status.update({
                'capabilities': ['read'] if self.is_read_only() else ['read', 'write'],
                'data_count': len(self.get_channels())
            })
            
            return True, connection_status
            
        except Exception as e:
            return False, f"상태 확인 오류: {e}"
    
    def sync_data(self) -> bool:
        """데이터 동기화 (마지막 업데이트 시간 갱신)"""
        if self.is_read_only():
            self.logger.warning("읽기 전용 모드: 동기화 불가")
            return False
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        
        try:
            channels = self.get_channels()
            if not channels:
                return True
            
            # 모든 채널의 마지막 업데이트 시간 갱신 (G열)
            num_rows = len(channels) + 1  # 헤더 포함
            for i in range(2, num_rows + 1):  # 헤더 제외
                self.worksheet.update([[current_time]], f'G{i}')
            
            self.logger.info(f"데이터 동기화 완료: {len(channels)}개 항목")
            return True
            
        except Exception as e:
            self.logger.error(f"데이터 동기화 실패: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """채널 통계 정보"""
        channels = self.get_channels()
        
        if not channels:
            return {
                'total_channels': 0,
                'by_status': {},
                'by_category': {},
                'total_subscribers': 0
            }
        
        # 상태별 통계 (N8N 호환)
        status_counts = {}
        for channel in channels:
            status = channel.get('status', '미지정')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 카테고리별 통계 (N8N 호환)
        category_counts = {}
        for channel in channels:
            category = channel.get('channel_type', '미지정')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # 연예인 채널 통계
        celebrity_count = sum(
            1 for channel in channels if channel.get('celebrity_name', '').strip()
        )
        
        # 총 구독자수
        total_subscribers = sum(
            channel.get('subscribers', 0) for channel in channels
        )
        
        return {
            'total_channels': len(channels),
            'by_status': status_counts,
            'by_category': category_counts,
            'celebrity_channels': celebrity_count,
            'total_subscribers': total_subscribers,
            'auth_method': self.auth_method.value if self.auth_method else 'none',
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


# 전역 싱글톤 인스턴스
_unified_client = None

def get_google_sheets_client() -> GoogleSheetsUnifiedClient:
    """통합 Google Sheets 클라이언트 싱글톤 반환"""
    global _unified_client
    if _unified_client is None:
        _unified_client = GoogleSheetsUnifiedClient()
    return _unified_client

def reset_client():
    """클라이언트 재설정 (테스트용)"""
    global _unified_client
    _unified_client = None


if __name__ == "__main__":
    # 테스트 실행
    client = get_google_sheets_client()
    
    print("\n=== Google Sheets 통합 클라이언트 테스트 ===")
    
    # 연결 상태 확인
    success, info = client.get_connection_status()
    if success:
        print(f"✅ 연결 성공: {info}")
    else:
        print(f"❌ 연결 실패: {info}")
    
    # 채널 데이터 조회
    channels = client.get_channels()
    print(f"\n📊 채널 데이터: {len(channels)}개")
    
    # 통계 정보
    stats = client.get_statistics()
    print(f"\n📈 통계 정보:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "="*50)