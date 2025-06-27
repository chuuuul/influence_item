#!/bin/bash

# .env.n8n 파일 로드
if [ -f "/Users/chul/Documents/claude/influence_item/.env.n8n" ]; then
    export $(cat /Users/chul/Documents/claude/influence_item/.env.n8n | grep -v '^#' | xargs)
    echo ".env.n8n 파일에서 환경 변수를 로드했습니다."
else
    echo "경고: .env.n8n 파일을 찾을 수 없습니다."
fi

# n8n 데이터 디렉토리 설정 (상위 디렉토리로 설정하여 .n8n이 생성되도록)
export N8N_USER_FOLDER=/Users/chul

# 환경변수 접근 허용 (중요!)
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false

# 중복 설정 파일 방지
unset N8N_CONFIG_FILE
unset N8N_CONFIG_FILES

# 디렉토리 생성
mkdir -p /Users/chul/.n8n
mkdir -p /Users/chul/Documents/claude/influence_item/data/uploads

# 경로 확인 로그
echo "N8N_USER_FOLDER: $N8N_USER_FOLDER"
echo "실제 데이터 위치: $N8N_USER_FOLDER/.n8n/"
echo "데이터베이스 위치: $N8N_USER_FOLDER/.n8n/database.sqlite"

# n8n 시작
echo "n8n을 시작합니다..."
echo "웹 브라우저에서 http://localhost:5678 로 접속하세요."
echo "종료하려면 Ctrl+C를 누르세요."

n8n start