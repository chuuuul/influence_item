"""
환경변수 로더
대시보드에서 .env 파일을 자동으로 로드
"""

import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_env_file():
    """
    .env 파일에서 환경변수 로드
    """
    # 프로젝트 루트에서 .env 파일 찾기
    current_path = Path(__file__).parent
    project_root = current_path.parent.parent
    env_file = project_root / '.env'
    
    if not env_file.exists():
        logger.warning(f".env 파일을 찾을 수 없습니다: {env_file}")
        return
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # 빈 줄이나 주석 무시
                if not line or line.startswith('#'):
                    continue
                
                # KEY=VALUE 형식 파싱
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 환경변수 설정 (기존 값이 없는 경우만)
                    if not os.getenv(key):
                        os.environ[key] = value
                        logger.debug(f"환경변수 설정: {key}")
                    
        logger.info(f".env 파일 로드 완료: {env_file}")
        
        # YouTube API 키 확인
        youtube_key = os.getenv('YOUTUBE_API_KEY')
        if youtube_key:
            logger.info(f"YouTube API 키 로드 완료: {youtube_key[:10]}...")
        else:
            logger.warning("YouTube API 키를 찾을 수 없습니다")
            
    except Exception as e:
        logger.error(f".env 파일 로드 실패: {str(e)}")

def ensure_youtube_api_key():
    """
    YouTube API 키가 있는지 확인하고 없으면 .env 파일에서 로드
    """
    if not os.getenv('YOUTUBE_API_KEY'):
        load_env_file()
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        raise ValueError("YouTube API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
    
    return api_key

def ensure_gemini_api_key():
    """
    Gemini API 키가 있는지 확인하고 없으면 .env 파일에서 로드
    """
    if not os.getenv('GEMINI_API_KEY'):
        load_env_file()
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Gemini API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
    
    return api_key

def get_google_sheet_settings():
    """
    Google Sheets 설정 정보 반환
    """
    if not os.getenv('GOOGLE_SHEET_ID'):
        load_env_file()
    
    return {
        'sheet_id': os.getenv('GOOGLE_SHEET_ID'),
        'sheet_url': os.getenv('GOOGLE_SHEET_URL')
    }

# 모듈 임포트 시 자동으로 .env 파일 로드
load_env_file()