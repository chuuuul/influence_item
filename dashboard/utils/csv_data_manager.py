"""
CSV 데이터 매니저
로컬 CSV 파일을 사용하여 실제 데이터 읽기/쓰기 기능 구현
"""

import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
import streamlit as st

logger = logging.getLogger(__name__)

class CSVDataManager:
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / 'data'
        self.csv_file = self.data_dir / 'channels.csv'
        self.data_dir.mkdir(exist_ok=True)
        
        # 기본 헤더 설정
        self.headers = ['채널명', '채널 ID', '카테고리', '구독자수', '상태', '마지막 업데이트']
        
        # CSV 파일이 없으면 생성
        if not self.csv_file.exists():
            self.create_initial_csv()
    
    def create_initial_csv(self):
        """
        초기 CSV 파일 생성 (샘플 데이터 포함)
        """
        try:
            sample_data = [
                ['아이유 IU', 'UC3SyT4_WLHzN7JmHQwKQZww', '음악', 5200000, '활성', '2025-06-27 18:00:00'],
                ['올리비아 로드리고', 'UCBVjMGOIkavEAhyqpxJ73Dw', '음악', 3100000, '활성', '2025-06-27 17:30:00'],
                ['블랙핑크', 'UCOmHUn--16B90oW2L6FRR3A', '음악', 8900000, '활성', '2025-06-27 16:00:00']
            ]
            
            df = pd.DataFrame(sample_data, columns=self.headers)
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"초기 CSV 파일 생성: {self.csv_file}")
            
        except Exception as e:
            logger.error(f"초기 CSV 파일 생성 실패: {e}")
    
    def get_channels(self):
        """
        모든 채널 데이터 가져오기
        """
        try:
            if not self.csv_file.exists():
                self.create_initial_csv()
            
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig')
            
            # DataFrame을 딕셔너리 리스트로 변환
            channels = df.to_dict('records')
            
            logger.info(f"채널 데이터 {len(channels)}개 로드")
            return channels
            
        except Exception as e:
            logger.error(f"채널 데이터 로드 실패: {e}")
            return []
    
    def add_channel(self, channel_name, category, channel_id=None, subscribers=None):
        """
        새 채널 추가
        """
        try:
            # 현재 데이터 읽기
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig') if self.csv_file.exists() else pd.DataFrame(columns=self.headers)
            
            # 중복 체크
            if channel_name in df['채널명'].values:
                logger.warning(f"이미 존재하는 채널: {channel_name}")
                return False
            
            # 새 행 데이터
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_row = {
                '채널명': channel_name,
                '채널 ID': channel_id or f'UC_{channel_name.replace(" ", "")}_{len(df)}',
                '카테고리': category,
                '구독자수': subscribers or 0,
                '상태': '활성',
                '마지막 업데이트': current_time
            }
            
            # 새 행 추가
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            # CSV 파일 저장
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"새 채널 추가 완료: {channel_name}")
            return True
            
        except Exception as e:
            logger.error(f"채널 추가 실패: {e}")
            return False
    
    def update_channel_status(self, channel_name, status):
        """
        채널 상태 업데이트
        """
        try:
            if not self.csv_file.exists():
                logger.warning("CSV 파일이 존재하지 않습니다")
                return False
            
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig')
            
            # 채널 찾기
            mask = df['채널명'] == channel_name
            if not mask.any():
                logger.warning(f"채널을 찾을 수 없습니다: {channel_name}")
                return False
            
            # 상태 업데이트
            df.loc[mask, '상태'] = status
            df.loc[mask, '마지막 업데이트'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # CSV 파일 저장
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"채널 상태 업데이트 완료: {channel_name} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"채널 상태 업데이트 실패: {e}")
            return False
    
    def delete_channel(self, channel_name):
        """
        채널 삭제
        """
        try:
            if not self.csv_file.exists():
                logger.warning("CSV 파일이 존재하지 않습니다")
                return False
            
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig')
            
            # 채널 삭제
            df = df[df['채널명'] != channel_name]
            
            # CSV 파일 저장
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"채널 삭제 완료: {channel_name}")
            return True
            
        except Exception as e:
            logger.error(f"채널 삭제 실패: {e}")
            return False
    
    def export_to_csv(self, filename=None):
        """
        CSV 파일을 exports 폴더로 복사
        """
        try:
            if not self.csv_file.exists():
                return None
            
            # 파일명 생성
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'channels_export_{timestamp}.csv'
            
            # exports 폴더로 복사
            export_path = self.data_dir / 'exports' / filename
            export_path.parent.mkdir(exist_ok=True)
            
            # 파일 복사
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig')
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"CSV 내보내기 완료: {export_path}")
            return str(export_path)
            
        except Exception as e:
            logger.error(f"CSV 내보내기 실패: {e}")
            return None
    
    def sync_data(self):
        """
        데이터 동기화 (모든 채널의 마지막 업데이트 시간 갱신)
        """
        try:
            if not self.csv_file.exists():
                return False
            
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig')
            
            # 모든 행의 마지막 업데이트 시간 갱신
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df['마지막 업데이트'] = current_time
            
            # CSV 파일 저장
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"데이터 동기화 완료: {len(df)}개 항목")
            return True
            
        except Exception as e:
            logger.error(f"데이터 동기화 실패: {e}")
            return False
    
    def get_connection_status(self):
        """
        연결 상태 확인
        """
        try:
            info = {
                'type': 'CSV Local Storage',
                'file_path': str(self.csv_file),
                'file_exists': self.csv_file.exists(),
                'file_size': self.csv_file.stat().st_size if self.csv_file.exists() else 0,
                'last_modified': datetime.fromtimestamp(self.csv_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if self.csv_file.exists() else 'N/A',
                'access_type': 'Read/Write',
                'note': '로컬 CSV 파일 기반 데이터 저장소'
            }
            
            return True, info
            
        except Exception as e:
            return False, f"상태 확인 오류: {e}"

# 전역 매니저 인스턴스
_csv_manager = None

def get_csv_data_manager():
    """
    CSV 데이터 매니저 싱글톤 인스턴스 반환
    """
    global _csv_manager
    if _csv_manager is None:
        _csv_manager = CSVDataManager()
    return _csv_manager

def test_csv_connection():
    """
    CSV 연결 테스트
    """
    manager = get_csv_data_manager()
    success, info = manager.get_connection_status()
    
    if success:
        st.success(f"✅ CSV 데이터 저장소 연결 성공!")
        st.json(info)
        
        # 데이터 읽기 테스트
        channels = manager.get_channels()
        if channels:
            st.success(f"📊 데이터 읽기 성공: {len(channels)}개 항목")
            st.dataframe(pd.DataFrame(channels))
        else:
            st.info("📋 데이터가 비어있습니다.")
    else:
        st.error(f"❌ CSV 연결 실패: {info}")
    
    return success