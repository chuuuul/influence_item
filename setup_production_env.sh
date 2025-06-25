#!/bin/bash
# 프로덕션 환경변수 설정 스크립트

echo "🔒 프로덕션 환경변수 설정"

# 보안 키 설정
export SECRET_KEY="DV7vkRILE4djlmQw11di_yNB9l56suqw8xw4s_umoTQ"
export JWT_SECRET="0YR81fU9_2AO-aWDd0MokxudS-qlZFuzz1jP_WHZwNs"
export ENCRYPTION_KEY="NFo0VzRLamFzRF9GSF92N3lRM2VmTW5CN3hmZE92WlpjYXRsdjNNOTg2TT0="

# 기본 설정
export ENVIRONMENT=production
export DEBUG=false
export LOG_LEVEL=INFO

# 허용된 호스트 (실제 도메인으로 변경 필요)
export ALLOWED_HOSTS="your-domain.com,api.your-domain.com"
export CORS_ORIGINS="https://your-domain.com,https://app.your-domain.com"

echo "✅ 환경변수 설정 완료"
echo "⚠️  실제 API 키들을 설정해주세요:"
echo "   export YOUTUBE_API_KEY='your_youtube_api_key'"
echo "   export GEMINI_API_KEY='your_gemini_api_key'"
echo "   export COUPANG_API_KEY='your_coupang_api_key'"
