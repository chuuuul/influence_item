# YouTube Data API v3 연동 설정 가이드

이 문서는 YouTube Data API v3 연동을 위한 완전한 설정 가이드입니다.

## 🚀 구현 완료 사항

### ✅ 1. YouTube Data API v3 클라이언트 구현
- **파일**: `src/youtube_api/youtube_client.py`
- **기능**:
  - 채널 정보 추출 (채널명, 구독자 수, 설명)
  - 영상 메타데이터 추출 (제목, 설명, 업로드 일자, 조회수, 좋아요)
  - URL 파싱 및 ID 추출
  - 캐싱 메커니즘으로 중복 요청 방지
  - 에러 처리 및 재시도 로직

### ✅ 2. API 할당량 관리 시스템
- **파일**: `src/youtube_api/quota_manager.py`
- **기능**:
  - 일일 10,000 요청 제한 관리
  - SQLite 기반 영구 저장
  - 요청 추적 및 통계
  - 할당량 초과 방지
  - 스레드 세이프 구현

### ✅ 3. 파이프라인 통합
- **파일**: `src/gemini_analyzer/pipeline.py`
- **변경사항**:
  - 하드코딩된 채널 정보를 실제 YouTube API로 교체
  - `_extract_channel_metrics()` 메서드에서 실제 API 데이터 사용
  - `_get_video_metadata()` 메서드로 비디오 정보 추출
  - `_map_to_prd_schema()` 메서드에서 실제 메타데이터 사용

### ✅ 4. 설정 파일 업데이트
- **파일**: `config/config.py`
- **추가된 설정**:
  - `YOUTUBE_API_KEY`: YouTube Data API v3 키
  - `YOUTUBE_API_DAILY_QUOTA`: 일일 할당량 (기본: 10,000)
  - `YOUTUBE_API_TIMEOUT`: API 타임아웃
  - `YOUTUBE_API_MAX_RETRIES`: 최대 재시도 횟수
  - `YOUTUBE_API_CACHE_TTL`: 캐시 유지 시간

## 🔧 설치 및 설정

### 1. 의존성 설치

```bash
pip install google-api-python-client google-auth google-auth-httplib2
```

또는 requirements.txt를 사용:

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Console에서 API 키 발급

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성 또는 선택
3. API 및 서비스 > 라이브러리로 이동
4. "YouTube Data API v3" 검색 및 활성화
5. 사용자 인증 정보 > API 키 생성
6. API 키 제한 설정 (선택사항):
   - Application restrictions: None (또는 IP 주소 제한)
   - API restrictions: YouTube Data API v3만 선택

### 3. 환경 변수 설정

`.env` 파일에 API 키 추가:

```bash
# YouTube Data API v3 키
YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY_HERE

# 또는 기존 Google API 키 사용 (YouTube API도 지원하는 경우)
GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY_HERE

# 선택적 설정
YOUTUBE_API_DAILY_QUOTA=10000
YOUTUBE_API_TIMEOUT=30
YOUTUBE_API_MAX_RETRIES=3
YOUTUBE_API_CACHE_TTL=3600
```

## 🧪 테스트 실행

### 통합 테스트 실행

```bash
python test_youtube_api_integration.py
```

### 테스트 항목

1. **할당량 관리자 테스트**
   - 할당량 상태 확인
   - 요청 기록 및 추적

2. **YouTube 클라이언트 초기화**
   - API 키 유효성 검사
   - 서비스 객체 생성

3. **URL 파싱 테스트**
   - 다양한 YouTube URL 형식 파싱
   - 비디오 ID 추출

4. **비디오 정보 추출**
   - 제목, 설명, 조회수, 좋아요 수
   - 업로드 일자, 영상 길이

5. **채널 정보 추출**
   - 채널명, 구독자 수, 영상 수
   - 총 조회수, 생성일, 인증 여부

6. **캐시 기능 테스트**
   - 첫 요청 시 API 호출
   - 두 번째 요청 시 캐시 사용

7. **파이프라인 통합 테스트**
   - 비디오 메타데이터 추출
   - 채널 메트릭스 추출

8. **에러 처리 테스트**
   - 잘못된 URL 처리
   - 존재하지 않는 비디오 처리

## 📊 API 사용량 모니터링

### 할당량 상태 확인

```python
from src.youtube_api.quota_manager import QuotaManager

quota_manager = QuotaManager()
status = quota_manager.get_status()
print(f"사용량: {status['requests_made']}/{status['daily_limit']}")
print(f"사용률: {status['usage_percentage']:.1f}%")
```

### 사용량 히스토리 조회

```python
history = quota_manager.get_usage_history(days=7)
for day in history:
    print(f"{day['date']}: {day['requests_made']}회 사용")
```

### 요청 통계 확인

```python
stats = quota_manager.get_request_stats(days=7)
print(f"성공률: {stats['success_rate']:.1f}%")
print(f"총 요청: {stats['total_requests']}회")
```

## 💡 사용 예시

### 기본 사용법

```python
import asyncio
from src.youtube_api.youtube_client import YouTubeAPIClient

async def main():
    client = YouTubeAPIClient(api_key="YOUR_API_KEY")
    
    # 비디오 정보 추출
    video_info = await client.get_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print(f"제목: {video_info.title}")
    print(f"조회수: {video_info.view_count:,}회")
    
    # 채널 정보 추출
    channel_info = await client.get_channel_info_from_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print(f"채널: {channel_info.channel_name}")
    print(f"구독자: {channel_info.subscriber_count:,}명")

asyncio.run(main())
```

### 파이프라인에서 사용

```python
from src.gemini_analyzer.pipeline import analyze_youtube_video

# 기존 파이프라인에 YouTube API가 자동으로 통합됨
result = await analyze_youtube_video("https://www.youtube.com/watch?v=VIDEO_ID")
```

## 🚨 주의사항

### API 할당량 관리

- **일일 제한**: 10,000 요청/일 (무료 티어)
- **비용**: 무료 할당량 초과 시 요청당 과금
- **모니터링**: 할당량 관리자가 자동으로 추적

### 에러 처리

- **401 Unauthorized**: API 키 확인
- **403 Forbidden**: 할당량 초과 또는 API 비활성화
- **404 Not Found**: 존재하지 않는 비디오/채널
- **429 Too Many Requests**: 요청 빈도 제한

### 최적화 팁

1. **캐싱 활용**: 동일한 요청은 1시간 캐시 사용
2. **배치 처리**: 가능한 경우 여러 ID를 한 번에 요청
3. **할당량 분산**: 피크 시간 피하고 요청 분산
4. **에러 재시도**: 일시적 오류에 대한 지수 백오프

## 🔍 문제 해결

### 일반적인 문제

1. **API 키 오류**
   ```
   YouTubeAPIError: YouTube API 인증 실패
   ```
   → API 키 확인 및 YouTube Data API v3 활성화

2. **할당량 초과**
   ```
   YouTubeAPIError: API 할당량 초과
   ```
   → 내일까지 대기 또는 Google Cloud에서 할당량 증설

3. **모듈 import 오류**
   ```
   ImportError: No module named 'googleapiclient'
   ```
   → `pip install google-api-python-client` 실행

### 디버깅

로그 레벨을 DEBUG로 설정하여 상세 정보 확인:

```python
import logging
logging.getLogger('src.youtube_api').setLevel(logging.DEBUG)
```

## 📈 성능 지표

### 예상 응답 시간

- **비디오 정보**: ~200-500ms
- **채널 정보**: ~300-700ms
- **캐시 히트**: ~1-5ms

### 메모리 사용량

- **클라이언트 객체**: ~5-10MB
- **캐시 (100개 항목)**: ~1-2MB
- **할당량 DB**: ~100KB-1MB

## 🎯 다음 단계

1. **고급 기능 추가**
   - 플레이리스트 정보 추출
   - 댓글 데이터 수집
   - 실시간 스트림 정보

2. **성능 최적화**
   - Redis 캐싱 도입
   - 비동기 배치 처리
   - CDN 활용

3. **모니터링 강화**
   - Prometheus 메트릭
   - Grafana 대시보드
   - 알림 시스템

---

## ✅ 완료된 작업 요약

1. ✅ YouTube Data API v3 디렉토리 및 구조 생성
2. ✅ YouTube Data API v3 클라이언트 구현 (youtube_client.py)
3. ✅ API 할당량 관리 시스템 구현 (quota_manager.py)
4. ✅ pipeline.py의 하드코딩된 영상 정보 부분을 YouTube API로 교체
5. ✅ 설정 파일에 YouTube API 키 추가
6. ✅ 통합 테스트 및 실제 API 동작 검증 스크립트 작성

**YouTube Data API v3 연동이 완전히 구현되었습니다!** 🎉