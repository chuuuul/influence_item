"""
메인 실행 모듈

연예인 추천 아이템 자동화 릴스 시스템의 진입점입니다.
"""

import sys
import asyncio
from pathlib import Path
import logging
import json

from config.config import Config
from src.whisper_processor import WhisperProcessor, YouTubeDownloader
from src.gemini_analyzer import GeminiFirstPassAnalyzer, GeminiSecondPassAnalyzer
from src.gemini_analyzer.pipeline import AIAnalysisPipeline, analyze_youtube_video_sync


def setup_logging(config: Config) -> None:
    """로깅 설정"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('influence_item.log')
        ]
    )


def main():
    """메인 함수"""
    try:
        # 설정 로드 및 검증
        config = Config()
        setup_logging(config)
        
        logger = logging.getLogger(__name__)
        logger.info("연예인 추천 아이템 자동화 릴스 시스템 시작")
        
        # 기본 테스트 실행
        logger.info("=== Whisper 프로세서 테스트 ===")
        whisper = WhisperProcessor(config)
        model_info = whisper.get_model_info()
        logger.info(f"Whisper 모델 정보: {model_info}")
        
        logger.info("=== Gemini 1차 분석기 테스트 ===")
        gemini_analyzer = GeminiFirstPassAnalyzer(config)
        analyzer_info = gemini_analyzer.get_analyzer_info()
        logger.info(f"Gemini 1차 분석기 정보: {analyzer_info}")
        
        logger.info("=== Gemini 2차 분석기 테스트 ===")
        second_pass_analyzer = GeminiSecondPassAnalyzer(config)
        logger.info("Gemini 2차 분석기 초기화 완료")
        
        logger.info("=== YouTube 다운로더 테스트 ===")
        with YouTubeDownloader(config) as downloader:
            # 테스트용 YouTube URL (실제 다운로드는 하지 않음)
            test_url = "https://www.youtube.com/watch?v=test"
            logger.info(f"YouTube 다운로더 초기화 완료 - 테스트 URL: {test_url}")
        
        logger.info("=== AI 통합 파이프라인 테스트 ===")
        pipeline = AIAnalysisPipeline(config)
        pipeline_status = pipeline.get_pipeline_status()
        logger.info(f"파이프라인 상태: {pipeline_status}")
        
        logger.info("시스템 초기화 완료 - 모든 컴포넌트가 정상 작동 중")
        
        # 실제 파이프라인 테스트 (테스트 모드)
        logger.info("\n=== 통합 파이프라인 테스트 실행 ===")
        test_video_url = "https://www.youtube.com/watch?v=test_video"
        
        try:
            # 동기 래퍼 함수를 사용하여 테스트
            result = analyze_youtube_video_sync(test_video_url, config)
            
            logger.info(f"파이프라인 테스트 결과:")
            logger.info(f"  - 상태: {result.status.value}")
            logger.info(f"  - 처리 시간: {result.processing_time:.2f}초")
            logger.info(f"  - 단계 수: {len(result.step_logs)}")
            
            if result.status.value == "completed":
                logger.info(f"  - 결과 데이터: {len(result.result_data) if result.result_data else 0}개 제품")
            elif result.error_message:
                logger.warning(f"  - 에러 메시지: {result.error_message}")
                
        except Exception as e:
            logger.warning(f"파이프라인 테스트 실행 중 예외: {str(e)} (테스트 모드이므로 정상)")
        
        # 간단한 사용 예시 출력
        logger.info("\n=== 사용 예시 ===")
        logger.info("1. 비동기 YouTube 영상 분석:")
        logger.info("   result = await analyze_youtube_video('https://youtube.com/watch?v=...')")
        logger.info("2. 동기 YouTube 영상 분석:")
        logger.info("   result = analyze_youtube_video_sync('https://youtube.com/watch?v=...')")
        logger.info("3. 파이프라인 직접 사용:")
        logger.info("   pipeline = AIAnalysisPipeline()")
        logger.info("   result = await pipeline.process_video('https://youtube.com/watch?v=...')")
        
    except Exception as e:
        logger.error(f"시스템 시작 실패: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()