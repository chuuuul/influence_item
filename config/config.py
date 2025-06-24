"""
설정 관리 모듈

환경 변수와 기본 설정을 관리합니다.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Config:
    """애플리케이션 설정 클래스"""
    
    # API 키
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", os.getenv("GOOGLE_API_KEY", ""))  # YouTube Data API v3 키 (Google API 키와 동일할 수 있음)
    COUPANG_ACCESS_KEY: str = os.getenv("COUPANG_ACCESS_KEY", "")
    COUPANG_SECRET_KEY: str = os.getenv("COUPANG_SECRET_KEY", "")
    
    # Google Sheets API 설정
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_SHEETS_SCOPE: list = ["https://www.googleapis.com/auth/spreadsheets"]
    
    # Whisper 모델 설정
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "small")
    
    # Gemini API 설정
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001")
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "8192"))
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
    GEMINI_TIMEOUT: int = int(os.getenv("GEMINI_TIMEOUT", "60"))
    
    # Gemini API 키 로테이션 설정
    GEMINI_API_KEYS: list = [key.strip() for key in os.getenv("GEMINI_API_KEYS", os.getenv("GOOGLE_API_KEY", "")).split(",") if key.strip()]
    GEMINI_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("GEMINI_RATE_LIMIT_PER_MINUTE", "60"))
    GEMINI_RATE_LIMIT_PER_DAY: int = int(os.getenv("GEMINI_RATE_LIMIT_PER_DAY", "1500"))
    GEMINI_RETRY_DELAYS: list = [1, 2, 4, 8, 16]  # 지수 백오프
    
    # 파일 경로 설정
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", "/tmp/influence_item"))
    PROJECT_ROOT: Path = Path(__file__).parent
    
    # SSL/TLS 설정
    SSL_CERT_PATH: str = os.getenv("SSL_CERT_PATH", "/etc/ssl/certs/server.crt")
    SSL_KEY_PATH: str = os.getenv("SSL_KEY_PATH", "/etc/ssl/private/server.key")
    SSL_CA_PATH: str = os.getenv("SSL_CA_PATH", "/etc/ssl/certs/ca.crt")
    USE_SSL: bool = os.getenv("USE_SSL", "false").lower() == "true"
    SSL_VERIFY: bool = os.getenv("SSL_VERIFY", "true").lower() == "true"
    
    # 서버 및 네트워크 설정
    DOMAIN_NAME: str = os.getenv("DOMAIN_NAME", "localhost")
    GPU_SERVER_URL: str = os.getenv("GPU_SERVER_URL", "http://localhost:8001")
    CPU_SERVER_URL: str = os.getenv("CPU_SERVER_URL", "http://localhost:8501")
    API_SERVER_PORT: int = int(os.getenv("API_SERVER_PORT", "8000"))
    
    # 로깅 설정
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 처리 설정
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "300"))
    
    # OCR 설정
    OCR_LANGUAGES: list = os.getenv("OCR_LANGUAGES", "ko,en").split(",")
    OCR_CONFIDENCE_THRESHOLD: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.5"))
    USE_GPU: bool = os.getenv("USE_GPU", "true").lower() == "true"
    
    # 이미지 처리 설정
    MAX_IMAGE_SIZE: int = int(os.getenv("MAX_IMAGE_SIZE", "2048"))
    MIN_IMAGE_SIZE: int = int(os.getenv("MIN_IMAGE_SIZE", "64"))
    
    # YOLO 객체 탐지 설정
    YOLO_MODEL_NAME: str = os.getenv("YOLO_MODEL_NAME", "yolo11n.pt")
    YOLO_CONFIDENCE_THRESHOLD: float = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.25"))
    YOLO_IOU_THRESHOLD: float = float(os.getenv("YOLO_IOU_THRESHOLD", "0.45"))
    YOLO_IMAGE_SIZE: int = int(os.getenv("YOLO_IMAGE_SIZE", "640"))
    
    # GPU 최적화 설정
    GPU_BATCH_SIZE: int = int(os.getenv("GPU_BATCH_SIZE", "8"))
    GPU_MEMORY_FRACTION: float = float(os.getenv("GPU_MEMORY_FRACTION", "0.9"))
    ENABLE_GPU_OPTIMIZATION: bool = os.getenv("ENABLE_GPU_OPTIMIZATION", "true").lower() == "true"
    AUTO_BATCH_SIZE: bool = os.getenv("AUTO_BATCH_SIZE", "true").lower() == "true"
    BASELINE_THROUGHPUT: float = float(os.getenv("BASELINE_THROUGHPUT", "10.0"))
    
    # 음성+시각 데이터 융합 설정
    FUSION_TIME_TOLERANCE: float = float(os.getenv("FUSION_TIME_TOLERANCE", "2.0"))
    TEXT_SIMILARITY_THRESHOLD: float = float(os.getenv("TEXT_SIMILARITY_THRESHOLD", "0.6"))
    FUSION_CONFIDENCE_THRESHOLD: float = float(os.getenv("FUSION_CONFIDENCE_THRESHOLD", "0.7"))
    
    # YouTube Data API v3 설정
    YOUTUBE_API_DAILY_QUOTA: int = int(os.getenv("YOUTUBE_API_DAILY_QUOTA", "10000"))  # 일일 할당량
    YOUTUBE_API_TIMEOUT: int = int(os.getenv("YOUTUBE_API_TIMEOUT", "30"))
    YOUTUBE_API_MAX_RETRIES: int = int(os.getenv("YOUTUBE_API_MAX_RETRIES", "3"))
    YOUTUBE_API_RETRY_DELAY: float = float(os.getenv("YOUTUBE_API_RETRY_DELAY", "1.0"))
    YOUTUBE_API_CACHE_TTL: int = int(os.getenv("YOUTUBE_API_CACHE_TTL", "3600"))  # 1시간 캐시
    YOUTUBE_API_ENABLE_CACHE: bool = os.getenv("YOUTUBE_API_ENABLE_CACHE", "true").lower() == "true"
    
    # 쿠팡 파트너스 API 설정
    COUPANG_API_TIMEOUT: int = int(os.getenv("COUPANG_API_TIMEOUT", "30"))
    COUPANG_MAX_RETRIES: int = int(os.getenv("COUPANG_MAX_RETRIES", "3"))
    COUPANG_RETRY_DELAY: float = float(os.getenv("COUPANG_RETRY_DELAY", "1.0"))
    COUPANG_REQUEST_LIMIT_PER_HOUR: int = int(os.getenv("COUPANG_REQUEST_LIMIT_PER_HOUR", "9"))  # 안전 마진
    COUPANG_SEARCH_LIMIT: int = int(os.getenv("COUPANG_SEARCH_LIMIT", "50"))
    COUPANG_CACHE_TTL: int = int(os.getenv("COUPANG_CACHE_TTL", "3600"))  # 1시간 캐시
    
    # 예산 관리 설정 (PRD 기준)
    MONTHLY_BUDGET: float = float(os.getenv("MONTHLY_BUDGET", "15000.0"))  # 월 예산 15,000원
    BUDGET_WARNING_THRESHOLD: float = float(os.getenv("BUDGET_WARNING_THRESHOLD", "0.70"))  # 70% 경고
    BUDGET_ALERT_THRESHOLD: float = float(os.getenv("BUDGET_ALERT_THRESHOLD", "0.80"))  # 80% 주의
    BUDGET_CRITICAL_THRESHOLD: float = float(os.getenv("BUDGET_CRITICAL_THRESHOLD", "0.90"))  # 90% 위험
    BUDGET_EMERGENCY_THRESHOLD: float = float(os.getenv("BUDGET_EMERGENCY_THRESHOLD", "0.95"))  # 95% 비상
    BUDGET_STOP_THRESHOLD: float = float(os.getenv("BUDGET_STOP_THRESHOLD", "1.00"))  # 100% 중단
    
    # YouTube 다운로드 설정
    YT_DLP_OPTS: dict = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'wav',
        'outtmpl': str(TEMP_DIR / '%(title)s.%(ext)s'),
        'noplaylist': True,
    }
    
    @classmethod
    def validate(cls) -> None:
        """설정 유효성 검사"""
        if not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # YouTube API 키 확인 (GOOGLE_API_KEY로 대체 가능)
        if not cls.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다. GOOGLE_API_KEY 또는 YOUTUBE_API_KEY를 설정하세요.")
            
        # 쿠팡 API 키는 선택사항이지만 둘 다 설정되어야 함
        if bool(cls.COUPANG_ACCESS_KEY) != bool(cls.COUPANG_SECRET_KEY):
            raise ValueError("COUPANG_ACCESS_KEY와 COUPANG_SECRET_KEY는 둘 다 설정되거나 둘 다 비어있어야 합니다.")
        
        # 임시 디렉토리 생성
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
    @classmethod
    def get_temp_dir(cls) -> Path:
        """임시 디렉토리 경로 반환"""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        return cls.TEMP_DIR