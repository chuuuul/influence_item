"""
Google Sheets 연동 모듈

PRD 요구사항에 따른 Google Sheets 연동:
- 채널 후보 결과를 Google Sheets에 자동 저장
- 운영자가 승인/제외 처리할 수 있는 형태로 구성
- 실시간 동기화 및 업데이트
- 채널 목록 관리 기능
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import os
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
    from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None  # 타입 힌트를 위한 더미 변수
    logging.warning("gspread가 설치되지 않았습니다. 'pip install gspread google-auth' 실행")

from .models import ChannelCandidate, ChannelStatus, ChannelType


class GoogleSheetsManager:
    """Google Sheets 관리자"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        if not GSPREAD_AVAILABLE:
            self.logger.warning("Google Sheets 연동이 비활성화되어 있습니다. gspread와 google-auth를 설치해주세요.")
            self.gc = None
            self.credentials_path = None
            return
        
        # 인증 설정
        self.credentials_path = credentials_path or self._find_credentials_file()
        self.gc = self._authenticate()
        
        # 워크시트 헤더 정의
        self.candidate_headers = [
            "탐색일시", "채널ID", "채널명", "채널URL", "구독자수", "영상수", "조회수",
            "설명", "카테고리", "국가", "인증여부", "총점수", "등급", "매칭점수",
            "품질점수", "잠재력점수", "수익화점수", "강점", "약점", "상태", "검토메모",
            "검토자", "검토일시", "승인여부"
        ]
        
        self.approved_headers = [
            "승인일시", "채널ID", "채널명", "채널URL", "구독자수", "영상수", 
            "채널타입", "주요키워드", "총점수", "등급", "추가메모"
        ]
    
    def _find_credentials_file(self) -> Optional[str]:
        """인증 파일 자동 탐지"""
        
        possible_paths = [
            "credentials/google_sheets_credentials.json",
            "config/google_sheets_credentials.json",
            "google_sheets_credentials.json",
            os.path.expanduser("~/.config/google_sheets_credentials.json")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"Google Sheets 인증 파일 발견: {path}")
                return path
        
        self.logger.warning("Google Sheets 인증 파일을 찾을 수 없습니다")
        return None
    
    def _authenticate(self):
        """Google Sheets 인증"""
        
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                "Google Sheets 인증 파일이 필요합니다. "
                "Service Account JSON 파일을 다운로드하여 credentials 폴더에 저장하세요."
            )
        
        try:
            # 필요한 권한 범위 설정
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            
            gc = gspread.authorize(credentials)
            self.logger.info("Google Sheets 인증 완료")
            return gc
            
        except Exception as e:
            self.logger.error(f"Google Sheets 인증 실패: {str(e)}")
            raise
    
    def create_discovery_spreadsheet(self, spreadsheet_name: str = None) -> Tuple[str, str]:
        """새로운 채널 탐색 스프레드시트 생성"""
        
        if not GSPREAD_AVAILABLE or self.gc is None:
            raise ImportError("Google Sheets 연동이 비활성화되어 있습니다")
        
        if not spreadsheet_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            spreadsheet_name = f"채널_탐색_결과_{timestamp}"
        
        try:
            # 새 스프레드시트 생성
            spreadsheet = self.gc.create(spreadsheet_name)
            
            # 후보 채널 워크시트 설정
            candidates_sheet = spreadsheet.sheet1
            candidates_sheet.update_title("채널_후보")
            candidates_sheet.update('A1', [self.candidate_headers])
            
            # 승인된 채널 워크시트 추가
            approved_sheet = spreadsheet.add_worksheet(
                title="승인된_채널", 
                rows=1000, 
                cols=len(self.approved_headers)
            )
            approved_sheet.update('A1', [self.approved_headers])
            
            # 대시보드 워크시트 추가
            dashboard_sheet = spreadsheet.add_worksheet(
                title="대시보드", 
                rows=50, 
                cols=10
            )
            self._setup_dashboard_sheet(dashboard_sheet)
            
            # 헤더 행 서식 설정
            self._format_header_rows(candidates_sheet, approved_sheet)
            
            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
            
            self.logger.info(f"스프레드시트 생성 완료: {spreadsheet_name}")
            self.logger.info(f"URL: {spreadsheet_url}")
            
            return spreadsheet.id, spreadsheet_url
            
        except Exception as e:
            self.logger.error(f"스프레드시트 생성 실패: {str(e)}")
            raise
    
    def _setup_dashboard_sheet(self, dashboard_sheet):
        """대시보드 워크시트 설정"""
        
        dashboard_data = [
            ["📊 채널 탐색 대시보드", "", "", ""],
            ["", "", "", ""],
            ["📈 요약 통계", "", "", ""],
            ["총 후보 채널 수", "=COUNTA(채널_후보!B:B)-1", "", ""],
            ["승인된 채널 수", "=COUNTA(승인된_채널!B:B)-1", "", ""],
            ["평균 점수", "=AVERAGE(채널_후보!L:L)", "", ""],
            ["S등급 채널 수", "=COUNTIF(채널_후보!M:M,\"S\")", "", ""],
            ["A등급 채널 수", "=COUNTIF(채널_후보!M:M,\"A\")", "", ""],
            ["", "", "", ""],
            ["🎯 상태별 분포", "", "", ""],
            ["검토 대기", "=COUNTIF(채널_후보!U:U,\"needs_review\")", "", ""],
            ["승인됨", "=COUNTIF(채널_후보!U:U,\"approved\")", "", ""],
            ["거부됨", "=COUNTIF(채널_후보!U:U,\"rejected\")", "", ""],
            ["", "", "", ""],
            ["📅 마지막 업데이트", f"=TODAY()", "", ""],
            ["", "", "", ""],
            ["💡 사용 방법", "", "", ""],
            ["1. '채널_후보' 탭에서 후보 채널 검토", "", "", ""],
            ["2. '상태' 열에서 승인/거부 선택", "", "", ""],
            ["3. '검토메모' 열에 의견 작성", "", "", ""],
            ["4. '승인여부' 열에 Y/N 입력", "", "", ""]
        ]
        
        dashboard_sheet.update('A1', dashboard_data)
    
    def _format_header_rows(self, *worksheets):
        """헤더 행 서식 설정"""
        
        for sheet in worksheets:
            try:
                # 헤더 행 볼드 처리
                sheet.format('1:1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
                
                # 컬럼 너비 자동 조정
                sheet.columns_auto_resize(0, len(sheet.row_values(1)))
                
            except Exception as e:
                self.logger.warning(f"헤더 서식 설정 실패: {str(e)}")
    
    def upload_channel_candidates(self, spreadsheet_id: str, candidates: List[ChannelCandidate],
                                worksheet_name: str = "채널_후보") -> bool:
        """채널 후보를 스프레드시트에 업로드"""
        
        if not GSPREAD_AVAILABLE or self.gc is None:
            self.logger.warning("Google Sheets 연동이 비활성화되어 있습니다")
            return False
        
        try:
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # 기존 데이터 제거 (헤더 제외)
            worksheet.clear('A2:Z')
            
            # 후보 데이터 변환
            rows_data = []
            for candidate in candidates:
                row = self._convert_candidate_to_row(candidate)
                rows_data.append(row)
            
            if rows_data:
                # 배치 업데이트
                range_name = f'A2:Y{len(rows_data) + 1}'
                worksheet.update(range_name, rows_data)
                
                # 데이터 검증 및 조건부 서식 설정
                self._setup_data_validation(worksheet)
                self._setup_conditional_formatting(worksheet)
                
                self.logger.info(f"채널 후보 업로드 완료: {len(candidates)}개")
                return True
            else:
                self.logger.warning("업로드할 채널 후보가 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"채널 후보 업로드 실패: {str(e)}")
            return False
    
    def _convert_candidate_to_row(self, candidate: ChannelCandidate) -> List[str]:
        """채널 후보를 스프레드시트 행으로 변환"""
        
        return [
            candidate.discovered_at.strftime("%Y-%m-%d %H:%M") if candidate.discovered_at else "",
            candidate.channel_id,
            candidate.channel_name,
            candidate.channel_url,
            str(candidate.subscriber_count),
            str(candidate.video_count),
            str(candidate.view_count),
            candidate.description[:500] + "..." if len(candidate.description) > 500 else candidate.description,
            candidate.channel_type.value if candidate.channel_type else "",
            candidate.country or "",
            "✓" if candidate.verified else "",
            f"{candidate.total_score:.1f}" if candidate.total_score else "0.0",
            candidate.metadata.get('grade', '') if candidate.metadata else "",
            f"{candidate.matching_scores.get('matching', 0):.2f}" if candidate.matching_scores else "0.00",
            f"{candidate.matching_scores.get('quality', 0):.2f}" if candidate.matching_scores else "0.00",
            f"{candidate.matching_scores.get('potential', 0):.2f}" if candidate.matching_scores else "0.00",
            f"{candidate.matching_scores.get('monetization', 0):.2f}" if candidate.matching_scores else "0.00",
            ", ".join(candidate.metadata.get('strengths', [])) if candidate.metadata else "",
            ", ".join(candidate.metadata.get('weaknesses', [])) if candidate.metadata else "",
            candidate.status.value if candidate.status else ChannelStatus.DISCOVERED.value,
            candidate.review_notes,
            candidate.reviewed_by,
            candidate.reviewed_at.strftime("%Y-%m-%d %H:%M") if candidate.reviewed_at else "",
            ""  # 승인여부 (수동 입력)
        ]
    
    def _setup_data_validation(self, worksheet):
        """데이터 검증 설정"""
        
        try:
            # 상태 열 (U열) 드롭다운 설정
            status_options = [status.value for status in ChannelStatus]
            
            worksheet.data_validation(
                'U2:U1000',
                {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': status_options
                    },
                    'strict': True,
                    'showCustomUi': True
                }
            )
            
            # 승인여부 열 (Y열) 드롭다운 설정
            worksheet.data_validation(
                'Y2:Y1000',
                {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': ['Y', 'N', '보류']
                    },
                    'strict': True,
                    'showCustomUi': True
                }
            )
            
        except Exception as e:
            self.logger.warning(f"데이터 검증 설정 실패: {str(e)}")
    
    def _setup_conditional_formatting(self, worksheet):
        """조건부 서식 설정"""
        
        try:
            # 점수별 색상 구분 (L열: 총점수)
            worksheet.format('L2:L1000', {
                'conditionalFormatRules': [
                    {
                        'ranges': [{'sheetId': worksheet.id, 'startRowIndex': 1, 'endRowIndex': 1000, 
                                  'startColumnIndex': 11, 'endColumnIndex': 12}],
                        'booleanRule': {
                            'condition': {'type': 'NUMBER_GREATER_THAN_EQ', 'values': [{'userEnteredValue': '80'}]},
                            'format': {'backgroundColor': {'red': 0.8, 'green': 1.0, 'blue': 0.8}}
                        }
                    },
                    {
                        'ranges': [{'sheetId': worksheet.id, 'startRowIndex': 1, 'endRowIndex': 1000,
                                  'startColumnIndex': 11, 'endColumnIndex': 12}],
                        'booleanRule': {
                            'condition': {'type': 'NUMBER_LESS_THAN', 'values': [{'userEnteredValue': '50'}]},
                            'format': {'backgroundColor': {'red': 1.0, 'green': 0.8, 'blue': 0.8}}
                        }
                    }
                ]
            })
            
            # 상태별 색상 구분 (U열: 상태)
            worksheet.format('U2:U1000', {
                'conditionalFormatRules': [
                    {
                        'ranges': [{'sheetId': worksheet.id, 'startRowIndex': 1, 'endRowIndex': 1000,
                                  'startColumnIndex': 20, 'endColumnIndex': 21}],
                        'booleanRule': {
                            'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'approved'}]},
                            'format': {'backgroundColor': {'red': 0.8, 'green': 1.0, 'blue': 0.8}}
                        }
                    },
                    {
                        'ranges': [{'sheetId': worksheet.id, 'startRowIndex': 1, 'endRowIndex': 1000,
                                  'startColumnIndex': 20, 'endColumnIndex': 21}],
                        'booleanRule': {
                            'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'rejected'}]},
                            'format': {'backgroundColor': {'red': 1.0, 'green': 0.8, 'blue': 0.8}}
                        }
                    }
                ]
            })
            
        except Exception as e:
            self.logger.warning(f"조건부 서식 설정 실패: {str(e)}")
    
    def sync_approved_channels(self, spreadsheet_id: str) -> List[Dict[str, Any]]:
        """승인된 채널을 별도 워크시트로 동기화"""
        
        try:
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            
            # 후보 워크시트에서 승인된 채널 조회
            candidates_sheet = spreadsheet.worksheet("채널_후보")
            all_records = candidates_sheet.get_all_records()
            
            approved_channels = []
            for record in all_records:
                if (record.get('승인여부') == 'Y' or 
                    record.get('상태') == 'approved'):
                    approved_channels.append(record)
            
            if not approved_channels:
                self.logger.info("승인된 채널이 없습니다")
                return []
            
            # 승인된 채널 워크시트 업데이트
            approved_sheet = spreadsheet.worksheet("승인된_채널")
            approved_sheet.clear('A2:K')
            
            approved_rows = []
            for channel in approved_channels:
                approved_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    channel.get('채널ID', ''),
                    channel.get('채널명', ''),
                    channel.get('채널URL', ''),
                    channel.get('구독자수', ''),
                    channel.get('영상수', ''),
                    channel.get('카테고리', ''),
                    ", ".join(channel.get('키워드', '').split(', ')[:5]),  # 상위 5개 키워드만
                    channel.get('총점수', ''),
                    channel.get('등급', ''),
                    channel.get('검토메모', '')
                ]
                approved_rows.append(approved_row)
            
            if approved_rows:
                range_name = f'A2:K{len(approved_rows) + 1}'
                approved_sheet.update(range_name, approved_rows)
            
            self.logger.info(f"승인된 채널 동기화 완료: {len(approved_channels)}개")
            return approved_channels
            
        except Exception as e:
            self.logger.error(f"승인된 채널 동기화 실패: {str(e)}")
            return []
    
    def get_review_updates(self, spreadsheet_id: str, 
                          last_sync_time: datetime = None) -> List[Dict[str, Any]]:
        """운영자의 검토 업데이트 가져오기"""
        
        try:
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            candidates_sheet = spreadsheet.worksheet("채널_후보")
            all_records = candidates_sheet.get_all_records()
            
            updated_records = []
            
            for record in all_records:
                # 검토 상태가 업데이트된 항목 확인
                if (record.get('상태') in ['approved', 'rejected'] or
                    record.get('승인여부') in ['Y', 'N'] or
                    record.get('검토메모')):
                    
                    # 마지막 동기화 이후 업데이트 확인 (간단한 구현)
                    if last_sync_time is None or record.get('검토일시'):
                        updated_records.append({
                            'channel_id': record.get('채널ID'),
                            'status': record.get('상태'),
                            'approval': record.get('승인여부'),
                            'review_notes': record.get('검토메모'),
                            'reviewer': record.get('검토자'),
                            'review_date': record.get('검토일시')
                        })
            
            self.logger.info(f"검토 업데이트 조회 완료: {len(updated_records)}개")
            return updated_records
            
        except Exception as e:
            self.logger.error(f"검토 업데이트 조회 실패: {str(e)}")
            return []
    
    def update_channel_status(self, spreadsheet_id: str, channel_id: str, 
                            status: str, review_notes: str = "",
                            reviewer: str = "") -> bool:
        """특정 채널의 상태 업데이트"""
        
        try:
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            candidates_sheet = spreadsheet.worksheet("채널_후보")
            
            # 채널 ID로 행 찾기
            channel_ids = candidates_sheet.col_values(2)  # B열: 채널ID
            
            try:
                row_index = channel_ids.index(channel_id) + 1  # 1-based index
            except ValueError:
                self.logger.warning(f"채널 ID를 찾을 수 없습니다: {channel_id}")
                return False
            
            # 상태 업데이트
            update_data = [
                [status],  # U열: 상태
                [review_notes],  # V열: 검토메모
                [reviewer],  # W열: 검토자
                [datetime.now().strftime("%Y-%m-%d %H:%M")]  # X열: 검토일시
            ]
            
            candidates_sheet.update(f'U{row_index}:X{row_index}', update_data, value_input_option='USER_ENTERED')
            
            self.logger.info(f"채널 상태 업데이트 완료: {channel_id} -> {status}")
            return True
            
        except Exception as e:
            self.logger.error(f"채널 상태 업데이트 실패: {str(e)}")
            return False
    
    def export_to_csv(self, spreadsheet_id: str, worksheet_name: str = "채널_후보") -> Optional[str]:
        """워크시트를 CSV로 내보내기"""
        
        try:
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # CSV 다운로드 URL 생성
            csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={worksheet.id}"
            
            self.logger.info(f"CSV 내보내기 URL 생성: {worksheet_name}")
            return csv_url
            
        except Exception as e:
            self.logger.error(f"CSV 내보내기 실패: {str(e)}")
            return None
    
    def share_spreadsheet(self, spreadsheet_id: str, email_addresses: List[str],
                         role: str = 'writer') -> bool:
        """스프레드시트 공유 설정"""
        
        if not GSPREAD_AVAILABLE or self.gc is None:
            self.logger.warning("Google Sheets 연동이 비활성화되어 있습니다")
            return False
        
        try:
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            
            for email in email_addresses:
                try:
                    spreadsheet.share(email, perm_type='user', role=role)
                    self.logger.info(f"스프레드시트 공유 완료: {email} ({role})")
                except Exception as e:
                    self.logger.warning(f"공유 실패 {email}: {str(e)}")
                    continue
            
            return True
            
        except Exception as e:
            self.logger.error(f"스프레드시트 공유 실패: {str(e)}")
            return False