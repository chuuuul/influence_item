#!/bin/bash
# 복구 스크립트

set -e

if [ $# -eq 0 ]; then
    echo "사용법: $0 <backup_date>"
    echo "예: $0 20241225_120000"
    exit 1
fi

BACKUP_DATE=$1
BACKUP_DIR="backup"

echo "🔄 복구 시작: $BACKUP_DATE"

# 서비스 중지
echo "⏹️ 서비스 중지"
docker-compose -f docker-compose.production.yml down

# 데이터베이스 복구
if [ -f "$BACKUP_DIR/db_backup_$BACKUP_DATE.sql" ]; then
    echo "🗄️ 데이터베이스 복구"
    docker-compose -f docker-compose.production.yml up -d postgres
    sleep 10
    docker-compose -f docker-compose.production.yml exec -T postgres psql -U ${DATABASE_USER} -d ${DATABASE_NAME} < $BACKUP_DIR/db_backup_$BACKUP_DATE.sql
else
    echo "❌ 데이터베이스 백업 파일을 찾을 수 없습니다: $BACKUP_DIR/db_backup_$BACKUP_DATE.sql"
    exit 1
fi

# 로그 복구
if [ -f "$BACKUP_DIR/logs_backup_$BACKUP_DATE.tar.gz" ]; then
    echo "📋 로그 복구"
    tar -xzf $BACKUP_DIR/logs_backup_$BACKUP_DATE.tar.gz
fi

# 서비스 재시작
echo "🚀 서비스 재시작"
docker-compose -f docker-compose.production.yml up -d

echo "✅ 복구 완료"
