"""
로깅 시스템 유틸리티
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger

from ..utils.env_loader import get_log_level, get_env_var


def setup_logger(
    log_file: Optional[str] = None,
    log_level: Optional[str] = None,
    enable_console: bool = True,
) -> None:
    """
    로거 설정을 초기화합니다.

    Args:
        log_file: 로그 파일 경로
        log_level: 로그 레벨
        enable_console: 콘솔 출력 여부
    """
    # 기본 로거 제거
    logger.remove()

    # 로그 레벨 설정
    if log_level is None:
        log_level = get_log_level()

    # 로그 파일 경로 설정
    if log_file is None:
        log_file = get_env_var("LOG_FILE_PATH", "logs/application.log")

    # 로그 디렉토리 생성
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 파일 핸들러 추가
    logger.add(
        log_file,
        rotation="10 MB",
        retention="30 days",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | "
        "{name}:{function}:{line} | {message}",
        compression="zip",
    )

    # 콘솔 핸들러 추가
    if enable_console:
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level}</level> | <cyan>{name}</cyan>:"
            "<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
        )

    logger.info(f"로거 초기화 완료 - 레벨: {log_level}, 파일: {log_file}")


def get_logger(name: str = __name__):
    """
    로거 인스턴스를 가져옵니다.

    Args:
        name: 로거 이름

    Returns:
        로거 인스턴스
    """
    return logger.bind(name=name)


# 모듈 로드 시 자동으로 로거 초기화
setup_logger()
