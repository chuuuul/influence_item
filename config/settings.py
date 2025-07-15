"""
Configuration settings for the influence item system.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Database settings
DATABASE_PATH = Path(
    os.getenv("DATABASE_PATH", PROJECT_ROOT / "data" / "influence_item.db")
)

# API keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COUPANG_PARTNERS_ACCESS_KEY = os.getenv("COUPANG_PARTNERS_ACCESS_KEY")
COUPANG_PARTNERS_SECRET_KEY = os.getenv("COUPANG_PARTNERS_SECRET_KEY")

# Google Sheets settings
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE_PATH = Path(
    os.getenv("LOG_FILE_PATH", PROJECT_ROOT / "logs" / "application.log")
)

# Application settings
MAX_ANALYSIS_WORKERS = int(os.getenv("MAX_ANALYSIS_WORKERS", "3"))
VIDEO_DOWNLOAD_PATH = Path(
    os.getenv("VIDEO_DOWNLOAD_PATH", PROJECT_ROOT / "data" / "temp_videos")
)
ANALYSIS_RESULTS_PATH = Path(
    os.getenv("ANALYSIS_RESULTS_PATH", PROJECT_ROOT / "data" / "analysis_results")
)

# Streamlit settings
STREAMLIT_SERVER_PORT = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
STREAMLIT_SERVER_ADDRESS = os.getenv("STREAMLIT_SERVER_ADDRESS", "localhost")

# Development/Debug settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
ENABLE_ANALYSIS_CACHE = os.getenv("ENABLE_ANALYSIS_CACHE", "True").lower() == "true"
MOCK_AI_RESPONSES = os.getenv("MOCK_AI_RESPONSES", "False").lower() == "true"

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "change_this_to_a_random_string_in_production")

# External services
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
)

# Performance settings
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))

# Paths
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"

# Required environment variables for production
REQUIRED_ENV_VARS = [
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
]

# Optional environment variables (will show warnings if missing)
OPTIONAL_ENV_VARS = [
    "OPENAI_API_KEY",
    "COUPANG_PARTNERS_ACCESS_KEY",
    "COUPANG_PARTNERS_SECRET_KEY",
    "GOOGLE_SHEETS_CREDENTIALS_PATH",
    "GOOGLE_SHEETS_SPREADSHEET_ID",
]


def create_directories():
    """Create necessary directories if they don't exist."""
    directories = [DATA_DIR, LOGS_DIR, VIDEO_DOWNLOAD_PATH, ANALYSIS_RESULTS_PATH]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def validate_environment(strict: bool = False):
    """
    Validate environment variables.

    Args:
        strict: If True, raise error for missing optional variables too
    """
    missing_required = []
    missing_optional = []

    # Check required variables
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing_required.append(var)

    # Check optional variables
    for var in OPTIONAL_ENV_VARS:
        if not os.getenv(var):
            missing_optional.append(var)

    if missing_required:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_required)}"
        )

    if missing_optional:
        warning_msg = (
            f"Missing optional environment variables: {', '.join(missing_optional)}"
        )
        if strict:
            raise ValueError(warning_msg)
        else:
            print(f"Warning: {warning_msg}")

    return True


def get_database_url() -> str:
    """Get database URL in SQLite format."""
    return f"sqlite:///{DATABASE_PATH}"


def is_development() -> bool:
    """Check if running in development mode."""
    return DEBUG_MODE


def get_log_level() -> str:
    """Get the logging level."""
    return LOG_LEVEL.upper()


# Initialize directories on import
create_directories()
