#!/usr/bin/env python3
"""
Google Sheets 통합 모듈
채널 탐색 결과를 Google Sheets에 자동 저장하고 관리
"""

import os
import sys
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("❌ Google API 라이브러리가 설치되지 않았습니다.")
    print("pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

class GoogleSheetsIntegration:
    """Google Sheets 통합 관리 클래스"""
    
    def __init__(self, credentials_path: str = None, spreadsheet_id: str = None):
        """
        Google Sheets 통합 초기화
        
        Args:
            credentials_path: Google Sheets 서비스 계정 키 파일 경로
            spreadsheet_id: Google Sheets 스프레드시트 ID
        """
        self.credentials_path = credentials_path or self._get_credentials_path()
        self.spreadsheet_id = spreadsheet_id or self._get_spreadsheet_id()
        self.service = None
        
        # 설정 유효성 검사
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Google Sheets credentials 파일이 없습니다: {self.credentials_path}")
        
        if not self.spreadsheet_id:
            raise ValueError("Google Sheets 스프레드시트 ID가 설정되지 않았습니다.")
        
        self._initialize_service()
        logger.info(f"Google Sheets 통합 초기화 완료: {self.spreadsheet_id}")
    
    def _get_credentials_path(self) -> str:
        """credentials 파일 경로 가져오기"""
        # 환경변수에서 먼저 확인
        env_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
        if env_path and os.path.exists(env_path):
            return env_path
        
        # 기본 경로 확인
        default_paths = [
            project_root / "credentials" / "google_sheets_credentials.json",
            project_root / "google_sheets_credentials.json",
            os.path.expanduser("~/.config/google_sheets_credentials.json")
        ]
        
        for path in default_paths:
            if os.path.exists(str(path)):
                return str(path)
        
        raise FileNotFoundError("Google Sheets credentials 파일을 찾을 수 없습니다.")
    
    def _get_spreadsheet_id(self) -> str:
        """스프레드시트 ID 가져오기"""
        # 환경변수에서 확인
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        if spreadsheet_id:
            return spreadsheet_id
        
        # .env 파일에서 확인
        env_file = project_root / '.env'
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('GOOGLE_SHEETS_SPREADSHEET_ID='):
                        return line.split('=', 1)[1].strip()
        
        raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID가 설정되지 않았습니다.")
    
    def _initialize_service(self):
        """Google Sheets API 서비스 초기화"""
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets API 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"Google Sheets API 초기화 실패: {str(e)}")
            raise
    
    def get_spreadsheet_info(self) -> Dict[str, Any]:
        """스프레드시트 정보 조회"""
        try:
            metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            return {
                "title": metadata.get('properties', {}).get('title', 'Unknown'),
                "sheets": [sheet.get('properties', {}).get('title') for sheet in metadata.get('sheets', [])],
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
            }
        except Exception as e:
            logger.error(f"스프레드시트 정보 조회 실패: {str(e)}")
            raise
    
    def ensure_channel_discovery_sheet(self) -> str:
        """채널 탐색 결과 시트 생성 또는 확인"""
        sheet_name = "Channel Discovery Results"
        
        try:
            # 기존 시트 확인
            metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            existing_sheets = [sheet.get('properties', {}).get('title') for sheet in metadata.get('sheets', [])]
            
            if sheet_name not in existing_sheets:
                # 새 시트 생성
                self._create_channel_discovery_sheet(sheet_name)
                logger.info(f"새 시트 생성: {sheet_name}")
            else:
                logger.info(f"기존 시트 사용: {sheet_name}")
            
            return sheet_name
            
        except Exception as e:
            logger.error(f"시트 생성/확인 실패: {str(e)}")
            raise
    
    def _create_channel_discovery_sheet(self, sheet_name: str):
        """채널 탐색 결과 시트 생성"""
        try:
            # 시트 추가
            request_body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=request_body
            ).execute()
            
            # 헤더 추가
            headers = [
                "발견일시", "세션ID", "채널명", "채널ID", "구독자수", "비디오수", 
                "총점수", "매칭점수", "품질점수", "잠재력점수", "수익화점수",
                "인증여부", "국가", "채널타입", "설명", "채널URL"
            ]
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1:P1",
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            
            # 헤더 스타일 적용
            self._format_header_row(sheet_name)
            
        except Exception as e:
            logger.error(f"시트 생성 실패: {str(e)}")
            raise
    
    def _format_header_row(self, sheet_name: str):
        """헤더 행 서식 적용"""
        try:
            # 시트 ID 찾기
            metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_id = None
            for sheet in metadata.get('sheets', []):
                if sheet.get('properties', {}).get('title') == sheet_name:
                    sheet_id = sheet.get('properties', {}).get('sheetId')
                    break
            
            if sheet_id is None:
                return
            
            # 헤더 행 서식 요청
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
                            'textFormat': {
                                'foregroundColor': {'red': 1, 'green': 1, 'blue': 1},
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            }]
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
        except Exception as e:
            logger.warning(f"헤더 서식 적용 실패: {str(e)}")
    
    def save_channel_discovery_results(self, candidates: List[Dict], session_info: Dict = None) -> bool:
        """채널 탐색 결과를 Google Sheets에 저장"""
        if not candidates:
            logger.warning("저장할 채널 후보가 없습니다.")
            return False
        
        try:
            sheet_name = self.ensure_channel_discovery_sheet()
            
            # 데이터 행 준비
            rows = []
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session_id = session_info.get('session_id', '') if session_info else ''
            
            for candidate in candidates:
                row = [
                    current_time,
                    session_id,
                    candidate.get('channel_name', ''),
                    candidate.get('channel_id', ''),
                    candidate.get('subscriber_count', 0),
                    candidate.get('video_count', 0),
                    round(candidate.get('total_score', 0), 2),
                    round(candidate.get('matching_score', 0), 2),
                    round(candidate.get('quality_score', 0), 2),
                    round(candidate.get('potential_score', 0), 2),
                    round(candidate.get('monetization_score', 0), 2),
                    "✓" if candidate.get('verified', False) else "✗",
                    candidate.get('country', ''),
                    candidate.get('channel_type', ''),
                    candidate.get('description', '')[:100] + "..." if len(candidate.get('description', '')) > 100 else candidate.get('description', ''),
                    candidate.get('channel_url', '')
                ]
                rows.append(row)
            
            # 기존 데이터 확인 후 다음 행부터 추가
            existing_data = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:A"
            ).execute()
            
            existing_rows = len(existing_data.get('values', []))
            start_row = existing_rows + 1
            
            # 데이터 추가
            range_name = f"{sheet_name}!A{start_row}:P{start_row + len(rows) - 1}"
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': rows}
            ).execute()
            
            logger.info(f"Google Sheets에 {len(candidates)}개 채널 결과 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 저장 실패: {str(e)}")
            return False
    
    def get_latest_discoveries(self, limit: int = 50) -> List[Dict]:
        """최근 탐색 결과 조회"""
        try:
            sheet_name = "Channel Discovery Results"
            
            # 전체 데이터 조회
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:P"
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # 헤더만 있는 경우
                return []
            
            headers = values[0]
            data_rows = values[1:]
            
            # 최근 데이터부터 반환 (역순으로 정렬)
            results = []
            for row in reversed(data_rows[-limit:]):
                if len(row) >= len(headers):
                    result_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            result_dict[header] = row[i]
                    results.append(result_dict)
            
            return results
            
        except Exception as e:
            logger.error(f"최근 탐색 결과 조회 실패: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """채널 탐색 통계 조회"""
        try:
            discoveries = self.get_latest_discoveries(limit=1000)
            
            if not discoveries:
                return {
                    "total_discoveries": 0,
                    "unique_channels": 0,
                    "average_score": 0,
                    "high_score_count": 0,
                    "verified_count": 0,
                    "last_discovery": None
                }
            
            # 통계 계산
            unique_channels = set()
            total_score = 0
            high_score_count = 0
            verified_count = 0
            
            for discovery in discoveries:
                channel_id = discovery.get('채널ID', '')
                if channel_id:
                    unique_channels.add(channel_id)
                
                try:
                    score = float(discovery.get('총점수', 0))
                    total_score += score
                    if score >= 70:
                        high_score_count += 1
                except (ValueError, TypeError):
                    pass
                
                if discovery.get('인증여부') == '✓':
                    verified_count += 1
            
            return {
                "total_discoveries": len(discoveries),
                "unique_channels": len(unique_channels),
                "average_score": round(total_score / len(discoveries), 2) if discoveries else 0,
                "high_score_count": high_score_count,
                "verified_count": verified_count,
                "last_discovery": discoveries[0].get('발견일시') if discoveries else None
            }
            
        except Exception as e:
            logger.error(f"통계 조회 실패: {str(e)}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """오래된 데이터 정리"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            discoveries = self.get_latest_discoveries(limit=10000)
            rows_to_keep = []
            
            for discovery in discoveries:
                try:
                    discovery_date = datetime.strptime(discovery.get('발견일시', ''), "%Y-%m-%d %H:%M:%S")
                    if discovery_date >= cutoff_date:
                        rows_to_keep.append(discovery)
                except (ValueError, TypeError):
                    # 날짜 파싱 실패시 보존
                    rows_to_keep.append(discovery)
            
            removed_count = len(discoveries) - len(rows_to_keep)
            
            if removed_count > 0:
                # 시트 클리어 후 유지할 데이터만 다시 저장
                sheet_name = "Channel Discovery Results"
                
                # 기존 데이터 클리어 (헤더 제외)
                self.service.spreadsheets().values().clear(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A2:P"
                ).execute()
                
                # 유지할 데이터 다시 저장
                if rows_to_keep:
                    # 데이터를 다시 변환
                    headers = ["발견일시", "세션ID", "채널명", "채널ID", "구독자수", "비디오수", 
                              "총점수", "매칭점수", "품질점수", "잠재력점수", "수익화점수",
                              "인증여부", "국가", "채널타입", "설명", "채널URL"]
                    
                    values = []
                    for discovery in reversed(rows_to_keep):  # 원래 순서로 복원
                        row = [discovery.get(header, '') for header in headers]
                        values.append(row)
                    
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{sheet_name}!A2:P{len(values) + 1}",
                        valueInputOption='RAW',
                        body={'values': values}
                    ).execute()
                
                logger.info(f"Google Sheets에서 {removed_count}개 오래된 레코드 정리 완료")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"데이터 정리 실패: {str(e)}")
            return 0

def test_google_sheets_integration():
    """Google Sheets 통합 테스트"""
    try:
        print("🔍 Google Sheets 통합 테스트 시작...")
        
        # 통합 모듈 초기화
        sheets = GoogleSheetsIntegration()
        
        # 스프레드시트 정보 조회
        info = sheets.get_spreadsheet_info()
        print(f"✅ 스프레드시트 연결 성공: {info['title']}")
        print(f"📄 URL: {info['url']}")
        
        # 시트 생성/확인
        sheet_name = sheets.ensure_channel_discovery_sheet()
        print(f"✅ 채널 탐색 시트 준비: {sheet_name}")
        
        # 테스트 데이터 저장
        test_candidates = [
            {
                "channel_name": "테스트 채널 1",
                "channel_id": "UC_TEST_001",
                "subscriber_count": 100000,
                "video_count": 150,
                "total_score": 75.5,
                "matching_score": 80.0,
                "quality_score": 70.0,
                "potential_score": 75.0,
                "monetization_score": 77.0,
                "verified": True,
                "country": "KR",
                "channel_type": "BEAUTY_INFLUENCER",
                "description": "테스트용 채널 설명입니다.",
                "channel_url": "https://www.youtube.com/channel/UC_TEST_001"
            }
        ]
        
        success = sheets.save_channel_discovery_results(
            test_candidates, 
            {"session_id": "test_session_001"}
        )
        
        if success:
            print("✅ 테스트 데이터 저장 성공")
        else:
            print("❌ 테스트 데이터 저장 실패")
        
        # 통계 조회
        stats = sheets.get_statistics()
        print(f"📊 통계 조회 성공: {stats}")
        
        print("🎉 Google Sheets 통합 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ Google Sheets 통합 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    test_google_sheets_integration()