"""
환경변수 로더 유틸리티
.env 파일을 로드하고 환경변수를 안전하게 관리
"""

import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path


def load_environment(env_file: Optional[str] = None) -> None:
    """
    환경변수 파일을 로드합니다.

    Args:
        env_file: .env 파일 경로 (None일 경우 프로젝트 루트의 .env 사용)
    """
    if env_file is None:
        # 프로젝트 루트 디렉토리 찾기
        current_path = Path(__file__).parent
        while current_path != current_path.parent:
            env_path = current_path / ".env"
            if env_path.exists():
                env_file = str(env_path)
                break
            current_path = current_path.parent

    if env_file and os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"환경변수 로드 완료: {env_file}")
    else:
        print("⚠️ .env 파일을 찾을 수 없습니다.")


def get_env_var(key: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    환경변수 값을 안전하게 가져옵니다.

    Args:
        key: 환경변수 키
        default: 기본값
        required: 필수 여부

    Returns:
        환경변수 값

    Raises:
        ValueError: 필수 환경변수가 없을 경우
    """
    value = os.getenv(key, default)

    if required and value is None:
        raise ValueError(f"필수 환경변수가 설정되지 않았습니다: {key}")

    return value


def get_database_url() -> str:
    """데이터베이스 URL을 가져옵니다."""
    return get_env_var("DATABASE_URL", "sqlite:///./data/influence_item.db")


def get_google_api_key() -> str:
    """Google API 키를 가져옵니다."""
    return get_env_var("GOOGLE_API_KEY", required=True)


def get_coupang_credentials() -> dict:
    """쿠팡 파트너스 API 인증 정보를 가져옵니다."""
    return {
        "access_key": get_env_var("COUPANG_ACCESS_KEY", required=True),
        "secret_key": get_env_var("COUPANG_SECRET_KEY", required=True),
        "partner_id": get_env_var("COUPANG_PARTNER_ID", required=True),
    }


def is_debug_mode() -> bool:
    """디버그 모드 여부를 확인합니다."""
    return get_env_var("DEBUG", "False").lower() in ("true", "1", "yes")


def get_log_level() -> str:
    """로그 레벨을 가져옵니다."""
    return get_env_var("LOG_LEVEL", "INFO")


# 모듈 로드 시 자동으로 환경변수 로드
load_environment()
