#!/usr/bin/env python3
"""
Python 스케줄러를 사용한 자동 실행
"""

import schedule
import time
import asyncio
import logging
from datetime import datetime
import subprocess
import sys
from pathlib import Path

# 프로젝트 루트 경로
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_daily_discovery():
    """매일 채널 탐색 실행"""
    try:
        logger.info("🚀 매일 채널 탐색 시작")
        
        # Python 스크립트 실행
        script_path = project_root / "scripts" / "daily_channel_discovery.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if result.returncode == 0:
            logger.info("✅ 채널 탐색 완료")
            logger.info(f"출력: {result.stdout[-500:]}")  # 마지막 500자만
        else:
            logger.error("❌ 채널 탐색 실패")
            logger.error(f"오류: {result.stderr}")
            
    except Exception as e:
        logger.error(f"❌ 실행 중 오류: {str(e)}")

def main():
    """메인 스케줄러"""
    logger.info("📅 Python 스케줄러 시작")
    
    # 매일 9시에 실행 스케줄 등록
    schedule.every().day.at("09:00").do(run_daily_discovery)
    
    # 테스트용: 1분마다 실행 (개발시에만 사용)
    # schedule.every(1).minutes.do(run_daily_discovery)
    
    logger.info("⏰ 스케줄 등록 완료: 매일 09:00")
    logger.info("🔄 스케줄러 실행 중... (Ctrl+C로 종료)")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크
            
    except KeyboardInterrupt:
        logger.info("⏹️  스케줄러 종료")

if __name__ == "__main__":
    main()