"""
pytest 설정 및 공통 픽스처
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def temp_env_file():
    """임시 .env 파일 생성 픽스처"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("TEST_VAR=test_value\n")
        f.write("GOOGLE_API_KEY=test_google_key\n")
        f.write("COUPANG_ACCESS_KEY=test_access_key\n")
        f.write("COUPANG_SECRET_KEY=test_secret_key\n")
        f.write("COUPANG_PARTNER_ID=test_partner_id\n")
        temp_file = f.name

    yield temp_file

    # 정리
    os.unlink(temp_file)


@pytest.fixture
def clean_env():
    """환경변수 정리 픽스처"""
    # 테스트 시작 전 환경변수 백업
    original_env = os.environ.copy()

    yield

    # 테스트 종료 후 환경변수 복원
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_env_vars():
    """테스트용 환경변수 모킹 픽스처"""
    env_vars = {
        "GOOGLE_API_KEY": "test_google_key",
        "GEMINI_API_KEY": "test_gemini_key",
        "COUPANG_ACCESS_KEY": "test_access_key",
        "COUPANG_SECRET_KEY": "test_secret_key",
        "COUPANG_PARTNER_ID": "test_partner_id",
        "DATABASE_URL": "sqlite:///test.db",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def temp_database():
    """임시 데이터베이스 파일 생성 픽스처"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # 정리
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_project_dir():
    """임시 프로젝트 디렉토리 생성 픽스처"""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)

        # 기본 디렉토리 구조 생성
        (project_dir / "data").mkdir()
        (project_dir / "logs").mkdir()
        (project_dir / "config").mkdir()
        (project_dir / "src").mkdir()

        yield project_dir
