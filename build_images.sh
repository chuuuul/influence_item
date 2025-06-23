#!/bin/bash
# Docker 이미지 빌드 스크립트

set -e

echo "🚀 Building Docker images for Influence Item system..."

# GPU 서버 이미지 빌드
echo "📦 Building GPU server image..."
docker build -f Dockerfile.gpu -t influence-item/gpu-server:latest .

# CPU 서버 이미지 빌드  
echo "📦 Building CPU server image..."
docker build -f Dockerfile.cpu -t influence-item/cpu-server:latest .

echo "✅ All images built successfully!"

# 이미지 목록 표시
echo "📋 Built images:"
docker images | grep influence-item

echo ""
echo "🎯 Next steps:"
echo "1. Copy .env.template to .env and configure your API keys"
echo "2. Run: docker-compose up -d"
echo "3. Access dashboard at: http://localhost:8501"