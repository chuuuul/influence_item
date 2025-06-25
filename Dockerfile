# 프로덕션용 Dockerfile
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    wget \
    ffmpeg \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 사용자 생성 (보안)
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY --chown=app:app . .

# 로그 디렉토리 생성
RUN mkdir -p /app/logs && chown -R app:app /app/logs

# 포트 노출
EXPOSE 8000 8501

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 사용자로 전환
USER app

# 애플리케이션 시작
CMD ["python", "-m", "uvicorn", "secure_api_server:app", "--host", "0.0.0.0", "--port", "8000"]
